import os
import json
import re
import math
from openai import OpenAI

SCRIPT_PATH = r"C:\Users\User\PycharmProjects\pythonProject2\script.txt"
CATALOG_PATH = r"C:\Users\User\PycharmProjects\pythonProject2\scene_catalog.json"
TIMELINE_OUT_PATH = r"C:\Users\User\PycharmProjects\pythonProject2\timeline_map.json"
client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")


def load_data():
    if not os.path.exists(SCRIPT_PATH) or not os.path.exists(CATALOG_PATH):
        raise FileNotFoundError("Missing script.txt or scene_catalog.json.")
    with open(SCRIPT_PATH, 'r', encoding='utf-8') as f:
        script_lines = [line.strip() for line in f.readlines() if line.strip()]
    with open(CATALOG_PATH, 'r', encoding='utf-8') as f:
        scene_catalog = json.load(f)
    return script_lines, scene_catalog


def fallback_proportional_mapping(script_lines, scene_catalog):
    print("\n[*] Triggering proportional mathematical fallback mapping...")
    timeline = []
    num_lines = len(script_lines)
    num_panels = len(scene_catalog)
    for i in range(num_lines):
        panel_idx = min(math.floor((i / num_lines) * num_panels), num_panels - 1)
        timeline.append({
            "audio_file": f"line_{i:03d}.wav",
            "text": script_lines[i],
            "panel_file": scene_catalog[panel_idx]["panel_file"]
        })
    return timeline


def extract_json_from_text(text):
    """Clean reasoning tags and extract JSON blocks from model outputs."""
    # Strip <think>...</think> tags if present
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    
    # Try finding markdown code block: ```json ... ```
    match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, flags=re.DOTALL)
    if match:
        return match.group(1).strip()
        
    # Find first opening bracket '[' and last closing bracket ']'
    match_arr = re.search(r'\[\s*\{.*\}\s*\]', text, flags=re.DOTALL)
    if match_arr:
        return match_arr.group(0).strip()
        
    return text.strip()


def run_mapping():
    print("[*] Starting Phase 3: Timeline Mapping (Batched)...")
    try:
        script_lines, scene_catalog = load_data()
    except Exception as e:
        print(f"[!] Error loading inputs: {e}")
        return

    batch_size = 5
    timeline = []
    
    print(f"[*] Processing {len(script_lines)} lines in batches of {batch_size}...")
    
    for start_idx in range(0, len(script_lines), batch_size):
        end_idx = min(start_idx + batch_size, len(script_lines))
        batch_lines = script_lines[start_idx:end_idx]
        
        batch_manifest = []
        for i, line in enumerate(batch_lines):
            global_idx = start_idx + i
            batch_manifest.append({
                "audio_file": f"line_{global_idx:03d}.wav",
                "text": line
            })
            
        prompt = (
            "You are an expert Anime/Manga Recap Video Director.\n"
            "Align each narration audio file with the single best corresponding image panel based on their visual descriptions.\n"
            "Output must be a valid JSON array of objects, where each object has exactly these keys:\n"
            "  - 'audio_file': the filename of the audio segment (e.g., 'line_000.wav')\n"
            "  - 'panel_file': the filename of the matching manga panel (e.g., '002_p1.png')\n\n"
            "Do NOT include any reasons, explanations, or extra fields in the objects. "
            "Output ONLY the JSON list inside a ```json ... ``` block.\n\n"
            f"AVAILABLE INPUTS:\n"
            f"Visual Catalog: {json.dumps(scene_catalog, indent=2)}\n\n"
            f"Audio Segments Manifest: {json.dumps(batch_manifest, indent=2)}"
        )
        
        batch_timeline = None
        try:
            print(f"[*] Sending batch {start_idx // batch_size + 1} ({start_idx} to {end_idx - 1}) to Gemma...")
            response = client.chat.completions.create(
                model="google/gemma-4-e4b",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=1500  # Ample room for 5 output items
            )
            
            raw_response = response.choices[0].message.content.strip()
            cleaned_json = extract_json_from_text(raw_response)
            
            try:
                batch_timeline = json.loads(cleaned_json)
                if isinstance(batch_timeline, list):
                    # Key normalization to handle LLM variations
                    for item in batch_timeline:
                        if "audio_file" not in item:
                            for k in ["audio", "file", "audio_path"]:
                                if k in item:
                                    item["audio_file"] = item[k]
                                    break
                        if "panel_file" not in item:
                            for k in ["panel", "image_file", "image", "image_path", "panel_path"]:
                                if k in item:
                                    item["panel_file"] = item[k]
                                    break
                    print(f"[*] Batch {start_idx // batch_size + 1} mapped successfully.")
                else:
                    print(f"[!] Warning: Batch response is not a list.")
                    batch_timeline = None
            except Exception as parse_err:
                print(f"[!] Batch JSON parsing failed: {parse_err}")
                batch_timeline = None
                
        except Exception as e:
            print(f"[!] Batch LLM call failed: {e}")
            batch_timeline = None
            
        # Local batch fallback if LLM mapping failed
        if not batch_timeline:
            print(f"[*] Using proportional fallback for batch {start_idx // batch_size + 1}...")
            batch_timeline = []
            num_panels = len(scene_catalog)
            for i, line in enumerate(batch_lines):
                global_idx = start_idx + i
                panel_idx = min(math.floor((global_idx / len(script_lines)) * num_panels), num_panels - 1)
                batch_timeline.append({
                    "audio_file": f"line_{global_idx:03d}.wav",
                    "text": line,
                    "panel_file": scene_catalog[panel_idx]["panel_file"]
                })
                
        timeline.extend(batch_timeline)

    # Post-process: ensure complete gap-filling/hold-frame for any missing global files
    llm_map = {item["audio_file"]: item["panel_file"] for item in timeline if "audio_file" in item and "panel_file" in item}
    complete_timeline = []
    last_valid_panel = scene_catalog[0]["panel_file"] if scene_catalog else None
    
    for i, line in enumerate(script_lines):
        audio_file = f"line_{i:03d}.wav"
        if audio_file in llm_map:
            panel_file = llm_map[audio_file]
            last_valid_panel = panel_file
        else:
            if last_valid_panel:
                panel_file = last_valid_panel
            else:
                panel_idx = min(math.floor((i / len(script_lines)) * len(scene_catalog)), len(scene_catalog) - 1)
                panel_file = scene_catalog[panel_idx]["panel_file"]
                last_valid_panel = panel_file
        
        complete_timeline.append({
            "audio_file": audio_file,
            "text": line,
            "panel_file": panel_file
        })
        
    timeline = complete_timeline
    print(f"[*] Successfully aligned and gap-filled all {len(timeline)} scenes.")
    
    # Save output map
    try:
        with open(TIMELINE_OUT_PATH, 'w', encoding='utf-8') as f:
            json.dump(timeline, f, indent=4)
        print(f"[*] Timeline saved to {TIMELINE_OUT_PATH}")
    except Exception as e:
        print(f"[!] Error saving timeline: {e}")


if __name__ == "__main__":
    run_mapping()