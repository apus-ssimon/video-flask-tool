#!/usr/bin/env python3

import os
import subprocess
import glob
import json

def get_video_info(video_path):
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        return json.loads(result.stdout)
    return None

def normalize_segment(input_file, output_file, target_duration):
    print(f"Normalizing {input_file} to {target_duration:.3f}s...")

    cmd = [
        "ffmpeg", "-y", "-i", input_file,
        "-t", str(target_duration),
        "-r", "25",
        "-c:v", "libx264", "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-vsync", "cfr",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
        "-af", f"apad=pad_dur=0.1{',afade=t=out:st=' + str(target_duration - 0.5) + ':d=0.5' if output_file.endswith('norm_7.mp4') else ''}",
        output_file
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to normalize {input_file}: {e}")
        return False

def add_background_music(video_file, music_file, output_file):
    if music_file is None:
        print("⚠️ No background music file provided, skipping...")
        return False
    
    print(f"Adding background music with fade-out: {music_file} -> {video_file}")

    video_info = get_video_info(video_file)
    if not video_info or 'format' not in video_info:
        print("❌ Failed to retrieve video duration for fade-out.")
        return

    duration = float(video_info['format']['duration'])
    fade_start = max(0, duration - 3)

    cmd = [
        "ffmpeg", "-y",
        "-i", video_file,
        "-i", music_file,
        "-filter_complex",
        f"[1:a]afade=t=out:st={fade_start:.3f}:d=3,volume=0.3[a1];"
        f"[0:a]volume=1.0[a0];"
        f"[a0][a1]amix=inputs=2:duration=first:dropout_transition=3[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", output_file
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True)
        print("✅ Background music with fade-out added successfully.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to add background music: {e.stderr.decode()}")

def concat_videos(video_dir, output_path, background_music="song.m4a"):
    print("📦 Starting video stitching process...")

    video_files = sorted(glob.glob(os.path.join(video_dir, "*.mp4")), key=lambda x: int(os.path.basename(x).split('.')[0]))
    if not video_files:
        print("No video files found!")
        return

    expected_durations = []
    for video_file in video_files:
        info = get_video_info(video_file)
        if info and 'format' in info:
            expected_durations.append(float(info['format']['duration']))
        else:
            expected_durations.append(4.0)

    normalized_files = []

    for i, video_file in enumerate(video_files):
        base_name = os.path.basename(video_file)
        normalized_file = os.path.join(video_dir, f"norm_{base_name}")
        if normalize_segment(video_file, normalized_file, expected_durations[i]):
            normalized_files.append(normalized_file)
        else:
            normalized_files.append(video_file)

    concat_list_path = os.path.join(video_dir, "normalized_files.txt")
    with open(concat_list_path, "w") as f:
        for file in normalized_files:
            f.write(f"file '{os.path.abspath(file)}'\n")

    stitched_path = os.path.join(video_dir, "stitched.mp4")

    try:
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list_path,
            "-c:v", "libx264", "-crf", "23",
            "-c:a", "aac", "-b:a", "192k",
            stitched_path
        ], check=True, capture_output=True)

        final_output = os.path.join(video_dir, output_path)

        if background_music and os.path.exists(os.path.join(".", background_music)):
            music_path = os.path.join(".", background_music)
            add_background_music(stitched_path, music_path, final_output)
        else:
            if background_music:
                print(f"⚠️ Background music file '{background_music}' not found, skipping...")
            else:
                print("⚠️ No background music specified, skipping...")
            os.rename(stitched_path, final_output)

        print("\n🧹 Cleaning up temporary files...")
        for f in normalized_files:
            if os.path.exists(f):
                os.remove(f)
        if os.path.exists(stitched_path):
            os.remove(stitched_path)
        if os.path.exists(concat_list_path):
            os.remove(concat_list_path)

        print(f"✅ Final video ready at: {final_output}")

    except subprocess.CalledProcessError as e:
        print(f"❌ Concatenation failed: {e.stderr.decode()}")
