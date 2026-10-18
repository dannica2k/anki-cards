"""
Google OAuth 2.0 Web Authentication helper for Streamlit.
Handles OAuth redirect flow, token exchange, and building user drive services.
"""

import os
import streamlit as st
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/userinfo.email',
    'openid'
]


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


def init_google_auth(redirect_uri: str):
    """
    Renders login state or initiates Google OAuth flow.
    Returns: (service, user_email_or_auth_url) or (None, None)
    """
    client_config = get_client_config()
    if not client_config:
        return None, None

    # Handle incoming OAuth callback code in query parameters
    query_params = st.query_params
    auth_code = query_params.get("code")

    if auth_code and "google_creds" not in st.session_state:
        try:
            # Relax scope comparison if Google returns openid/profile/email in different order
            os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
            flow = Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=redirect_uri)
            flow.fetch_token(code=auth_code)
            creds = flow.credentials
            st.session_state["google_creds"] = creds
            st.query_params.clear()
        except Exception as e:
            st.sidebar.error(f"Authentication failed: {e}")

    # Check if user is authenticated in session state
    if "google_creds" in st.session_state:
        creds = st.session_state["google_creds"]
        try:
            oauth_service = build('oauth2', 'v2', credentials=creds)
            user_info = oauth_service.userinfo().get().execute()
            user_email = user_info.get("email", "Signed in")
            drive_service = build('drive', 'v3', credentials=creds)
            return drive_service, user_email
        except Exception:
            del st.session_state["google_creds"]

    # Not logged in: generate auth URL
    flow = Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=redirect_uri)
    auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
    return None, auth_url
