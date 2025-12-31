"""
Stereo reverb processor - Freeverb style
Ported from EllenRipley.cpp
Numba optimized version
"""

import numpy as np
from numba import njit
from numba.typed import List


@njit(fastmath=True, cache=True)
def process_comb_filter(input_val, buffer, index, lp_state, feedback, damping):
    """
    Process single comb filter with lowpass filtering

    Returns: (output, new_index, new_lp_state)
    """
    size = len(buffer)
    output = buffer[index]

    # Lowpass filter on feedback
    lp_state = lp_state + (output - lp_state) * damping

    # Write input + filtered feedback
    buffer[index] = input_val + lp_state * feedback
    index = (index + 1) % size

    return output, index, lp_state


@njit(fastmath=True, cache=True)
def process_allpass_filter(input_val, buffer, index, gain=0.5):
    """
    Process allpass filter

    Returns: (output, new_index)
    """
    size = len(buffer)
    delayed = buffer[index]
    output = -input_val * gain + delayed
    buffer[index] = input_val + delayed * gain
    index = (index + 1) % size
    return output, index


@njit(fastmath=True, cache=True)
def process_reverb_numba(
    left_in, right_in,
    comb_buffers_l, comb_buffers_r,
    comb_indices_l, comb_indices_r,
    comb_lp_l, comb_lp_r,
    allpass_buffers, allpass_indices,
    hp_state_l, hp_state_r,
    feedback, damping_coeff, room_scale,
    sample_rate
):
    """
    Numba-optimized reverb processing

    Returns: (left_out, right_out, updated_states_tuple)
    """
    buffer_size = len(left_in)
    left_out = np.zeros(buffer_size, dtype=np.float32)
    right_out = np.zeros(buffer_size, dtype=np.float32)

    for i in range(buffer_size):
        # Scale input by room size
        input_l = left_in[i] * room_scale
        input_r = right_in[i] * room_scale

        # Process left channel comb filters
        comb_out_l = 0.0
        for j in range(4):
            out, idx, lp = process_comb_filter(
                input_l, comb_buffers_l[j], comb_indices_l[j],
                comb_lp_l[j], feedback, damping_coeff
            )
            comb_out_l += out
            comb_indices_l[j] = idx
            comb_lp_l[j] = lp

        # Process right channel comb filters
        comb_out_r = 0.0
        for j in range(4):
            out, idx, lp = process_comb_filter(
                input_r, comb_buffers_r[j], comb_indices_r[j],
                comb_lp_r[j], feedback, damping_coeff
            )
            comb_out_r += out
            comb_indices_r[j] = idx
            comb_lp_r[j] = lp

        # Scale comb output
        comb_out_l *= 0.25
        comb_out_r *= 0.25

        # Series allpass diffusion (shared for stereo)
        diffused_l = comb_out_l
        diffused_r = comb_out_r

        for j in range(4):
            out_l, idx = process_allpass_filter(diffused_l, allpass_buffers[j],
                                               allpass_indices[j])
            out_r, _ = process_allpass_filter(diffused_r, allpass_buffers[j],
                                             allpass_indices[j])
            diffused_l = out_l
            diffused_r = out_r
            allpass_indices[j] = idx

        # Highpass filter (remove sub-100Hz)
        hp_cutoff = 100.0 / (sample_rate * 0.5)
        # Manual clamp for Numba
        if hp_cutoff < 0.001:
            hp_cutoff = 0.001
        elif hp_cutoff > 0.1:
            hp_cutoff = 0.1

        hp_state_l += (diffused_l - hp_state_l) * hp_cutoff
        hp_state_r += (diffused_r - hp_state_r) * hp_cutoff

        left_out[i] = diffused_l - hp_state_l
        right_out[i] = diffused_r - hp_state_r

    return left_out, right_out, hp_state_l, hp_state_r


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
        self.comb_indices_l = np.zeros(4, dtype=np.int32)
        self.comb_indices_r = np.zeros(4, dtype=np.int32)

        # Lowpass filters for comb feedback
        self.comb_lp_l = np.zeros(4, dtype=np.float32)
        self.comb_lp_r = np.zeros(4, dtype=np.float32)

        # Allpass filters
        self.allpass_buffers = [np.zeros(size, dtype=np.float32) for size in self.ALLPASS_SIZES]
        self.allpass_indices = np.zeros(4, dtype=np.int32)

        # Highpass filter state
        self.hp_state_l = 0.0
        self.hp_state_r = 0.0

        # Parameters
        self.room_size = 0.5
        self.damping = 0.4
        self.decay = 0.6

    def process(self, left_in: np.ndarray, right_in: np.ndarray) -> tuple:
        """
        Process stereo input
        Returns: (left_out, right_out)
        """
        # Calculate feedback from decay
        feedback = 0.5 + self.decay * 0.485  # 0.5 to 0.985
        feedback = np.clip(feedback, 0.0, 0.995)

        # Damping coefficient
        damping_coeff = 0.05 + self.damping * 0.9

        # Room size scaling
        room_scale = 0.3 + self.room_size * 1.4

        # Convert lists to Numba typed Lists
        comb_buffers_l_typed = List()
        for buf in self.comb_buffers_l:
            comb_buffers_l_typed.append(buf)

        comb_buffers_r_typed = List()
        for buf in self.comb_buffers_r:
            comb_buffers_r_typed.append(buf)

        allpass_buffers_typed = List()
        for buf in self.allpass_buffers:
            allpass_buffers_typed.append(buf)

        # Call Numba-optimized function
        left_out, right_out, self.hp_state_l, self.hp_state_r = process_reverb_numba(
            left_in, right_in,
            comb_buffers_l_typed, comb_buffers_r_typed,
            self.comb_indices_l, self.comb_indices_r,
            self.comb_lp_l, self.comb_lp_r,
            allpass_buffers_typed, self.allpass_indices,
            self.hp_state_l, self.hp_state_r,
            feedback, damping_coeff, room_scale,
            self.sample_rate
        )

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
        self.comb_indices_l.fill(0)
        self.comb_indices_r.fill(0)
        self.allpass_indices.fill(0)
        self.comb_lp_l.fill(0.0)
        self.comb_lp_r.fill(0.0)
        self.hp_state_l = 0.0
        self.hp_state_r = 0.0
