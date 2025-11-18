#!/usr/bin/env python3
"""
Vision Narrator GUI
Real-time Vision Description and Speech Narrator System
"""

import tkinter as tk
from tkinter import ttk
import threading
from modules import CameraCapture, VisionDescriptor, TTSEngine, AudioDeviceManager


class NarratorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Vision Narrator")
        self.root.geometry("450x450")

        self.running = False
        self.narrator_thread = None

        # 系統組件
        self.camera = None
        self.vision = None
        self.tts = None

        # 音訊裝置管理
        self.audio_manager = AudioDeviceManager()
        self.selected_device = None

        # 語言模式
        self.language_mode = tk.StringVar(value="random")
        self.current_lang_index = 0
        self.languages = ["zh-TW", "en-GB", "ja-JP"]

        # MLX執行緒鎖（避免Metal命令衝突）
        self.vision_lock = threading.Lock()

        # 建立介面
        self.create_widgets()

    def create_widgets(self):
        # 控制按鈕放在最上方
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=10)

        self.start_button = tk.Button(button_frame, text="Start",
                                      command=self.start_system,
                                      bg="#4CAF50", fg="white",
                                      font=("Arial", 11, "bold"),
                                      padx=30, pady=8)
        self.start_button.pack(side="left", padx=5)

        self.stop_button = tk.Button(button_frame, text="Stop",
                                     command=self.stop_system,
                                     bg="#f44336", fg="white",
                                     font=("Arial", 11, "bold"),
                                     padx=30, pady=8,
                                     state="disabled")
        self.stop_button.pack(side="left", padx=5)

        # Settings area
        settings_frame = tk.Frame(self.root, padx=20)
        settings_frame.pack(fill="x", pady=5)

        # Language mode dropdown
        lang_label = tk.Label(settings_frame, text="Language:")
        lang_label.grid(row=0, column=0, sticky="w", pady=5)

        lang_options = [
            "Chinese Only",
            "English Only",
            "Japanese Only",
            "Rotate",
            "Random Mix"
        ]
        self.lang_combo = ttk.Combobox(settings_frame, values=lang_options,
                                       state="readonly", width=14)
        self.lang_combo.set("Random Mix")
        self.lang_combo.grid(row=0, column=1, sticky="w", padx=10, pady=5)

        # Audio output device dropdown
        device_label = tk.Label(settings_frame, text="Audio Output:")
        device_label.grid(row=1, column=0, sticky="w", pady=5)

        # 建立裝置選項列表
        self.device_options = ["System Default"]
        self.device_map = {}  # 顯示名稱 -> 裝置資訊的映射

        for device in self.audio_manager.get_devices():
            display_name = device['display_name']
            self.device_options.append(display_name)
            self.device_map[display_name] = device

        self.device_combo = ttk.Combobox(settings_frame, values=self.device_options,
                                         state="readonly", width=30)
        self.device_combo.set("System Default")
        self.device_combo.grid(row=1, column=1, sticky="w", padx=10, pady=5)

        # Status display
        status_frame = ttk.LabelFrame(self.root, text="Status", padding=10)
        status_frame.pack(fill="both", expand=True, padx=20, pady=10)

        self.status_text = tk.Text(status_frame, height=8, state="disabled")
        self.status_text.pack(fill="both", expand=True)

        scrollbar = ttk.Scrollbar(status_frame, command=self.status_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.status_text.config(yscrollcommand=scrollbar.set)

    def log(self, message):
        self.status_text.config(state="normal")
        self.status_text.insert("end", message + "\n")
        self.status_text.see("end")
        self.status_text.config(state="disabled")

    def start_system(self):
        if self.running:
            return

        self.running = True
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")

        # 在新執行緒中初始化和運行系統
        self.narrator_thread = threading.Thread(target=self.run_narrator, daemon=True)
        self.narrator_thread.start()

    def stop_system(self):
        self.running = False
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")

        self.log("System stopped")

        # Cleanup resources
        if self.camera:
            self.camera.stop()
        if self.tts:
            self.tts.cleanup()

    def run_narrator(self):
        try:
            # Initialize system
            self.log("Initializing camera...")
            self.camera = CameraCapture(camera_id=0, resolution=(640, 480))
            if not self.camera.start():
                self.log("Camera failed to start")
                self.running = False
                self.start_button.config(state="normal")
                self.stop_button.config(state="disabled")
                return

            self.log("Loading vision model...")
            try:
                # Set environment variable to avoid MLX thread conflicts
                import os
                os.environ['OBJC_DISABLE_INITIALIZE_FORK_SAFETY'] = 'YES'

                self.vision = VisionDescriptor(backend="mlx-vlm", model_name="models/smolvlm")
            except Exception as e:
                self.log(f"Model loading failed: {e}")
                self.log("Please check models/smolvlm directory exists")
                self.running = False
                self.start_button.config(state="normal")
                self.stop_button.config(state="disabled")
                if self.camera:
                    self.camera.stop()
                return

            self.log("Initializing TTS engine...")
            lang_text = self.lang_combo.get()
            mode_map = {
                "Chinese Only": "zh-TW",
                "English Only": "en-GB",
                "Japanese Only": "ja-JP",
                "Rotate": "rotate",
                "Random Mix": "random"
            }
            mode = mode_map.get(lang_text, "random")
            multilang = (mode == "random")
            lang = "zh-TW" if mode in ["rotate", "random"] else mode

            # 取得選擇的音訊裝置
            device_name = self.device_combo.get()
            if device_name == "System Default":
                audio_device = None
            else:
                audio_device = self.device_map.get(device_name)
                if audio_device:
                    self.log(f"Using audio device: {device_name}")

            self.tts = TTSEngine(backend="edge-tts", language=lang, multilang=multilang, audio_device=audio_device)

            self.log("System started successfully")

            # Main loop
            while self.running:
                self.describe_and_speak()

                # Wait 5 seconds
                import time
                time.sleep(5)

        except Exception as e:
            self.log(f"Error: {e}")
            import traceback
            self.log(traceback.format_exc())
            self.running = False
            self.start_button.config(state="normal")
            self.stop_button.config(state="disabled")

    def describe_and_speak(self):
        try:
            # Capture frame
            frame = self.camera.get_frame_rgb()
            if frame is None:
                self.log("Failed to capture frame")
                return

            # Get language mode from dropdown
            lang_text = self.lang_combo.get()
            mode_map = {
                "Chinese Only": "zh-TW",
                "English Only": "en-GB",
                "Japanese Only": "ja-JP",
                "Rotate": "rotate",
                "Random Mix": "random"
            }
            mode = mode_map.get(lang_text, "random")

            if mode == "random":
                # Random mix mode
                self.log("Generating multilingual descriptions...")
                with self.vision_lock:
                    descriptions = self.vision.describe_multilang(frame, max_tokens=100, temperature=0.5)

                self.log("Playing multilingual mix...")
                # 阻塞播放，音訊會自動循環填補空白
                self.tts.speak_multilang_mix(descriptions, blocking=True)

            elif mode == "rotate":
                # Rotate mode
                lang = self.languages[self.current_lang_index]
                self.current_lang_index = (self.current_lang_index + 1) % len(self.languages)

                prompts = {
                    "zh-TW": "請用繁體中文簡短描述這張圖片",
                    "en-GB": "Briefly describe this image in English",
                    "ja-JP": "この画像を日本語で簡潔に説明してください"
                }

                self.log(f"Generating {lang} description...")
                with self.vision_lock:
                    description = self.vision.describe(frame, prompt=prompts[lang], max_tokens=100, temperature=0.5)

                self.log(f"Playing {lang}...")
                # 阻塞播放
                self.tts.speak(description, blocking=True, language=lang)

            else:
                # Single language mode
                lang = mode
                prompts = {
                    "zh-TW": "請用繁體中文簡短描述這張圖片",
                    "en-GB": "Briefly describe this image in English",
                    "ja-JP": "この画像を日本語で簡潔に説明してください"
                }

                self.log(f"Generating {lang} description...")
                with self.vision_lock:
                    description = self.vision.describe(frame, prompt=prompts[lang], max_tokens=100, temperature=0.5)

                self.log(f"Playing {lang}...")
                # 阻塞播放
                self.tts.speak(description, blocking=True, language=lang)

        except Exception as e:
            self.log(f"Processing error: {e}")


def main():
    root = tk.Tk()
    app = NarratorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
