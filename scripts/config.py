# config.py - Configuration file for video generator

# API Credentials
HUME_API_KEY = "dB852RAl2Aaxp70PZYVtsSFNpApNb4aZQoOImz32QFB8NUvA"
HUME_SECRET_KEY = "eA9nrnUElJ1BTIuIe1hvK7Gh81Hh0Cy9kvLGyh31QcGfEjGG9gHh1jHE38lfMQuq"
ELEVENLABS_API_KEY = "sk_4f9b1de6fe5f98a3e3d6ddfb8009e4e9ad81037e4c11dbcb"

# File paths and directories
TEMP_AUDIO_DIR = "temp_audio"
MEDIA_DIR = "images"
OUTPUT_VIDEO = "output.mp4"
TEXT_FILE = "text.txt"

# Audio settings
MUSIC_VOLUME = 0.2  # Background music volume (0.1 = quiet, 0.5 = loud)
MUSIC_FADEOUT = 2.0  # Background music fade-out duration in seconds
# TTS provider-specific speed settings
TTS_SPEED_SETTINGS = {
    "hume": 1.3,
    "elevenlabs": 1.0  # No speed adjustment for ElevenLabs
}
VIDEO_SPEED = 1.3  # Used for video effects only
GENERATE_AUDIO = True

# Video orientation options (set dynamically)
ORIENTATION_OPTIONS = {
   "vertical": {
       "width": 1080,
       "height": 1920,
       "text_y_position": 400,
       "text_size": 48,
       "text_wrap_width": 30
   },
   "horizontal": {
       "width": 1920,
       "height": 1080,
       "text_y_position": 130,
       "text_size": 56,
       "text_wrap_width": 40
   }
}

# Text and visual effects settings
TEXT_OPACITY = 0.5  # Background box opacity (0.0 = transparent, 1.0 = solid)
TEXT_LINE_SPACING = 18  # Spacing between lines in pixels
VIGNETTE_STRENGTH = 0.5  # Vignette strength (0.1 = subtle, 0.5 = strong, 0.8 = dramatic)
ZOOM_SPEED = 0.15  # Zoom amount (0.05 = subtle, 0.15 = moderate, 0.3 = dramatic)
ZOOM_TYPE = "ease-out"  # Options: "linear", "ease-in", "ease-out", "ease-in-out"
FADE_DURATION = 0.5  # Fade in/out duration in seconds

# Voice configuration
ELEVENLABS_VOICE_ID = "kPzsL2i3teMYv0FxEYQ6"
HUME_VOICE_ID = "d8ab67c6-953d-4bd8-9370-8fa53a0f1453"
HUME_VOICE_PROVIDER = "HUME_AI"
HUME_VOICE_NAME = "Colton Rivers"
VOICE_DESCRIPTION = "Previously Charming Cowboy. A grizzled old cowboy with a folksy Texan drawl Southern accent, speaking in a charismatic tone with a deep but relaxed vibe."

# Media file extensions
IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp']
VIDEO_EXTENSIONS = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.m4v']
MUSIC_EXTENSIONS = ['.m4a', '.mp3', '.wav', '.aac']

# Video processing settings
FPS = 25
VIDEO_CRF = 18  # Video quality (lower = higher quality)
FALLBACK_CRF = 23  # Fallback video quality

# Temporary directories
TEMP_DIRS = ["temp_audio", "temp_video", "temp_frames"]