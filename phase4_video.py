import os
import json
import random
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from moviepy import VideoClip, AudioFileClip, concatenate_videoclips, CompositeAudioClip

# --- Absolute Paths from Context ---
TIMELINE_PATH = r"C:\Users\User\PycharmProjects\pythonProject2\timeline_map.json"
IMAGE_DIR = r"C:\Users\User\PycharmProjects\pythonProject2\manga_panels"
AUDIO_DIR = r"C:\Users\User\PycharmProjects\pythonProject2\generated_audio"
VIDEO_OUT = r"C:\Users\User\PycharmProjects\pythonProject2\final_recap_video.mp4"


def load_timeline(timeline_path=None):
    if timeline_path is None:
        timeline_path = TIMELINE_PATH
    if not os.path.exists(timeline_path):
        raise FileNotFoundError(f"Timeline blueprint missing at {timeline_path}")
    with open(timeline_path, 'r', encoding='utf-8') as f:
        return json.load(f)


# (Subtitles functions get_font and wrap_text removed)


def create_vignette_alpha_mask(width=1280, height=720):
    bg = Image.new("L", (width, height), 0)
    bg_draw = ImageDraw.Draw(bg)
    # White ellipse in the center
    margin_w = -150
    margin_h = -100
    bg_draw.ellipse([margin_w, margin_h, width - margin_w, height - margin_h], fill=255)
    # Blur heavily
    blurred = bg.filter(ImageFilter.GaussianBlur(radius=110))
    # Invert and scale to set corner opacity to ~165
    vignette_alpha = blurred.point(lambda p: int((255 - p) * 0.65))
    return vignette_alpha


def create_blurred_background(orig_img, target_width=1280, target_height=720):
    orig_w, orig_h = orig_img.size
    target_aspect = target_width / target_height
    orig_aspect = orig_w / orig_h
    
    if orig_aspect > target_aspect:
        # Original is wider than target: fit height, crop width
        new_h = target_height
        new_w = int(orig_w * (target_height / orig_h))
        resized = orig_img.resize((new_w, new_h), Image.Resampling.BILINEAR)
        left = (new_w - target_width) // 2
        bg = resized.crop((left, 0, left + target_width, target_height))
    else:
        # Original is taller than target: fit width, crop height
        new_w = target_width
        new_h = int(orig_h * (target_width / orig_w))
        resized = orig_img.resize((new_w, new_h), Image.Resampling.BILINEAR)
        top = (new_h - target_height) // 2
        bg = resized.crop((0, top, target_width, top + target_height))
        
    bg_blurred = bg.filter(ImageFilter.GaussianBlur(radius=20))
    
    # Desaturate the background slightly (e.g. by 60%) to draw focus to the sharp central panel
    return ImageEnhance.Color(bg_blurred).enhance(0.4)


