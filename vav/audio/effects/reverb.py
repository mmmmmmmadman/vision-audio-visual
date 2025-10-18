"""
Stereo reverb processor - Freeverb style
Ported from EllenRipley.cpp
"""

import numpy as np


class ReverbProcessor:
    """Stereo reverb with comb and allpass filters"""

    # Comb filter sizes (samples at 48kHz)
    COMB_SIZES = [1557, 1617, 1491, 1422, 1277, 1356, 1188, 1116]
    ALLPASS_SIZES = [556, 441, 341, 225]

    def __init__(self, sample_rate: int = 48000):
        self.sample_rate = sample_rate

        # Comb filters (4 per channel)
        self.comb_buffers_l = [np.zeros(size, dtype=np.float32) for size in self.COMB_SIZES[:4]]
        self.comb_buffers_r = [np.zeros(size, dtype=np.float32) for size in self.COMB_SIZES[4:]]
        self.comb_indices_l = [0] * 4
        self.comb_indices_r = [0] * 4

        # Lowpass filters for comb feedback
        self.comb_lp_l = [0.0] * 4
        self.comb_lp_r = [0.0] * 4

        # Allpass filters
        self.allpass_buffers = [np.zeros(size, dtype=np.float32) for size in self.ALLPASS_SIZES]
        self.allpass_indices = [0] * 4

        # Highpass filter state
        self.hp_state_l = 0.0
        self.hp_state_r = 0.0

        # Parameters
        self.room_size = 0.5
        self.damping = 0.4
        self.decay = 0.6

    def _process_comb(self, input_val: float, buffer: np.ndarray, index: int,
                      lp_state: float, feedback: float, damping: float) -> tuple:
        """Process single comb filter, returns (output, new_index, new_lp_state)"""
        size = len(buffer)
        output = buffer[index]

        # Lowpass filter on feedback
        lp_state = lp_state + (output - lp_state) * damping

        # Write input + filtered feedback
        buffer[index] = input_val + lp_state * feedback
        index = (index + 1) % size

        return output, index, lp_state

    def _process_allpass(self, input_val: float, buffer: np.ndarray,
                        index: int, gain: float = 0.5) -> tuple:
        """Process allpass filter, returns (output, new_index)"""
        size = len(buffer)
        delayed = buffer[index]
        output = -input_val * gain + delayed
        buffer[index] = input_val + delayed * gain
        index = (index + 1) % size
        return output, index

    def process(self, left_in: np.ndarray, right_in: np.ndarray) -> tuple:
        """
        Process stereo input
        Returns: (left_out, right_out)
        """
        buffer_size = len(left_in)
        left_out = np.zeros(buffer_size, dtype=np.float32)
        right_out = np.zeros(buffer_size, dtype=np.float32)

        # Calculate feedback from decay
        feedback = 0.5 + self.decay * 0.485  # 0.5 to 0.985
        feedback = np.clip(feedback, 0.0, 0.995)

        # Damping coefficient
        damping_coeff = 0.05 + self.damping * 0.9

        # Room size scaling
        room_scale = 0.3 + self.room_size * 1.4

        for i in range(buffer_size):
            # Scale input by room size
            input_l = left_in[i] * room_scale
            input_r = right_in[i] * room_scale

            # Process left channel comb filters
            comb_out_l = 0.0
            for j in range(4):
                out, idx, lp = self._process_comb(
                    input_l, self.comb_buffers_l[j], self.comb_indices_l[j],
                    self.comb_lp_l[j], feedback, damping_coeff
                )
                comb_out_l += out
                self.comb_indices_l[j] = idx
                self.comb_lp_l[j] = lp

            # Process right channel comb filters
            comb_out_r = 0.0
            for j in range(4):
                out, idx, lp = self._process_comb(
                    input_r, self.comb_buffers_r[j], self.comb_indices_r[j],
                    self.comb_lp_r[j], feedback, damping_coeff
                )
                comb_out_r += out
                self.comb_indices_r[j] = idx
                self.comb_lp_r[j] = lp

            # Scale comb output
            comb_out_l *= 0.25
            comb_out_r *= 0.25

            # Series allpass diffusion (shared for stereo)
            diffused_l = comb_out_l
            diffused_r = comb_out_r

            for j in range(4):
                out_l, idx = self._process_allpass(diffused_l, self.allpass_buffers[j],
                                                   self.allpass_indices[j])
                out_r, _ = self._process_allpass(diffused_r, self.allpass_buffers[j],
                                                 self.allpass_indices[j])
                diffused_l = out_l
                diffused_r = out_r
                self.allpass_indices[j] = idx

            # Highpass filter (remove sub-100Hz)
            hp_cutoff = 100.0 / (self.sample_rate * 0.5)
            hp_cutoff = np.clip(hp_cutoff, 0.001, 0.1)

            self.hp_state_l += (diffused_l - self.hp_state_l) * hp_cutoff
            self.hp_state_r += (diffused_r - self.hp_state_r) * hp_cutoff

            left_out[i] = diffused_l - self.hp_state_l
            right_out[i] = diffused_r - self.hp_state_r

        return left_out, right_out

    def set_parameters(self, room_size: float = None, damping: float = None,
                      decay: float = None):
        """Set reverb parameters (0-1)"""
        if room_size is not None:
            self.room_size = np.clip(room_size, 0.0, 1.0)
        if damping is not None:
            self.damping = np.clip(damping, 0.0, 1.0)
        if decay is not None:
            self.decay = np.clip(decay, 0.0, 1.0)

    def clear(self):
        """Clear all buffers"""
        for buf in self.comb_buffers_l + self.comb_buffers_r + self.allpass_buffers:
            buf.fill(0.0)
        self.comb_indices_l = [0] * 4
        self.comb_indices_r = [0] * 4
        self.allpass_indices = [0] * 4
        self.comb_lp_l = [0.0] * 4
        self.comb_lp_r = [0.0] * 4
        self.hp_state_l = 0.0
        self.hp_state_r = 0.0
