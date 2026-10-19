"""
Google OAuth 2.0 Web Authentication helper for Streamlit.
Handles OAuth redirect flow, persistent token caching across F5 reloads,
and silent re-authentication without forcing repeated consent screens.
"""

import os
import json
import hashlib
import datetime
from pathlib import Path
import streamlit as st
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/userinfo.email',
    'openid'
]

TOKEN_CACHE_DIR = Path(__file__).resolve().parent / "extracted" / ".tokens"


def safe_get_secret(key: str, default: str = "") -> str:
    """Safely reads from environment variables first, then st.secrets without raising StreamlitSecretNotFoundError."""
    val = os.getenv(key)
    if val:
        return val
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


def get_client_config():
    """Extracts client configuration from Streamlit secrets or environment variables."""
    client_id = safe_get_secret("GOOGLE_CLIENT_ID")
    client_secret = safe_get_secret("GOOGLE_CLIENT_SECRET")

    if client_id and client_secret:
        return {
            "web": {
                "client_id": client_id.strip(),
                "client_secret": client_secret.strip(),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs"
            }
        }
    return None


def _get_sid_for_email(email: str) -> str:
    return hashlib.sha256(email.lower().strip().encode("utf-8")).hexdigest()[:16]


def _has_stored_refresh_token() -> bool:
    """Checks whether any cached credential file on disk already holds a valid refresh_token."""
    if not TOKEN_CACHE_DIR.exists():
        return False
    for p in TOKEN_CACHE_DIR.glob("*.json"):
        if p.name.endswith("_profile.json"):
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            c_info = json.loads(data.get("creds_json", "{}"))
            if c_info.get("refresh_token"):
                return True
        except Exception:
            continue
    return False


def _save_cached_creds(creds: Credentials, email: str) -> str:
    """Saves credentials to disk cache (preserving any prior refresh_token) and returns a short session ID."""
    TOKEN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    sid = _get_sid_for_email(email)
    cache_file = TOKEN_CACHE_DIR / f"{sid}.json"
    last_file = TOKEN_CACHE_DIR / "last_active.json"

    creds_info = json.loads(creds.to_json())

    # Preserve existing refresh_token if Google omitted it on a subsequent non-consent login
    if not creds_info.get("refresh_token"):
        for candidate in [cache_file, last_file]:
            if candidate.exists():
                try:
                    prev_data = json.loads(candidate.read_text(encoding="utf-8"))
                    if prev_data.get("email", "").lower().strip() == email.lower().strip():
                        prev_creds = json.loads(prev_data.get("creds_json", "{}"))
                        if prev_creds.get("refresh_token"):
                            creds_info["refresh_token"] = prev_creds["refresh_token"]
                            creds._refresh_token = prev_creds["refresh_token"]
                            break
                except Exception:
                    pass

    data = {
        "email": email,
        "sid": sid,
        "creds_json": json.dumps(creds_info)
    }
    serialized = json.dumps(data)
    cache_file.write_text(serialized, encoding="utf-8")
    # Also save as 'last_active.json' so plain F5 / Ctrl+F5 without query params still restores login
    last_file.write_text(serialized, encoding="utf-8")
    return sid


def _load_cached_creds(sid: str = None):
    """
    Loads credentials from disk cache (either by sid or last_active.json).
    Constructs Credentials directly so missing refresh_token fields never raise ValueError.
    """
    TOKEN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    target = TOKEN_CACHE_DIR / f"{sid}.json" if sid else TOKEN_CACHE_DIR / "last_active.json"
    if not target.exists():
        target = TOKEN_CACHE_DIR / "last_active.json"
    if not target.exists():
        return None, None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        creds_info = json.loads(data["creds_json"])
        email = data.get("email")
        if not email or not creds_info.get("token"):
            return None, None

        expiry = None
        raw_expiry = creds_info.get("expiry")
        if raw_expiry:
            try:
                expiry = datetime.datetime.fromisoformat(raw_expiry.rstrip("Z")).replace(tzinfo=None)
            except Exception:
                expiry = None

        client_cfg = (get_client_config() or {}).get("web", {})
        creds = Credentials(
            token=creds_info.get("token"),
            refresh_token=creds_info.get("refresh_token"),
            token_uri=creds_info.get("token_uri") or client_cfg.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=creds_info.get("client_id") or client_cfg.get("client_id"),
            client_secret=creds_info.get("client_secret") or client_cfg.get("client_secret"),
            scopes=creds_info.get("scopes") or SCOPES,
            expiry=expiry
        )

        if creds.expired:
            if creds.refresh_token:
                creds.refresh(Request())
                _save_cached_creds(creds, email)
            else:
                return None, None
        return creds, email
    except Exception:
        return None, None


def clear_cached_creds():
    """Clears cached login session when user explicitly clicks Log Out."""
    email = st.session_state.get("google_email")
    if "google_creds" in st.session_state:
        del st.session_state["google_creds"]
    if "google_email" in st.session_state:
        del st.session_state["google_email"]
    if email:
        sid_file = TOKEN_CACHE_DIR / f"{_get_sid_for_email(email)}.json"
        if sid_file.exists():
            sid_file.unlink()
    last_file = TOKEN_CACHE_DIR / "last_active.json"
    if last_file.exists():
        last_file.unlink()
    if "sid" in st.query_params:
        del st.query_params["sid"]
    if "code" in st.query_params:
        del st.query_params["code"]


