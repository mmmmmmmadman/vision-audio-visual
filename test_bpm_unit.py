#!/usr/bin/env python3
"""
Unit Tests for BPM Transition - No Audio Dependencies
Tests the BPM transition logic without requiring audio playback
"""

import sys
import os

# Mock the audio libraries
class MockSoundFile:
    @staticmethod
    def read(filepath):
        import numpy as np
        # Return mock audio data
        return np.random.randn(44100), 44100

class MockScipy:
    class signal:
        @staticmethod
        def resample(audio, length):
            import numpy as np
            return np.random.randn(length)

sys.modules['soundfile'] = MockSoundFile
sys.modules['scipy'] = MockScipy
sys.modules['scipy.signal'] = MockScipy.signal

from breakbeat_engine import BreakBeatEngine
import numpy as np


def test_bpm_scheduling():
    """Test 1: BPM changes are scheduled, not applied immediately"""
    print("=" * 60)
    print("Test 1: BPM Scheduling")
    print("=" * 60)

    # Create a minimal engine (will fail to load samples but that's ok)
    try:
        engine = BreakBeatEngine(
            sample_dir=".",  # Won't find samples but that's fine
            bpm=140,
            sample_rate=44100
        )
    except:
        # If it fails, create manually
        engine = BreakBeatEngine.__new__(BreakBeatEngine)
        engine.sample_dir = "."
        engine.bpm = 140
        engine.sample_rate = 44100
        engine.samples = {}
        engine.beat_duration = 60.0 / 140
        engine.step_duration = engine.beat_duration / 4
        engine.samples_per_step = int(engine.step_duration * 44100)
        engine.pattern_length_samples = engine.samples_per_step * 16
        engine.pending_bpm = None
        engine.pending_timing = None
        engine.current_pattern = None
        engine.pattern_position = 0
        engine.bar_count = 0
        engine.pattern_type = 'amen'
        engine.latin_enabled = False
        engine.latin_pattern = None
        engine.all_samples = []
        engine.rest_probability = 0.0
        engine.rest_pattern = []
        engine.fill_amount = 0.0
        engine.last_fill_bar = -99

    initial_bpm = engine.bpm
    initial_samples_per_step = engine.samples_per_step

    print(f"Initial BPM: {initial_bpm}")
    print(f"Initial samples_per_step: {initial_samples_per_step}")

    # Call set_bpm
    new_bpm = 180
    print(f"\n-> Calling set_bpm({new_bpm})")
    engine.set_bpm(new_bpm)

    # Check state
    print(f"\nAfter set_bpm():")
    print(f"  engine.bpm: {engine.bpm}")
    print(f"  engine.pending_bpm: {engine.pending_bpm}")
    print(f"  engine.samples_per_step: {engine.samples_per_step}")

    # Verify BPM not changed immediately
    if engine.bpm == initial_bpm:
        print("✓ BPM not changed immediately")
    else:
        print("✗ BPM changed immediately (should be scheduled)")
        return False

    # Verify pending BPM set
    if engine.pending_bpm == new_bpm:
        print("✓ Pending BPM set correctly")
    else:
        print(f"✗ Pending BPM incorrect: {engine.pending_bpm}")
        return False

    # Verify timing not changed
    if engine.samples_per_step == initial_samples_per_step:
        print("✓ Timing parameters unchanged")
    else:
        print("✗ Timing parameters changed immediately")
        return False

    # Verify pending timing calculated
    if engine.pending_timing is not None:
        expected_samples_per_step = int((60.0 / new_bpm / 4) * 44100)
        actual = engine.pending_timing['samples_per_step']

        if abs(actual - expected_samples_per_step) <= 1:
            print(f"✓ Pending timing calculated correctly ({actual} samples/step)")
        else:
            print(f"✗ Pending timing incorrect: {actual} (expected ~{expected_samples_per_step})")
            return False
    else:
        print("✗ Pending timing not set")
        return False

    return True


def test_bpm_application():
    """Test 2: BPM is applied at pattern boundary"""
    print("\n" + "=" * 60)
    print("Test 2: BPM Application at Pattern Boundary")
    print("=" * 60)

    # Create engine
    engine = BreakBeatEngine.__new__(BreakBeatEngine)
    engine.bpm = 140
    engine.sample_rate = 44100
    engine.beat_duration = 60.0 / 140
    engine.step_duration = engine.beat_duration / 4
    engine.samples_per_step = int(engine.step_duration * 44100)
    engine.pattern_length_samples = engine.samples_per_step * 16

    # Initialize transition state
    engine.pending_bpm = 180
    new_beat_duration = 60.0 / 180
    new_step_duration = new_beat_duration / 4
    engine.pending_timing = {
        'beat_duration': new_beat_duration,
        'step_duration': new_step_duration,
        'samples_per_step': int(new_step_duration * 44100),
        'pattern_length_samples': int(new_step_duration * 44100) * 16
    }

    print(f"Before _apply_pending_bpm():")
    print(f"  engine.bpm: {engine.bpm}")
    print(f"  engine.pending_bpm: {engine.pending_bpm}")
    print(f"  engine.samples_per_step: {engine.samples_per_step}")

    # Call _apply_pending_bpm
    print(f"\n-> Calling _apply_pending_bpm()")
    engine._apply_pending_bpm()

    print(f"\nAfter _apply_pending_bpm():")
    print(f"  engine.bpm: {engine.bpm}")
    print(f"  engine.pending_bpm: {engine.pending_bpm}")
    print(f"  engine.samples_per_step: {engine.samples_per_step}")

    # Verify BPM applied
    if engine.bpm == 180:
        print("✓ BPM applied correctly")
    else:
        print(f"✗ BPM not applied: {engine.bpm}")
        return False

    # Verify pending cleared
    if engine.pending_bpm is None and engine.pending_timing is None:
        print("✓ Pending state cleared")
    else:
        print("✗ Pending state not cleared")
        return False

    # Verify timing updated
    expected_samples_per_step = int((60.0 / 180 / 4) * 44100)
    if abs(engine.samples_per_step - expected_samples_per_step) <= 1:
        print(f"✓ Timing updated correctly ({engine.samples_per_step} samples/step)")
    else:
        print(f"✗ Timing incorrect: {engine.samples_per_step} (expected ~{expected_samples_per_step})")
        return False

    return True


