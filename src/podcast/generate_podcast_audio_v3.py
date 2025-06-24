import os
import re
import google.generativeai as genai
from google.genai import types
from google import genai as google_genai
import argparse
from dotenv import load_dotenv
import io
import tempfile
import wave
import random
import time
import json

# Handle Python 3.13+ audio compatibility
try:
    from pydub import AudioSegment
    from pydub.effects import normalize
    AUDIO_AVAILABLE = True
    print("✅ Audio processing ready")
except ImportError as e:
    print(f"⚠️  Audio processing issue: {e}")
    from audio_utils import get_audio_segment, install_audio_dependencies
    
    # Try to install missing dependencies
    if install_audio_dependencies():
        try:
            from pydub import AudioSegment
            from pydub.effects import normalize
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

# Voice configuration with characteristics
# Available voices from error message: achernar, achird, algenib, algieba, alnilam, aoede, autonoe, 
# callirrhoe, charon, despina, enceladus, erinome, fenrir, gacrux, iapetus, kore, laomedeia, 
# leda, orus, puck, pulcherrima, rasalgethi, sadachbia, sadaltager, schedar, sulafat, umbriel, 
# vindemiatrix, zephyr, zubenelgenubi
VOICE_CONFIG = {
    'female_analytical': {
        'voices': ['kore', 'aoede', 'callirrhoe'],  # Clear, articulate voices
        'traits': 'thoughtful and analytical',
        'pace': 'measured'
    },
    'female_professional': {
        'voices': ['vindemiatrix', 'schedar', 'algieba'],  # Professional, balanced voices
        'traits': 'professional and engaging',
        'pace': 'steady'
    },
    'female_engaged': {
        'voices': ['umbriel', 'erinome', 'laomedeia'],  # Engaged but not overly excited
        'traits': 'interested and conversational',
        'pace': 'natural'
    },
    'male_enthusiastic': {
        'voices': ['puck', 'zephyr', 'orus'],  # Upbeat, bright voices
        'traits': 'enthusiastic and engaging',
        'pace': 'energetic'
    },
    'male_conversational': {
        'voices': ['gacrux', 'algenib', 'rasalgethi'],  # Natural conversational voices
        'traits': 'friendly and conversational',
        'pace': 'relaxed'
    },
    'male_expert': {
        'voices': ['achird', 'fenrir', 'charon'],  # Authoritative voices
        'traits': 'knowledgeable and clear',
        'pace': 'steady'
    },
    'female_curious': {
        'voices': ['leda', 'autonoe', 'despina'],  # Warm, inviting voices
        'traits': 'curious and warm',
        'pace': 'conversational'
    }
}

