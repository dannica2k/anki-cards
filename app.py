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

# Configure Streamlit page (auto collapses on mobile, expanded on desktop)
st.set_page_config(
    page_title="Anki Flashcard Studio",
    page_icon="📇",
    layout="wide",
    initial_sidebar_state="auto"
)

# Custom CSS:
# 1. Desktop (>=769px): Sleek 64px fixed Gmail-style left icon rail flush with edge
# 2. Mobile (<=768px): Sidebar tucks cleanly offscreen into a top-left hamburger menu
# 3. Universal: Hide top-right 3 dots menu (#MainMenu), deploy button, and header chrome
st.markdown("""
<style>
    /* Hide top-right 3 dots menu (#MainMenu), deploy button, and right-side toolbar actions */
    #MainMenu,
    [data-testid="stMainMenu"],
    [data-testid="stMainMenuButton"],
    [data-testid="stAppDeployButton"],
    [data-testid="stToolbarActions"],
    header[data-testid="stHeader"] button[title="View app options"],
    header[data-testid="stHeader"] button[aria-label="Main menu"] {
        display: none !important;
        visibility: hidden !important;
    }
    header[data-testid="stHeader"] {
        background-color: transparent !important;
    }

    /* Hide "Press Enter to apply" tooltip */
    [data-testid="InputInstructions"] {
        display: none !important;
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

    /* =========================================================================
       DESKTOP (>= 769px): Docked 64px Gmail-style left rail
       ========================================================================= */
    @media (min-width: 769px) {
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
        /* Hide collapse toggle on desktop because rail is permanently docked */
        [data-testid="stSidebarCollapseButton"],
        [data-testid="collapsedControl"],
        [data-testid="stExpandSidebarButton"],
        [data-testid="stSidebarHeader"] {
            display: none !important;
            visibility: hidden !important;
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
        .block-container {
            padding-top: 2.2rem !important;
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
    }

    /* =========================================================================
       MOBILE (<= 768px): Tucked slide-over drawer with top-left hamburger menu
       ========================================================================= */
    @media (max-width: 768px) {
        /* When open, slide-over drawer */
        section[data-testid="stSidebar"] {
            width: 250px !important;
            min-width: 250px !important;
            max-width: 80vw !important;
            background-color: #f6f8fc !important;
            border-right: 1px solid #e1e5ea !important;
            box-shadow: 2px 0 12px rgba(0,0,0,0.15) !important;
            z-index: 999999 !important;
        }
        section[data-testid="stSidebar"] > div {
            width: 100% !important;
            padding: 0 !important;
        }
        /* Top-left rounded hamburger menu button */
        [data-testid="collapsedControl"],
        [data-testid="stExpandSidebarButton"] {
            display: flex !important;
            visibility: visible !important;
            position: fixed !important;
            top: 10px !important;
            left: 10px !important;
            z-index: 1000000 !important;
            background-color: #ffffff !important;
            border: 1px solid #dadce0 !important;
            border-radius: 8px !important;
            box-shadow: 0 1px 3px rgba(0,0,0,0.12) !important;
            padding: 4px 6px !important;
        }
        [data-testid="stSidebarHeader"] {
            display: flex !important;
            padding: 8px 12px !important;
        }
        [data-testid="stSidebarCollapseButton"] {
            display: flex !important;
        }
        [data-testid="stSidebarUserContent"] {
            padding: 12px 16px !important;
            display: flex !important;
            flex-direction: column !important;
            align-items: flex-start !important;
            gap: 12px !important;
            height: auto !important;
        }
        .sidebar-version {
            position: static !important;
            width: 100% !important;
            margin-top: 2rem !important;
            font-size: 11px !important;
            font-weight: 600 !important;
            color: #9aa0a6 !important;
            text-align: center !important;
        }
        /* Full width content with compact padding */
        .block-container {
            padding-top: 3.5rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            max-width: 100% !important;
        }
        .main-title {
            font-size: 1.6rem !important;
            font-weight: 700;
            color: #1E88E5;
            margin-top: 0.2rem;
            margin-bottom: 0.2rem;
            line-height: 1.25;
        }
        .sub-title {
            font-size: 0.9rem !important;
            color: #5f6368;
            margin-bottom: 1.2rem;
        }
    }
</style>
""", unsafe_allow_html=True)

