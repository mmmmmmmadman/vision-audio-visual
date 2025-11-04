"""
Stereo delay with feedback
Ported from EllenRipley.cpp
Numba optimized version
"""

import numpy as np
from numba import njit


@njit(fastmath=True, cache=True)
def process_stereo_delay_numba(
    left_in, right_in,
    left_buffer, right_buffer,
    write_index,
    delay_samples_l, delay_samples_r,
    feedback,
    buffer_size_max
):
    """
    Numba-optimized stereo delay processing

    Returns: (left_out, right_out, final_write_index)
    """
    buffer_len = len(left_in)
    left_out = np.zeros(buffer_len, dtype=np.float32)
    right_out = np.zeros(buffer_len, dtype=np.float32)

    for i in range(buffer_len):
        # Calculate read indices
        read_index_l = (write_index - delay_samples_l) % buffer_size_max
        read_index_r = (write_index - delay_samples_r) % buffer_size_max

        # Read delayed signals
        left_delayed = left_buffer[read_index_l]
        right_delayed = right_buffer[read_index_r]

        # Write input + feedback to buffer
        left_buffer[write_index] = left_in[i] + left_delayed * feedback
        right_buffer[write_index] = right_in[i] + right_delayed * feedback

        # Output delayed signals
        left_out[i] = left_delayed
        right_out[i] = right_delayed

        # Advance write index
        write_index = (write_index + 1) % buffer_size_max

    return left_out, right_out, write_index


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
        # Calculate delay samples
        delay_samples_l = int(self.delay_time_l * self.sample_rate)
        delay_samples_r = int(self.delay_time_r * self.sample_rate)

        delay_samples_l = np.clip(delay_samples_l, 1, self.buffer_size - 1)
        delay_samples_r = np.clip(delay_samples_r, 1, self.buffer_size - 1)

        # Call Numba-optimized function
        left_out, right_out, self.write_index = process_stereo_delay_numba(
            left_in, right_in,
            self.left_buffer, self.right_buffer,
            self.write_index,
            delay_samples_l, delay_samples_r,
            self.feedback,
            self.buffer_size
        )

        return left_out, right_out

    def clear(self):
        """Clear delay buffers"""
        self.left_buffer.fill(0.0)
        self.right_buffer.fill(0.0)
        self.write_index = 0
