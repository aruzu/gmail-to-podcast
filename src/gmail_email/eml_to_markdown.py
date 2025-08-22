import os
import email
from email import policy
from email.parser import BytesParser

SOURCE_DIR = 's2e2_sources'
OUTPUT_DIR = 's2e2_markdown'

os.makedirs(OUTPUT_DIR, exist_ok=True)

def extract_text_from_email(msg):
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get('Content-Disposition'))
            if content_type == 'text/plain' and 'attachment' not in content_disposition:
                return part.get_payload(decode=True).decode(part.get_content_charset('utf-8'), errors='replace')
        # fallback to first part
        return msg.get_payload(0).get_payload(decode=True).decode('utf-8', errors='replace')
    else:
        return msg.get_payload(decode=True).decode(msg.get_content_charset('utf-8'), errors='replace')

def eml_to_markdown(eml_path, md_path):
    with open(eml_path, 'rb') as f:
        msg = BytesParser(policy=policy.default).parse(f)
    subject = msg['subject'] or ''
    from_ = msg['from'] or ''
    date = msg['date'] or ''
    body = extract_text_from_email(msg)
    
    md_content = f"""# {subject}

**From:** {from_}

**Date:** {date}

---

{body}
"""
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_content)

def convert_all_eml_to_markdown(source_dir, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    for filename in os.listdir(source_dir):
        if filename.lower().endswith('.eml'):
            eml_path = os.path.join(source_dir, filename)
            base_name = os.path.splitext(filename)[0]
            md_path = os.path.join(output_dir, base_name + '.md')
            eml_to_markdown(eml_path, md_path)
            print(f"Converted {filename} -> {base_name}.md")

def main():
    convert_all_eml_to_markdown(SOURCE_DIR, OUTPUT_DIR)

if __name__ == '__main__':
    main() 