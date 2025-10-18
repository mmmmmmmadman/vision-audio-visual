"""
Audio analysis for visual feedback
"""

import numpy as np
from scipy import signal


class AudioAnalyzer:
    """Real-time audio feature extraction"""

    def __init__(self, sample_rate: int = 48000, buffer_size: int = 1024):
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size

        # FFT parameters
        self.fft_size = 2048
        self.window = signal.windows.hann(self.fft_size)

        # Feature history
        self.rms_history = []
        self.peak_history = []
        self.spectrum_history = []

    def analyze(self, audio_buffer: np.ndarray) -> dict:
        """
        Analyze audio buffer and extract features
        Returns dict with: rms, peak, spectrum, centroid, etc.
        """
        # RMS level
        rms = np.sqrt(np.mean(audio_buffer ** 2))

        # Peak level
        peak = np.max(np.abs(audio_buffer))

        # Spectral analysis
        if len(audio_buffer) >= self.fft_size:
            # Take last FFT_SIZE samples
            fft_input = audio_buffer[-self.fft_size:] * self.window
            spectrum = np.abs(np.fft.rfft(fft_input))
            spectrum = spectrum / np.max(spectrum + 1e-10)  # Normalize

            # Spectral centroid
            freqs = np.fft.rfftfreq(self.fft_size, 1.0 / self.sample_rate)
            centroid = np.sum(freqs * spectrum) / (np.sum(spectrum) + 1e-10)

            # Spectral energy in bands
            bass = np.mean(spectrum[: int(len(spectrum) * 0.1)])  # 0-10%
            mid = np.mean(spectrum[int(len(spectrum) * 0.1): int(len(spectrum) * 0.5)])
            high = np.mean(spectrum[int(len(spectrum) * 0.5):])

        else:
            spectrum = np.zeros(self.fft_size // 2 + 1)
            centroid = 0.0
            bass = mid = high = 0.0

        # Update history
        self.rms_history.append(rms)
        self.peak_history.append(peak)
        if len(self.rms_history) > 100:
            self.rms_history.pop(0)
            self.peak_history.pop(0)

        return {
            "rms": float(rms),
            "peak": float(peak),
            "spectrum": spectrum,
            "centroid": float(centroid),
            "bass": float(bass),
            "mid": float(mid),
            "high": float(high),
            "rms_avg": float(np.mean(self.rms_history)) if self.rms_history else 0.0,
        }

    def get_visual_parameters(self, features: dict) -> dict:
        """
        Convert audio features to visual parameters
        Returns parameters for visual rendering
        """
        rms = features["rms"]
        peak = features["peak"]
        centroid = features["centroid"]
        bass = features["bass"]
        mid = features["mid"]
        high = features["high"]

        return {
            "brightness": np.clip(rms * 3.0, 0.0, 1.0),
            "color_shift": np.clip(centroid / 10000.0, 0.0, 1.0),
            "bass_intensity": np.clip(bass * 5.0, 0.0, 1.0),
            "mid_intensity": np.clip(mid * 5.0, 0.0, 1.0),
            "high_intensity": np.clip(high * 5.0, 0.0, 1.0),
            "energy": np.clip(peak, 0.0, 1.0),
        }

    def detect_onset(self, current_rms: float, threshold: float = 1.5) -> bool:
        """Detect audio onset/transient"""
        if len(self.rms_history) < 2:
            return False

        avg_rms = np.mean(self.rms_history[-10:]) if len(self.rms_history) >= 10 else self.rms_history[-1]

        return current_rms > avg_rms * threshold

    def clear(self):
        """Clear history"""
        self.rms_history.clear()
        self.peak_history.clear()
        self.spectrum_history.clear()
