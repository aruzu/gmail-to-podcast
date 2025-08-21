import os
import pickle
import argparse
import base64
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
INPUT_FILE = 'filtered_message_ids.txt'

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

def mark_as_read_and_archive(service, msg_id):
    """Mark email as read and archive it (remove from INBOX)."""
    try:
        # Mark as read by removing UNREAD label
        service.users().messages().modify(
            userId='me',
            id=msg_id,
            body={'removeLabelIds': ['UNREAD']}
        ).execute()
        
        # Archive by removing INBOX label
        service.users().messages().modify(
            userId='me',
            id=msg_id,
            body={'removeLabelIds': ['INBOX']}
        ).execute()
        
        return True
    except Exception as e:
        print(f"Failed to mark as read/archive {msg_id}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Download .eml files for filtered Gmail messages.')
    parser.add_argument('--outdir', type=str, default='s2e2_sources/', help='Output directory for .eml files')
    parser.add_argument('--mark-processed', action='store_true', 
                        help='Mark emails as read and archive them after downloading')
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
            print("Done.", end='')
            
            # Mark as read and archive if requested
            if args.mark_processed:
                print(" Marking as read and archiving...", end=' ')
                if mark_as_read_and_archive(service, msg_id):
                    print("Done.")
                else:
                    print("Failed.")
            else:
                print()
        else:
            print("Failed.")

if __name__ == '__main__':
    main() 