# Determine redirect URI safely
redirect_uri = google_auth.safe_get_secret("REDIRECT_URI")
if not redirect_uri:
    if os.getenv("K_SERVICE"):
        redirect_uri = "https://anki.maranica.com/"
    elif os.path.exists("/home/daniel"):
        redirect_uri = "http://localhost:8501/"
    else:
        redirect_uri = "https://anki.maranica.com/"

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
            user_profile = google_auth.get_user_profile(user_auth_info)
            user_pic = user_profile.get("picture")
            if user_pic:
                st.image(user_pic, width=48)
            st.success(f"Signed in as:\n**{user_auth_info}**")
            saved_key = user_profile.get("personal_gemini_api_key", "")
            user_key_input = st.text_input(
                "Personal Gemini API Key",
                value=saved_key,
                type="password",
                help="Optional personal key. Used first before falling back to the project backup key."
            )
            if user_key_input != saved_key:
                norm_key = google_auth.normalize_gemini_api_key(user_key_input)
                user_profile["personal_gemini_api_key"] = norm_key
                google_auth.save_user_profile(user_auth_info, user_profile)
                st.toast("Personal Gemini key saved to profile!", icon="✅")
            st.caption("Your personal key is used first. If quota is exhausted, it automatically falls back to the project backup key.")
            if st.button("Log out", use_container_width=True):
                google_auth.clear_cached_creds()
                st.rerun()
        elif isinstance(user_auth_info, str) and user_auth_info.startswith("http"):
            st.markdown(
                f'<a href="{user_auth_info}" target="_self" '
                f'style="display:inline-flex;align-items:center;justify-content:center;width:100%;'
                f'padding:0.45rem 0.75rem;margin-bottom:0.5rem;background-color:#ffffff;color:#31333F;'
                f'border:1px solid rgba(49,51,63,0.2);border-radius:0.5rem;'
                f'text-decoration:none;font-weight:500;font-size:0.95rem;'
                f'box-shadow:0 1px 2px rgba(0,0,0,0.04);">'
                f'🔑 Sign in with Google</a>',
                unsafe_allow_html=True
            )
            st.caption("Sign in to fetch private files and sync decks to Google Drive.")
        else:
            st.caption("Add GOOGLE_CLIENT_ID & GOOGLE_CLIENT_SECRET to enable Google Sign-In.")

    # 2. Second icon right under: Settings popover
    with st.popover("", icon=":material/settings:", help="Settings"):
        st.markdown("##### ⚙️ Settings")
        default_key = google_auth.safe_get_secret("GEMINI_API_KEY")
        fallback_key = st.text_input("Project Backup Gemini API Key", value=default_key, type="password", help="Backup key used if a user's personal key is not set or exhausted.")
        folder_id = st.text_input("Target Google Drive Folder ID", value=anki_cli.DEFAULT_SHARED_FOLDER_ID)

    # 3. Bottom version label
    st.markdown(f'<div class="sidebar-version">{version.__version__}</div>', unsafe_allow_html=True)

# Resolve active API keys pool (User Personal Key -> Project Backup Key)
user_personal_key = ""
if is_logged_in:
    u_prof = google_auth.get_user_profile(user_auth_info)
    user_personal_key = u_prof.get("personal_gemini_api_key", "")

project_backup_key = fallback_key or google_auth.safe_get_secret("GEMINI_API_KEY")
api_keys_pool = [k for k in [user_personal_key, project_backup_key] if k]
api_key = api_keys_pool[0] if api_keys_pool else ""


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


