"""
Ellen Ripley - Complete effects chain
Stereo Delay → Grain → Reverb with Chaos modulation
Ported from EllenRipley.cpp
"""

import numpy as np
from .delay import StereoDelay
from .grain import GrainProcessor
from .reverb import ReverbProcessor
from .chaos import ChaosGenerator


class EllenRipleyEffectChain:
    """
    Complete Ellen Ripley effect chain

    Features:
    - Stereo delay with independent L/R times
    - Granular processor (GRATCH)
    - Stereo reverb
    - Chaos generator with modulation
    - Wet/Dry control for each effect
    """

    def __init__(self, sample_rate: int = 48000):
        self.sample_rate = sample_rate

        # Initialize processors
        self.delay = StereoDelay(sample_rate=sample_rate, max_delay=2.0)
        self.grain_l = GrainProcessor(sample_rate=sample_rate)
        self.grain_r = GrainProcessor(sample_rate=sample_rate)
        self.reverb = ReverbProcessor(sample_rate=sample_rate)
        self.chaos = ChaosGenerator(sample_rate=sample_rate)

        # Parameters
        self.delay_time_l = 0.25  # seconds
        self.delay_time_r = 0.25
        self.delay_feedback = 0.3
        self.delay_chaos_enabled = False
        self.delay_wet_dry = 0.0  # 0=dry, 1=wet

        self.grain_size = 0.3
        self.grain_density = 0.4
        self.grain_position = 0.5
        self.grain_chaos_enabled = False
        self.grain_wet_dry = 0.0

        self.reverb_room_size = 0.5
        self.reverb_damping = 0.4
        self.reverb_decay = 0.6
        self.reverb_chaos_enabled = False
        self.reverb_wet_dry = 0.0

        self.chaos_rate = 0.01
        self.chaos_amount = 1.0
        self.chaos_shape = False  # False=smooth, True=stepped

        # Chaos step state
        self.last_step_value = 0.0
        self.step_phase = 0.0

    def set_delay_params(self, time_l: float = None, time_r: float = None,
                        feedback: float = None, chaos_enabled: bool = None,
                        wet_dry: float = None):
        """Set delay parameters"""
        if time_l is not None:
            self.delay_time_l = np.clip(time_l, 0.001, 2.0)
        if time_r is not None:
            self.delay_time_r = np.clip(time_r, 0.001, 2.0)
        if feedback is not None:
            self.delay_feedback = np.clip(feedback, 0.0, 0.95)
        if chaos_enabled is not None:
            self.delay_chaos_enabled = chaos_enabled
        if wet_dry is not None:
            self.delay_wet_dry = np.clip(wet_dry, 0.0, 1.0)

    def set_grain_params(self, size: float = None, density: float = None,
                        position: float = None, chaos_enabled: bool = None,
                        wet_dry: float = None):
        """Set grain parameters"""
        if size is not None:
            self.grain_size = np.clip(size, 0.0, 1.0)
        if density is not None:
            self.grain_density = np.clip(density, 0.0, 1.0)
        if position is not None:
            self.grain_position = np.clip(position, 0.0, 1.0)
        if chaos_enabled is not None:
            self.grain_chaos_enabled = chaos_enabled
        if wet_dry is not None:
            self.grain_wet_dry = np.clip(wet_dry, 0.0, 1.0)

    def set_reverb_params(self, room_size: float = None, damping: float = None,
                         decay: float = None, chaos_enabled: bool = None,
                         wet_dry: float = None):
        """Set reverb parameters"""
        if room_size is not None:
            self.reverb_room_size = np.clip(room_size, 0.0, 1.0)
        if damping is not None:
            self.reverb_damping = np.clip(damping, 0.0, 1.0)
        if decay is not None:
            self.reverb_decay = np.clip(decay, 0.0, 1.0)
        if chaos_enabled is not None:
            self.reverb_chaos_enabled = chaos_enabled
        if wet_dry is not None:
            self.reverb_wet_dry = np.clip(wet_dry, 0.0, 1.0)

    def set_chaos_params(self, rate: float = None, amount: float = None,
                        shape: bool = None):
        """Set chaos generator parameters"""
        if rate is not None:
            self.chaos_rate = np.clip(rate, 0.0, 1.0)
        if amount is not None:
            self.chaos_amount = np.clip(amount, 0.0, 1.0)
        if shape is not None:
            self.chaos_shape = shape

    def _get_chaos_value(self) -> float:
        """Get current chaos modulation value"""
        # Determine chaos rate based on shape
        if self.chaos_shape:
            # Shape ON: 1.0-10.0 range (faster)
            rate = 1.0 + self.chaos_rate * 9.0
        else:
            # Shape OFF: 0.01-1.0 range (slower)
            rate = 0.01 + self.chaos_rate * 0.99

        # Generate raw chaos
        chaos_raw = self.chaos.process(rate) * self.chaos_amount

        # Apply shape (stepped or smooth)
        if self.chaos_shape:
            # Stepped output
            step_rate = rate * 10.0
            self.step_phase += step_rate / self.sample_rate
            if self.step_phase >= 1.0:
                self.last_step_value = chaos_raw
                self.step_phase = 0.0
            return self.last_step_value
        else:
            # Smooth output
            return chaos_raw

    def process(self, left_in: np.ndarray, right_in: np.ndarray) -> tuple:
        """
        Process stereo input through the complete effect chain

        Chain order: Input → Delay → Grain → Reverb → Output

        Returns: (left_out, right_out, chaos_cv)
        """
        buffer_size = len(left_in)
        chaos_cv = np.zeros(buffer_size, dtype=np.float32)

        # Initialize outputs
        left_out = left_in.copy()
        right_out = right_in.copy()

        # Process sample by sample to apply chaos modulation
        for i in range(buffer_size):
            # Generate chaos value
            chaos_value = self._get_chaos_value()
            chaos_cv[i] = chaos_value * 5.0  # Scale to ±5V CV range

            # === Stage 1: Delay ===
            delay_time_l = self.delay_time_l
            delay_time_r = self.delay_time_r
            delay_feedback = self.delay_feedback

            if self.delay_chaos_enabled:
                delay_time_l += chaos_value * 0.1
                delay_time_r += chaos_value * 0.1
                delay_feedback += chaos_value * 0.1

            delay_time_l = np.clip(delay_time_l, 0.001, 2.0)
            delay_time_r = np.clip(delay_time_r, 0.001, 2.0)
            delay_feedback = np.clip(delay_feedback, 0.0, 0.95)

            self.delay.set_delay_time(delay_time_l, delay_time_r)
            self.delay.set_feedback(delay_feedback)

        # Process delay (batch)
        delay_l, delay_r = self.delay.process(left_out, right_out)

        # Mix delay wet/dry
        left_out = left_out * (1.0 - self.delay_wet_dry) + delay_l * self.delay_wet_dry
        right_out = right_out * (1.0 - self.delay_wet_dry) + delay_r * self.delay_wet_dry

        # === Stage 2: Grain ===
        grain_size = self.grain_size
        grain_density = self.grain_density
        grain_position = self.grain_position

        # Apply chaos modulation to grain parameters
        if self.grain_chaos_enabled:
            # Get average chaos for this buffer
            avg_chaos = np.mean(chaos_cv) / 5.0

            # Modulate grain parameters
            grain_density = np.clip(grain_density + avg_chaos * 0.3, 0.0, 1.0)
            grain_position = np.clip(grain_position + avg_chaos * 0.2, 0.0, 1.0)

            # Random direction and pitch variations
            if avg_chaos > 0.3:
                # Add some randomness to grains
                for grain in self.grain_l.grains:
                    if grain.active and np.random.random() < 0.3:
                        grain.direction = -1.0 if np.random.random() < 0.5 else 1.0
                for grain in self.grain_r.grains:
                    if grain.active and np.random.random() < 0.3:
                        grain.direction = -1.0 if np.random.random() < 0.5 else 1.0

        self.grain_l.set_parameters(size=grain_size, density=grain_density, position=grain_position)
        self.grain_r.set_parameters(size=grain_size, density=grain_density, position=grain_position)

        grain_l = self.grain_l.process(left_out)
        grain_r = self.grain_r.process(right_out)

        # Mix grain wet/dry
        left_out = left_out * (1.0 - self.grain_wet_dry) + grain_l * self.grain_wet_dry
        right_out = right_out * (1.0 - self.grain_wet_dry) + grain_r * self.grain_wet_dry

        # === Stage 3: Reverb ===
        reverb_room = self.reverb_room_size
        reverb_damp = self.reverb_damping
        reverb_decay = self.reverb_decay

        if self.reverb_chaos_enabled:
            avg_chaos = np.mean(chaos_cv) / 5.0
            reverb_decay = np.clip(reverb_decay + avg_chaos * 0.5, 0.0, 1.0)

        self.reverb.set_parameters(
            room_size=reverb_room,
            damping=reverb_damp,
            decay=reverb_decay
        )

        reverb_l, reverb_r = self.reverb.process(left_out, right_out)

        # Mix reverb wet/dry
        left_out = left_out * (1.0 - self.reverb_wet_dry) + reverb_l * self.reverb_wet_dry
        right_out = right_out * (1.0 - self.reverb_wet_dry) + reverb_r * self.reverb_wet_dry

        return left_out, right_out, chaos_cv

    def clear(self):
        """Clear all internal buffers"""
        self.delay.clear()
        self.grain_l.clear()
        self.grain_r.clear()
        self.reverb.clear()
        self.chaos.reset()
        self.step_phase = 0.0
        self.last_step_value = 0.0
