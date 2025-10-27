# video_generator.py - Video segment creation and processing
import os
import subprocess
import shutil
import json
from pydub import AudioSegment
from video_effects import *
from video_effects import add_corner_text_overlay, create_text_overlay_image
from config import *
from config import TTS_SPEED_SETTINGS

def find_media_file(segment_index):
    """Find the media file for a given segment index (image or video)"""
    all_extensions = IMAGE_EXTENSIONS + VIDEO_EXTENSIONS
    
    for ext in all_extensions:
        media_path = os.path.join(MEDIA_DIR, f"{segment_index}{ext}")
        if os.path.exists(media_path):
            is_video = ext.lower() in VIDEO_EXTENSIONS
            return media_path, is_video
    
    return None, None

def get_video_info(video_path):
    """Get video duration and dimensions using ffprobe"""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise Exception(f"Could not get video info for {video_path}")
    
    info = json.loads(result.stdout)
    
    # Find video stream
    video_stream = None
    for stream in info['streams']:
        if stream['codec_type'] == 'video':
            video_stream = stream
            break
    
    if not video_stream:
        raise Exception(f"No video stream found in {video_path}")
    
    duration = float(info['format']['duration'])
    width = int(video_stream['width'])
    height = int(video_stream['height'])
    
    return duration, width, height

def create_video_segment(media_path, audio_path, text_line, segment_index, total_segments, is_video, orientation_config, tts_provider, overlay_text=None, header_text=None, include_video_audio=False):
    """Create a video segment from either an image or video file
    
    Parameters:
    - text_line: Used for skip/loop logic (raw text from file)
    - overlay_text: The actual text to display on video (controlled by checkbox)
    - header_text: Title text to display (if provided)
    """
    
    # Create overlay image once if this is the first segment and has header text
    overlay_image_path = None
    if header_text and segment_index == 1:
        overlay_image_path = create_text_overlay_image(
            header_text,
            orientation_config["width"],
            orientation_config["height"],
            font_size=36,
            padding=50
        )
    
    # For image-based segments
    if not is_video:
        return create_video_segment_from_image(
            media_path, 
            audio_path, 
            text_line,  # Keep for skip/loop logic
            segment_index, 
            total_segments, 
            orientation_config, 
            tts_provider, 
            overlay_text,  # Text to actually display
            overlay_image_path,
            header_text  # Pass header_text
        )
    else:
        # For video-based segments
        return create_video_segment_from_video(
            media_path, 
            audio_path, 
            text_line,  # Keep for skip/loop logic
            segment_index, 
            total_segments, 
            orientation_config, 
            tts_provider, 
            overlay_text,  # Text to actually display
            overlay_image_path,
            header_text,  # Pass header_text
            include_video_audio
        )

