import os
import pickle
import argparse
import base64
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
INPUT_FILE = 'filtered_message_ids.txt'

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

def download_eml(service, msg_id, out_dir):
    try:
        msg = service.users().messages().get(userId='me', id=msg_id, format='raw').execute()
        raw_data = msg['raw']
        eml_bytes = base64.urlsafe_b64decode(raw_data.encode('ASCII'))
        out_path = os.path.join(out_dir, f'{msg_id}.eml')
        with open(out_path, 'wb') as f:
            f.write(eml_bytes)
        return True
    except Exception as e:
        print(f"Failed to download {msg_id}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Download .eml files for filtered Gmail messages.')
    parser.add_argument('--outdir', type=str, default='s2e2_sources/', help='Output directory for .eml files')
    args = parser.parse_args()
    out_dir = args.outdir
    os.makedirs(out_dir, exist_ok=True)

    service = authenticate_gmail()
    with open(INPUT_FILE) as f:
        msg_ids = [line.strip() for line in f if line.strip()]

    for i, msg_id in enumerate(msg_ids, 1):
        out_path = os.path.join(out_dir, f'{msg_id}.eml')
        if os.path.exists(out_path):
            print(f"[{i}/{len(msg_ids)}] {msg_id}.eml already exists, skipping.")
            continue
        print(f"[{i}/{len(msg_ids)}] Downloading {msg_id}.eml ...", end=' ')
        success = download_eml(service, msg_id, out_dir)
        if success:
            print("Done.")
        else:
            print("Failed.")

if __name__ == '__main__':
    main() 