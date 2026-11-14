#!/usr/bin/env python3
"""
FastAPI / Starlette + HTMX Server for Anki Flashcard Studio.
Runs locally on port 8000 for instant, zero-rerun testing alongside Streamlit.
"""

import os
import sys
import json
import re
import uuid
import shutil
import asyncio
import html
import urllib.parse
from pathlib import Path
from typing import Dict, Any, Optional, List

def format_sse(data: str, event: str = "message") -> str:
    """Formats payload into valid multi-line SSE frame."""
    lines = data.splitlines()
    body = "\n".join(f"data: {l}" for l in lines)
    return f"event: {event}\n{body}\n\n"

from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse, RedirectResponse
from starlette.routing import Route, Mount
from starlette.templating import Jinja2Templates
from starlette.staticfiles import StaticFiles

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
sys.path.insert(0, str(BASE_DIR / ".agents" / "skills" / "anki-card-generator" / "scripts"))
sys.path.insert(0, str(BASE_DIR))

# Import existing domain logic without modification
import generator
import google_auth
import version
import anki_cli


def get_oauth_redirect_uri(request: Optional[Any] = None) -> str:
    """Determines authorized OAuth redirect URI for Cloud Run or local dev."""
    configured = os.getenv("REDIRECT_URI")
    if configured:
        return configured
    if request:
        host = request.headers.get("host", "")
        if "anki.maranica.com" in host:
            return "https://anki.maranica.com/"
        if host:
            proto = request.headers.get("x-forwarded-proto", "http" if "localhost" in host else "https")
            return f"{proto}://{host}/"
    if os.getenv("K_SERVICE"):
        return "https://anki.maranica.com/"
    return "https://anki.maranica.com/"


def get_request_sid(request: Optional[Any] = None) -> Optional[str]:
    """Extracts and verifies session ID from request cookies or query params."""
    if not request:
        return None
    try:
        raw_cookie = request.cookies.get(google_auth.SESSION_COOKIE_NAME)
        if raw_cookie:
            sid = google_auth.verify_session_token(raw_cookie)
            if sid:
                return sid
    except Exception:
        pass
    try:
        query_sid = request.query_params.get("sid")
        if query_sid:
            sid = google_auth.verify_session_token(query_sid)
            if sid:
                return sid
    except Exception:
        pass
    return None


def get_user_session_info(request: Optional[Any] = None) -> Dict[str, Any]:
    """Retrieves authenticated user session information and profile picture for the active request."""
    # Support previewing authenticated UI via test_user query parameter
    if request and request.query_params.get("test_user"):
        return {
            "is_authenticated": True,
            "user_email": "mara@sfu.ca",
            "user_picture": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100&auto=format&fit=crop&q=80",
            "user_name": "Mara Nica",
            "cached_creds": None,
        }

    sid = get_request_sid(request)
    cached_creds, cached_email = google_auth._load_cached_creds(sid, allow_fallback=False)
    is_authenticated = bool(cached_creds and not cached_creds.expired)

    if not is_authenticated or not cached_email:
        return {
            "is_authenticated": False,
            "user_email": "Default User (Local)",
            "user_picture": None,
            "user_name": None,
            "cached_creds": None,
        }

    profile = google_auth.get_user_profile(cached_email)
    picture = profile.get("picture")
    name = profile.get("name")

    if not picture and cached_creds:
        try:
            oauth_service = google_auth.build('oauth2', 'v2', credentials=cached_creds)
            info = oauth_service.userinfo().get().execute()
            picture = info.get("picture")
            name = info.get("name")
            if picture:
                profile["picture"] = picture
            if name:
                profile["name"] = name
            google_auth.save_user_profile(cached_email, profile)
        except Exception as e:
            print("Error retrieving profile picture:", e)

    return {
        "is_authenticated": True,
        "user_email": cached_email,
        "user_picture": picture,
        "user_name": name,
        "cached_creds": cached_creds,
    }


def get_authenticated_drive_service(request: Optional[Any] = None, sid: Optional[str] = None):
    """Returns an authenticated Google Drive API service using cached user credentials for the active request session or sid."""
    if not sid and request:
        sid = get_request_sid(request)
    cached_creds, cached_email = google_auth._load_cached_creds(sid, allow_fallback=False)
    if cached_creds:
        try:
            if cached_creds.expired and cached_creds.refresh_token:
                cached_creds.refresh(google_auth.Request())
                if cached_email:
                    google_auth._save_cached_creds(cached_creds, cached_email)
            if not cached_creds.expired:
                return google_auth.build('drive', 'v3', credentials=cached_creds)
        except Exception as e:
            print("Error building Drive service from user credentials:", e)

    try:
        return anki_cli.get_drive_service()
    except Exception:
        return None

BASE_DIR = Path(__file__).resolve().parent
EXTRACTED_DIR = BASE_DIR / "extracted"
EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
REFERENCES_DIR = BASE_DIR / ".agents" / "skills" / "anki-card-generator" / "references"

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# In-memory store for active generation jobs and results
JOBS: Dict[str, Dict[str, Any]] = {}


def get_courses_list() -> List[Dict[str, str]]:
    """Discovers available courses from references/ directory or returns default set."""
    courses = []
    if REFERENCES_DIR.exists():
        for f in sorted(REFERENCES_DIR.glob("*.md")):
            if f.name.startswith("_"):
                continue
            content = f.read_text(encoding="utf-8", errors="replace")
            code = f.stem.upper().replace("-", " ")
            title = ""
            m_hdr = re.search(r"#\s*Course Profile:\s*([^\n—\-]+)[—\-]\s*([^\n]+)", content)
            if m_hdr:
                code = m_hdr.group(1).strip()
                title = m_hdr.group(2).strip()
            else:
                m_title = re.search(r"\*\*(?:Course Title):\*\*\s*([^\n]+)", content)
                if m_title:
                    title = m_title.group(1).strip()
            courses.append({"code": code, "title": title, "slug": f.stem, "filename": f.name})
    if not courses:
        courses = [
            {"code": "MBB 321", "title": "Intermediary Metabolism", "slug": "mbb-321", "filename": "mbb-321.md"},
            {"code": "BPK 207", "title": "Sensorimotor Control & Learning", "slug": "bpk-207", "filename": "bpk-207.md"},
            {"code": "BPK 305", "title": "Human Locomotor Biochemistry", "slug": "bpk-305", "filename": "bpk-305.md"},
        ]
    return courses


def add_new_course(course_code: str, course_title: str) -> bool:
    """Creates a new course markdown profile in references directory."""
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', course_code.strip()).lower().strip('-')
    if not slug:
        return False
    REFERENCES_DIR.mkdir(parents=True, exist_ok=True)
    ref_file = REFERENCES_DIR / f"{slug}.md"
    template_file = REFERENCES_DIR / "_course_template.md"
    clean_code = course_code.strip().upper()
    clean_compact = clean_code.replace(" ", "")
    if template_file.exists():
        template_text = template_file.read_text(encoding="utf-8")
        content = (
            template_text
            .replace("<COURSE_CODE>", clean_code)
            .replace("<COURSE_COMPACT>", clean_compact)
            .replace("<COURSE_DISPLAY>", clean_code)
            .replace("<COURSE_TITLE>", course_title.strip())
        )
    else:
        content = f"# Course Profile: {clean_code} — {course_title.strip()}\n\n- **Course Code:** `{clean_code}`\n- **Course Title:** {course_title.strip()}\n"
    ref_file.write_text(content, encoding="utf-8")
    return True


def delete_course(slug_or_code: str) -> bool:
    """Removes a course markdown profile from references directory."""
    target_slug = re.sub(r'[^a-zA-Z0-9]+', '-', slug_or_code.strip()).lower().strip('-')
    ref_file = REFERENCES_DIR / f"{target_slug}.md"
    if ref_file.exists():
        ref_file.unlink()
        return True
    return False


def format_card_html(text: str) -> str:
    """Renders Cloze markup {{c1::...}} through {{c9::...}} into styled HTML tags."""
    if not text:
        return ""
    # Convert newlines to breaks
    formatted = text.replace("\n", "<br>")

    # Generic replacement for any {{c(\d+)::(.*?)(?:::([^}]*))?}}
    def replace_cloze(m):
        idx = m.group(1)
        ans = m.group(2)
        hint = m.group(3) if len(m.groups()) >= 3 and m.group(3) else ""
        hint_text = f' <span class="opacity-60 text-xs">[{hint}]</span>' if hint else ""
        cls_num = ((int(idx) - 1) % 6) + 1
        return f'<span class="cloze-c{cls_num}" title="Cloze #{idx}">{ans}{hint_text}</span>'

    formatted = re.sub(
        r'\{\{c(\d+)::(.*?)(?:::([^}]*))?\}\}',
        replace_cloze,
        formatted
    )
    return formatted