def create_video_segment_from_image(image_path, audio_path, text_line, segment_index, total_segments, orientation_config, tts_provider, overlay_text=None, overlay_image_path=None, header_text=None):
    """Create a video segment from an image with zoom, vignette, and text overlay using Pillow
    
    Parameters:
    - text_line: Used for skip detection and loop logic
    - overlay_text: The actual text to display (controlled by checkbox)
    - header_text: Title/header text (if any)
    """
    print(f"   Creating segment {segment_index} from image with Pillow...")
    
    target_width = orientation_config["width"]
    target_height = orientation_config["height"]
    text_size = orientation_config["text_size"]
    text_y_position = orientation_config["text_y_position"]
    text_wrap_width = orientation_config["text_wrap_width"]
    
    # Load audio and add padding
    original = AudioSegment.from_file(audio_path)
    silence = AudioSegment.silent(duration=1000)  # 1 second
    padded_audio = original + silence

    # Export padded audio
    padded_audio_path = f"temp_audio/{segment_index}_padded.mp3"
    padded_audio.export(padded_audio_path, format="mp3")

    # Get duration in seconds using TTS-specific speed
    audio_speed = TTS_SPEED_SETTINGS[tts_provider]
    audio_duration = padded_audio.duration_seconds / audio_speed
    
    # Prepare image canvas
    canvas = prepare_image_canvas(image_path, target_width, target_height)
    if canvas is None:
        return None
    
    # Load overlay image if available
    overlay_img = None
    if overlay_image_path and segment_index == 1:
        try:
            overlay_img = Image.open(overlay_image_path).convert("RGBA")
            print(f"   Loaded overlay image for header text: {header_text}")
        except Exception as e:
            print(f"   Could not load overlay image: {e}")
            overlay_img = None
    
    # Video settings
    total_frames = int(audio_duration * FPS)
    
    # Create frames directory for this segment
    frames_dir = f"temp_frames/segment_{segment_index}"
    os.makedirs(frames_dir, exist_ok=True)
    
    # Generate frames
    for frame_num in range(total_frames):
        t = frame_num / FPS  # Current time in seconds
        
        # Calculate zoom factor and apply zoom
        zoom_factor = create_zoom_factor(t, audio_duration, ZOOM_TYPE, ZOOM_SPEED)
        frame = apply_zoom_effect(canvas, target_width, target_height, zoom_factor)
        
        # Apply fade in/out (only at beginning and end of entire video)
        frame = apply_fade_effect(frame, t, FADE_DURATION, audio_duration, segment_index, total_segments, t)
        
        # Add main text overlay - use overlay_text (controlled by checkbox) instead of text_line
        if overlay_text and overlay_text.strip():
            frame = add_text_overlay(frame, overlay_text, target_width, target_height, text_size, text_y_position, text_wrap_width)

        # Add overlay image if available
        if overlay_img and segment_index == 1:
            # Convert frame to RGBA for compositing
            frame_rgba = frame.convert("RGBA")
            # Composite the overlay on top
            frame = Image.alpha_composite(frame_rgba, overlay_img).convert("RGB")
            if frame_num == 0:
                print(f"   Added overlay image to frame with header text: {header_text}")
        # Fallback to old method if overlay image isn't available
        elif header_text and segment_index == 1 and not overlay_img:
            frame = add_corner_text_overlay(
                frame,
                header_text,
                target_width,
                target_height,
                font_size=36,
                padding=50,
                font_path="fonts/Gibson-Bold.otf"
            )

        # Apply vignette effect
        frame = create_vignette_effect(frame, VIGNETTE_STRENGTH_IMAGE)

        # Save frame
        frame_path = os.path.join(frames_dir, f"frame_{frame_num:06d}.jpg")
        frame.save(frame_path, 'JPEG', quality=95)
    
    # Create video from frames using FFmpeg
    temp_video_path = f"temp_video/{segment_index}_temp.mp4"
    frames_pattern = os.path.join(frames_dir, "frame_%06d.jpg")
    
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", frames_pattern,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", str(VIDEO_CRF),
        temp_video_path
    ]
    
    subprocess.run(cmd, check=True, capture_output=True)
    
    # Combine with audio
    final_video_path = f"temp_video/{segment_index}.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-i", temp_video_path,
        "-i", padded_audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        final_video_path
    ]
    
    subprocess.run(cmd, check=True, capture_output=True)
    
    # Clean up temporary files
    os.remove(temp_video_path)
    shutil.rmtree(frames_dir)
    
    print(f"   ✅ Created video segment {segment_index}")
    return final_video_path

