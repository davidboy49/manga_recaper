Context Seed for Local Manga/Anime Recap Automation Project
Copy and paste this entire document as your first message in a new session to fully restore the environment context, hardware profiles, path settings, and complete codebase.
1. Project Overview & Workflow Goals
The goal of this project is to build an automated, fully local, private content pipeline that converts an anime/manga story script and a folder of images (panels) into a finished, narrative recap video (.mp4) with smooth panning/zooming visual movements.
The production engine executes a strict 4-Phase Sequence:
1. Phase 1: Local TTS Voiceovers — Reads script.txt line-by-line and generates natural, human-sounding narrative audio tracks (.wav) via the offline Kokoro-82M model.
2. Phase 2: Visual Catalog Extraction — Loops over manga panels sequentially, encodes them to base64, and feeds them into local Gemma Vision (via LM Studio) to extract high-fidelity action descriptions of what is happening in each scene.
3. Phase 3: Automated Timeline Mapping — Feeds the script lines and visual scene catalog to Gemma's reasoning layer to create a matched mapping blueprint (pairing the best narration file to the most visually appropriate image panel). Includes robust regex filters to strip strict local model guardrail conversational prefixes and outputs clean JSON. Also includes a crash-proof mathematical proportional mapping fallback if context size crashes occur.
4. Phase 4: Multi-Threaded GPU Video Assembly — Reads the matched JSON timeline, matches image durations directly to local audio lengths, applies Ken Burns-style zoom/pan transitions, stitches everything sequentially, and renders a high-quality output using NVIDIA hardware acceleration.
2. Hardware Architecture & System Environment
* GPU: NVIDIA GeForce RTX 4060 Ti (8GB VRAM) — Used for LM Studio (Gemma Vision/Reasoning), PyTorch-accelerated CUDA execution for Kokoro TTS, and video rendering.
* CPU: 13th Gen Intel Core i7-13700KF (24 CPUs, ~3.4GHz) — Leveraged for multithreaded processing throughout the composition phase.
* RAM: 32768MB (32GB)
* OS: Windows 11 Pro 64-bit
* Workspace Paths (Absolute Windows Targets):
   * Image Source Folder: C:\Users\User\PycharmProjects\pythonProject2\manga_panels
   * Input Script: C:\Users\User\PycharmProjects\pythonProject2\script.txt
   * Video Output: C:\Users\User\PycharmProjects\pythonProject2\final_recap_video.mp4
   * Generated Soundclips Folder: C:\Users\User\PycharmProjects\pythonProject2\generated_audio
3. Local Software Configurations
1. LM Studio: Exposing an OpenAI-compatible API on port 1234. Context window (n_ctx) should be set to 8192 or 16384 under Hardware Settings to prevent prompt token size overflow boundaries. GPU offload turned on, claiming roughly 4.5–5GB of VRAM.
2. Virtual Environment Setup (pip commands):
pip install openai kokoro soundfile moviepy tqdm huggingface_hub python-dotenv
# Install CUDA-Accelerated PyTorch for the RTX 4060 Ti:
pip install torch torchvision torchaudio --index-url [https://download.pytorch.org/whl/cu121](https://download.pytorch.org/whl/cu121)