def render_extra_html(extra_text: str) -> str:
    """
    Renders the extra field for preview:
    - Strips the footer if present
    - Converts <img src="filename"> to clean, full-size <img src="/api/media/filename">
    - Formats line breaks and inline markdown
    """
    if not extra_text:
        return ""
    cleaned = generator.strip_card_footer(extra_text)

    # Rewrite local img src to /api/media/...
    def img_sub(m):
        src = m.group(1)
        if not src.startswith("http") and not src.startswith("/api/media/"):
            return (
                f'<div class="my-3 rounded-xl overflow-hidden border border-slate-200/90 shadow-2xs bg-slate-50 inline-block">'
                f'  <img src="/api/media/{src}" alt="{html.escape(src)}" class="max-h-72 w-auto object-contain rounded-xl cursor-pointer hover:opacity-95 transition" onclick="window.open(this.src)" title="Click to view full image in new tab">'
                f'</div>'
            )
        return m.group(0)

    cleaned = re.sub(r'<img\s+[^>]*src=[\'"]([^\'"]+)[\'"][^>]*>', img_sub, cleaned)
    cleaned = cleaned.replace("\n", "<br>")
    return cleaned


def extract_images_from_extra(extra_text: str) -> List[str]:
    """Finds all image filenames referenced in extra field."""
    if not extra_text:
        return []
    return re.findall(r'<img\s+[^>]*src=[\'"]([^\'"]+)[\'"]', extra_text)


def format_inline_markdown(text: str) -> str:
    """Converts bold, italics, and inline code to safe HTML tags."""
    t = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    t = re.sub(r'\*(.*?)\*', r'<em>\1</em>', t)
    t = re.sub(r'`(.*?)`', r'<code class="px-1 py-0.5 bg-slate-100 rounded text-xs font-mono">\1</code>', t)
    return t


# ============================================================================
# Page & Modal Endpoints
# ============================================================================

async def index(request):
    """Main application home page."""
    # Redirect if ?guide=... was requested
    guide_param = request.query_params.get("guide")
    if guide_param:
        return RedirectResponse(f"/guide/{guide_param}", status_code=303)

    # Handle Google OAuth code callback
    code = request.query_params.get("code")
    if code:
        try:
            client_config = google_auth.get_client_config()
            redirect_uri = get_oauth_redirect_uri(request)
            if client_config:
                flow = google_auth.Flow.from_client_config(
                    client_config,
                    scopes=google_auth.SCOPES,
                    redirect_uri=redirect_uri,
                    autogenerate_code_verifier=False
                )
                flow.fetch_token(code=code)
                creds = flow.credentials
                oauth_service = google_auth.build('oauth2', 'v2', credentials=creds)
                user_info_resp = oauth_service.userinfo().get().execute()
                email = user_info_resp.get("email", "Local User")
                picture = user_info_resp.get("picture")
                name = user_info_resp.get("name")
                google_auth._save_cached_creds(creds, email)
                profile = google_auth.get_user_profile(email)
                if picture:
                    profile["picture"] = picture
                if name:
                    profile["name"] = name
                google_auth.save_user_profile(email, profile)

                session_token = google_auth.create_session_token(email)
                response = RedirectResponse("/", status_code=303)
                proto = request.headers.get("x-forwarded-proto", "")
                is_secure = request.url.scheme == "https" or "https" in proto
                response.set_cookie(
                    key=google_auth.SESSION_COOKIE_NAME,
                    value=session_token,
                    max_age=30 * 24 * 3600,
                    httponly=True,
                    samesite="lax",
                    secure=is_secure
                )
                return response
        except Exception as e:
            print("OAuth exchange error:", e)

    # Retrieve user info from session or default
    user_info = get_user_session_info(request)
    user_email = user_info["user_email"]

    test_cards_html = None
    if request.query_params.get("test_cards"):
        test_job_id = "test-preview-job"
        sample_notes = [
            {
                "text": "The {{c1::muscle spindle}} is a proprioceptor that detects changes in {{c2::muscle length}} and the {{c3::rate of length change}}.",
                "extra": "<img src=\"slide_24_fig_1.jpeg\"><br><b>Sensory Innervation:</b> Primary (Ia) sensory afferents spiral around intrafusal fibers.",
            },
            {
                "text": "The equilibrium potential for potassium ($E_K$) is given by the Nernst Equation: {{c1::$$E_K = \\frac{RT}{zF} \\ln \\frac{[K^+]_o}{[K^+]_i}$$}}.",
                "extra": "At 37°C, this simplifies to $E_K = 61.5 \\text{ mV} \\cdot \\log_{10} \\frac{[K^+]_o}{[K^+]_i}$.",
            },
            {
                "text": "Golgi tendon organs are arranged in {{c1::series}} with extrafusal muscle fibers, whereas muscle spindles are arranged in {{c2::parallel}}.",
                "extra": "<b>Differential Sensitivity:</b> GTOs fire strongly during active contraction; spindles fire during passive stretch.",
            }
        ]
        # In test mode, allow simulating both guide present and not generated
        has_guide = not bool(request.query_params.get("no_guide"))
        guide_id = "BPK207_Session_3a" if has_guide else None

        for c in sample_notes:
            c["rendered_html"] = format_card_html(c.get("text", ""))
            clean_extra = generator.strip_card_footer(c.get("extra", ""))
            c["extra_clean"] = clean_extra
            c["extra_rendered"] = render_extra_html(clean_extra)
            c["images"] = extract_images_from_extra(clean_extra)
            c["ask_gemini_url"] = generator.build_ask_gemini_url(c.get("text", ""), clean_extra, "BPK 207", "3a")
            c["study_guide_url"] = f"/guide/{guide_id}" if guide_id else ""
            c["guide_exists"] = bool(guide_id)
            c["course_code"] = "BPK 207"
            c["session_num"] = "3a"

        JOBS[test_job_id] = {
            "result": {
                "job_id": test_job_id,
                "cards": sample_notes,
                "deck_name": "BPK 207 - Session 3a Cloze",
                "deck_filename": "BPK207_Session_3a_Cloze.apkg",
                "guide_id": guide_id,
                "course_code": "BPK 207",
                "session_num": "3a",
                "media_files": [],
            }
        }
        test_cards_html = templates.get_template("partials/cards_result.html").render(
            {
                "job_id": test_job_id,
                "cards": sample_notes,
                "deck_name": "BPK 207 - Session 3a Cloze",
                "deck_filename": "BPK207_Session_3a_Cloze.apkg",
                "guide_id": guide_id,
                "course_code": "BPK 207",
                "session_num": "3a",
                "initial_mode": request.query_params.get("mode", "preview"),
            }
        )

    test_pdf_html = ""
    if request.query_params.get("test_pdf"):
        audit_file = BASE_DIR / "extracted" / "BPK207_Session_3a" / "audit.json"
        audit_data = {}
        if audit_file.exists():
            try:
                audit_data = json.loads(audit_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        sections = audit_data.get("sections", [
            "3a.1 Section Learning Outcomes: Sensory receptors & proprioception",
            "3a.2 Why do we need sensory information? (Sensory feedback in motor control)",
            "3a.3 General principles of sensory physiology & neuron anatomy",
            "3a.3.4 Information extracted: Modality, Intensity, Duration",
            "3a.4 Somatosensory system: Proprioception & kinesthesia",
            "3a.4.2 Muscle spindles: Intrafusal vs. extrafusal fibers & Ia afferents",
            "3a.4.2.2 Alpha-gamma co-activation & maintaining sensitivity",
            "3a.4.2.8 Monosynaptic stretch reflex circuitry",
            "3a.4.3 Golgi tendon organs (GTO): Tension vs. length sensing",
            "3a.4.4 Joint receptors & capsule mechanics",
            "3a.4.7 Touch & Cutaneous mechanoreceptors: Merkel, Meissner, Pacinian, Ruffini",
            "3a.4.8 Ascending feedback pathways to the primary sensory cortex"
        ])
        observations = [
            "📌 **Exam Review Focus:** Pre-lecture review concepts (e.g. general action potential propagation) will be condensed, focusing strictly on high-yield testable distinctions.",
            "🖼️ **Diagram Integration:** Identified **14 illustrative anatomical figures/diagrams**. High-yield receptor and spindle cross-sections will be embedded directly in the extra explanation field."
        ]
        gap_warnings = [
            "📄 **Dense Letter Format Detected:** This lecture contains **278 words/page** across **12 key sections**. Regular Recap or Deep Dive is recommended to ensure complete mechanistic recall."
        ]
        test_pdf_html = templates.get_template("partials/file_preview.html").render(
            {
                "filename": "BPK 207 - Chapter 3a - Sensory Contribution.pdf",
                "pdf_path": str(audit_file),
                "num_pages": 25,
                "num_images": 14,
                "course_code": "BPK 207",
                "session_num": "3a",
                "proj_counts": {
                    "High Level": 18,
                    "Regular Recap": 38,
                    "Deep Dive": 62
                },
                "observations": [format_inline_markdown(o) for o in observations],
                "gap_warnings": [format_inline_markdown(w) for w in gap_warnings],
                "sections": sections,
                "courses": get_courses_list(),
            }
        )

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "version": version.__version__,
            "user_email": user_info["user_email"],
            "user_picture": user_info.get("user_picture"),
            "user_name": user_info.get("user_name"),
            "is_authenticated": user_info.get("is_authenticated", False),
            "test_cards_html": test_cards_html,
            "test_pdf_html": test_pdf_html,
        }
    )


