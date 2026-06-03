import os
import torch
import soundfile as sf
import numpy as np
from kokoro import KPipeline
from tqdm import tqdm

# --- Absolute Paths from Context ---
SCRIPT_PATH = r"C:\Users\User\PycharmProjects\pythonProject2\script.txt"
AUDIO_OUT_DIR = r"C:\Users\User\PycharmProjects\pythonProject2\generated_audio"


def ensure_directories():
    """Ensure output directories exist."""
    os.makedirs(AUDIO_OUT_DIR, exist_ok=True)


def load_script(path):
    """Read the script line-by-line, ignoring empty lines."""
    with open(path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
    return lines


def generate_voiceovers():
    ensure_directories()

    # 1. Check CUDA availability for RTX 4060 Ti
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"[*] Initializing Kokoro TTS Pipeline on device: {device.upper()}")

    try:
        # Initialize the pipeline for American English ('a')
        pipeline = KPipeline(lang_code='a')
    except Exception as e:
        print(f"[!] Error initializing Kokoro Pipeline. (Are you missing espeak-ng?): {e}")
        return

    # 2. Load the script
    if not os.path.exists(SCRIPT_PATH):
        print(f"[!] Error: Script not found at {SCRIPT_PATH}")
        return

    script_lines = load_script(SCRIPT_PATH)
    print(f"[*] Found {len(script_lines)} lines in script.txt")

    # 3. Process each line
    print("[*] Starting Phase 1: TTS Generation...")
    for i, text in enumerate(tqdm(script_lines, desc="Generating Audio")):
        try:
            # generator yields (graphemes, phonemes, audio_chunk)
            generator = pipeline(text, voice='af_heart', speed=1.0)

            all_audio = []
            for graphemes, phonemes, audio_chunk in generator:
                all_audio.append(audio_chunk)

            # If the pipeline successfully generated audio
            if all_audio:
                # Concatenate chunks (in case long lines were split by KPipeline)
                final_audio = np.concatenate(all_audio)

                # Format output filename (e.g., line_001.wav)
                output_filename = os.path.join(AUDIO_OUT_DIR, f"line_{i:03d}.wav")

                # Save via soundfile (Kokoro operates at 24000 Hz)
                sf.write(output_filename, final_audio, 24000)

        except Exception as e:
            print(f"\n[!] Error generating audio for line {i}: {text}")
            print(f"Error details: {e}")


if __name__ == "__main__":
    generate_voiceovers()
    print("[*] Phase 1 Complete. Audio files are ready for timeline mapping.")