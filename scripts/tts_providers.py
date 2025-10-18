# tts_providers.py - Text-to-speech provider implementations
import os
import subprocess
import time
import httpx
from pydub import AudioSegment
from config import *

def generate_elevenlabs_audio(text, output_file, voice_id=None):
   """Generate audio using ElevenLabs API"""
   try:
       # Use provided voice_id or fall back to config default
       selected_voice_id = voice_id if voice_id else ELEVENLABS_VOICE_ID
       
       headers = {
           "Accept": "audio/mpeg", 
           "Content-Type": "application/json",
           "xi-api-key": ELEVENLABS_API_KEY
       }
       
       data = {
           "text": text,
           "model_id": "eleven_monolingual_v1", 
           "voice_settings": {
               "stability": 0.5,
               "similarity_boost": 0.5
           }
       }
       
       response = httpx.post(
           f"https://api.elevenlabs.io/v1/text-to-speech/{selected_voice_id}",
           json=data,
           headers=headers,
           timeout=30.0
       )
       
       if response.status_code == 200:
           with open(output_file, 'wb') as f:
               f.write(response.content)
           return True
       else:
           print(f"   ❌ ElevenLabs API Error: {response.status_code}")
           return False
           
   except Exception as e:
       print(f"   ❌ ElevenLabs error: {e}")
       return False

def generate_hume_audio(text, output_file):
   """Generate audio using Hume AI API"""
   try:
       headers = {
           "X-Hume-Api-Key": HUME_API_KEY,
           "Content-Type": "application/json"
       }
       
       # Build payload based on available voice options
       if HUME_VOICE_ID:
           payload = {
               "utterances": [
                   {
                       "text": text,
                       "voice": {
                           "id": HUME_VOICE_ID,
                           "provider": HUME_VOICE_PROVIDER
                       }
                   }
               ],
               "format": {"type": "mp3"},
               "num_generations": 1
           }
       elif HUME_VOICE_NAME:
           payload = {
               "utterances": [
                   {
                       "text": text,
                       "voice": {"name": HUME_VOICE_NAME}
                   }
               ],
               "format": {"type": "mp3"},
               "num_generations": 1
           }
       else:
           payload = {
               "utterances": [
                   {
                       "text": text,
                       "description": VOICE_DESCRIPTION
                   }
               ],
               "format": {"type": "mp3"},
               "num_generations": 1
           }
       
       response = httpx.post(
           "https://api.hume.ai/v0/tts/file",
           headers=headers,
           json=payload,
           timeout=30.0
       )
       
       if response.status_code == 200:
           with open(output_file, 'wb') as f:
               f.write(response.content)
           return True
       elif response.status_code == 422:
           print(f"   ❌ Validation error - check text length and voice parameters")
           print(f"   Response: {response.text}")
           return False
       elif response.status_code == 429:
           print(f"   ❌ Rate limit exceeded - waiting longer...")
           time.sleep(5)
           return False
       else:
           print(f"   ❌ Hume API Error: {response.status_code}")
           print(f"   Response: {response.text}")
           return False
           
   except Exception as e:
       print(f"   ❌ Hume error: {e}")
       return False

def generate_silence_file(output_file, duration=4):
    """Generate a silence audio file"""
    try:
        # Generate silence using ffmpeg (accepts float duration)
        silence_cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-t", str(duration), 
            "-i", "anullsrc=r=44100:cl=stereo",
            "-q:a", "9", "-acodec", "libmp3lame",
            output_file
        ]
        subprocess.run(silence_cmd, check=True, capture_output=True)
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"   ❌ Error generating silence: {e}")
        # Fallback: create with pydub
        try:
            silence = AudioSegment.silent(duration=int(duration * 1000))  # Convert to milliseconds
            silence.export(output_file, format="mp3")
            return True
        except Exception as fallback_e:
            print(f"   ❌ Fallback silence generation failed: {fallback_e}")
            return False

def generate_fallback_silence(output_file, duration=3):
   """Generate fallback silence when TTS fails"""
   try:
       silence = AudioSegment.silent(duration=duration * 1000)  # Convert to milliseconds
       silence.export(output_file, format="mp3")
       return True
   except Exception as e:
       print(f"   ❌ Fallback silence creation failed: {e}")
       return False

def get_tts_function(provider):
   """Return the appropriate TTS function based on provider"""
   if provider == "elevenlabs":
       return generate_elevenlabs_audio
   elif provider == "hume":
       return generate_hume_audio
   else:
       raise ValueError(f"Unknown TTS provider: {provider}")