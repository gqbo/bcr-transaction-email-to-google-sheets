"""
OAuth Token Generator for BCR Email Sync

This script generates the OAuth token required for Gmail and Google Sheets APIs.
Run this ONCE on your local machine to authenticate.

Usage:
1. Download credentials.json from Google Cloud Console
2. Place credentials.json in the same directory as this script
3. Run: python generate_token.py
4. A browser window will open for authentication
5. token.json will be created after successful authentication

After running:
- Copy the contents of token.json to GitHub Secrets as GOOGLE_TOKEN
- Copy the contents of credentials.json to GitHub Secrets as GOOGLE_CREDENTIALS
"""

import os
import json
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Scopes required for Gmail and Sheets access
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/spreadsheets',
]

CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'


def main():
    """Generate OAuth token for Gmail and Sheets APIs."""
    print("=" * 50)
    print("BCR Email Sync - OAuth Token Generator")
    print("=" * 50)
    print()

    # Check if credentials.json exists
    creds_path = Path(CREDENTIALS_FILE)
    if not creds_path.exists():
        print(f"ERROR: {CREDENTIALS_FILE} not found!")
        print()
        print("To get credentials.json:")
        print("1. Go to https://console.cloud.google.com")
        print("2. Create a new project (or select existing)")
        print("3. Enable Gmail API and Google Sheets API")
        print("4. Go to Credentials > Create Credentials > OAuth Client ID")
        print("5. Select 'Desktop App' as application type")
        print("6. Download the JSON file")
        print(f"7. Rename it to '{CREDENTIALS_FILE}' and place it here")
        return

    creds = None
    token_path = Path(TOKEN_FILE)

    # Check if token already exists
    if token_path.exists():
        print(f"Found existing {TOKEN_FILE}")
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # If no valid credentials, run OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired token...")
            creds.refresh(Request())
        else:
            print("Starting OAuth flow...")
            print("A browser window will open for authentication.")
            print()

            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save the credentials
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

        print(f"\nToken saved to {TOKEN_FILE}")

    print()
    print("=" * 50)
    print("SUCCESS! Token generated.")
    print("=" * 50)
    print()
    print("Next steps:")
    print()
    print("1. Add GOOGLE_TOKEN to GitHub Secrets:")
    print(f"   - Open {TOKEN_FILE}")
    print("   - Copy the entire contents")
    print("   - Go to GitHub repo > Settings > Secrets > Actions")
    print("   - Create new secret named 'GOOGLE_TOKEN'")
    print("   - Paste the token JSON")
    print()
    print("2. Add GOOGLE_CREDENTIALS to GitHub Secrets:")
    print(f"   - Open {CREDENTIALS_FILE}")
    print("   - Copy the entire contents")
    print("   - Create new secret named 'GOOGLE_CREDENTIALS'")
    print("   - Paste the credentials JSON")
    print()
    print("3. Get your GEMINI_API_KEY:")
    print("   - Go to https://aistudio.google.com/app/apikey")
    print("   - Create an API key")
    print("   - Add as secret 'GEMINI_API_KEY'")
    print()
    print("4. Get your SPREADSHEET_ID:")
    print("   - Open your Google Sheet")
    print("   - Copy the ID from the URL:")
    print("     https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit")
    print("   - Add as secret 'SPREADSHEET_ID'")
    print()


if __name__ == "__main__":
    main()