def create_video_segment_from_video(video_path, audio_path, text_line, segment_index, total_segments, orientation_config, tts_provider, overlay_text=None, overlay_image_path=None, header_text=None, include_video_audio=False):
    """Create a video segment from a video file
    
    Parameters:
    - text_line: Used for skip detection and loop logic  
    - overlay_text: The actual text to display (controlled by checkbox)
    - header_text: Title/header text (if any)
    """
    print(f"   Processing video segment {segment_index}...")
    
    target_width = orientation_config["width"]
    target_height = orientation_config["height"]
    text_size = orientation_config["text_size"]
    text_y_position = orientation_config["text_y_position"]
    text_wrap_width = orientation_config["text_wrap_width"]
    
    # Get video info
    video_duration, video_width, video_height = get_video_info(video_path)
    
    # Load audio and add padding
    original = AudioSegment.from_file(audio_path)
    silence = AudioSegment.silent(duration=1000)  # 1 second
    padded_audio = original + silence
    
    # Export padded audio
    padded_audio_path = f"temp_audio/{segment_index}_padded.mp3"
    padded_audio.export(padded_audio_path, format="mp3")
    
    # Get audio duration in seconds
    audio_speed = TTS_SPEED_SETTINGS[tts_provider]
    audio_duration = padded_audio.duration_seconds / audio_speed
    
    # Determine if we need to loop the video (using text_line for skip logic)
    needs_loop = False
    if text_line and text_line.strip() == '-skip-':
        # For -skip-, use the video's natural duration
        final_duration = video_duration
        print(f"   Using natural video duration: {final_duration:.2f}s (skip mode)")
    else:
        # Otherwise, match audio duration
        final_duration = audio_duration
        if final_duration > video_duration:
            needs_loop = True
            print(f"   Video will loop: video={video_duration:.2f}s, needed={final_duration:.2f}s")
    
    # Prepare FFmpeg inputs
    inputs = ["-i", video_path, "-i", padded_audio_path]
    
    # Build video filters
    video_filters = []
    
    # Scale and pad to target resolution
    scale_filter = f"scale=w={target_width}:h={target_height}:force_original_aspect_ratio=decrease"
    pad_filter = f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black"
    video_filters.append(scale_filter)
    video_filters.append(pad_filter)
    
    # Apply vignette
    vignette_filter = f"vignette=PI/{VIGNETTE_STRENGTH_VIDEO}"
    video_filters.append(vignette_filter)
    
    # Handle looping if needed
    if needs_loop:
        loop_count = int(final_duration / video_duration) + 1
        video_filters.insert(0, f"loop=loop={loop_count}:size=999999:start=0")
    
    # Apply fade effects
    if segment_index == 1:
        video_filters.append(f"fade=t=in:st=0:d={FADE_DURATION}")
    if segment_index == total_segments:
        fade_start = final_duration - FADE_DURATION
        video_filters.append(f"fade=t=out:st={fade_start}:d={FADE_DURATION}:color=black")
    
    # Use a new approach for adding text overlays
    has_overlay = False
    if overlay_image_path and segment_index == 1:
        # Add overlay image as input
        inputs.extend(["-i", overlay_image_path])
        has_overlay = True
        print(f"   Adding overlay image for header text: {header_text}")
    
    # Prepare filter graph
    filter_parts = []
    
    # Start with main video processing
    video_filter_part = f"[0:v]{','.join(video_filters)}[scaled_video]"
    filter_parts.append(video_filter_part)
    last_video_label = "[scaled_video]"
    
    # Add main text - use overlay_text (controlled by checkbox) instead of text_line
    if overlay_text and overlay_text.strip():
        escaped_text = escape_text_for_ffmpeg(overlay_text, text_wrap_width)
        print(f"   Debug - Display text: {overlay_text}")
        print(f"   Debug - Escaped text: {escaped_text}")
        text_y_pos = target_height - 50
        text_filter = f"{last_video_label}drawtext=text='{escaped_text}':fontsize={text_size}:fontcolor=white:bordercolor=black:borderw=3:x=(w-text_w)/2:y=h-th-50[video_with_text]"
        print(f"   Debug - FFmpeg filter: {text_filter}")
        filter_parts.append(text_filter)
        last_video_label = "[video_with_text]"
    
    # Add overlay image if available
    if has_overlay:
        # Use the third input (index 2) for the overlay
        overlay_filter = f"{last_video_label}[2:v]overlay=0:0[video_with_overlay]"
        filter_parts.append(overlay_filter)
        last_video_label = "[video_with_overlay]"
    # Fallback to old method if overlay image isn't available
    elif header_text and segment_index == 1 and not has_overlay:
        padding = 50
        font_size = 36
        escaped_overlay_text = escape_text_for_ffmpeg(header_text, 40)
        text_x = f"w-tw-{padding}"
        text_y = f"h-th-{padding}"
        
        # Try to use Gibson-Bold font, or fallback to a system font
        font_path = "fonts/Gibson-Bold.otf"
        if os.path.exists(font_path):
            font_param = f":fontfile='{font_path}'"
        else:
            font_param = ""
        
        overlay_filter = f"{last_video_label}drawtext=text='{escaped_overlay_text}'{font_param}:fontsize={font_size}:fontcolor=black:bordercolor=white:borderw=2:x={text_x}:y={text_y}[video_with_overlay]"
        filter_parts.append(overlay_filter)
        last_video_label = "[video_with_overlay]"
        print(f"   Adding corner text overlay using drawtext: '{header_text}' to video")
    
    # Join all filter parts
    complete_filter = ";".join(filter_parts)
    
    # Build ffmpeg command
    cmd = [
        "ffmpeg", "-y"
    ]
    cmd.extend(inputs)
    
    final_video_path = f"temp_video/{segment_index}.mp4"
    
    # Determine audio mapping based on include_video_audio flag
    if include_video_audio:
        # Mix original video audio with TTS audio
        audio_filter = "[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=2[a]"
        cmd.extend([
            "-filter_complex", f"{complete_filter};{audio_filter}",
            "-map", last_video_label,
            "-map", "[a]",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-crf", str(FALLBACK_CRF),
            "-pix_fmt", "yuv420p",
            "-t", str(final_duration),
            final_video_path
        ])
    else:
        # Use only TTS audio (original behavior)
        cmd.extend([
            "-filter_complex", complete_filter,
            "-map", last_video_label,
            "-map", "1:a",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-crf", str(FALLBACK_CRF),
            "-pix_fmt", "yuv420p",
            "-t", str(final_duration),
            final_video_path
        ])
    try:
        print(f"   Running FFmpeg command...")
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"   Successfully created video segment {segment_index}")
        return final_video_path
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg error for segment {segment_index}: {e}")
        return _try_video_fallbacks(video_path, padded_audio_path, final_duration, final_video_path, segment_index, target_width, target_height, overlay_text, overlay_image_path, header_text, include_video_audio)