async def modal_account(request):
    """Account profile modal with Google Sign-In support."""
    user_info = get_user_session_info(request)
    user_email = user_info["user_email"]
    is_authenticated = user_info["is_authenticated"]
    user_picture = user_info.get("user_picture")
    user_name = user_info.get("user_name")
    cached_creds = user_info.get("cached_creds")

    profile = google_auth.get_user_profile(user_email)
    user_key = profile.get("gemini_api_key", "")

    login_url = None
    client_configured = False

    client_config = google_auth.get_client_config()
    if client_config:
        client_configured = True
        if not is_authenticated:
            try:
                redirect_uri = get_oauth_redirect_uri(request)
                flow = google_auth.Flow.from_client_config(
                    client_config,
                    scopes=google_auth.SCOPES,
                    redirect_uri=redirect_uri,
                    autogenerate_code_verifier=False
                )
                auth_kwargs = {"access_type": "offline", "include_granted_scopes": "true"}
                if not google_auth._has_stored_refresh_token():
                    auth_kwargs["prompt"] = "consent"
                login_url, _ = flow.authorization_url(**auth_kwargs)
            except Exception as e:
                print("Error generating Google OAuth URL:", e)

    return templates.TemplateResponse(
        request=request,
        name="partials/account_modal.html",
        context={
            "user_email": user_email,
            "user_key": user_key,
            "is_authenticated": is_authenticated,
            "user_picture": user_picture,
            "user_name": user_name,
            "login_url": login_url,
            "client_configured": client_configured,
        }
    )


async def auth_logout(request):
    """Logs out active session, removes its cached creds, and clears the session cookie."""
    sid = get_request_sid(request)
    if sid:
        google_auth.clear_session_creds(sid)
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(google_auth.SESSION_COOKIE_NAME)
    return response


async def save_profile_key(request):
    """Saves user personal Gemini API key for active session."""
    user_info = get_user_session_info(request)
    user_email = user_info.get("user_email")
    if not user_info.get("is_authenticated") or not user_email:
        return HTMLResponse(
            '<div class="p-2.5 bg-rose-50 text-rose-800 rounded-lg text-xs font-semibold border border-rose-200">'
            'Please sign in with Google to save your personal API key.'
            '</div>',
            status_code=401
        )
    form = await request.form()
    personal_key = form.get("personal_key", "").strip()
    profile = google_auth.get_user_profile(user_email)
    profile["gemini_api_key"] = google_auth.normalize_gemini_api_key(personal_key)
    google_auth.save_user_profile(user_email, profile)

    return HTMLResponse(
        '<div class="p-2.5 bg-emerald-50 text-emerald-800 rounded-lg text-xs font-semibold border border-emerald-200">'
        '✓ Personal API key updated successfully!'
        '</div>'
    )


async def modal_settings(request):
    """Settings modal."""
    raw_key = google_auth.safe_get_secret("GEMINI_API_KEY", "")
    masked_key = f"{raw_key[:6]}...{raw_key[-4:]}" if len(raw_key) > 10 else "(Not configured)"
    folder_id = google_auth.safe_get_secret("TARGET_FOLDER_ID", "16v8w952a1v9FmZg8x5T_default")

    return templates.TemplateResponse(
        request=request,
        name="partials/settings_modal.html",
        context={
            "project_key_masked": masked_key,
            "target_folder_id": folder_id,
        }
    )


def get_study_guides_list() -> List[Dict[str, Any]]:
    """Returns a list of all saved study guides on disk."""
    guides_dir = EXTRACTED_DIR / "study_guides"
    guides_dir.mkdir(parents=True, exist_ok=True)

    guides_list = []
    for json_file in sorted(guides_dir.glob("*_guide.json"), key=os.path.getmtime, reverse=True):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            gid = data.get("guide_id") or json_file.stem.replace("_guide", "")
            has_pdf = (guides_dir / f"{gid}_Study_Guide.pdf").exists()
            guides_list.append({
                "id": gid,
                "title": data.get("title", gid),
                "course": data.get("course_code", "Course"),
                "session": data.get("session_num", "1"),
                "has_pdf": has_pdf,
            })
        except Exception:
            continue
    return guides_list


async def modal_guides(request):
    """Lists saved Study Guides."""
    guides_list = get_study_guides_list()
    return templates.TemplateResponse(
        request=request,
        name="partials/guides_modal.html",
        context={
            "guides": guides_list,
        }
    )


async def guides_delete(request):
    """Deletes a study guide locally and on Google Drive, then returns updated modal body."""
    guide_id = request.query_params.get("id", "").strip()
    if guide_id:
        generator.delete_local_study_guide(guide_id, BASE_DIR)
        drive_service = get_authenticated_drive_service(request)
        if drive_service and hasattr(anki_cli, "delete_study_guide_from_drive"):
            try:
                anki_cli.delete_study_guide_from_drive(drive_service, guide_id)
            except Exception as e:
                print(f"Notice: Google Drive study guide deletion: {e}")

    guides_list = get_study_guides_list()
    return templates.TemplateResponse(
        request=request,
        name="partials/guides_modal_body.html",
        context={
            "guides": guides_list,
        }
    )


async def modal_courses(request):
    """Renders the Course Management modal."""
    courses = get_courses_list()
    return templates.TemplateResponse(
        request=request,
        name="partials/courses_modal.html",
        context={"courses": courses}
    )


async def courses_options(request):
    """Returns <option> tags for target course dropdown."""
    selected_code = request.query_params.get("selected", "")
    courses = get_courses_list()
    course_codes = [c["code"] for c in courses]
    return templates.TemplateResponse(
        request=request,
        name="partials/course_options.html",
        context={
            "courses": courses,
            "selected_code": selected_code,
            "course_codes": course_codes
        }
    )


async def courses_add(request):
    """Adds a new course and returns updated modal body with HX-Trigger."""
    form = await request.form()
    course_code = form.get("course_code", "").strip()
    course_title = form.get("course_title", "").strip()
    if course_code:
        add_new_course(course_code, course_title)
    courses = get_courses_list()
    html_content = templates.get_template("partials/courses_modal_body.html").render({"courses": courses})
    response = HTMLResponse(html_content)
    response.headers["HX-Trigger"] = "coursesChanged"
    return response


async def courses_delete(request):
    """Deletes a course and returns updated modal body with HX-Trigger."""
    slug = request.query_params.get("slug", "").strip()
    if slug:
        delete_course(slug)
    courses = get_courses_list()
    html_content = templates.get_template("partials/courses_modal_body.html").render({"courses": courses})
    response = HTMLResponse(html_content)
    response.headers["HX-Trigger"] = "coursesChanged"
    return response


def get_api_keys_pool(request: Optional[Any] = None, sid: Optional[str] = None) -> List[str]:
    """Retrieves list of active Gemini API keys (user profile key + backup key) for the active session or sid."""
    if not sid and request:
        sid = get_request_sid(request)
    cached_creds, cached_email = google_auth._load_cached_creds(sid, allow_fallback=False)
    user_email = cached_email or "Local User"
    profile = google_auth.get_user_profile(user_email)
    user_key = profile.get("gemini_api_key", "")
    project_key = google_auth.safe_get_secret("GEMINI_API_KEY", "")
    keys_pool = []
    if user_key:
        keys_pool.append(user_key)
    if project_key and project_key != user_key:
        keys_pool.append(project_key)
    return keys_pool


async def modal_request_guide(request):
    """Renders the modal for requesting a study guide on demand."""
    course_code = request.query_params.get("course_code") or "BPK 207"
    session_num = request.query_params.get("session_num") or "1"
    job_id = request.query_params.get("job_id", "")

    return templates.TemplateResponse(
        request=request,
        name="partials/request_guide_modal.html",
        context={
            "course_code": course_code,
            "session_num": session_num,
            "job_id": job_id,
        }
    )


