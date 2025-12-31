"""
Base signal classes for CV generation
"""

import numpy as np
from typing import List
from abc import ABC, abstractmethod


class CVSignal(ABC):
    """Base class for CV signal generators"""

    def __init__(self, sample_rate: int = 48000):
        self.sample_rate = sample_rate
        self.value = 0.0

    @abstractmethod
    def process(self) -> float:
        """Generate next sample"""
        pass

    def get_voltage(self) -> float:
        """Get current voltage (0-10V Eurorack standard)"""
        return np.clip(self.value * 10.0, 0.0, 10.0)

    def reset(self):
        """Reset signal state"""
        self.value = 0.0


class SignalBuffer:
    """Circular buffer for signal history"""

    def __init__(self, size: int = 1024):
        self.size = size
        self.buffer = np.zeros(size, dtype=np.float32)
        self.index = 0

    def write(self, value: float):
        """Write value to buffer"""
        self.buffer[self.index] = value
        self.index = (self.index + 1) % self.size

    def read(self, num_samples: int = None) -> np.ndarray:
        """Read recent samples"""
        if num_samples is None:
            num_samples = self.size

        # Return samples in chronological order
        if self.index >= num_samples:
            return self.buffer[self.index - num_samples : self.index]
        else:
            # Wrap around
            return np.concatenate(
                [
                    self.buffer[self.size - (num_samples - self.index) :],
                    self.buffer[: self.index],
                ]
            )

    def clear(self):
        """Clear buffer"""
        self.buffer.fill(0.0)
        self.index = 0