def _try_video_fallbacks(video_path, padded_audio_path, final_duration, final_video_path, segment_index, target_width, target_height, overlay_text=None, overlay_image_path=None, header_text=None, include_video_audio=False):
    """Try fallback methods for video processing
    
    Parameters:
    - overlay_text: The actual text to display (controlled by checkbox)
    - header_text: Title/header text (if any)
    """
    print(f"   Trying fallback: simple audio replacement with scaling...")
    
    fallback_filter = f"scale=w={target_width}:h={target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black"
    
    has_overlay = False
    inputs = ["-i", video_path, "-i", padded_audio_path]
    
    if overlay_image_path and segment_index == 1:
        inputs.extend(["-i", overlay_image_path])
        has_overlay = True
        print(f"   Adding overlay image in fallback for header text: {header_text}")
    
    try:
        # Start with basic fallback filter
        filter_complex = f"[0:v]{fallback_filter}"
        
        # Add overlay if available
        if has_overlay:
            filter_complex += f"[v];[v][2:v]overlay=0:0"
        # Fallback to old method if overlay image isn't available
        elif header_text and segment_index == 1 and not has_overlay:
            padding = 50
            font_size = 36
            escaped_overlay_text = escape_text_for_ffmpeg(header_text, 40)
            text_x = f"w-tw-{padding}"
            text_y = f"h-th-{padding}"
            
            # Try to use Gibson-Bold font, or fallback to a system font
            font_path = "fonts/Gibson-Bold.otf"
            if os.path.exists(font_path):
                font_param = f":fontfile='{font_path}'"
            else:
                font_param = ""
            
            filter_complex += f",drawtext=text='{escaped_overlay_text}'{font_param}:fontsize={font_size}:fontcolor=black:bordercolor=white:borderw=2:x={text_x}:y={text_y}"
            print(f"   Adding corner text overlay in fallback using drawtext: '{header_text}'")
        
        filter_complex += "[v]"
        
        fallback_cmd = [
            "ffmpeg", "-y"
        ]
        fallback_cmd.extend(inputs)
        if include_video_audio:
            # Mix original video audio with TTS audio
            audio_filter = "[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=2[a]"
            fallback_cmd.extend([
                "-filter_complex", f"{filter_complex};{audio_filter}",
                "-map", "[v]",
                "-map", "[a]",
                "-c:v", "libx264",
                "-c:a", "aac",
                "-crf", str(FALLBACK_CRF),
                "-pix_fmt", "yuv420p",
                "-t", str(final_duration),
                final_video_path
            ])
        else:
            fallback_cmd.extend([
                "-filter_complex", filter_complex,
                "-map", "[v]",
                "-map", "1:a",
                "-c:v", "libx264",
                "-c:a", "aac",
                "-crf", str(FALLBACK_CRF),
                "-pix_fmt", "yuv420p",
                "-t", str(final_duration),
                final_video_path
            ])
        
        subprocess.run(fallback_cmd, check=True, capture_output=True)
        print(f"   ✅ Fallback successful for segment {segment_index}")
        return final_video_path
    except subprocess.CalledProcessError:
        print(f"   Trying final fallback: direct audio replacement...")
        try:
            # For the final fallback, we can't add text overlays since we're using copy codec
            simple_cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-i", padded_audio_path,
                "-map", "0:v",
                "-map", "1:a",
                "-c:v", "copy",
                "-c:a", "aac",
                "-t", str(final_duration),
                final_video_path
            ]
            subprocess.run(simple_cmd, check=True, capture_output=True)
            print(f"   ✅ Final fallback successful for segment {segment_index} (note: no text overlay added in final fallback)")
            return final_video_path
        except subprocess.CalledProcessError:
            print(f"❌ All fallbacks failed for segment {segment_index}")
            return None