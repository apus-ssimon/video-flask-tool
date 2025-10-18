# video_effects.py - Video processing and effects functions
import os
import numpy as np
import textwrap
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from config import *

def create_zoom_factor(t, duration, zoom_type, zoom_speed):
   """Calculate zoom factor based on time and zoom type"""
   progress = min(t / duration, 1.0)  # Ensure progress doesn't exceed 1
   
   if zoom_type == "ease-in":
       # Starts slow, accelerates (quadratic)
       zoom_factor = 1 + zoom_speed * (progress ** 2)
   elif zoom_type == "ease-out":
       # Starts fast, slows down  
       zoom_factor = 1 + zoom_speed * (1 - (1 - progress) ** 2)
   elif zoom_type == "ease-in-out":
       # Smooth S-curve
       if progress < 0.5:
           zoom_factor = 1 + zoom_speed * (2 * progress ** 2)
       else:
           zoom_factor = 1 + zoom_speed * (1 - 2 * (1 - progress) ** 2)
   else:  # linear
       zoom_factor = 1 + zoom_speed * progress
   
   return zoom_factor

def create_vignette_effect(img, strength=0.5):
   """Create vignette effect using PIL and numpy"""
   width, height = img.size
   
   # Create coordinate arrays
   x, y = np.meshgrid(np.arange(width), np.arange(height))
   
   # Calculate distance from center
   center_x, center_y = width // 2, height // 2
   distance = np.sqrt((x - center_x)**2 + (y - center_y)**2)
   max_distance = np.sqrt(center_x**2 + center_y**2)
   
   # Normalize distance
   normalized_distance = distance / max_distance
   
   # Create vignette mask
   vignette_mask = 1 - (normalized_distance ** 2) * strength
   vignette_mask = np.clip(vignette_mask, 0, 1)
   
   # Convert image to numpy array
   img_array = np.array(img)
   
   # Apply vignette to each color channel
   if len(img_array.shape) == 3:
       for c in range(img_array.shape[2]):
           img_array[:, :, c] = img_array[:, :, c] * vignette_mask
   else:
       img_array = img_array * vignette_mask
   
   # Convert back to PIL Image
   return Image.fromarray(img_array.astype(np.uint8))

def apply_fade_effect(img, progress, fade_duration, total_duration, segment_index, total_segments, global_progress):
   """Apply fade in/out effect only at beginning and end of entire video"""
   alpha = 1.0
   
   # Only apply fade to first and last segments
   if segment_index == 1 and progress <= fade_duration:
       # Fade in at very beginning of video
       alpha = progress / fade_duration
   elif segment_index == total_segments and progress >= (total_duration - fade_duration):
       # Fade out at very end of video
       alpha = (total_duration - progress) / fade_duration
   
   alpha = max(0, min(1, alpha))  # Clamp between 0 and 1
   
   if alpha < 1.0:
       # Create fade effect by blending with black
       black_img = Image.new('RGB', img.size, (0, 0, 0))
       img = Image.blend(black_img, img, alpha)
   
   return img

def add_text_overlay(frame, text_line, target_width, target_height, text_size, text_y_position, text_wrap_width):
   """Add text overlay to a frame"""
   if not text_line or text_line.strip() == '-skip-':
       return frame
   
   draw = ImageDraw.Draw(frame)
   
   # Wrap text
   wrapped_text = textwrap.fill(text_line, width=text_wrap_width)
   
   # Try to load a font
   try:
       font = ImageFont.truetype("fonts/Gibson-Regular.otf", text_size)
   except:
       try:
           font = ImageFont.truetype("arial.ttf", text_size)
       except:
           font = ImageFont.load_default()
   
   # Calculate text position
   bbox = draw.textbbox((0, 0), wrapped_text, font=font)
   text_width = bbox[2] - bbox[0]
   text_height = bbox[3] - bbox[1]
   
   x = (target_width - text_width) // 2
   y = target_height - text_y_position  # Use orientation-specific position
   
   # Draw text with outline
   outline_width = 3
   for dx in range(-outline_width, outline_width + 1):
       for dy in range(-outline_width, outline_width + 1):
           if dx*dx + dy*dy <= outline_width*outline_width:
               draw.text((x + dx, y + dy), wrapped_text, font=font, fill='black')
   
   # Draw main text
   draw.text((x, y), wrapped_text, font=font, fill='white')
   
   return frame

