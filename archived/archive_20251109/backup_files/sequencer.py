"""
Sequence CV generator
"""

import numpy as np
from .signal import CVSignal
from typing import List


class SequenceCV(CVSignal):
    """Step sequencer for CV output"""

    def __init__(
        self,
        sample_rate: int = 48000,
        num_steps: int = 16,
        clock_rate: float = 120.0,  # BPM
    ):
        super().__init__(sample_rate)
        self.num_steps = num_steps
        self.clock_rate = clock_rate
        self.sequence = np.zeros(num_steps, dtype=np.float32)
        self.current_step = 0
        self.phase = 0.0
        self.samples_per_step = 0
        self.step_changed = False
        self.update_clock()

    def update_clock(self):
        """Calculate samples per step from BPM"""
        # Convert BPM to samples per step
        beats_per_second = self.clock_rate / 60.0
        self.samples_per_step = int(self.sample_rate / beats_per_second)

    def set_sequence(self, values: List[float]):
        """Set sequence values (0-1 range)"""
        self.sequence = np.array(values[: self.num_steps], dtype=np.float32)
        if len(values) < self.num_steps:
            # Pad with zeros
            self.sequence = np.pad(
                self.sequence, (0, self.num_steps - len(values)), constant_values=0
            )

    def set_sequence_from_positions(self, positions: List[float]):
        """Generate sequence from cable positions"""
        # Map positions (0-1) to voltages
        self.sequence = np.array(positions[: self.num_steps], dtype=np.float32)
        if len(positions) < self.num_steps:
            # Pad with last value
            last_val = positions[-1] if positions else 0.0
            self.sequence = np.pad(
                self.sequence,
                (0, self.num_steps - len(positions)),
                constant_values=last_val,
            )

    def process(self) -> float:
        """Generate next sample"""
        self.step_changed = False  # Reset before checking
        self.phase += 1

        if self.phase >= self.samples_per_step:
            self.phase = 0
            self.current_step = (self.current_step + 1) % self.num_steps
            self.step_changed = True  # Mark that step changed

        self.value = self.sequence[self.current_step]
        return self.value

    def did_step_change(self) -> bool:
        """Check if the step changed on the last process() call"""
        result = self.step_changed
        # Don't reset here - let process() reset it next time
        return result

    def set_clock_rate(self, bpm: float):
        """Set clock rate in BPM"""
        self.clock_rate = np.clip(bpm, 1.0, 999.0)
        self.update_clock()

    def set_num_steps(self, steps: int):
        """Set number of steps"""
        old_sequence = self.sequence.copy()
        self.num_steps = np.clip(steps, 1, 32)
        self.sequence = np.zeros(self.num_steps, dtype=np.float32)

        # Copy old values
        copy_len = min(len(old_sequence), self.num_steps)
        self.sequence[:copy_len] = old_sequence[:copy_len]

        self.current_step = min(self.current_step, self.num_steps - 1)

    def reset(self):
        """Reset sequencer"""
        super().reset()
        self.current_step = 0
        self.phase = 0.0
