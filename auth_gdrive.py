#!/usr/bin/env python3
"""
Authorize Google Drive and save token.json.
Supports both automatic local browser launch and manual URL paste.
"""

import os
import sys
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/drive']
CREDENTIALS_FILE = os.path.expanduser('~/.config/gdrive/credentials.json')
TOKEN_FILE = os.path.expanduser('~/.config/gdrive/token.json')

def main():
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"Error: {CREDENTIALS_FILE} not found!")
        sys.exit(1)

    print("Initializing OAuth flow...")
    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)

    try:
        # Try local server first (opens browser automatically)
        print("Starting local auth server... (will open your default browser)")
        creds = flow.run_local_server(port=0, open_browser=True)
    except Exception as e:
        print(f"Local server failed ({e}), falling back to console flow...")
        creds = flow.run_console()

    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, 'w') as f:
        f.write(creds.to_json())

    print(f"\nSuccess! Token saved to: {TOKEN_FILE}")

if __name__ == '__main__':
    main()