class SceneFrameGenerator:
    def __init__(self, orig_image_path, text, duration, scene_idx, target_width=1280, target_height=720):
        self.orig_img = Image.open(orig_image_path).convert('RGB')
        self.orig_w, self.orig_h = self.orig_img.size
        self.text = text
        self.duration = duration
        self.scene_idx = scene_idx
        self.target_width = target_width
        self.target_height = target_height
        
        # Precompute background and vignette
        self.bg_blurred = create_blurred_background(self.orig_img, target_width, target_height)
        self.vignette_alpha = create_vignette_alpha_mask(target_width, target_height)
        
        # Action/Impact detection
        keywords = ["chopped", "blast", "explosion", "axe", "hit", "shaking", "blood", "cut", 
                    "attacked", "stabbed", "slashed", "lunged", "stomped", "shouted", "screamed"]
        self.is_impact = any(kw in self.text.lower() for kw in keywords)
        
        # Panel aspect ratio and layout mode
        self.ratio = self.orig_h / self.orig_w
        self.is_tall = self.ratio > 1.8
        
        # Particles
        self.particles = []
        rng = random.Random(scene_idx + 1000)
        num_particles = 25
        for _ in range(num_particles):
            self.particles.append({
                'x_start': rng.uniform(0, target_width),
                'y_start': rng.uniform(0, target_height),
                'vx': rng.uniform(-15, 15),
                'vy': rng.uniform(-35, -10),
                'radius': rng.uniform(1.2, 3.5),
                'color': rng.choice([
                    (255, 255, 255), 
                    (245, 245, 250), 
                    (230, 230, 240), 
                    (220, 225, 235)
                ])
            })
            
        pass

    def make_frame(self, t):
        # 1. Start with the desaturated blurred background
        frame = self.bg_blurred.copy()
        
        progress = t / self.duration if self.duration > 0 else 0.0
        progress = max(0.0, min(1.0, progress))
        
        draw = ImageDraw.Draw(frame)
        
        # Screen shake offset for the first 0.3 seconds on action/impact frames
        shake_x = 0
        shake_y = 0
        if self.is_impact and t < 0.3:
            shake_x = int(math.sin(t * 80) * 8)
            shake_y = int(math.cos(t * 80) * 8)
        
        if self.is_tall:
            # Layout vertical panel: scroll from top to bottom
            panel_w = 540
            scale_factor = panel_w / self.orig_w
            panel_h = int(self.orig_h * scale_factor)
            
            scaled_panel = self.orig_img.resize((panel_w, panel_h), Image.Resampling.LANCZOS)
            
            max_scroll = panel_h - self.target_height
            y_offset = int(max_scroll * progress) if max_scroll > 0 else 0
                
            visible_panel = scaled_panel.crop((0, y_offset, panel_w, y_offset + self.target_height))
            
            x_pos = (self.target_width - panel_w) // 2
            frame.paste(visible_panel, (x_pos + shake_x, shake_y))
            
            # Draw thin vertical borders (dark gray)
            draw.line([(x_pos, 0), (x_pos, self.target_height)], fill=(15, 15, 15), width=3)
            draw.line([(x_pos + panel_w, 0), (x_pos + panel_w, self.target_height)], fill=(15, 15, 15), width=3)
            
        else:
            # Layout horizontal/square panel: zoom-in
            panel_h = self.target_height
            scale_factor = panel_h / self.orig_h
            panel_w = int(self.orig_w * scale_factor)
            
            if panel_w > self.target_width:
                panel_w = self.target_width
                scale_factor = panel_w / self.orig_w
                panel_h = int(self.orig_h * scale_factor)
                
                zoom = 1.0 + 0.08 * progress
                z_w = int(panel_w * zoom)
                z_h = int(panel_h * zoom)
                
                scaled_panel = self.orig_img.resize((z_w, z_h), Image.Resampling.LANCZOS)
                x_crop = (z_w - panel_w) // 2
                y_crop = (z_h - panel_h) // 2
                visible_panel = scaled_panel.crop((x_crop, y_crop, x_crop + panel_w, y_crop + panel_h))
                
                y_pos = (self.target_height - panel_h) // 2
                frame.paste(visible_panel, (shake_x, y_pos + shake_y))
                
                draw.line([(0, y_pos), (self.target_width, y_pos)], fill=(15, 15, 15), width=3)
                draw.line([(0, y_pos + panel_h), (self.target_width, y_pos + panel_h)], fill=(15, 15, 15), width=3)
            else:
                zoom = 1.0 + 0.08 * progress
                z_w = int(panel_w * zoom)
                z_h = int(panel_h * zoom)
                
                scaled_panel = self.orig_img.resize((z_w, z_h), Image.Resampling.LANCZOS)
                x_crop = (z_w - panel_w) // 2
                y_crop = (z_h - panel_h) // 2
                visible_panel = scaled_panel.crop((x_crop, y_crop, x_crop + panel_w, y_crop + panel_h))
                
                x_pos = (self.target_width - panel_w) // 2
                frame.paste(visible_panel, (x_pos + shake_x, shake_y))
                
                draw.line([(x_pos, 0), (x_pos, self.target_height)], fill=(15, 15, 15), width=3)
                draw.line([(x_pos + panel_w, 0), (x_pos + panel_w, self.target_height)], fill=(15, 15, 15), width=3)
                
        # 2. Paste Vignette
        frame.paste((0, 0, 0), (0, 0), mask=self.vignette_alpha)
        
        # Screen flash overlay (1-2 frame bright white decay flash) for impact scenes
        if self.is_impact and t < 0.08:
            flash_overlay = Image.new("RGB", (self.target_width, self.target_height), (255, 255, 255))
            opacity = int(180 * (1.0 - t / 0.08))
            frame = Image.blend(frame, flash_overlay, opacity / 255.0)
        
        # 3. Draw Floating Particles
        particle_draw = ImageDraw.Draw(frame)
        for p in self.particles:
            px = int((p['x_start'] + p['vx'] * t) % self.target_width)
            py = int((p['y_start'] + p['vy'] * t) % self.target_height)
            r = p['radius']
            particle_draw.ellipse([px - r, py - r, px + r, py + r], fill=p['color'])
            
        return np.array(frame)


