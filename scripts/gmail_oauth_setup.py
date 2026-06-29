"""One-time helper to mint a Gmail read-only refresh token for email_sync.py.

Steps:
  1. In Google Cloud Console, create (or reuse) a project and enable the Gmail API.
  2. Configure an OAuth consent screen (External is fine; add your own Gmail as a
     test user) and create an OAuth client ID of type "Desktop app".
  3. Download its credentials JSON and pass the path to this script:

         pip install google-auth-oauthlib
         python scripts/gmail_oauth_setup.py path/to/credentials.json

  4. A browser opens; sign in with the inbox you want read and approve the
     read-only scope. The script prints GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET /
     GMAIL_REFRESH_TOKEN. Put those in .env locally and in the repo's GitHub
     Actions secrets so the scheduled run can read the inbox.

The token only grants gmail.readonly — email_sync never sends or deletes mail.
"""

import json
import sys

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/gmail_oauth_setup.py path/to/credentials.json")
        sys.exit(2)

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("Install the helper dependency first: pip install google-auth-oauthlib")
        sys.exit(1)

    creds_path = sys.argv[1]
    flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")

    with open(creds_path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    installed = raw.get("installed") or raw.get("web") or {}

    print("\nAdd these to .env (local) and GitHub Actions secrets:\n")
    print(f"GMAIL_CLIENT_ID={installed.get('client_id', '')}")
    print(f"GMAIL_CLIENT_SECRET={installed.get('client_secret', '')}")
    print(f"GMAIL_REFRESH_TOKEN={creds.refresh_token}")


if __name__ == "__main__":
    main()
