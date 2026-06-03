import os
import sys

# Import our phase modules
import phase1_tts
import phase2_vision
import phase3_mapping
import phase4_video


def run_pipeline():
    print("==================================================")
    print("MANGA/ANIME RECAP AUTOMATION WORKFLOW ORCHESTRATOR")
    print("==================================================")

    # Phase 1: Local TTS Voiceovers
    print("\n[PHASE 1] Executing Local TTS Voiceovers...")
    phase1_tts.generate_voiceovers()

    # Phase 2: Visual Catalog Extraction
    print("\n[PHASE 2] Executing Visual Catalog Extraction...")
    phase2_vision.process_panels()

    # Phase 3: Automated Timeline Mapping
    print("\n[PHASE 3] Executing Automated Timeline Mapping...")
    phase3_mapping.run_mapping()

    # Phase 4: Multi-Threaded Video Assembly
    print("\n[PHASE 4] Executing Video Assembly...")
    phase4_video.assemble_video()

    print("\n==================================================")
    print("AUTOMATION WORKFLOW COMPLETION CHECK")
    print("==================================================")
    video_out = phase4_video.VIDEO_OUT
    if os.path.exists(video_out):
        print(f"[SUCCESS] Final recap video is ready at: {video_out}")
    else:
        print("[FAILURE] Pipeline completed, but output video was not found.")


if __name__ == "__main__":
    run_pipeline()