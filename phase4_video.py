import os
import json
import math
from PIL import Image
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips

# --- Absolute Paths from Context ---
TIMELINE_PATH = r"C:\Users\User\PycharmProjects\pythonProject2\timeline_map.json"
IMAGE_DIR = r"C:\Users\User\PycharmProjects\pythonProject2\manga_panels"
AUDIO_DIR = r"C:\Users\User\PycharmProjects\pythonProject2\generated_audio"
VIDEO_OUT = r"C:\Users\User\PycharmProjects\pythonProject2\final_recap_video.mp4"
PROCESSED_DIR = r"C:\Users\User\PycharmProjects\pythonProject2\processed_panels"


def load_timeline():
    if not os.path.exists(TIMELINE_PATH):
        raise FileNotFoundError(f"Timeline blueprint missing at {TIMELINE_PATH}")
    with open(TIMELINE_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def preprocess_panel(image_path, out_path, target_width=1280, target_height=720):
    """Load image, crop/pad to target aspect ratio (16:9), and save it to avoid FFMPEG aspect ratio crashes."""
    with Image.open(image_path) as img:
        img = img.convert('RGB')
        target_aspect = target_width / target_height
        img_aspect = img.width / img.height
        
        if img_aspect > target_aspect:
            # Image is wider than 16:9: crop sides
            new_width = int(img.height * target_aspect)
            offset = (img.width - new_width) // 2
            img = img.crop((offset, 0, offset + new_width, img.height))
        else:
            # Image is taller than 16:9 (e.g., vertical webtoon scroll): crop top section
            new_height = int(img.width / target_aspect)
            img = img.crop((0, 0, img.width, new_height))
            
        img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
        img.save(out_path, "JPEG", quality=90)


def zoom_in_effect(t):
    """Simple Ken Burns effect: gradually zooms in by 5% over the clip's duration."""
    return 1 + 0.05 * t


def assemble_video():
    print("[*] Starting Phase 4: Multi-Threaded Video Assembly...")

    try:
        timeline = load_timeline()
    except Exception as e:
        print(f"[!] Error: {e}")
        return

    # Ensure processed panels directory exists
    os.makedirs(PROCESSED_DIR, exist_ok=True)

    video_clips = []

    print(f"[*] Preprocessing and compiling {len(timeline)} scenes...")
    for idx, scene in enumerate(timeline):
        audio_path = os.path.join(AUDIO_DIR, scene["audio_file"])
        orig_image_path = os.path.join(IMAGE_DIR, scene["panel_file"])
        processed_image_path = os.path.join(PROCESSED_DIR, f"proc_{scene['panel_file']}.jpg")

        # Verify source files exist
        if not os.path.exists(audio_path) or not os.path.exists(orig_image_path):
            print(f"[!] Warning: Missing files for Scene {idx} (Audio: {scene['audio_file']}, Image: {scene['panel_file']}). Skipping.")
            continue

        try:
            # 1. Preprocess the panel to standard 1280x720 (16:9) to prevent crashes and optimize rendering speed
            if not os.path.exists(processed_image_path):
                preprocess_panel(orig_image_path, processed_image_path)

            # 2. Load Audio to dictate the duration
            audio_clip = AudioFileClip(audio_path)
            duration = audio_clip.duration

            # 3. Load standardized image and set its duration to perfectly match the audio (MoviePy v2.x with_duration)
            img_clip = ImageClip(processed_image_path).with_duration(duration)

            # 4. Apply the Ken Burns Zoom effect (MoviePy v2.x resized)
            img_clip = img_clip.resized(zoom_in_effect)

            # 5. Attach the audio to the image (MoviePy v2.x with_audio)
            img_clip = img_clip.with_audio(audio_clip)

            video_clips.append(img_clip)

        except Exception as e:
            print(f"[!] Error building clip {idx}: {e}")

    if not video_clips:
        print("[!] No clips were successfully generated. Aborting render.")
        return

    print("[*] All scenes processed. Stitching timeline together...")

    # Compose the final timeline
    # method='compose' handles varying heights safely by centering them
    final_video = concatenate_videoclips(video_clips, method="compose")

    print(f"[*] Rendering video with MoviePy v2.x...")

    # Render with hardware acceleration
    try:
        print("[*] Attempting NVIDIA GPU hardware acceleration (h264_nvenc)...")
        final_video.write_videofile(
            VIDEO_OUT,
            fps=15,  # 15 fps is extremely fast and plenty smooth for static recap narration
            codec="h264_nvenc",  # NVIDIA GPU Encoder
            audio_codec="aac",
            threads=24,  # Maximizing the i7-13700KF cores
            preset="fast"
        )
        print(f"\n[*] SUCCESS: Final recap video rendered at {VIDEO_OUT}")

    except Exception as e:
        print(f"\n[!] Render Error using NVENC: {e}")
        print("[*] Falling back to standard CPU rendering (libx264)...")
        # Fallback if the specific ffmpeg build doesn't have NVENC compiled or driver lacks capability
        final_video.write_videofile(
            VIDEO_OUT,
            fps=15,
            codec="libx264",
            audio_codec="aac",
            threads=24,
            preset="ultrafast"
        )
        print(f"\n[*] SUCCESS: Final recap video rendered at {VIDEO_OUT}")


if __name__ == "__main__":
    assemble_video()