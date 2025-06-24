import argparse
import os
import base64
import re
from datetime import datetime
# Add parent directory to path for imports
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.email.fetch_gmail_by_sender import authenticate_gmail, fetch_message_ids
from scripts.email.filter_subjects_with_llm import fetch_subject, ask_llm
from scripts.email.download_eml_files import download_eml
from scripts.email.eml_to_markdown import convert_all_eml_to_markdown
# Try to import v2 versions first for better NotebookLM-style output
try:
    from scripts.podcast.generate_podcast_script_v2 import read_markdown_files, generate_podcast_script, save_podcast_script
    print("Using improved podcast script generator (v2)")
except ImportError:
    try:
        from scripts.podcast.generate_podcast_script import read_markdown_files, generate_podcast_script, save_podcast_script
        print("Using standard podcast script generator")
    except ImportError:
        from generate_podcast_script import read_markdown_files, generate_podcast_script, save_podcast_script
        print("Using standard podcast script generator (legacy path)")

try:
    from scripts.podcast.generate_podcast_audio_v3 import parse_podcast_script, create_podcast_audio, combine_audio_segments
    print("Using advanced podcast audio generator (v3)")
except ImportError:
    try:
        from scripts.podcast.generate_podcast_audio_v2 import parse_podcast_script, create_podcast_audio, combine_audio_segments
        print("Using improved podcast audio generator (v2)")
    except ImportError:
        try:
            from scripts.podcast.generate_podcast_audio import parse_podcast_script, create_podcast_audio, combine_audio_segments
            print("Using standard podcast audio generator")
        except ImportError:
            from generate_podcast_audio import parse_podcast_script, create_podcast_audio, combine_audio_segments
            print("Using standard podcast audio generator (legacy path)")
from google import genai
try:
    from scripts.podcast.generate_podcast_video import create_podcast_video
    HAS_VIDEO = True
except ImportError:
    try:
        from generate_podcast_video import create_podcast_video
        HAS_VIDEO = True
    except ImportError:
        HAS_VIDEO = False
        print("Warning: moviepy not installed. Video generation will be skipped.")
import google.generativeai as genai
from dotenv import load_dotenv
from googleapiclient.errors import HttpError
load_dotenv()

# Preset sender groups for convenience
SENDER_PRESETS = {
    'ai-news': [
        'thezvi@substack.com',
        'turingpost@mail.beehiiv.com',
        'datapoints@deeplearning.ai',
        'newsletter@aisecret.us',
        'news@daily.therundown.ai',
        'bensbites@substack.com',
        'ai-agents-weekly@mail.beehiiv.com',
        'oneusefulthing@substack.com',
        'importai@substack.com',
    ],
    'tech-newsletters': [
        'email@stratechery.com',
        'scottbelsky@substack.com',
        'will@lethain.com',
        'list@ben-evans.com',
        'inferencebysequoia+this-week-in-inference@substack.com',
        'sundaylettersfromsam@substack.com',
    ],
    'productivity': [
        'superhuman@mail.joinsuperhuman.ai',
        'lenny@substack.com',
        'bj@bjfogg.com',
        'sundaylettersfromsam@substack.com',
    ],
    'news': [
        'info@theinformation.com',
    ],
    'all': []  # Will be populated with all unique senders
}

# Populate 'all' preset with unique senders
all_senders = set()
for preset_senders in SENDER_PRESETS.values():
    if preset_senders:  # Skip the empty 'all' list
        all_senders.update(preset_senders)
SENDER_PRESETS['all'] = sorted(list(all_senders))

