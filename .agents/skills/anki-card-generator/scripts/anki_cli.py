#!/usr/bin/env python3
"""
Unified Anki Card Generator CLI for Multi-Course Flashcard Workflows.

Subcommands:
1. inspect:
   Downloads a source PDF from Google Drive (by URL or File ID) or reads a local PDF,
   auto-detects the Course Code (e.g. "MBB 321" / "MBB321") and Session number,
   extracts all slide text, handwritten margin annotations, and embedded images,
   and checks the shared Google Drive folder for an existing "<COURSE>*.apkg" deck.

2. sync:
   Takes a JSON file of generated notes (`cards.json`), finds or creates the
   course's `.apkg` file (`<COURSE>*.apkg` or `<COURSE> - Flashcards.apkg`),
   updates/inserts the notes (and optional media images), and syncs the `.apkg`
   directly to the shared Google Drive folder.
"""

import os
import re
import sys
import json
import time
import zlib
import glob
import random
import string
import shutil
import zipfile
import sqlite3
import tempfile
import argparse
from pathlib import Path

import pymupdf
import genanki
import zstandard as zstd

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

SCOPES = ['https://www.googleapis.com/auth/drive']
CREDENTIALS_FILE = os.path.expanduser('~/.config/gdrive/credentials.json')
TOKEN_FILE = os.path.expanduser('~/.config/gdrive/token.json')
DEFAULT_SHARED_FOLDER_ID = '1JD0rlrkJIFJ6n4hv5Mxc9zLSP-UEZJja'


def get_drive_service():
    """Authenticates and returns the Google Drive API service."""
    from google.oauth2 import service_account

    # 1. Check if Service Account JSON or Token is in environment / Streamlit secrets
    sa_json = os.getenv("GCP_SA_KEY") or os.getenv("GDRIVE_SERVICE_ACCOUNT")
    if sa_json:
        try:
            info = json.loads(sa_json) if isinstance(sa_json, str) and sa_json.startswith('{') else None
            if info:
                creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
                return build('drive', 'v3', credentials=creds)
        except Exception:
            pass

    # 2. Check token from secrets/env
    raw_token = os.getenv("GDRIVE_TOKEN_JSON")
    if raw_token:
        try:
            info = json.loads(raw_token)
            creds = Credentials.from_authorized_user_info(info, SCOPES)
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
            return build('drive', 'v3', credentials=creds)
        except Exception:
            pass

    # 3. Check local file paths
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            cred_path = CREDENTIALS_FILE if os.path.exists(CREDENTIALS_FILE) else "credentials.json"
            if not os.path.exists(cred_path):
                raise RuntimeError(
                    "Google Drive credentials not found on cloud server. "
                    "For private files, add GCP_SA_KEY or GDRIVE_TOKEN_JSON to Streamlit Secrets, "
                    "or upload the PDF directly using the 'Upload Lecture PDF' tab."
                )
            flow = InstalledAppFlow.from_client_secrets_file(cred_path, SCOPES)
            creds = flow.run_local_server(port=0)
        os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    return build('drive', 'v3', credentials=creds)


def extract_drive_id(url_or_id: str) -> str:
    """Extracts the Google Drive file/folder ID from a URL or returns the ID directly."""
    m = re.search(r'/d/([a-zA-Z0-9_-]+)', url_or_id)
    if m:
        return m.group(1)
    m = re.search(r'id=([a-zA-Z0-9_-]+)', url_or_id)
    if m:
        return m.group(1)
    m = re.search(r'/folders/([a-zA-Z0-9_-]+)', url_or_id)
    if m:
        return m.group(1)
    return url_or_id.strip()


