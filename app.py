# app.py - Flask application for video generator
import os
import sys
import shutil
import uuid
from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify
from werkzeug.utils import secure_filename
import threading
from pydub import AudioSegment

# Add scripts folder to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'scripts'))

import config
from audio_processor import process_all_audio
from video_generator import find_media_file, create_video_segment, get_video_info
from concat import concat_videos

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'outputs'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size
app.secret_key = 'your-secret-key-here-change-this'  # Change this!

# Allowed file extensions
ALLOWED_TEXT_EXTENSIONS = {'txt'}
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'mov', 'avi', 'mkv'}
ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'm4a'}

# Store job status in memory (for simple implementation)
# In production, use Redis or a database
job_status = {}

def allowed_file(filename, allowed_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def load_voices():
    """Load available voices from voices.txt file"""
    voices = {}
    voices_file = "voices.txt"
    
    if not os.path.exists(voices_file):
        return voices
    
    try:
        with open(voices_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and ':' in line:
                    name, voice_id = line.split(':', 1)
                    voices[name.strip()] = voice_id.strip()
    except Exception as e:
        print(f"Error reading {voices_file}: {e}")
    
    return voices

@app.route('/')
def index():
    """Home page with upload form"""
    # Clean up old output files (optional: only delete files older than 1 hour)
    cleanup_old_outputs()
    voices = load_voices()
    return render_template('index.html', voices=voices)

def cleanup_old_outputs(max_age_hours=1):
    """Delete old output files to save space"""
    try:
        import time
        output_folder = app.config['OUTPUT_FOLDER']
        
        if not os.path.exists(output_folder):
            return
        
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        for filename in os.listdir(output_folder):
            if filename.endswith('.mp4'):
                filepath = os.path.join(output_folder, filename)
                file_age = current_time - os.path.getmtime(filepath)
                
                # Delete files older than max_age_hours
                if file_age > max_age_seconds:
                    os.remove(filepath)
                    print(f"Cleaned up old file: {filename}")
    except Exception as e:
        print(f"Error during cleanup: {e}")

@app.route('/upload', methods=['POST'])
def upload_files():
    """Handle file uploads and start video generation"""
    try:
        # Generate unique job ID
        job_id = str(uuid.uuid4())
        job_folder = os.path.join(app.config['UPLOAD_FOLDER'], job_id)
        os.makedirs(job_folder, exist_ok=True)
        
        # Get form data
        orientation = request.form.get('orientation', 'vertical')
        tts_provider = request.form.get('tts_provider', 'hume')
        selected_voice = request.form.get('voice', None)
        show_text = request.form.get('show_text') == 'on'
        include_video_audio = request.form.get('include_video_audio') == 'on'
        course_text = request.form.get('course_text', '').strip()
        
        # Handle text file upload
        if 'text_file' not in request.files:
            return "No text file provided", 400
        
        text_file = request.files['text_file']
        if text_file.filename == '':
            return "No text file selected", 400
        
        if not allowed_file(text_file.filename, ALLOWED_TEXT_EXTENSIONS):
            return "Invalid text file format", 400
        
        text_path = os.path.join(job_folder, 'text.txt')
        text_file.save(text_path)
        
        # Handle media files (images and videos)
        media_files = request.files.getlist('media_files')
        media_folder = os.path.join(job_folder, 'images')
        os.makedirs(media_folder, exist_ok=True)
        
        for i, media_file in enumerate(media_files, 1):
            if media_file.filename:
                filename = secure_filename(media_file.filename)
                ext = filename.rsplit('.', 1)[1].lower()
                # Save with numbered filename (1.jpg, 2.mp4, etc.)
                new_filename = f"{i}.{ext}"
                media_file.save(os.path.join(media_folder, new_filename))
        
        # Handle optional background music
        music_path = None
        if 'background_music' in request.files:
            music_file = request.files['background_music']
            if music_file.filename and allowed_file(music_file.filename, ALLOWED_AUDIO_EXTENSIONS):
                ext = music_file.filename.rsplit('.', 1)[1].lower()
                music_path = os.path.join(job_folder, f'song.{ext}')
                music_file.save(music_path)
        
        # Initialize job status
        job_status[job_id] = {
            'status': 'queued',
            'progress': 0,
            'message': 'Job queued...'
        }
        
        # Start video generation in background thread
        thread = threading.Thread(
            target=generate_video_background,
            args=(job_id, job_folder, text_path, media_folder, orientation, 
                  tts_provider, selected_voice, show_text, course_text, music_path, include_video_audio)
        )
        thread.daemon = True
        thread.start()
        
        return redirect(url_for('processing', job_id=job_id))
    
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/processing/<job_id>')
def processing(job_id):
    """Show processing status page"""
    return render_template('processing.html', job_id=job_id)

@app.route('/status/<job_id>')
def get_status(job_id):
    """API endpoint to check job status"""
    if job_id not in job_status:
        return jsonify({'status': 'not_found'}), 404
    
    return jsonify(job_status[job_id])

@app.route('/download/<job_id>')
def download(job_id):
    """Download the generated video"""
    output_path = os.path.join(app.config['OUTPUT_FOLDER'], f"{job_id}.mp4")
    
    if not os.path.exists(output_path):
        return "Video not found", 404
    
    return send_file(output_path, as_attachment=True, download_name='generated_video.mp4')

@app.route('/outputs/<job_id>.mp4')
def serve_video(job_id):
    """Serve video file for preview"""
    output_path = os.path.join(app.config['OUTPUT_FOLDER'], f"{job_id}.mp4")
    
    if not os.path.exists(output_path):
        return "Video not found", 404
    
    return send_file(output_path, mimetype='video/mp4')

def generate_video_background(job_id, job_folder, text_path, media_folder, 
                              orientation, tts_provider, selected_voice, 
                              show_text, course_text, music_path, include_video_audio):
    """Background task for video generation"""
    # Change to job directory so all relative paths work
    original_cwd = os.getcwd()
    
    try:
        os.chdir(job_folder)
        
        job_status[job_id]['status'] = 'processing'
        job_status[job_id]['message'] = 'Reading text file...'
        job_status[job_id]['progress'] = 10
        
        # Read text file
        with open('text.txt', 'r', encoding='utf-8') as f:
            text_lines = [line.strip() for line in f if line.strip()]
        
        if not text_lines:
            job_status[job_id]['status'] = 'error'
            job_status[job_id]['message'] = 'No text lines found'
            return
        
        # Create temporary directories
        os.makedirs('temp_audio', exist_ok=True)
        os.makedirs('temp_video', exist_ok=True)
        os.makedirs('temp_frames', exist_ok=True)
        
        job_status[job_id]['message'] = 'Processing audio...'
        job_status[job_id]['progress'] = 20
        
        # Process audio
        process_all_audio(text_lines, tts_provider, selected_voice)
        
        job_status[job_id]['message'] = 'Creating video segments...'
        job_status[job_id]['progress'] = 40
        
        # Get orientation config
        orientation_config = config.ORIENTATION_OPTIONS[orientation]
        
        # Create video segments
        video_files = []
        for i in range(1, len(text_lines) + 1):
            audio_path = os.path.join('temp_audio', f"{i}.mp3")
            media_path, is_video = find_media_file(i)
            
            if not media_path:
                continue
            
            # Keep original text line for skip detection
            original_text_line = text_lines[i - 1] if i <= len(text_lines) else ""
            is_skip = original_text_line.strip() == '-skip-'
            
            overlay_text = course_text if i == 1 and course_text else None
            
            # Determine display text: empty for skip or when show_text is off
            if is_skip or not show_text:
                display_text = ""
            else:
                display_text = original_text_line
            
            # For skip videos, pass '-skip-' so video_generator can detect it
            text_to_pass = '-skip-' if is_skip else display_text
            
            video_file = create_video_segment(
                media_path, audio_path, text_to_pass, i, len(text_lines),
                is_video, orientation_config, tts_provider, overlay_text=overlay_text,
                include_video_audio=include_video_audio
            )
            
            if video_file:
                video_files.append(video_file)
            
            progress = 40 + (i / len(text_lines)) * 40
            job_status[job_id]['progress'] = int(progress)
        
        job_status[job_id]['message'] = 'Concatenating videos...'
        job_status[job_id]['progress'] = 80
        
        # Concatenate videos
        output_path = os.path.join(original_cwd, app.config['OUTPUT_FOLDER'], f"{job_id}.mp4")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Use music file if it exists in job folder
        background_music = music_path if music_path and os.path.exists(music_path) else None
        if not background_music:
            # Check for song.m4a or song.mp3 in job folder
            for ext in ['m4a', 'mp3']:
                test_path = f'song.{ext}'
                if os.path.exists(test_path):
                    background_music = test_path
                    break
        
        concat_videos(
            video_dir='temp_video',
            output_path=output_path,
            background_music=background_music
        )
        
        job_status[job_id]['message'] = 'Cleaning up...'
        job_status[job_id]['progress'] = 90
        
        # Return to original directory before cleanup
        os.chdir(original_cwd)
        
        # Cleanup job folder
        shutil.rmtree(job_folder)
        
        job_status[job_id]['status'] = 'completed'
        job_status[job_id]['message'] = 'Video generated successfully!'
        job_status[job_id]['progress'] = 100
        
    except Exception as e:
        os.chdir(original_cwd)
        job_status[job_id]['status'] = 'error'
        job_status[job_id]['message'] = f'Error: {str(e)}'
        print(f"Error in job {job_id}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    # Create necessary directories
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)
    
    app.run(debug=True, host='0.0.0.0', port=5000)