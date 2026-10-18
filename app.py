"""
Streamlit Web App for Multi-Course Anki Flashcard Generation.
Supports Google OAuth 2.0 Identity ("Sign in with Google") for Drive sync.
"""

import os
import sys
import json
import tempfile
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
import importlib
import anki_cli
import generator
import google_auth
importlib.reload(google_auth)
importlib.reload(generator)

# Configure Streamlit page
st.set_page_config(
    page_title="Anki Flashcard Studio",
    page_icon="📇",
    layout="wide"
)

# Custom CSS for modern styling
st.markdown("""
<style>
    .main-title { font-size: 2.2rem; font-weight: 700; color: #1E88E5; margin-bottom: 0.2rem; }
    .sub-title { font-size: 1.05rem; color: #555; margin-bottom: 1.5rem; }
    .google-btn {
        background-color: #ffffff;
        color: #3c4043;
        border: 1px solid #dadce0;
        border-radius: 4px;
        padding: 8px 16px;
        text-align: center;
        text-decoration: none;
        display: inline-block;
        font-weight: 500;
        font-size: 14px;
        box-shadow: 0 1px 2px rgba(60,64,67,0.3);
    }
    .google-btn:hover { background-color: #f8f9fa; color: #202124; }
</style>
""", unsafe_allow_html=True)

# Determine redirect URI safely (allow override via secret/env or default to production app URL)
redirect_uri = google_auth.safe_get_secret("REDIRECT_URI")
if not redirect_uri:
    # Check if running locally vs Streamlit Cloud
    if os.path.exists("/home/daniel"):
        redirect_uri = "http://localhost:8501/"
    else:
        redirect_uri = "https://mara-anki-studio.streamlit.app/"

# Sidebar Configuration
st.sidebar.title("⚙️ Settings")

# Google Identity Authentication in Sidebar
st.sidebar.subheader("👤 Google Account")
drive_service, user_auth_info = google_auth.init_google_auth(redirect_uri)

if drive_service and isinstance(user_auth_info, str) and not user_auth_info.startswith("http"):
    st.sidebar.success(f"Signed in as:\n**{user_auth_info}**")
    if st.sidebar.button("Log out"):
        google_auth.clear_cached_creds()
        st.rerun()
elif isinstance(user_auth_info, str) and user_auth_info.startswith("http"):
    st.sidebar.link_button("🔑 Sign in with Google", user_auth_info, use_container_width=True)
    st.sidebar.caption("Opens Google Sign-In in a new tab to authorize Google Drive sync.")
else:
    st.sidebar.caption("Google Identity not configured. Add GOOGLE_CLIENT_ID & SECRET to enable.")

# API Key handling
default_key = google_auth.safe_get_secret("GEMINI_API_KEY")
api_key = st.sidebar.text_input("Gemini API Key", value=default_key, type="password")

# Google Drive Folder ID
st.sidebar.markdown("---")
st.sidebar.subheader("☁️ Google Drive Destination")
folder_id = st.sidebar.text_input("Target Folder ID", value=anki_cli.DEFAULT_SHARED_FOLDER_ID)

# Course selection / profiles
ref_dir = BASE_DIR / ".agents" / "skills" / "anki-card-generator" / "references"
courses = ["MBB 321"]
if ref_dir.exists():
    for ref_file in ref_dir.glob("*.md"):
        if not ref_file.name.startswith("_"):
            c_name = ref_file.stem.upper()
            if c_name not in courses:
                courses.append(c_name)

selected_course = st.sidebar.selectbox("Course", courses, index=0)
session_num = st.sidebar.text_input("Session / Lecture #", value="13")

# Main Page Header
st.markdown('<div class="main-title">📇 Anki Flashcard Studio</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Upload course slides (PDF) to generate exam-ready Anki Cloze flashcards tailored to your course.</div>', unsafe_allow_html=True)

# Tabs: File Upload vs Google Drive URL
tab_upload, tab_drive = st.tabs(["📄 Upload Lecture PDF", "🔗 Paste Google Drive Link"])

slide_text = ""

with tab_upload:
    uploaded_file = st.file_uploader("Choose an annotated slide PDF", type=["pdf"])
    if uploaded_file is not None:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_file.read())
            st.session_state["uploaded_pdf_path"] = tmp.name
            st.session_state["uploaded_pdf_name"] = uploaded_file.name

with tab_drive:
    drive_url = st.text_input("Google Drive PDF Link or ID", placeholder="https://drive.google.com/file/d/...")
    if drive_url and st.button("Fetch from Drive"):
        with st.spinner("Downloading from Google Drive..."):
            fid = anki_cli.extract_drive_id(drive_url)
            dest = BASE_DIR / "extracted" / f"drive_download_{fid}.pdf"
            dest.parent.mkdir(parents=True, exist_ok=True)
            download_success = False

            # Try 1: Signed-in User Drive Service (preserves original filename!)
            if drive_service:
                try:
                    downloaded_path = anki_cli.download_drive_file(drive_service, fid, BASE_DIR / "extracted")
                    st.session_state["uploaded_pdf_path"] = str(downloaded_path)
                    st.session_state["uploaded_pdf_name"] = downloaded_path.name
                    download_success = True
                    st.success(f"Downloaded using your Google Account: {downloaded_path.name}")
                except Exception:
                    pass

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
                            st.success(f"Downloaded: {dest.name}")
                except Exception:
                    pass

            # Try 3: Default Service / Local Credentials fallback
            if not download_success:
                try:
                    fallback_service = anki_cli.get_drive_service()
                    downloaded_path = anki_cli.download_drive_file(fallback_service, fid, BASE_DIR / "extracted")
                    st.session_state["uploaded_pdf_path"] = str(downloaded_path)
                    st.session_state["uploaded_pdf_name"] = downloaded_path.name
                    download_success = True
                    st.success(f"Downloaded: {downloaded_path.name}")
                except Exception as e:
                    st.error(
                        f"Could not download file: {e}\n\n"
                        "💡 Tip: Click 'Sign in with Google' on the sidebar or drag & drop the PDF into the 'Upload Lecture PDF' tab!"
                    )

