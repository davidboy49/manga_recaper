import os
import json
import phase4_video

# Load full timeline
full_timeline = phase4_video.load_timeline()

# Slice to just first 2 scenes for a quick test
short_timeline = full_timeline[:2]

# Override the timeline loading function and output video path
phase4_video.load_timeline = lambda: short_timeline
phase4_video.VIDEO_OUT = r"C:\Users\User\PycharmProjects\pythonProject2\test_recap_video.mp4"

print("[*] Running test rendering for short video (first 2 scenes)...")
phase4_video.assemble_video()
print("[*] Test rendering complete!")
