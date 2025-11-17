#!/usr/bin/env python3
"""
Break Beat Engine with GUI
Real-time break beat generation with GUI controls
"""

import os
import tkinter as tk
from tkinter import ttk
import sounddevice as sd
from breakbeat_engine import BreakBeatEngine


class BreakBeatGUI:
    """GUI controller for Break Beat Engine"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Break Beat Engine")
        self.root.geometry("400x650")

        # Engine
        self.engine = None
        self.stream = None
        self.playing = False

        # Audio device
        self.selected_device = None
        self._detect_audio_devices()

        # Setup UI
        self._setup_ui()

        # Initialize engine
        self._init_engine()

    def _detect_audio_devices(self):
        """Detect available audio output devices"""
        self.audio_devices = []
        devices = sd.query_devices()

        for i, device in enumerate(devices):
            # Only list output devices
            if device['max_output_channels'] > 0:
                name = device['name']
                self.audio_devices.append((i, name))

        # Set default device
        default_device = sd.default.device[1]  # Output device
        self.selected_device = default_device
        print(f"Default audio device: {default_device}")
        print(f"Available output devices: {self.audio_devices}")

    def _setup_ui(self):
        """Setup GUI components"""

        # Main frame
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Title
        title = ttk.Label(main_frame, text="Break Beat Engine", font=("Arial", 16, "bold"))
        title.grid(row=0, column=0, columnspan=2, pady=(0, 20))

        # BPM Control
        ttk.Label(main_frame, text="BPM:").grid(row=1, column=0, sticky=tk.W, pady=5)

        bpm_frame = ttk.Frame(main_frame)
        bpm_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5)

        self.bpm_var = tk.IntVar(value=140)
        self.bpm_label = ttk.Label(bpm_frame, text="140", width=5)
        self.bpm_label.pack(side=tk.LEFT, padx=(0, 10))

        self.bpm_slider = ttk.Scale(
            bpm_frame,
            from_=60,
            to=200,
            orient=tk.HORIZONTAL,
            variable=self.bpm_var,
            command=self._on_bpm_change
        )
        self.bpm_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Pattern Selection
        ttk.Label(main_frame, text="Pattern:").grid(row=2, column=0, sticky=tk.W, pady=5)

        self.pattern_var = tk.StringVar(value="Amen Break")
        pattern_combo = ttk.Combobox(
            main_frame,
            textvariable=self.pattern_var,
            values=["Amen Break", "Jungle", "Boom Bap", "Techno"],
            state="readonly",
            width=20
        )
        pattern_combo.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5)
        pattern_combo.bind("<<ComboboxSelected>>", self._on_pattern_change)

        # Audio Device Selection
        ttk.Label(main_frame, text="Audio Device:").grid(row=3, column=0, sticky=tk.W, pady=5)

        device_names = [name for _, name in self.audio_devices]
        self.device_var = tk.StringVar()

        # Find default device name
        for idx, name in self.audio_devices:
            if idx == self.selected_device:
                self.device_var.set(name)
                break

        device_combo = ttk.Combobox(
            main_frame,
            textvariable=self.device_var,
            values=device_names,
            state="readonly",
            width=20
        )
        device_combo.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=5)
        device_combo.bind("<<ComboboxSelected>>", self._on_device_change)

        # Status
        ttk.Label(main_frame, text="Status:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.status_label = ttk.Label(main_frame, text="Stopped", foreground="red")
        self.status_label.grid(row=4, column=1, sticky=tk.W, pady=5)

        # Bar Counter
        ttk.Label(main_frame, text="Bar:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.bar_label = ttk.Label(main_frame, text="0")
        self.bar_label.grid(row=5, column=1, sticky=tk.W, pady=5)

        # Latin Rhythm Controls
        latin_separator = ttk.Separator(main_frame, orient=tk.HORIZONTAL)
        latin_separator.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)

        ttk.Label(main_frame, text="Latin Layer:", font=("Arial", 10, "bold")).grid(
            row=7, column=0, columnspan=2, sticky=tk.W, pady=(5, 0)
        )

        # Latin Enable Checkbox
        self.latin_enabled_var = tk.BooleanVar(value=False)
        latin_cb = ttk.Checkbutton(
            main_frame,
            text="Enable Latin Rhythm",
            variable=self.latin_enabled_var,
            command=self._on_latin_toggle
        )
        latin_cb.grid(row=8, column=0, columnspan=2, sticky=tk.W, pady=5)

        # Latin Pattern Selection
        ttk.Label(main_frame, text="Latin Style:").grid(row=9, column=0, sticky=tk.W, pady=5)

        self.latin_pattern_var = tk.StringVar(value="Samba")
        latin_pattern_combo = ttk.Combobox(
            main_frame,
            textvariable=self.latin_pattern_var,
            values=["Samba", "Bossa Nova", "Salsa"],
            state="readonly",
            width=20
        )
        latin_pattern_combo.grid(row=9, column=1, sticky=(tk.W, tk.E), pady=5)
        latin_pattern_combo.bind("<<ComboboxSelected>>", self._on_latin_pattern_change)

        # Rest Control
        rest_separator = ttk.Separator(main_frame, orient=tk.HORIZONTAL)
        rest_separator.grid(row=10, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)

        ttk.Label(main_frame, text="Rest Amount:").grid(row=11, column=0, sticky=tk.W, pady=5)

        rest_frame = ttk.Frame(main_frame)
        rest_frame.grid(row=11, column=1, sticky=(tk.W, tk.E), pady=5)

        self.rest_var = tk.DoubleVar(value=0.0)
        self.rest_label = ttk.Label(rest_frame, text="0%", width=5)
        self.rest_label.pack(side=tk.LEFT, padx=(0, 10))

        self.rest_slider = ttk.Scale(
            rest_frame,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            variable=self.rest_var,
            command=self._on_rest_change
        )
        self.rest_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Fill In Control
        ttk.Label(main_frame, text="Fill In Amount:").grid(row=12, column=0, sticky=tk.W, pady=5)

        fill_frame = ttk.Frame(main_frame)
        fill_frame.grid(row=12, column=1, sticky=(tk.W, tk.E), pady=5)

        self.fill_var = tk.DoubleVar(value=0.0)
        self.fill_label = ttk.Label(fill_frame, text="0%", width=5)
        self.fill_label.pack(side=tk.LEFT, padx=(0, 10))

        self.fill_slider = ttk.Scale(
            fill_frame,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            variable=self.fill_var,
            command=self._on_fill_change
        )
        self.fill_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Swing Control
        ttk.Label(main_frame, text="Swing:").grid(row=13, column=0, sticky=tk.W, pady=5)

        self.swing_var = tk.StringVar(value="None")
        swing_combo = ttk.Combobox(
            main_frame,
            textvariable=self.swing_var,
            values=["None", "Light", "Medium", "Heavy", "Triplet"],
            state="readonly",
            width=20
        )
        swing_combo.grid(row=13, column=1, sticky=(tk.W, tk.E), pady=5)
        swing_combo.bind("<<ComboboxSelected>>", self._on_swing_change)

        # Control Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=14, column=0, columnspan=2, pady=20)

        self.play_button = ttk.Button(
            button_frame,
            text="▶ Play",
            command=self._toggle_play,
            width=15
        )
        self.play_button.pack(side=tk.LEFT, padx=5)

        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

        # Update bar counter periodically
        self._update_bar_counter()

    def _init_engine(self):
        """Initialize break beat engine"""
        try:
            self.engine = BreakBeatEngine(
                sample_dir="Audio Sample",
                bpm=140,
                sample_rate=44100
            )
            print(f"Engine initialized: {len(self.engine.samples)} categories loaded")
        except Exception as e:
            print(f"Error initializing engine: {e}")
            self.status_label.config(text=f"Error: {e}", foreground="red")

    def _on_bpm_change(self, value):
        """Handle BPM slider change"""
        bpm = int(float(value))
        self.bpm_label.config(text=str(bpm))

        if self.engine:
            self.engine.set_bpm(bpm)

    def _on_pattern_change(self, event):
        """Handle pattern selection change"""
        pattern_map = {
            "Amen Break": "amen",
            "Jungle": "jungle",
            "Boom Bap": "boom_bap",
            "Techno": "techno"
        }

        pattern = pattern_map.get(self.pattern_var.get(), "amen")

        if self.engine:
            self.engine.set_pattern_type(pattern)
            print(f"Pattern changed to: {pattern}")

    def _on_latin_toggle(self):
        """Handle latin rhythm enable/disable"""
        if self.engine:
            enabled = self.latin_enabled_var.get()
            self.engine.set_latin_enabled(enabled)
            print(f"Latin rhythm: {'enabled' if enabled else 'disabled'}")

    def _on_latin_pattern_change(self, event):
        """Handle latin pattern selection change"""
        pattern_map = {
            "Samba": "samba",
            "Bossa Nova": "bossa",
            "Salsa": "salsa"
        }

        pattern = pattern_map.get(self.latin_pattern_var.get(), "samba")

        if self.engine:
            self.engine.set_latin_pattern_type(pattern)
            print(f"Latin pattern changed to: {pattern}")

    def _on_rest_change(self, value):
        """Handle rest slider change"""
        rest_pct = float(value)
        self.rest_label.config(text=f"{int(rest_pct)}%")

        if self.engine:
            probability = rest_pct / 100.0
            self.engine.set_rest_probability(probability)
            print(f"Rest probability: {probability:.2f} ({int(rest_pct)}%)")

    def _on_fill_change(self, value):
        """Handle fill slider change"""
        fill_pct = float(value)
        self.fill_label.config(text=f"{int(fill_pct)}%")

        if self.engine:
            amount = fill_pct / 100.0
            self.engine.set_fill_amount(amount)
            print(f"Fill amount: {amount:.2f} ({int(fill_pct)}%)")

    def _on_device_change(self, event):
        """Handle audio device selection change"""
        device_name = self.device_var.get()

        # Find device index by name
        for idx, name in self.audio_devices:
            if name == device_name:
                self.selected_device = idx
                print(f"Audio device changed to: {name} (index: {idx})")

                # If playing, restart with new device
                if self.playing:
                    print("Restarting playback with new device...")
                    self._stop()
                    self._play()
                break

    def _on_swing_change(self, event):
        """Handle swing selection change"""
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
            print(f"Swing changed to: {self.swing_var.get()} ({swing_value:.2f})")

    def _toggle_play(self):
        """Toggle play/stop"""
        if self.playing:
            self._stop()
        else:
            self._play()

    def _play(self):
        """Start playback"""
        if not self.engine:
            return

        try:
            def audio_callback(outdata, frames, time_info, status):
                if status:
                    print(f"Audio status: {status}")

                chunk = self.engine.get_audio_chunk(frames)
                outdata[:, 0] = chunk

            # Use selected device
            self.stream = sd.OutputStream(
                channels=1,
                callback=audio_callback,
                samplerate=self.engine.sample_rate,
                blocksize=1024,
                device=self.selected_device
            )
            self.stream.start()

            self.playing = True
            self.play_button.config(text="⏸ Stop")
            self.status_label.config(text="Playing", foreground="green")

            device_name = next((name for idx, name in self.audio_devices if idx == self.selected_device), "Unknown")
            print(f"Playback started on device: {device_name} (index: {self.selected_device})")

        except Exception as e:
            print(f"Error starting playback: {e}")
            self.status_label.config(text=f"Error: {e}", foreground="red")

    def _stop(self):
        """Stop playback"""
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        self.playing = False
        self.play_button.config(text="▶ Play")
        self.status_label.config(text="Stopped", foreground="red")

        print("Playback stopped")

    def _update_bar_counter(self):
        """Update bar counter display"""
        if self.engine:
            self.bar_label.config(text=str(self.engine.bar_count))

        # Schedule next update
        self.root.after(100, self._update_bar_counter)

    def run(self):
        """Run the GUI"""
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _on_close(self):
        """Handle window close"""
        self._stop()
        self.root.destroy()


def main():
    """Main function"""
    print("Break Beat Engine GUI")
    print("=" * 50)

    app = BreakBeatGUI()
    app.run()


if __name__ == '__main__':
    main()
