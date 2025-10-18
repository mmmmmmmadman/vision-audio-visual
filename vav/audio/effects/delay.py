"""
Stereo delay with feedback
Ported from EllenRipley.cpp
"""

import numpy as np


class StereoDelay:
    """Stereo delay processor"""

    def __init__(self, sample_rate: int = 48000, max_delay: float = 2.0):
        self.sample_rate = sample_rate
        self.max_delay = max_delay

        # Calculate buffer size
        self.buffer_size = int(max_delay * sample_rate)

        # Create delay buffers
        self.left_buffer = np.zeros(self.buffer_size, dtype=np.float32)
        self.right_buffer = np.zeros(self.buffer_size, dtype=np.float32)
        self.write_index = 0

        # Parameters
        self.delay_time_l = 0.25  # seconds
        self.delay_time_r = 0.25
        self.feedback = 0.3

    def set_delay_time(self, left: float, right: float):
        """Set delay times in seconds"""
        self.delay_time_l = np.clip(left, 0.001, self.max_delay)
        self.delay_time_r = np.clip(right, 0.001, self.max_delay)

    def set_feedback(self, feedback: float):
        """Set feedback amount (0-0.95)"""
        self.feedback = np.clip(feedback, 0.0, 0.95)

    def process(self, left_in: np.ndarray, right_in: np.ndarray) -> tuple:
        """
        Process stereo input
        Returns: (left_out, right_out)
        """
        buffer_size = len(left_in)
        left_out = np.zeros(buffer_size, dtype=np.float32)
        right_out = np.zeros(buffer_size, dtype=np.float32)

        # Calculate delay samples
        delay_samples_l = int(self.delay_time_l * self.sample_rate)
        delay_samples_r = int(self.delay_time_r * self.sample_rate)

        delay_samples_l = np.clip(delay_samples_l, 1, self.buffer_size - 1)
        delay_samples_r = np.clip(delay_samples_r, 1, self.buffer_size - 1)

        for i in range(buffer_size):
            # Calculate read indices
            read_index_l = (self.write_index - delay_samples_l) % self.buffer_size
            read_index_r = (self.write_index - delay_samples_r) % self.buffer_size

            # Read delayed signals
            left_delayed = self.left_buffer[read_index_l]
            right_delayed = self.right_buffer[read_index_r]

            # Write input + feedback to buffer
            self.left_buffer[self.write_index] = left_in[i] + left_delayed * self.feedback
            self.right_buffer[self.write_index] = right_in[i] + right_delayed * self.feedback

            # Output delayed signals
            left_out[i] = left_delayed
            right_out[i] = right_delayed

            # Advance write index
            self.write_index = (self.write_index + 1) % self.buffer_size

        return left_out, right_out

    def clear(self):
        """Clear delay buffers"""
        self.left_buffer.fill(0.0)
        self.right_buffer.fill(0.0)
        self.write_index = 0
