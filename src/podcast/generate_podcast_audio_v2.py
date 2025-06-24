import os
import re
from google import genai
from google.genai import types
import argparse
from dotenv import load_dotenv
import io
import tempfile
import wave
import random

# Handle Python 3.13+ audio compatibility
try:
    from pydub import AudioSegment
    AUDIO_AVAILABLE = True
    print("✅ Audio processing ready")
except ImportError as e:
    print(f"⚠️  Audio processing issue: {e}")
    from audio_utils import get_audio_segment, install_audio_dependencies
    
    # Try to install missing dependencies
    if install_audio_dependencies():
        try:
            from pydub import AudioSegment
            AUDIO_AVAILABLE = True
            print("✅ Audio processing now working")
        except ImportError:
            AudioSegment = get_audio_segment()
            AUDIO_AVAILABLE = False
            print("⚠️  Using fallback audio processing")
    else:
        AudioSegment = get_audio_segment()
        AUDIO_AVAILABLE = False
        print("⚠️  Using fallback audio processing")

load_dotenv()

def parse_podcast_script(script_path):
    """Parse podcast script and extract dialogue segments"""
    with open(script_path, 'r', encoding='utf-8') as f:
        script_content = f.read()
    
    # Split script into segments
    segments = []
    lines = script_content.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        if not line:
            i += 1
            continue
            
        # Match [Speaker 0] or [Speaker 1] with optional (name)
        speaker0_match = re.match(r'\[Speaker 0\](?:\s*\([^)]+\))?\s*(.*)', line)
        speaker1_match = re.match(r'\[Speaker 1\](?:\s*\([^)]+\))?\s*(.*)', line)
        
        if speaker0_match:
            # Get the text from the match
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
                segments.append({
                    'speaker': 'speaker0',
                    'text': text,
                    'type': 'dialogue'
                })
                
        elif speaker1_match:
            # Get the text from the match
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
                segments.append({
                    'speaker': 'speaker1',
                    'text': text,
                    'type': 'dialogue'
                })
        
        i += 1
    
    return segments

def wave_file(filename, pcm, channels=1, rate=24000, sample_width=2):
    """Helper function to save PCM data as WAV file"""
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm)

def generate_speech_audio(text, voice_gender, output_path):
    """Generate speech audio using Gemini TTS API with proper voice configuration"""
    
    try:
        print(f"🎤 Generating audio with Gemini TTS for {voice_gender} voice...")
        
        # Create client using correct API
        client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
        
        # Choose voice based on gender - Kore=female, Puck=male according to Gemini docs
        voice_name = "Kore" if voice_gender == "female" else "Puck"
        
        # Create the prompt
        # Keep names if they're introducing themselves (e.g., "I'm Sarah")
        if "I'm Sarah" in text or "I'm Michael" in text:
            speaker_name = "Sarah" if voice_gender == "female" else "Michael"
            prompt = f"TTS the following: {speaker_name}: {text}"
        else:
            # Otherwise, don't include speaker names
            prompt = f"TTS the following: {text}"
        
        # Generate content with proper voice configuration
        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice_name,
                        )
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
                    # Save as WAV first, then convert if needed
                    wav_path = output_path.replace('.mp3', '.wav')
                    wave_file(wav_path, part.inline_data.data)
                    
                    # Convert to MP3 if needed using pydub
                    if output_path.endswith('.mp3') and AUDIO_AVAILABLE:
                        try:
                            audio = AudioSegment.from_wav(wav_path)
                            audio.export(output_path, format="mp3")
                            # Keep both files for now - WAV as backup
                            print(f"✅ Converted WAV to MP3: {os.path.basename(output_path)}")
                        except Exception as e:
                            print(f"⚠️  Could not convert to MP3: {e}, keeping WAV")
                    else:
                        # Keep as WAV if MP3 conversion not available
                        final_path = output_path.replace('.mp3', '.wav')
                        if wav_path != final_path:
                            os.rename(wav_path, final_path)
                    
                    print(f"✅ Generated audio with Gemini TTS (voice: {voice_name})")
                    return True
        
        print("❌ No audio data found in Gemini TTS response")
        return False
        
    except Exception as e:
        print(f"❌ Gemini TTS failed: {e}")
        print(f"   Make sure GEMINI_API_KEY is set and Gemini TTS is enabled")
        return False

