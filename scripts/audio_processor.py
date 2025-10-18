# audio_processor.py - Audio generation and processing logic
import os
import time
from tts_providers import generate_elevenlabs_audio, generate_hume_audio, generate_silence_file, generate_fallback_silence, get_tts_function
from config import *

def generate_all_audio(text_lines, tts_provider, selected_voice=None):
   """Generate audio files for all text lines using the specified TTS provider"""
   if not GENERATE_AUDIO or not text_lines:
       return
   
   # Display provider selection
   if tts_provider == "hume":
       print("🎤 Generating audio files with Hume AI...")
   else:
       voice_info = f" (Voice: {selected_voice})" if selected_voice else ""
       print(f"🎤 Generating audio files with ElevenLabs{voice_info}...")
   
   tts_function = get_tts_function(tts_provider)
   
   for i, text in enumerate(text_lines, 1):
       if text.strip() == '-skip-':
           # Check if this is a video file
           from video_generator import find_media_file
           media_path, is_video = find_media_file(i)
           if is_video:
               print(f"   Skipping audio generation for video {i} with '-skip-' marker")
               continue  # Skip audio generation for video + skip
           else:
               continue  # Handle in generate_skip_audio for images
               
       audio_file = os.path.join(TEMP_AUDIO_DIR, f"{i}.mp3")
       
       # Skip if audio file already exists
       if os.path.exists(audio_file):
           print(f"   Audio {i}.mp3 already exists, skipping...")
           continue
           
       print(f"   Generating audio {i}.mp3: '{text[:50]}...'")
       
       # Generate audio using selected provider
       if tts_provider == "elevenlabs" and selected_voice:
           # Pass the selected voice to ElevenLabs
           success = tts_function(text, audio_file, voice_id=selected_voice)
       else:
           # For Hume AI or ElevenLabs without voice selection
           success = tts_function(text, audio_file)
       
       if success:
            # Boost volume by 6dB
            from pydub import AudioSegment
            audio = AudioSegment.from_file(audio_file)
            louder_audio = audio + 6
            louder_audio.export(audio_file, format="mp3")
            print(f"   ✅ Generated {audio_file} with {tts_provider.title()} (volume boosted)")
       else:
           # Fallback to silence if generation failed
           generate_fallback_silence(audio_file)
           print(f"   📝 Created fallback silence for {audio_file}")
       
       # Rate limiting
       time.sleep(0.7)

def generate_skip_audio(text_lines):
    """Generate silence files for '-skip-' lines"""
    print("🔇 Generating silence files for skipped lines...")
    
    for i, text in enumerate(text_lines, 1):
        if text.strip() == '-skip-':
            silence_file = os.path.join(TEMP_AUDIO_DIR, f"{i}.mp3")
            
            # Skip if silence file already exists
            if os.path.exists(silence_file):
                print(f"   Silence {i}.mp3 already exists, skipping...")
                continue
            
            # Check if there's a corresponding video file for this segment
            from video_generator import find_media_file, get_video_info
            media_path, is_video = find_media_file(i)
            
            if is_video and media_path:
                try:
                    # Get video duration and use that for silence length
                    video_duration, _, _ = get_video_info(media_path)
                    silence_duration = video_duration
                    print(f"   Generating silence {i}.mp3 for skip marker (matching video duration: {video_duration:.2f}s)")
                except Exception as e:
                    print(f"   Could not get video duration for {media_path}: {e}")
                    silence_duration = 4  # Fallback to 4 seconds
                    print(f"   Generating silence {i}.mp3 for skip marker (fallback: {silence_duration}s)")
            else:
                silence_duration = 4  # Default 4 seconds for image or no media
                print(f"   Generating silence {i}.mp3 for skip marker (default: {silence_duration}s)")
            
            success = generate_silence_file(silence_file, duration=silence_duration)
            
            if success:
                print(f"   ✅ Generated {silence_file}")
            else:
                print(f"   📝 Created fallback silence for {silence_file}")

def setup_audio_environment():
   """Set up audio processing environment"""
   from pydub.utils import which
   from pydub import AudioSegment
   
   # Ensure pydub can find ffmpeg
   AudioSegment.converter = which("ffmpeg")
   
   # Create temp directories
   for temp_dir in TEMP_DIRS:
       os.makedirs(temp_dir, exist_ok=True)

def read_text_file():
   """Read and parse the text file"""
   text_lines = []
   if os.path.exists(TEXT_FILE):
       with open(TEXT_FILE, 'r', encoding='utf-8') as f:
           text_lines = [line.strip() for line in f.readlines() if line.strip()]
   else:
       print(f"⚠️  Warning: {TEXT_FILE} not found. Videos will be created without text overlay.")
   
   return text_lines

def process_all_audio(text_lines, tts_provider, selected_voice=None):
   """Main function to process all audio generation"""
   setup_audio_environment()
   generate_all_audio(text_lines, tts_provider, selected_voice)
   generate_skip_audio(text_lines)