import os
import argparse
from moviepy.editor import *
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from pydub import AudioSegment
import json

def create_simple_background(width=1920, height=1080, color=(45, 55, 70)):
    """Create a simple gradient background"""
    img = Image.new('RGB', (width, height), color)
    draw = ImageDraw.Draw(img)
    
    # Add subtle gradient effect
    for y in range(height):
        shade = int(color[0] + (20 * y / height))
        shade = min(255, max(0, shade))
        draw.line([(0, y), (width, y)], fill=(shade, shade + 10, shade + 25))
    
    return np.array(img)

def create_speaker_indicator(width=1920, height=1080, speaker_name="SARAH", active=True):
    """Create visual indicator for active speaker"""
    img = Image.new('RGB', (width, height), (45, 55, 70))
    draw = ImageDraw.Draw(img)
    
    # Try to load a font, fall back to default if not available
    try:
        font_large = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 60)
        font_small = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 40)
    except:
        try:
            font_large = ImageFont.truetype("arial.ttf", 60)
            font_small = ImageFont.truetype("arial.ttf", 40)
        except:
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()
    
    # Colors for active/inactive states
    if active:
        text_color = (255, 255, 255)
        accent_color = (0, 150, 255)
        circle_color = (0, 200, 100)
    else:
        text_color = (150, 150, 150)
        accent_color = (100, 120, 140)
        circle_color = (80, 90, 100)
    
    # Draw microphone icon (simple circle)
    center_x, center_y = width // 2, height // 2 - 100
    draw.ellipse([center_x - 50, center_y - 50, center_x + 50, center_y + 50], 
                 fill=circle_color, outline=accent_color, width=5)
    
    # Draw speaker name
    bbox = draw.textbbox((0, 0), speaker_name, font=font_large)
    text_width = bbox[2] - bbox[0]
    text_x = (width - text_width) // 2
    draw.text((text_x, center_y + 80), speaker_name, fill=text_color, font=font_large)
    
    # Draw "SPEAKING" indicator if active
    if active:
        speaking_text = "SPEAKING"
        bbox = draw.textbbox((0, 0), speaking_text, font=font_small)
        speaking_width = bbox[2] - bbox[0]
        speaking_x = (width - speaking_width) // 2
        draw.text((speaking_x, center_y + 160), speaking_text, fill=accent_color, font=font_small)
        
        # Add pulsing effect with small dots
        for i in range(3):
            x = center_x - 30 + (i * 30)
            y = center_y + 200
            draw.ellipse([x - 5, y - 5, x + 5, y + 5], fill=accent_color)
    
    return np.array(img)

