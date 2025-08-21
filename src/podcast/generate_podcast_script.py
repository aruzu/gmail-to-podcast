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

CRITICAL REQUIREMENTS:
1. Create natural, dynamic conversation between two hosts with distinct personalities
2. Sarah (analytical): asks probing questions, provides context, thinks deeply
3. Michael (enthusiastic): makes connections, adds energy, gets excited about insights
4. Use quick back-and-forth exchanges - most responses should be 1-3 sentences
5. Include natural interruptions, overlapping dialogue, and reactions ("mm-hmm", "yeah", "exactly")
6. NO explicit pause markers - let conversation flow naturally
7. Include emotional variety - surprise, curiosity, agreement, thoughtfulness

Format the script EXACTLY like this:
[SARAH]: Text here
[MICHAEL]: Text here

CONVERSATION FLOW:
- Start with brief introductions
- Move through content with natural transitions
- Build excitement and engagement throughout
- End with thoughtful summary and key takeaways
- Make it sound like a genuine conversation between two intelligent people discovering insights together

Content to discuss:
{combined_content}

Create an engaging {duration_minutes}-minute podcast script (approximately {target_words} words) that feels like an authentic, dynamic conversation. Focus on making the hosts sound genuinely excited about the material and engaged with each other.
"""

    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=0.7
            )
        )
    except Exception as e:
        print(f"Error generating script: {e}")
        return generate_fallback_script(duration_minutes)
    
    # Extract text from response
    try:
        if hasattr(response, 'text') and response.text:
            return response.text
        elif hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'content') and candidate.content:
                if hasattr(candidate.content, 'parts') and candidate.content.parts:
                    return candidate.content.parts[0].text
        
        print("No text response received. Using fallback.")
        return generate_fallback_script(duration_minutes)
        
    except Exception as e:
        print(f"Error extracting response: {e}")
        return generate_fallback_script(duration_minutes)

def generate_fallback_script(duration_minutes):
    """Generate a basic fallback script when AI generation fails"""
    return f"""[SARAH] Welcome to our tech news deep dive. I'm Sarah.

[MICHAEL] And I'm Michael. We've got some interesting developments to discuss today.

[SARAH] That's right. Unfortunately, we encountered some technical difficulties processing the full content, but let's talk about what we can.

[MICHAEL] Technology is moving at such an incredible pace these days.

[SARAH] It really is. Every week brings new breakthroughs and challenges.

[MICHAEL] The implications for how we work and live are fascinating to consider.

[SARAH] Absolutely. It's important to stay informed about these developments.

[MICHAEL] Well, that's all for today's episode. Thanks for listening!

[SARAH] See you next time!"""

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