def apply_zoom_effect(canvas, target_width, target_height, zoom_factor):
   """Apply zoom effect to an image"""
   if zoom_factor == 1.0:
       return canvas.copy()
   
   # Calculate new dimensions
   zoom_width = int(target_width * zoom_factor)
   zoom_height = int(target_height * zoom_factor)
   
   # Resize image with zoom
   zoomed_img = canvas.resize((zoom_width, zoom_height), Image.LANCZOS)
   
   # Center crop back to original size
   left = (zoom_width - target_width) // 2
   top = (zoom_height - target_height) // 2
   right = left + target_width
   bottom = top + target_height
   
   # Handle edge cases
   if left >= 0 and top >= 0 and right <= zoom_width and bottom <= zoom_height:
       return zoomed_img.crop((left, top, right, bottom))
   else:
       # Create black canvas and paste zoomed image
       frame = Image.new('RGB', (target_width, target_height), (0, 0, 0))
       paste_x = max(0, -left)
       paste_y = max(0, -top)
       crop_left = max(0, left)
       crop_top = max(0, top)
       crop_right = min(zoom_width, right)
       crop_bottom = min(zoom_height, bottom)
       
       if crop_right > crop_left and crop_bottom > crop_top:
           cropped_zoom = zoomed_img.crop((crop_left, crop_top, crop_right, crop_bottom))
           frame.paste(cropped_zoom, (paste_x, paste_y))
       
       return frame

def prepare_image_canvas(image_path, target_width, target_height):
   """Prepare an image canvas with proper scaling and centering"""
   try:
       img = Image.open(image_path)
       if img.mode != 'RGB':
           img = img.convert('RGB')
   except Exception as e:
       print(f"❌ Could not load image: {image_path} - {e}")
       return None
   
   # Get image dimensions
   original_width, original_height = img.size
   
   # Resize image to fit target dimensions while maintaining aspect ratio
   scale_w = target_width / original_width
   scale_h = target_height / original_height
   scale = min(scale_w, scale_h)
   
   new_width = int(original_width * scale)
   new_height = int(original_height * scale)
   
   # Resize image with high quality
   img = img.resize((new_width, new_height), Image.LANCZOS)
   
   # Create black canvas and center the image
   canvas = Image.new('RGB', (target_width, target_height), (0, 0, 0))
   x_offset = (target_width - new_width) // 2
   y_offset = (target_height - new_height) // 2
   canvas.paste(img, (x_offset, y_offset))
   
   return canvas

def create_text_overlay_image(text, width, height, font_size=24, padding=50):
    """Create a transparent PNG with text overlay for more reliable FFmpeg processing"""
    # Create temp directory if it doesn't exist
    os.makedirs("temp_frames", exist_ok=True)
    
    # Create a transparent image
    overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    # Try to load font
    try:
        font = ImageFont.truetype("fonts/Gibson-Bold.otf", font_size)
        print(f"   Loaded Gibson-Bold font for overlay image")
    except Exception as e:
        print(f"   Could not load Gibson-Bold font: {e}, using default")
        font = ImageFont.load_default()
    
    # Calculate position
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = width - text_width - padding
    y = height - text_height - padding
    
    # Draw white outline
    outline_width = 2
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx*dx + dy*dy <= outline_width*outline_width:
                draw.text((x + dx, y + dy), text, font=font, fill=(255, 255, 255, 255))
    
    # Draw black text
    draw.text((x, y), text, font=font, fill=(0, 0, 0, 255))
    
    # Save overlay image
    overlay_path = "temp_frames/text_overlay.png"
    overlay.save(overlay_path, "PNG")
    print(f"   Created text overlay image: {overlay_path}")
    
    return overlay_path

def escape_text_for_ffmpeg(text, text_wrap_width):
    """Escape text for use in FFmpeg drawtext filter"""
    wrapped_text = textwrap.fill(text, width=text_wrap_width)
    # Simple escaping approach
    escaped_text = wrapped_text.replace("'", "'\\''")  # Replace ' with '\''
    escaped_text = escaped_text.replace(":", "\\:")
    escaped_text = escaped_text.replace("%", "\\%")
    return escaped_text

def add_corner_text_overlay(frame, text, width, height, font_size=24, padding=50, font_path=None):
    print(f"Adding corner text: '{text}' on frame {width}x{height}")
    """Overlay text in the bottom-right corner of a frame"""
    if not text:
        return frame

    draw = ImageDraw.Draw(frame)

    # Load font - try Gibson-Bold first
    try:
        font = ImageFont.truetype("fonts/Gibson-Bold.otf", font_size)
    except:
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            font = ImageFont.load_default()

    # Calculate text size and position
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = width - text_width - padding  # Increased padding
    y = height - text_height - padding  # Increased padding

    # Draw white outline (thicker for better visibility)
    outline_width = 2
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx*dx + dy*dy <= outline_width*outline_width:
                draw.text((x + dx, y + dy), text, font=font, fill="white")

    # Draw main text in black
    draw.text((x, y), text, font=font, fill="black")

    return frame

