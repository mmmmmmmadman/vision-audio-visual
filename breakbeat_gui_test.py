#!/usr/bin/env python3
"""
Breakbeat C++ Engine GUI Test
簡單的 Tkinter GUI 測試即時參數調整
"""

import tkinter as tk
from tkinter import ttk
import threading
import random
import sounddevice as sd
import breakbeat

class BreakbeatGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Breakbeat C++ Engine Test")
        self.root.geometry("360x520")

        # Initialize engine
        print("Initializing engine...")
        self.engine = breakbeat.BreakbeatEngine("Audio Sample", 44100)
        print(f"Engine ready, sample rate: {self.engine.get_sample_rate()}")

        # Audio state
        self.stream = None
        self.playing = False

        # Detect audio devices
        self._detect_audio_devices()

        # Setup UI
        self._setup_ui()

        # Set initial params
        self._apply_all_params()

    def _detect_audio_devices(self):
        """偵測可用音訊輸出裝置和通道"""
        self.audio_devices = []
        devices = sd.query_devices()

        for i, device in enumerate(devices):
            if device['max_output_channels'] > 0:
                name = device['name']
                channels = device['max_output_channels']

                # 為多通道裝置建立每個通道的選項
                if channels > 2:
                    for ch in range(1, channels + 1):
                        channel_name = f"{name} - Output {ch}"
                        self.audio_devices.append((i, channel_name, ch))
                else:
                    self.audio_devices.append((i, name, 1))

        # 設定預設裝置
        default_device = sd.default.device[1]
        self.selected_device = default_device
        self.selected_channel = 1

    def _setup_ui(self):
        """建立 GUI"""
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill="both", expand=True)

        # Title
        title = ttk.Label(main_frame, text="Breakbeat C++ Engine", font=("Arial", 16, "bold"))
        title.pack(pady=10)

        # Controls
        controls = ttk.Frame(main_frame)
        controls.pack(fill="both", expand=True, pady=10)

        row = 0

        # Audio Device
        ttk.Label(controls, text="Audio Device:").grid(row=row, column=0, sticky="w", pady=5)

        device_names = [name for _, name, _ in self.audio_devices]
        self.device_var = tk.StringVar()

        # 找到預設裝置名稱
        for idx, name, ch in self.audio_devices:
            if idx == self.selected_device and ch == self.selected_channel:
                self.device_var.set(name)
                break

        device_combo = ttk.Combobox(controls, textvariable=self.device_var,
                                    values=device_names,
                                    state="readonly", width=30)
        device_combo.grid(row=row, column=1, columnspan=2, sticky="ew", padx=5)
        device_combo.bind("<<ComboboxSelected>>", self._on_device_change)
        row += 1

        # BPM
        ttk.Label(controls, text="BPM:").grid(row=row, column=0, sticky="w", pady=5)
        self.bpm_var = tk.IntVar(value=137)
        self.bpm_label = ttk.Label(controls, text="137", width=4)
        self.bpm_label.grid(row=row, column=1, sticky="w", padx=5)
        bpm_slider = ttk.Scale(controls, from_=60, to=200, orient="horizontal",
                              variable=self.bpm_var, command=self._on_bpm_change)
        bpm_slider.grid(row=row, column=2, sticky="ew", padx=5)
        row += 1

        # Pattern
        ttk.Label(controls, text="Pattern:").grid(row=row, column=0, sticky="w", pady=5)
        self.pattern_var = tk.StringVar(value="AMEN")
        pattern_combo = ttk.Combobox(controls, textvariable=self.pattern_var,
                                     values=["AMEN", "JUNGLE", "BOOM_BAP", "TECHNO"],
                                     state="readonly", width=12)
        pattern_combo.grid(row=row, column=1, columnspan=2, sticky="ew", padx=5)
        pattern_combo.bind("<<ComboboxSelected>>", self._on_pattern_change)
        row += 1

        # Swing
        ttk.Label(controls, text="Swing:").grid(row=row, column=0, sticky="w", pady=5)
        self.swing_var = tk.DoubleVar(value=7.0)
        self.swing_label = ttk.Label(controls, text="7%", width=4)
        self.swing_label.grid(row=row, column=1, sticky="w", padx=5)
        swing_slider = ttk.Scale(controls, from_=0, to=33, orient="horizontal",
                                variable=self.swing_var, command=self._on_swing_change)
        swing_slider.grid(row=row, column=2, sticky="ew", padx=5)
        row += 1

        # Rest
        ttk.Label(controls, text="Rest:").grid(row=row, column=0, sticky="w", pady=5)
        self.rest_var = tk.DoubleVar(value=0.0)
        self.rest_label = ttk.Label(controls, text="0%", width=4)
        self.rest_label.grid(row=row, column=1, sticky="w", padx=5)
        rest_slider = ttk.Scale(controls, from_=0, to=100, orient="horizontal",
                               variable=self.rest_var, command=self._on_rest_change)
        rest_slider.grid(row=row, column=2, sticky="ew", padx=5)
        row += 1

        # Latin
        ttk.Separator(controls, orient="horizontal").grid(row=row, column=0, columnspan=3,
                                                          sticky="ew", pady=10)
        row += 1

        ttk.Label(controls, text="Latin Layer:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", pady=5
        )
        row += 1

        self.latin_enabled_var = tk.BooleanVar(value=False)
        latin_cb = ttk.Checkbutton(controls, text="Enable Latin Layer",
                                   variable=self.latin_enabled_var,
                                   command=self._on_latin_toggle)
        latin_cb.grid(row=row, column=0, columnspan=3, sticky="w", pady=5)
        row += 1

        ttk.Label(controls, text="Latin Style:").grid(row=row, column=0, sticky="w", pady=5)
        self.latin_pattern_var = tk.StringVar(value="SAMBA")
        latin_combo = ttk.Combobox(controls, textvariable=self.latin_pattern_var,
                                   values=["SAMBA", "BOSSA", "SALSA"],
                                   state="readonly", width=15)
        latin_combo.grid(row=row, column=1, columnspan=2, sticky="ew", padx=5)
        latin_combo.bind("<<ComboboxSelected>>", self._on_latin_pattern_change)
        row += 1

        # Latin Fill
        ttk.Label(controls, text="Latin Fill:").grid(row=row, column=0, sticky="w", pady=5)
        self.latin_fill_var = tk.DoubleVar(value=100.0)
        self.latin_fill_label = ttk.Label(controls, text="100%", width=4)
        self.latin_fill_label.grid(row=row, column=1, sticky="w", padx=5)
        latin_fill_slider = ttk.Scale(controls, from_=0, to=100, orient="horizontal",
                                     variable=self.latin_fill_var, command=self._on_latin_fill_change)
        latin_fill_slider.grid(row=row, column=2, sticky="ew", padx=5)
        row += 1


        # Compressor
        ttk.Separator(controls, orient="horizontal").grid(row=row, column=0, columnspan=3,
                                                          sticky="ew", pady=10)
        row += 1

        ttk.Label(controls, text="LA-2A Compressor:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", pady=5
        )
        row += 1

        # Peak Reduction
        ttk.Label(controls, text="Peak Reduction:").grid(row=row, column=0, sticky="w", pady=5)
        self.comp_peak_var = tk.DoubleVar(value=30.0)
        self.comp_peak_label = ttk.Label(controls, text="30%", width=4)
        self.comp_peak_label.grid(row=row, column=1, sticky="w", padx=5)
        comp_peak_slider = ttk.Scale(controls, from_=0, to=100, orient="horizontal",
                                     variable=self.comp_peak_var, command=self._on_comp_peak_change)
        comp_peak_slider.grid(row=row, column=2, sticky="ew", padx=5)
        row += 1

        # Makeup Gain
        ttk.Label(controls, text="Makeup Gain:").grid(row=row, column=0, sticky="w", pady=5)
        self.comp_gain_var = tk.DoubleVar(value=6.0)
        self.comp_gain_label = ttk.Label(controls, text="6dB", width=4)
        self.comp_gain_label.grid(row=row, column=1, sticky="w", padx=5)
        comp_gain_slider = ttk.Scale(controls, from_=-20, to=20, orient="horizontal",
                                     variable=self.comp_gain_var, command=self._on_comp_gain_change)
        comp_gain_slider.grid(row=row, column=2, sticky="ew", padx=5)
        row += 1

        # Configure column weights
        controls.columnconfigure(2, weight=1)

        # Play button
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)

        self.play_button = ttk.Button(button_frame, text="▶ Play",
                                      command=self._toggle_play, width=15)
        self.play_button.pack()

    def _apply_all_params(self):
        """套用所有參數到引擎"""
        self.engine.set_bpm(float(self.bpm_var.get()))

        pattern_map = {
            "AMEN": breakbeat.PatternType.AMEN,
            "JUNGLE": breakbeat.PatternType.JUNGLE,
            "BOOM_BAP": breakbeat.PatternType.BOOM_BAP,
            "TECHNO": breakbeat.PatternType.TECHNO
        }
        self.engine.set_pattern_type(pattern_map[self.pattern_var.get()])

        self.engine.set_swing_amount(self.swing_var.get() / 100.0)
        self.engine.set_rest_probability(self.rest_var.get() / 100.0)
        self.engine.set_latin_enabled(self.latin_enabled_var.get())
        self.engine.set_latin_fill_amount(self.latin_fill_var.get() / 100.0)

        latin_map = {
            "SAMBA": breakbeat.LatinPatternType.SAMBA,
            "BOSSA": breakbeat.LatinPatternType.BOSSA,
            "SALSA": breakbeat.LatinPatternType.SALSA
        }
        self.engine.set_latin_pattern_type(latin_map[self.latin_pattern_var.get()])

        # Compressor - 永遠開啟
        self.engine.set_comp_enabled(True)
        self.engine.set_comp_peak_reduction(self.comp_peak_var.get() / 100.0)
        self.engine.set_comp_gain(self.comp_gain_var.get())
        self.engine.set_comp_mix(1.0)  # Fixed at 100%

    def _on_bpm_change(self, value):
        bpm = int(float(value))
        self.bpm_label.config(text=str(bpm))
        self.engine.set_bpm(float(bpm))

    def _on_pattern_change(self, event):
        pattern_map = {
            "AMEN": breakbeat.PatternType.AMEN,
            "JUNGLE": breakbeat.PatternType.JUNGLE,
            "BOOM_BAP": breakbeat.PatternType.BOOM_BAP,
            "TECHNO": breakbeat.PatternType.TECHNO
        }
        self.engine.set_pattern_type(pattern_map[self.pattern_var.get()])


    def _on_swing_change(self, value):
        val = int(float(value))
        self.swing_label.config(text=f"{val}%")
        self.engine.set_swing_amount(val / 100.0)

    def _on_rest_change(self, value):
        val = int(float(value))
        self.rest_label.config(text=f"{val}%")
        self.engine.set_rest_probability(val / 100.0)

    def _on_latin_toggle(self):
        self.engine.set_latin_enabled(self.latin_enabled_var.get())

    def _on_latin_pattern_change(self, event):
        latin_map = {
            "SAMBA": breakbeat.LatinPatternType.SAMBA,
            "BOSSA": breakbeat.LatinPatternType.BOSSA,
            "SALSA": breakbeat.LatinPatternType.SALSA
        }
        self.engine.set_latin_pattern_type(latin_map[self.latin_pattern_var.get()])

    def _on_latin_fill_change(self, value):
        val = int(float(value))
        self.latin_fill_label.config(text=f"{val}%")
        self.engine.set_latin_fill_amount(val / 100.0)

    def _on_comp_peak_change(self, value):
        val = int(float(value))
        self.comp_peak_label.config(text=f"{val}%")
        self.engine.set_comp_peak_reduction(val / 100.0)

    def _on_comp_gain_change(self, value):
        val = int(float(value))
        self.comp_gain_label.config(text=f"{val}dB")
        self.engine.set_comp_gain(float(val))

    def _on_device_change(self, event):
        """處理音訊裝置改變"""
        selected_name = self.device_var.get()

        # 找到裝置索引和通道
        for idx, name, ch in self.audio_devices:
            if name == selected_name:
                self.selected_device = idx
                self.selected_channel = ch
                print(f"Audio device changed to: {name} (device: {idx}, channel: {ch})")

                # 如果正在播放 重啟音訊串流
                if self.playing:
                    self._stop()
                    self._play()
                break

    def _toggle_play(self):
        if self.playing:
            self._stop()
        else:
            self._play()

    def _play(self):
        """開始播放"""
        def audio_callback(outdata, frames, time_info, status):
            if status:
                print(f"Audio status: {status}")
            chunk = self.engine.get_audio_chunk(frames)

            # 清空所有通道
            outdata[:] = 0

            # 寫入指定通道（單聲道）
            ch = self.selected_channel - 1  # 0-indexed
            if ch < outdata.shape[1]:
                outdata[:, ch] = chunk

        # 決定需要的輸出通道數
        num_channels = self.selected_channel

        self.stream = sd.OutputStream(
            channels=num_channels,
            callback=audio_callback,
            samplerate=44100,
            blocksize=1024,
            device=self.selected_device
        )
        self.stream.start()

        self.playing = True
        self.play_button.config(text="⏸ Stop")

    def _stop(self):
        """停止播放"""
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        self.playing = False
        self.play_button.config(text="▶ Play")

    def run(self):
        """執行 GUI"""
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _on_close(self):
        """關閉視窗"""
        self._stop()
        self.root.destroy()

def main():
    print("=" * 60)
    print("Breakbeat C++ Engine GUI Test")
    print("=" * 60)
    print()

    app = BreakbeatGUI()
    app.run()

if __name__ == '__main__':
    main()
