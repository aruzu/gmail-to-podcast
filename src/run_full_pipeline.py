#!/usr/bin/env python3
"""
Gmail to Podcast - Main Pipeline

Orchestrates the complete workflow from Gmail emails to podcast generation.
Uses a flexible configuration system that supports both personal and public use.
"""

import argparse
import os
import sys
import base64
import re
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config_loader import get_config
from email.fetch_gmail_by_sender import authenticate_gmail, fetch_message_ids
from email.filter_subjects_with_llm import fetch_subject, ask_llm
from email.download_eml_files import download_eml
from email.eml_to_markdown import convert_all_eml_to_markdown
from podcast.generate_podcast_script import read_markdown_files, generate_podcast_script, save_podcast_script
from podcast.generate_podcast_audio import parse_podcast_script, create_podcast_audio, combine_audio_segments

try:
    from podcast.generate_podcast_video import create_podcast_video
    HAS_VIDEO = True
except ImportError:
    HAS_VIDEO = False
    print("Warning: moviepy not installed. Video generation will be skipped.")

from openai import OpenAI
from dotenv import load_dotenv
from googleapiclient.errors import HttpError

# Load environment variables
load_dotenv()

# Load configuration
config = get_config()


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


def generate_dir_names(after_date, before_date, mode="fetch"):
    """Generate directory names based on date range and mode"""
    # Get patterns from config
    patterns = {
        'eml': config.get('output.eml_dir_pattern', '{date}_eml'),
        'markdown': config.get('output.markdown_dir_pattern', '{date}_markdown'),
        'podcast': config.get('output.podcast_dir_pattern', '{date}_podcast')
    }
    
    # Create date string
    if after_date and before_date:
        after_clean = after_date.replace("/", "").replace("-", "").replace(".", "").replace(" ", "")
        before_clean = before_date.replace("/", "").replace("-", "").replace(".", "").replace(" ", "")
        date_str = f"{after_clean}_{before_clean}"
    elif after_date:
        after_clean = after_date.replace("/", "").replace("-", "").replace(".", "").replace(" ", "")
        date_str = f"{after_clean}_onwards"
    elif before_date:
        before_clean = before_date.replace("/", "").replace("-", "").replace(".", "").replace(" ", "")
        date_str = f"until_{before_clean}"
    else:
        date_str = datetime.now().strftime("%Y%m%d")
    
    # Generate directory names
    result = {}
    for key, pattern in patterns.items():
        result[key] = pattern.format(
            date=date_str,
            after=after_clean if after_date else "",
            before=before_clean if before_date else "",
            mode=mode
        )
    
    return result


def fetch_body(service, msg_id):
    """Fetch email body for LLM filtering"""
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
                        decoded = base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
                        return decoded
        
        # Fallback: try the main body
        body_data = payload.get('body', {}).get('data')
        if body_data:
            decoded = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='replace')
            return decoded
        
        return ''
    except HttpError as e:
        print(f"Failed to fetch body for {msg_id}: {e}")
        return ''


def fetch_and_filter_ids(service, senders, after, before, filter_description, openai_client, temp_dir, skip_llm_filter, llm_filter_on_body):
    """Fetch and optionally filter message IDs"""
    # Step 1: Fetch message IDs
    print("Fetching message IDs from Gmail...")
    message_ids = fetch_message_ids(service, senders, after=after, before=before)
    print(f"Fetched {len(message_ids)} message IDs.")
    
    if skip_llm_filter:
        print("Skipping LLM filtering. All fetched message IDs will be used.")
        relevant_ids = message_ids
    else:
        # Step 2: Filter with LLM
        print("Filtering subjects with LLM...")
        print(f"Filter: {filter_description}")
        
        relevant_ids = []
        temp_file = os.path.join(temp_dir, "pipeline_fetched_message_ids.txt")
        
        # Save fetched IDs to temp file
        with open(temp_file, 'w') as f:
            for mid in message_ids:
                f.write(mid + '\n')
        
        # Process each message
        for i, msg_id in enumerate(message_ids, 1):
            print(f"[{i}/{len(message_ids)}] ", end='')
            subject = fetch_subject(service, msg_id)
            
            content_for_llm = f"Subject: {subject}"
            if llm_filter_on_body:
                body = fetch_body(service, msg_id)
                # Take first 20 lines of body
                body_lines = body.split('\n')[:20]
                body_preview = '\n'.join(body_lines)
                content_for_llm = f"Subject: {subject}\n\nBody preview:\n{body_preview}"
            
            keep = ask_llm(content_for_llm, filter_description, openai_client)
            
            if keep:
                relevant_ids.append(msg_id)
                print(f"✓ Keeping: {subject}")
            else:
                print(f"✗ Skipping: {subject}")
        
        print(f"\nFiltered down to {len(relevant_ids)} relevant emails.")
    
    # Save filtered IDs
    filtered_file = os.path.join(temp_dir, "pipeline_filtered_message_ids.txt")
    with open(filtered_file, 'w') as f:
        for mid in relevant_ids:
            f.write(mid + '\n')
    
    return relevant_ids, filtered_file