def render_study_guide_ui(
    guide_data: dict,
    target_folder_id: str,
    active_drive_service,
    app_base_url: str,
    key_prefix: str = "sg"
):
    """Renders an interactive Illustrated Study Guide inside Streamlit with HTML/MD export and Drive sync."""
    guide_id = guide_data.get("guide_id") or generator.get_study_guide_id(
        guide_data.get("course_code", "Course"),
        guide_data.get("session_num", "1")
    )
    paths = generator.save_study_guide_files(guide_data, BASE_DIR, app_base_url=app_base_url)
    hosted_url = generator.build_study_guide_url(
        guide_data.get("course_code", "Course"),
        guide_data.get("session_num", "1"),
        app_base_url=app_base_url
    )

    with st.container(border=True):
        hdr_c1, hdr_c2 = st.columns([3.5, 1.2], vertical_alignment="center")
        with hdr_c1:
            st.markdown(f"### 📚 {guide_data.get('title', 'Supplementary Study Guide')}")
            st.caption(
                f"**Course:** {guide_data.get('course_code', '')} • "
                f"**Session/Chapter:** {guide_data.get('session_num', '')} • "
                f"🔗 [Hosted App Link (`?guide={guide_id}`)]({hosted_url})"
            )
        with hdr_c2:
            if st.button("☁️ Sync Guide to Drive", key=f"{key_prefix}_sync_btn", use_container_width=True):
                with st.spinner("Syncing Study Guide to Google Drive..."):
                    try:
                        svc = active_drive_service or anki_cli.get_drive_service()
                        res = anki_cli.sync_study_guide_to_drive(
                            svc, paths["json_path"], paths["html_path"], folder_id=target_folder_id
                        )
                        html_link = res.get("html_file", {}).get("webViewLink", f"https://drive.google.com/drive/folders/{target_folder_id}")
                        st.success("Synced to Google Drive!")
                        st.markdown(f"👉 [Open HTML Guide in Drive]({html_link})")
                    except Exception as e:
                        st.error(f"Drive sync error: {e}")

        if guide_data.get("executive_summary"):
            st.info(f"**🎯 Big-Picture Synthesis:**\n\n{guide_data['executive_summary']}")

        for s_idx, sec in enumerate(guide_data.get("sections", [])):
            st.markdown("---")
            st.markdown(f"#### {sec.get('heading', f'Section {s_idx + 1}')}")
            st.markdown(sec.get("content_markdown", ""))

            fig_path = sec.get("figure_path", "")
            fig_uri = sec.get("figure_data_uri", "")
            fig_name = sec.get("figure_filename", "")
            fig_cap = sec.get("figure_caption", "")

            if fig_path and os.path.exists(fig_path):
                st.image(fig_path, caption=f"🖼️ Diagram Walkthrough ({fig_name}): {fig_cap}", width=480)
            elif fig_uri:
                st.markdown(
                    f'<div style="background:#f8f9fa;border:1px solid #dadce0;border-radius:8px;padding:12px;margin:10px 0;">'
                    f'<img src="{fig_uri}" style="max-width:100%;max-height:380px;border-radius:4px;" />'
                    f'<div style="margin-top:8px;font-size:0.88rem;color:#3c4043;">'
                    f'<strong>🖼️ Diagram Walkthrough ({fig_name}):</strong> {fig_cap}</div></div>',
                    unsafe_allow_html=True
                )

            takeaways = sec.get("exam_takeaways", [])
            if takeaways:
                takeaways_md = "\n".join([f"- {t}" for t in takeaways])
                st.warning(f"**⚡ High-Yield Exam Takeaways & Common Traps:**\n{takeaways_md}")

        st.markdown("---")
        dl_col1, dl_col2 = st.columns([1, 1])
        with dl_col1:
            with open(paths["html_path"], "rb") as fh:
                st.download_button(
                    label="⬇️ Download Illustrated HTML Guide (.html)",
                    data=fh.read(),
                    file_name=paths["html_path"].name,
                    mime="text/html",
                    key=f"{key_prefix}_dl_html",
                    use_container_width=True
                )
        with dl_col2:
            pdf_target = paths.get("pdf_path")
            if pdf_target and pdf_target.exists():
                with open(pdf_target, "rb") as fp:
                    st.download_button(
                        label="⬇️ Download Study Guide PDF (.pdf)",
                        data=fp.read(),
                        file_name=pdf_target.name,
                        mime="application/pdf",
                        key=f"{key_prefix}_dl_pdf",
                        use_container_width=True
                    )


