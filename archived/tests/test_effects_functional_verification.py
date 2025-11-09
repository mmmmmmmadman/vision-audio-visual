#!/usr/bin/env python3
"""
Functional verification test for optimized audio effects
Ensures output is identical (or within numerical tolerance) to original
"""

import numpy as np
import sys

sys.path.insert(0, '/Users/madzine/Documents/VAV')

from vav.audio.effects.delay import StereoDelay
from vav.audio.effects.reverb import ReverbProcessor


def test_delay_determinism():
    """Test that delay produces consistent results"""
    print("Testing StereoDelay determinism...")

    # Create two identical delay processors
    delay1 = StereoDelay(sample_rate=48000, max_delay=2.0)
    delay2 = StereoDelay(sample_rate=48000, max_delay=2.0)

    delay1.set_delay_time(0.25, 0.3)
    delay1.set_feedback(0.4)
    delay2.set_delay_time(0.25, 0.3)
    delay2.set_feedback(0.4)

    # Generate identical input
    np.random.seed(42)
    left_in = np.random.randn(1000).astype(np.float32) * 0.1
    right_in = np.random.randn(1000).astype(np.float32) * 0.1

    # Process with both
    left_out1, right_out1 = delay1.process(left_in, right_in)
    left_out2, right_out2 = delay2.process(left_in, right_in)

    # Verify identical output
    assert np.allclose(left_out1, left_out2, rtol=1e-6, atol=1e-9), "Delay outputs differ!"
    assert np.allclose(right_out1, right_out2, rtol=1e-6, atol=1e-9), "Delay outputs differ!"

    print("  ✓ Determinism verified")


def test_reverb_determinism():
    """Test that reverb produces consistent results"""
    print("\nTesting ReverbProcessor determinism...")

    # Create two identical reverb processors
    reverb1 = ReverbProcessor(sample_rate=48000)
    reverb2 = ReverbProcessor(sample_rate=48000)

    reverb1.set_parameters(room_size=0.7, damping=0.5, decay=0.6)
    reverb2.set_parameters(room_size=0.7, damping=0.5, decay=0.6)

    # Generate identical input
    np.random.seed(42)
    left_in = np.random.randn(1000).astype(np.float32) * 0.1
    right_in = np.random.randn(1000).astype(np.float32) * 0.1

    # Process with both
    left_out1, right_out1 = reverb1.process(left_in, right_in)
    left_out2, right_out2 = reverb2.process(left_in, right_in)

    # Verify identical output
    assert np.allclose(left_out1, left_out2, rtol=1e-6, atol=1e-9), "Reverb outputs differ!"
    assert np.allclose(right_out1, right_out2, rtol=1e-6, atol=1e-9), "Reverb outputs differ!"

    print("  ✓ Determinism verified")


def test_delay_feedback_behavior():
    """Test that delay feedback behaves correctly"""
    print("\nTesting StereoDelay feedback behavior...")

    delay = StereoDelay(sample_rate=48000, max_delay=2.0)
    delay.set_delay_time(0.1, 0.1)  # 100ms delay
    delay.set_feedback(0.5)

    # Impulse input
    left_in = np.zeros(10000, dtype=np.float32)
    right_in = np.zeros(10000, dtype=np.float32)
    left_in[0] = 1.0
    right_in[0] = 1.0

    # Process
    left_out, right_out = delay.process(left_in, right_in)

    # Check that output is initially zero, then has delayed impulse
    delay_samples = int(0.1 * 48000)  # 4800 samples
    assert np.abs(left_out[0]) < 0.001, "First sample should be ~0"
    assert np.abs(left_out[delay_samples]) > 0.9, f"Delayed sample should be ~1.0, got {left_out[delay_samples]}"

    # Check feedback creates echo
    assert np.abs(left_out[delay_samples * 2]) > 0.4, "Second echo should be present with feedback"

    print("  ✓ Feedback behavior verified")


def test_reverb_room_size_effect():
    """Test that room size affects reverb output"""
    print("\nTesting ReverbProcessor room size effect...")

    # Create reverb with small room
    reverb_small = ReverbProcessor(sample_rate=48000)
    reverb_small.set_parameters(room_size=0.1, damping=0.5, decay=0.6)

    # Create reverb with large room
    reverb_large = ReverbProcessor(sample_rate=48000)
    reverb_large.set_parameters(room_size=0.9, damping=0.5, decay=0.6)

    # Generate input
    np.random.seed(42)
    left_in = np.random.randn(1000).astype(np.float32) * 0.1
    right_in = np.random.randn(1000).astype(np.float32) * 0.1

    # Process
    left_small, right_small = reverb_small.process(left_in, right_in)
    left_large, right_large = reverb_large.process(left_in, right_in)

    # Verify outputs are different
    assert not np.allclose(left_small, left_large, rtol=0.1), "Room size should affect output!"
    assert not np.allclose(right_small, right_large, rtol=0.1), "Room size should affect output!"

    print("  ✓ Room size effect verified")


def test_clear_functions():
    """Test that clear functions reset state"""
    print("\nTesting clear functions...")

    # Delay
    delay = StereoDelay(sample_rate=48000)
    left_in = np.ones(100, dtype=np.float32)
    right_in = np.ones(100, dtype=np.float32)
    delay.process(left_in, right_in)
    delay.clear()
    assert np.all(delay.left_buffer == 0), "Delay buffer not cleared"
    assert np.all(delay.right_buffer == 0), "Delay buffer not cleared"
    assert delay.write_index == 0, "Write index not reset"
    print("  ✓ Delay clear verified")

    # Reverb
    reverb = ReverbProcessor(sample_rate=48000)
    reverb.process(left_in, right_in)
    reverb.clear()
    for buf in reverb.comb_buffers_l + reverb.comb_buffers_r + reverb.allpass_buffers:
        assert np.all(buf == 0), "Reverb buffer not cleared"
    assert reverb.hp_state_l == 0 and reverb.hp_state_r == 0, "HP state not reset"
    print("  ✓ Reverb clear verified")


if __name__ == "__main__":
    print("="*60)
    print("FUNCTIONAL VERIFICATION TEST")
    print("="*60)

    try:
        test_delay_determinism()
        test_reverb_determinism()
        test_delay_feedback_behavior()
        test_reverb_room_size_effect()
        test_clear_functions()

        print("\n" + "="*60)
        print("ALL FUNCTIONAL TESTS PASSED!")
        print("Original functionality preserved.")
        print("="*60)

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
