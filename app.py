"""
Streamlit Web App for Multi-Course Anki Flashcard Generation.
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
load_dotenv(BASE_DIR / ".env")

# Add scripts to sys.path
sys.path.insert(0, str(BASE_DIR / ".agents" / "skills" / "anki-card-generator" / "scripts"))
import anki_cli
import generator

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
    .card-box {
        background-color: #f8f9fa;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 14px 18px;
        margin-bottom: 12px;
    }
    .cloze-badge {
        background-color: #E3F2FD;
        color: #1565C0;
        font-weight: 600;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar Configuration
st.sidebar.title("⚙️ Settings")

# API Key handling
default_key = os.getenv("GEMINI_API_KEY", "")
api_key = st.sidebar.text_input("Gemini API Key", value=default_key, type="password")

# Google Drive Sync option
st.sidebar.markdown("---")
st.sidebar.subheader("☁️ Google Drive Sync")
auto_sync = st.sidebar.checkbox("Auto-sync output deck to Shared Drive", value=True)
folder_id = st.sidebar.text_input("Shared Drive Folder ID", value=anki_cli.DEFAULT_SHARED_FOLDER_ID)

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

uploaded_pdf_path = None
slide_text = ""

with tab_upload:
    uploaded_file = st.file_uploader("Choose an annotated slide PDF", type=["pdf"])
    if uploaded_file is not None:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_file.read())
            uploaded_pdf_path = tmp.name

with tab_drive:
    drive_url = st.text_input("Google Drive PDF Link or ID", placeholder="https://drive.google.com/file/d/...")
    if drive_url and st.button("Fetch from Drive"):
        with st.spinner("Downloading from Google Drive..."):
            try:
                service = anki_cli.get_drive_service()
                fid = anki_cli.extract_drive_id(drive_url)
                dest = BASE_DIR / "extracted" / f"drive_download_{fid}.pdf"
                dest.parent.mkdir(parents=True, exist_ok=True)
                anki_cli.download_drive_file(service, fid, dest)
                uploaded_pdf_path = str(dest)
                st.success(f"Downloaded: {dest.name}")
            except Exception as e:
                st.error(f"Error downloading: {e}")

# Process PDF if available
if uploaded_pdf_path:
    doc = pymupdf.open(uploaded_pdf_path)
    total_slides = len(doc)
    st.info(f"Loaded: **{Path(uploaded_pdf_path).name}** ({total_slides} slides)")

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
            with st.spinner(f"Analyzing {total_slides} slides and crafting high-yield cards with Gemini 3.8 Flash..."):
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
        # Build local .apkg for direct browser download
        temp_apkg_path = BASE_DIR / "extracted" / f"{selected_course.replace(' ', '')}_Session_{session_num}.apkg"
        temp_apkg_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write temporary cards.json
        tmp_cards_json = BASE_DIR / "extracted" / "temp_cards.json"
        tmp_cards_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        if st.button("📦 Build & Sync to Google Drive", type="primary"):
            with st.spinner("Building .apkg and pushing to Google Drive..."):
                try:
                    sys.argv = ["anki_cli.py", "sync", str(tmp_cards_json), "--folder-id", folder_id, "-w", str(BASE_DIR)]
                    anki_cli.cmd_sync(anki_cli.argparse.Namespace(
                        cards=str(tmp_cards_json),
                        course=selected_course,
                        session=session_num,
                        append=False,
                        folder_id=folder_id,
                        workdir=str(BASE_DIR)
                    ))
                    st.success("Successfully synced to Google Drive shared folder!")
                    st.markdown(f"👉 [Open Shared Google Drive Folder](https://drive.google.com/drive/folders/{folder_id})")
                except Exception as e:
                    st.error(f"Sync error: {e}")

    with btn_col2:
        # Provide instant .apkg file download button
        if tmp_cards_json.exists():
            # Build anki package in memory/temp for instant download
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
