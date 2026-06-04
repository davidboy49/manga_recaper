import os
import base64
import json
import io
from PIL import Image
from openai import OpenAI
from tqdm import tqdm

# --- Absolute Paths from Context ---
IMAGE_DIR = r"C:\Users\User\PycharmProjects\pythonProject2\manga_panels"
CATALOG_OUT_PATH = r"C:\Users\User\PycharmProjects\pythonProject2\scene_catalog.json"



def encode_image(image_path):
    """Resize image if too large and convert to a base64 string."""
    max_size = 1024  # Standard max size for vision LLMs to prevent HTTP payload overhead
    try:
        with Image.open(image_path) as img:
            file_size = os.path.getsize(image_path)
            # If image exceeds max dimensions or is larger than 1MB, resize it
            if img.width > max_size or img.height > max_size or file_size > 1024 * 1024:
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                
                # Convert back to RGB if necessary (e.g. if RGBA/PNG)
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                    
                # Save to BytesIO as JPEG
                buffered = io.BytesIO()
                img.save(buffered, format="JPEG", quality=85)
                return base64.b64encode(buffered.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"[!] Warning: failed to resize image {image_path}: {e}. Falling back to raw file.")

    # Fallback to raw file encoding
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def process_panels(image_dir=None, catalog_out_path=None, api_url="http://localhost:1234/v1", api_key="lm-studio", model="google/gemma-4-e4b"):
    if image_dir is None:
        image_dir = IMAGE_DIR
    if catalog_out_path is None:
        catalog_out_path = CATALOG_OUT_PATH

    client = OpenAI(base_url=api_url, api_key=api_key)

    if not os.path.exists(image_dir):
        print(f"[!] Error: Image directory not found at {image_dir}")
        return

    # Grab supported images and sort them so they stay in chronological order
    valid_ext = ('.png', '.jpg', '.jpeg', '.webp')
    image_files = sorted([f for f in os.listdir(image_dir) if f.lower().endswith(valid_ext)])

    if not image_files:
        print(f"[!] No images found in {image_dir}")
        return

    # Load existing catalog for caching/checkpointing
    scene_catalog = {}
    if os.path.exists(catalog_out_path):
        try:
            with open(catalog_out_path, 'r', encoding='utf-8') as f:
                existing_list = json.load(f)
                # Filter out default placeholder texts and error descriptions to force reprocessing
                for item in existing_list:
                    desc = item.get("description", "")
                    # If description contains error patterns or is too short or is a placeholder, skip
                    if (desc and 
                        desc != "Action scene action marker." and 
                        "Please provide the manga panel image" not in desc and
                        len(desc.strip()) > 10):
                        scene_catalog[item["panel_file"]] = desc
            print(f"[*] Loaded {len(scene_catalog)} valid existing descriptions from {catalog_out_path}")
        except Exception as e:
            print(f"[!] Error reading existing catalog: {e}. Starting fresh.")

    print(f"[*] Found {len(image_files)} panels. Starting Phase 2: Visual Extraction...")

    # We will save checkpoint on each processed image to prevent data loss
    for img_name in tqdm(image_files, desc="Processing Panels"):
        if img_name in scene_catalog:
            continue

        img_path = os.path.join(image_dir, img_name)
        base64_image = encode_image(img_path)

        try:
            # Send the base64 image to local Gemma Vision via LM Studio
            response = client.chat.completions.create(
                model=model,  # Use the specified model
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text",
                             "text": "Describe the core action, characters, and emotion in this manga panel concisely. Focus strictly on visual facts."},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                temperature=0.2,  # Keep the model highly factual and less creative
                max_tokens=1000
            )

            description = response.choices[0].message.content.strip()
            scene_catalog[img_name] = description

        except Exception as e:
            print(f"\n[!] Error processing {img_name}: {e}")
            scene_catalog[img_name] = "Action scene action marker."

        # Save checkpoint immediately
        try:
            output_list = [{"panel_file": k, "description": v} for k, v in sorted(scene_catalog.items())]
            with open(catalog_out_path, 'w', encoding='utf-8') as f:
                json.dump(output_list, f, indent=4)
        except Exception as checkpoint_err:
            print(f"[!] Error saving checkpoint: {checkpoint_err}")

    # Final write to confirm everything is sorted and formatted
    output_list = [{"panel_file": k, "description": v} for k, v in sorted(scene_catalog.items())]
    with open(catalog_out_path, 'w', encoding='utf-8') as f:
        json.dump(output_list, f, indent=4)

    print(f"\n[*] Phase 2 Complete. Scene catalog saved to {catalog_out_path}")


if __name__ == "__main__":
    process_panels()