def assemble_video(timeline_path=None, image_dir=None, audio_dir=None, video_out=None, fps=30):
    if timeline_path is None:
        timeline_path = TIMELINE_PATH
    if image_dir is None:
        image_dir = IMAGE_DIR
    if audio_dir is None:
        audio_dir = AUDIO_DIR
    if video_out is None:
        video_out = VIDEO_OUT

    print("[*] Starting Upgraded Phase 4: Multi-Threaded Video Assembly...")

    try:
        timeline = load_timeline(timeline_path)
    except Exception as e:
        print(f"[!] Error loading timeline: {e}")
        return

    video_clips = []

    print(f"[*] Compiling {len(timeline)} scenes...")
    for idx, scene in enumerate(timeline):
        audio_path = os.path.join(audio_dir, scene["audio_file"])
        orig_image_path = os.path.join(image_dir, scene["panel_file"])

        if not os.path.exists(audio_path) or not os.path.exists(orig_image_path):
            print(f"[!] Warning: Missing files for Scene {idx} (Audio: {scene['audio_file']}, Image: {scene['panel_file']}). Skipping.")
            continue

        try:
            audio_clip = AudioFileClip(audio_path)
            duration = audio_clip.duration

            gen = SceneFrameGenerator(orig_image_path, scene.get("text", ""), duration, idx)
            img_clip = VideoClip(gen.make_frame).with_duration(duration)
            img_clip = img_clip.with_audio(audio_clip)

            video_clips.append(img_clip)
            print(f"[+] Loaded scene {idx}: {scene['panel_file']} paired with {scene['audio_file']} ({duration:.2f}s)")

        except Exception as e:
            print(f"[!] Error building clip {idx}: {e}")

    if not video_clips:
        print("[!] No clips were successfully generated. Aborting render.")
        return

    print("[*] All scenes loaded. Stitching timeline together...")
    final_video = concatenate_videoclips(video_clips, method="compose")

    # Dynamic BGM looping and mixing if a background music file exists in the directory
    bgm_path = None
    for filename in ["bgm.mp3", "background.mp3", "bgm.wav"]:
        if os.path.exists(filename):
            bgm_path = filename
            break

    if bgm_path:
        print(f"[*] Found background music track: {bgm_path}")
        try:
            bgm_clip = AudioFileClip(bgm_path).with_volume_scaled(0.12).loop(duration=final_video.duration)
            combined_audio = CompositeAudioClip([final_video.audio, bgm_clip])
            final_video = final_video.with_audio(combined_audio)
            print("[*] Successfully mixed BGM track with video audio.")
        except Exception as bgm_err:
            print(f"[!] Error mixing BGM: {bgm_err}")

    print("[*] Rendering video...")

    try:
        print("[*] Attempting NVIDIA GPU hardware acceleration (h264_nvenc)...")
        final_video.write_videofile(
            video_out,
            fps=fps,
            codec="h264_nvenc",
            audio_codec="aac",
            threads=24,
            preset="fast"
        )
        print(f"\n[*] SUCCESS: Final recap video rendered at {video_out}")

    except Exception as e:
        print(f"\n[!] Render Error using NVENC: {e}")
        print("[*] Falling back to standard CPU rendering (libx264)...")
        final_video.write_videofile(
            video_out,
            fps=fps,
            codec="libx264",
            audio_codec="aac",
            threads=24,
            preset="ultrafast"
        )
        print(f"\n[*] SUCCESS: Final recap video rendered at {video_out}")


if __name__ == "__main__":
    assemble_video()