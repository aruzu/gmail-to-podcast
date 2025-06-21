import os
import pickle
import base64
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import argparse

# If modifying these SCOPES, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
SENDERS = ['thezvi@substack.com', 'thebatch@deeplearning.ai']
OUTPUT_FILE = 'fetched_message_ids.txt'


def authenticate_gmail():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
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