"""
Chaos generator - Lorenz attractor for modulation
Ported from EllenRipley.cpp
"""

import numpy as np


class ChaosGenerator:
    """Lorenz attractor chaos generator"""

    def __init__(self, sample_rate: int = 48000):
        self.sample_rate = sample_rate
        self.x = 0.1
        self.y = 0.1
        self.z = 0.1

    def reset(self):
        """Reset to initial state"""
        self.x = 0.1
        self.y = 0.1
        self.z = 0.1

    def process(self, rate: float) -> float:
        """
        Generate chaos output
        rate: modulation rate (higher = faster chaos)
        returns: chaos value (-1 to 1)
        """
        dt = rate * 0.001

        # Lorenz attractor equations
        dx = 7.5 * (self.y - self.x)
        dy = self.x * (30.9 - self.z) - self.y
        dz = self.x * self.y - 1.02 * self.z

        self.x += dx * dt
        self.y += dy * dt
        self.z += dz * dt

        # Prevent numerical explosion
        if (not np.isfinite(self.x) or not np.isfinite(self.y) or
            not np.isfinite(self.z) or
            abs(self.x) > 100.0 or abs(self.y) > 100.0 or abs(self.z) > 100.0):
            self.reset()

        return np.clip(self.x * 0.1, -1.0, 1.0)

    def process_buffer(self, buffer_size: int, rate: float) -> np.ndarray:
        """Generate buffer of chaos values"""
        output = np.zeros(buffer_size, dtype=np.float32)
        for i in range(buffer_size):
            output[i] = self.process(rate)
        return output
