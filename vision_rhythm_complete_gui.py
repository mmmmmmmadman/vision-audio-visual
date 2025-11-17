#!/usr/bin/env python3
"""
Vision Rhythm Complete GUI - Single Page
Complete integration of Vision Narrator + Breakbeat Engine
All controls on one page
"""

import sys
import os
import tkinter as tk
from tkinter import ttk
import threading
import time
import random
import numpy as np
import sounddevice as sd

# Add vision_narrator to path
sys.path.insert(0, 'vision_narrator')

from breakbeat_engine import BreakBeatEngine

# Vision narrator imports (with fallback)
try:
    from modules import CameraCapture, VisionDescriptor, TTSEngine
    VISION_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Vision Narrator not available: {e}")
    VISION_AVAILABLE = False


class VisionRhythmGUI:
    """Complete integrated GUI - Single Page"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Vision Rhythm System")
        self.root.geometry("900x750")

        # Vision Narrator components
        self.vision_running = False
        self.narrator_thread = None
        self.camera = None
        self.vision = None
        self.tts = None
        self.vision_lock = threading.Lock()

        # Language settings
        self.current_lang_index = 0
        self.languages = ["zh-TW", "en-GB", "ja-JP"]

        # Breakbeat Engine
        self.engine = None
        self.stream = None
        self.rhythm_playing = False

        # Audio device
        self.selected_device = None
        self._detect_audio_devices()

        # Integration settings
        self.voice_to_rhythm_enabled = tk.BooleanVar(value=False)
        self.current_description = "等待描述"

        # Setup UI
        self._setup_ui()

        # Initialize breakbeat engine
        self._init_engine()

        # Update status
        self._update_bar_counter()
        self._update_integration_status()

    def _detect_audio_devices(self):
        """Detect available audio output devices"""
        self.audio_devices = []
        devices = sd.query_devices()

        for i, device in enumerate(devices):
            if device['max_output_channels'] > 0:
                name = device['name']
                self.audio_devices.append((i, name))

        # Set default device
        default_device = sd.default.device[1]
        self.selected_device = default_device

    def _setup_ui(self):
        """Setup single-page GUI with all controls"""

        # Main container with scrollbar
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill="both", expand=True)

        # Left column - Vision Narrator
        left_frame = ttk.LabelFrame(main_frame, text="Vision Narrator", padding=10)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # Right column - Rhythm Engine
        right_frame = ttk.LabelFrame(main_frame, text="Rhythm Engine", padding=10)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

        # Bottom - Integration
        bottom_frame = ttk.LabelFrame(main_frame, text="Integration", padding=10)
        bottom_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=5)

        # Configure grid weights
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)

        # Setup sections
        self._setup_vision_section(left_frame)
        self._setup_rhythm_section(right_frame)
        self._setup_integration_section(bottom_frame)

    def _setup_vision_section(self, parent):
        """Setup Vision Narrator section"""

        # Control buttons
        button_frame = tk.Frame(parent)
        button_frame.pack(pady=5)

        self.vision_start_button = tk.Button(
            button_frame, text="Start",
            command=self.start_vision_system,
            bg="#4CAF50", fg="white",
            font=("Arial", 10, "bold"),
            padx=20, pady=5
        )
        self.vision_start_button.pack(side="left", padx=3)

        self.vision_stop_button = tk.Button(
            button_frame, text="Stop",
            command=self.stop_vision_system,
            bg="#f44336", fg="white",
            font=("Arial", 10, "bold"),
            padx=20, pady=5,
            state="disabled"
        )
        self.vision_stop_button.pack(side="left", padx=3)

        # Language mode
        lang_frame = tk.Frame(parent)
        lang_frame.pack(fill="x", pady=5)

        tk.Label(lang_frame, text="Language:").pack(side="left", padx=5)

        lang_options = [
            "Chinese Only",
            "English Only",
            "Japanese Only",
            "Rotate",
            "Random Mix"
        ]
        self.lang_combo = ttk.Combobox(
            lang_frame, values=lang_options,
            state="readonly", width=12
        )
        self.lang_combo.set("Chinese Only")
        self.lang_combo.pack(side="left", padx=5)

        # Status display
        status_frame = ttk.LabelFrame(parent, text="Status", padding=5)
        status_frame.pack(fill="both", expand=True, pady=5)

        self.vision_status_text = tk.Text(status_frame, height=15, width=35, state="disabled")
        self.vision_status_text.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(status_frame, command=self.vision_status_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.vision_status_text.config(yscrollcommand=scrollbar.set)

    def _setup_rhythm_section(self, parent):
        """Setup Breakbeat section"""

        # Controls frame
        controls = ttk.Frame(parent)
        controls.pack(fill="both", expand=True)

        row = 0

        # BPM Control
        ttk.Label(controls, text="BPM:").grid(row=row, column=0, sticky=tk.W, pady=3)

        bpm_frame = ttk.Frame(controls)
        bpm_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=3)

        self.bpm_var = tk.IntVar(value=120)
        self.bpm_label = ttk.Label(bpm_frame, text="120", width=4)
        self.bpm_label.pack(side=tk.LEFT, padx=(0, 5))

        self.bpm_slider = ttk.Scale(
            bpm_frame, from_=60, to=200, orient=tk.HORIZONTAL,
            variable=self.bpm_var, command=self._on_bpm_change
        )
        self.bpm_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        row += 1

        # Pattern
        ttk.Label(controls, text="Pattern:").grid(row=row, column=0, sticky=tk.W, pady=3)

        self.pattern_var = tk.StringVar(value="Amen Break")
        pattern_combo = ttk.Combobox(
            controls, textvariable=self.pattern_var,
            values=["Amen Break", "Jungle", "Boom Bap", "Techno"],
            state="readonly", width=15
        )
        pattern_combo.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=3)
        pattern_combo.bind("<<ComboboxSelected>>", self._on_pattern_change)
        row += 1

        # Audio Device
        ttk.Label(controls, text="Audio Device:").grid(row=row, column=0, sticky=tk.W, pady=3)

        device_names = [name for _, name in self.audio_devices]
        self.device_var = tk.StringVar()

        for idx, name in self.audio_devices:
            if idx == self.selected_device:
                self.device_var.set(name)
                break

        device_combo = ttk.Combobox(
            controls, textvariable=self.device_var,
            values=device_names, state="readonly", width=15
        )
        device_combo.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=3)
        device_combo.bind("<<ComboboxSelected>>", self._on_device_change)
        row += 1

        # Status
        ttk.Label(controls, text="Status:").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.rhythm_status_label = ttk.Label(controls, text="Stopped", foreground="red")
        self.rhythm_status_label.grid(row=row, column=1, sticky=tk.W, pady=3)
        row += 1

        # Bar Counter
        ttk.Label(controls, text="Bar:").grid(row=row, column=0, sticky=tk.W, pady=3)
        self.bar_label = ttk.Label(controls, text="0")
        self.bar_label.grid(row=row, column=1, sticky=tk.W, pady=3)
        row += 1

        # Separator
        ttk.Separator(controls, orient=tk.HORIZONTAL).grid(
            row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=8
        )
        row += 1

        # Latin Layer
        ttk.Label(controls, text="Latin Layer:", font=("Arial", 9, "bold")).grid(
            row=row, column=0, columnspan=2, sticky=tk.W, pady=(3, 0)
        )
        row += 1

        self.latin_enabled_var = tk.BooleanVar(value=False)
        latin_cb = ttk.Checkbutton(
            controls, text="Enable",
            variable=self.latin_enabled_var,
            command=self._on_latin_toggle
        )
        latin_cb.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=2)
        row += 1

        ttk.Label(controls, text="Latin Style:").grid(row=row, column=0, sticky=tk.W, pady=3)

        self.latin_pattern_var = tk.StringVar(value="Samba")
        latin_pattern_combo = ttk.Combobox(
            controls, textvariable=self.latin_pattern_var,
            values=["Samba", "Bossa Nova", "Salsa"],
            state="readonly", width=15
        )
        latin_pattern_combo.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=3)
        latin_pattern_combo.bind("<<ComboboxSelected>>", self._on_latin_pattern_change)
        row += 1

        # Separator
        ttk.Separator(controls, orient=tk.HORIZONTAL).grid(
            row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=8
        )
        row += 1

        # Rest Amount
        ttk.Label(controls, text="Rest:").grid(row=row, column=0, sticky=tk.W, pady=3)

        rest_frame = ttk.Frame(controls)
        rest_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=3)

        self.rest_var = tk.DoubleVar(value=0.0)
        self.rest_label = ttk.Label(rest_frame, text="0%", width=4)
        self.rest_label.pack(side=tk.LEFT, padx=(0, 5))

        self.rest_slider = ttk.Scale(
            rest_frame, from_=0, to=100, orient=tk.HORIZONTAL,
            variable=self.rest_var, command=self._on_rest_change
        )
        self.rest_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        row += 1

        # Fill In
        ttk.Label(controls, text="Fill In:").grid(row=row, column=0, sticky=tk.W, pady=3)

        fill_frame = ttk.Frame(controls)
        fill_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=3)

        self.fill_var = tk.DoubleVar(value=0.0)
        self.fill_label = ttk.Label(fill_frame, text="0%", width=4)
        self.fill_label.pack(side=tk.LEFT, padx=(0, 5))

        self.fill_slider = ttk.Scale(
            fill_frame, from_=0, to=100, orient=tk.HORIZONTAL,
            variable=self.fill_var, command=self._on_fill_change
        )
        self.fill_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        row += 1

        # Swing
        ttk.Label(controls, text="Swing:").grid(row=row, column=0, sticky=tk.W, pady=3)

        self.swing_var = tk.StringVar(value="None")
        swing_combo = ttk.Combobox(
            controls, textvariable=self.swing_var,
            values=["None", "Light", "Medium", "Heavy", "Triplet"],
            state="readonly", width=15
        )
        swing_combo.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=3)
        swing_combo.bind("<<ComboboxSelected>>", self._on_swing_change)
        row += 1

        # Play button
        button_frame = ttk.Frame(controls)
        button_frame.grid(row=row, column=0, columnspan=2, pady=15)

        self.rhythm_play_button = ttk.Button(
            button_frame, text="▶ Play",
            command=self._toggle_rhythm_play, width=15
        )
        self.rhythm_play_button.pack()

        # Configure grid
        controls.columnconfigure(1, weight=1)

    def _setup_integration_section(self, parent):
        """Setup Integration section"""

        # Integration toggle
        integration_cb = ttk.Checkbutton(
            parent,
            text="啟用 語音→節奏 整合 (語音取代Latin層)",
            variable=self.voice_to_rhythm_enabled,
            command=self._on_integration_toggle
        )
        integration_cb.pack(pady=5)

        # Status frame
        status_frame = ttk.Frame(parent)
        status_frame.pack(fill="x", pady=5)

        ttk.Label(status_frame, text="Vision:").grid(row=0, column=0, sticky="w", padx=5)
        self.integration_vision_status = ttk.Label(status_frame, text="Stopped", foreground="red")
        self.integration_vision_status.grid(row=0, column=1, sticky="w", padx=5)

        ttk.Label(status_frame, text="Rhythm:").grid(row=0, column=2, sticky="w", padx=5)
        self.integration_rhythm_status = ttk.Label(status_frame, text="Stopped", foreground="red")
        self.integration_rhythm_status.grid(row=0, column=3, sticky="w", padx=5)

        ttk.Label(status_frame, text="Integration:").grid(row=0, column=4, sticky="w", padx=5)
        self.integration_active_status = ttk.Label(status_frame, text="Disabled", foreground="gray")
        self.integration_active_status.grid(row=0, column=5, sticky="w", padx=5)

        # Current description
        ttk.Label(parent, text="當前描述:").pack(anchor="w", padx=5, pady=(5,0))
        self.desc_label = ttk.Label(parent, text=self.current_description, wraplength=800)
        self.desc_label.pack(anchor="w", padx=5, pady=(0,5))

    # Vision Narrator Methods
    def vision_log(self, message):
        """Log to vision status text (thread-safe)"""
        def update_log():
            self.vision_status_text.config(state="normal")
            self.vision_status_text.insert("end", message + "\n")
            self.vision_status_text.see("end")
            self.vision_status_text.config(state="disabled")

        # Schedule GUI update in main thread
        self.root.after(0, update_log)

    def start_vision_system(self):
        """Start Vision Narrator system"""
        if self.vision_running:
            return

        if not VISION_AVAILABLE:
            self.vision_log("錯誤: Vision Narrator模組無法載入")
            return

        self.vision_running = True
        self.vision_start_button.config(state="disabled")
        self.vision_stop_button.config(state="normal")

        self.narrator_thread = threading.Thread(target=self.run_narrator, daemon=True)
        self.narrator_thread.start()

    def stop_vision_system(self):
        """Stop Vision Narrator system"""
        self.vision_running = False
        self.vision_start_button.config(state="normal")
        self.vision_stop_button.config(state="disabled")
        self.vision_log("系統已停止")

        if self.camera:
            self.camera.stop()
        if self.tts:
            self.tts.cleanup()

    def run_narrator(self):
        """Vision narrator main loop"""
        try:
            # Initialize
            self.vision_log("初始化攝影機...")
            self.camera = CameraCapture(camera_id=0, resolution=(640, 480))
            if not self.camera.start():
                self.vision_log("攝影機啟動失敗")
                self.vision_running = False
                self.root.after(0, lambda: self.vision_start_button.config(state="normal"))
                self.root.after(0, lambda: self.vision_stop_button.config(state="disabled"))
                return

            self.vision_log("載入視覺模型...")
            try:
                os.environ['OBJC_DISABLE_INITIALIZE_FORK_SAFETY'] = 'YES'
                self.vision = VisionDescriptor(
                    backend="mlx-vlm",
                    model_name="vision_narrator/models/smolvlm"
                )
            except Exception as e:
                self.vision_log(f"模型載入失敗: {e}")
                self.vision_running = False
                self.root.after(0, lambda: self.vision_start_button.config(state="normal"))
                self.root.after(0, lambda: self.vision_stop_button.config(state="disabled"))
                if self.camera:
                    self.camera.stop()
                return

            self.vision_log("初始化TTS引擎...")
            lang_text = self.lang_combo.get()
            mode_map = {
                "Chinese Only": "zh-TW",
                "English Only": "en-GB",
                "Japanese Only": "ja-JP",
                "Rotate": "rotate",
                "Random Mix": "random"
            }
            mode = mode_map.get(lang_text, "zh-TW")

            # Random Mix模式使用multilang切碎文字 Rotate模式在describe_and_speak裡處理
            multilang = (mode == "random")
            lang = "zh-TW" if mode in ["rotate", "random"] else mode

            self.tts = TTSEngine(backend="edge-tts", language=lang, multilang=multilang)
            self.vision_log("系統啟動成功")

            # Main loop
            while self.vision_running:
                self.describe_and_speak()
                time.sleep(5)

        except Exception as e:
            self.vision_log(f"錯誤: {e}")
            import traceback
            self.vision_log(traceback.format_exc())
            self.vision_running = False
            self.root.after(0, lambda: self.vision_start_button.config(state="normal"))
            self.root.after(0, lambda: self.vision_stop_button.config(state="disabled"))

    def describe_and_speak(self):
        """Generate description and speak or send to rhythm"""
        try:
            frame = self.camera.get_frame_rgb()
            if frame is None:
                self.vision_log("無法捕捉畫面")
                return

            lang_text = self.lang_combo.get()
            mode_map = {
                "Chinese Only": "zh-TW",
                "English Only": "en-GB",
                "Japanese Only": "ja-JP",
                "Rotate": "rotate",
                "Random Mix": "random"
            }
            mode = mode_map.get(lang_text, "zh-TW")

            # Branch based on mode BEFORE generating descriptions
            if mode == "random":
                # Random Mix mode - use multilingual pipeline
                integration_enabled = self.voice_to_rhythm_enabled.get()
                print(f"[DEBUG] Random Mix mode - Integration: {integration_enabled}, Rhythm playing: {self.rhythm_playing}")

                if integration_enabled:
                    # For rhythm integration, generate single description
                    print("[DEBUG] Using integration path - NO TTS playback")
                    lang = random.choice(self.languages)
                    prompts = {
                        "zh-TW": "請用繁體中文簡短描述這張圖片",
                        "en-GB": "Briefly describe this image in English",
                        "ja-JP": "この画像を日本語で簡潔に説明してください"
                    }
                    self.vision_log(f"生成 {lang} 描述 (for rhythm)...")
                    with self.vision_lock:
                        description = self.vision.describe(
                            frame, prompt=prompts[lang],
                            max_tokens=100, temperature=0.5
                        )
                    self.current_description = description
                    self.root.after(0, lambda: self.desc_label.config(text=description))

                    if self.rhythm_playing:
                        print("[DEBUG] Sending to rhythm engine")
                        self._send_voice_to_rhythm(description)
                    else:
                        print("[DEBUG] Rhythm not playing - skipping voice send")
                else:
                    # Normal Random Mix - use multilingual pipeline
                    print("[DEBUG] Using standalone TTS path")
                    self.vision_log("Generating multilingual descriptions...")
                    with self.vision_lock:
                        descriptions = self.vision.describe_multilang(frame, max_tokens=100, temperature=0.5)

                    # Update display with combined text
                    combined = " | ".join([f"{lang}: {text}" for lang, text in descriptions.items()])
                    self.current_description = combined
                    self.root.after(0, lambda: self.desc_label.config(text=combined))

                    self.vision_log("Playing multilingual mix...")
                    print("[DEBUG] Starting TTS playback")
                    self.tts.speak_multilang_mix(descriptions, blocking=True)
                    print("[DEBUG] TTS playback finished")

            elif mode == "rotate":
                # Rotate mode
                lang = self.languages[self.current_lang_index]
                self.current_lang_index = (self.current_lang_index + 1) % len(self.languages)

                prompts = {
                    "zh-TW": "請用繁體中文簡短描述這張圖片",
                    "en-GB": "Briefly describe this image in English",
                    "ja-JP": "この画像を日本語で簡潔に説明してください"
                }

                self.vision_log(f"生成 {lang} 描述...")
                with self.vision_lock:
                    description = self.vision.describe(
                        frame, prompt=prompts[lang],
                        max_tokens=100, temperature=0.5
                    )

                self.current_description = description
                self.root.after(0, lambda d=description: self.desc_label.config(text=d))

                if self.voice_to_rhythm_enabled.get():
                    # Only send to rhythm if rhythm is playing
                    if self.rhythm_playing:
                        self._send_voice_to_rhythm(description)
                else:
                    self.vision_log(f"播放 {lang} (循環)...")
                    self.tts.speak(description, blocking=True, language=lang, loop=True)

            else:
                # Single language mode
                lang = mode
                prompts = {
                    "zh-TW": "請用繁體中文簡短描述這張圖片",
                    "en-GB": "Briefly describe this image in English",
                    "ja-JP": "この画像を日本語で簡潔に說明してください"
                }

                self.vision_log(f"生成 {lang} 描述...")
                with self.vision_lock:
                    description = self.vision.describe(
                        frame, prompt=prompts[lang],
                        max_tokens=100, temperature=0.5
                    )

                self.current_description = description
                self.root.after(0, lambda d=description: self.desc_label.config(text=d))

                if self.voice_to_rhythm_enabled.get():
                    # Only send to rhythm if rhythm is playing
                    if self.rhythm_playing:
                        self._send_voice_to_rhythm(description)
                else:
                    self.vision_log(f"播放 {lang} (循環)...")
                    self.tts.speak(description, blocking=True, language=lang, loop=True)

        except Exception as e:
            self.vision_log(f"處理錯誤: {e}")

    def _send_voice_to_rhythm(self, text: str):
        """Send voice description to rhythm engine (thread-safe)"""
        if not self.engine:
            return

        try:
            # Use lock to avoid TTS conflicts
            with self.vision_lock:
                self.vision_log(f"傳送至節奏: {text[:30]}...")
                success = self.engine.load_voice_from_text(text)

                if success:
                    self.vision_log("語音已更新至節奏層")
                else:
                    self.vision_log("語音生成失敗")

        except Exception as e:
            self.vision_log(f"傳送錯誤: {e}")

    # Breakbeat Methods
    def _init_engine(self):
        """Initialize breakbeat engine"""
        try:
            self.engine = BreakBeatEngine(
                sample_dir="Audio Sample",
                bpm=120,
                sample_rate=44100
            )
            print(f"Engine initialized: {len(self.engine.samples)} categories loaded")
        except Exception as e:
            print(f"Error initializing engine: {e}")

    def _on_bpm_change(self, value):
        """Handle BPM change"""
        bpm = int(float(value))
        self.bpm_label.config(text=str(bpm))
        if self.engine:
            self.engine.set_bpm(bpm)

    def _on_pattern_change(self, event):
        """Handle pattern change"""
        pattern_map = {
            "Amen Break": "amen",
            "Jungle": "jungle",
            "Boom Bap": "boom_bap",
            "Techno": "techno"
        }
        pattern = pattern_map.get(self.pattern_var.get(), "amen")
        if self.engine:
            self.engine.set_pattern_type(pattern)

    def _on_latin_toggle(self):
        """Handle latin rhythm toggle"""
        if self.engine:
            enabled = self.latin_enabled_var.get()
            self.engine.set_latin_enabled(enabled)

    def _on_latin_pattern_change(self, event):
        """Handle latin pattern change"""
        pattern_map = {
            "Samba": "samba",
            "Bossa Nova": "bossa",
            "Salsa": "salsa"
        }
        pattern = pattern_map.get(self.latin_pattern_var.get(), "samba")
        if self.engine:
            self.engine.set_latin_pattern_type(pattern)

    def _on_rest_change(self, value):
        """Handle rest slider change"""
        rest_pct = float(value)
        self.rest_label.config(text=f"{int(rest_pct)}%")
        if self.engine:
            probability = rest_pct / 100.0
            self.engine.set_rest_probability(probability)

    def _on_fill_change(self, value):
        """Handle fill slider change"""
        fill_pct = float(value)
        self.fill_label.config(text=f"{int(fill_pct)}%")
        if self.engine:
            amount = fill_pct / 100.0
            self.engine.set_fill_amount(amount)

    def _on_device_change(self, event):
        """Handle audio device change"""
        device_name = self.device_var.get()
        for idx, name in self.audio_devices:
            if name == device_name:
                self.selected_device = idx
                if self.rhythm_playing:
                    self._stop_rhythm()
                    self._play_rhythm()
                break

    def _on_swing_change(self, event):
        """Handle swing change"""
        swing_map = {
            "None": 0.0,
            "Light": 0.10,
            "Medium": 0.17,
            "Heavy": 0.28,
            "Triplet": 0.33
        }
        swing_value = swing_map.get(self.swing_var.get(), 0.0)
        if self.engine:
            self.engine.set_swing_amount(swing_value)

    def _toggle_rhythm_play(self):
        """Toggle rhythm playback"""
        if self.rhythm_playing:
            self._stop_rhythm()
        else:
            self._play_rhythm()

    def _play_rhythm(self):
        """Start rhythm playback"""
        if not self.engine:
            return

        try:
            def audio_callback(outdata, frames, time_info, status):
                if status:
                    print(f"Audio status: {status}")
                chunk = self.engine.get_audio_chunk(frames)
                outdata[:, 0] = chunk

            self.stream = sd.OutputStream(
                channels=1,
                callback=audio_callback,
                samplerate=self.engine.sample_rate,
                blocksize=1024,
                device=self.selected_device
            )
            self.stream.start()

            self.rhythm_playing = True
            self.rhythm_play_button.config(text="⏸ Stop")
            self.rhythm_status_label.config(text="Playing", foreground="green")

        except Exception as e:
            print(f"Error starting playback: {e}")

    def _stop_rhythm(self):
        """Stop rhythm playback"""
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        self.rhythm_playing = False
        self.rhythm_play_button.config(text="▶ Play")
        self.rhythm_status_label.config(text="Stopped", foreground="red")

    def _update_bar_counter(self):
        """Update bar counter display"""
        if self.engine:
            self.bar_label.config(text=str(self.engine.bar_count))
        self.root.after(100, self._update_bar_counter)

    # Integration Methods
    def _on_integration_toggle(self):
        """Handle integration toggle"""
        enabled = self.voice_to_rhythm_enabled.get()
        print(f"\n[DEBUG] Integration toggle - Enabled: {enabled}")

        if enabled:
            # Stop any ongoing TTS loop playback
            print("[DEBUG] Stopping any TTS loop playback...")
            if self.tts:
                self.tts.should_stop_loop = True
                print(f"[DEBUG] TTS should_stop_loop = True")
                if self.tts.current_audio_process:
                    try:
                        print(f"[DEBUG] Terminating TTS process: {self.tts.current_audio_process.pid}")
                        self.tts.current_audio_process.terminate()
                    except Exception as e:
                        print(f"[DEBUG] Failed to terminate: {e}")
                        pass
                else:
                    print("[DEBUG] No TTS process running")

            if self.engine:
                self.engine.set_voice_enabled(True)
                self.engine.set_latin_enabled(True)
                print("[DEBUG] Engine voice and latin enabled")
                print("整合啟用: 語音→節奏")
        else:
            if self.engine:
                self.engine.set_voice_enabled(False)
                # Keep latin enabled for latin drums when integration is off
                if self.latin_enabled_var.get():
                    self.engine.set_latin_enabled(True)
                print("[DEBUG] Engine voice disabled")
                print("整合停用")

    def _update_integration_status(self):
        """Update integration status display"""
        # Vision status
        if self.vision_running:
            self.integration_vision_status.config(text="Running", foreground="green")
        else:
            self.integration_vision_status.config(text="Stopped", foreground="red")

        # Rhythm status
        if self.rhythm_playing:
            self.integration_rhythm_status.config(text="Playing", foreground="green")
        else:
            self.integration_rhythm_status.config(text="Stopped", foreground="red")

        # Integration status
        if self.voice_to_rhythm_enabled.get():
            if self.vision_running and self.rhythm_playing:
                self.integration_active_status.config(text="Active", foreground="green")
            else:
                self.integration_active_status.config(text="Enabled", foreground="orange")
        else:
            self.integration_active_status.config(text="Disabled", foreground="gray")

        self.root.after(500, self._update_integration_status)

    def run(self):
        """Run the GUI"""
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _on_close(self):
        """Handle window close"""
        self.stop_vision_system()
        self._stop_rhythm()
        self.root.destroy()


def main():
    """Main function"""
    print("Vision Rhythm Complete GUI - Single Page")
    print("=" * 60)

    app = VisionRhythmGUI()
    app.run()


if __name__ == '__main__':
    main()