# Main Content Area
st.markdown('<div class="main-title">📇 Anki Flashcard Studio</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Upload course slides or paste a Google Drive link to generate exam-ready Anki Cloze flashcards.</div>', unsafe_allow_html=True)

# Hosted Study Guide Route (?guide=<COURSE>_Session_<N>) linked directly from Anki cards
requested_guide_id = st.query_params.get("guide")
if requested_guide_id:
    nav_c1, nav_c2 = st.columns([4, 1], vertical_alignment="center")
    with nav_c1:
        st.caption(f"📖 **Hosted Study Guide View** (`{requested_guide_id}`)")
    with nav_c2:
        if st.button("⬅️ Back to Studio", use_container_width=True):
            st.query_params.pop("guide", None)
            st.rerun()

    active_svc = None
    try:
        active_svc = drive_service or anki_cli.get_drive_service()
    except Exception:
        active_svc = None

    loaded_guide = generator.load_local_study_guide(requested_guide_id, BASE_DIR)
    if not loaded_guide and active_svc:
        with st.spinner(f"Fetching Study Guide '{requested_guide_id}' from Google Drive..."):
            loaded_guide = anki_cli.fetch_study_guide_from_drive(
                active_svc, requested_guide_id, BASE_DIR, folder_id=folder_id
            )

    if loaded_guide:
        render_study_guide_ui(
            loaded_guide,
            target_folder_id=folder_id,
            active_drive_service=active_svc,
            app_base_url=redirect_uri,
            key_prefix="hosted_sg"
        )
    else:
        st.info(
            f"📌 **No saved Study Guide found yet for `{requested_guide_id}`.**\n\n"
            "Load the lecture PDF in the Studio and click **📚 Request Supplementary Study Guide on this Topic** "
            "to generate and sync it to Google Drive."
        )
    st.stop()

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

