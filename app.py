"""
Streamlit Web App for Multi-Course Anki Flashcard Generation.
Features:
- Thin left icon rail with popover menus for Google Account (👤) and Settings (⚙️).
- Instant "Fetch from Drive" on pressing Enter (with "Press Enter to apply" hidden).
- Course & Session/Lecture controls aligned on the same row as the "Generate Anki Flashcards" CTA.
"""

import os
import sys
import json
import tempfile
import importlib
from pathlib import Path
from dotenv import load_dotenv

import streamlit as st
import pymupdf

# Load .env
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

# Add scripts to sys.path
sys.path.insert(0, str(BASE_DIR / ".agents" / "skills" / "anki-card-generator" / "scripts"))
sys.path.insert(0, str(BASE_DIR))
import anki_cli
import generator
import google_auth

importlib.reload(anki_cli)
importlib.reload(google_auth)
importlib.reload(generator)

# Configure Streamlit page (hide bulky default sidebar)
st.set_page_config(
    page_title="Anki Flashcard Studio",
    page_icon="📇",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS:
# 1. Hide default sidebar and header clutter
# 2. Hide "Press Enter to apply" input instructions
# 3. Style thin left icon rail and align the Generate CTA row
st.markdown("""
<style>
    [data-testid="stSidebar"], [data-testid="collapsedControl"] {
        display: none !important;
    }
    [data-testid="InputInstructions"] {
        display: none !important;
    }
    .block-container {
        padding-top: 2rem !important;
        max-width: 1200px !important;
    }
    .main-title {
        font-size: 2.1rem;
        font-weight: 700;
        color: #1E88E5;
        margin-bottom: 0.1rem;
        line-height: 1.2;
    }
    .sub-title {
        font-size: 1.0rem;
        color: #666;
        margin-bottom: 1.2rem;
    }
    /* Style the thin left utility rail */
    div[data-testid="stHorizontalBlock"] > div:first-child .stPopover > button {
        width: 44px !important;
        height: 44px !important;
        padding: 0 !important;
        border-radius: 10px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        font-size: 1.25rem !important;
    }
    /* Hide the tiny down-chevron inside the icon-only popover buttons */
    div[data-testid="stHorizontalBlock"] > div:first-child .stPopover > button svg {
        display: none !important;
    }
</style>
""", unsafe_allow_html=True)

# Determine redirect URI safely
redirect_uri = google_auth.safe_get_secret("REDIRECT_URI")
if not redirect_uri:
    if os.path.exists("/home/daniel"):
        redirect_uri = "http://localhost:8501/"
    else:
        redirect_uri = "https://mara-anki-studio.streamlit.app/"

# Initialize Google Auth
drive_service, user_auth_info = google_auth.init_google_auth(redirect_uri)
is_logged_in = bool(drive_service and isinstance(user_auth_info, str) and not user_auth_info.startswith("http"))

# Layout: Thin left utility rail + Main content area
rail_col, main_col = st.columns([0.06, 0.94], gap="medium")

with rail_col:
    # 1. Top icon: Login / Account popover
    login_icon = "🟢" if is_logged_in else "👤"
    with st.popover(login_icon, help="Google Account"):
        st.markdown("##### 👤 Google Account")
        if is_logged_in:
            st.success(f"Signed in as:\n**{user_auth_info}**")
            if st.button("Log out", use_container_width=True):
                google_auth.clear_cached_creds()
                st.rerun()
        elif isinstance(user_auth_info, str) and user_auth_info.startswith("http"):
            st.link_button("🔑 Sign in with Google", user_auth_info, use_container_width=True)
            st.caption("Sign in to fetch private files and sync decks to Google Drive.")
        else:
            st.caption("Add GOOGLE_CLIENT_ID & GOOGLE_CLIENT_SECRET to enable Google Sign-In.")

    # 2. Second icon right under: Settings popover
    with st.popover("⚙️", help="Settings"):
        st.markdown("##### ⚙️ Settings")
        default_key = google_auth.safe_get_secret("GEMINI_API_KEY")
        api_key = st.text_input("Gemini API Key", value=default_key, type="password")
        folder_id = st.text_input("Target Google Drive Folder ID", value=anki_cli.DEFAULT_SHARED_FOLDER_ID)


def fetch_drive_pdf(drive_url_str: str):
    """Downloads a PDF from Google Drive (via signed-in account, public link, or local credentials) and updates session_state."""
    if not drive_url_str or not drive_url_str.strip():
        return
    fid = anki_cli.extract_drive_id(drive_url_str)
    dest = BASE_DIR / "extracted" / f"drive_download_{fid}.pdf"
    dest.parent.mkdir(parents=True, exist_ok=True)
    download_success = False
    last_err = None

    # Try 1: Signed-in User Drive Service (preserves original filename!)
    if drive_service:
        try:
            downloaded_path = anki_cli.download_drive_file(drive_service, fid, BASE_DIR / "extracted")
            st.session_state["uploaded_pdf_path"] = str(downloaded_path)
            st.session_state["uploaded_pdf_name"] = downloaded_path.name
            download_success = True
        except Exception as e:
            last_err = e

    # Try 2: Direct public download (no login needed if link is shared)
    if not download_success:
        try:
            import urllib.request
            public_url = f"https://drive.google.com/uc?export=download&id={fid}"
            req = urllib.request.Request(public_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                content = resp.read()
                if content.startswith(b'%PDF'):
                    with open(dest, 'wb') as f:
                        f.write(content)
                    st.session_state["uploaded_pdf_path"] = str(dest)
                    st.session_state["uploaded_pdf_name"] = dest.name
                    download_success = True
        except Exception as e:
            last_err = last_err or e

    # Try 3: Default Service / Local Credentials fallback
    if not download_success:
        try:
            fallback_service = anki_cli.get_drive_service()
            downloaded_path = anki_cli.download_drive_file(fallback_service, fid, BASE_DIR / "extracted")
            st.session_state["uploaded_pdf_path"] = str(downloaded_path)
            st.session_state["uploaded_pdf_name"] = downloaded_path.name
            download_success = True
        except Exception as e:
            last_err = last_err or e

    if download_success:
        # Auto-infer course and session from filename if possible
        fname = st.session_state.get("uploaded_pdf_name", "")
        c_disp, _, s_num = anki_cli.parse_course_and_session(fname)
        if c_disp != "UNKNOWN":
            st.session_state["inferred_course"] = c_disp
        if s_num:
            st.session_state["inferred_session"] = s_num
        st.session_state["fetch_error"] = None
    else:
        st.session_state["fetch_error"] = (
            f"Could not download file: {last_err}\n\n"
            "💡 Tip: Click the 👤 icon on the left to Sign in with Google, or drag & drop the PDF into the 'Upload Lecture PDF' tab!"
        )


with main_col:
    # Main Page Header
    st.markdown('<div class="main-title">📇 Anki Flashcard Studio</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Upload course slides or paste a Google Drive link to generate exam-ready Anki Cloze flashcards.</div>', unsafe_allow_html=True)

    # Tabs: Google Drive URL vs File Upload
    tab_drive, tab_upload = st.tabs(["🔗 Paste Google Drive Link", "📄 Upload Lecture PDF"])

    with tab_drive:
        # Using a form without border so pressing Enter inside the text box OR clicking the button immediately fetches!
        with st.form("drive_fetch_form", clear_on_submit=False, border=False):
            url_col, btn_col = st.columns([4, 1], vertical_alignment="bottom")
            with url_col:
                drive_url = st.text_input(
                    "Google Drive PDF Link or ID",
                    placeholder="Paste link here and press Enter (e.g. https://drive.google.com/file/d/...)"
                )
            with btn_col:
                fetch_submitted = st.form_submit_button("Fetch from Drive", use_container_width=True)

            if fetch_submitted and drive_url:
                with st.spinner("Downloading from Google Drive..."):
                    fetch_drive_pdf(drive_url)

        if st.session_state.get("fetch_error"):
            st.error(st.session_state["fetch_error"])

    with tab_upload:
        uploaded_file = st.file_uploader("Choose an annotated slide PDF", type=["pdf"])
        if uploaded_file is not None:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(uploaded_file.read())
                st.session_state["uploaded_pdf_path"] = tmp.name
                st.session_state["uploaded_pdf_name"] = uploaded_file.name
                c_disp, _, s_num = anki_cli.parse_course_and_session(uploaded_file.name)
                if c_disp != "UNKNOWN":
                    st.session_state["inferred_course"] = c_disp
                if s_num:
                    st.session_state["inferred_session"] = s_num

    # Discover available courses from references/
    ref_dir = BASE_DIR / ".agents" / "skills" / "anki-card-generator" / "references"
    courses = ["MBB 321"]
    if ref_dir.exists():
        for ref_file in sorted(ref_dir.glob("*.md")):
            if not ref_file.name.startswith("_"):
                c_name = ref_file.stem.upper().replace("-", " ")
                if c_name not in courses:
                    courses.append(c_name)

    # Process PDF if available in session_state
    uploaded_pdf_path = st.session_state.get("uploaded_pdf_path")
    uploaded_pdf_name = st.session_state.get("uploaded_pdf_name", "")

    if uploaded_pdf_path and os.path.exists(uploaded_pdf_path):
        doc = pymupdf.open(uploaded_pdf_path)
        total_slides = len(doc)
        st.success(f"Loaded: **{uploaded_pdf_name or Path(uploaded_pdf_path).name}** ({total_slides} slides)")

        # Extract text from all slides
        text_blocks = []
        for pno in range(total_slides):
            page = doc[pno]
            b_list = page.get_text("blocks")
            for b in b_list:
                t = b[4].strip().replace("\n", " ")
                if t:
                    text_blocks.append(f"[Slide {pno+1}] {t}")
        slide_text = "\n".join(text_blocks)

        # Course, Session/Lecture #, and Generate CTA on the exact same line!
        default_course_idx = 0
        inferred_c = st.session_state.get("inferred_course")
        if inferred_c and inferred_c in courses:
            default_course_idx = courses.index(inferred_c)
        default_session = st.session_state.get("inferred_session", "13")

        ctl_col1, ctl_col2, ctl_col3 = st.columns([1.5, 1.2, 2.3], vertical_alignment="bottom")
        with ctl_col1:
            selected_course = st.selectbox("Course", courses, index=default_course_idx)
        with ctl_col2:
            session_num = st.text_input("Session / Lecture #", value=default_session)
        with ctl_col3:
            generate_clicked = st.button("✨ Generate Anki Flashcards", type="primary", use_container_width=True)

        if generate_clicked:
            if not api_key:
                st.error("Please click the ⚙️ Settings icon on the left and enter a Gemini API Key.")
            else:
                with st.spinner(f"Analyzing {total_slides} slides with Gemini..."):
                    try:
                        payload = generator.generate_cards_from_text(
                            slide_text=slide_text,
                            course_code=selected_course,
                            session_num=session_num,
                            base_dir=BASE_DIR,
                            api_key=api_key
                        )
                        st.session_state["generated_payload"] = payload
                        st.session_state["active_course"] = selected_course
                        st.session_state["active_session"] = session_num
                        st.success(f"Generated {len(payload.get('notes', []))} notes!")
                    except Exception as e:
                        st.error(f"Generation failed: {e}")

    # Review & Edit Generated Cards
    if "generated_payload" in st.session_state:
        payload = st.session_state["generated_payload"]
        active_course = st.session_state.get("active_course", courses[0])
        active_session = st.session_state.get("active_session", "13")
        notes = payload.get("notes", [])

        st.markdown("---")
        st.subheader(f"📝 Review Generated Cards ({len(notes)} notes)")

        edited_notes = []
        for idx, n in enumerate(notes):
            with st.container():
                st.markdown(f"**Card #{idx + 1}**")
                col1, col2 = st.columns([3, 2])
                with col1:
                    front = st.text_area("Front (Cloze)", value=n.get("text", ""), key=f"front_{idx}", height=100)
                with col2:
                    extra = st.text_area("Extra / High-Yield Note", value=n.get("extra", ""), key=f"extra_{idx}", height=100)
                edited_notes.append({"text": front, "extra": extra})

        payload["notes"] = edited_notes

        # Action buttons: Download .apkg & Sync to Drive
        st.markdown("---")
        btn_col1, btn_col2 = st.columns([1, 1])

        with btn_col1:
            tmp_cards_json = BASE_DIR / "extracted" / "temp_cards.json"
            tmp_cards_json.parent.mkdir(parents=True, exist_ok=True)
            tmp_cards_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            if st.button("📦 Build & Sync to Google Drive", type="primary", use_container_width=True):
                with st.spinner("Building .apkg and pushing to Google Drive..."):
                    active_service = drive_service or anki_cli.get_drive_service()
                    try:
                        course_compact = active_course.replace(" ", "")
                        remote_deck = anki_cli.find_course_apkg_on_drive(active_service, course_compact, active_course, folder_id)
                        work_dir = BASE_DIR / "extracted"

                        if remote_deck:
                            local_deck = work_dir / remote_deck['name']
                            anki_cli.download_drive_file(active_service, remote_deck['id'], local_deck)
                            tot_n, tot_c = anki_cli.update_existing_apkg(
                                local_deck,
                                edited_notes,
                                payload.get("tag", f"#{course_compact}::Session::{active_session}")
                            )
                            from googleapiclient.http import MediaFileUpload
                            media = MediaFileUpload(str(local_deck), resumable=True)
                            active_service.files().update(fileId=remote_deck['id'], media_body=media).execute()
                            st.success(f"Updated '{remote_deck['name']}' in Google Drive! (Total Notes: {tot_n})")
                        else:
                            new_name = f"{course_compact} - Flashcards.apkg"
                            local_deck = work_dir / new_name
                            anki_cli.create_new_apkg(
                                local_deck,
                                f"{active_course} - Flashcards",
                                edited_notes,
                                payload.get("tag", f"#{course_compact}::Session::{active_session}")
                            )
                            from googleapiclient.http import MediaFileUpload
                            media = MediaFileUpload(str(local_deck), resumable=True)
                            active_service.files().create(
                                body={'name': new_name, 'parents': [folder_id]},
                                media_body=media
                            ).execute()
                            st.success(f"Created and uploaded '{new_name}' to Google Drive!")

                        st.markdown(f"👉 [Open Target Google Drive Folder](https://drive.google.com/drive/folders/{folder_id})")
                    except Exception as e:
                        st.error(f"Sync error: {e}")

        with btn_col2:
            if tmp_cards_json.exists():
                download_deck_name = f"{active_course.replace(' ', '')} - Session {active_session}.apkg"
                download_path = BASE_DIR / "extracted" / download_deck_name
                anki_cli.create_new_apkg(
                    download_path,
                    f"{active_course} - Session {active_session}",
                    edited_notes,
                    payload.get("tag", f"#{active_course.replace(' ', '')}::Session::{active_session}")
                )
                with open(download_path, "rb") as f:
                    st.download_button(
                        label="⬇️ Download .apkg File Directly",
                        data=f.read(),
                        file_name=download_deck_name,
                        mime="application/octet-stream",
                        use_container_width=True
                    )
