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
You are a podcast script writer. Create a {duration_minutes}-minute conversational podcast script between two hosts discussing the content provided below. 

The podcast should be in the style of NotebookLM's Audio Overview - engaging, informative, and conversational. The two hosts should:
- Be named Sarah (female) and Michael (male)
- Have distinct personalities (Sarah is more analytical, Michael is more enthusiastic)
- Discuss the key themes, insights, and interesting points from the articles
- Ask each other questions and build on each other's points
- Use natural conversation flow with occasional interruptions, agreements, and clarifications
- Include smooth transitions between topics
- End with a thoughtful summary and key takeaways

Format the script clearly with:
- [SARAH]: for host Sarah's dialogue
- [MICHAEL]: for host Michael's dialogue
- [PAUSE] for natural pauses
- [MUSIC] for intro/outro music cues

Content to discuss:
{combined_content}

Create an engaging {duration_minutes}-minute podcast script (approximately {target_words} words) that covers the most interesting and important points from this content. Adjust the depth of discussion and number of topics covered to fit the {duration_minutes}-minute timeframe.
"""

    model = genai.GenerativeModel('gemini-2.5-flash')
    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=0.7
        )
    )
    
    return response.text

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