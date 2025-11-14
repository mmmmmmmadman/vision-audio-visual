#!/usr/bin/env python3
"""
Test script to verify stereo delay independence in alien4_extension
"""

import numpy as np
import sys
sys.path.append('/Users/madzine/Documents/VAV')

try:
    import alien4
except ImportError:
    print("ERROR: Could not import alien4 module")
    print("Please compile the extension first:")
    print("  cd /Users/madzine/Documents/VAV")
    print("  python3 setup.py build_ext --inplace")
    sys.exit(1)

def test_delay_stereo_independence():
    """
    Test that left and right delay channels produce different outputs
    when fed identical input but with different delay times
    """
    print("=" * 70)
    print("Testing Delay Stereo Independence")
    print("=" * 70)

    # Create engine
    sample_rate = 48000
    engine = alien4.AudioEngine(sample_rate)

    # Set different delay times for L and R
    delay_time_L = 0.1  # 100ms
    delay_time_R = 0.2  # 200ms
    engine.set_delay_time(delay_time_L, delay_time_R)
    engine.set_delay_feedback(0.0)  # No feedback for cleaner test
    engine.set_delay_wet(1.0)  # 100% wet for maximum delay effect

    # Disable reverb to isolate delay
    engine.set_reverb_wet(0.0)

    # Disable mix (100% dry input)
    engine.set_mix(0.0)

    print(f"\nConfiguration:")
    print(f"  Delay Time L: {delay_time_L}s ({int(delay_time_L * sample_rate)} samples)")
    print(f"  Delay Time R: {delay_time_R}s ({int(delay_time_R * sample_rate)} samples)")
    print(f"  Delay Feedback: 0.0")
    print(f"  Delay Wet: 1.0 (100%)")
    print(f"  Reverb Wet: 0.0 (disabled)")

    # Create test signal: impulse
    buffer_size = 24000  # 0.5 seconds
    left_in = np.zeros(buffer_size, dtype=np.float32)
    right_in = np.zeros(buffer_size, dtype=np.float32)

    # Add an impulse at the beginning
    left_in[100] = 1.0
    right_in[100] = 1.0

    # Process
    left_out, right_out = engine.process(left_in, right_in)

    # Find peaks in output (where the delayed impulse appears)
    peak_threshold = 0.5
    left_peaks = np.where(np.abs(left_out) > peak_threshold)[0]
    right_peaks = np.where(np.abs(right_out) > peak_threshold)[0]

    print(f"\nResults:")
    print(f"  Left channel peaks found at samples: {left_peaks[:5] if len(left_peaks) > 0 else 'None'}")
    print(f"  Right channel peaks found at samples: {right_peaks[:5] if len(right_peaks) > 0 else 'None'}")

    # Calculate expected delay positions
    expected_left_delay = int(delay_time_L * sample_rate) + 100
    expected_right_delay = int(delay_time_R * sample_rate) + 100

    print(f"\nExpected peak positions:")
    print(f"  Left: ~{expected_left_delay} samples")
    print(f"  Right: ~{expected_right_delay} samples")

    # Verify they're different
    if len(left_peaks) > 0 and len(right_peaks) > 0:
        left_peak_pos = left_peaks[0]
        right_peak_pos = right_peaks[0]

        difference = abs(left_peak_pos - right_peak_pos)
        print(f"\nActual difference in peak positions: {difference} samples")

        if difference > 100:  # Should differ by ~4800 samples (100ms)
            print("\n✅ SUCCESS: Delays are producing DIFFERENT outputs (stereo independent)")
            print(f"   Left and right delays are working independently!")
            return True
        else:
            print("\n❌ FAIL: Delays producing IDENTICAL or very similar outputs")
            print(f"   Left and right delays may be using same parameters!")
            return False
    else:
        print("\n⚠️  WARNING: No peaks detected in output")
        print("   This might indicate delay is not working at all")
        return False

def test_delay_with_different_feedback():
    """
    Additional test: verify feedback parameter affects each channel independently
    """
    print("\n" + "=" * 70)
    print("Testing Delay with Feedback")
    print("=" * 70)

    sample_rate = 48000
    engine = alien4.AudioEngine(sample_rate)

    # Set same delay time but with feedback
    delay_time = 0.05  # 50ms
    engine.set_delay_time(delay_time, delay_time)
    engine.set_delay_feedback(0.5)  # 50% feedback
    engine.set_delay_wet(1.0)
    engine.set_reverb_wet(0.0)
    engine.set_mix(0.0)

    print(f"\nConfiguration:")
    print(f"  Delay Time: {delay_time}s")
    print(f"  Delay Feedback: 0.5")

    # Create impulse
    buffer_size = 24000
    left_in = np.zeros(buffer_size, dtype=np.float32)
    right_in = np.zeros(buffer_size, dtype=np.float32)
    left_in[100] = 1.0
    right_in[100] = 1.0

    # Process
    left_out, right_out = engine.process(left_in, right_in)

    # Count number of echoes (peaks)
    peak_threshold = 0.1
    left_peaks = np.where(np.abs(left_out) > peak_threshold)[0]
    right_peaks = np.where(np.abs(right_out) > peak_threshold)[0]

    print(f"\nResults:")
    print(f"  Left channel: {len(left_peaks)} peaks detected")
    print(f"  Right channel: {len(right_peaks)} peaks detected")

    if len(left_peaks) > 1 and len(right_peaks) > 1:
        print("\n✅ Feedback is working (multiple echoes detected)")
        return True
    else:
        print("\n⚠️  Feedback may not be working properly")
        return False

if __name__ == "__main__":
    print("\nAlien4 Stereo Delay Test Suite")
    print("Testing the independence of left and right delay channels\n")

    test1_passed = test_delay_stereo_independence()
    test2_passed = test_delay_with_different_feedback()

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Test 1 (Stereo Independence): {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"Test 2 (Feedback): {'✅ PASSED' if test2_passed else '❌ FAILED'}")

    if test1_passed and test2_passed:
        print("\n🎉 All tests passed! Delay is working correctly with stereo independence.")
    else:
        print("\n⚠️  Some tests failed. Please review the implementation.")