def parse_date(date_str):
    """Parse date from various formats to YYYY/MM/DD format required by Gmail API"""
    if not date_str:
        return None
    
    # Remove any extra whitespace
    date_str = date_str.strip()
    
    # Try different date formats
    formats = [
        "%Y%m%d",      # YYYYMMDD
        "%Y/%m/%d",    # YYYY/MM/DD
        "%Y-%m-%d",    # YYYY-MM-DD
        "%Y.%m.%d",    # YYYY.MM.DD
        "%Y %m %d",    # YYYY MM DD
    ]
    
    for fmt in formats:
        try:
            date_obj = datetime.strptime(date_str, fmt)
            # Return in Gmail API format
            return date_obj.strftime("%Y/%m/%d")
        except ValueError:
            continue
    
    # If no format matched, return as-is and let Gmail API handle it
    print(f"Warning: Could not parse date '{date_str}', using as-is")
    return date_str

def generate_dir_names(after_date, before_date):
    """Generate default directory names based on date range"""
    # Parse dates to get clean format
    after_clean = after_date.replace("/", "").replace("-", "").replace(".", "").replace(" ", "") if after_date else ""
    before_clean = before_date.replace("/", "").replace("-", "").replace(".", "").replace(" ", "") if before_date else ""
    
    if after_clean and before_clean:
        dir_suffix = f"{after_clean}_{before_clean}"
    elif after_clean:
        dir_suffix = f"{after_clean}_onwards"
    elif before_clean:
        dir_suffix = f"until_{before_clean}"
    else:
        # Use current date if no dates provided
        dir_suffix = datetime.now().strftime("%Y%m%d")
    
    return {
        'eml': f"{dir_suffix}_eml",
        'markdown': f"{dir_suffix}_markdown"
    }

def fetch_body(service, msg_id):
    try:
        msg = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
        payload = msg.get('payload', {})
        parts = payload.get('parts', [])
        # Try to find the text/plain part
        if parts:
            for part in parts:
                if part.get('mimeType') == 'text/plain':
                    data = part.get('body', {}).get('data')
                    if data:
                        import base64
                        decoded = base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
                        return decoded
        # Fallback: try the main body
        body_data = payload.get('body', {}).get('data')
        if body_data:
            import base64
            decoded = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='replace')
            return decoded
        return ''
    except HttpError as e:
        print(f"Failed to fetch body for {msg_id}: {e}")
        return ''

def fetch_and_filter_ids(service, senders, after, before, filter_description, temp_dir, skip_llm_filter, llm_filter_on_body):
    # Step 1: Fetch message IDs
    print("Fetching message IDs from Gmail...")
    message_ids = fetch_message_ids(service, senders, after=after, before=before)
    print(f"Fetched {len(message_ids)} message IDs.")
    if skip_llm_filter:
        print("Skipping LLM filtering. All fetched message IDs will be used.")
        relevant_ids = message_ids
    else:
        # Step 2: Filter with LLM
        if llm_filter_on_body:
            print("LLM filtering on subject and first 20 lines of body...")
        else:
            print("LLM filtering on subject only...")
        relevant_ids = []
        for i, msg_id in enumerate(message_ids, 1):
            subject = fetch_subject(service, msg_id)
            if not subject:
                continue
            body_lines = ''
            if llm_filter_on_body:
                body = fetch_body(service, msg_id)
                body_lines = '\n'.join(body.splitlines()[:20])
            prompt = None
            if llm_filter_on_body:
                prompt = f"Subject: {subject}\n\nFirst 20 lines of email body:\n{body_lines}"
            else:
                prompt = subject
            keep = ask_llm(prompt, filter_description)
            print(f"[{i}/{len(message_ids)}] Subject: {subject}\nKeep: {keep}\n---")
            if keep:
                relevant_ids.append(msg_id)
        print(f"Filtered down to {len(relevant_ids)} relevant message IDs.")
    # Save to temp file for next step
    temp_path = os.path.join(temp_dir, 'pipeline_filtered_message_ids.txt')
    with open(temp_path, 'w') as f:
        for mid in relevant_ids:
            f.write(mid + '\n')
    return relevant_ids, temp_path

def download_emls(service, msg_ids, out_dir):
    os.makedirs(out_dir, exist_ok=True)
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

