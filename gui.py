import os
import sys

# Redirection of standard streams to prevent loguru failure in windowed/noconsole mode
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

import json
import threading
import winsound
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image
import customtkinter

# Import our existing pipeline phases
import phase1_tts
import phase2_vision
import phase4_video
from phase3_mapping import get_cosine_similarity, align_timeline

# Expose LM Studio configurations
API_URL = "http://localhost:1234/v1"
API_KEY = "lm-studio"
MODEL_NAME = "google/gemma-4-e4b"

class MangaRecapEditorApp(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        # Configure window
        self.title("Manga Recap Storyboard Editor")
        self.geometry("1200x880")
        self.minsize(980, 700)

        # Set theme colors to match modern dark styling
        customtkinter.set_appearance_mode("dark")
        customtkinter.set_default_color_theme("blue")

        # Workspace paths and active state
        self.workspace_dir = r"C:\Users\User\PycharmProjects\pythonProject2"
        self.current_panels_dir = os.path.join(self.workspace_dir, "manga_panels")
        
        # Fallback to manga_panel_2 if default manga_panels doesn't exist
        if not os.path.exists(self.current_panels_dir):
            fallback_dir = os.path.join(self.workspace_dir, "manga_panel_2")
            if os.path.exists(fallback_dir):
                self.current_panels_dir = fallback_dir
                
        self.audio_dir = os.path.join(self.workspace_dir, "generated_audio")
        self.split_dir = os.path.join(self.workspace_dir, "split_scenes")
        
        # Ensure audio and split directories exist
        os.makedirs(self.audio_dir, exist_ok=True)
        os.makedirs(self.split_dir, exist_ok=True)

        # Storyboard State
        self.storyboard_items = []
        self.thumbnails = {}
        self.script_sentences = []
        self.cancel_flag = False

        # Load settings
        self.load_settings()

        # Build GUI Layout
        self.build_ui()

        # Startup status
        self.set_status("Ready. Please click 'Load Folder' or 'Load Files' to import panels.")

    def load_settings(self):
        """Loads VLM API, Voice, and Render settings from config.json if it exists."""
        config_path = os.path.join(self.workspace_dir, "config.json")
        self.api_url = "http://localhost:1234/v1"
        self.api_key = "lm-studio"
        self.model_name = "google/gemma-4-e4b"
        self.provider = "LM Studio"
        self.tts_voice = "af_heart"
        self.tts_speed = 1.0
        self.render_quality = "720p (HD)"
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    self.api_url = config_data.get("api_url", self.api_url)
                    self.api_key = config_data.get("api_key", self.api_key)
                    self.model_name = config_data.get("model_name", self.model_name)
                    self.provider = config_data.get("provider", self.provider)
                    self.tts_voice = config_data.get("tts_voice", self.tts_voice)
                    self.tts_speed = float(config_data.get("tts_speed", self.tts_speed))
                    self.render_quality = config_data.get("render_quality", self.render_quality)
            except Exception as e:
                print(f"Failed to load settings: {e}")

    def save_settings(self):
        """Persists VLM API, Voice, and Render settings to config.json."""
        config_path = os.path.join(self.workspace_dir, "config.json")
        try:
            # Safely check widget availability in case save_settings is triggered during construction
            voice_val = self.opt_voice.get() if hasattr(self, "opt_voice") else getattr(self, "tts_voice", "af_heart")
            speed_val = self.sld_speed.get() if hasattr(self, "sld_speed") else getattr(self, "tts_speed", 1.0)
            quality_val = self.opt_quality.get() if hasattr(self, "opt_quality") else getattr(self, "render_quality", "720p (HD)")
            
            config_data = {
                "api_url": self.ent_url.get().strip() if hasattr(self, "ent_url") else getattr(self, "api_url", "http://localhost:1234/v1"),
                "api_key": self.ent_key.get().strip() if hasattr(self, "ent_key") else getattr(self, "api_key", "lm-studio"),
                "model_name": self.ent_model.get().strip() if hasattr(self, "ent_model") else getattr(self, "model_name", "google/gemma-4-e4b"),
                "provider": self.opt_provider.get() if hasattr(self, "opt_provider") else getattr(self, "provider", "LM Studio"),
                "tts_voice": voice_val,
                "tts_speed": speed_val,
                "render_quality": quality_val
            }
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4)
        except Exception as e:
            print(f"Failed to save settings: {e}")

    def clear_audio_directory(self):
        """Deletes all WAV audio files in the generated_audio directory to prevent old voice clips from being reused."""
        try:
            if os.path.exists(self.audio_dir):
                count = 0
                for filename in os.listdir(self.audio_dir):
                    if filename.endswith(".wav"):
                        file_path = os.path.join(self.audio_dir, filename)
                        try:
                            if os.path.isfile(file_path):
                                os.remove(file_path)
                                count += 1
                        except Exception as e:
                            print(f"Failed to delete audio file {file_path}: {e}")
                print(f"[*] Cleared {count} files from generated_audio directory.")
        except Exception as e:
            print(f"Error clearing audio directory: {e}")

    def get_render_dimensions(self):
        """Returns (width, height) based on selected render quality."""
        quality = self.opt_quality.get() if hasattr(self, "opt_quality") else getattr(self, "render_quality", "720p (HD)")
        if "1080p" in quality:
            return 1920, 1080
        elif "480p" in quality:
            return 854, 480
        else:
            return 1280, 720

    def build_ui(self):
        # 1. Sticky Header Frame (Three-row layout for utility controls & API settings)
        self.header_frame = customtkinter.CTkFrame(self, fg_color="#18181b", height=195, corner_radius=0)
        self.header_frame.pack(fill="x", side="top")
        self.header_frame.pack_propagate(False)

        # Style tokens
        btn_color = "#2563eb"
        btn_hover = "#1d4ed8"
        sec_btn_color = "#3f3f46"
        sec_btn_hover = "#52525b"
        warn_btn_color = "#991b1b"
        warn_btn_hover = "#7f1d1d"

        # --- ROW 1: Import & Modify Operations ---
        self.row1_frame = customtkinter.CTkFrame(self.header_frame, fg_color="transparent")
        self.row1_frame.pack(fill="x", padx=15, pady=(10, 5))

        # Load Folder Button
        self.btn_load_folder = customtkinter.CTkButton(
            self.row1_frame, 
            text="Load Folder", 
            command=self.load_chapter_dialog,
            fg_color=btn_color,
            hover_color=btn_hover,
            font=("Outfit", 12, "bold"),
            corner_radius=6
        )
        self.btn_load_folder.pack(side="left", padx=5)

        # Load Files Button
        self.btn_load_files = customtkinter.CTkButton(
            self.row1_frame, 
            text="Load Files", 
            command=self.load_files_dialog,
            fg_color=btn_color,
            hover_color=btn_hover,
            font=("Outfit", 12, "bold"),
            corner_radius=6
        )
        self.btn_load_files.pack(side="left", padx=5)

        # Upload Script Button
        self.btn_upload_script = customtkinter.CTkButton(
            self.row1_frame, 
            text="Upload Script", 
            command=self.upload_script_file,
            fg_color=btn_color,
            hover_color=btn_hover,
            font=("Outfit", 12, "bold"),
            corner_radius=6
        )
        self.btn_upload_script.pack(side="left", padx=5)

        # AI Match Script Button
        self.btn_ai_match = customtkinter.CTkButton(
            self.row1_frame, 
            text="AI Match Script", 
            command=self.run_ai_matching,
            fg_color="#0891b2",
            hover_color="#0e7490",
            font=("Outfit", 12, "bold"),
            corner_radius=6
        )
        self.btn_ai_match.pack(side="left", padx=5)

        # Select/Deselect All Toggle
        self.btn_select_all = customtkinter.CTkButton(
            self.row1_frame, 
            text="Select All", 
            width=90,
            command=self.toggle_select_all,
            fg_color=sec_btn_color,
            hover_color=sec_btn_hover,
            font=("Outfit", 12),
            corner_radius=6
        )
        self.btn_select_all.pack(side="left", padx=5)

        # Remove Selected Button
        self.btn_remove_selected = customtkinter.CTkButton(
            self.row1_frame, 
            text="Remove Selected", 
            command=self.remove_selected_panels,
            fg_color=warn_btn_color,
            hover_color=warn_btn_hover,
            font=("Outfit", 12, "bold"),
            corner_radius=6
        )
        self.btn_remove_selected.pack(side="left", padx=5)

        # Clear All Button
        self.btn_clear_all = customtkinter.CTkButton(
            self.row1_frame, 
            text="Clear All Panels", 
            command=self.clear_all_panels,
            fg_color=warn_btn_color,
            hover_color=warn_btn_hover,
            font=("Outfit", 12, "bold"),
            corner_radius=6
        )
        self.btn_clear_all.pack(side="left", padx=5)

        # Force Stop Button
        self.btn_stop = customtkinter.CTkButton(
            self.row1_frame, 
            text="Force Stop", 
            command=self.confirm_force_stop,
            fg_color="#ea580c", 
            hover_color="#c2410c",
            font=("Outfit", 12, "bold"),
            corner_radius=6
        )
        self.btn_stop.pack(side="left", padx=5)

        # Script Info status label
        self.lbl_script_info = customtkinter.CTkLabel(self.row1_frame, text="Script: [None Loaded]", text_color="#a1a1aa", font=("Outfit", 11))
        self.lbl_script_info.pack(side="right", padx=5)

        # --- ROW 2: Synthesis & Export Actions ---
        self.row2_frame = customtkinter.CTkFrame(self.header_frame, fg_color="transparent")
        self.row2_frame.pack(fill="x", padx=15, pady=4)

        # Export Panels JSON
        self.btn_export_panels = customtkinter.CTkButton(
            self.row2_frame, 
            text="Export Panels", 
            command=self.export_panels_json,
            fg_color=sec_btn_color,
            hover_color=sec_btn_hover,
            font=("Outfit", 12, "bold"),
            corner_radius=6
        )
        self.btn_export_panels.pack(side="left", padx=5)

        # Export Narration TXT
        self.btn_export_narration = customtkinter.CTkButton(
            self.row2_frame, 
            text="Export Narration", 
            command=self.export_narration_txt,
            fg_color=sec_btn_color,
            hover_color=sec_btn_hover,
            font=("Outfit", 12, "bold"),
            corner_radius=6
        )
        self.btn_export_narration.pack(side="left", padx=5)

        # Kokoro-TTS Batch Generation
        self.btn_kokoro = customtkinter.CTkButton(
            self.row2_frame, 
            text="Kokoro-TTS", 
            command=self.run_batch_tts,
            fg_color=sec_btn_color,
            hover_color=sec_btn_hover,
            font=("Outfit", 12, "bold"),
            corner_radius=6
        )
        self.btn_kokoro.pack(side="left", padx=5)

        # Long TTS Button
        self.btn_long_tts = customtkinter.CTkButton(
            self.row2_frame, 
            text="Long TTS", 
            command=self.run_long_tts,
            fg_color=sec_btn_color,
            hover_color=sec_btn_hover,
            font=("Outfit", 12, "bold"),
            corner_radius=6
        )
        self.btn_long_tts.pack(side="left", padx=5)

        # Edge-TTS alternative shortcut
        self.btn_edge = customtkinter.CTkButton(
            self.row2_frame, 
            text="Edge-TTS", 
            command=self.run_edge_tts_not_implemented,
            fg_color=sec_btn_color,
            hover_color=sec_btn_hover,
            font=("Outfit", 12, "bold"),
            corner_radius=6
        )
        self.btn_edge.pack(side="left", padx=5)

        # Video Compositor Button
        self.btn_composite = customtkinter.CTkButton(
            self.row2_frame, 
            text="Video Compositor", 
            command=self.run_video_compositor,
            fg_color=sec_btn_color,
            hover_color=sec_btn_hover,
            font=("Outfit", 12, "bold"),
            corner_radius=6
        )
        self.btn_composite.pack(side="left", padx=5)

        # Export Selected Clips Button
        self.btn_export_selected = customtkinter.CTkButton(
            self.row2_frame, 
            text="Export Selected Clips", 
            command=self.run_export_selected_clips,
            fg_color="#06b6d4",
            hover_color="#0891b2",
            font=("Outfit", 12, "bold"),
            corner_radius=6
        )
        self.btn_export_selected.pack(side="left", padx=5)

        # BGM Selection Control
        self.lbl_bgm = customtkinter.CTkLabel(self.row2_frame, text="BGM: None", text_color="#a1a1aa", font=("Outfit", 11))
        self.lbl_bgm.pack(side="right", padx=5)
        self.btn_select_bgm = customtkinter.CTkButton(
            self.row2_frame,
            text="Set BGM",
            width=70,
            command=self.select_bgm_file,
            fg_color=sec_btn_color,
            hover_color=sec_btn_hover,
            font=("Outfit", 11),
            corner_radius=6
        )
        self.btn_select_bgm.pack(side="right", padx=5)

        # Video Effects Toggle Checkbox
        self.effects_var = tk.BooleanVar(value=True)
        self.chk_effects = customtkinter.CTkCheckBox(
            self.row2_frame,
            text="Video Effects (Ken Burns/Shake)",
            variable=self.effects_var,
            text_color="#e4e4e7",
            font=("Outfit", 11, "bold"),
            fg_color="#0891b2",
            hover_color="#0e7490"
        )
        self.chk_effects.pack(side="right", padx=15)

        # --- ROW 3: API & Model Settings Panel ---
        self.row3_frame = customtkinter.CTkFrame(self.header_frame, fg_color="transparent")
        self.row3_frame.pack(fill="x", padx=15, pady=(4, 8))

        # Provider Selector Dropdown
        lbl_prov = customtkinter.CTkLabel(self.row3_frame, text="VLM API Provider:", font=("Outfit", 11, "bold"), text_color="#38bdf8")
        lbl_prov.pack(side="left", padx=(5, 3))
        self.opt_provider = customtkinter.CTkOptionMenu(
            self.row3_frame,
            values=["Local LM Studio", "OpenAI", "OpenRouter", "Google", "Custom"],
            width=140,
            height=25,
            command=self.on_provider_change,
            font=("Outfit", 11)
        )
        self.opt_provider.pack(side="left", padx=3)
        self.opt_provider.set(self.provider)

        # Endpoint Entry
        lbl_url = customtkinter.CTkLabel(self.row3_frame, text="API URL:", font=("Outfit", 11, "bold"), text_color="#a1a1aa")
        lbl_url.pack(side="left", padx=(10, 3))
        self.ent_url = customtkinter.CTkEntry(self.row3_frame, width=190, height=25, font=("Consolas", 11))
        self.ent_url.pack(side="left", padx=3)
        self.ent_url.insert(0, self.api_url)
        self.ent_url.bind("<KeyRelease>", lambda e: self.save_settings())

        # API Key Entry
        lbl_key = customtkinter.CTkLabel(self.row3_frame, text="API Key:", font=("Outfit", 11, "bold"), text_color="#a1a1aa")
        lbl_key.pack(side="left", padx=(10, 3))
        self.ent_key = customtkinter.CTkEntry(self.row3_frame, width=140, height=25, show="*", font=("Consolas", 11))
        self.ent_key.pack(side="left", padx=3)
        self.ent_key.insert(0, self.api_key)
        self.ent_key.bind("<KeyRelease>", lambda e: self.save_settings())

        # Model Entry
        lbl_model = customtkinter.CTkLabel(self.row3_frame, text="Model Name:", font=("Outfit", 11, "bold"), text_color="#a1a1aa")
        lbl_model.pack(side="left", padx=(10, 3))
        self.ent_model = customtkinter.CTkEntry(self.row3_frame, width=220, height=25, font=("Consolas", 11))
        self.ent_model.pack(side="left", padx=3)
        self.ent_model.insert(0, self.model_name)
        self.ent_model.bind("<KeyRelease>", lambda e: self.save_settings())

        # --- ROW 4: Voice & Audio Settings Panel ---
        self.row4_frame = customtkinter.CTkFrame(self.header_frame, fg_color="transparent")
        self.row4_frame.pack(fill="x", padx=15, pady=(4, 8))

        # Voice Selector Dropdown
        lbl_voice = customtkinter.CTkLabel(self.row4_frame, text="Voice Actor:", font=("Outfit", 11, "bold"), text_color="#38bdf8")
        lbl_voice.pack(side="left", padx=(5, 3))
        self.opt_voice = customtkinter.CTkOptionMenu(
            self.row4_frame,
            values=[
                "af_heart", "af_sky", "af_nova", "af_bella", "af_nicole", "af_sarah", 
                "am_adam", "am_echo", "am_eric", "am_michael", 
                "bf_emma", "bf_isabella", 
                "bm_george", "bm_lewis"
            ],
            width=140,
            height=25,
            command=lambda choice: self.save_settings(),
            font=("Outfit", 11)
        )
        self.opt_voice.pack(side="left", padx=3)
        self.opt_voice.set(self.tts_voice)

        # Speed Slider
        self.lbl_speed = customtkinter.CTkLabel(self.row4_frame, text=f"Voice Speed ({self.tts_speed:.2f}x):", font=("Outfit", 11, "bold"), text_color="#a1a1aa")
        self.lbl_speed.pack(side="left", padx=(15, 3))
        
        def on_speed_change(val):
            formatted_val = f"{float(val):.2f}"
            self.lbl_speed.configure(text=f"Voice Speed ({formatted_val}x):")
            self.save_settings()
            
        self.sld_speed = customtkinter.CTkSlider(
            self.row4_frame,
            from_=0.5,
            to=2.0,
            number_of_steps=30,
            width=200,
            command=on_speed_change
        )
        self.sld_speed.pack(side="left", padx=3, pady=2)
        self.sld_speed.set(self.tts_speed)

        # Render Quality Selector Dropdown
        lbl_quality = customtkinter.CTkLabel(self.row4_frame, text="Render Quality:", font=("Outfit", 11, "bold"), text_color="#38bdf8")
        lbl_quality.pack(side="left", padx=(15, 3))
        self.opt_quality = customtkinter.CTkOptionMenu(
            self.row4_frame,
            values=["1080p (FHD)", "720p (HD)", "480p (SD)"],
            width=120,
            height=25,
            command=lambda choice: self.save_settings(),
            font=("Outfit", 11)
        )
        self.opt_quality.pack(side="left", padx=3)
        self.opt_quality.set(self.render_quality)

        # 2. Main Scrollable Container for Panel Cards
        self.main_scrollable = customtkinter.CTkScrollableFrame(self, fg_color="#121214", corner_radius=0)
        self.main_scrollable.pack(fill="both", expand=True, padx=0, pady=0)

        # 3. Status Bar at the bottom
        self.status_bar = customtkinter.CTkFrame(self, fg_color="#18181b", height=30, corner_radius=0)
        self.status_bar.pack(fill="x", side="bottom")
        self.lbl_status = customtkinter.CTkLabel(self.status_bar, text="Ready", text_color="#a1a1aa", font=("Outfit", 12))
        self.lbl_status.pack(side="left", padx=15, pady=3)

        self.progress_bar = customtkinter.CTkProgressBar(self.status_bar, width=150)
        self.progress_bar.pack(side="right", padx=15, pady=8)
        self.progress_bar.set(0.0)

    def set_status(self, text, progress=None):
        self.lbl_status.configure(text=text)
        if progress is not None:
            self.progress_bar.set(progress)
        else:
            self.progress_bar.set(0.0)

    def on_provider_change(self, choice):
        """Pre-populates fields based on selected API provider."""
        if hasattr(self, "opt_provider") and self.opt_provider.get() != choice:
            self.opt_provider.set(choice)
        self.ent_url.delete(0, "end")
        self.ent_key.delete(0, "end")
        self.ent_model.delete(0, "end")

        if choice == "Local LM Studio":
            self.ent_url.insert(0, "http://localhost:1234/v1")
            self.ent_key.insert(0, "lm-studio")
            self.ent_model.insert(0, "google/gemma-4-e4b")
            self.set_status("Set provider to Local LM Studio.")
        elif choice == "OpenAI":
            self.ent_url.insert(0, "https://api.openai.com/v1")
            # Fallback to env key
            openai_key = os.environ.get("OPENAI_API_KEY", "")
            self.ent_key.insert(0, openai_key)
            self.ent_model.insert(0, "gpt-4o-mini")
            self.set_status("Set provider to OpenAI (GPT-4o-mini).")
        elif choice == "OpenRouter":
            self.ent_url.insert(0, "https://openrouter.ai/api/v1")
            or_key = os.environ.get("OPENROUTER_API_KEY", "")
            self.ent_key.insert(0, or_key)
            self.ent_model.insert(0, "google/gemma-2-9b-it:free")
            self.set_status("Set provider to OpenRouter.")
        elif choice == "Google":
            self.ent_url.insert(0, "https://generativelanguage.googleapis.com/v1beta/openai")
            gemini_key = os.environ.get("GEMINI_API_KEY", "")
            self.ent_key.insert(0, gemini_key)
            self.ent_model.insert(0, "gemini-1.5-flash")
            self.set_status("Set provider to Google (Gemini-1.5-Flash).")
        elif choice == "Custom":
            self.set_status("Custom provider selected. Please enter API details manually.")

        # Save settings on change
        self.save_settings()

    def confirm_force_stop(self):
        """Asks user for confirmation before setting the cancellation flag."""
        if messagebox.askyesno("Confirm Force Stop", "Are you sure you want to stop the active background operation?"):
            self.cancel_flag = True
            self.set_status("Force stop signal sent. Cancelling...")

    def load_existing_catalog(self, directory_path=None):
        """Loads visual descriptions from scene_catalog.json if it exists."""
        catalog_paths = []
        if directory_path:
            catalog_paths.append(os.path.join(directory_path, "scene_catalog.json"))
        catalog_paths.append(os.path.join(self.workspace_dir, "scene_catalog.json"))
        
        catalog = {}
        for path in catalog_paths:
            if os.path.exists(path):
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            for item in data:
                                if "panel_file" in item and "description" in item:
                                    catalog[item["panel_file"]] = item["description"]
                        elif isinstance(data, dict):
                            catalog.update(data)
                    print(f"[*] Loaded {len(catalog)} panel descriptions from {path}")
                    break  # Stop at first successfully loaded catalog
                except Exception as e:
                    print(f"[!] Error loading catalog from {path}: {e}")
        return catalog

    def load_chapter_dialog(self):
        """Opens a directory chooser dialog to load manga panels."""
        selected_dir = filedialog.askdirectory(
            initialdir=self.workspace_dir,
            title="Select Manga Panels Directory"
        )
        if selected_dir:
            self.current_panels_dir = selected_dir
            self.load_panels_from_directory(selected_dir)

    def load_files_dialog(self):
        """Opens a file dialog to select multiple individual panel images."""
        selected_files = filedialog.askopenfilenames(
            initialdir=self.workspace_dir,
            title="Select Manga Panel Images",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.webp")]
        )
        if selected_files:
            # Sort chronologically/alphanumerically
            selected_files = sorted(selected_files)
            self.clear_audio_directory()
            
            # Determine directory of the first file
            first_dir = os.path.dirname(selected_files[0]) if selected_files else None
            catalog = self.load_existing_catalog(first_dir)
            
            # Populate state
            self.storyboard_items = []
            self.thumbnails = {}
            
            for idx, img_path in enumerate(selected_files):
                img_name = os.path.basename(img_path)
                vis_desc = catalog.get(img_name, "")
                self.storyboard_items.append({
                    "panel_file": img_name,
                    "image_path": img_path,
                    "text": "", # Empty not preloaded
                    "visual_description": vis_desc,
                    "audio_file": f"scene_{idx:03d}.wav",
                    "video_file": f"scene_{idx:03d}.mp4",
                    "status": "idle",
                    "selected_var": tk.BooleanVar(value=False)
                })

            self.refresh_timeline()
            self.set_status(f"Successfully loaded {len(self.storyboard_items)} panel files. All textareas cleared.", 0.0)

    def load_panels_from_directory(self, directory_path):
        """Scans directory for panel images and loads them (Textboxes are intentionally kept completely empty)."""
        self.clear_audio_directory()
        self.set_status(f"Scanning directory: {os.path.basename(directory_path)}...")
        
        valid_ext = ('.png', '.jpg', '.jpeg', '.webp')
        try:
            image_files = sorted([f for f in os.listdir(directory_path) if f.lower().endswith(valid_ext)])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to list directory: {e}")
            return

        if not image_files:
            messagebox.showwarning("Warning", f"No panels found in directory:\n{directory_path}")
            self.set_status("No panels found.")
            return

        catalog = self.load_existing_catalog(directory_path)

        # Populate state with empty textbox strings as requested
        self.storyboard_items = []
        self.thumbnails = {}
        
        for idx, img_name in enumerate(image_files):
            img_path = os.path.join(directory_path, img_name)
            vis_desc = catalog.get(img_name, "")
            
            self.storyboard_items.append({
                "panel_file": img_name,
                "image_path": img_path,
                "text": "", # Kept completely empty
                "visual_description": vis_desc,
                "audio_file": f"scene_{idx:03d}.wav",
                "video_file": f"scene_{idx:03d}.mp4",
                "status": "idle",
                "selected_var": tk.BooleanVar(value=False)
            })

        self.refresh_timeline()
        self.set_status(f"Successfully loaded {len(self.storyboard_items)} panels. All textareas cleared.", 0.0)

    def refresh_timeline(self):
        """Clears and rebuilds the scrollable storyboard timeline."""
        # Clear existing widgets
        for widget in self.main_scrollable.winfo_children():
            widget.destroy()

        # Build each card
        for idx, item in enumerate(self.storyboard_items):
            self.build_card_row(idx, item)

    def build_card_row(self, idx, item):
        # Card Container Frame
        card_frame = customtkinter.CTkFrame(self.main_scrollable, fg_color="#1e1e24", corner_radius=10, border_width=1, border_color="#2d2d30")
        card_frame.pack(fill="x", padx=15, pady=8)

        # --- Column 1: Panel Info, Checkbox & Thumbnail ---
        col1_frame = customtkinter.CTkFrame(card_frame, fg_color="transparent")
        col1_frame.pack(side="left", padx=10, pady=10)

        # Left subframe for checkbox & filename index
        left_header = customtkinter.CTkFrame(col1_frame, fg_color="transparent")
        left_header.pack(fill="x", anchor="w", pady=(0, 5))

        # Checkbox for multi-selection removal
        chk_select = customtkinter.CTkCheckBox(
            left_header, 
            text="", 
            variable=item["selected_var"], 
            width=20,
            fg_color="#2563eb",
            hover_color="#1d4ed8"
        )
        chk_select.pack(side="left", padx=(0, 5))

        # Index and Filename Label
        filename_short = item["panel_file"]
        if len(filename_short) > 16:
            filename_short = filename_short[:8] + "..." + filename_short[-6:]
        lbl_info = customtkinter.CTkLabel(
            left_header, 
            text=f"{idx + 1}. {filename_short}", 
            text_color="#f4f4f5", 
            font=("Outfit", 12, "bold")
        )
        lbl_info.pack(side="left")

        # Thumbnail Image Display
        thumbnail_img = self.get_thumbnail(item["image_path"])
        if thumbnail_img:
            lbl_thumb = customtkinter.CTkLabel(col1_frame, image=thumbnail_img, text="")
            lbl_thumb.pack(anchor="w", padx=25)
            # Click thumbnail to open image in OS default viewer
            lbl_thumb.bind("<Button-1>", lambda e, p=item["image_path"]: os.startfile(p))
            lbl_thumb.configure(cursor="hand2")
        else:
            lbl_thumb = customtkinter.CTkLabel(col1_frame, text="[No Image]", text_color="#ef4444")
            lbl_thumb.pack(anchor="w", padx=25)

        # --- Column 2: Narration Text Area & Inline Process Controls ---
        col2_frame = customtkinter.CTkFrame(card_frame, fg_color="transparent")
        col2_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        # Multiline text box (No placeholder text)
        txt_box = customtkinter.CTkTextbox(col2_frame, height=90, font=("Inter", 12), fg_color="#18181b", text_color="#e4e4e7")
        txt_box.pack(fill="x", expand=True, pady=(0, 6))
        
        # Fill text if exists (otherwise keep completely empty)
        if item["text"]:
            txt_box.insert("1.0", item["text"])
            
        # Bind focus out and key release to save text to state
        txt_box.bind("<FocusOut>", lambda e, index=idx, tb=txt_box: self.save_text_state(index, tb))
        txt_box.bind("<KeyRelease>", lambda e, index=idx, tb=txt_box: self.save_text_state(index, tb))

        # Inline Action controls (Describe, TTS, Render Clip)
        control_row = customtkinter.CTkFrame(col2_frame, fg_color="transparent")
        control_row.pack(fill="x", anchor="w")

        # Describe (Vision) Button
        btn_desc = customtkinter.CTkButton(
            control_row, 
            text="Describe", 
            width=80, 
            height=26,
            command=lambda index=idx, tb=txt_box: self.describe_single_panel(index, tb),
            fg_color="#3f3f46", 
            hover_color="#52525b",
            font=("Outfit", 11, "bold"),
            corner_radius=5
        )
        btn_desc.pack(side="left", padx=(0, 5))

        # TTS Generate Button
        btn_tts = customtkinter.CTkButton(
            control_row, 
            text="Generate TTS", 
            width=90, 
            height=26,
            command=lambda index=idx, tb=txt_box: self.generate_single_tts_clip(index, tb),
            fg_color="#3f3f46", 
            hover_color="#52525b",
            font=("Outfit", 11, "bold"),
            corner_radius=5
        )
        btn_tts.pack(side="left", padx=5)

        # Play Audio Button
        audio_path = os.path.join(self.audio_dir, item["audio_file"])
        audio_exists = os.path.exists(audio_path)
        btn_play = customtkinter.CTkButton(
            control_row, 
            text="▶ Listen", 
            width=70, 
            height=26,
            command=lambda path=audio_path: self.play_audio_clip(path),
            state="normal" if audio_exists else "disabled",
            fg_color="#10b981" if audio_exists else "#27272a",
            hover_color="#059669" if audio_exists else "#27272a",
            text_color="#ffffff" if audio_exists else "#71717a",
            font=("Outfit", 11, "bold"),
            corner_radius=5
        )
        btn_play.pack(side="left", padx=5)

        # Render Clip Button
        btn_render_clip = customtkinter.CTkButton(
            control_row, 
            text="Render Clip", 
            width=90, 
            height=26,
            command=lambda index=idx: self.render_single_clip(index),
            fg_color="#3f3f46", 
            hover_color="#52525b",
            font=("Outfit", 11, "bold"),
            corner_radius=5
        )
        btn_render_clip.pack(side="left", padx=5)

        # Play/View Rendered Video Button
        video_path = os.path.join(self.split_dir, item["video_file"])
        video_exists = os.path.exists(video_path)
        btn_play_video = customtkinter.CTkButton(
            control_row, 
            text="🎬 Play Clip", 
            width=80, 
            height=26,
            command=lambda path=video_path: self.play_video_clip(path),
            state="normal" if video_exists else "disabled",
            fg_color="#06b6d4" if video_exists else "#27272a",
            hover_color="#0891b2" if video_exists else "#27272a",
            text_color="#ffffff" if video_exists else "#71717a",
            font=("Outfit", 11, "bold"),
            corner_radius=5
        )
        btn_play_video.pack(side="left", padx=5)

        # Status indicator inside card
        lbl_card_status = customtkinter.CTkLabel(
            control_row, 
            text=f"Status: {item['status'].upper()}", 
            text_color="#71717a" if item['status'] == "idle" else "#06b6d4",
            font=("Outfit", 11)
        )
        lbl_card_status.pack(side="right", padx=10)

        # --- Column 3: Reordering Controls ---
        col3_frame = customtkinter.CTkFrame(card_frame, fg_color="transparent")
        col3_frame.pack(side="right", padx=15, pady=10)

        # Move Up Button
        btn_up = customtkinter.CTkButton(
            col3_frame, 
            text="Move Up", 
            width=90, 
            height=26,
            command=lambda index=idx: self.move_panel_up(index),
            fg_color="#27272a", 
            hover_color="#3f3f46",
            font=("Outfit", 11),
            corner_radius=5
        )
        btn_up.pack(pady=2)

        # Move Down Button
        btn_down = customtkinter.CTkButton(
            col3_frame, 
            text="Move Down", 
            width=90, 
            height=26,
            command=lambda index=idx: self.move_panel_down(index),
            fg_color="#27272a", 
            hover_color="#3f3f46",
            font=("Outfit", 11),
            corner_radius=5
        )
        btn_down.pack(pady=2)

        # Insert After Button
        btn_insert = customtkinter.CTkButton(
            col3_frame, 
            text="Insert After", 
            width=90, 
            height=26,
            command=lambda index=idx: self.insert_after_panel(index),
            fg_color="#27272a", 
            hover_color="#3f3f46",
            font=("Outfit", 11),
            corner_radius=5
        )
        btn_insert.pack(pady=2)

        # Remove Button
        btn_remove = customtkinter.CTkButton(
            col3_frame, 
            text="Remove", 
            width=90, 
            height=26,
            command=lambda index=idx: self.remove_panel(index),
            fg_color="#991b1b", 
            hover_color="#7f1d1d",
            font=("Outfit", 11, "bold"),
            corner_radius=5
        )
        btn_remove.pack(pady=2)
        
        # Store widget references in state for scrolling/focusing
        item["card_frame"] = card_frame
        item["txt_box"] = txt_box
        item["btn_play"] = btn_play
        item["btn_play_video"] = btn_play_video
        item["lbl_card_status"] = lbl_card_status

    def get_thumbnail(self, img_path):
        """Loads and crops a square thumbnail of the panel."""
        if img_path in self.thumbnails:
            return self.thumbnails[img_path]

        if not os.path.exists(img_path):
            return None

        try:
            img = Image.open(img_path)
            # Create a 120x120 thumbnail preserving aspect ratio
            img.thumbnail((120, 120), Image.Resampling.LANCZOS)
            ctk_img = customtkinter.CTkImage(light_image=img, dark_image=img, size=img.size)
            self.thumbnails[img_path] = ctk_img
            return ctk_img
        except Exception as e:
            print(f"Failed to generate thumbnail for {img_path}: {e}")
            return None

    def save_text_state(self, index, text_box):
        """Saves edited text box content back into state."""
        raw_text = text_box.get("1.0", "end-1c").strip()
        old_text = self.storyboard_items[index].get("text", "").strip()
        if raw_text != old_text:
            self.storyboard_items[index]["text"] = raw_text
            
            # Remove its audio_file from disk
            audio_filename = self.storyboard_items[index].get("audio_file")
            if audio_filename:
                audio_path = os.path.join(self.audio_dir, audio_filename)
                if os.path.exists(audio_path):
                    try:
                        os.remove(audio_path)
                        print(f"[*] Deleted stale audio file {audio_path} due to text change.")
                    except Exception as e:
                        print(f"Failed to delete stale audio file {audio_path}: {e}")
            
            # Remove its video_file from disk
            video_filename = self.storyboard_items[index].get("video_file")
            if video_filename:
                video_path = os.path.join(self.split_dir, video_filename)
                if os.path.exists(video_path):
                    try:
                        os.remove(video_path)
                        print(f"[*] Deleted stale video file {video_path} due to text change.")
                    except Exception as e:
                        print(f"Failed to delete stale video file {video_path}: {e}")
                        
            self.update_card_ui(index)

    def go_to_scene(self, index):
        """Scrolls the timeline to the selected scene card and highlights it."""
        if index < 0 or index >= len(self.storyboard_items):
            return
            
        item = self.storyboard_items[index]
        card_frame = item.get("card_frame")
        txt_box = item.get("txt_box")
        
        if not card_frame:
            return
            
        self.update_idletasks()
        
        try:
            canvas = self.main_scrollable._parent_canvas
            scrollregion = canvas.cget("scrollregion")
            total_height = 0
            if scrollregion:
                try:
                    parts = [float(x) for x in scrollregion.split()]
                    total_height = parts[3] - parts[1]
                except Exception:
                    total_height = canvas.bbox("all")[3]
            else:
                total_height = canvas.bbox("all")[3]
                
            y_coord = card_frame.winfo_rooty() - canvas.winfo_rooty() + canvas.canvasy(0)
            
            if total_height > 0:
                fraction = max(0.0, min(1.0, y_coord / total_height))
                canvas.yview_moveto(fraction)
        except Exception as scroll_err:
            print(f"Scrolling error: {scroll_err}")
            
        if txt_box:
            try:
                txt_box.focus_set()
            except Exception:
                pass
                
        # Flash highlighting of border
        try:
            original_color = card_frame.cget("border_color")
            def highlight():
                if card_frame.winfo_exists():
                    card_frame.configure(border_color="#ef4444")
            def restore():
                if card_frame.winfo_exists():
                    card_frame.configure(border_color=original_color)
                
            self.after(100, highlight)
            self.after(1100, restore)
            self.after(1300, highlight)
            self.after(2300, restore)
        except Exception:
            pass

    def update_card_ui(self, index):
        """Updates the visual widgets of a specific card in-place without rebuilding the layout."""
        if index < 0 or index >= len(self.storyboard_items):
            return
            
        item = self.storyboard_items[index]
        
        # 1. Update text if the widget exists and is out of sync
        txt_box = item.get("txt_box")
        if txt_box and txt_box.winfo_exists():
            try:
                current_val = txt_box.get("1.0", "end-1c").strip()
                if current_val != item["text"]:
                    txt_box.delete("1.0", "end")
                    txt_box.insert("1.0", item["text"])
            except Exception:
                pass
                
        # 2. Update status label
        lbl_status = item.get("lbl_card_status")
        if lbl_status and lbl_status.winfo_exists():
            try:
                status_str = f"Status: {item['status'].upper()}"
                lbl_status.configure(
                    text=status_str,
                    text_color="#71717a" if item['status'] == "idle" else "#06b6d4"
                )
            except Exception:
                pass
            
        # 3. Update Audio Listen Button
        btn_play = item.get("btn_play")
        if btn_play and btn_play.winfo_exists():
            try:
                audio_path = os.path.join(self.audio_dir, item["audio_file"])
                audio_exists = os.path.exists(audio_path)
                btn_play.configure(
                    state="normal" if audio_exists else "disabled",
                    fg_color="#10b981" if audio_exists else "#27272a",
                    hover_color="#059669" if audio_exists else "#27272a",
                    text_color="#ffffff" if audio_exists else "#71717a"
                )
            except Exception:
                pass
            
        # 4. Update Play Clip Video Button
        btn_play_video = item.get("btn_play_video")
        if btn_play_video and btn_play_video.winfo_exists():
            try:
                video_path = os.path.join(self.split_dir, item["video_file"])
                video_exists = os.path.exists(video_path)
                btn_play_video.configure(
                    state="normal" if video_exists else "disabled",
                    fg_color="#06b6d4" if video_exists else "#27272a",
                    hover_color="#0891b2" if video_exists else "#27272a",
                    text_color="#ffffff" if video_exists else "#71717a"
                )
            except Exception:
                pass

    # --- Storyboard Sequence Operations ---
    def move_panel_up(self, index):
        if index > 0:
            self.storyboard_items[index], self.storyboard_items[index - 1] = \
                self.storyboard_items[index - 1], self.storyboard_items[index]
            
            # Recalculate default audio/video output names to match indices chronologically
            self.align_filenames()
            self.refresh_timeline()
            self.set_status(f"Moved scene {index + 1} up.")

    def move_panel_down(self, index):
        if index < len(self.storyboard_items) - 1:
            self.storyboard_items[index], self.storyboard_items[index + 1] = \
                self.storyboard_items[index + 1], self.storyboard_items[index]
            
            self.align_filenames()
            self.refresh_timeline()
            self.set_status(f"Moved scene {index + 1} down.")

    def remove_panel(self, index):
        item = self.storyboard_items[index]
        if messagebox.askyesno("Confirm Removal", f"Remove scene panel '{item['panel_file']}'?"):
            self.storyboard_items.pop(index)
            self.align_filenames()
            self.refresh_timeline()
            self.set_status("Removed scene.")

    def insert_after_panel(self, index):
        """Inserts a selected image panel after this index."""
        selected_file = filedialog.askopenfilename(
            initialdir=self.current_panels_dir,
            title="Select Panel Image to Insert",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.webp")]
        )
        if selected_file:
            new_item = {
                "panel_file": os.path.basename(selected_file),
                "image_path": selected_file,
                "text": "",
                "audio_file": "",
                "video_file": "",
                "status": "idle",
                "selected_var": tk.BooleanVar(value=False)
            }
            self.storyboard_items.insert(index + 1, new_item)
            self.align_filenames()
            self.refresh_timeline()
            self.set_status("Inserted new panel scene.")

    def align_filenames(self):
        """Aligns audio and video filenames to match chronological indices."""
        for idx, item in enumerate(self.storyboard_items):
            item["audio_file"] = f"scene_{idx:03d}.wav"
            item["video_file"] = f"scene_{idx:03d}.mp4"

    # --- Multi-selection Removal Controls ---
    def toggle_select_all(self):
        if not self.storyboard_items:
            return
        # Toggle all selected checkboxes
        all_checked = all(item["selected_var"].get() for item in self.storyboard_items)
        new_val = not all_checked
        for item in self.storyboard_items:
            item["selected_var"].set(new_val)
        self.btn_select_all.configure(text="Deselect All" if new_val else "Select All")

    def remove_selected_panels(self):
        to_remove = [idx for idx, item in enumerate(self.storyboard_items) if item["selected_var"].get()]
        if not to_remove:
            messagebox.showinfo("Select Panels", "No panels selected! Use checkboxes next to panels to select.")
            return

        if messagebox.askyesno("Confirm Removal", f"Remove {len(to_remove)} selected panel(s)?"):
            # Remove from bottom to top to avoid shift in indices
            for idx in sorted(to_remove, reverse=True):
                self.storyboard_items.pop(idx)
            self.align_filenames()
            self.refresh_timeline()
            self.set_status(f"Removed {len(to_remove)} panel(s).")
            self.btn_select_all.configure(text="Select All")

    def clear_all_panels(self):
        if not self.storyboard_items:
            return
        if messagebox.askyesno("Confirm Clear", "Are you sure you want to remove ALL loaded panels?"):
            self.clear_audio_directory()
            self.storyboard_items = []
            self.thumbnails = {}
            self.refresh_timeline()
            self.set_status("All panels cleared.")
            self.btn_select_all.configure(text="Select All")

    # --- Script Operations ---
    def upload_script_file(self):
        selected_file = filedialog.askopenfilename(
            initialdir=self.workspace_dir,
            title="Select script.txt to Upload",
            filetypes=[("Text Files", "*.txt")]
        )
        if selected_file:
            try:
                with open(selected_file, 'r', encoding='utf-8') as f:
                    paragraphs = [line.strip() for line in f.readlines() if line.strip()]
                
                # Split paragraphs into sentences
                import re
                sentence_endings = re.compile(r'(?<=[.!?])\s+')
                self.script_sentences = []
                for para in paragraphs:
                    for s in sentence_endings.split(para):
                        if s.strip():
                            self.script_sentences.append(s.strip())

                filename = os.path.basename(selected_file)
                self.lbl_script_info.configure(text=f"Script: {filename} ({len(self.script_sentences)} lines)")
                self.set_status(f"Loaded script: {filename} with {len(self.script_sentences)} sentences.")
                messagebox.showinfo("Success", f"Script successfully loaded!\nFound {len(self.script_sentences)} sentences.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load script:\n{e}")

    # --- AI Script Mapping Action ---
    def run_ai_matching(self):
        if not self.storyboard_items:
            messagebox.showwarning("Warning", "Please load panels first.")
            return
        if not self.script_sentences:
            messagebox.showwarning("Warning", "Please upload a script file first.")
            return
        self.clear_audio_directory()
        self.set_status("Analyzing storyboard and matching script lines...", 0.0)
        self.cancel_flag = False # Reset cancellation flag

        def worker():
            try:
                # 1. Look for any empty descriptions
                empty_indices = []
                for idx, item in enumerate(self.storyboard_items):
                    vd = item.get("visual_description", "").strip()
                    t = item.get("text", "").strip()
                    if not vd and not t:
                        empty_indices.append(idx)

                if empty_indices:
                    total_empty = len(empty_indices)
                    self.set_status(f"AI Processing visual description (0 of {total_empty} processed)...", 0.05)
                    for c_idx, idx in enumerate(empty_indices):
                        if self.cancel_flag:
                            def cancel_vision():
                                self.set_status("AI matching cancelled by user.", 0.0)
                                self.cancel_flag = False
                            self.after(0, cancel_vision)
                            return

                        # Update progress bar with exact X of Y processed format
                        progress_val = 0.05 + (c_idx / total_empty) * 0.45
                        def update_vision_progress(current=c_idx+1, total=total_empty, p=progress_val):
                            self.set_status(f"AI Processing visual description ({current} of {total} processed)...", p)
                        self.after(0, update_vision_progress)

                        item = self.storyboard_items[idx]
                        try:
                            # Try querying local or online vision model
                            desc = self.query_gemma_vision(item["image_path"])
                            item["visual_description"] = desc
                        except Exception as e:
                            # Direct fallback to clean representation based on panel name
                            clean_name = os.path.splitext(item["panel_file"])[0].replace("_", " ").replace("-", " ")
                            item["visual_description"] = f"Action scene showing {clean_name}"
                            print(f"Vision call skipped/failed for card {idx}: {e}")

                # 2. Extract scene catalog representing active panel state
                scene_catalog = []
                for item in self.storyboard_items:
                    desc = item.get("visual_description", "").strip()
                    if not desc:
                        desc = item.get("text", "").strip()
                    if not desc:
                        clean_name = os.path.splitext(item["panel_file"])[0].replace("_", " ").replace("-", " ")
                        desc = f"Action scene showing {clean_name}"
                    scene_catalog.append({"panel_file": item["panel_file"], "description": desc})
                script_lines = self.script_sentences

                num_lines = len(script_lines)
                num_panels = len(scene_catalog)

                self.set_status(f"AI Matching script (0 of {num_lines} processed)...", 0.5)
                
                # Dictionary to group sentences assigned to each panel index
                panel_sentences = {j: [] for j in range(num_panels)}
                
                names = ["eugene", "hamel", "vermouth", "senya", "anise", "gordon", "father", "wife", "concubine", "lionhart", "wise", "great", "faithful", "brave"]
                keywords = ["sword", "dummy", "carriage", "portal", "fight", "train", "ritual", "shield", "axe", "monster", "castle", "forest", "gate", "dummy", "wood", "blacksmith", "magic", "blood"]

                # Process sentence-by-sentence matching and build scores
                S_indices = []
                for i, line in enumerate(script_lines):
                    if self.cancel_flag:
                        def cancel_matching():
                            self.set_status("AI matching cancelled by user.", 0.0)
                            self.cancel_flag = False
                        self.after(0, cancel_matching)
                        return

                    line_lower = line.lower()
                    best_j = 0
                    best_score = -float('inf')
                    
                    for j, panel in enumerate(scene_catalog):
                        desc_lower = panel["description"].lower()
                        
                        # Cosine Similarity metric
                        sim = get_cosine_similarity(line_lower, desc_lower)
                        
                        # Name matching bonus
                        name_bonus = 0.0
                        for name in names:
                            if name in line_lower and name in desc_lower:
                                name_bonus += 0.4
                                
                        # Keyword matching bonus
                        keyword_bonus = 0.0
                        for kw in keywords:
                            if kw in line_lower and kw in desc_lower:
                                keyword_bonus += 0.2
                                
                        # Chronological distance penalty to prevent out-of-order jumps
                        prop_j = (i / num_lines) * num_panels
                        dist_penalty = 0.08 * abs(j - prop_j)
                        
                        # Pure semantic score with chronological distance penalty
                        score = sim + name_bonus + keyword_bonus - dist_penalty
                        
                        if score > best_score:
                            best_score = score
                            best_j = j
                            
                    S_indices.append(best_j)
                    
                    # Update progress bar with exact X of Y processed format
                    if (i + 1) % 5 == 0 or i == num_lines - 1:
                        progress = 0.5 + ((i + 1) / num_lines) * 0.5
                        def update_matching_progress(current=i+1, total=num_lines, p=progress):
                            self.set_status(f"AI Matching script ({current} of {total} processed)...", p)
                        self.after(0, update_matching_progress)

                # Solve alignment sequence globally using DP from phase3_mapping
                strictly_increasing = (num_lines <= num_panels)
                path = align_timeline(S_indices, num_panels, strictly_increasing=strictly_increasing)
                
                # Assign sentences according to path
                for i, line in enumerate(script_lines):
                    panel_idx = path[i]
                    panel_sentences[panel_idx].append(line)

                # Update textbox narrations back on the main thread
                def update_ui():
                    for j, sentences in panel_sentences.items():
                        if sentences:
                            self.storyboard_items[j]["text"] = " ".join(sentences)
                            self.storyboard_items[j]["status"] = "idle"
                        else:
                            # Keep empty if no sentences mapped to it
                            self.storyboard_items[j]["text"] = ""
                            self.storyboard_items[j]["status"] = "idle"
                    for j in range(len(self.storyboard_items)):
                        self.update_card_ui(j)
                    self.set_status("AI script mapping successfully completed.", 1.0)
                    messagebox.showinfo("Success", "AI Script Alignment completed successfully!\nMatched textboxes populated based on best visual fit.")

                self.after(0, update_ui)

            except Exception as e:
                def update_err():
                    self.set_status("AI matching failed.", 0.0)
                    messagebox.showerror("Error", f"AI Script Matching failed:\n{e}")
                self.after(0, update_err)

        threading.Thread(target=worker, daemon=True).start()

    # --- Multi-selection Export Clips Job (With progress bar support) ---
    def run_export_selected_clips(self):
        selected_items = [(idx, item) for idx, item in enumerate(self.storyboard_items) if item["selected_var"].get()]
        if not selected_items:
            messagebox.showinfo("Select Scenes", "No scenes selected! Check the boxes next to the panels you wish to export.")
            return

        # Check if they have narration text
        missing_text = []
        for idx, item in selected_items:
            t = item["text"].strip()
            if not t:
                missing_text.append(idx)
        if missing_text:
            msg = f"Scenes {[i + 1 for i in missing_text]} are missing narration.\n\n" \
                  "Click 'Yes' to automatically locate the first missing scene in the timeline.\n" \
                  "Click 'No' to export anyway (scenes without narration will render as a 5-second clip).\n" \
                  "Click 'Cancel' to abort export."
            res = messagebox.askyesnocancel("Missing Narration", msg)
            if res is True:
                self.go_to_scene(missing_text[0])
                return
            elif res is None:
                return

        # Prompt for output directory
        export_dir = filedialog.askdirectory(
            initialdir=self.workspace_dir,
            title="Select Folder to Export Video Clips"
        )
        if not export_dir:
            return

        self.set_status("Starting export of selected scenes...", 0.0)
        self.cancel_flag = False # Reset cancellation flag

        def worker():
            total = len(selected_items)
            for c_idx, (idx, item) in enumerate(selected_items):
                if self.cancel_flag:
                    def cancel_export():
                        self.set_status("Export cancelled by user.", 0.0)
                        self.cancel_flag = False
                    self.after(0, cancel_export)
                    return

                # Update status bar & card state to 'rendering' with X of Y processed format
                progress = c_idx / total
                def update_start(current=c_idx, index=idx, p=progress):
                    self.set_status(f"Exporting clips ({current} of {total} processed)...", p)
                    self.storyboard_items[index]["status"] = "rendering"
                    self.update_card_ui(index)
                self.after(0, update_start)

                try:
                    # 1. Generate TTS audio first if it does not exist
                    audio_filename = item["audio_file"]
                    audio_path = os.path.join(self.audio_dir, audio_filename)
                    if not os.path.exists(audio_path):
                        self.synthesize_speech_kokoro(item["text"], audio_path)

                    # 2. Compile video clip using MoviePy
                    video_filename = f"scene_{idx:03d}_clip.mp4"
                    output_path = os.path.join(export_dir, video_filename)
                    
                    self.compile_single_video_clip(
                        image_path=item["image_path"],
                        text=item["text"],
                        audio_path=audio_path,
                        output_path=output_path,
                        scene_idx=idx
                    )

                    def update_success(index=idx):
                        self.storyboard_items[index]["status"] = "completed"
                        self.update_card_ui(index)
                    self.after(0, update_success)

                except Exception as err:
                    print(f"Export failed for scene {idx}: {err}")
                    def update_failure(index=idx):
                        self.storyboard_items[index]["status"] = "error"
                        self.update_card_ui(index)
                    self.after(0, update_failure)

            def finish():
                self.set_status("Selected scenes export completed successfully!", 1.0)
                messagebox.showinfo("Export Successful", f"Successfully exported {total} video clip(s) to:\n{export_dir}")
                os.startfile(export_dir)
            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    # --- Gemma/Other Provider Vision Description Job ---
    def describe_single_panel(self, index, text_box):
        item = self.storyboard_items[index]
        self.save_text_state(index, text_box)
        
        # Set loading state
        item["status"] = "describing"
        self.update_card_ui(index)
        self.set_status(f"Querying Gemma Vision for panel {index + 1}...")

        def worker():
            try:
                description = self.query_gemma_vision(item["image_path"])
                
                # Update textbox content and status on main thread
                def update_ui():
                    item["visual_description"] = description
                    item["text"] = description
                    item["status"] = "described"
                    self.update_card_ui(index)
                    self.set_status(f"Described panel {index + 1} successfully.")

                self.after(0, update_ui)
            except Exception as e:
                def update_err():
                    item["status"] = "error"
                    self.update_card_ui(index)
                    self.set_status(f"Description failed for panel {index + 1}: {e}")
                    messagebox.showerror("Vision Error", f"Gemma Vision request failed:\n{e}")
                self.after(0, update_err)

        threading.Thread(target=worker, daemon=True).start()

    def query_gemma_vision(self, image_path):
        """Queries local or online Vision instance via standard OpenAI client interface."""
        from openai import OpenAI
        from phase2_vision import encode_image

        api_url = self.ent_url.get().strip()
        api_key = self.ent_key.get().strip()
        model_name = self.ent_model.get().strip()

        client = OpenAI(base_url=api_url, api_key=api_key)
        base64_image = encode_image(image_path)

        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe the core action, characters, and emotion in this manga panel concisely. Focus strictly on visual facts."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            temperature=0.2,
            max_tokens=500
        )
        return response.choices[0].message.content.strip()

    # --- Kokoro-TTS Audition Job ---
    def generate_single_tts_clip(self, index, text_box):
        item = self.storyboard_items[index]
        self.save_text_state(index, text_box)
        
        text = item["text"]
        if not text:
            messagebox.showwarning("Warning", "Please write or generate text description first!")
            return

        item["status"] = "tts-generating"
        self.update_card_ui(index)
        self.set_status(f"Generating TTS for scene {index + 1}...")

        def worker():
            try:
                output_path = os.path.join(self.audio_dir, item["audio_file"])
                success = self.synthesize_speech_kokoro(text, output_path)
                
                if success:
                    def update_ui():
                        item["status"] = "tts-ready"
                        self.update_card_ui(index)
                        self.set_status(f"TTS audio ready for scene {index + 1}.")
                        # Autoplay clip on success
                        self.play_audio_clip(output_path)
                    self.after(0, update_ui)
                else:
                    raise Exception("TTS pipeline returned empty audio data")
            except Exception as e:
                def update_err():
                    item["status"] = "error"
                    self.update_card_ui(index)
                    self.set_status(f"TTS synthesis failed for scene {index + 1}: {e}")
                    messagebox.showerror("TTS Error", f"TTS synthesis failed:\n{e}")
                self.after(0, update_err)

        threading.Thread(target=worker, daemon=True).start()

    def synthesize_speech_kokoro(self, text, output_path):
        """Initializes and caches KPipeline to synthesize audio using Kokoro model."""
        import soundfile as sf
        import numpy as np
        
        if not text or not text.strip():
            print(f"[*] Generating 5 seconds of silence for empty narration: {output_path}")
            silence = np.zeros(24000 * 5, dtype=np.float32)
            sf.write(output_path, silence, 24000)
            return True
        
        # Cached Kokoro pipeline loading helper
        pipeline = self.get_cached_tts_pipeline()
        
        voice_val = self.opt_voice.get() if hasattr(self, "opt_voice") else getattr(self, "tts_voice", "af_heart")
        speed_val = float(self.sld_speed.get()) if hasattr(self, "sld_speed") else float(getattr(self, "tts_speed", 1.0))
        
        generator = pipeline(text, voice=voice_val, speed=speed_val)
        all_audio = []
        for graphemes, phonemes, audio_chunk in generator:
            all_audio.append(audio_chunk)

        if all_audio:
            final_audio = np.concatenate(all_audio)
            sf.write(output_path, final_audio, 24000)
            return True
        return False

    _pipeline_cache = None
    @classmethod
    def get_cached_tts_pipeline(cls):
        if cls._pipeline_cache is None:
            from kokoro import KPipeline
            import torch
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            print(f"[*] Initializing Kokoro TTS Pipeline on device: {device.upper()}")
            cls._pipeline_cache = KPipeline(lang_code='a')
        return cls._pipeline_cache

    def play_audio_clip(self, wav_path):
        """Plays wav file asynchronously without blocking GUI."""
        if os.path.exists(wav_path):
            try:
                winsound.PlaySound(wav_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
                self.set_status(f"Playing audio: {os.path.basename(wav_path)}")
            except Exception as e:
                print(f"Audio playback error: {e}")

    # --- MoviePy Single Scene Rendering Job ---
    def render_single_clip(self, index):
        item = self.storyboard_items[index]
        audio_path = os.path.join(self.audio_dir, item["audio_file"])
        
        if not os.path.exists(audio_path):
            messagebox.showwarning("Warning", "Please generate TTS audio for this card first!")
            return

        item["status"] = "rendering"
        self.update_card_ui(index)
        self.set_status(f"Rendering split scene clip {index + 1}...")

        def worker():
            try:
                output_video_path = os.path.join(self.split_dir, item["video_file"])
                
                # Trigger single-scene custom MoviePy compilation
                self.compile_single_video_clip(
                    image_path=item["image_path"],
                    text=item["text"],
                    audio_path=audio_path,
                    output_path=output_video_path,
                    scene_idx=index
                )
                
                def update_ui():
                    item["status"] = "completed"
                    self.update_card_ui(index)
                    self.set_status(f"Successfully compiled clip for scene {index + 1}.")
                self.after(0, update_ui)

            except Exception as e:
                def update_err():
                    item["status"] = "error"
                    self.update_card_ui(index)
                    self.set_status(f"Video clip compilation failed for scene {index + 1}: {e}")
                    messagebox.showerror("Video Composition Error", f"Failed to compile clip:\n{e}")
                self.after(0, update_err)

        threading.Thread(target=worker, daemon=True).start()

    def compile_single_video_clip(self, image_path, text, audio_path, output_path, scene_idx):
        from moviepy import VideoClip, AudioFileClip
        from phase4_video import SceneFrameGenerator, make_static_frame

        audio_clip = AudioFileClip(audio_path)
        duration = audio_clip.duration
        
        # Get render quality dimensions
        w, h = self.get_render_dimensions()
        
        # Use existing high-quality frame generator featuring Ken Burns effect/shaking/particles or static fallback
        if self.effects_var.get():
            gen = SceneFrameGenerator(image_path, text, duration, scene_idx, target_width=w, target_height=h)
            img_clip = VideoClip(gen.make_frame).with_duration(duration)
        else:
            frame_np = make_static_frame(image_path, target_width=w, target_height=h)
            img_clip = VideoClip(lambda t: frame_np).with_duration(duration)
            
        img_clip = img_clip.with_audio(audio_clip)

        # Attempt hardware accelerated GPU assembly, with CPU fallback
        try:
            img_clip.write_videofile(
                output_path,
                fps=30,
                codec="h264_nvenc",
                audio_codec="aac",
                threads=12,
                preset="fast",
                logger=None
            )
        except Exception as nvenc_err:
            print(f"[-] NVIDIA GPU render failed: {nvenc_err}. Retrying on CPU.")
            img_clip.write_videofile(
                output_path,
                fps=30,
                codec="libx264",
                audio_codec="aac",
                threads=12,
                preset="ultrafast",
                logger=None
            )
        
        audio_clip.close()
        img_clip.close()

    def play_video_clip(self, video_path):
        """Plays rendered mp4 file in the default OS media player."""
        if os.path.exists(video_path):
            os.startfile(video_path)

    # --- Batch TTS Processing Job ---
    def run_batch_tts(self):
        if not self.storyboard_items:
            messagebox.showwarning("Warning", "No panels loaded to process.")
            return

        self.set_status("Starting batch TTS voiceover generation...", 0.0)
        self.cancel_flag = False # Reset cancellation flag

        def worker():
            total = len(self.storyboard_items)
            for idx, item in enumerate(self.storyboard_items):
                if self.cancel_flag:
                    def cancel_tts():
                        self.set_status("Batch TTS cancelled by user.", 0.0)
                        self.cancel_flag = False
                    self.after(0, cancel_tts)
                    return

                text = item["text"]
                if not text:
                    continue

                def update_progress(current=idx):
                    self.set_status(f"Generating TTS (Processed {current + 1} of {total})...", current / total)
                    self.storyboard_items[current]["status"] = "tts-generating"
                    self.update_card_ui(current)
                self.after(0, update_progress)

                try:
                    output_path = os.path.join(self.audio_dir, item["audio_file"])
                    success = self.synthesize_speech_kokoro(text, output_path)
                    
                    def update_success(current=idx):
                        self.storyboard_items[current]["status"] = "tts-ready"
                        self.update_card_ui(current)
                    self.after(0, update_success)
                except Exception as err:
                    print(f"TTS failed for {idx}: {err}")
                    def update_failure(current=idx):
                        self.storyboard_items[current]["status"] = "error"
                        self.update_card_ui(current)
                    self.after(0, update_failure)

            def finish():
                self.set_status("Batch TTS voiceover generation completed.", 1.0)
                messagebox.showinfo("Success", "Batch TTS voiceover generation completed successfully!")
            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def run_long_tts(self):
        """Allows uploading a script file and generating a single long voiceover WAV file in an isolated background thread."""
        script_file = filedialog.askopenfilename(
            initialdir=self.workspace_dir,
            title="Select script.txt to generate Long TTS",
            filetypes=[("Text Files", "*.txt")]
        )
        if not script_file:
            return

        output_wav = filedialog.asksaveasfilename(
            initialdir=self.workspace_dir,
            title="Save Long TTS Audio As",
            defaultextension=".wav",
            filetypes=[("WAV Audio", "*.wav")]
        )
        if not output_wav:
            return

        self.set_status("Initializing Long TTS generation...", 0.1)

        def worker():
            try:
                # Read entire script
                with open(script_file, 'r', encoding='utf-8') as f:
                    text = f.read().strip()

                if not text:
                    def empty_warning():
                        self.set_status("Long TTS failed: Script is empty.", 0.0)
                        messagebox.showwarning("Warning", "The selected script file is empty.")
                    self.after(0, empty_warning)
                    return

                self.after(0, lambda: self.set_status("Synthesizing long voiceover track...", 0.5))
                
                success = self.synthesize_speech_kokoro(text, output_wav)
                
                if success:
                    def success_ui():
                        self.set_status("Long TTS audio successfully generated!", 1.0)
                        messagebox.showinfo("Success", f"Long TTS voiceover saved successfully to:\n{output_wav}")
                    self.after(0, success_ui)
                else:
                    def fail_ui():
                        self.set_status("Long TTS generation failed.", 0.0)
                        messagebox.showerror("Error", "Speech synthesis failed. Check your console logs.")
                    self.after(0, fail_ui)

            except Exception as e:
                def error_ui():
                    self.set_status("Long TTS error.", 0.0)
                    messagebox.showerror("Error", f"Long TTS generation failed:\n{e}")
                self.after(0, error_ui)

        import threading
        threading.Thread(target=worker, daemon=True).start()

    def run_edge_tts_not_implemented(self):
        messagebox.showinfo("Edge-TTS", "Edge-TTS is an alternative engine option. Currently using offline Kokoro-TTS.")

    # --- Global Video Compositor ---
    def run_video_compositor(self):
        if not self.storyboard_items:
            messagebox.showwarning("Warning", "No timeline items to compose.")
            return

        # Check if they have narration text
        missing_text = []
        for idx, item in enumerate(self.storyboard_items):
            t = item["text"].strip()
            if not t:
                missing_text.append(idx)
        if missing_text:
            msg = f"Scenes {[i + 1 for i in missing_text]} are missing narration.\n\n" \
                  "Click 'Yes' to automatically locate the first missing scene in the timeline.\n" \
                  "Click 'No' to compose anyway (scenes without narration will render as a 5-second clip).\n" \
                  "Click 'Cancel' to abort composition."
            res = messagebox.askyesnocancel("Missing Narration", msg)
            if res is True:
                self.go_to_scene(missing_text[0])
                return
            elif res is None:
                return

        # Prompt for output file path
        output_file = filedialog.asksaveasfilename(
            initialdir=self.workspace_dir,
            title="Save Recap Video As",
            defaultextension=".mp4",
            filetypes=[("MPEG-4 Video", "*.mp4")]
        )
        if not output_file:
            return

        self.set_status("Compiling video timeline in background...", 0.1)
        self.cancel_flag = False # Reset flag

        def worker():
            from moviepy import VideoClip, AudioFileClip, concatenate_videoclips, CompositeAudioClip
            from phase4_video import SceneFrameGenerator, make_static_frame

            video_clips = []
            total = len(self.storyboard_items)
            w, h = self.get_render_dimensions()

            try:
                for idx, item in enumerate(self.storyboard_items):
                    if self.cancel_flag:
                        def cancel_compose():
                            self.set_status("Composition cancelled by user.", 0.0)
                            self.cancel_flag = False
                        self.after(0, cancel_compose)
                        return

                    def update_scene_load(c=idx):
                        self.set_status(f"Preparing scenes (Processed {c + 1} of {total})...", (c + 1) / total * 0.5)
                    self.after(0, update_scene_load)

                    audio_path = os.path.join(self.audio_dir, item["audio_file"])
                    if not os.path.exists(audio_path):
                        self.synthesize_speech_kokoro(item["text"], audio_path)
                    audio_clip = AudioFileClip(audio_path)
                    duration = audio_clip.duration

                    # Use premium zooming frame generator or static frame depending on effects checkbox
                    if self.effects_var.get():
                        gen = SceneFrameGenerator(item["image_path"], item["text"], duration, idx, target_width=w, target_height=h)
                        img_clip = VideoClip(gen.make_frame).with_duration(duration)
                    else:
                        frame_np = make_static_frame(item["image_path"], target_width=w, target_height=h)
                        img_clip = VideoClip(lambda t: frame_np).with_duration(duration)
                        
                    img_clip = img_clip.with_audio(audio_clip)
                    video_clips.append(img_clip)

                self.after(0, lambda: self.set_status("Stitching clips and mixing BGM...", 0.6))
                
                final_video = concatenate_videoclips(video_clips, method="compose")

                # Mix BGM if selected
                bgm_file = getattr(self, "selected_bgm_file", None)
                if bgm_file and os.path.exists(bgm_file):
                    bgm_clip = AudioFileClip(bgm_file).with_volume_scaled(0.12).loop(duration=final_video.duration)
                    combined_audio = CompositeAudioClip([final_video.audio, bgm_clip])
                    final_video = final_video.with_audio(combined_audio)

                self.after(0, lambda: self.set_status("Rendering final video file...", 0.8))

                # Render output
                try:
                    final_video.write_videofile(
                        output_file,
                        fps=30,
                        codec="h264_nvenc",
                        audio_codec="aac",
                        threads=24,
                        preset="fast"
                    )
                except Exception as gpu_err:
                    print(f"[-] GPU render failed, falling back to CPU: {gpu_err}")
                    final_video.write_videofile(
                        output_file,
                        fps=30,
                        codec="libx264",
                        audio_codec="aac",
                        threads=24,
                        preset="ultrafast"
                    )

                # Clean up clips
                for clip in video_clips:
                    clip.close()
                final_video.close()

                def success():
                    self.set_status("Rendering complete!", 1.0)
                    messagebox.showinfo("Success", f"Recap video successfully compiled!\nSaved to: {output_file}")
                    os.startfile(output_file)
                self.after(0, success)

            except Exception as e:
                def failure():
                    self.set_status("Compositor rendering failed.", 0.0)
                    messagebox.showerror("Error", f"Video Compositor failed:\n{e}")
                self.after(0, failure)

        threading.Thread(target=worker, daemon=True).start()

    def select_bgm_file(self):
        """Lets the user pick an optional background music track."""
        bgm_path = filedialog.askopenfilename(
            initialdir=self.workspace_dir,
            title="Select Background Music Track",
            filetypes=[("Audio Files", "*.mp3 *.wav *.aac")]
        )
        if bgm_path:
            self.selected_bgm_file = bgm_path
            self.lbl_bgm.configure(text=f"BGM: {os.path.basename(bgm_path)}")
            self.set_status(f"BGM track set to: {os.path.basename(bgm_path)}")

    # --- Export Metadata Utilities ---
    def export_panels_json(self):
        """Saves current panel-text bindings to scene_catalog.json."""
        if not self.storyboard_items:
            messagebox.showwarning("Warning", "No panel storyboard elements loaded to export.")
            return

        export_data = []
        for item in self.storyboard_items:
            export_data.append({
                "panel_file": item["panel_file"],
                "description": item["text"]
            })

        output_path = os.path.join(self.workspace_dir, "scene_catalog.json")
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=4)
            messagebox.showinfo("Success", f"Panels timeline JSON exported to:\n{output_path}")
            self.set_status(f"Exported storyboard timeline to {os.path.basename(output_path)}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save panels JSON:\n{e}")

    def export_narration_txt(self):
        """Saves text narration script sequentially to script.txt."""
        if not self.storyboard_items:
            messagebox.showwarning("Warning", "No narration content loaded to export.")
            return

        paragraphs = []
        for item in self.storyboard_items:
            t = item["text"].strip()
            if t:
                paragraphs.append(t)

        if not paragraphs:
            messagebox.showwarning("Warning", "Storyboard narrations are empty.")
            return

        output_path = os.path.join(self.workspace_dir, "script.txt")
        try:
            with open(output_path, "w", encoding="utf-color") as f:
                f.write("\n\n".join(paragraphs))
            messagebox.showinfo("Success", f"Narration script exported to:\n{output_path}")
            self.set_status(f"Exported narration script to {os.path.basename(output_path)}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save narration text file:\n{e}")

if __name__ == "__main__":
    app = MangaRecapEditorApp()
    app.mainloop()
