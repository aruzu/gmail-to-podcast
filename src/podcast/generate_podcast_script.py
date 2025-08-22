import os
import glob
from google import genai
from google.genai import types
from dotenv import load_dotenv
import re
from datetime import datetime
import collections

load_dotenv()

def parse_date_from_markdown(content):
    match = re.search(r'\*\*Date:\*\* (.+)', content)
    if match:
        date_str = match.group(1).strip()
        # Try common date formats
        formats = [
            "%a, %d %b %Y %H:%M:%S",  # e.g., Tue, 18 Jun 2024 10:00:00
            "%Y-%m-%d",
            "%d %b %Y",
            "%Y/%m/%d",
            "%Y.%m.%d",
            "%Y %m %d",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
    return None

def trim_markdown_content(content):
    """Trim markdown content: remove signatures, unsubscribe lines, and quoted replies, but keep all other content."""
    lines = content.splitlines()
    trimmed = []
    signature_patterns = [
        r'^-- ?$', r'^Best,', r'^Regards,', r'^Sent from my', r'^On .+ wrote:', r'^From: ',
        r'^This email.*unsubscribe', r'^To unsubscribe', r'^View this email in your browser', r'^You are receiving this',
        r'^If you no longer wish to receive', r'^Click here to unsubscribe', r'^Privacy Policy', r'^All rights reserved',
    ]
    in_signature = False
    for line in lines:
        # Stop at signature or unsubscribe lines
        if any(re.match(pat, line.strip(), re.IGNORECASE) for pat in signature_patterns):
            in_signature = True
        if in_signature:
            continue
        # Skip quoted replies (lines starting with '>')
        if line.strip().startswith('>'):
            continue
        trimmed.append(line)
    return '\n'.join(trimmed)

def extract_sender_from_markdown(content):
    for line in content.splitlines():
        if line.startswith('**From:**'):
            return line.split('**From:**')[1].split('<')[0].strip()
    return 'Unknown Source'

def read_markdown_files(markdown_dir):
    """Read all markdown files, trim, parse date, extract sender, and return grouped/sorted content by sender."""
    markdown_files = glob.glob(os.path.join(markdown_dir, "*.md"))
    grouped = collections.defaultdict(list)
    for file_path in markdown_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            trimmed_content = trim_markdown_content(content)
            date = parse_date_from_markdown(content)
            sender = extract_sender_from_markdown(content)
            grouped[sender].append({
                'filename': os.path.basename(file_path),
                'content': trimmed_content,
                'date': date or datetime.min
            })
    # Sort news inside each sender group by date (oldest first)
    for sender in grouped:
        grouped[sender].sort(key=lambda x: x['date'])
    return grouped

def generate_podcast_script(markdown_grouped, duration_minutes=30):
    """Generate a podcast script from grouped markdown content using Gemini."""
    # Combine all content, grouped by sender
    combined_content = ""
    for sender, articles in markdown_grouped.items():
        combined_content += f"\n\n=== News from {sender} ===\n\n"
        for piece in articles:
            combined_content += f"Article: {piece['filename']}\n{piece['content']}\n\n"
    # Truncate if too long (keeping within token limits)
    if len(combined_content) > 150000:
        combined_content = combined_content[:150000] + "\n\n[Content truncated...]"
    
    # Calculate approximate word count target based on duration
    # Average speaking rate is about 140-160 words per minute for conversational content
    target_words = duration_minutes * 150  # Using 150 WPM as middle ground
    
    # Adjust max_tokens based on duration (rough estimate: 1 token ≈ 0.75 words)
    max_tokens = min(8000, int(target_words * 1.5)) # Cap at 8000 tokens for API limits

    example_opening = "[Speaker 0] Welcome to Briefly.AI News Roundup. I'm Sarah.\n[Speaker 1] And I'm Michael. Today we're looking at some really fascinating material.\n[Speaker 0] Right, so let's jump in..."

    prompt = f"""
Generate the entire podcast script in English.
You are a podcast script writer creating a {duration_minutes}-minute conversational podcast called 'Briefly.AI News Roundup' in the style of NotebookLM's Audio Overview.

IMPORTANT: The script MUST begin with:
{example_opening}

CRITICAL RULES:
1. Hosts should introduce themselves ONLY at the very beginning (e.g., 'I'm Sarah' and 'I'm Michael')
2. After introductions, NEVER have hosts say their own names again during the conversation
3. Use natural conversation flow with quick back-and-forth exchanges
4. Include natural interruptions, overlapping dialogue, and reactions
5. Keep responses short and punchy - most exchanges should be 1-3 sentences
6. Use conversational fillers and reactions like 'mm-hmm', 'yeah', 'right', 'exactly', 'oh', 'ah'
7. NO explicit pause markers - let conversation flow naturally
8. Include emotional variety - surprise ('Wow!'), curiosity ('Hmm, that's interesting...'), agreement ('Absolutely!'), thoughtfulness ('You know, that makes me think...')
9. Use natural speech patterns including occasional 'uh', 'um', trailing off with '...', and incomplete thoughts

The two hosts:
- Speaker 0 (female): More analytical, asks probing questions, provides context
- Speaker 1 (male): More enthusiastic, makes connections, adds energy

CONTENT COVERAGE INSTRUCTIONS:
- Cover all the news items below. If there are too many, summarize the less important ones briefly, but make sure the most important news is discussed in detail.
- Prioritize covering the content over strictly matching a target duration.
- The script length should be driven by the amount of news content provided. Use the suggested duration as a guideline for pacing and style, not as a hard limit.
- You MUST group all news items by sender/source.
- For each sender/source group, you MUST start with a clear spoken transition mentioning the sender/source (e.g., 'Now, let's look at news from {{SENDER}}')
- For each sender/source, you MUST discuss at least one news item from that sender, even if only as a brief summary.
- Do NOT skip any sender/source, even if their content is short. Every group must be introduced and discussed, even if briefly.
- Do NOT blend or mix news from different senders in the same segment. Each sender/source must have its own group and transition.

Format the script EXACTLY like this:
[Speaker 0] Text here
[Speaker 1] Text here

Example opening:
{example_opening}

IMPORTANT: Make the conversation feel REAL - with genuine reactions, natural interruptions, incomplete thoughts, and authentic engagement. The hosts should sound like they're discovering insights together, not reading a script.

Content to discuss:
{combined_content}

Create an engaging {duration_minutes}-minute podcast script (approximately {target_words} words) that covers the most interesting and important points from this content. Focus on making it sound like a genuine, dynamic conversation between two intelligent people who are genuinely excited about the topic.
"""
    api_key = os.getenv('GEMINI_API_KEY')
    client = genai.Client(api_key=api_key)
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        # Check if response was blocked
        if hasattr(response, "candidates") and response.candidates and getattr(response.candidates[0], "finish_reason", None) == 2:
            print("⚠️  Content was blocked by safety filters. Trying with adjusted prompt...")
            safer_prompt = f"""
Create a {duration_minutes}-minute conversational podcast script between two hosts discussing technology news and insights.

Format:
[Speaker 0] (female host Sarah)
[Speaker 1] (male host Michael)

The hosts should introduce themselves at the beginning, then have a natural conversation about the key points from the articles provided. Keep it informative but engaging.

Content summary to discuss:
{combined_content[:10000]}

Generate approximately {target_words} words.
"""
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=safer_prompt
            )
        # Extract text from response
        if hasattr(response, "text") and response.text:
            return response.text
        # Fallback: try to extract from candidates
        if hasattr(response, "candidates") and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, "content") and candidate.content and hasattr(candidate.content, "parts") and candidate.content.parts:
                part = candidate.content.parts[0]
                if hasattr(part, "text") and part.text:
                    return part.text
        print("No valid text response from Gemini. Full response:", response)
        # Return a fallback script
        return f"""[Speaker 0] Welcome to our tech news deep dive. I'm Sarah.
[Speaker 1] And I'm Michael. We've got some interesting developments to discuss today.
[Speaker 0] That's right. Unfortunately, we encountered some technical difficulties processing the full content, but let's talk about what we can.
[Speaker 1] Technology is moving at such an incredible pace these days.
[Speaker 0] It really is. Every week brings new breakthroughs and challenges.
[Speaker 1] Well, that's all for today's episode. Thanks for listening!
[Speaker 0] See you next time!"""
    except Exception as e:
        print(f"Error generating podcast script: {e}")
        # Return a fallback script
        return f"""[Speaker 0] Welcome to our tech news deep dive. I'm Sarah.
[Speaker 1] And I'm Michael. We've got some interesting developments to discuss today.
[Speaker 0] That's right. Unfortunately, we encountered some technical difficulties processing the full content, but let's talk about what we can.
[Speaker 1] Technology is moving at such an incredible pace these days.
[Speaker 0] It really is. Every week brings new breakthroughs and challenges.
[Speaker 1] Well, that's all for today's episode. Thanks for listening!
[Speaker 0] See you next time!"""


def save_podcast_script(script, output_path):
    """Save the podcast script to a file"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(script)
    print(f"Podcast script saved to: {output_path}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate podcast script from markdown files')
    parser.add_argument('--markdown_dir', type=str, required=True, help='Directory containing markdown files')
    parser.add_argument('--output', type=str, default='podcast_script.txt', help='Output file for podcast script')
    parser.add_argument('--duration', type=int, default=30, help='Podcast duration in minutes (default: 30)')
    args = parser.parse_args()
    
    # Check for Gemini API key
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("Please set the GEMINI_API_KEY environment variable.")
        return
    
    # Read markdown files
    print(f"Reading markdown files from {args.markdown_dir}...")
    markdown_grouped = read_markdown_files(args.markdown_dir)
    
    if not markdown_grouped:
        print("No markdown files found in the specified directory or no news articles found.")
        return
    
    print(f"Found {sum(len(articles) for articles in markdown_grouped.values())} news articles across {len(markdown_grouped)} senders.")
    
    # Generate podcast script
    print(f"Generating {args.duration}-minute podcast script...")
    script = generate_podcast_script(markdown_grouped, args.duration)
    
    # Save script
    save_podcast_script(script, args.output)

if __name__ == '__main__':
    main()