def generate_podcast_from_markdown(md_outdir, output_dir="podcast_output", duration_minutes=30):
    """Generate podcast script, audio, and video from markdown files"""
    os.makedirs(output_dir, exist_ok=True)
    
    script_path = os.path.join(output_dir, "podcast_script.txt")
    audio_path = os.path.join(output_dir, "podcast.mp3")
    video_path = os.path.join(output_dir, "podcast_video.mp4")
    
    # Step 1: Generate podcast script
    print(f"Generating {duration_minutes}-minute podcast script...")
    markdown_content = read_markdown_files(md_outdir)
    if not markdown_content:
        print("No markdown files found for podcast generation.")
        return False
    
    script = generate_podcast_script(markdown_content, duration_minutes)
    save_podcast_script(script, script_path)
    
    # Step 2: Generate audio
    print("Generating podcast audio...")
    try:
        segments = parse_podcast_script(script_path)
        audio_segments = create_podcast_audio(segments, os.path.join(output_dir, "audio_segments"))
        
        if audio_segments:
            success = combine_audio_segments(audio_segments, audio_path)
            if not success:
                print("Failed to generate podcast audio.")
                return False
        else:
            print("No audio segments generated.")
            return False
    except Exception as e:
        print(f"Error generating podcast audio: {e}")
        return False
    
    # Step 3: Generate video
    if HAS_VIDEO:
        print("Generating podcast video...")
        try:
            success = create_podcast_video(audio_path, script_path, video_path)
            if success:
                print(f"Podcast generation complete! Files saved in: {output_dir}")
                print(f"- Script: {script_path}")
                print(f"- Audio: {audio_path}")
                print(f"- Video: {video_path}")
                return True
            else:
                print("Failed to generate podcast video.")
                return False
        except Exception as e:
            print(f"Error generating podcast video: {e}")
            print(f"Podcast audio generation complete! Files saved in: {output_dir}")
            print(f"- Script: {script_path}")
            print(f"- Audio: {audio_path}")
            return True
    else:
        print(f"Podcast generation complete! Files saved in: {output_dir}")
        print(f"- Script: {script_path}")
        print(f"- Audio: {audio_path}")
        return True