def parse_podcast_script(script_path):
    """Parse podcast script and extract dialogue segments with emotional context"""
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
            
        # Match various speaker formats
        # Format 1: [Speaker 0] or [Speaker 1] with optional (name)
        # Format 2: **[Speaker 0] Name:** or **[Speaker 1] Name:**
        speaker0_match = re.match(r'(?:\*\*)?\[Speaker 0\](?:\s*\([^)]+\))?(?:\s*[^:]*:)?\s*(.*)', line)
        speaker1_match = re.match(r'(?:\*\*)?\[Speaker 1\](?:\s*\([^)]+\))?(?:\s*[^:]*:)?\s*(.*)', line)
        
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
                # Analyze emotional context
                emotion = analyze_emotion(text)
                segments.append({
                    'speaker': 'speaker0',
                    'text': text,
                    'type': 'dialogue',
                    'emotion': emotion
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
                # Analyze emotional context
                emotion = analyze_emotion(text)
                segments.append({
                    'speaker': 'speaker1',
                    'text': text,
                    'type': 'dialogue',
                    'emotion': emotion
                })
        
        i += 1
    
    return segments

def analyze_emotion(text):
    """Simple emotion analysis for more natural delivery"""
    # For more neutral, natural sound, default to 'engaged' for most segments
    # Only use other emotions sparingly
    
    text_lower = text.lower()
    
    # Short acknowledgments
    if len(text) < 20 and any(ack in text_lower for ack in ['yeah', 'mm-hmm', 'uh-huh', 'right', 'okay', 'ah']):
        return 'acknowledging'
    
    # Questions get curious tone
    elif '?' in text and len(text) < 100:
        return 'curious'
    
    # Default to engaged for natural conversation
    else:
        return 'engaged'

def get_voice_for_segment(speaker, emotion, voice_type='default'):
    """Select appropriate voice based on speaker and emotional context"""
    # Use Zephyr for Sarah (female) and Puck for Michael (male) as requested
    if speaker == 'speaker0':  # Sarah - female
        voice_name = 'zephyr'
        config = {
            'traits': 'professional and engaging',
            'pace': 'steady'
        }
    else:  # Michael - male
        voice_name = 'puck'
        config = {
            'traits': 'friendly and conversational', 
            'pace': 'natural'
        }
    
    return voice_name, config

def wave_file(filename, pcm, channels=1, rate=24000, sample_width=2):
    """Helper function to save PCM data as WAV file"""
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm)

def generate_speech_audio(text, speaker, emotion, output_path, retry_count=3, api_delay=2.0):
    """Generate speech audio using Gemini TTS API with emotion-aware voice selection
    
    Args:
        text: Text to convert to speech
        speaker: Speaker identifier
        emotion: Emotional context
        output_path: Where to save the audio
        retry_count: Number of retries on failure
        api_delay: Delay in seconds before making API request to avoid quota limits
    """
    
    voice_name, voice_config = get_voice_for_segment(speaker, emotion)
    
    for attempt in range(retry_count):
        try:
            # Add delay before API request to avoid hitting quota
            if api_delay > 0:
                print(f"⏱️  Waiting {api_delay}s before API request...")
                time.sleep(api_delay)
            
            print(f"🎤 Generating {emotion} audio with voice '{voice_name}'...")
            
            # Create client using correct API
            client = google_genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
            
            # Create emotion-aware prompt with FASTER PACING
            base_instruction = "Read at a brisk, energetic pace. "
            if emotion == 'mildly_excited':
                instruction = base_instruction + "With mild interest and engagement, not overly excited"
            elif emotion == 'thoughtful':
                instruction = base_instruction + "In a thoughtful manner but keep the pace moving"
            elif emotion == 'curious':
                instruction = base_instruction + "With genuine curiosity, maintain professional tone"
            elif emotion == 'acknowledging':
                instruction = "Say this very quickly as a natural acknowledgment"
            elif emotion == 'contrasting':
                instruction = base_instruction + "With slight emphasis on the contrast"
            elif emotion == 'agreeable':
                instruction = base_instruction + "With pleasant agreement, keep it quick"
            elif emotion == 'engaged':
                instruction = base_instruction + "With professional engagement and energy"
            else:
                instruction = base_instruction + f"In a {voice_config['traits']} voice"
            
            # Format prompt with natural speech instructions
            if "I'm Sarah" in text or "I'm Michael" in text:
                # Introduction - clear and welcoming
                prompt = f"Read this introduction clearly and warmly: {text}"
            else:
                prompt = f"{instruction}: {text}"
            
            # Generate content with proper voice configuration
            response = client.models.generate_content(
                model="gemini-2.5-pro-preview-tts",
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
                                # Normalize audio levels
                                audio = normalize(audio)
                                audio.export(output_path, format="mp3", bitrate="128k")
                                # Keep both files for now - WAV as backup
                                print(f"✅ Generated {emotion} audio with voice '{voice_name}'")
                            except Exception as e:
                                print(f"⚠️  Could not convert to MP3: {e}, keeping WAV")
                        else:
                            # Keep as WAV if MP3 conversion not available
                            final_path = output_path.replace('.mp3', '.wav')
                            if wav_path != final_path:
                                os.rename(wav_path, final_path)
                        
                        return True
            
            print(f"❌ No audio data found in response (attempt {attempt + 1}/{retry_count})")
            
        except Exception as e:
            print(f"❌ Attempt {attempt + 1} failed: {e}")
            if attempt < retry_count - 1:
                # Try with a fallback voice
                voices = VOICE_CONFIG['female_analytical']['voices'] if speaker == 'speaker0' else VOICE_CONFIG['male_enthusiastic']['voices']
                voice_name = voices[min(attempt + 1, len(voices) - 1)]
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                print(f"   Make sure GEMINI_API_KEY is set and Gemini TTS is enabled")
                
    return False

def create_podcast_audio(segments, output_dir="podcast_audio_segments", api_delay=2.0):
    """Create audio segments for the podcast with emotion-aware generation
    
    Args:
        segments: List of dialogue segments
        output_dir: Directory to save audio segments
        api_delay: Delay in seconds between API requests to avoid quota limits
    """
    os.makedirs(output_dir, exist_ok=True)
    
    audio_segments = []
    segment_count = 0
    
    for i, segment in enumerate(segments):
        if segment['type'] == 'dialogue':
            segment_count += 1
            emotion = segment.get('emotion', 'neutral')
            print(f"Generating segment {segment_count}/{len([s for s in segments if s['type'] == 'dialogue'])}: {segment['speaker']} ({emotion})")
            
            audio_file = os.path.join(output_dir, f"segment_{segment_count:03d}_{segment['speaker']}.mp3")
            
            # Generate speech with emotion context and API delay
            success = generate_speech_audio(
                segment['text'], 
                segment['speaker'],
                emotion,
                audio_file,
                api_delay=api_delay
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
                        try:
                            if actual_file.endswith('.wav'):
                                audio = AudioSegment.from_wav(actual_file)
                            elif actual_file.endswith('.mp3'):
                                audio = AudioSegment.from_mp3(actual_file)
                            else:
                                audio = AudioSegment.from_file(actual_file)
                            
                            # Add natural micro-pauses between segments - FASTER PACING
                            if i > 0:
                                prev_emotion = segments[i-1].get('emotion', 'neutral')
                                curr_emotion = segment.get('emotion', 'neutral')
                                
                                # Reduced pauses for faster pacing
                                if curr_emotion == 'acknowledging' or prev_emotion == 'acknowledging':
                                    pause_ms = random.randint(30, 60)  # Ultra short
                                elif curr_emotion in ['mildly_excited', 'curious'] and prev_emotion in ['mildly_excited', 'curious']:
                                    pause_ms = random.randint(50, 100)  # Very quick exchange
                                elif curr_emotion == 'thoughtful' or prev_emotion == 'thoughtful':
                                    pause_ms = random.randint(150, 250)  # Shorter thoughtful pause
                                else:
                                    pause_ms = random.randint(80, 150)  # Faster normal pace
                                
                                pause = AudioSegment.silent(duration=pause_ms)
                                audio_segments.append(pause)
                            
                            # Add subtle fade in/out for smoother transitions
                            if len(audio) > 100:
                                audio = audio.fade_in(50).fade_out(50)
                            
                            audio_segments.append(audio)
                            print(f"✅ Loaded audio segment {segment_count}")
                        except Exception as e:
                            print(f"❌ Failed to load audio file {actual_file}: {e}")
                            silent = AudioSegment.silent(duration=2000)
                            audio_segments.append(silent)
                    else:
                        print(f"⚠️  Audio file not found or empty: {actual_file}")
                        silent = AudioSegment.silent(duration=2000)
                        audio_segments.append(silent)
                        
                except Exception as e:
                    print(f"❌ Failed to process audio segment: {e}")
                    silent = AudioSegment.silent(duration=2000)
                    audio_segments.append(silent)
            else:
                print(f"❌ Failed to generate audio for segment {segment_count}")
                if AUDIO_AVAILABLE:
                    silent = AudioSegment.silent(duration=2000)
                    audio_segments.append(silent)
                else:
                    audio_segments.append(AudioSegment())
    
    return audio_segments

def combine_audio_segments(audio_segments, output_path):
    """Combine all audio segments into final podcast with audio normalization"""
    if not audio_segments:
        print("No audio segments to combine.")
        return False
    
    print("Combining audio segments...")
    
    # Add intro music placeholder (shorter for faster pacing)
    intro_music = AudioSegment.silent(duration=500)  # 0.5 seconds
    intro_music = intro_music.fade_in(300)  # Quick fade in
    final_audio = intro_music
    
    # Add all segments
    for segment in audio_segments:
        final_audio += segment
    
    # Add outro music placeholder (shorter)
    outro_music = AudioSegment.silent(duration=800)  # 0.8 seconds
    outro_music = outro_music.fade_out(500)  # Quick fade out
    final_audio += outro_music
    
    # Normalize the entire audio for consistent volume
    if AUDIO_AVAILABLE:
        try:
            final_audio = normalize(final_audio)
        except:
            print("⚠️  Could not normalize audio levels")
    
    # Export final podcast
    final_audio.export(output_path, format="mp3", bitrate="128k")
    print(f"Final podcast audio saved to: {output_path}")
    return True

def main():
    parser = argparse.ArgumentParser(description='Generate podcast audio from script using Gemini TTS v3')
    parser.add_argument('--script', type=str, required=True, help='Path to podcast script file')
    parser.add_argument('--output', type=str, default='podcast.mp3', help='Output audio file')
    parser.add_argument('--segments_dir', type=str, default='podcast_audio_segments', help='Directory for audio segments')
    parser.add_argument('--voice_style', type=str, default='default', choices=['default', 'varied', 'consistent'], help='Voice selection strategy')
    parser.add_argument('--api_delay', type=float, default=2.0, help='Delay in seconds between API requests to avoid quota limits (default: 2.0)')
    args = parser.parse_args()
    
    # Check for Gemini API key
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("Please set the GEMINI_API_KEY environment variable.")
        return
    
    # API key is used when creating client, no need to configure here
    
    # Parse script
    print(f"Parsing podcast script from {args.script}...")
    segments = parse_podcast_script(args.script)
    
    dialogue_segments = [s for s in segments if s['type'] == 'dialogue']
    print(f"Found {len(dialogue_segments)} dialogue segments to convert to audio.")
    
    # Show emotion analysis
    emotions = [s['emotion'] for s in dialogue_segments]
    print(f"Emotional tones detected: {', '.join(set(emotions))}")
    
    if not dialogue_segments:
        print("No dialogue segments found in script.")
        return
    
    # Generate audio segments with API delay
    print(f"\n🔧 API delay set to {args.api_delay} seconds between requests")
    audio_segments = create_podcast_audio(segments, args.segments_dir, api_delay=args.api_delay)
    
    # Combine into final podcast
    if audio_segments:
        combine_audio_segments(audio_segments, args.output)
        print("Podcast audio generation complete!")
    else:
        print("No audio segments were generated successfully.")

if __name__ == '__main__':
    main()