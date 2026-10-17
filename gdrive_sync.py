#!/usr/bin/env python3
"""
Google Drive helper utility for downloading and uploading files.
"""

import os
import sys
import argparse
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

# Scopes needed for full Drive access
SCOPES = ['https://www.googleapis.com/auth/drive']

CREDENTIALS_FILE = os.path.expanduser('~/.config/gdrive/credentials.json')
TOKEN_FILE = os.path.expanduser('~/.config/gdrive/token.json')


def get_drive_service():
    """Authenticates and returns the Google Drive API service."""
    os.makedirs(os.path.dirname(CREDENTIALS_FILE), exist_ok=True)
    
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                # Also check current working directory for convenience
                if os.path.exists("credentials.json"):
                    cred_path = "credentials.json"
                else:
                    print(f"Error: Credentials file not found at '{CREDENTIALS_FILE}' or in the current directory.")
                    print("Please download your OAuth 2.0 Client ID JSON from Google Cloud Console and save it there.")
                    sys.exit(1)
            else:
                cred_path = CREDENTIALS_FILE

            flow = InstalledAppFlow.from_client_secrets_file(cred_path, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    return build('drive', 'v3', credentials=creds)


def download_file(file_id: str, destination_path: str):
    """Downloads a file by ID from Google Drive."""
    service = get_drive_service()
    
    # Retrieve file metadata (name) if destination is a directory
    file_metadata = service.files().get(fileId=file_id, fields='name').execute()
    dest = Path(destination_path)
    if dest.is_dir():
        dest = dest / file_metadata['name']

    print(f"Downloading '{file_metadata['name']}' (ID: {file_id}) to {dest}...")
    request = service.files().get_media(fileId=file_id)
    with open(dest, 'wb') as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                print(f"Download progress: {int(status.progress() * 100)}%")
    print(f"Download completed: {dest}")
    return dest


def upload_file(local_path: str, folder_id: str = None, description: str = None):
    """Uploads a local file to Google Drive (or updates it)."""
    service = get_drive_service()
    path = Path(local_path)
    if not path.is_file():
        print(f"Error: File '{local_path}' does not exist.")
        sys.exit(1)

    file_metadata = {'name': path.name}
    if folder_id:
        file_metadata['parents'] = [folder_id]
    if description:
        file_metadata['description'] = description

    media = MediaFileUpload(str(path), resumable=True)
    print(f"Uploading '{path.name}' to Google Drive...")
    file = service.files().create(body=file_metadata, media_body=media, fields='id, name, webViewLink').execute()
    print(f"File uploaded successfully!")
    print(f"File ID: {file.get('id')}")
    print(f"View Link: {file.get('webViewLink')}")
    return file


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Google Drive CLI Helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Download command
    download_parser = subparsers.add_parser("download", help="Download a file by Google Drive File ID")
    download_parser.add_argument("file_id", help="The Google Drive File ID")
    download_parser.add_argument("-o", "--output", default=".", help="Destination path or directory (default: current directory)")

    # Upload command
    upload_parser = subparsers.add_parser("upload", help="Upload a file to Google Drive")
    upload_parser.add_argument("file", help="Path to the local file to upload")
    upload_parser.add_argument("-f", "--folder-id", default=None, help="Target Google Drive folder ID (optional)")

    args = parser.parse_args()

    if args.command == "download":
        download_file(args.file_id, args.output)
    elif args.command == "upload":
        upload_file(args.file, args.folder_id)
