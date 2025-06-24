import os
import glob
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

def read_markdown_files(markdown_dir):
    """Read all markdown files from a directory and return their content"""
    markdown_files = glob.glob(os.path.join(markdown_dir, "*.md"))
    content_pieces = []
    
    for file_path in markdown_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            content_pieces.append({
                'filename': os.path.basename(file_path),
                'content': content
            })
    
    return content_pieces

def generate_podcast_script(markdown_content, duration_minutes=30):
    """Generate a podcast script from markdown content using Gemini"""
    
    # Combine all content into a single string for analysis
    combined_content = "\n\n---\n\n".join([
        f"Article: {piece['filename']}\n{piece['content']}" 
        for piece in markdown_content
    ])
    
    # Truncate if too long (keeping within token limits)
    if len(combined_content) > 50000:
        combined_content = combined_content[:50000] + "\n\n[Content truncated...]"
    
    # Calculate approximate word count target based on duration
    # Average speaking rate is about 140-160 words per minute for conversational content
    target_words = duration_minutes * 150  # Using 150 WPM as middle ground
    
    # Adjust max_tokens based on duration (rough estimate: 1 token ≈ 0.75 words)
    max_tokens = min(8000, int(target_words * 1.5))  # Cap at 8000 tokens for API limits
    
    prompt = f"""
You are a podcast script writer creating a {duration_minutes}-minute conversational podcast in the style of NotebookLM's Audio Overview.

CRITICAL RULES:
1. Hosts should introduce themselves ONLY at the very beginning (e.g., "I'm Sarah" and "I'm Michael")
2. After introductions, NEVER have hosts say their own names again during the conversation
3. Use natural conversation flow with quick back-and-forth exchanges
4. Include natural interruptions, overlapping dialogue, and reactions
5. Keep responses short and punchy - most exchanges should be 1-3 sentences
6. Use conversational fillers and reactions like "mm-hmm", "yeah", "right", "exactly", "oh", "ah"
7. NO explicit pause markers - let conversation flow naturally
8. Include emotional variety - surprise ("Wow!"), curiosity ("Hmm, that's interesting..."), agreement ("Absolutely!"), thoughtfulness ("You know, that makes me think...")
9. Use natural speech patterns including occasional "uh", "um", trailing off with "...", and incomplete thoughts

The two hosts:
- Speaker 0 (female): More analytical, asks probing questions, provides context
- Speaker 1 (male): More enthusiastic, makes connections, adds energy

Format the script EXACTLY like this:
[Speaker 0] Text here
[Speaker 1] Text here

Example opening:
[Speaker 0] Welcome to our deep dive into [topic]. I'm Sarah.
[Speaker 1] And I'm Michael. Today we're looking at some really fascinating material.
[Speaker 0] Right, so let's jump in...

Example of natural flow (after intro):
[Speaker 0] So, the sheer speed of change in AI is... I, I mean, it's just astounding.
[Speaker 1] It really is.
[Speaker 0] But here's this thought from, uh, one of the leading voices at OpenAI that really stuck with me...

IMPORTANT: Make the conversation feel REAL - with genuine reactions, natural interruptions, incomplete thoughts, and authentic engagement. The hosts should sound like they're discovering insights together, not reading a script.

Content to discuss:
{combined_content}

Create an engaging {duration_minutes}-minute podcast script (approximately {target_words} words) that covers the most interesting and important points from this content. Focus on making it sound like a genuine, dynamic conversation between two intelligent people who are genuinely excited about the topic.
"""

    # Configure API key
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    model = genai.GenerativeModel('gemini-2.5-pro')
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=0.8  # Slightly higher for more natural variation
            )
        )
        
        # Check if response was blocked
        if response.candidates and response.candidates[0].finish_reason == 2:
            print("⚠️  Content was blocked by safety filters. Trying with adjusted prompt...")
            # Try a simpler prompt
            safer_prompt = f"""
Create a {duration_minutes}-minute conversational podcast script between two hosts discussing technology news and insights.

Format:
[Speaker 0] (female host Sarah)
[Speaker 1] (male host Michael)

The hosts should introduce themselves at the beginning, then have a natural conversation about the key points from the articles provided. Keep it informative but engaging.

Content summary to discuss:
{combined_content[:10000]}  # Limit content size

Generate approximately {target_words} words.
"""
            response = model.generate_content(
                safer_prompt,
                generation_config=genai.GenerationConfig(
                    max_output_tokens=max_tokens,
                    temperature=0.7
                )
            )
        
        return response.text
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
    
    genai.configure(api_key=api_key)
    
    # Read markdown files
    print(f"Reading markdown files from {args.markdown_dir}...")
    markdown_content = read_markdown_files(args.markdown_dir)
    
    if not markdown_content:
        print("No markdown files found in the specified directory.")
        return
    
    print(f"Found {len(markdown_content)} markdown files.")
    
    # Generate podcast script
    print(f"Generating {args.duration}-minute podcast script...")
    script = generate_podcast_script(markdown_content, args.duration)
    
    # Save script
    save_podcast_script(script, args.output)

if __name__ == '__main__':
    main()