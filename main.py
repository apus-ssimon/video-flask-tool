# main.py - Main execution script for video generator
import sys
import os
import subprocess
import shutil
from pydub import AudioSegment

# Add scripts folder to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'scripts'))

from config import *
from audio_processor import process_all_audio, read_text_file
from video_generator import find_media_file, create_video_segment, get_video_info
from concat import concat_videos

def check_dependencies():
    """Check if required libraries are available"""
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageFilter
        import numpy as np
        print("Pillow and NumPy imported successfully")
    except ImportError as e:
        print(f"Pillow/NumPy import failed: {e}")
        print("Please install: pip3 install pillow numpy")
        return False
    
    try:
        from hume.client import HumeClient
        print("Hume library imported successfully")
    except ImportError as e:
        print(f"Hume library import failed: {e}")
    
    return True

def load_voices():
    """Load available voices from voices.txt file"""
    voices = {}
    voices_file = "voices.txt"
    
    if not os.path.exists(voices_file):
        print(f"Warning: {voices_file} not found. Using default voice.")
        return voices
    
    try:
        with open(voices_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and ':' in line:
                    name, voice_id = line.split(':', 1)
                    voices[name.strip()] = voice_id.strip()
        print(f"Loaded {len(voices)} voices from {voices_file}")
    except Exception as e:
        print(f"Error reading {voices_file}: {e}")
    
    return voices

def get_user_choices():
    """Get video orientation and TTS provider choices from user"""
    # Video orientation selection
    print("Video Orientation Setup")
    print("Choose your video orientation:")
    print("1. Vertical (9:16) - Perfect for TikTok, Instagram Stories, YouTube Shorts")
    print("2. Horizontal (16:9) - Perfect for YouTube, standard video platforms")

    while True:
        choice = input("\nEnter your choice (1 or 2): ").strip()
        if choice == "1":
            orientation = "vertical"
            print(f"Selected: VERTICAL orientation (1080x1920)")
            break
        elif choice == "2":
            orientation = "horizontal"
            print(f"Selected: HORIZONTAL orientation (1920x1080)")
            break
        else:
            print("Invalid choice. Please enter 1 or 2.")

    print()

    # TTS provider selection
    print("TTS Provider Setup")
    print("Choose your text-to-speech provider:")
    print("1. Hume AI - Advanced emotional voice synthesis")
    print("2. ElevenLabs - High-quality voice cloning and synthesis")

    selected_voice = None  # Default for Hume AI
    
    while True:
        tts_choice = input("\nEnter your choice (1 or 2): ").strip()
        if tts_choice == "1":
            tts_provider = "hume"
            print("Selected: Hume AI")
            break
        elif tts_choice == "2":
            tts_provider = "elevenlabs"
            print("Selected: ElevenLabs")
            
            # Voice selection for ElevenLabs
            voices = load_voices()
            if voices:
                print("\nAvailable Voices:")
                voice_names = list(voices.keys())
                for i, name in enumerate(voice_names, 1):
                    print(f"{i}. {name}")
                
                while True:
                    try:
                        voice_choice = input(f"\nChoose a voice (1-{len(voice_names)}): ").strip()
                        voice_index = int(voice_choice) - 1
                        
                        if 0 <= voice_index < len(voice_names):
                            selected_voice_name = voice_names[voice_index]
                            selected_voice = voices[selected_voice_name]
                            print(f"Selected voice: {selected_voice_name} ({selected_voice})")
                            break
                        else:
                            print(f"Invalid choice. Please enter a number between 1 and {len(voice_names)}.")
                    except ValueError:
                        print("Invalid input. Please enter a number.")
            else:
                print("No voices file found, using default voice.")
            break
        else:
            print("Invalid choice. Please enter 1 or 2.")

    print()

    # Text display option
    print("Text Display Setup")
    show_text = input("Show text overlay on videos? (y/n): ").strip().lower() == 'y'
    if show_text:
        print("Selected: Text overlays will be displayed on videos")
    else:
        print("Selected: No text overlays (audio only)")
    print()

    # Optional course text
    course_text = ""
    add_text = input("Add course text in bottom right? (y/n): ").strip().lower()
    if add_text == "y":
        course_text = input("Enter the course text to display: ").strip()
    print()

    return orientation, tts_provider, course_text, selected_voice, show_text

def create_video_segments(text_lines, orientation_config, tts_provider, course_text, show_text=True):
    """Create video segments from media files and audio"""
    print("Creating video segments with mixed media support...")
    if not show_text:
        print("   Text overlays disabled - creating video with audio only")
    if course_text:
        print(f"   Course text will be displayed: '{course_text}'")
    
    video_files = []

    for i in range(1, len(text_lines) + 1):
        audio_path = os.path.join(TEMP_AUDIO_DIR, f"{i}.mp3")
        media_path, is_video = find_media_file(i)
        
        text_line = text_lines[i - 1] if i <= len(text_lines) else ""

        if is_video and text_line.strip() == '-skip-':
            print(f"   Processing segment {i}: video (skip) - {os.path.basename(media_path)}")
        else:
            if not os.path.exists(audio_path):
                print(f"Warning: {audio_path} not found, skipping segment {i}")
                continue

        if not media_path:
            print(f"Warning: No media file found for segment {i}, skipping")
            continue

        media_type = "video" if is_video else "image"
        if not (is_video and text_line.strip() == '-skip-'):
            text_status = " (no main text)" if not show_text else ""
            course_status = f" (course text: '{course_text}')" if course_text and i == 1 else ""
            print(f"   Processing segment {i}: {media_type} - {os.path.basename(media_path)}{text_status}{course_status}")

        if text_line.strip() == '-skip-':
            text_line = ""

        # Course text overlay - ALWAYS show if provided (independent of show_text setting)
        overlay_text = course_text if i == 1 and course_text else None

        # Main text overlay - only show if show_text is True
        display_text = text_line if show_text else ""

        video_file = create_video_segment(
            media_path,
            audio_path,
            display_text,  # Main text (empty if disabled)
            i,
            len(text_lines),
            is_video,
            orientation_config,
            tts_provider,
            overlay_text=overlay_text  # Course text (always shows if provided)
        )

        if video_file:
            video_files.append(video_file)

    return video_files

def calculate_total_duration(text_lines, tts_provider):
    """Calculate total video duration for background music handling"""
    print("Calculating total video duration...")
    total_duration = 0
    
    for i in range(1, len(text_lines) + 1):
        audio_path = os.path.join(TEMP_AUDIO_DIR, f"{i}.mp3")
        media_path, is_video = find_media_file(i)
        text_line = text_lines[i - 1] if i <= len(text_lines) else ""

        if is_video:
            try:
                video_duration, _, _ = get_video_info(media_path)
                segment_duration = video_duration
                print(f"   Segment {i} (video): {segment_duration:.2f}s")
            except Exception as e:
                print(f"   Could not get video duration for segment {i}: {e}")
                segment_duration = 4
        else:
            if os.path.exists(audio_path):
                original = AudioSegment.from_file(audio_path)
                silence = AudioSegment.silent(duration=1000)
                padded_audio = original + silence
                segment_duration = padded_audio.duration_seconds / TTS_SPEED_SETTINGS[tts_provider]
                print(f"   Segment {i} (image): {segment_duration:.2f}s")
            else:
                segment_duration = 4
                print(f"   Segment {i} (image, no audio): {segment_duration:.2f}s")

        total_duration += segment_duration

    print(f"   Total video duration: {total_duration:.2f} seconds")
    return total_duration

def cleanup_temp_files():
    """Clean up temporary files and directories"""
    print("Cleaning up temporary files...")
    for temp_dir in TEMP_DIRS:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"   Removed {temp_dir} directory")