if "generated_payload" not in st.session_state and st.query_params.get("test_cards"):
    sample_cards_file = BASE_DIR / "extracted" / "test_preview_cards.json"
    if sample_cards_file.exists():
        st.session_state["generated_payload"] = json.loads(sample_cards_file.read_text(encoding="utf-8"))
        st.session_state["active_course"] = st.session_state["generated_payload"].get("course_display", "BPK 207")
        st.session_state["active_session"] = st.session_state["generated_payload"].get("session", "2")

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
        if not api_keys_pool:
            st.error("Please enter a Gemini API Key in your Google Account profile or Settings.")
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
                    api_keys_pool=api_keys_pool,
                    progress_callback=on_progress
                )
                generated_notes = payload.get("notes", [])
                if not generated_notes:
                    status_box.warning("⚠️ Generation completed, but no flashcards were returned. Please check your guidance prompt or lecture slides.")
                else:
                    st.session_state["generated_payload"] = payload
                    st.session_state["active_course"] = selected_course
                    st.session_state["active_session"] = session_num
                    prog_bar.progress(1.0)
                    status_box.success(f"🎉 Successfully generated {len(generated_notes)} exam-ready notes!")
            except Exception as e:
                err_text = str(e)
                if "429" in err_text or "RESOURCE_EXHAUSTED" in err_text:
                    status_box.error(
                        "🛑 **Gemini API Quota Exceeded**: All configured API keys (personal and project backup) have reached their daily request limit.\n\n"
                        "- Free-tier quotas automatically reset every 24 hours.\n"
                        "- You can attach a payment method to your [Google AI Studio](https://aistudio.google.com/) account for unlimited usage, or enter a fresh key in your Google Account profile."
                    )
                elif "503" in err_text or "UNAVAILABLE" in err_text:
                    status_box.error("🌐 **Google API High Demand (503)**: Google's AI servers are temporarily experiencing a traffic spike. Please wait a few seconds and click Generate again.")
                else:
                    status_box.error(f"❌ **Generation failed**: {err_text}")

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
                clean_extra_val = generator.strip_card_footer(n.get("extra", ""))
                extra = st.text_area("Extra / High-Yield Explanation", value=clean_extra_val, key=f"extra_{idx}", height=120)
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

                # Per-Card AI Tutor & Session Study Guide Links (also auto-embedded into exported .apkg)
                ask_gemini_href = generator.build_ask_gemini_url(front, extra, active_course, active_session)
                study_guide_href = generator.build_study_guide_url(active_course, active_session, app_base_url=redirect_uri)
                st.markdown(
                    f'<div style="margin-top:4px;font-size:0.84rem;line-height:1.4;">'
                    f'<a href="{ask_gemini_href}" target="_blank" rel="noopener noreferrer" '
                    f'style="color:#1a73e8;text-decoration:none;font-weight:600;margin-right:10px;">💬 Ask Gemini</a>'
                    f'<span style="color:#9aa0a6;margin-right:10px;">•</span>'
                    f'<a href="{study_guide_href}" target="_blank" rel="noopener noreferrer" '
                    f'style="color:#1a73e8;text-decoration:none;font-weight:600;">📚 Session Study Guide</a>'
                    f'</div>',
                    unsafe_allow_html=True
                )

            edited_notes.append({"text": front, "extra": extra})

    if to_delete is not None:
        notes.pop(to_delete)
        payload["notes"] = notes
        st.rerun()

    payload["notes"] = edited_notes

    # Supplementary Study Guide Generator & Viewer (Item BL-01)
    st.markdown("---")
    st.markdown("##### 💡 Supplementary Learning Materials")
    sg_col1, sg_col2 = st.columns([2.2, 1.3], vertical_alignment="bottom")
    with sg_col1:
        sg_focus = st.text_input(
            "Study Guide Focus (Optional — leave blank for full lecture guide)",
            placeholder="e.g. Explain muscle spindle Ia vs. II coding and reflex pathways in depth",
            key="sg_focus_input"
        )
    with sg_col2:
        sg_clicked = st.button("📚 Request Supplementary Study Guide on this Topic", use_container_width=True)

    active_service = None
    try:
        active_service = drive_service or anki_cli.get_drive_service()
    except Exception:
        active_service = None

    current_guide_id = generator.get_study_guide_id(active_course, active_session)

    if sg_clicked:
        if not api_keys_pool:
            st.error("Please enter a Gemini API Key in your Google Account profile or Settings.")
        else:
            sg_prog = st.progress(0)
            sg_status = st.empty()

            def on_sg_progress(batch_num, total_batches, msg=None):
                if msg is None:
                    sg_status.info(f"📖 {batch_num}")
                else:
                    frac = batch_num / max(total_batches, 1)
                    sg_prog.progress(frac)
                    sg_status.info(f"📖 {msg}")

            try:
                # Use slides_data from assessment if loaded, or synthesize from current notes
                slides_for_sg = []
                if "pdf_assessment" in st.session_state and st.session_state["pdf_assessment"].get("slides_data"):
                    slides_for_sg = st.session_state["pdf_assessment"]["slides_data"]
                else:
                    slides_for_sg = [{
                        "page_num": idx + 1,
                        "text": f"{n.get('text', '')}\n{generator.strip_card_footer(n.get('extra', ''))}",
                        "sections": [],
                        "snapshot_path": "",
                        "figure_paths": media_files if idx == 0 else []
                    } for idx, n in enumerate(edited_notes)]

                guide_payload = generator.generate_study_guide(
                    slides_data=slides_for_sg,
                    course_code=active_course,
                    session_num=active_session,
                    custom_focus=sg_focus,
                    base_dir=BASE_DIR,
                    api_keys_pool=api_keys_pool,
                    app_base_url=redirect_uri,
                    progress_callback=on_sg_progress
                )
                st.session_state["active_study_guide"] = guide_payload
                sg_paths = generator.save_study_guide_files(guide_payload, BASE_DIR, app_base_url=redirect_uri)
                if active_service:
                    try:
                        anki_cli.sync_study_guide_to_drive(
                            active_service, sg_paths["json_path"], sg_paths["html_path"], folder_id=folder_id
                        )
                    except Exception:
                        pass
                sg_prog.progress(1.0)
                sg_status.success(f"🎉 Supplementary Study Guide generated ({len(guide_payload.get('sections', []))} sections) and ready!")
            except Exception as e:
                sg_status.error(f"❌ Study Guide generation failed: {e}")

    # Load existing or newly generated Study Guide for this session if available
    active_guide = st.session_state.get("active_study_guide")
    if not active_guide or active_guide.get("guide_id") != current_guide_id:
        active_guide = generator.load_local_study_guide(current_guide_id, BASE_DIR)
        if active_guide:
            st.session_state["active_study_guide"] = active_guide

    if active_guide and active_guide.get("guide_id") == current_guide_id:
        with st.expander(f"📖 View Illustrated Study Guide: {active_guide.get('title', current_guide_id)}", expanded=True):
            render_study_guide_ui(
                active_guide,
                target_folder_id=folder_id,
                active_drive_service=active_service,
                app_base_url=redirect_uri,
                key_prefix="inline_sg"
            )

    # Action buttons: Download .apkg & Sync to Drive (with full media packing + Ask Gemini / Study Guide links!)
    st.markdown("---")

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

    # Attach '💬 Ask Gemini' and '📚 Session Study Guide' links to every card's extra field for Anki export
    export_app_url = "https://anki.maranica.com/" if "localhost" not in redirect_uri else redirect_uri
    notes_with_links = generator.attach_footers_to_notes(
        edited_notes,
        course_code=active_course,
        session_num=active_session,
        app_base_url=export_app_url
    )

    # Build the updated package (master or new)
    if baseline_apkg and os.path.exists(str(baseline_apkg)):
        if Path(baseline_apkg).resolve() != master_export_path.resolve():
            shutil.copyfile(str(baseline_apkg), str(master_export_path))
        tot_notes, tot_cards = anki_cli.update_existing_apkg(
            master_export_path,
            notes_with_links,
            tag_str,
            media_files=media_files
        )
    else:
        anki_cli.create_new_apkg(
            master_export_path,
            canonical_deck_name,
            notes_with_links,
            tag_str,
            media_files=media_files
        )
        tot_notes = len(notes_with_links)
        tot_cards = tot_notes

    st.caption(f"🎯 **Target Anki Deck:** `{canonical_deck_name}` • Master Archive: `{canonical_file_name}` ({tot_notes} notes, with `💬 Ask Gemini` & `📚 Session Study Guide` embedded)")

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

                    # Also sync Study Guide if generated for this session
                    if active_guide and active_guide.get("guide_id") == current_guide_id:
                        sg_paths = generator.save_study_guide_files(active_guide, BASE_DIR, app_base_url=export_app_url)
                        anki_cli.sync_study_guide_to_drive(
                            active_service, sg_paths["json_path"], sg_paths["html_path"], folder_id=folder_id
                        )

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

