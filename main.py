import os
import sys
import argparse
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

# Import our phase modules
import phase1_tts
import phase2_vision
import phase3_mapping
import phase4_video


def run_pipeline(args):
    print("==================================================")
    print("MANGA/ANIME RECAP AUTOMATION WORKFLOW ORCHESTRATOR")
    print("==================================================")
    print(f"[*] Configuration:")
    print(f"    - Input Script: {args.script}")
    print(f"    - Panels Directory: {args.panels}")
    print(f"    - Generated Audio Directory: {args.audio_dir}")
    print(f"    - Scene Catalog Output: {args.catalog}")
    print(f"    - Timeline Blueprint: {args.timeline}")
    print(f"    - Video Output: {args.output}")
    print(f"    - API URL: {args.api_url}")
    print(f"    - Model Name: {args.model}")
    print(f"    - Render Frame Rate: {args.fps} FPS")
    # Mask API key for logs
    masked_key = (args.api_key[:6] + "..." + args.api_key[-4:]) if len(args.api_key) > 10 else args.api_key
    print(f"    - API Key: {masked_key}")
    print("==================================================")

    # Phase 1: Local TTS Voiceovers
    print("\n[PHASE 1] Executing Local TTS Voiceovers...")
    phase1_tts.generate_voiceovers(script_path=args.script, audio_out_dir=args.audio_dir)

    # Phase 2: Visual Catalog Extraction
    print("\n[PHASE 2] Executing Visual Catalog Extraction...")
    phase2_vision.process_panels(
        image_dir=args.panels, 
        catalog_out_path=args.catalog, 
        api_url=args.api_url,
        api_key=args.api_key,
        model=args.model
    )

    # Phase 3: Automated Timeline Mapping
    print("\n[PHASE 3] Executing Automated Timeline Mapping...")
    phase3_mapping.run_mapping(
        script_path=args.script, 
        catalog_path=args.catalog, 
        timeline_out_path=args.timeline, 
        api_url=args.api_url,
        api_key=args.api_key,
        model=args.model
    )

    # Phase 4: Multi-Threaded Video Assembly
    print("\n[PHASE 4] Executing Video Assembly...")
    phase4_video.assemble_video(
        timeline_path=args.timeline,
        image_dir=args.panels,
        audio_dir=args.audio_dir,
        video_out=args.output,
        fps=args.fps
    )

    print("\n==================================================")
    print("AUTOMATION WORKFLOW COMPLETION CHECK")
    print("==================================================")
    if os.path.exists(args.output):
        print(f"[SUCCESS] Final recap video is ready at: {args.output}")
    else:
        print("[FAILURE] Pipeline completed, but output video was not found.")


def main():
    parser = argparse.ArgumentParser(description="Manga/Anime Recap Automation Orchestrator")
    parser.add_argument("-s", "--script", default="script.txt", help="Path to script.txt")
    parser.add_argument("-p", "--panels", default="manga_panels", help="Path to manga panels directory")
    parser.add_argument("-a", "--audio-dir", default="generated_audio", help="Directory for generated sound clips")
    parser.add_argument("-c", "--catalog", default="scene_catalog.json", help="Path to save scene catalog json")
    parser.add_argument("-t", "--timeline", default="timeline_map.json", help="Path to save timeline map json")
    parser.add_argument("-o", "--output", default="final_recap_video.mp4", help="Path to output recap video mp4")
    parser.add_argument("-f", "--fps", type=int, default=30, help="Output video FPS (default: 30)")
    parser.add_argument("--api-url", default="http://localhost:1234/v1", help="OpenAI-compatible API base URL")
    
    # Check environment variable overrides for api key
    default_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY") or "lm-studio"
    parser.add_argument("-k", "--api-key", default=default_key, help="API key (defaults to OPENROUTER_API_KEY or OPENAI_API_KEY env vars)")
    parser.add_argument("-m", "--model", default="google/gemma-4-e4b", help="Model name to query (e.g. google/gemma-4-26b-a4b-it:free)")

    args = parser.parse_args()
    run_pipeline(args)


if __name__ == "__main__":
    main()