def create_podcast_audio(segments, output_dir="podcast_audio_segments"):
    """Create audio segments for the podcast with dynamic pacing"""
    os.makedirs(output_dir, exist_ok=True)
    
    audio_segments = []
    segment_count = 0
    
    # Voice mapping
    voice_map = {
        'speaker0': 'female',    # Analytical female voice
        'speaker1': 'male'       # Enthusiastic male voice
    }
    
    for i, segment in enumerate(segments):
        if segment['type'] == 'dialogue':
            segment_count += 1
            print(f"Generating audio segment {segment_count}/{len([s for s in segments if s['type'] == 'dialogue'])}: {segment['speaker']}")
            
            audio_file = os.path.join(output_dir, f"segment_{segment_count:03d}_{segment['speaker']}.mp3")
            
            # Generate speech
            success = generate_speech_audio(
                segment['text'], 
                voice_map[segment['speaker']], 
                audio_file
            )
            
            if success:
                try:
                    # Find the actual generated file (might be .wav if MP3 conversion failed)
                    actual_file = audio_file
                    wav_file = audio_file.replace('.mp3', '.wav')
                    
                    if not os.path.exists(audio_file) and os.path.exists(wav_file):
                        actual_file = wav_file
                    
                    # Load the generated audio segment
                    if AUDIO_AVAILABLE and os.path.exists(actual_file) and os.path.getsize(actual_file) > 0:
                        # Try to load the audio file
                        try:
                            if actual_file.endswith('.wav'):
                                audio = AudioSegment.from_wav(actual_file)
                            elif actual_file.endswith('.mp3'):
                                audio = AudioSegment.from_mp3(actual_file)
                            else:
                                audio = AudioSegment.from_file(actual_file)
                            
                            # Add natural micro-pauses between segments
                            # Determine pause duration based on context
                            if i > 0:
                                prev_text = segments[i-1].get('text', '')
                                curr_text = segment['text']
                                
                                # Short pause for quick exchanges
                                if len(curr_text) < 20 or curr_text.lower() in ['mm-hmm.', 'yeah.', 'right.', 'exactly.', 'oh.', 'uh-huh.']:
                                    pause_ms = random.randint(50, 150)  # Very short pause
                                # Slightly longer for topic transitions
                                elif '?' in prev_text or curr_text.startswith(('So,', 'Now,', 'But', 'And', 'Let')):
                                    pause_ms = random.randint(200, 400)
                                # Normal conversational pause
                                else:
                                    pause_ms = random.randint(100, 250)
                                
                                # Add the pause before this segment
                                pause = AudioSegment.silent(duration=pause_ms)
                                audio_segments.append(pause)
                            
                            audio_segments.append(audio)
                            print(f"✅ Loaded audio segment {segment_count} ({os.path.basename(actual_file)})")
                        except Exception as e:
                            print(f"❌ Failed to load audio file {actual_file}: {e}")
                            # Add silent segment as fallback
                            silent = AudioSegment.silent(duration=2000)
                            audio_segments.append(silent)
                    else:
                        print(f"⚠️  Audio file not found or empty: {actual_file}")
                        # Add silent segment as placeholder
                        silent = AudioSegment.silent(duration=2000)  # 2 seconds
                        audio_segments.append(silent)
                        
                except Exception as e:
                    print(f"❌ Failed to process audio segment: {e}")
                    # Add silent segment as fallback
                    silent = AudioSegment.silent(duration=2000)
                    audio_segments.append(silent)
            else:
                print(f"❌ Failed to generate audio for segment {segment_count}")
                print(f"   Check GEMINI_API_KEY and Gemini TTS availability")
                # Add silent segment as placeholder
                if AUDIO_AVAILABLE:
                    silent = AudioSegment.silent(duration=2000)
                    audio_segments.append(silent)
                else:
                    # Mock audio segment for fallback mode
                    audio_segments.append(AudioSegment())
    
    return audio_segments

def combine_audio_segments(audio_segments, output_path):
    """Combine all audio segments into final podcast"""
    if not audio_segments:
        print("No audio segments to combine.")
        return False
    
    print("Combining audio segments...")
    
    # Add intro music placeholder (just silence for now)
    intro_music = AudioSegment.silent(duration=2000)  # 2 seconds
    final_audio = intro_music
    
    # Add all segments
    for segment in audio_segments:
        final_audio += segment
    
    # Add outro music placeholder
    outro_music = AudioSegment.silent(duration=2000)  # 2 seconds
    final_audio += outro_music
    
    # Export final podcast
    final_audio.export(output_path, format="mp3", bitrate="128k")
    print(f"Final podcast audio saved to: {output_path}")
    return True

def main():
    parser = argparse.ArgumentParser(description='Generate podcast audio from script using Gemini TTS')
    parser.add_argument('--script', type=str, required=True, help='Path to podcast script file')
    parser.add_argument('--output', type=str, default='podcast.mp3', help='Output audio file')
    parser.add_argument('--segments_dir', type=str, default='podcast_audio_segments', help='Directory for audio segments')
    args = parser.parse_args()
    
    # Check for Gemini API key
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("Please set the GEMINI_API_KEY environment variable.")
        return
    
    # Configure Gemini
    genai.configure(api_key=api_key)
    
    # Parse script
    print(f"Parsing podcast script from {args.script}...")
    segments = parse_podcast_script(args.script)
    
    dialogue_segments = [s for s in segments if s['type'] == 'dialogue']
    print(f"Found {len(dialogue_segments)} dialogue segments to convert to audio.")
    
    if not dialogue_segments:
        print("No dialogue segments found in script.")
        return
    
    # Generate audio segments
    audio_segments = create_podcast_audio(segments, args.segments_dir)
    
    # Combine into final podcast
    if audio_segments:
        combine_audio_segments(audio_segments, args.output)
        print("Podcast audio generation complete!")
    else:
        print("No audio segments were generated successfully.")

if __name__ == '__main__':
    main()