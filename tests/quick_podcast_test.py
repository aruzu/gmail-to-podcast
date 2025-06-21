#!/usr/bin/env python3
"""
Quick test for 5-minute podcast generation.
Tests only the last 2 steps: script generation and audio creation.
"""

import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

def test_quick_podcast():
    """Quick test using existing markdown files"""
    
    print("🎤 Quick 5-Minute Podcast Test")
    print("=" * 40)
    
    # Check API keys
    gemini_key = os.getenv('GEMINI_API_KEY')
    
    if not gemini_key:
        print("❌ Missing GEMINI_API_KEY")
        return
    
    print("✅ API keys found")
    
    # Step 1: Generate 5-minute script from existing markdown
    print("\n📝 Step 1: Generating 5-minute conversation script...")
    
    try:
        from generate_podcast_script import read_markdown_files, generate_podcast_script, save_podcast_script
        
        # Use existing markdown directory
        markdown_dir = "s2e2_markdown"
        if not os.path.exists(markdown_dir):
            print(f"❌ Markdown directory '{markdown_dir}' not found")
            print("   Run the pipeline first to generate markdown files")
            return
        
        genai.configure(api_key=gemini_key)
        markdown_content = read_markdown_files(markdown_dir)
        
        if not markdown_content:
            print(f"❌ No markdown files found in {markdown_dir}")
            return
        
        print(f"📄 Found {len(markdown_content)} markdown files")
        
        # Generate 5-minute script
        script = generate_podcast_script(markdown_content, duration_minutes=5)
        
        # Save script
        os.makedirs("test_output", exist_ok=True)
        script_path = "test_output/quick_test_script.txt"
        save_podcast_script(script, script_path)
        
        print(f"✅ Script generated: {script_path}")
        
        # Show preview
        lines = script.split('\n')
        sarah_count = len([l for l in lines if l.startswith('[SARAH]:')])
        michael_count = len([l for l in lines if l.startswith('[MICHAEL]:')])
        print(f"💬 Sarah: {sarah_count} lines, Michael: {michael_count} lines")
        
    except Exception as e:
        print(f"❌ Script generation failed: {e}")
        return
    
    # Step 2: Generate audio using Gemini TTS
    print("\n🎵 Step 2: Generating audio with Gemini TTS...")
    
    try:
        from generate_podcast_audio import parse_podcast_script, create_podcast_audio, combine_audio_segments
        
        # Parse script and generate audio
        segments = parse_podcast_script(script_path)
        dialogue_segments = [s for s in segments if s['type'] == 'dialogue']
        print(f"🎭 Processing {len(dialogue_segments)} dialogue segments...")
        
        # Generate audio segments
        audio_segments = create_podcast_audio(segments, "test_output/audio_segments")
        
        if audio_segments:
            # Combine into final audio
            audio_path = "test_output/quick_test_podcast.mp3"
            success = combine_audio_segments(audio_segments, audio_path)
            
            if success:
                size = os.path.getsize(audio_path)
                print(f"✅ Audio generated: {audio_path} ({size:,} bytes)")
            else:
                print("❌ Failed to combine audio segments")
                return
        else:
            print("❌ No audio segments generated")
            return
            
    except Exception as e:
        print(f"❌ Audio generation failed: {e}")
        return
    
    # Success summary
    print("\n🎉 Test completed successfully!")
    print("Files generated:")
    print(f"   📝 Script: test_output/quick_test_script.txt")
    print(f"   🎵 Audio:  test_output/quick_test_podcast.mp3")
    print("\nTo listen: open test_output/quick_test_podcast.mp3")

if __name__ == "__main__":
    test_quick_podcast()