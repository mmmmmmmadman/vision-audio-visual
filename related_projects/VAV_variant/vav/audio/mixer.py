"""
4-track stereo mixer
"""

import numpy as np
from typing import List


class StereoChannel:
    """Single stereo channel"""

    def __init__(self):
        self.volume = 1.0
        self.pan = 0.0  # -1.0 (left) to 1.0 (right)
        self.mute = False
        self.solo = False

    def process(self, left: np.ndarray, right: np.ndarray) -> tuple:
        """Process stereo input"""
        if self.mute:
            return np.zeros_like(left), np.zeros_like(right)

        # Apply volume
        left = left * self.volume
        right = right * self.volume

        # Apply pan (constant power panning)
        if self.pan < 0:
            # Pan left
            pan_factor = 1.0 + self.pan
            left_gain = 1.0
            right_gain = pan_factor
        else:
            # Pan right
            pan_factor = 1.0 - self.pan
            left_gain = pan_factor
            right_gain = 1.0

        left = left * left_gain
        right = right * right_gain

        return left, right


class StereoMixer:
    """4-track stereo mixer"""

    def __init__(self, num_channels: int = 4):
        self.num_channels = num_channels
        self.channels = [StereoChannel() for _ in range(num_channels)]
        self.master_volume = 1.0

    def process(self, inputs: List[tuple]) -> tuple:
        """
        Process multiple stereo inputs and mix to stereo output
        inputs: list of (left, right) tuples
        returns: (left_mix, right_mix)
        """
        if not inputs:
            return np.zeros(1), np.zeros(1)

        # Check for solo channels
        any_solo = any(ch.solo for ch in self.channels)

        # Mix all channels
        left_mix = np.zeros_like(inputs[0][0])
        right_mix = np.zeros_like(inputs[0][1])

        for i, (left, right) in enumerate(inputs[:self.num_channels]):
            if i >= len(self.channels):
                break

            channel = self.channels[i]

            # Skip if any channel is solo and this isn't one
            if any_solo and not channel.solo:
                continue

            # Process channel
            ch_left, ch_right = channel.process(left, right)

            # Add to mix
            left_mix += ch_left
            right_mix += ch_right

        # Apply master volume
        left_mix *= self.master_volume
        right_mix *= self.master_volume

        # Soft clip to prevent harsh clipping
        left_mix = np.tanh(left_mix)
        right_mix = np.tanh(right_mix)

        return left_mix, right_mix

    def set_channel_volume(self, channel: int, volume: float):
        """Set channel volume (0-2)"""
        if 0 <= channel < self.num_channels:
            self.channels[channel].volume = np.clip(volume, 0.0, 2.0)

    def set_channel_pan(self, channel: int, pan: float):
        """Set channel pan (-1 to 1)"""
        if 0 <= channel < self.num_channels:
            self.channels[channel].pan = np.clip(pan, -1.0, 1.0)

    def set_channel_mute(self, channel: int, mute: bool):
        """Set channel mute"""
        if 0 <= channel < self.num_channels:
            self.channels[channel].mute = mute

    def set_channel_solo(self, channel: int, solo: bool):
        """Set channel solo"""
        if 0 <= channel < self.num_channels:
            self.channels[channel].solo = solo
