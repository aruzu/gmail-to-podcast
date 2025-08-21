import argparse
import os
import base64
import re
from datetime import datetime
# Add parent directory to path for imports
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_loader import get_config

import sys
import os
# Add the src directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from gmail_email.fetch_gmail_by_sender import authenticate_gmail, fetch_message_ids, fetch_message_ids_combined
from gmail_email.filter_subjects_with_llm import fetch_subject, ask_llm
from gmail_email.download_eml_files import download_eml
from gmail_email.eml_to_markdown import convert_all_eml_to_markdown
# Import podcast generation functions
from podcast.generate_podcast_script import read_markdown_files, generate_podcast_script, save_podcast_script
print("Using enhanced podcast script generator")

try:
    from podcast.generate_podcast_audio import parse_podcast_script, create_podcast_audio, combine_audio_segments
    print("Using enhanced multi-speaker podcast audio generator")
    HAS_AUDIO = True
except ImportError as e:
    print(f"Warning: Audio generation not available ({e})")
    HAS_AUDIO = False
try:
    from podcast.generate_podcast_video import create_podcast_video
    HAS_VIDEO = True
    print("Video generation available")
except ImportError:
    HAS_VIDEO = False
    print("Warning: moviepy not installed. Video generation will be skipped.")
from google import genai
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

# Load configuration system for additional presets with label support
config = get_config()

def get_preset_config(preset_name):
    """Get preset configuration from both hardcoded and config sources"""
    # First check config system (supports labels)
    config_preset = config.get_preset_config(preset_name)
    if config_preset:
        return {
            'senders': config_preset.get('senders', []),
            'labels': config_preset.get('labels', []),
            'description': config_preset.get('description', '')
        }
    
    # Fall back to hardcoded presets (senders only)
    if preset_name in SENDER_PRESETS:
        return {
            'senders': SENDER_PRESETS[preset_name],
            'labels': [],
            'description': f"Hardcoded preset: {preset_name}"
        }
    
    return None

def get_all_preset_names():
    """Get all available preset names from both sources"""
    names = set(SENDER_PRESETS.keys())
    names.update(config.get_all_presets())
    return sorted(list(names))

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

def fetch_and_filter_ids(service, senders, labels, after, before, filter_description, temp_dir, skip_llm_filter, llm_filter_on_body):
    # Step 1: Fetch message IDs
    print("Fetching message IDs from Gmail...")
    if senders or labels:
        message_ids = fetch_message_ids_combined(service, senders=senders, labels=labels, after=after, before=before)
    else:
        message_ids = []
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

def download_emls(service, msg_ids, out_dir, mark_processed=False):
    os.makedirs(out_dir, exist_ok=True)
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
            if mark_processed:
                print(" Marking as read and archiving...", end=' ')
                try:
                    # Mark as read by removing UNREAD label and archive by removing INBOX label
                    service.users().messages().modify(
                        userId='me',
                        id=msg_id,
                        body={'removeLabelIds': ['UNREAD', 'INBOX']}
                    ).execute()
                    print("Done.")
                except Exception as e:
                    print(f"Failed: {e}")
            else:
                print()
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
    markdown_grouped = read_markdown_files(md_outdir)
    if not markdown_grouped:
        print("No markdown files found for podcast generation.")
        return False
    
    script = generate_podcast_script(markdown_grouped, duration_minutes)
    save_podcast_script(script, script_path)
    
    # Step 2: Generate audio
    if HAS_AUDIO:
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
    else:
        print("⚠️  Audio generation skipped (dependencies not available)")
        # Create a placeholder audio file
        with open(audio_path.replace('.mp3', '.txt'), 'w') as f:
            f.write("Audio generation not available in this environment")
    
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
    # Build preset list for help text (include both hardcoded and config presets)
    all_preset_names = get_all_preset_names()
    preset_list = []
    for name in all_preset_names:
        preset_config = get_preset_config(name)
        if preset_config:
            sender_count = len(preset_config['senders'])
            label_count = len(preset_config['labels'])
            if sender_count and label_count:
                preset_list.append(f"  {name}: {sender_count} senders, {label_count} labels")
            elif sender_count:
                preset_list.append(f"  {name}: {sender_count} senders")
            elif label_count:
                preset_list.append(f"  {name}: {label_count} labels")
    preset_list_text = "\n".join(preset_list)
    
    parser = argparse.ArgumentParser(description='Run the full Gmail-to-Markdown-to-Podcast pipeline.',
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=f"""Date formats supported: YYYYMMDD, YYYY/MM/DD, YYYY-MM-DD, YYYY.MM.DD
Directory names are auto-generated based on date range if not specified.

Sender presets available:
{preset_list_text}

Examples:
  python run_full_pipeline.py --preset ai-news --after 20250616 --before 20250622
  python run_full_pipeline.py --senders user@example.com --after 2025-06-16
  python run_full_pipeline.py --preset all --outdir weekly_digest --generate_podcast
  python run_full_pipeline.py --preset example_ai_labels --generate_podcast""")
    
    # Sender arguments - either preset or explicit list
    sender_group = parser.add_mutually_exclusive_group(required=True)
    sender_group.add_argument('--preset', choices=all_preset_names, 
                             help='Use a preset group (supports both senders and labels)')
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
    parser.add_argument('--mark-processed', action='store_true', 
                        help='Mark emails as read and archive them after processing')
    
    args = parser.parse_args()
    
    # Get senders and labels from preset or explicit list
    if args.preset:
        preset_config = get_preset_config(args.preset)
        if not preset_config:
            print(f"Preset '{args.preset}' not found.")
            return
        
        senders = preset_config['senders']
        labels = preset_config['labels']
        
        # Print what we're using
        parts = []
        if senders:
            parts.append(f"{len(senders)} senders")
        if labels:
            parts.append(f"{len(labels)} labels")
        print(f"Using preset '{args.preset}' with {', '.join(parts)}")
        
        if not senders and not labels:
            print(f"Preset '{args.preset}' has no senders or labels configured.")
            return
    else:
        senders = args.senders
        labels = []
    
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
    
    # Note: New SDK doesn't need configure call, API key passed directly to client

    if not args.skip_markdown:
        filter_description = args.filter or (input("Enter a human-readable filter for email subjects/bodies: ") if not args.skip_llm_filter else None)
        service = authenticate_gmail()
        # Step 1 & 2: Fetch and filter
        relevant_ids, _ = fetch_and_filter_ids(
            service, senders, labels, after_parsed, before_parsed, filter_description, args.tempdir, args.skip_llm_filter, args.llm_filter_on_body
        )
        # Step 3: Download .eml files
        print(f"Downloading .eml files to {eml_dir}...")
        download_emls(service, relevant_ids, eml_dir, args.mark_processed)
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