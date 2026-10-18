"""
Streamlit Web App for Multi-Course Anki Flashcard Generation.
Features:
- True Gmail-style full-height left navigation rail docked to the left edge of the viewport (using st.sidebar).
- Instant "Fetch from Drive" on pressing Enter (with "Press Enter to apply" hidden).
- Proportional input columns (82% URL input / 18% Fetch CTA).
- Course & Session/Lecture controls aligned on the same row as the "Generate Anki Flashcards" CTA.
"""

import os
import re
import sys
import json
import shutil
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
import version

importlib.reload(anki_cli)
importlib.reload(google_auth)
importlib.reload(generator)
importlib.reload(version)

# Configure Streamlit page (keep sidebar always expanded as a narrow 64px Gmail rail)
st.set_page_config(
    page_title="Anki Flashcard Studio",
    page_icon="📇",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS:
# 1. Transform native [data-testid="stSidebar"] into a fixed 64px full-height Gmail-style left rail docked at left=0
# 2. Hide sidebar collapse/expand buttons and resize handles so it stays a clean static icon bar
# 3. Scope popover icon styling strictly inside [data-testid="stSidebar"] so main content columns are NEVER affected!
st.markdown("""
<style>
    /* Hide "Press Enter to apply" tooltip */
    [data-testid="InputInstructions"] {
        display: none !important;
    }

    /* Transform stSidebar into a 64px full-height Gmail icon rail flush against the left screen edge */
    section[data-testid="stSidebar"] {
        width: 64px !important;
        min-width: 64px !important;
        max-width: 64px !important;
        background-color: #f6f8fc !important;
        border-right: 1px solid #e1e5ea !important;
        transform: none !important;
    }
    section[data-testid="stSidebar"] > div {
        width: 64px !important;
        padding: 0 !important;
    }
    /* Hide the sidebar collapse button and header spacing */
    [data-testid="stSidebarCollapseButton"],
    [data-testid="collapsedControl"],
    [data-testid="stSidebarHeader"] {
        display: none !important;
    }
    [data-testid="stSidebarUserContent"] {
        padding: 16px 8px 16px 8px !important;
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        gap: 10px !important;
        height: 100vh !important;
        box-sizing: border-box !important;
    }
    .sidebar-version {
        position: fixed !important;
        bottom: 14px !important;
        left: 0 !important;
        width: 64px !important;
        font-size: 11px !important;
        font-weight: 600 !important;
        color: #9aa0a6 !important;
        text-align: center !important;
        white-space: nowrap !important;
        letter-spacing: 0.2px !important;
        line-height: 1 !important;
        user-select: none !important;
        z-index: 99 !important;
    }

    /* Circular icon-only buttons strictly inside the sidebar rail */
    section[data-testid="stSidebar"] button[data-testid="stPopoverButton"] {
        width: 44px !important;
        height: 44px !important;
        min-width: 44px !important;
        min-height: 44px !important;
        padding: 0 !important;
        border-radius: 50% !important;
        border: none !important;
        background-color: transparent !important;
        color: #444746 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        box-shadow: none !important;
        transition: background-color 0.15s ease;
    }
    section[data-testid="stSidebar"] button[data-testid="stPopoverButton"]:hover {
        background-color: #e1e5ea !important;
    }
    /* Hide the popover 'expand_more' chevron div strictly inside the sidebar rail */
    section[data-testid="stSidebar"] button[data-testid="stPopoverButton"] > div > div:nth-child(2) {
        display: none !important;
    }
    section[data-testid="stSidebar"] button[data-testid="stPopoverButton"] span[data-testid="stIconMaterial"] {
        font-size: 26px !important;
        margin: 0 !important;
    }

    /* Main content area padding & typography */
    .block-container {
        padding-top: 3.5rem !important;
        padding-left: 3rem !important;
        padding-right: 3rem !important;
        max-width: 1150px !important;
    }
    .main-title {
        font-size: 2.1rem;
        font-weight: 700;
        color: #1E88E5;
        margin-top: 0.2rem;
        margin-bottom: 0.2rem;
        line-height: 1.3;
    }
    .sub-title {
        font-size: 1.0rem;
        color: #5f6368;
        margin-bottom: 1.5rem;
    }
</style>
""", unsafe_allow_html=True)

# Determine redirect URI safely
redirect_uri = google_auth.safe_get_secret("REDIRECT_URI")
if not redirect_uri:
    if os.getenv("K_SERVICE"):
        redirect_uri = "https://anki-studio-bacy4cozoa-uc.a.run.app/"
    elif os.path.exists("/home/daniel"):
        redirect_uri = "http://localhost:8501/"
    else:
        redirect_uri = "https://mara-anki-studio.streamlit.app/"

# Initialize Google Auth
drive_service, user_auth_info = google_auth.init_google_auth(redirect_uri)
is_logged_in = bool(drive_service and isinstance(user_auth_info, str) and not user_auth_info.startswith("http"))

# Left Gmail-Style Navigation Rail (using native st.sidebar so it is full-height and flush left)
with st.sidebar:
    # 1. Top icon: Login / Account popover
    account_icon = ":material/verified_user:" if is_logged_in else ":material/account_circle:"
    with st.popover("", icon=account_icon, help="Google Account"):
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
    with st.popover("", icon=":material/settings:", help="Settings"):
        st.markdown("##### ⚙️ Settings")
        default_key = google_auth.safe_get_secret("GEMINI_API_KEY")
        api_key = st.text_input("Gemini API Key", value=default_key, type="password")
        folder_id = st.text_input("Target Google Drive Folder ID", value=anki_cli.DEFAULT_SHARED_FOLDER_ID)

    # 3. Bottom version label
    st.markdown(f'<div class="sidebar-version">{version.__version__}</div>', unsafe_allow_html=True)


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
        fname = st.session_state.get("uploaded_pdf_name", "")
        c_disp, _, s_num = anki_cli.parse_course_and_session(fname)
        if c_disp != "UNKNOWN":
            st.session_state["inferred_course"] = c_disp
        if s_num:
            st.session_state["inferred_session"] = s_num
        st.session_state["fetch_error"] = None
    else:
        if not is_logged_in:
            st.session_state["fetch_error"] = "Please log in to your Google Account."
        else:
            err_msg = str(last_err) if last_err else ""
            if "not found" in err_msg.lower() or "404" in err_msg:
                st.session_state["fetch_error"] = "File not found. Please check the link and permissions."
            else:
                st.session_state["fetch_error"] = "Please log in to your Google Account."


# Main Content Area
st.markdown('<div class="main-title">📇 Anki Flashcard Studio</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Upload course slides or paste a Google Drive link to generate exam-ready Anki Cloze flashcards.</div>', unsafe_allow_html=True)

# Tabs: Google Drive URL vs File Upload
tab_drive, tab_upload = st.tabs(["🔗 Paste Google Drive Link", "📄 Upload Lecture PDF"])

with tab_drive:
    with st.form("drive_fetch_form", clear_on_submit=False, border=False):
        url_col, btn_col = st.columns([4.5, 1], vertical_alignment="bottom")
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
            # Clear previous assessment if file changed
            st.session_state.pop("pdf_assessment", None)

# Discover available courses from references/
ref_dir = BASE_DIR / ".agents" / "skills" / "anki-card-generator" / "references"
courses = ["MBB 321"]
if ref_dir.exists():
    for ref_file in sorted(ref_dir.glob("*.md")):
        if not ref_file.name.startswith("_"):
            c_name = ref_file.stem.upper().replace("-", " ")
            if c_name not in courses:
                courses.append(c_name)

# Process PDF if available in session_state (or via ?test_pdf=1 for visual verification)
if "uploaded_pdf_path" not in st.session_state and st.query_params.get("test_pdf"):
    sample_pdf = BASE_DIR / "extracted" / "BPK 207 - Chapter 2 - annotated.pdf"
    if sample_pdf.exists():
        st.session_state["uploaded_pdf_path"] = str(sample_pdf)
        st.session_state["uploaded_pdf_name"] = sample_pdf.name
        st.session_state["inferred_course"] = "BPK 207"
        st.session_state["inferred_session"] = "2"

uploaded_pdf_path = st.session_state.get("uploaded_pdf_path")
uploaded_pdf_name = st.session_state.get("uploaded_pdf_name", "")

if uploaded_pdf_path and os.path.exists(uploaded_pdf_path):
    # Auto-run pre-generation audit if not yet computed for this PDF
    if "pdf_assessment" not in st.session_state or st.session_state.get("assessment_file") != uploaded_pdf_path:
        with st.spinner("Analyzing lecture structure, formatting, and annotations..."):
            initial_c = st.session_state.get("inferred_course", courses[0])
            initial_s = st.session_state.get("inferred_session", "1")
            audit = generator.analyze_lecture_pdf(
                uploaded_pdf_path,
                BASE_DIR,
                course_code=initial_c,
                session_num=initial_s,
                api_key=api_key
            )
            st.session_state["pdf_assessment"] = audit
            st.session_state["assessment_file"] = uploaded_pdf_path

    assessment = st.session_state["pdf_assessment"]
    layout = assessment["layout"]
    proj_counts = assessment["projected_counts"]

    # Header Card for Loaded Document
    st.markdown("---")
    info_col1, info_col2 = st.columns([3, 1], vertical_alignment="center")
    with info_col1:
        st.subheader(f"📄 {uploaded_pdf_name or Path(uploaded_pdf_path).name}")
        st.caption(f"**Format:** {layout['format_name']} • {assessment['total_pages']} pages • ~{layout['avg_words_per_page']} words/page • {len(assessment['sections'])} numbered sections")
    with info_col2:
        if st.button("🔄 Re-Analyze PDF", use_container_width=True):
            st.session_state.pop("pdf_assessment", None)
            st.rerun()

    # Pre-Generation Assessment & Configuration Dashboard
    st.markdown("##### ⚙️ Flashcard Configuration & Density")
    cfg_col1, cfg_col2, cfg_col3, cfg_col4 = st.columns([1.1, 0.9, 2.4, 1.6], vertical_alignment="top")

    with cfg_col1:
        default_course_idx = 0
        inferred_c = st.session_state.get("inferred_course")
        if inferred_c and inferred_c in courses:
            default_course_idx = courses.index(inferred_c)
        selected_course = st.selectbox("Course", courses, index=default_course_idx)

    with cfg_col2:
        default_session = st.session_state.get("inferred_session", "1")
        session_num = st.text_input("Session / Chapter #", value=default_session)

    with cfg_col3:
        density_mode = st.radio(
            "Density Level",
            ["High Level", "Regular Recap", "Deep Dive"],
            index=1,
            horizontal=True,
            help="High Level: Core concepts (~1 card/sec). Regular Recap: Full exam coverage of all mechanisms. Deep Dive: Exhaustive sub-bullet granularity."
        )

    with cfg_col4:
        default_target = proj_counts.get(density_mode, 35)
        target_count = st.number_input(
            f"Target Cards (Est: {default_target})",
            min_value=5,
            max_value=250,
            value=default_target,
            help=f"Projected {default_target} cards for {density_mode}. Adjust desired count as needed."
        )

    # Observations, Hints, and Exclusions Box
    with st.expander("🔍 Lecture Audit & Detected Exam Notes", expanded=True):
        if assessment.get("observations"):
            for obs in assessment["observations"]:
                st.markdown(obs)
        if assessment.get("gap_warnings"):
            for warn in assessment["gap_warnings"]:
                st.info(warn)
        if assessment.get("sections"):
            with st.expander(f"View {len(assessment['sections'])} Detected Sub-Sections"):
                st.markdown("\n".join([f"- `{s}`" for s in assessment["sections"]]))

    custom_guidance = st.text_input(
        "Custom Focus Guidance (Optional)",
        placeholder="e.g. Focus heavily on reflex pathways, muscle vibration illusions, and the GTO mechanism"
    )

    # Primary Generation CTA
    generate_clicked = st.button("✨ Generate Anki Flashcards", type="primary", use_container_width=True)

    if generate_clicked:
        if not api_key:
            st.error("Please click the ⚙️ Settings icon on the left rail and enter a Gemini API Key.")
        else:
            prog_bar = st.progress(0)
            status_box = st.empty()

            def on_progress(batch_num, total_batches, msg):
                frac = batch_num / max(total_batches, 1)
                prog_bar.progress(frac)
                status_box.info(f"⚡ {msg}")

            try:
                payload = generator.generate_cards_chunked(
                    slides_data=assessment["slides_data"],
                    course_code=selected_course,
                    session_num=session_num,
                    density_mode=density_mode,
                    target_count=int(target_count),
                    custom_guidance=custom_guidance,
                    base_dir=BASE_DIR,
                    api_key=api_key,
                    progress_callback=on_progress
                )
                st.session_state["generated_payload"] = payload
                st.session_state["active_course"] = selected_course
                st.session_state["active_session"] = session_num
                prog_bar.progress(1.0)
                status_box.success(f"🎉 Successfully generated {len(payload.get('notes', []))} exam-ready notes!")
            except Exception as e:
                status_box.error(f"Generation failed: {e}")

# Review & Edit Generated Cards
if "generated_payload" in st.session_state:
    payload = st.session_state["generated_payload"]
    active_course = st.session_state.get("active_course", courses[0])
    active_session = st.session_state.get("active_session", "1")
    notes = payload.get("notes", [])
    media_files = payload.get("media_files", [])

    st.markdown("---")
    rev_hdr_col1, rev_hdr_col2 = st.columns([3, 1], vertical_alignment="center")
    with rev_hdr_col1:
        st.subheader(f"📝 Review Generated Cards ({len(notes)} notes)")
    with rev_hdr_col2:
        if st.button("➕ Add New Flashcard", use_container_width=True):
            notes.append({"text": "New question with {{c1::cloze deletion}}", "extra": ""})
            st.rerun()

    edited_notes = []
    to_delete = None

    for idx, n in enumerate(notes):
        with st.container(border=True):
            head_col1, head_col2 = st.columns([5, 1])
            with head_col1:
                st.markdown(f"**Card #{idx + 1}**")
            with head_col2:
                if st.button("🗑️", key=f"del_{idx}", help="Delete this card"):
                    to_delete = idx

            col1, col2 = st.columns([3, 2])
            with col1:
                front = st.text_area("Front (Cloze Deletions)", value=n.get("text", ""), key=f"front_{idx}", height=120)

            with col2:
                extra = st.text_area("Extra / High-Yield Explanation", value=n.get("extra", ""), key=f"extra_{idx}", height=120)
                # Live Preview of Embedded Images
                img_matches = re.findall(r'<img\s+src=[\'"]([^\'"]+)[\'"]', extra)
                for img_name in img_matches:
                    img_match_path = None
                    for mf in media_files:
                        if Path(mf).name == img_name and os.path.exists(mf):
                            img_match_path = mf
                            break
                    if not img_match_path:
                        img_cand = BASE_DIR / "extracted" / f"{active_course.replace(' ', '')}_Session_{active_session}" / "images" / img_name
                        if img_cand.exists():
                            img_match_path = str(img_cand)
                    if img_match_path and os.path.exists(img_match_path):
                        st.image(img_match_path, caption=f"Embedded Diagram: {img_name}", width=250)

            edited_notes.append({"text": front, "extra": extra})

    if to_delete is not None:
        notes.pop(to_delete)
        payload["notes"] = notes
        st.rerun()

    payload["notes"] = edited_notes

    # Backlog Feature: Study Guide Request
    st.markdown("---")
    st.caption("💡 Supplementary Learning Materials")
    if st.button("📚 Request Supplementary Study Guide on this Topic (Backlog Item BL-01)", use_container_width=True):
        st.info("📌 **Queued in Backlog (Item BL-01):** The on-demand illustrated Study Guide & Concept Explainer will be available in the upcoming release!")

    # Action buttons: Download .apkg & Sync to Drive (with full media packing!)
    st.markdown("---")

    active_service = drive_service or anki_cli.get_drive_service()
    course_compact = active_course.replace(" ", "")
    work_dir = BASE_DIR / "extracted"
    work_dir.mkdir(parents=True, exist_ok=True)

    # Dynamically find existing master .apkg (local or Drive)
    baseline_apkg = anki_cli.find_baseline_apkg(active_course, BASE_DIR, service=active_service, folder_id=folder_id)
    deck_info = anki_cli.get_deck_info_from_apkg(baseline_apkg) if baseline_apkg else None

    if deck_info:
        canonical_deck_name = deck_info["deck_name"]
        canonical_file_name = deck_info["file_name"]
    else:
        canonical_deck_name = f"{active_course} - Flashcards"
        canonical_file_name = f"{course_compact} - Flashcards.apkg"

    master_export_path = work_dir / canonical_file_name
    tag_str = payload.get("tag", f"#{course_compact}::Session::{active_session}")

    # Build the updated package (master or new)
    if baseline_apkg and os.path.exists(str(baseline_apkg)):
        if Path(baseline_apkg).resolve() != master_export_path.resolve():
            shutil.copyfile(str(baseline_apkg), str(master_export_path))
        tot_notes, tot_cards = anki_cli.update_existing_apkg(
            master_export_path,
            edited_notes,
            tag_str,
            media_files=media_files
        )
    else:
        anki_cli.create_new_apkg(
            master_export_path,
            canonical_deck_name,
            edited_notes,
            tag_str,
            media_files=media_files
        )
        tot_notes = len(edited_notes)
        tot_cards = tot_notes

    st.caption(f"🎯 **Target Anki Deck:** `{canonical_deck_name}` • Master Archive: `{canonical_file_name}` ({tot_notes} notes)")

    btn_col1, btn_col2 = st.columns([1, 1])

    with btn_col1:
        if st.button("📦 Build & Sync to Google Drive", type="primary", use_container_width=True):
            with st.spinner(f"Syncing '{canonical_file_name}' to Google Drive..."):
                try:
                    remote_deck = anki_cli.find_course_apkg_on_drive(active_service, course_compact, active_course, folder_id)
                    from googleapiclient.http import MediaFileUpload
                    media = MediaFileUpload(str(master_export_path), resumable=True)

                    if remote_deck:
                        active_service.files().update(fileId=remote_deck['id'], media_body=media).execute()
                        st.success(f"Updated '{remote_deck['name']}' in Google Drive! (Total Notes: {tot_notes})")
                    else:
                        active_service.files().create(
                            body={'name': canonical_file_name, 'parents': [folder_id]},
                            media_body=media
                        ).execute()
                        st.success(f"Created and uploaded '{canonical_file_name}' to Google Drive! (Total Notes: {tot_notes})")

                    st.markdown(f"👉 [Open Target Google Drive Folder](https://drive.google.com/drive/folders/{folder_id})")
                except Exception as e:
                    st.error(f"Sync error: {e}")

    with btn_col2:
        with open(master_export_path, "rb") as f:
            st.download_button(
                label=f"⬇️ Download Updated Deck ({tot_notes} notes)",
                data=f.read(),
                file_name=canonical_file_name,
                mime="application/octet-stream",
                use_container_width=True,
                help=f"Internal Anki Deck Name: '{canonical_deck_name}'. Importing into Anki updates this deck in place without duplicates!"
            )