def init_google_auth(redirect_uri: str):
    """
    Renders login state or initiates Google OAuth flow.
    Maintains login across F5 / Ctrl+F5 browser reloads and avoids repeated consent prompts.
    Returns: (service, user_email_or_auth_url) or (None, None)
    """
    client_config = get_client_config()
    if not client_config:
        return None, None

    query_params = st.query_params
    auth_code = query_params.get("code")
    sid_param = query_params.get("sid")
    if not sid_param:
        try:
            sid_param = st.context.cookies.get("anki_sid")
        except Exception:
            sid_param = None

    # 1. Handle incoming OAuth callback code
    if auth_code and "google_creds" not in st.session_state:
        try:
            os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
            flow = Flow.from_client_config(
                client_config,
                scopes=SCOPES,
                redirect_uri=redirect_uri,
                autogenerate_code_verifier=False
            )
            flow.fetch_token(code=auth_code)
            creds = flow.credentials
            oauth_service = build('oauth2', 'v2', credentials=creds)
            user_info = oauth_service.userinfo().get().execute()
            user_email = user_info.get("email", "Signed in")

            st.session_state["google_creds"] = creds
            st.session_state["google_email"] = user_email
            sid = _save_cached_creds(creds, user_email)
            st.query_params.clear()
            st.query_params["sid"] = sid
        except Exception as e:
            st.sidebar.error(f"Authentication failed: {e}")

    # 2. Restore from disk cache on F5 / Ctrl+F5 reload if session_state was cleared
    if "google_creds" not in st.session_state:
        cached_creds, cached_email = _load_cached_creds(sid_param)
        if cached_creds and cached_email:
            st.session_state["google_creds"] = cached_creds
            st.session_state["google_email"] = cached_email
            restored_sid = _get_sid_for_email(cached_email)
            if query_params.get("sid") != restored_sid:
                st.query_params["sid"] = restored_sid

    # 3. Return active authenticated service if present
    if "google_creds" in st.session_state:
        creds = st.session_state["google_creds"]
        try:
            if creds.expired:
                if creds.refresh_token:
                    creds.refresh(Request())
                    if st.session_state.get("google_email"):
                        _save_cached_creds(creds, st.session_state["google_email"])
                else:
                    clear_cached_creds()
            if "google_creds" in st.session_state:
                user_email = st.session_state.get("google_email")
                if not user_email:
                    oauth_service = build('oauth2', 'v2', credentials=creds)
                    user_info = oauth_service.userinfo().get().execute()
                    user_email = user_info.get("email", "Signed in")
                    st.session_state["google_email"] = user_email
                drive_service = build('drive', 'v3', credentials=creds)
                return drive_service, user_email
        except Exception:
            clear_cached_creds()

    # 4. Not logged in: generate auth URL
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=redirect_uri,
        autogenerate_code_verifier=False
    )
    auth_kwargs = {
        "access_type": "offline",
        "include_granted_scopes": "true",
    }
    if not _has_stored_refresh_token():
        auth_kwargs["prompt"] = "consent"
    auth_url, _ = flow.authorization_url(**auth_kwargs)
    return None, auth_url


def normalize_gemini_api_key(key: str) -> str:
    """Ensures Gemini API key is properly trimmed and prefixed with AQ. if required."""
    if not key:
        return ""
    clean = key.strip()
    if clean.startswith("AQ.") or clean.startswith("AIzaSy"):
        return clean
    return f"AQ.{clean}"


def get_user_profile(email: str) -> dict:
    """Loads user profile preferences (like personal Gemini API key) from disk."""
    if not email:
        return {}
    TOKEN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    norm_email = email.lower().strip()
    sid = hashlib.sha256(norm_email.encode("utf-8")).hexdigest()[:16]
    profile_file = TOKEN_CACHE_DIR / f"{sid}_profile.json"
    data = {}
    if profile_file.exists():
        try:
            data = json.loads(profile_file.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    if not data.get("personal_gemini_api_key"):
        # Auto-associate pre-configured environment keys for designated family accounts
        if "maranica" in norm_email:
            env_k = safe_get_secret("MARA_GEMINI_API_KEY")
            if env_k:
                data["personal_gemini_api_key"] = normalize_gemini_api_key(env_k)
        elif "dannica" in norm_email:
            env_k = safe_get_secret("DANIEL_GEMINI_API_KEY") or safe_get_secret("GEMINI_API_KEY")
            if env_k:
                data["personal_gemini_api_key"] = normalize_gemini_api_key(env_k)
    return data


def save_user_profile(email: str, profile_data: dict):
    """Saves user profile preferences to disk."""
    if not email:
        return
    TOKEN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    norm_email = email.lower().strip()
    sid = hashlib.sha256(norm_email.encode("utf-8")).hexdigest()[:16]
    profile_file = TOKEN_CACHE_DIR / f"{sid}_profile.json"
    profile_file.write_text(json.dumps(profile_data, indent=2), encoding="utf-8")

