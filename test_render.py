import os
import json
import argparse
import phase4_video

def main():
    parser = argparse.ArgumentParser(description="Test render script")
    parser.add_argument("-t", "--timeline", default="timeline_map.json", help="Timeline JSON path")
    parser.add_argument("-p", "--panels", default="manga_panels", help="Panels folder path")
    parser.add_argument("-a", "--audio-dir", default="generated_audio", help="Audio clips folder path")
    parser.add_argument("-o", "--output", default="test_recap_video.mp4", help="Output path")
    parser.add_argument("-f", "--fps", type=int, default=30, help="Output video FPS")
    args = parser.parse_args()

    # Load full timeline from specified path
    full_timeline = phase4_video.load_timeline(args.timeline)
    short_timeline = full_timeline[:2]

    # Temporarily save a short timeline to match the test request
    test_timeline_path = "test_timeline_temp.json"
    with open(test_timeline_path, 'w', encoding='utf-8') as f:
        json.dump(short_timeline, f, indent=4)

    print("[*] Running test rendering for short video (first 2 scenes)...")
    phase4_video.assemble_video(
        timeline_path=test_timeline_path,
        image_dir=args.panels,
        audio_dir=args.audio_dir,
        video_out=args.output,
        fps=args.fps
    )
    
    # Cleanup temp timeline
    if os.path.exists(test_timeline_path):
        os.remove(test_timeline_path)
        
    print("[*] Test rendering complete!")

if __name__ == "__main__":
    main()
