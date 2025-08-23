#!/usr/bin/env python3
"""
Minimal test for podcast generation with sample content.
Creates sample markdown content and tests 5-minute podcast generation.
"""

import os
import tempfile
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

def create_test_markdown():
    """Create minimal test markdown content"""
    return [
        {
            'filename': 'ai_news.md',
            'content': '''# AI Makes Major Breakthrough

**From:** TechNews <news@tech.com>
**Date:** Today

Scientists announced a new AI model that can understand context better than ever before. 
The model achieved 95% accuracy on reasoning tasks and uses less computing power.

Key points:
- Better language understanding
- Improved reasoning capabilities  
- More efficient processing
- Potential for real-world applications

This could revolutionize how we interact with AI systems.'''
        },
        {
            'filename': 'tech_update.md', 
            'content': '''# Quantum Computing Progress

**From:** ScienceDaily <updates@science.com>
**Date:** Yesterday

Researchers built a new quantum computer with 1000 qubits. This is a major milestone
for the field and brings practical quantum applications closer to reality.

Achievements:
- Record number of stable qubits
- Better error correction
- Faster processing speeds
- New optimization algorithms

Companies are investing billions in this technology.'''
        }
    ]

def main():
    print("[TEST] Minimal Podcast Generation Test")
    print("Testing: 5-minute conversation + audio generation")
    print("=" * 50)
    
    # Check environment
    gemini_key = os.getenv('GEMINI_API_KEY')
    
    if not gemini_key:
        print("❌ Set GEMINI_API_KEY in .env file") 
        return
    
    print("✅ Environment ready")
    
    # Test 1: Generate script
    print("\n🎬 Test 1: Generate 5-minute script with Gemini...")
    try:
        genai.configure(api_key=gemini_key)
        
        # Import here to avoid issues if modules aren't ready
        from podcast.generate_podcast_script import generate_podcast_script
        
        # Create sample content
        markdown_list = create_test_markdown()
        # Convert to grouped format expected by the function
        markdown_content = {
            "TechNews": [markdown_list[0]],
            "ScienceDaily": [markdown_list[1]]
        }
        print(f"📄 Using {len(markdown_list)} sample articles")
        
        # Generate 5-minute script
        script = generate_podcast_script(markdown_content, duration_minutes=5)
        
        # Save and analyze
        os.makedirs("test_output", exist_ok=True)
        script_path = "test_output/minimal_test_script.txt"
        
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script)
        
        # Count dialogue
        sarah_lines = script.count('[SARAH]:')
        michael_lines = script.count('[MICHAEL]:')
        word_count = len(script.split())
        
        print(f"✅ Script saved: {script_path}")
        print(f"📊 Sarah: {sarah_lines} lines, Michael: {michael_lines} lines")
        print(f"📝 Word count: {word_count} words (~{word_count/150:.1f} minutes)")
        
    except Exception as e:
        print(f"❌ Script generation failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test 2: Generate audio  
    print(f"\n🎵 Test 2: Generate audio with Gemini TTS...")
    try:
        # Note: No need to configure - the genai.Client will use the API key directly
        from podcast.generate_podcast_audio import parse_podcast_script, create_podcast_audio, combine_audio_segments
        
        # Parse script
        segments = parse_podcast_script(script_path)
        dialogue_count = len([s for s in segments if s['type'] == 'dialogue'])
        
        print(f"🎭 Found {dialogue_count} dialogue segments")
        
        # Generate audio (limiting to first few segments for quick test)
        test_segments = [s for s in segments if s['type'] == 'dialogue'][:3]  # Test with first 3 segments
        print(f"🎤 Testing with first {len(test_segments)} segments...")
        
        audio_segments = create_podcast_audio(test_segments, "test_output/audio_segments")
        
        if audio_segments:
            audio_path = "test_output/minimal_test_audio.mp3"
            success = combine_audio_segments(audio_segments, audio_path)
            
            if success and os.path.exists(audio_path):
                size = os.path.getsize(audio_path)
                print(f"✅ Audio generated: {audio_path} ({size:,} bytes)")
            else:
                print("❌ Audio combining failed")
        else:
            print("❌ No audio segments generated")
            
    except Exception as e:
        print(f"❌ Audio generation failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n🎉 Minimal test completed!")
    print("Check test_output/ directory for results")

if __name__ == "__main__":
    main()