def download_emls(service, message_ids, output_dir):
    """Download email messages as .eml files"""
    os.makedirs(output_dir, exist_ok=True)
    
    for i, msg_id in enumerate(message_ids, 1):
        eml_path = os.path.join(output_dir, f"{msg_id}.eml")
        
        if os.path.exists(eml_path):
            print(f"[{i}/{len(message_ids)}] Skipping {msg_id}.eml (already exists)")
            continue
        
        print(f"[{i}/{len(message_ids)}] Downloading {msg_id}.eml ... ", end='', flush=True)
        
        if download_eml(service, msg_id, eml_path):
            print("Done.")
        else:
            print("Failed.")


def generate_podcast_from_markdown(markdown_dir, openai_client, output_dir, duration):
    """Generate podcast from markdown files"""
    os.makedirs(output_dir, exist_ok=True)
    
    # File paths
    script_path = os.path.join(output_dir, "podcast_script.txt")
    audio_path = os.path.join(output_dir, "podcast.mp3")
    video_path = os.path.join(output_dir, "podcast_video.mp4")
    
    # Step 1: Generate script
    print("Reading markdown files...")
    content = read_markdown_files(markdown_dir)
    
    if not content:
        print("No content found in markdown files.")
        return False
    
    print(f"Generating {duration}-minute podcast script...")
    script = generate_podcast_script(content, duration, openai_client)
    
    if not script:
        print("Failed to generate podcast script.")
        return False
    
    save_podcast_script(script, script_path)
    print(f"Script saved to: {script_path}")
    
    # Step 2: Generate audio
    print("Generating podcast audio...")
    try:
        segments = parse_podcast_script(script_path)
        audio_segments = create_podcast_audio(segments, output_dir)
        
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
    
    # Step 3: Generate video (if available)
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
    presets = config.get_all_presets()
    preset_descriptions = []
    for name in presets:
        preset_data = config.senders.get(name, {})
        if isinstance(preset_data, dict) and 'senders' in preset_data:
            count = len(preset_data['senders'])
            desc = preset_data.get('description', f'{name} senders')
            preset_descriptions.append(f"  {name}: {count} senders - {desc}")
    
    preset_list = "\n".join(preset_descriptions)
    
    parser = argparse.ArgumentParser(
        description='Run the full Gmail-to-Markdown-to-Podcast pipeline.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""Date formats supported: YYYYMMDD, YYYY/MM/DD, YYYY-MM-DD, YYYY.MM.DD
Directory names are auto-generated based on date range if not specified.

Available sender presets:
{preset_list}

Examples:
  python run_full_pipeline.py --preset ai-news --after 20250616 --before 20250622
  python run_full_pipeline.py --senders user@example.com --after 2025-06-16
  python run_full_pipeline.py --preset all --outdir weekly_digest --generate_podcast"""
    )
    
    # Sender arguments - either preset or explicit list
    sender_group = parser.add_mutually_exclusive_group(required=True)
    sender_group.add_argument('--preset', choices=presets, 
                             help='Use a preset group of senders')
    sender_group.add_argument('--senders', nargs='+', 
                             help='List of sender email addresses (space-separated)')
    
    # Date arguments with flexible parsing
    parser.add_argument('--after', type=str, help='Start date (flexible format, e.g., 20250616 or 2025/06/16)')
    parser.add_argument('--before', type=str, help='End date (flexible format)')
    parser.add_argument('--days-back', type=int, help='Alternative to dates: fetch emails from N days ago')
    
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
    parser.add_argument('--podcast_duration', type=int, help='Podcast duration in minutes')
    parser.add_argument('--podcast_outdir', type=str, help='Directory for podcast files (auto-generated if not specified)')
    parser.add_argument('--skip_markdown', action='store_true', help='Skip email processing, generate podcast from existing markdown')
    
    # Other options
    parser.add_argument('--tempdir', type=str, help='Directory for temp files')
    parser.add_argument('--config', type=str, help='Path to config directory')
    
    args = parser.parse_args()
    
    # Reload config if custom path specified
    if args.config:
        global config
        config = get_config(args.config)
    
    # Get senders list from preset or explicit list
    if args.preset:
        senders = config.get_sender_preset(args.preset)
        if not senders:
            print(f"Error: Preset '{args.preset}' not found or has no senders")
            return
        print(f"Using preset '{args.preset}' with {len(senders)} senders")
    else:
        senders = args.senders
    
    # Handle date arguments
    if args.days_back:
        # Calculate dates from days back
        end_date = datetime.now()
        start_date = end_date - timedelta(days=args.days_back)
        after_parsed = start_date.strftime("%Y/%m/%d")
        before_parsed = end_date.strftime("%Y/%m/%d")
    else:
        # Parse provided dates
        after_parsed = parse_date(args.after) if args.after else None
        before_parsed = parse_date(args.before) if args.before else None
    
    # Get default values from config
    temp_dir = args.tempdir or config.get('output.temp_dir', '.')
    podcast_duration = args.podcast_duration or config.get('podcast.default_duration', 30)
    
    # Generate default directory names if not provided
    base_output_dir = config.get('output.base_dir', 'output')
    
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
        
        # Prepend base output directory
        eml_dir = args.eml_outdir or os.path.join(base_output_dir, default_dirs['eml'])
        md_dir = args.md_outdir or os.path.join(base_output_dir, default_dirs['markdown'])
        podcast_dir = args.podcast_outdir or os.path.join(base_output_dir, default_dirs['podcast'])
    
    # Check API keys
    openai_api_key = os.getenv('OPENAI_API_KEY')
    gemini_api_key = os.getenv('GEMINI_API_KEY')
    
    if not args.skip_llm_filter and not openai_api_key:
        print("Please set the OPENAI_API_KEY environment variable.")
        return
    
    if args.generate_podcast and not openai_api_key:
        print("Please set the OPENAI_API_KEY environment variable for podcast script generation.")
        return
    
    if args.generate_podcast and not gemini_api_key:
        print("Please set the GEMINI_API_KEY environment variable for Gemini TTS audio generation.")
        return
    
    openai_client = OpenAI(api_key=openai_api_key) if openai_api_key else None
    
    # Main pipeline execution
    if not args.skip_markdown:
        # Get filter description
        if args.skip_llm_filter:
            filter_description = None
        else:
            filter_description = args.filter or config.get('filtering.default_filter')
            if not filter_description:
                filter_description = input("Enter a human-readable filter for email subjects/bodies: ")
        
        # Authenticate Gmail
        credentials_path = config.get('gmail.credentials_path', 'credentials.json')
        if not os.path.exists(credentials_path):
            print(f"Error: Gmail credentials not found at {credentials_path}")
            print("Please follow the setup instructions to configure Gmail API access.")
            return
        
        service = authenticate_gmail()
        
        # Step 1 & 2: Fetch and filter
        relevant_ids, _ = fetch_and_filter_ids(
            service, senders, after_parsed, before_parsed, filter_description, 
            openai_client, temp_dir, args.skip_llm_filter, args.llm_filter_on_body
        )
        
        if not relevant_ids:
            print("No emails found matching the criteria.")
            return
        
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
        success = generate_podcast_from_markdown(md_dir, openai_client, podcast_dir, podcast_duration)
        if success:
            print("Full pipeline complete!")
        else:
            print("Pipeline completed with errors in podcast generation.")
    else:
        print(f"Pipeline complete! Markdown files saved to: {md_dir}")
        print("Use --generate_podcast to create a podcast from the markdown files.")


if __name__ == '__main__':
    main()