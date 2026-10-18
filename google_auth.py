"""
Google OAuth 2.0 Web Authentication helper for Streamlit.
Handles OAuth redirect flow, persistent token caching across F5 reloads,
and silent re-authentication without forcing repeated consent screens.
"""

import os
import json
import hashlib
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


def _save_cached_creds(creds: Credentials, email: str) -> str:
    """Saves credentials to disk cache and returns a short session token ID."""
    TOKEN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    sid = hashlib.sha256(email.lower().encode("utf-8")).hexdigest()[:16]
    cache_file = TOKEN_CACHE_DIR / f"{sid}.json"
    data = {
        "email": email,
        "creds_json": creds.to_json()
    }
    cache_file.write_text(json.dumps(data), encoding="utf-8")
    # Also save as 'last_active.json' so plain F5 without query params still restores login
    (TOKEN_CACHE_DIR / "last_active.json").write_text(json.dumps(data), encoding="utf-8")
    return sid


def _load_cached_creds(sid: str = None):
    """Loads credentials from disk cache (either by sid or last_active.json)."""
    TOKEN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    target = TOKEN_CACHE_DIR / f"{sid}.json" if sid else TOKEN_CACHE_DIR / "last_active.json"
    if not target.exists():
        target = TOKEN_CACHE_DIR / "last_active.json"
    if not target.exists():
        return None, None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        creds_info = json.loads(data["creds_json"])
        creds = Credentials.from_authorized_user_info(creds_info, SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            _save_cached_creds(creds, data["email"])
        return creds, data["email"]
    except Exception:
        return None, None


def clear_cached_creds():
    """Clears cached login session when user explicitly clicks Log Out."""
    if "google_creds" in st.session_state:
        del st.session_state["google_creds"]
    if "google_email" in st.session_state:
        del st.session_state["google_email"]
    last_file = TOKEN_CACHE_DIR / "last_active.json"
    if last_file.exists():
        last_file.unlink()
    st.query_params.clear()


def init_google_auth(redirect_uri: str):
    """
    Renders login state or initiates Google OAuth flow.
    Maintains login across F5 browser reloads and avoids repeated consent prompts.
    Returns: (service, user_email_or_auth_url) or (None, None)
    """
    client_config = get_client_config()
    if not client_config:
        return None, None

    query_params = st.query_params
    auth_code = query_params.get("code")
    sid_param = query_params.get("sid")

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

    # 2. Restore from disk cache on F5 reload if session_state was cleared
    if "google_creds" not in st.session_state:
        cached_creds, cached_email = _load_cached_creds(sid_param)
        if cached_creds and cached_email:
            st.session_state["google_creds"] = cached_creds
            st.session_state["google_email"] = cached_email

    # 3. Return active authenticated service if present
    if "google_creds" in st.session_state:
        creds = st.session_state["google_creds"]
        try:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
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

    # 4. Not logged in: generate auth URL WITHOUT prompt='consent' so returning users don't get the full approval flow
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=redirect_uri,
        autogenerate_code_verifier=False
    )
    auth_url, _ = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    return None, auth_url