def print_final_summary(orientation, total_duration):
    """Print final video creation summary"""
    orientation_config = ORIENTATION_OPTIONS[orientation]
    width, height = orientation_config["width"], orientation_config["height"]

    print(f"Video created: {OUTPUT_VIDEO}")
    print(f"Features: Mixed media support (images + videos), smooth zoom ({ZOOM_TYPE}), fade in/out ({FADE_DURATION}s), vignette effect")
    print(f"Orientation: {orientation.upper()} ({width}x{height})")
    print(f"Duration: {total_duration:.2f} seconds")
    print("Supported formats:")
    print(f"   Images: {', '.join(IMAGE_EXTENSIONS)}")
    print(f"   Videos: {', '.join(VIDEO_EXTENSIONS)}")

def find_background_music():
    """Find available background music file (m4a or mp3)"""
    music_files = ["song.m4a", "song.mp3"]
    for music_file in music_files:
        if os.path.exists(music_file):
            print(f"Found background music: {music_file}")
            return music_file
    print("Warning: No background music file found (song.m4a or song.mp3)")
    return None

def main():
    """Main execution function"""
    if not check_dependencies():
        exit(1)

    orientation, tts_provider, course_text, selected_voice, show_text = get_user_choices()
    orientation_config = ORIENTATION_OPTIONS[orientation]

    text_lines = read_text_file()
    if not text_lines:
        print("No text lines found. Cannot create video.")
        exit(1)

    # Pass selected_voice to process_all_audio
    process_all_audio(text_lines, tts_provider, selected_voice)

    # Pass show_text to video segment creation
    video_files = create_video_segments(text_lines, orientation_config, tts_provider, course_text, show_text)
    
    if not video_files:
        print("No video segments created. Please check your audio and media files.")
        exit(1)

    total_duration = calculate_total_duration(text_lines, tts_provider)

    background_music = find_background_music()
    concat_videos(
        video_dir="temp_video",
        output_path=os.path.join(os.getcwd(), "final_output.mp4"),
        background_music=background_music
    )

    cleanup_temp_files()
    print_final_summary(orientation, total_duration)

if __name__ == "__main__":
    main()