def create_title_slide(width=1920, height=1080, title="AI Podcast"):
    """Create opening title slide"""
    img = Image.new('RGB', (width, height), (30, 40, 60))
    draw = ImageDraw.Draw(img)
    
    try:
        font_title = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 80)
        font_subtitle = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 40)
    except:
        try:
            font_title = ImageFont.truetype("arial.ttf", 80)
            font_subtitle = ImageFont.truetype("arial.ttf", 40)
        except:
            font_title = ImageFont.load_default()
            font_subtitle = ImageFont.load_default()
    
    # Title
    bbox = draw.textbbox((0, 0), title, font=font_title)
    title_width = bbox[2] - bbox[0]
    title_x = (width - title_width) // 2
    draw.text((title_x, height // 2 - 100), title, fill=(255, 255, 255), font=font_title)
    
    # Subtitle
    subtitle = "Generated from Email Newsletter Analysis"
    bbox = draw.textbbox((0, 0), subtitle, font=font_subtitle)
    subtitle_width = bbox[2] - bbox[0]
    subtitle_x = (width - subtitle_width) // 2
    draw.text((subtitle_x, height // 2 + 20), subtitle, fill=(150, 200, 255), font=font_subtitle)
    
    return np.array(img)

def parse_script_for_timing(script_path):
    """Parse script to determine speaker timing"""
    with open(script_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    segments = []
    lines = content.split('\n')
    
    for line in lines:
        line = line.strip()
        
        # Handle multiple speaker formats for better compatibility
        if line.startswith('[SARAH]:') or line.startswith('[Speaker 0]'):
            text = line.replace('[SARAH]:', '').replace('[Speaker 0]', '').strip()
            segments.append({
                'speaker': 'SARAH',
                'text': text,
                'estimated_duration': len(text) * 0.05  # rough estimate
            })
        elif line.startswith('[MICHAEL]:') or line.startswith('[Speaker 1]'):
            text = line.replace('[MICHAEL]:', '').replace('[Speaker 1]', '').strip()
            segments.append({
                'speaker': 'MICHAEL', 
                'text': text,
                'estimated_duration': len(text) * 0.05
            })
        elif line.startswith('[PAUSE]'):
            segments.append({
                'speaker': 'PAUSE',
                'estimated_duration': 1.0
            })
    
    return segments

def create_podcast_video(audio_path, script_path, output_path):
    """Create podcast video with audio and simple visuals"""
    print("Loading audio file...")
    
    # Load audio
    try:
        audio_clip = AudioFileClip(audio_path)
        audio_duration = audio_clip.duration
        print(f"Audio duration: {audio_duration:.2f} seconds")
    except Exception as e:
        print(f"Error loading audio: {e}")
        return False
    
    # Parse script for timing
    print("Parsing script for speaker timing...")
    segments = parse_script_for_timing(script_path)
    
    # Create visual clips
    clips = []
    current_time = 0
    
    # Title slide (5 seconds)
    print("Creating title slide...")
    title_frame = create_title_slide()
    title_clip = ImageClip(title_frame, duration=5)
    clips.append(title_clip.set_start(0))
    current_time = 5
    
    # Create speaker clips based on script timing
    print("Creating speaker visual segments...")
    for i, segment in enumerate(segments):
        if segment['speaker'] in ['SARAH', 'MICHAEL']:
            duration = max(2.0, segment['estimated_duration'])  # Minimum 2 seconds per segment
            
            # Create active speaker visual
            active_frame = create_speaker_indicator(speaker_name=segment['speaker'], active=True)
            speaker_clip = ImageClip(active_frame, duration=duration)
            clips.append(speaker_clip.set_start(current_time))
            
            current_time += duration
            
        elif segment['speaker'] == 'PAUSE':
            # Show neutral background during pauses
            bg_frame = create_simple_background()
            pause_clip = ImageClip(bg_frame, duration=segment['estimated_duration'])
            clips.append(pause_clip.set_start(current_time))
            
            current_time += segment['estimated_duration']
    
    # If video is shorter than audio, extend with final background
    if current_time < audio_duration:
        remaining_duration = audio_duration - current_time
        final_frame = create_simple_background()
        final_clip = ImageClip(final_frame, duration=remaining_duration)
        clips.append(final_clip.set_start(current_time))
    
    print(f"Creating composite video with {len(clips)} visual segments...")
    
    # Composite all clips
    video = CompositeVideoClip(clips, size=(1920, 1080))
    
    # Set the audio
    final_video = video.set_audio(audio_clip)
    
    # Write the video file
    print(f"Rendering video to {output_path}...")
    final_video.write_videofile(
        output_path,
        fps=24,
        codec='libx264',
        audio_codec='aac',
        temp_audiofile='temp-audio.m4a',
        remove_temp=True
    )
    
    # Clean up
    audio_clip.close()
    video.close()
    final_video.close()
    
    print("Video generation complete!")
    return True

def main():
    parser = argparse.ArgumentParser(description='Generate podcast video from audio and script')
    parser.add_argument('--audio', type=str, required=True, help='Path to podcast audio file')
    parser.add_argument('--script', type=str, required=True, help='Path to podcast script file')
    parser.add_argument('--output', type=str, default='podcast_video.mp4', help='Output video file')
    args = parser.parse_args()
    
    # Check if input files exist
    if not os.path.exists(args.audio):
        print(f"Audio file not found: {args.audio}")
        return
    
    if not os.path.exists(args.script):
        print(f"Script file not found: {args.script}")
        return
    
    # Generate video
    success = create_podcast_video(args.audio, args.script, args.output)
    
    if success:
        print(f"Podcast video saved to: {args.output}")
    else:
        print("Failed to generate podcast video.")

if __name__ == '__main__':
    main()