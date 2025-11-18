"""
Granular processor
Ported from EllenRipley.cpp
"""

import numpy as np


class Grain:
    """Single grain"""

    def __init__(self):
        self.active = False
        self.position = 0.0
        self.size = 0.0
        self.envelope = 0.0
        self.direction = 1.0
        self.pitch = 1.0


class GrainProcessor:
    """Granular synthesis/processing"""

    GRAIN_BUFFER_SIZE = 8192
    MAX_GRAINS = 16

    def __init__(self, sample_rate: int = 48000):
        self.sample_rate = sample_rate

        # Grain buffer
        self.buffer = np.zeros(self.GRAIN_BUFFER_SIZE, dtype=np.float32)
        self.write_index = 0

        # Active grains
        self.grains = [Grain() for _ in range(self.MAX_GRAINS)]

        # Parameters
        self.grain_size = 0.3  # 0-1
        self.density = 0.4  # 0-1
        self.position = 0.5  # 0-1

        # Trigger phase
        self.phase = 0.0

    def process(self, input_signal: np.ndarray) -> np.ndarray:
        """Process input through granulator"""
        output = np.zeros_like(input_signal)

        for i, sample in enumerate(input_signal):
            # Write to buffer
            self.buffer[self.write_index] = sample
            self.write_index = (self.write_index + 1) % self.GRAIN_BUFFER_SIZE

            # Calculate grain size in samples
            grain_size_ms = self.grain_size * 99.0 + 1.0  # 1-100ms
            grain_samples = int((grain_size_ms / 1000.0) * self.sample_rate)

            # Trigger rate based on density
            trigger_rate = self.density * 50.0 + 1.0  # 1-51 Hz
            self.phase += trigger_rate / self.sample_rate

            # Trigger new grain
            if self.phase >= 1.0:
                self.phase -= 1.0
                self._trigger_grain(grain_samples)

            # Process active grains
            grain_output = 0.0
            active_count = 0

            for grain in self.grains:
                if not grain.active:
                    continue

                # Calculate envelope position
                env_phase = grain.envelope / grain.size

                if env_phase >= 1.0:
                    grain.active = False
                    continue

                # Hann window envelope
                env = 0.5 * (1.0 - np.cos(env_phase * 2.0 * np.pi))

                # Read from buffer
                read_pos = int(grain.position) % self.GRAIN_BUFFER_SIZE
                sample_val = self.buffer[read_pos]

                grain_output += sample_val * env

                # Update grain position
                grain.position += grain.direction * grain.pitch
                grain.position = grain.position % self.GRAIN_BUFFER_SIZE

                grain.envelope += 1.0
                active_count += 1

            # Mix grain output
            if active_count > 0:
                grain_output /= np.sqrt(active_count)

            output[i] = grain_output

        return output

    def _trigger_grain(self, size: float):
        """Trigger new grain"""
        for grain in self.grains:
            if not grain.active:
                grain.active = True
                grain.size = size
                grain.envelope = 0.0
                grain.direction = 1.0
                grain.pitch = 1.0

                # Set grain position based on position parameter
                pos = self.position * self.GRAIN_BUFFER_SIZE
                grain.position = pos
                break

    def set_parameters(self, size: float = None, density: float = None,
                      position: float = None):
        """Set grain parameters"""
        if size is not None:
            self.grain_size = np.clip(size, 0.0, 1.0)
        if density is not None:
            self.density = np.clip(density, 0.0, 1.0)
        if position is not None:
            self.position = np.clip(position, 0.0, 1.0)

    def clear(self):
        """Clear buffer and reset grains"""
        self.buffer.fill(0.0)
        self.write_index = 0
        for grain in self.grains:
            grain.active = False
        self.phase = 0.0
