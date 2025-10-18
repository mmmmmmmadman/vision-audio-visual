"""
Decay envelope generator for CV signals
"""

import numpy as np
from .signal import CVSignal


class DecayEnvelope(CVSignal):
    """Exponential decay envelope generator"""

    def __init__(self, sample_rate: int = 48000, decay_time: float = 1.0):
        super().__init__(sample_rate)
        self.decay_time = decay_time  # seconds
        self.decay_coeff = 0.0
        self.is_active = False
        self.update_decay_coeff()

    def update_decay_coeff(self):
        """Calculate decay coefficient from decay time"""
        # Exponential decay: v(t) = e^(-t/tau)
        # After decay_time seconds, value should be ~0.01
        self.decay_coeff = np.exp(-1.0 / (self.decay_time * self.sample_rate))

    def trigger(self):
        """Trigger envelope"""
        self.value = 1.0
        self.is_active = True

    def process(self) -> float:
        """Generate next sample"""
        if self.is_active:
            self.value *= self.decay_coeff

            # Stop when value is very small
            if self.value < 0.001:
                self.value = 0.0
                self.is_active = False

        return self.value

    def set_decay_time(self, time: float):
        """Set decay time in seconds"""
        self.decay_time = np.clip(time, 0.01, 10.0)
        self.update_decay_coeff()

    def reset(self):
        """Reset envelope"""
        super().reset()
        self.is_active = False
