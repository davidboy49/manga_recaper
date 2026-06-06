import os
import re
import torch
import soundfile as sf
import numpy as np
from kokoro import KPipeline
from tqdm import tqdm

# --- Absolute Paths from Context ---
SCRIPT_PATH = r"C:\Users\User\PycharmProjects\pythonProject2\script.txt"
AUDIO_OUT_DIR = r"C:\Users\User\PycharmProjects\pythonProject2\generated_audio"


def ensure_directories(audio_out_dir):
    """Ensure output directories exist."""
    os.makedirs(audio_out_dir, exist_ok=True)


def load_script(path):
    """Read the script and split into individual sentences."""
    with open(path, 'r', encoding='utf-8') as f:
        paragraphs = [line.strip() for line in f.readlines() if line.strip()]
    
    # Regex to split paragraphs by sentence-ending punctuation (., !, ?) followed by whitespace
    sentence_endings = re.compile(r'(?<=[.!?])\s+')
    sentences = []
    for para in paragraphs:
        for s in sentence_endings.split(para):
            if s.strip():
                sentences.append(s.strip())
    return sentences


def generate_voiceovers(script_path=None, audio_out_dir=None, voice=None, speed=None):
    if script_path is None:
        script_path = SCRIPT_PATH
    if audio_out_dir is None:
        audio_out_dir = AUDIO_OUT_DIR

    # Load defaults from config.json if available
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    if voice is None or speed is None:
        import json
        loaded_voice = "af_heart"
        loaded_speed = 1.0
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    loaded_voice = config_data.get("tts_voice", loaded_voice)
                    loaded_speed = float(config_data.get("tts_speed", loaded_speed))
            except Exception:
                pass
        if voice is None:
            voice = loaded_voice
        if speed is None:
            speed = loaded_speed

    ensure_directories(audio_out_dir)

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
    if not os.path.exists(script_path):
        print(f"[!] Error: Script not found at {script_path}")
        return

    script_lines = load_script(script_path)
    print(f"[*] Found {len(script_lines)} lines in script: {script_path}")

    # 3. Process each line
    print(f"[*] Starting Phase 1: TTS Generation (Voice: {voice}, Speed: {speed})...")
    for i, text in enumerate(tqdm(script_lines, desc="Generating Audio")):
        try:
            # generator yields (graphemes, phonemes, audio_chunk)
            generator = pipeline(text, voice=voice, speed=speed)

            all_audio = []
            for graphemes, phonemes, audio_chunk in generator:
                all_audio.append(audio_chunk)

            # If the pipeline successfully generated audio
            if all_audio:
                # Concatenate chunks (in case long lines were split by KPipeline)
                final_audio = np.concatenate(all_audio)

                # Format output filename (e.g., line_001.wav)
                output_filename = os.path.join(audio_out_dir, f"line_{i:03d}.wav")

                # Save via soundfile (Kokoro operates at 24000 Hz)
                sf.write(output_filename, final_audio, 24000)

        except Exception as e:
            print(f"\n[!] Error generating audio for line {i}: {text}")
            print(f"Error details: {e}")


if __name__ == "__main__":
    generate_voiceovers()
    print("[*] Phase 1 Complete. Audio files are ready for timeline mapping.")