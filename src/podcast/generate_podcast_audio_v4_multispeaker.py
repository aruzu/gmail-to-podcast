import os
import re
import google.generativeai as genai
from google.genai import types
from google import genai as google_genai
import argparse
from dotenv import load_dotenv
import wave
import tempfile

# Handle Python 3.13+ audio compatibility
try:
    from pydub import AudioSegment
    from pydub.effects import normalize
    AUDIO_AVAILABLE = True
    print("✅ Audio processing ready")
except ImportError as e:
    print(f"⚠️  Audio processing issue: {e}")
    AUDIO_AVAILABLE = False

load_dotenv()

def parse_podcast_script(script_path):
    """Parse podcast script and prepare it for multi-speaker TTS"""
    with open(script_path, 'r', encoding='utf-8') as f:
        script_content = f.read()
    
    # Convert speaker tags to named speakers for multi-speaker TTS
    # [Speaker 0] -> Sarah:
    # [Speaker 1] -> Michael:
    
    lines = script_content.split('\n')
    formatted_lines = []
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        if not line:
            formatted_lines.append('')
            i += 1
            continue
            
        # Match speaker patterns
        speaker0_match = re.match(r'(?:\*\*)?\[Speaker 0\](?:\s*\([^)]+\))?(?:\s*[^:]*:)?\s*(.*)', line)
        speaker1_match = re.match(r'(?:\*\*)?\[Speaker 1\](?:\s*\([^)]+\))?(?:\s*[^:]*:)?\s*(.*)', line)
        
        if speaker0_match:
            text = speaker0_match.group(1).strip()
            
            # If text is empty, check the next line(s)
            if not text and i + 1 < len(lines):
                i += 1
                text = lines[i].strip()
                # Continue reading lines until we hit another speaker or empty line
                while i + 1 < len(lines) and not re.match(r'\[Speaker [01]\]', lines[i + 1]) and lines[i + 1].strip():
                    i += 1
                    text += " " + lines[i].strip()
            
            if text:
                formatted_lines.append(f"Sarah: {text}")
                
        elif speaker1_match:
            text = speaker1_match.group(1).strip()
            
            # If text is empty, check the next line(s)
            if not text and i + 1 < len(lines):
                i += 1
                text = lines[i].strip()
                # Continue reading lines until we hit another speaker or empty line
                while i + 1 < len(lines) and not re.match(r'\[Speaker [01]\]', lines[i + 1]) and lines[i + 1].strip():
                    i += 1
                    text += " " + lines[i].strip()
            
            if text:
                formatted_lines.append(f"Michael: {text}")
        else:
            # Keep other lines as-is
            formatted_lines.append(line)
        
        i += 1
    
    return '\n'.join(formatted_lines)

def wave_file(filename, pcm, channels=1, rate=24000, sample_width=2):
    """Helper function to save PCM data as WAV file"""
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm)

def generate_multispeaker_podcast(transcript, output_path):
    """Generate podcast audio using Gemini TTS multi-speaker API"""
    
    try:
        print("🎤 Generating multi-speaker podcast audio...")
        print("   Sarah: Zephyr voice (analytical female)")
        print("   Michael: Puck voice (enthusiastic male)")
        
        # Create client
        client = google_genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
        
        # Generate with multi-speaker configuration
        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=transcript,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                        speaker_voice_configs=[
                            types.SpeakerVoiceConfig(
                                speaker='Sarah',
                                voice_config=types.VoiceConfig(
                                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                        voice_name='zephyr',
                                    )
                                )
                            ),
                            types.SpeakerVoiceConfig(
                                speaker='Michael',
                                voice_config=types.VoiceConfig(
                                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                        voice_name='puck',
                                    )
                                )
                            ),
                        ]
                    )
                )
            )
        )
        
        # Extract audio data
        if response.candidates and len(response.candidates) > 0:
            candidate = response.candidates[0]
            if candidate.content and candidate.content.parts and len(candidate.content.parts) > 0:
                part = candidate.content.parts[0]
                if hasattr(part, 'inline_data') and part.inline_data:
                    # Save as WAV first
                    wav_path = output_path.replace('.mp3', '.wav')
                    wave_file(wav_path, part.inline_data.data)
                    
                    print(f"✅ Generated multi-speaker audio: {wav_path}")
                    
                    # Convert to MP3 if needed
                    if output_path.endswith('.mp3') and AUDIO_AVAILABLE:
                        try:
                            audio = AudioSegment.from_wav(wav_path)
                            # Normalize audio levels
                            audio = normalize(audio)
                            # Speed up by 10% for faster pacing
                            audio = audio._spawn(audio.raw_data, overrides={
                                "frame_rate": int(audio.frame_rate * 1.1)
                            }).set_frame_rate(audio.frame_rate)
                            
                            audio.export(output_path, format="mp3", bitrate="192k")
                            print(f"✅ Converted to MP3 with 10% speed increase: {output_path}")
                            
                            # Calculate duration
                            duration = len(audio) / 1000
                            print(f"⏱️  Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
                        except Exception as e:
                            print(f"⚠️  Could not convert to MP3: {e}")
                    
                    return True
        
        print("❌ No audio data found in response")
        return False
        
    except Exception as e:
        print(f"❌ Error generating multi-speaker audio: {e}")
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            print("   ⚠️  Hit quota limit. Try again later.")
        return False

def main():
    parser = argparse.ArgumentParser(description='Generate podcast audio using Gemini TTS multi-speaker API')
    parser.add_argument('--script', type=str, required=True, help='Path to podcast script file')
    parser.add_argument('--output', type=str, default='podcast_multispeaker.mp3', help='Output audio file')
    args = parser.parse_args()
    
    # Check for Gemini API key
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("❌ Please set the GEMINI_API_KEY environment variable.")
        return
    
    # Parse and format script for multi-speaker TTS
    print(f"📝 Parsing podcast script from {args.script}...")
    formatted_transcript = parse_podcast_script(args.script)
    
    # Count dialogue lines
    dialogue_count = len([line for line in formatted_transcript.split('\n') if line.startswith(('Sarah:', 'Michael:'))])
    print(f"📊 Found {dialogue_count} dialogue segments")
    
    # Preview first few lines
    preview_lines = formatted_transcript.split('\n')[:5]
    print("\n📄 Preview of formatted transcript:")
    for line in preview_lines:
        if line:
            print(f"   {line}")
    print("   ...")
    
    # Generate multi-speaker audio in one API call
    print(f"\n🎯 Generating entire podcast in ONE API call...")
    success = generate_multispeaker_podcast(formatted_transcript, args.output)
    
    if success:
        print(f"\n✅ Podcast audio generation complete!")
        print(f"📁 Output: {args.output}")
        print("\nFeatures:")
        print("   ✓ Multi-speaker dialogue with distinct voices")
        print("   ✓ Natural conversation flow")
        print("   ✓ 10% faster pacing")
        print("   ✓ Single API call (no quota issues!)")
    else:
        print("\n❌ Failed to generate podcast audio")

if __name__ == '__main__':
    main()