def parse_course_and_session(filename: str):
    """
    Infers course code (e.g. 'MBB 321' / 'MBB321') and session number from filename.
    Example: 'MBB 321 - Session 13 - Annotated.pdf' -> ('MBB 321', 'MBB321', '13')
    """
    base = Path(filename).stem
    course_match = re.search(r'\b([A-Za-z]{2,5})\s*[-_]?\s*(\d{3}[A-Za-z]?)\b', base)
    if course_match:
        dept = course_match.group(1).upper()
        num = course_match.group(2).upper()
        course_display = f"{dept} {num}"
        course_compact = f"{dept}{num}"
    else:
        course_display = "UNKNOWN"
        course_compact = "UNKNOWN"

    session_match = re.search(r'(?:Session|Lecture|Week|Mod|Ch|Chapter)\s*[-_#]?\s*(\d+)', base, re.IGNORECASE)
    session_num = session_match.group(1) if session_match else "1"
    return course_display, course_compact, session_num


def find_course_apkg_on_drive(service, course_compact: str, course_display: str, folder_id: str):
    """
    Searches the shared Google Drive folder (and user's Drive) for an existing .apkg matching the course code.
    Matches either 'MBB321*.apkg' or 'MBB 321*.apkg'.
    """
    query = f"trashed = false and name contains '.apkg' and '{folder_id}' in parents"
    res = service.files().list(q=query, fields="files(id, name, modifiedTime, webViewLink)").execute()
    files = res.get('files', [])

    pattern = re.compile(rf'^({re.escape(course_compact)}|{re.escape(course_display)}).*\.apkg$', re.IGNORECASE)
    matches = [f for f in files if pattern.match(f['name'])]
    if matches:
        # Sort by modifiedTime descending
        matches.sort(key=lambda x: x.get('modifiedTime', ''), reverse=True)
        return matches[0]
    return None


def download_drive_file(service, file_id: str, dest_path: Path) -> Path:
    meta = service.files().get(fileId=file_id, fields='name').execute()
    if dest_path.is_dir():
        dest_path = dest_path / meta['name']
    request = service.files().get_media(fileId=file_id)
    with open(dest_path, 'wb') as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    return dest_path


def cmd_inspect(args):
    """Downloads/reads PDF, extracts text + annotations + images, and reports deck status."""
    work_dir = Path(args.workdir).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    service = get_drive_service()
    source = args.source
    if os.path.exists(source):
        pdf_path = Path(source).resolve()
    else:
        file_id = extract_drive_id(source)
        print(f"Downloading source PDF (Drive ID: {file_id})...")
        pdf_path = download_drive_file(service, file_id, work_dir)
        print(f"Downloaded: {pdf_path.name}")

    course_display, course_compact, session_num = parse_course_and_session(pdf_path.name)
    if args.course:
        course_compact = args.course.replace(" ", "").upper()
        course_display = args.course.upper()
    if args.session:
        session_num = str(args.session)

    # Extract slide text, blocks, and images
    extract_dir = work_dir / "extracted" / f"{course_compact}_Session_{session_num}"
    images_dir = extract_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    doc = pymupdf.open(str(pdf_path))
    slides_data = []
    full_text_lines = [
        f"# Extracted Source: {pdf_path.name}",
        f"- **Course:** {course_display} (`{course_compact}`)",
        f"- **Session:** {session_num}",
        f"- **Total Slides:** {len(doc)}\n"
    ]

    for pno in range(len(doc)):
        page = doc[pno]
        blocks = page.get_text("blocks")
        slide_blocks = []
        full_text_lines.append(f"## Slide {pno + 1}")
        for b in blocks:
            txt = b[4].strip().replace('\n', ' ')
            if txt:
                slide_blocks.append({"x": round(b[0], 1), "y": round(b[1], 1), "text": txt})
                full_text_lines.append(f"- `[{b[0]:.1f}, {b[1]:.1f}]` {txt}")

        # Optionally render slide image or extract embedded images if requested
        slide_images = []
        if args.extract_images:
            # Save full slide snapshot for visual reference / image cards
            pix = page.get_pixmap(dpi=150)
            slide_img_name = f"{course_compact}_S{session_num}_slide_{pno+1:02d}.png"
            slide_img_path = images_dir / slide_img_name
            pix.save(str(slide_img_path))
            slide_images.append(str(slide_img_path))

            # Also extract embedded figures
            for img_idx, img_info in enumerate(page.get_images(full=True)):
                xref = img_info[0]
                base_img = doc.extract_image(xref)
                ext = base_img["ext"]
                fig_name = f"{course_compact}_S{session_num}_slide_{pno+1:02d}_fig_{img_idx+1}.{ext}"
                fig_path = images_dir / fig_name
                with open(fig_path, "wb") as img_f:
                    img_f.write(base_img["image"])
                slide_images.append(str(fig_path))
            if slide_images:
                full_text_lines.append(f"- **Extracted Images:** {', '.join(Path(p).name for p in slide_images)}")

        full_text_lines.append("")
        slides_data.append({
            "slide_number": pno + 1,
            "blocks": slide_blocks,
            "images": slide_images
        })

    markdown_out = extract_dir / "extracted_slides.md"
    json_out = extract_dir / "extracted_slides.json"
    markdown_out.write_text("\n".join(full_text_lines), encoding="utf-8")

    # Check shared Drive folder for existing course .apkg
    remote_deck = find_course_apkg_on_drive(service, course_compact, course_display, args.folder_id)

    summary = {
        "pdf_file": str(pdf_path),
        "course_display": course_display,
        "course_compact": course_compact,
        "session": session_num,
        "num_slides": len(doc),
        "extracted_markdown": str(markdown_out),
        "images_dir": str(images_dir),
        "existing_drive_deck": remote_deck
    }
    json_out.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n=== INSPECTION COMPLETE ===")
    print(f"Course:            {course_display} ({course_compact})")
    print(f"Session:           {session_num}")
    print(f"Total Slides:      {len(doc)}")
    print(f"Extracted Text:    {markdown_out}")
    if remote_deck:
        print(f"Existing Deck:     {remote_deck['name']} (Drive ID: {remote_deck['id']})")
    else:
        print(f"Existing Deck:     None found in folder. Will create new '{course_display} - Flashcards.apkg' on sync.")