# Process PDF if available in session_state
uploaded_pdf_path = st.session_state.get("uploaded_pdf_path")
uploaded_pdf_name = st.session_state.get("uploaded_pdf_name", "")
if uploaded_pdf_path and os.path.exists(uploaded_pdf_path):
    doc = pymupdf.open(uploaded_pdf_path)
    total_slides = len(doc)
    st.info(f"Loaded: **{uploaded_pdf_name or Path(uploaded_pdf_path).name}** ({total_slides} slides)")

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

    if st.button("✨ Generate Anki Flashcards", type="primary"):
        if not api_key:
            st.error("Please enter a Gemini API Key in the sidebar.")
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
                    st.success(f"Generated {len(payload.get('notes', []))} notes!")
                except Exception as e:
                    st.error(f"Generation failed: {e}")

# Review & Edit Generated Cards
if "generated_payload" in st.session_state:
    payload = st.session_state["generated_payload"]
    notes = payload.get("notes", [])
    st.markdown("---")
    st.subheader(f"📝 Review Generated Cards ({len(notes)} notes)")

    edited_notes = []
    for idx, n in enumerate(notes):
        with st.container():
            st.markdown(f"**Card #{idx + 1}**")
            col1, col2 = st.columns([3, 2])
            with col1:
                front = st.text_area(f"Front (Cloze)", value=n.get("text", ""), key=f"front_{idx}", height=100)
            with col2:
                extra = st.text_area(f"Extra / High-Yield Note", value=n.get("extra", ""), key=f"extra_{idx}", height=100)
            edited_notes.append({"text": front, "extra": extra})

    payload["notes"] = edited_notes

    # Action buttons: Download .apkg & Sync to Drive
    st.markdown("---")
    btn_col1, btn_col2 = st.columns([1, 1])

    with btn_col1:
        tmp_cards_json = BASE_DIR / "extracted" / "temp_cards.json"
        tmp_cards_json.parent.mkdir(parents=True, exist_ok=True)
        tmp_cards_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        if st.button("📦 Build & Sync to Google Drive", type="primary"):
            with st.spinner("Building .apkg and pushing to Google Drive..."):
                active_service = drive_service or anki_cli.get_drive_service()
                try:
                    course_compact = selected_course.replace(" ", "")
                    remote_deck = anki_cli.find_course_apkg_on_drive(active_service, course_compact, selected_course, folder_id)
                    work_dir = BASE_DIR / "extracted"
                    
                    if remote_deck:
                        local_deck = work_dir / remote_deck['name']
                        anki_cli.download_drive_file(active_service, remote_deck['id'], local_deck)
                        tot_n, tot_c = anki_cli.update_existing_apkg(local_deck, edited_notes, payload.get("tag", f"#{course_compact}::Session::{session_num}"))
                        # Update remote
                        from googleapiclient.http import MediaFileUpload
                        media = MediaFileUpload(str(local_deck), resumable=True)
                        active_service.files().update(fileId=remote_deck['id'], media_body=media).execute()
                        st.success(f"Updated '{remote_deck['name']}' in Google Drive! (Total Notes: {tot_n})")
                    else:
                        new_name = f"{course_compact} - Flashcards.apkg"
                        local_deck = work_dir / new_name
                        anki_cli.create_new_apkg(local_deck, f"{selected_course} - Flashcards", edited_notes, payload.get("tag", f"#{course_compact}::Session::{session_num}"))
                        from googleapiclient.http import MediaFileUpload
                        media = MediaFileUpload(str(local_deck), resumable=True)
                        active_service.files().create(body={'name': new_name, 'parents': [folder_id]}, media_body=media).execute()
                        st.success(f"Created and uploaded '{new_name}' to Google Drive!")

                    st.markdown(f"👉 [Open Target Google Drive Folder](https://drive.google.com/drive/folders/{folder_id})")
                except Exception as e:
                    st.error(f"Sync error: {e}")

    with btn_col2:
        if tmp_cards_json.exists():
            download_deck_name = f"{selected_course.replace(' ', '')} - Session {session_num}.apkg"
            download_path = BASE_DIR / "extracted" / download_deck_name
            anki_cli.create_new_apkg(
                download_path,
                f"{selected_course} - Session {session_num}",
                edited_notes,
                payload.get("tag", f"#{selected_course}::Session::{session_num}")
            )
            with open(download_path, "rb") as f:
                st.download_button(
                    label="⬇️ Download .apkg File Directly",
                    data=f.read(),
                    file_name=download_deck_name,
                    mime="application/octet-stream"
                )