async def generate_guide_on_demand(request):
    """Generates an illustrated study guide on-demand and returns ready fragment."""
    course_code = request.query_params.get("course_code") or "BPK 207"
    session_num = request.query_params.get("session_num") or "1"
    job_id = request.query_params.get("job_id", "")

    clean_course = course_code.replace(" ", "")
    expected_id = f"{clean_course}_Session_{session_num}"
    guides_dir = EXTRACTED_DIR / "study_guides"
    guides_dir.mkdir(parents=True, exist_ok=True)
    guide_html = guides_dir / f"{expected_id}_Study_Guide.html"
    guide_pdf = guides_dir / f"{expected_id}_Study_Guide.pdf"
    guide_json = guides_dir / f"{expected_id}_guide.json"

    # Check if a valid, non-placeholder guide already exists on disk
    is_valid_guide = False
    if guide_html.exists() and guide_pdf.exists():
        try:
            content = guide_html.read_text(encoding="utf-8")
            if "Generated on demand." not in content and len(content) > 500:
                is_valid_guide = True
        except Exception:
            pass

    if not is_valid_guide:
        # 1. Retrieve slides_data from job memory if available
        slides_data = []
        if job_id and job_id in JOBS:
            job_obj = JOBS[job_id]
            slides_data = job_obj.get("slides_data", [])
            if not slides_data and job_obj.get("result"):
                slides_data = job_obj["result"].get("slides_data", [])

        # 2. Check expected_id directory on disk
        if not slides_data:
            audit_file = EXTRACTED_DIR / expected_id / "audit.json"
            if audit_file.exists():
                try:
                    ad = json.loads(audit_file.read_text(encoding="utf-8"))
                    slides_data = ad.get("slides_data", [])
                except Exception:
                    pass

        # 3. Check any audit.json files in extracted directory
        if not slides_data:
            for af in sorted(EXTRACTED_DIR.glob("**/audit.json")):
                try:
                    ad = json.loads(af.read_text(encoding="utf-8"))
                    if ad.get("slides_data"):
                        slides_data = ad["slides_data"]
                        break
                except Exception:
                    pass

        # 4. Check if lecture PDF can be analyzed on the fly
        if not slides_data:
            pdf_path_cand = None
            if job_id and job_id in JOBS:
                pdf_path_cand = JOBS[job_id].get("pdf_path")
            if not pdf_path_cand:
                pdf_matches = list(EXTRACTED_DIR.glob(f"*{clean_course}*Session*{session_num}*.pdf"))
                if pdf_matches:
                    pdf_path_cand = str(pdf_matches[0])
            if pdf_path_cand and os.path.exists(pdf_path_cand):
                try:
                    audit = generator.analyze_lecture_pdf(pdf_path_cand, BASE_DIR, course_code=course_code, session_num=session_num)
                    slides_data = audit.get("slides_data", [])
                except Exception as e:
                    print("Could not analyze lecture PDF on demand:", e)

        if not slides_data:
            return HTMLResponse(
                f'<div class="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl">'
                f'Could not find lecture slides data to generate study guide. Please generate the deck with the "Generate Supplementary Study Guide" option selected.'
                f'</div>',
                status_code=400
            )

        keys_pool = get_api_keys_pool(request)
        main_loop = asyncio.get_running_loop()
        try:
            guide_data = await main_loop.run_in_executor(
                None,
                lambda: generator.generate_study_guide(
                    slides_data=slides_data,
                    course_code=course_code,
                    session_num=session_num,
                    custom_focus="",
                    base_dir=BASE_DIR,
                    api_keys_pool=keys_pool,
                    app_base_url="https://anki.maranica.com/"
                )
            )
            if guide_data:
                guide_id = guide_data.get("guide_id") or expected_id
                guide_data["guide_id"] = guide_id
                await main_loop.run_in_executor(
                    None,
                    lambda: generator.save_study_guide_files(guide_data, BASE_DIR, app_base_url="https://anki.maranica.com/")
                )
                # Sync to Google Drive if authenticated
                sync_service = get_authenticated_drive_service(request)
                if sync_service:
                    try:
                        g_json = guides_dir / f"{guide_id}_guide.json"
                        g_html = guides_dir / f"{guide_id}_Study_Guide.html"
                        g_pdf = guides_dir / f"{guide_id}_Study_Guide.pdf"
                        if g_json.exists() and g_html.exists():
                            anki_cli.sync_study_guide_to_drive(
                                sync_service,
                                g_json,
                                g_html,
                                pdf_path=g_pdf if g_pdf.exists() else None
                            )
                    except Exception as se:
                        print("On-demand drive sync notice:", se)
            else:
                return HTMLResponse('<div class="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl">Study guide generation failed to produce sections.</div>', status_code=500)
        except Exception as e:
            return HTMLResponse(f'<div class="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl">Error generating study guide: {html.escape(str(e))}</div>', status_code=500)
    else:
        guide_id = expected_id

    if job_id and job_id in JOBS and JOBS[job_id].get("result"):
        JOBS[job_id]["result"]["guide_id"] = guide_id

    return templates.TemplateResponse(
        request=request,
        name="partials/guide_ready_fragment.html",
        context={
            "guide_id": guide_id,
            "course_code": course_code,
            "session_num": session_num,
        }
    )


# ============================================================================
# File Fetch & Upload Endpoints
# ============================================================================

def format_drive_error(err: Any) -> str:
    """Formats raw Google Drive exceptions into clear, human-readable explanations."""
    if not err:
        return "File could not be downloaded."
    err_str = str(err)
    if "404" in err_str or "notFound" in err_str:
        return "File not found. Please double-check the Google Drive link or ID."
    if "403" in err_str or "forbidden" in err_str or "insufficientPermissions" in err_str:
        return "Access denied. Your Google account does not have permission to view this file, or the link has not been shared with you."
    if "Please log in to your Google Account" in err_str:
        return "Authentication required to access private Google Drive files."
    if len(err_str) > 120 and "returned \"" in err_str:
        try:
            return err_str.split('returned "')[1].split('"')[0]
        except Exception:
            pass
    return err_str[:160]