def main():
    # Build preset list for help text
    preset_list = "\n".join([f"  {name}: {len(senders)} senders" for name, senders in SENDER_PRESETS.items()])
    
    parser = argparse.ArgumentParser(description='Run the full Gmail-to-Markdown-to-Podcast pipeline.',
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=f"""Date formats supported: YYYYMMDD, YYYY/MM/DD, YYYY-MM-DD, YYYY.MM.DD
Directory names are auto-generated based on date range if not specified.

Sender presets available:
{preset_list}

Examples:
  python run_full_pipeline.py --preset ai-news --after 20250616 --before 20250622
  python run_full_pipeline.py --senders user@example.com --after 2025-06-16
  python run_full_pipeline.py --preset all --outdir weekly_digest --generate_podcast""")
    
    # Sender arguments - either preset or explicit list
    sender_group = parser.add_mutually_exclusive_group(required=True)
    sender_group.add_argument('--preset', choices=list(SENDER_PRESETS.keys()), 
                             help='Use a preset group of senders')
    sender_group.add_argument('--senders', nargs='+', 
                             help='List of sender email addresses (space-separated)')
    
    # Date arguments with flexible parsing
    parser.add_argument('--after', type=str, help='Start date (flexible format, e.g., 20250616 or 2025/06/16)')
    parser.add_argument('--before', type=str, help='End date (flexible format)')
    
    # Optional directory arguments - will be auto-generated if not provided
    parser.add_argument('--outdir', type=str, help='Base output directory (subdirs will be created for eml and markdown)')
    parser.add_argument('--eml_outdir', type=str, help='Directory for .eml files (auto-generated if not specified)')
    parser.add_argument('--md_outdir', type=str, help='Directory for .md files (auto-generated if not specified)')
    
    # Filtering options
    parser.add_argument('--filter', type=str, help='Human-readable filter for email subjects/bodies')
    parser.add_argument('--skip_llm_filter', action='store_true', help='Skip LLM filtering, download all fetched emails')
    parser.add_argument('--llm_filter_on_body', action='store_true', help='Include email body in LLM filtering')
    
    # Podcast options
    parser.add_argument('--generate_podcast', action='store_true', help='Generate podcast from markdown files')
    parser.add_argument('--podcast_duration', type=int, default=30, help='Podcast duration in minutes (default: 30)')
    parser.add_argument('--podcast_outdir', type=str, help='Directory for podcast files (auto-generated if not specified)')
    parser.add_argument('--skip_markdown', action='store_true', help='Skip email processing, generate podcast from existing markdown')
    
    # Other options
    parser.add_argument('--tempdir', type=str, default='.', help='Directory for temp files (default: current dir)')
    
    args = parser.parse_args()
    
    # Get senders list from preset or explicit list
    if args.preset:
        senders = SENDER_PRESETS[args.preset]
        print(f"Using preset '{args.preset}' with {len(senders)} senders")
    else:
        senders = args.senders
    
    # Parse dates to Gmail API format
    after_parsed = parse_date(args.after) if args.after else None
    before_parsed = parse_date(args.before) if args.before else None
    
    # Generate default directory names if not provided
    if args.outdir:
        # If base output directory is specified, use it for all subdirectories
        base_dir = args.outdir
        os.makedirs(base_dir, exist_ok=True)
        eml_dir = args.eml_outdir or os.path.join(base_dir, 'eml')
        md_dir = args.md_outdir or os.path.join(base_dir, 'markdown')
        podcast_dir = args.podcast_outdir or os.path.join(base_dir, 'podcast')
    else:
        # Generate directory names based on date range
        default_dirs = generate_dir_names(after_parsed, before_parsed)
        eml_dir = args.eml_outdir or default_dirs['eml']
        md_dir = args.md_outdir or default_dirs['markdown']
        # For podcast, use the markdown directory name as base
        podcast_base = md_dir.replace('_markdown', '_podcast')
        podcast_dir = args.podcast_outdir or podcast_base

    gemini_api_key = os.getenv('GEMINI_API_KEY')
    
    if not args.skip_llm_filter and not gemini_api_key:
        print("Please set the GEMINI_API_KEY environment variable.")
        return
    if args.generate_podcast and not gemini_api_key:
        print("Please set the GEMINI_API_KEY environment variable for script and audio generation.")
        return
    
    if gemini_api_key:
        genai.configure(api_key=gemini_api_key)

    if not args.skip_markdown:
        filter_description = args.filter or (input("Enter a human-readable filter for email subjects/bodies: ") if not args.skip_llm_filter else None)
        service = authenticate_gmail()
        # Step 1 & 2: Fetch and filter
        relevant_ids, _ = fetch_and_filter_ids(
            service, senders, after_parsed, before_parsed, filter_description, args.tempdir, args.skip_llm_filter, args.llm_filter_on_body
        )
        # Step 3: Download .eml files
        print(f"Downloading .eml files to {eml_dir}...")
        download_emls(service, relevant_ids, eml_dir)
        # Step 4: Convert to Markdown
        print(f"Converting .eml files to Markdown in {md_dir}...")
        convert_all_eml_to_markdown(eml_dir, md_dir)
        print("Markdown conversion complete!")
    
    # Step 5: Generate podcast (if requested)
    if args.generate_podcast:
        print("Starting podcast generation...")
        success = generate_podcast_from_markdown(md_dir, podcast_dir, args.podcast_duration)
        if success:
            print("Full pipeline complete!")
        else:
            print("Pipeline completed with errors in podcast generation.")
    else:
        print(f"Pipeline complete! Markdown files saved to: {md_dir}")
        print("Use --generate_podcast to create a podcast from the markdown files.")

if __name__ == '__main__':
    main() 