def gen_guid():
    chars = string.ascii_letters + string.digits + "!#$%&()*+,-./:;<=>?@[]^_`{|}~"
    return "".join(random.choice(chars) for _ in range(10))


def extract_cloze_numbers(text):
    matches = re.findall(r'\{\{c(\d+)::', text)
    nums = sorted(list(set(int(m) for m in matches)))
    return nums if nums else [1]


def update_existing_apkg(apkg_path: Path, notes_list: list, tag_str: str, replace_session_tag: bool = True, media_files: list = None):
    """Updates an existing Anki 2.1b (.apkg) file with new notes and optional media."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(apkg_path, 'r') as z:
            z.extractall(tmpdir)

        anki21b_path = os.path.join(tmpdir, 'collection.anki21b')
        db_path = os.path.join(tmpdir, 'collection.anki21')

        is_zstd = os.path.exists(anki21b_path)
        if is_zstd:
            dctx = zstd.ZstdDecompressor()
            with open(anki21b_path, 'rb') as ifh, open(db_path, 'wb') as ofh:
                dctx.copy_stream(ifh, ofh)
        elif not os.path.exists(db_path):
            db_path = os.path.join(tmpdir, 'collection.anki2')

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        cur.execute('SELECT mid, did FROM cards JOIN notes ON cards.nid = notes.id LIMIT 1')
        row = cur.fetchone()
        if row:
            mid, did = row
        else:
            cur.execute('SELECT id FROM notetypes WHERE name LIKE "%Cloze%" LIMIT 1')
            mid = cur.fetchone()[0]
            cur.execute('SELECT id FROM decks WHERE name != "Default" LIMIT 1')
            did = cur.fetchone()[0]

        clean_tag = tag_str.strip()
        if replace_session_tag and clean_tag:
            cur.execute('SELECT id FROM notes WHERE tags LIKE ?', (f"%{clean_tag}%",))
            existing_ids = [r[0] for r in cur.fetchall()]
            if existing_ids:
                print(f"Replacing {len(existing_ids)} existing notes with tag '{clean_tag}'...")
                for nid in existing_ids:
                    cur.execute('DELETE FROM cards WHERE nid = ?', (nid,))
                    cur.execute('DELETE FROM notes WHERE id = ?', (nid,))

        now_ts = int(time.time())
        padded_tag = f" {clean_tag} " if clean_tag else ""

        for idx, item in enumerate(notes_list):
            front = item["text"]
            extra = item.get("extra", "")
            item_tag = f" {item['tags'].strip()} " if "tags" in item else padded_tag

            nid = int(time.time() * 1000) + idx * 47 + random.randint(1, 40)
            guid = gen_guid()
            flds = f"{front}\x1f{extra}"
            sfld = front
            csum = zlib.crc32(sfld.encode('utf-8')) & 0xffffffff

            cur.execute('''
                INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data)
                VALUES (?, ?, ?, ?, -1, ?, ?, ?, ?, 0, "")
            ''', (nid, guid, mid, now_ts, item_tag, flds, sfld, csum))

            cloze_nums = extract_cloze_numbers(front)
            for ord_idx in cloze_nums:
                cid = int(time.time() * 1000) + random.randint(1000, 999999)
                cur.execute('''
                    INSERT INTO cards (id, nid, did, ord, mod, usn, type, queue, due, ivl, factor, reps, lapses, left, odue, odid, flags, data)
                    VALUES (?, ?, ?, ?, ?, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, "")
                ''', (cid, nid, did, ord_idx - 1, now_ts))

        conn.commit()
        cur.execute('SELECT count(*) FROM notes')
        tot_notes = cur.fetchone()[0]
        cur.execute('SELECT count(*) FROM cards')
        tot_cards = cur.fetchone()[0]
        conn.close()

        if is_zstd:
            cctx = zstd.ZstdCompressor(level=3)
            with open(db_path, 'rb') as ifh, open(anki21b_path, 'wb') as ofh:
                cctx.copy_stream(ifh, ofh)
            os.remove(db_path)

        with zipfile.ZipFile(apkg_path, 'w', zipfile.ZIP_DEFLATED) as zout:
            for root, _, files in os.walk(tmpdir):
                for f in files:
                    full_p = os.path.join(root, f)
                    rel_p = os.path.relpath(full_p, tmpdir)
                    zout.write(full_p, rel_p)

        return tot_notes, tot_cards


def create_new_apkg(apkg_path: Path, deck_name: str, notes_list: list, tag_str: str, media_files: list = None):
    """Creates a brand-new Cloze .apkg file using genanki when a course has no existing deck."""
    deck_id = random.randrange(1 << 30, 1 << 31)
    deck = genanki.Deck(deck_id, deck_name)
    clean_tag = tag_str.strip().lstrip('#')

    for item in notes_list:
        front = item["text"]
        extra = item.get("extra", "")
        raw_tags = item.get("tags", clean_tag).strip().split()
        note = genanki.Note(
            model=genanki.CLOZE_MODEL,
            fields=[front, extra],
            tags=raw_tags
        )
        deck.add_note(note)

    pkg = genanki.Package(deck)
    if media_files:
        pkg.media_files = [str(m) for m in media_files if os.path.exists(m)]
    pkg.write_to_file(str(apkg_path))
    return len(notes_list), sum(len(extract_cloze_numbers(n["text"])) for n in notes_list)


def cmd_sync(args):
    """Builds/updates the course .apkg from cards.json and syncs it to the shared Google Drive folder."""
    work_dir = Path(args.workdir).resolve()
    cards_file = Path(args.cards).resolve()
    if not cards_file.exists():
        print(f"Error: Cards JSON file not found: {cards_file}")
        sys.exit(1)

    payload = json.loads(cards_file.read_text(encoding="utf-8"))
    course_display = payload.get("course_display", args.course or "MBB 321")
    course_compact = payload.get("course_compact", course_display.replace(" ", ""))
    session_num = str(payload.get("session", args.session or "1"))
    tag_str = payload.get("tag", f"#{course_compact}::Session::{session_num}")
    notes_list = payload.get("notes", [])
    media_files = payload.get("media_files", [])

    if not notes_list:
        print("Error: No notes found in JSON payload.")
        sys.exit(1)

    service = get_drive_service()
    remote_deck = find_course_apkg_on_drive(service, course_compact, course_display, args.folder_id)

    # Check local directory for matching <COURSE>*.apkg
    local_matches = sorted(
        list(work_dir.glob(f"{course_compact}*.apkg")) + list(work_dir.glob(f"{course_display}*.apkg")),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    if remote_deck:
        apkg_path = work_dir / remote_deck['name']
        print(f"Found existing Drive deck: '{remote_deck['name']}' (ID: {remote_deck['id']}). Downloading latest copy...")
        download_drive_file(service, remote_deck['id'], apkg_path)
        tot_notes, tot_cards = update_existing_apkg(
            apkg_path, notes_list, tag_str, replace_session_tag=not args.append, media_files=media_files
        )
    elif local_matches:
        apkg_path = local_matches[0]
        print(f"Found local deck: '{apkg_path.name}'. Updating...")
        tot_notes, tot_cards = update_existing_apkg(
            apkg_path, notes_list, tag_str, replace_session_tag=not args.append, media_files=media_files
        )
    else:
        apkg_name = f"{course_compact} - Flashcards.apkg"
        apkg_path = work_dir / apkg_name
        deck_title = payload.get("deck_name", f"{course_display} - Flashcards")
        print(f"No existing deck found for {course_compact}. Creating new deck: '{apkg_name}'...")
        tot_notes, tot_cards = create_new_apkg(apkg_path, deck_title, notes_list, tag_str, media_files=media_files)

    print(f"Deck updated locally: {apkg_path.name} (Total Notes: {tot_notes}, Total Cards: {tot_cards})")

    # Sync to Google Drive shared folder
    media = MediaFileUpload(str(apkg_path), resumable=True)
    if remote_deck:
        print(f"Syncing updated '{apkg_path.name}' to Google Drive (File ID: {remote_deck['id']})...")
        updated = service.files().update(
            fileId=remote_deck['id'],
            media_body=media,
            fields='id, name, webViewLink, modifiedTime'
        ).execute()
        print(f"Sync complete! Link: {updated.get('webViewLink')}")
    else:
        print(f"Uploading new '{apkg_path.name}' to shared Google Drive folder ({args.folder_id})...")
        file_meta = {
            'name': apkg_path.name,
            'parents': [args.folder_id]
        }
        created = service.files().create(
            body=file_meta,
            media_body=media,
            fields='id, name, webViewLink'
        ).execute()
        print(f"Upload complete! Link: {created.get('webViewLink')}")


def main():
    parser = argparse.ArgumentParser(description="Multi-Course Anki Flashcard CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # inspect
    p_inspect = subparsers.add_parser("inspect", help="Download/inspect lecture PDF and check course deck status")
    p_inspect.add_argument("source", help="Google Drive URL/ID or local PDF path")
    p_inspect.add_argument("-c", "--course", default=None, help="Override course code (e.g. MBB321)")
    p_inspect.add_argument("-s", "--session", default=None, help="Override session number")
    p_inspect.add_argument("--extract-images", action="store_true", help="Extract slide snapshots and embedded figures")
    p_inspect.add_argument("--folder-id", default=DEFAULT_SHARED_FOLDER_ID, help="Shared Google Drive folder ID")
    default_workdir = str(Path(__file__).resolve().parents[4])
    p_inspect.add_argument("-w", "--workdir", default=default_workdir, help="Working directory")

    # sync
    p_sync = subparsers.add_parser("sync", help="Build/update course .apkg from JSON and sync to Google Drive")
    p_sync.add_argument("cards", help="Path to cards JSON file")
    p_sync.add_argument("-c", "--course", default=None, help="Override course code")
    p_sync.add_argument("-s", "--session", default=None, help="Override session number")
    p_sync.add_argument("--append", action="store_true", help="Append notes instead of replacing existing session tag")
    p_sync.add_argument("--folder-id", default=DEFAULT_SHARED_FOLDER_ID, help="Shared Google Drive folder ID")
    p_sync.add_argument("-w", "--workdir", default=default_workdir, help="Working directory")

    args = parser.parse_args()
    if args.command == "inspect":
        cmd_inspect(args)
    elif args.command == "sync":
        cmd_sync(args)


if __name__ == "__main__":
    main()