def test_no_change_same_bpm():
    """Test 3: set_bpm with same BPM does nothing"""
    print("\n" + "=" * 60)
    print("Test 3: No Change for Same BPM")
    print("=" * 60)

    engine = BreakBeatEngine.__new__(BreakBeatEngine)
    engine.bpm = 140
    engine.sample_rate = 44100
    engine.pending_bpm = None
    engine.pending_timing = None

    print(f"BPM: {engine.bpm}")
    print(f"-> Calling set_bpm(140)")
    engine.set_bpm(140)

    if engine.pending_bpm is None:
        print("✓ No pending change for same BPM")
        return True
    else:
        print("✗ Pending change created for same BPM")
        return False


def test_multiple_bpm_changes():
    """Test 4: Multiple BPM changes before application"""
    print("\n" + "=" * 60)
    print("Test 4: Multiple BPM Changes")
    print("=" * 60)

    engine = BreakBeatEngine.__new__(BreakBeatEngine)
    engine.bpm = 140
    engine.sample_rate = 44100
    engine.beat_duration = 60.0 / 140
    engine.step_duration = engine.beat_duration / 4
    engine.samples_per_step = int(engine.step_duration * 44100)
    engine.pattern_length_samples = engine.samples_per_step * 16
    engine.pending_bpm = None
    engine.pending_timing = None

    print(f"Initial BPM: {engine.bpm}")

    # First change
    print(f"-> set_bpm(160)")
    engine.set_bpm(160)
    if engine.pending_bpm == 160:
        print("  ✓ First change scheduled")
    else:
        print(f"  ✗ Unexpected pending BPM: {engine.pending_bpm}")
        return False

    # Second change (before first is applied)
    print(f"-> set_bpm(180)")
    engine.set_bpm(180)
    if engine.pending_bpm == 180:
        print("  ✓ Second change overwrites first")
    else:
        print(f"  ✗ Unexpected pending BPM: {engine.pending_bpm}")
        return False

    # Apply
    print(f"-> _apply_pending_bpm()")
    engine._apply_pending_bpm()

    if engine.bpm == 180:
        print("  ✓ Latest BPM change applied")
        return True
    else:
        print(f"  ✗ Wrong BPM applied: {engine.bpm}")
        return False


def test_timing_calculations():
    """Test 5: Verify timing calculations are correct"""
    print("\n" + "=" * 60)
    print("Test 5: Timing Calculations")
    print("=" * 60)

    test_cases = [
        (120, 44100),
        (140, 44100),
        (160, 44100),
        (180, 44100),
        (90, 48000),
        (200, 48000),
    ]

    all_passed = True

    for bpm, sample_rate in test_cases:
        engine = BreakBeatEngine.__new__(BreakBeatEngine)
        engine.bpm = 100  # Different starting BPM
        engine.sample_rate = sample_rate
        engine.beat_duration = 60.0 / 100
        engine.step_duration = engine.beat_duration / 4
        engine.samples_per_step = int(engine.step_duration * sample_rate)
        engine.pending_bpm = None
        engine.pending_timing = None

        engine.set_bpm(bpm)

        # Calculate expected values
        expected_beat_duration = 60.0 / bpm
        expected_step_duration = expected_beat_duration / 4
        expected_samples_per_step = int(expected_step_duration * sample_rate)
        expected_pattern_length = expected_samples_per_step * 16

        # Check pending timing
        if engine.pending_timing is None:
            print(f"✗ BPM {bpm} @ {sample_rate}Hz: No pending timing")
            all_passed = False
            continue

        actual_samples_per_step = engine.pending_timing['samples_per_step']
        actual_pattern_length = engine.pending_timing['pattern_length_samples']

        # Allow ±1 sample tolerance for rounding
        samples_ok = abs(actual_samples_per_step - expected_samples_per_step) <= 1
        length_ok = abs(actual_pattern_length - expected_pattern_length) <= 16

        if samples_ok and length_ok:
            print(f"✓ BPM {bpm:3d} @ {sample_rate}Hz: {actual_samples_per_step:4d} samples/step, {actual_pattern_length:6d} samples/pattern")
        else:
            print(f"✗ BPM {bpm} @ {sample_rate}Hz: Expected {expected_samples_per_step}, got {actual_samples_per_step}")
            all_passed = False

    return all_passed


def main():
    """Run all tests"""
    print("\nBreakBeat Engine - BPM Transition Unit Tests")
    print("=" * 60)
    print()

    results = []

    tests = [
        ("BPM Scheduling", test_bpm_scheduling),
        ("BPM Application", test_bpm_application),
        ("No Change Same BPM", test_no_change_same_bpm),
        ("Multiple BPM Changes", test_multiple_bpm_changes),
        ("Timing Calculations", test_timing_calculations),
    ]

    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"✗ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")

    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠ {total - passed} test(s) failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
