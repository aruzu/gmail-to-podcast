from dotenv import load_dotenv
load_dotenv()

import os
import pickle
import google.generativeai as genai
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
INPUT_FILE = 'fetched_message_ids.txt'
OUTPUT_FILE = 'filtered_message_ids.txt'


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


def fetch_subject(service, msg_id):
    msg = service.users().messages().get(userId='me', id=msg_id, format='metadata', metadataHeaders=['Subject']).execute()
    headers = msg.get('payload', {}).get('headers', [])
    for h in headers:
        if h['name'].lower() == 'subject':
            return h['value']
    return ''


def ask_llm(email, filter_description):
    prompt = f"""
You are an assistant that helps filter emails. The filter is: {filter_description}

Email: {email}

Should this email be kept? Answer YES or NO and explain briefly why.
"""
    print(prompt)
    
    model = genai.GenerativeModel('gemini-2.5-flash')
    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            max_output_tokens=50,
            temperature=0
        )
    )
    answer = response.text
    return 'YES' in answer.upper()


def main():
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("Please set the GEMINI_API_KEY environment variable.")
        return
    genai.configure(api_key=api_key)

    filter_description = input("Enter a human-readable filter for email subjects: ")
    service = authenticate_gmail()

    with open(INPUT_FILE) as f:
        msg_ids = [line.strip() for line in f if line.strip()]

    relevant_ids = []
    for msg_id in msg_ids:
        subject = fetch_subject(service, msg_id)
        if not subject:
            continue
        keep = ask_llm(subject, filter_description)
        print(f"Subject: {subject}\nKeep: {keep}\n---")
        if keep:
            relevant_ids.append(msg_id)

    with open(OUTPUT_FILE, 'w') as f:
        for mid in relevant_ids:
            f.write(mid + '\n')
    print(f"Saved {len(relevant_ids)} relevant message IDs to {OUTPUT_FILE}")


if __name__ == '__main__':
    main() 