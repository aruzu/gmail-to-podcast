import os
import pickle
import base64
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import argparse

# If modifying these SCOPES, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
SENDERS = ['thezvi@substack.com', 'thebatch@deeplearning.ai']
OUTPUT_FILE = 'fetched_message_ids.txt'


def authenticate_gmail():
    # Get paths relative to script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, '..', '..'))
    config_dir = os.path.join(project_root, 'config')
    token_path = os.path.join(config_dir, 'token.pickle')
    credentials_path = os.path.join(config_dir, 'credentials.json')
    
    creds = None
    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)
    
    # Check if credentials need refresh
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                # If refresh fails (token revoked/expired), delete token and re-authenticate
                print(f"Token refresh failed: {e}")
                print("Removing expired token and re-authenticating...")
                if os.path.exists(token_path):
                    os.remove(token_path)
                creds = None
        
        # If no valid creds at this point, run the OAuth flow
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for next run
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)
    
    return build('gmail', 'v1', credentials=creds)


def fetch_message_ids(service, senders, after=None, before=None):
    message_ids = []
    for sender in senders:
        query = f"from:{sender}"
        if after:
            query += f" after:{after}"
        if before:
            query += f" before:{before}"
        response = service.users().messages().list(userId='me', q=query, maxResults=500).execute()
        messages = response.get('messages', [])
        print(f"Found {len(messages)} messages from {sender} (query: {query})")
        for msg in messages:
            message_ids.append(msg['id'])
    return message_ids


def main():
    parser = argparse.ArgumentParser(description='Fetch Gmail message IDs by sender and date range.')
    parser.add_argument('--after', type=str, help='Start date (YYYY/MM/DD), inclusive')
    parser.add_argument('--before', type=str, help='End date (YYYY/MM/DD), exclusive')
    args = parser.parse_args()

    service = authenticate_gmail()
    message_ids = fetch_message_ids(service, SENDERS, after=args.after, before=args.before)
    with open(OUTPUT_FILE, 'w') as f:
        for mid in message_ids:
            f.write(mid + '\n')
    print(f"Saved {len(message_ids)} message IDs to {OUTPUT_FILE}")


if __name__ == '__main__':
    main() 