async def drive_fetch(request):
    """Fetches a PDF from Google Drive via URL or ID."""
    form = await request.form()
    drive_url = form.get("drive_url", "").strip()

    if not drive_url:
        return HTMLResponse('<div class="p-4 bg-red-50 text-red-700 rounded-xl text-sm border border-red-200">Please provide a Google Drive link or ID.</div>')

    # Extract ID cleanly
    fid = anki_cli.extract_drive_id(drive_url)
    if not fid:
        return HTMLResponse('<div class="p-4 bg-red-50 text-red-700 rounded-xl text-sm border border-red-200">Could not extract a valid Google Drive file ID from the provided link.</div>')

    dest = EXTRACTED_DIR / f"drive_{fid}.pdf"
    download_success = False
    last_err = None

    # 1. Attempt authenticated download via Google Drive API if user is signed in
    drive_service = get_authenticated_drive_service(request)
    if drive_service:
        try:
            downloaded_path = anki_cli.download_drive_file(drive_service, fid, EXTRACTED_DIR)
            dest = Path(downloaded_path)
            download_success = True
        except Exception as e:
            last_err = e
            print("Drive API authenticated download failed, trying public fallback:", e)

    # 2. Fallback to public unauthenticated download
    if not download_success:
        try:
            import urllib.request
            public_url = f"https://drive.google.com/uc?export=download&id={fid}"
            req = urllib.request.Request(public_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                content = resp.read()
                if content.startswith(b'%PDF'):
                    dest = EXTRACTED_DIR / f"drive_{fid}.pdf"
                    with open(dest, 'wb') as f:
                        f.write(content)
                    download_success = True
        except Exception as e:
            if not last_err:
                last_err = e

    if not download_success:
        clean_err = format_drive_error(last_err)
        user_info = get_user_session_info(request)
        if not user_info.get("is_authenticated"):
            err_html = (
                f'<div class="p-4 bg-red-50 text-red-700 rounded-xl text-sm border border-red-200 space-y-2">'
                f'<div><strong>Fetch Failed:</strong> {clean_err}</div>'
                f'<div class="text-xs text-red-600">If this is a private university file, please '
                f'<button type="button" hx-get="/api/modal/account" hx-target="#modal-container-slot" class="font-bold underline text-red-800 hover:text-red-950">Sign in with Google</button> first, or set the file sharing to "Anyone with the link can view".</div>'
                f'</div>'
            )
        else:
            err_html = (
                f'<div class="p-4 bg-red-50 text-red-700 rounded-xl text-sm border border-red-200 space-y-2">'
                f'<div><strong>Fetch Failed:</strong> {clean_err}</div>'
                f'<div class="text-xs text-red-600">Signed in as <strong>{user_info.get("user_email")}</strong>. Ensure this account has view access to the file, or change the file sharing to "Anyone with the link can view".</div>'
                f'</div>'
            )
        return HTMLResponse(err_html)

    # Parse course and audit PDF
    try:
        c_disp, _, s_num = anki_cli.parse_course_and_session(dest.name)
        course_code = c_disp if c_disp != "UNKNOWN" else "MBB 321"
        session_num = s_num or "1"
        audit = generator.analyze_lecture_pdf(str(dest), BASE_DIR, course_code=course_code, session_num=session_num)
        total_pages = audit["total_pages"]
        slides_data = audit["slides_data"]
        num_images = sum(len(s.get("figure_paths", [])) for s in slides_data)

        sections = audit.get("sections", [])
        if not sections and slides_data:
            headings = []
            for s in slides_data:
                lines = [l.strip() for l in s.get("text", "").split("\n") if l.strip()]
                if lines:
                    title_candidate = lines[0]
                    if len(title_candidate) > 4 and title_candidate not in headings:
                        headings.append(f"Slide {s.get('page_num')}: {title_candidate[:60]}")
            sections = headings[:25]

        return templates.TemplateResponse(
            request=request,
            name="partials/file_preview.html",
            context={
                "filename": dest.name,
                "pdf_path": str(dest),
                "num_pages": total_pages,
                "num_images": num_images,
                "course_code": course_code,
                "session_num": session_num,
                "proj_counts": audit.get("projected_counts", {
                    "High Level": 15,
                    "Regular Recap": 25,
                    "Deep Dive": 40
                }),
                "observations": [format_inline_markdown(o) for o in audit.get("observations", [])],
                "gap_warnings": [format_inline_markdown(w) for w in audit.get("gap_warnings", [])],
                "sections": sections,
                "courses": get_courses_list(),
            }
        )
    except Exception as e:
        return HTMLResponse(
            f'<div class="p-4 bg-red-50 text-red-700 rounded-xl text-sm border border-red-200">'
            f'<strong>PDF Analysis Error:</strong> {e}</div>'
        )


async def direct_upload(request):
    """Handles direct PDF upload from local file picker."""
    form = await request.form()
    uploaded_file = form.get("file")

    if not uploaded_file or not hasattr(uploaded_file, "filename"):
        return HTMLResponse('<div class="p-4 bg-red-50 text-red-700 rounded-xl text-sm">No valid file uploaded.</div>')

    filename = uploaded_file.filename
    dest = EXTRACTED_DIR / filename
    content = await uploaded_file.read()
    dest.write_bytes(content)

    try:
        c_disp, _, s_num = anki_cli.parse_course_and_session(filename)
        course_code = c_disp if c_disp != "UNKNOWN" else "MBB 321"
        session_num = s_num or "1"
        audit = generator.analyze_lecture_pdf(str(dest), BASE_DIR, course_code=course_code, session_num=session_num)
        total_pages = audit["total_pages"]
        slides_data = audit["slides_data"]
        num_images = sum(len(s.get("figure_paths", [])) for s in slides_data)

        sections = audit.get("sections", [])
        if not sections and slides_data:
            headings = []
            for s in slides_data:
                lines = [l.strip() for l in s.get("text", "").split("\n") if l.strip()]
                if lines:
                    title_candidate = lines[0]
                    if len(title_candidate) > 4 and title_candidate not in headings:
                        headings.append(f"Slide {s.get('page_num')}: {title_candidate[:60]}")
            sections = headings[:25]

        return templates.TemplateResponse(
            request=request,
            name="partials/file_preview.html",
            context={
                "filename": filename,
                "pdf_path": str(dest),
                "num_pages": total_pages,
                "num_images": num_images,
                "course_code": course_code,
                "session_num": session_num,
                "proj_counts": audit.get("projected_counts", {
                    "High Level": 15,
                    "Regular Recap": 25,
                    "Deep Dive": 40
                }),
                "observations": [format_inline_markdown(o) for o in audit.get("observations", [])],
                "gap_warnings": [format_inline_markdown(w) for w in audit.get("gap_warnings", [])],
                "sections": sections,
                "courses": get_courses_list(),
            }
        )
    except Exception as e:
        return HTMLResponse(
            f'<div class="p-4 bg-red-50 text-red-700 rounded-xl text-sm border border-red-200">'
            f'<strong>PDF Analysis Error:</strong> {e}</div>'
        )


# ============================================================================
# Asynchronous Generation & Real-Time SSE Stream
# ============================================================================

async def generate_start(request):
    """Initializes generation job and returns the SSE progress listener container."""
    form = await request.form()
    pdf_path = form.get("pdf_path")
    filename = form.get("filename")
    course_code = form.get("course_code", "MBB 321")
    session_num = form.get("session_num", "1")
    density_mode = form.get("density_mode", "Regular Recap")
    try:
        target_count = int(form.get("target_count", 25))
    except Exception:
        target_count = 25
    custom_guidance = form.get("custom_guidance", "").strip()
    gen_study_guide = form.get("gen_study_guide") == "true"

    job_id = str(uuid.uuid4())[:8]
    queue = asyncio.Queue()

    JOBS[job_id] = {
        "queue": queue,
        "status": "running",
        "result": None,
        "course_code": course_code,
        "session_num": session_num,
    }

    request_sid = get_request_sid(request)
    app_base_url = get_oauth_redirect_uri(request)

    # Start generation in the background
    asyncio.create_task(run_generation_task(
        job_id, pdf_path, filename, course_code, session_num, 
        density_mode, target_count, custom_guidance, gen_study_guide,
        request_sid=request_sid, app_base_url=app_base_url
    ))

    return templates.TemplateResponse(
        request=request,
        name="partials/generation_progress.html",
        context={
            "job_id": job_id,
            "course_code": course_code,
            "session_num": session_num,
        }
    )


def compile_course_decks(
    course_code: str,
    session_num: str,
    notes: List[Dict[str, Any]],
    media_files: List[Any],
    drive_service: Optional[Any] = None,
    folder_id: Optional[str] = None,
    app_base_url: str = "https://anki.maranica.com/"
) -> Dict[str, Any]:
    """
    Builds or updates the Master Course .apkg (overwriting existing session cards)
    and also generates a standalone session .apkg.
    """
    clean_course = course_code.replace(" ", "")
    tag_str = f"#{clean_course}::Session::{session_num}"
    if not folder_id:
        folder_id = os.getenv("TARGET_FOLDER_ID", anki_cli.DEFAULT_SHARED_FOLDER_ID)

    # 1. Attach AI Tutor / Study Guide footer links to notes
    notes_with_links = generator.attach_footers_to_notes(
        notes,
        course_code=course_code,
        session_num=session_num,
        app_base_url=app_base_url
    )

    # 2. Locate baseline master deck (locally or from Google Drive)
    baseline_apkg = anki_cli.find_baseline_apkg(
        course_code,
        BASE_DIR,
        service=drive_service,
        folder_id=folder_id
    )
    deck_info = anki_cli.get_deck_info_from_apkg(baseline_apkg) if baseline_apkg else None

    if deck_info:
        canonical_deck_name = deck_info["deck_name"]
        canonical_file_name = deck_info["file_name"]
    else:
        canonical_deck_name = f"{course_code} - Flashcards"
        canonical_file_name = f"{clean_course} - Flashcards.apkg"

    master_path = EXTRACTED_DIR / canonical_file_name

    # 3. Compile or update master package
    if baseline_apkg and os.path.exists(str(baseline_apkg)):
        if Path(baseline_apkg).resolve() != master_path.resolve():
            shutil.copyfile(str(baseline_apkg), str(master_path))
        tot_notes, tot_cards = anki_cli.update_existing_apkg(
            master_path,
            notes_with_links,
            tag_str,
            replace_session_tag=True,
            media_files=media_files
        )
    else:
        tot_notes, tot_cards = anki_cli.create_new_apkg(
            master_path,
            canonical_deck_name,
            notes_with_links,
            tag_str,
            media_files=media_files
        )

    # 4. Also build standalone session package
    session_file_name = f"{clean_course}_Session_{session_num}_Cloze.apkg"
    session_path = EXTRACTED_DIR / session_file_name
    anki_cli.create_new_apkg(
        session_path,
        f"{course_code} - Session {session_num} Cloze",
        notes_with_links,
        tag_str,
        media_files=media_files
    )

    return {
        "master_path": master_path,
        "master_filename": canonical_file_name,
        "master_deck_name": canonical_deck_name,
        "session_path": session_path,
        "session_filename": session_file_name,
        "total_notes": tot_notes,
        "total_cards": tot_cards,
        "notes_with_links": notes_with_links,
        "tag_str": tag_str,
    }


async def run_generation_task(
    job_id: str, pdf_path: str, filename: str, course_code: str, session_num: str, 
    density_mode: str, target_count: int, custom_guidance: str, gen_study_guide: bool,
    request_sid: Optional[str] = None, app_base_url: str = "https://anki.maranica.com/"
):
    """Background worker for card and study guide generation."""
    queue = JOBS[job_id]["queue"]
    main_loop = asyncio.get_running_loop()

    async def emit_log(msg: str, percent: int = None, stage_title: str = None):
        payload = {"log": msg}
        if percent is not None:
            payload["percent"] = percent
        if stage_title:
            payload["title"] = stage_title
        await queue.put(payload)

    try:
        await emit_log("Analyzing lecture structure and auditing diagrams...", percent=10, stage_title="Auditing Lecture Material")
        pdf = Path(pdf_path)
        audit = generator.analyze_lecture_pdf(str(pdf), BASE_DIR, course_code=course_code, session_num=session_num)
        slides_data = audit["slides_data"]
        JOBS[job_id]["slides_data"] = slides_data
        JOBS[job_id]["pdf_path"] = str(pdf)

        # Build keys pool for the active request session
        keys_pool = get_api_keys_pool(sid=request_sid)

        await emit_log(
            f"Configured API Key pool ({len(keys_pool)} keys). Generating {target_count} cards ({density_mode})...", 
            percent=25, 
            stage_title="Generating Flashcards"
        )

        # Custom progress callback running inside thread pool
        def progress_cb(current, total, msg):
            pct = 25 + int((current / max(1, total)) * 45)
            asyncio.run_coroutine_threadsafe(
                emit_log(f"Batch {current}/{total}: {msg}", percent=pct, stage_title=f"Generating Cards ({current}/{total})"),
                main_loop
            )

        # Run card generation (blocking call inside executor)
        payload = await main_loop.run_in_executor(
            None,
            lambda: generator.generate_cards_chunked(
                slides_data=slides_data,
                course_code=course_code,
                session_num=session_num,
                density_mode=density_mode,
                target_count=target_count,
                custom_guidance=custom_guidance,
                base_dir=BASE_DIR,
                api_keys_pool=keys_pool,
                progress_callback=progress_cb
            )
        )
        notes = payload.get("notes", [])
        media_files = payload.get("media_files", [])

        await emit_log(f"Generated {len(notes)} Cloze cards. Building Anki packages...", percent=75, stage_title="Packaging Anki Decks")

        drive_service = get_authenticated_drive_service(sid=request_sid)
        folder_id = os.getenv("TARGET_FOLDER_ID", anki_cli.DEFAULT_SHARED_FOLDER_ID)

        deck_res = await main_loop.run_in_executor(
            None,
            lambda: compile_course_decks(
                course_code=course_code,
                session_num=session_num,
                notes=notes,
                media_files=media_files,
                drive_service=drive_service,
                folder_id=folder_id,
                app_base_url=app_base_url
            )
        )
        canonical_deck_name = deck_res["master_deck_name"]
        canonical_file_name = deck_res["master_filename"]
        session_apkg_name = deck_res["session_filename"]
        tot_notes = deck_res["total_notes"]
        master_output_apkg = deck_res["master_path"]

        clean_course = course_code.replace(" ", "")
        await emit_log(f"Packaged master deck '{canonical_deck_name}' ({tot_notes} total notes, replaced #{clean_course}::Session::{session_num}).", percent=80)

        guide_id = None
        if gen_study_guide:
            await emit_log("Generating Illustrated Supplementary Study Guide & PDF...", percent=85, stage_title="Creating Study Guide")
            try:
                guide_data = await main_loop.run_in_executor(
                    None,
                    lambda: generator.generate_study_guide(
                        slides_data=slides_data,
                        course_code=course_code,
                        session_num=session_num,
                        custom_focus="",
                        base_dir=BASE_DIR,
                        api_keys_pool=keys_pool,
                        app_base_url=app_base_url
                    )
                )
                if guide_data:
                    guide_id = guide_data.get("guide_id") or generator.get_study_guide_id(course_code, session_num)
                    guide_data["guide_id"] = guide_id
                    await main_loop.run_in_executor(
                        None,
                        lambda: generator.save_study_guide_files(guide_data, BASE_DIR, app_base_url=app_base_url)
                    )
                    await emit_log(f"Study Guide created & saved: {guide_id}", percent=95)
                    # Sync to Google Drive if authenticated
                    if drive_service:
                        try:
                            g_json = BASE_DIR / "extracted" / "study_guides" / f"{guide_id}_guide.json"
                            g_html = BASE_DIR / "extracted" / "study_guides" / f"{guide_id}_Study_Guide.html"
                            g_pdf = BASE_DIR / "extracted" / "study_guides" / f"{guide_id}_Study_Guide.pdf"
                            if g_json.exists() and g_html.exists():
                                anki_cli.sync_study_guide_to_drive(
                                    drive_service,
                                    g_json,
                                    g_html,
                                    folder_id=folder_id,
                                    pdf_path=g_pdf if g_pdf.exists() else None
                                )
                                await emit_log("Study Guide synced to Google Drive!", percent=97)
                        except Exception as sync_e:
                            print("Drive sync notice:", sync_e)
            except Exception as e:
                await emit_log(f"Warning: Study guide generation error: {e}", percent=90)

        # Sync Master Deck to Google Drive if authenticated
        if drive_service:
            try:
                await emit_log(f"Syncing updated master deck to Google Drive ({canonical_file_name})...", percent=98)
                remote_res = await main_loop.run_in_executor(
                    None,
                    lambda: anki_cli._upsert_drive_file(drive_service, master_output_apkg, folder_id=folder_id)
                )
                if remote_res:
                    await emit_log("Master deck synced to Google Drive!", percent=99)
            except Exception as de:
                print("Drive master deck sync notice:", de)

        # Format cards for preview & editor
        for c in notes:
            c["rendered_html"] = format_card_html(c.get("text", ""))
            raw_extra = c.get("extra", "")
            clean_extra = generator.strip_card_footer(raw_extra)
            c["extra_clean"] = clean_extra
            c["extra_rendered"] = render_extra_html(clean_extra)
            c["images"] = extract_images_from_extra(clean_extra)
            c["ask_gemini_url"] = generator.build_ask_gemini_url(c.get("text", ""), clean_extra, course_code, session_num)
            c["study_guide_url"] = f"/guide/{guide_id}" if guide_id else ""
            c["guide_exists"] = bool(guide_id)
            c["course_code"] = course_code
            c["session_num"] = session_num

        JOBS[job_id]["result"] = {
            "job_id": job_id,
            "cards": notes,
            "deck_name": canonical_deck_name,
            "deck_filename": canonical_file_name,
            "session_filename": session_apkg_name,
            "total_notes": tot_notes,
            "guide_id": guide_id,
            "course_code": course_code,
            "session_num": session_num,
            "media_files": media_files,
            "slides_data": slides_data,
            "pdf_path": str(pdf),
            "request_sid": request_sid,
            "app_base_url": app_base_url,
        }
        JOBS[job_id]["status"] = "complete"

        await emit_log("✨ Generation complete! Compiling review interface...", percent=100, stage_title="Done")
        await queue.put({"complete": True})

    except Exception as e:
        JOBS[job_id]["status"] = "error"
        await emit_log(f"❌ Error during generation: {str(e)}", percent=100, stage_title="Error")
        await queue.put({"error": str(e)})


async def generate_stream(request):
    """Streams SSE events to HTMX until generation completes."""
    job_id = request.query_params.get("job_id")
    if not job_id or job_id not in JOBS:
        return HTMLResponse("Job not found", status_code=404)

    queue = JOBS[job_id]["queue"]

    async def event_generator():
        while True:
            try:
                data = await asyncio.wait_for(queue.get(), timeout=30.0)
                if "complete" in data:
                    res = JOBS[job_id]["result"]
                    rendered_cards = templates.get_template("partials/cards_result.html").render(
                        {
                            "job_id": job_id,
                            "cards": res["cards"],
                            "deck_name": res["deck_name"],
                            "deck_filename": res["deck_filename"],
                            "session_filename": res.get("session_filename"),
                            "total_notes": res.get("total_notes"),
                            "guide_id": res["guide_id"],
                            "course_code": res.get("course_code", ""),
                            "session_num": res.get("session_num", ""),
                        }
                    )
                    yield format_sse(rendered_cards, event="finish")
                    break
                elif "error" in data:
                    err_html = (
                        f'<div class="p-6 bg-red-50 text-red-800 rounded-2xl border border-red-200 shadow-sm space-y-3 animate-in fade-in">'
                        f'  <div class="flex items-center gap-2 font-bold text-base text-red-900">'
                        f'    <span class="material-icons text-xl">error_outline</span>'
                        f'    <span>Generation Encountered an Error</span>'
                        f'  </div>'
                        f'  <div class="text-xs font-mono bg-white/80 p-3 rounded-xl border border-red-200 text-red-700 leading-relaxed overflow-x-auto">{html.escape(data["error"])}</div>'
                        f'  <button onclick="window.location.reload()" class="px-4 py-2 text-xs font-semibold bg-red-600 hover:bg-red-700 text-white rounded-xl shadow-xs transition inline-flex items-center gap-1.5">'
                        f'    <span class="material-icons text-sm">refresh</span> Try Again'
                        f'  </button>'
                        f'</div>'
                    )
                    yield format_sse(err_html, event="finish")
                    break
                else:
                    # Progress update via HTMX out-of-band swaps
                    pct = data.get("percent")
                    title = data.get("title")
                    log_msg = data.get("log")

                    oob_parts = []
                    if pct is not None:
                        oob_parts.append(
                            f'<div id="sse-progress-bar" hx-swap-oob="outerHTML" '
                            f'class="bg-gradient-to-r from-blue-500 to-brand h-full rounded-full transition-all duration-300" '
                            f'style="width: {pct}%"></div>'
                        )
                        oob_parts.append(
                            f'<span id="sse-percentage" hx-swap-oob="outerHTML" '
                            f'class="px-3 py-1 bg-blue-50 text-brand font-mono font-bold text-sm rounded-full border border-blue-100">'
                            f'{pct}%</span>'
                        )
                    if title:
                        oob_parts.append(
                            f'<h4 id="sse-stage-title" hx-swap-oob="outerHTML" '
                            f'class="font-bold text-slate-800 text-base">{html.escape(title)}</h4>'
                        )
                    if log_msg:
                        oob_parts.append(
                            f'<div id="sse-logs" hx-swap-oob="beforeend">'
                            f'  <div class="text-slate-300 text-[11px] font-mono leading-tight">↳ {html.escape(log_msg)}</div>'
                            f'  <script>document.getElementById("sse-log-container")?.scrollTo(0, 1e9);</script>'
                            f'</div>'
                        )

                    payload = "".join(oob_parts)
                    yield format_sse(payload, event="message")
            except asyncio.TimeoutError:
                # Keep-alive heartbeat
                yield ": ping\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# ============================================================================
# Downloads & Study Guide Static Serving
# ============================================================================

async def download_deck(request):
    """Serves the generated or master .apkg file for download."""
    deck_filename = request.path_params.get("deck_filename")
    target = EXTRACTED_DIR / deck_filename
    if not target.exists():
        # Case-insensitive fallback lookup
        for f in EXTRACTED_DIR.glob("*.apkg"):
            if f.name.lower() == deck_filename.lower():
                target = f
                break
    if not target.exists():
        return HTMLResponse("Deck not found", status_code=404)
    return FileResponse(
        str(target),
        filename=target.name,
        media_type="application/octet-stream"
    )


async def sync_deck_to_drive(request):
    """Syncs the master .apkg to Google Drive."""
    job_id = request.query_params.get("job_id")
    if not job_id or job_id not in JOBS or "result" not in JOBS[job_id]:
        return HTMLResponse('<span class="text-xs text-red-600 font-semibold">Session expired. Please re-generate.</span>', status_code=400)

    res = JOBS[job_id]["result"]
    deck_filename = res.get("deck_filename")
    apkg_path = EXTRACTED_DIR / deck_filename
    if not apkg_path.exists():
        return HTMLResponse('<span class="text-xs text-red-600 font-semibold">Deck file not found on disk.</span>', status_code=404)

    drive_service = get_authenticated_drive_service(request)
    if not drive_service:
        return HTMLResponse('<span class="text-xs text-amber-700 font-semibold">Please sign in with Google to sync to Drive.</span>', status_code=401)

    folder_id = os.getenv("TARGET_FOLDER_ID", anki_cli.DEFAULT_SHARED_FOLDER_ID)
    main_loop = asyncio.get_running_loop()
    try:
        remote = await main_loop.run_in_executor(
            None,
            lambda: anki_cli._upsert_drive_file(drive_service, apkg_path, folder_id=folder_id)
        )
        web_link = remote.get("webViewLink", f"https://drive.google.com/drive/folders/{folder_id}")
        return HTMLResponse(
            f'<div class="flex items-center gap-1.5 text-xs text-emerald-800 bg-emerald-100/90 px-3 py-1.5 rounded-xl border border-emerald-300 shadow-2xs animate-in fade-in">'
            f'  <span class="material-icons text-sm text-emerald-600">cloud_done</span>'
            f'  <span>Synced to Google Drive!</span>'
            f'  <a href="{web_link}" target="_blank" class="underline font-semibold ml-1 hover:text-emerald-950">Open in Drive</a>'
            f'</div>'
        )
    except Exception as e:
        return HTMLResponse(
            f'<div class="text-xs text-red-700 bg-red-50 px-3 py-1.5 rounded-xl border border-red-200">'
            f'Drive sync error: {html.escape(str(e))}'
            f'</div>',
            status_code=500
        )


async def view_guide(request):
    """Instant static viewer for generated Study Guide HTML."""
    guide_id = request.path_params.get("guide_id")
    clean_id = re.sub(r'[^A-Za-z0-9_-]', '', guide_id)
    guides_dir = EXTRACTED_DIR / "study_guides"
    guides_dir.mkdir(parents=True, exist_ok=True)
    html_target = guides_dir / f"{clean_id}_Study_Guide.html"
    if not html_target.exists():
        html_target = guides_dir / f"{clean_id}.html"

    # If not on local disk, try fetching from Google Drive
    if not html_target.exists():
        drive_service = get_authenticated_drive_service(request)
        if drive_service:
            try:
                g_data = anki_cli.fetch_study_guide_from_drive(drive_service, clean_id, BASE_DIR)
                if g_data:
                    generator.save_study_guide_files(g_data, BASE_DIR, app_base_url="https://anki.maranica.com/")
            except Exception as de:
                print("Drive fetch notice for HTML guide:", de)

    if not html_target.exists():
        # Check case-insensitive match
        for f in guides_dir.glob("*.html"):
            if clean_id.lower() in f.stem.lower():
                html_target = f
                break

    if not html_target.exists():
        return HTMLResponse(
            f'''<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Study Guide Not Found — Anki Flashcard Studio</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-50 flex items-center justify-center min-h-screen p-4 font-sans text-slate-800">
  <div class="max-w-md w-full bg-white p-8 rounded-2xl border border-slate-200 shadow-sm text-center space-y-4">
    <div class="w-14 h-14 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center mx-auto text-2xl font-bold">
      📚
    </div>
    <h2 class="text-xl font-bold text-slate-900">Study Guide Not Generated</h2>
    <p class="text-xs text-slate-500 leading-relaxed">
      A supplementary study guide has not been generated for <strong>{html.escape(clean_id)}</strong> yet. 
      You can generate one using the on-demand option at the bottom of the flashcard review page.
    </p>
    <div class="pt-2">
      <a href="/" class="inline-block px-5 py-2.5 bg-blue-600 text-white rounded-xl text-xs font-bold hover:bg-blue-700 transition shadow-xs">
        Return to Flashcard Studio
      </a>
    </div>
  </div>
</body>
</html>''',
            status_code=404
        )
    return HTMLResponse(html_target.read_text(encoding="utf-8"))


async def view_guide_pdf(request):
    """Instant download/view for generated Study Guide PDF with on-the-fly rendering."""
    guide_id = request.path_params.get("guide_id")
    clean_id = re.sub(r'[^A-Za-z0-9_-]', '', guide_id)
    guides_dir = EXTRACTED_DIR / "study_guides"
    guides_dir.mkdir(parents=True, exist_ok=True)
    pdf_target = guides_dir / f"{clean_id}_Study_Guide.pdf"

    # 1. Check if PDF already exists
    if not pdf_target.exists():
        for f in guides_dir.glob("*.pdf"):
            if clean_id.lower() in f.stem.lower():
                pdf_target = f
                break

    # 2. If PDF not found, check if JSON guide exists and render PDF
    if not pdf_target.exists():
        json_target = guides_dir / f"{clean_id}_guide.json"
        if not json_target.exists():
            for f in guides_dir.glob("*.json"):
                if clean_id.lower() in f.stem.lower():
                    json_target = f
                    break
        if json_target.exists():
            try:
                g_data = json.loads(json_target.read_text(encoding="utf-8"))
                generator.render_study_guide_pdf(g_data, pdf_target, app_base_url="https://anki.maranica.com/")
            except Exception as e:
                print(f"Error rendering PDF from JSON guide: {e}")

    # 3. If PDF still not found, check if HTML guide exists and render PDF via PyMuPDF Story
    if not pdf_target.exists():
        html_target = guides_dir / f"{clean_id}_Study_Guide.html"
        if not html_target.exists():
            html_target = guides_dir / f"{clean_id}.html"
        if not html_target.exists():
            for f in guides_dir.glob("*.html"):
                if clean_id.lower() in f.stem.lower():
                    html_target = f
                    break
        if html_target.exists():
            try:
                html_str = html_target.read_text(encoding="utf-8")
                for emoji_char in ["📇 ", "⬅️ ", "📚 ", "🎯 ", "🖼️ ", "⚡ "]:
                    html_str = html_str.replace(emoji_char, "")
                mediabox = pymupdf.paper_rect("letter")
                where = mediabox + (36, 36, -36, -36)
                story = pymupdf.Story(html=html_str)
                writer = pymupdf.DocumentWriter(str(pdf_target))
                more = True
                while more:
                    dev = writer.begin_page(mediabox)
                    more, _ = story.place(where)
                    story.draw(dev)
                    writer.end_page()
                writer.close()
            except Exception as e:
                print(f"Error rendering PDF from HTML guide: {e}")

    # 4. If still not found, try fetching from Google Drive
    if not pdf_target.exists():
        drive_service = get_authenticated_drive_service(request)
        if drive_service:
            try:
                g_data = anki_cli.fetch_study_guide_from_drive(drive_service, clean_id, BASE_DIR)
                if g_data:
                    generator.save_study_guide_files(g_data, BASE_DIR, app_base_url="https://anki.maranica.com/")
            except Exception as de:
                print("Drive fetch notice for PDF guide:", de)

    # 5. Serve PDF if available
    if pdf_target.exists():
        return FileResponse(
            str(pdf_target),
            filename=f"{clean_id}_Study_Guide.pdf",
            media_type="application/pdf"
        )

    # 6. Fallback styled error page
    return HTMLResponse(
        f'''<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Study Guide PDF Not Found — Anki Flashcard Studio</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-50 flex items-center justify-center min-h-screen p-4 font-sans text-slate-800">
  <div class="max-w-md w-full bg-white p-8 rounded-2xl border border-slate-200 shadow-sm text-center space-y-4">
    <div class="w-14 h-14 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center mx-auto text-2xl font-bold">
      📄
    </div>
    <h2 class="text-xl font-bold text-slate-900">Study Guide PDF Not Found</h2>
    <p class="text-xs text-slate-500 leading-relaxed">
      The PDF study guide for <strong>{html.escape(clean_id)}</strong> could not be located.
      You can view the web version or generate a new study guide from your flashcard deck.
    </p>
    <div class="flex items-center justify-center gap-2 pt-2">
      <a href="/guide/{clean_id}" class="px-4 py-2 bg-slate-100 text-slate-700 rounded-xl text-xs font-semibold hover:bg-slate-200 transition">
        View Web Guide
      </a>
      <a href="/" class="px-4 py-2 bg-blue-600 text-white rounded-xl text-xs font-bold hover:bg-blue-700 transition">
        Return to Studio
      </a>
    </div>
  </div>
</body>
</html>''',
        status_code=404
    )


async def serve_media(request):
    """Safely serves extracted slide images and figures."""
    filename = request.path_params.get("filename", "")
    safe_name = Path(filename).name
    # Search in EXTRACTED_DIR
    matches = list(EXTRACTED_DIR.glob(f"**/{safe_name}"))
    if matches and matches[0].is_file():
        suffix = matches[0].suffix.lower()
        media_type = "image/jpeg" if suffix in [".jpg", ".jpeg"] else ("image/png" if suffix == ".png" else "application/octet-stream")
        return FileResponse(str(matches[0]), media_type=media_type)
    return HTMLResponse("Image not found", status_code=404)


async def update_deck(request):
    """Updates cards in memory and rebuilds the .apkg with user edits."""
    form = await request.form()
    job_id = form.get("job_id")
    if not job_id or job_id not in JOBS or "result" not in JOBS[job_id]:
        return HTMLResponse('<div class="p-4 bg-red-50 text-red-700 rounded-xl">Session expired. Please re-generate.</div>', status_code=400)

    res = JOBS[job_id]["result"]
    course_code = res.get("course_code", "Course")
    session_num = res.get("session_num", "1")
    media_files = res.get("media_files", [])
    output_apkg = EXTRACTED_DIR / res["deck_filename"]
    deck_name = res["deck_name"]
    clean_course = course_code.replace(" ", "")

    updated_cards = []
    # Collect all front_{idx} and extra_{idx}
    indices = sorted([int(k.split("_")[1]) for k in form.keys() if k.startswith("front_")])
    for idx in indices:
        front_val = form.get(f"front_{idx}", "").strip()
        extra_val = form.get(f"extra_{idx}", "").strip()
        if front_val:
            clean_extra = generator.strip_card_footer(extra_val)
            updated_cards.append({
                "text": front_val,
                "extra": clean_extra,
                "rendered_html": format_card_html(front_val),
                "extra_clean": clean_extra,
                "extra_rendered": render_extra_html(clean_extra),
                "images": extract_images_from_extra(clean_extra),
                "ask_gemini_url": generator.build_ask_gemini_url(front_val, clean_extra, course_code, session_num),
                "study_guide_url": f"/guide/{res.get('guide_id')}" if res.get('guide_id') else "",
                "guide_exists": bool(res.get('guide_id')),
                "course_code": course_code,
                "session_num": session_num,
            })

    res["cards"] = updated_cards

    request_sid = res.get("request_sid") or get_request_sid(request)
    app_base_url = res.get("app_base_url") or get_oauth_redirect_uri(request)
    drive_service = get_authenticated_drive_service(request, sid=request_sid)
    folder_id = os.getenv("TARGET_FOLDER_ID", anki_cli.DEFAULT_SHARED_FOLDER_ID)

    # Rebuild the Master .apkg and standalone session package
    main_loop = asyncio.get_running_loop()
    deck_res = await main_loop.run_in_executor(
        None,
        lambda: compile_course_decks(
            course_code=course_code,
            session_num=session_num,
            notes=updated_cards,
            media_files=media_files,
            drive_service=drive_service,
            folder_id=folder_id,
            app_base_url=app_base_url
        )
    )
    res["deck_name"] = deck_res["master_deck_name"]
    res["deck_filename"] = deck_res["master_filename"]
    res["session_filename"] = deck_res["session_filename"]
    res["total_notes"] = deck_res["total_notes"]

    # Sync to Google Drive if authenticated
    if drive_service:
        try:
            await main_loop.run_in_executor(
                None,
                lambda: anki_cli._upsert_drive_file(drive_service, deck_res["master_path"], folder_id=folder_id)
            )
        except Exception as de:
            print("Drive deck sync notice on update:", de)

    banner_html = templates.get_template("partials/deck_banner.html").render(
        {
            "job_id": job_id,
            "cards": updated_cards,
            "deck_name": res["deck_name"],
            "deck_filename": res["deck_filename"],
            "session_filename": res.get("session_filename"),
            "total_notes": res.get("total_notes"),
            "guide_id": res.get("guide_id"),
            "course_code": course_code,
            "session_num": session_num,
            "success_msg": f"✨ Deck successfully updated & rebuilt! Master deck total: {res.get('total_notes')} cards."
        }
    )
    return HTMLResponse(banner_html)


async def add_card(request):
    """Returns HTML for a new blank card item row."""
    job_id = request.query_params.get("job_id", "")
    card_index = int(request.query_params.get("card_index", 0))
    new_card = {
        "text": "New question with {{c1::cloze deletion}}",
        "extra": "",
        "rendered_html": format_card_html("New question with {{c1::cloze deletion}}"),
        "extra_clean": "",
        "extra_rendered": "",
        "images": [],
        "ask_gemini_url": "#",
        "study_guide_url": "",
    }
    card_html = templates.get_template("partials/single_card_item.html").render(
        {
            "card": new_card,
            "index": card_index,
            "job_id": job_id,
            "is_new": True,
        }
    )
    return HTMLResponse(card_html)


# ============================================================================
# Application Routing Setup
# ============================================================================

routes = [
    Route("/", endpoint=index, methods=["GET"]),
    Route("/api/modal/account", endpoint=modal_account, methods=["GET"]),
    Route("/api/auth/logout", endpoint=auth_logout, methods=["GET"]),
    Route("/api/modal/settings", endpoint=modal_settings, methods=["GET"]),
    Route("/api/modal/guides", endpoint=modal_guides, methods=["GET"]),
    Route("/api/guides/delete", endpoint=guides_delete, methods=["POST"]),
    Route("/api/modal/courses", endpoint=modal_courses, methods=["GET"]),
    Route("/api/modal/request-guide", endpoint=modal_request_guide, methods=["GET"]),
    Route("/api/guide/generate-on-demand", endpoint=generate_guide_on_demand, methods=["POST"]),
    Route("/api/courses/options", endpoint=courses_options, methods=["GET"]),
    Route("/api/courses/add", endpoint=courses_add, methods=["POST"]),
    Route("/api/courses/delete", endpoint=courses_delete, methods=["POST"]),
    Route("/api/profile/key", endpoint=save_profile_key, methods=["POST"]),
    Route("/api/drive/fetch", endpoint=drive_fetch, methods=["POST"]),
    Route("/api/upload", endpoint=direct_upload, methods=["POST"]),
    Route("/api/generate/start", endpoint=generate_start, methods=["POST"]),
    Route("/api/generate/stream", endpoint=generate_stream, methods=["GET"]),
    Route("/api/deck/download/{deck_filename:path}", endpoint=download_deck, methods=["GET"]),
    Route("/api/deck/sync", endpoint=sync_deck_to_drive, methods=["POST"]),
    Route("/api/deck/update", endpoint=update_deck, methods=["POST"]),
    Route("/api/card/add", endpoint=add_card, methods=["POST"]),
    Route("/api/media/{filename:path}", endpoint=serve_media, methods=["GET"]),
    Route("/guide/{guide_id}", endpoint=view_guide, methods=["GET"]),
    Route("/guide/{guide_id}/pdf", endpoint=view_guide_pdf, methods=["GET"]),
    Route("/favicon.ico", endpoint=lambda req: FileResponse(BASE_DIR / "static" / "favicon.ico", media_type="image/x-icon"), methods=["GET"]),
    Mount("/static", app=StaticFiles(directory=str(BASE_DIR / "static")), name="static"),
]

app = Starlette(debug=True, routes=routes)

if __name__ == "__main__":
    import uvicorn
    print("Launching Anki Flashcard Studio (Starlette + HTMX) on http://0.0.0.0:8000...")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
