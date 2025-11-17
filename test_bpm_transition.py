#!/usr/bin/env python3
"""
Test BPM Transition Smoothness
Tests that BPM changes don't cause audio glitches or interruptions
"""

import numpy as np
import sounddevice as sd
import time
from breakbeat_engine import BreakBeatEngine


def test_bpm_transition_timing():
    """Test that BPM changes are applied at pattern boundaries"""
    print("=" * 60)
    print("Test 1: BPM Transition Timing")
    print("=" * 60)

    engine = BreakBeatEngine(
        sample_dir="Audio Sample",
        bpm=140,
        sample_rate=44100
    )

    # Initial state
    print(f"Initial BPM: {engine.bpm}")
    print(f"Initial samples_per_step: {engine.samples_per_step}")
    print(f"Initial pattern_length: {engine.pattern_length_samples}")

    # Request BPM change
    print("\n-> Requesting BPM change to 180...")
    engine.set_bpm(180)

    # Check that timing hasn't changed yet
    print(f"Current BPM (should still be 140): {engine.bpm}")
    print(f"Pending BPM: {engine.pending_bpm}")
    print(f"Current samples_per_step: {engine.samples_per_step}")

    if engine.bpm == 140 and engine.pending_bpm == 180:
        print("✓ BPM change scheduled correctly")
    else:
        print("✗ BPM change not scheduled correctly")
        return False

    # Generate audio to trigger pattern boundary
    print("\n-> Generating audio to trigger pattern boundary...")
    chunk1 = engine.get_audio_chunk(1024)

    # Keep generating until pattern boundary
    max_iterations = 100
    iteration = 0
    old_bar_count = engine.bar_count

    while engine.pending_bpm is not None and iteration < max_iterations:
        chunk = engine.get_audio_chunk(1024)
        iteration += 1

        if engine.bar_count > old_bar_count:
            print(f"   Pattern boundary reached after {iteration} chunks")
            break

    # Check that BPM has been applied
    print(f"\nAfter pattern boundary:")
    print(f"Current BPM: {engine.bpm}")
    print(f"Pending BPM: {engine.pending_bpm}")
    print(f"New samples_per_step: {engine.samples_per_step}")

    expected_samples_per_step = int((60.0 / 180 / 4) * 44100)

    if engine.bpm == 180 and engine.pending_bpm is None:
        print("✓ BPM change applied at pattern boundary")
        if abs(engine.samples_per_step - expected_samples_per_step) <= 1:
            print("✓ Timing parameters updated correctly")
            return True
        else:
            print(f"✗ Timing parameters incorrect (expected ~{expected_samples_per_step})")
            return False
    else:
        print("✗ BPM change not applied")
        return False


def test_audio_continuity():
    """Test that audio doesn't have gaps during BPM transition"""
    print("\n" + "=" * 60)
    print("Test 2: Audio Continuity")
    print("=" * 60)

    engine = BreakBeatEngine(
        sample_dir="Audio Sample",
        bpm=140,
        sample_rate=44100
    )

    print("Generating audio chunks with BPM change...")

    # Generate several chunks
    chunks = []
    chunk_size = 1024

    # Generate a few chunks at 140 BPM
    for i in range(5):
        chunk = engine.get_audio_chunk(chunk_size)
        chunks.append(chunk)
        if len(chunk) != chunk_size:
            print(f"✗ Chunk {i} has wrong size: {len(chunk)} (expected {chunk_size})")
            return False

    # Request BPM change
    print(f"-> Changing BPM from 140 to 160 (bar {engine.bar_count})")
    engine.set_bpm(160)

    # Generate more chunks during and after transition
    for i in range(10):
        chunk = engine.get_audio_chunk(chunk_size)
        chunks.append(chunk)

        if len(chunk) != chunk_size:
            print(f"✗ Chunk {5+i} has wrong size: {len(chunk)} (expected {chunk_size})")
            return False

        # Check for complete silence (potential audio dropout)
        if np.all(chunk == 0):
            print(f"✗ Chunk {5+i} is completely silent (potential dropout)")
            return False

        # Check for discontinuities (sudden large changes)
        if i > 0:
            last_sample_prev = chunks[-2][-1]
            first_sample_curr = chunk[0]
            diff = abs(first_sample_curr - last_sample_prev)

            if diff > 0.5:  # Threshold for detecting clicks
                print(f"⚠ Large discontinuity detected at chunk {5+i}: {diff:.3f}")

    print(f"✓ Generated {len(chunks)} chunks without gaps")
    print(f"✓ All chunks have correct size ({chunk_size} samples)")
    print(f"✓ No audio dropouts detected")

    # Check that BPM actually changed
    if engine.bpm == 160:
        print(f"✓ BPM successfully changed to 160")
        return True
    else:
        print(f"✗ BPM is {engine.bpm}, expected 160")
        return False


def test_multiple_bpm_changes():
    """Test multiple rapid BPM changes"""
    print("\n" + "=" * 60)
    print("Test 3: Multiple BPM Changes")
    print("=" * 60)

    engine = BreakBeatEngine(
        sample_dir="Audio Sample",
        bpm=120,
        sample_rate=44100
    )

    bpm_sequence = [120, 140, 160, 180, 150, 130]
    print(f"Testing BPM sequence: {bpm_sequence}")

    for target_bpm in bpm_sequence[1:]:
        print(f"\n-> Changing from {engine.bpm} to {target_bpm} BPM")
        engine.set_bpm(target_bpm)

        # Generate enough audio to trigger transition
        max_chunks = 100
        for i in range(max_chunks):
            chunk = engine.get_audio_chunk(1024)

            if engine.pending_bpm is None:
                # Transition completed
                if engine.bpm == target_bpm:
                    print(f"   ✓ Transitioned to {target_bpm} BPM after {i+1} chunks")
                    break
                else:
                    print(f"   ✗ BPM is {engine.bpm}, expected {target_bpm}")
                    return False
        else:
            print(f"   ✗ Transition to {target_bpm} didn't complete in {max_chunks} chunks")
            return False

    print(f"\n✓ Successfully completed {len(bpm_sequence)-1} BPM transitions")
    return True


def test_live_playback():
    """Test live playback with BPM changes"""
    print("\n" + "=" * 60)
    print("Test 4: Live Playback with BPM Changes")
    print("=" * 60)
    print("\nThis test will play audio for 15 seconds with BPM changes.")
    print("Listen for any clicks, pops, or discontinuities.")
    print("\nBPM schedule:")
    print("  0-3s:  140 BPM")
    print("  3-6s:  180 BPM")
    print("  6-9s:  120 BPM")
    print("  9-12s: 160 BPM")
    print("  12-15s: 140 BPM")

    input("\nPress Enter to start playback...")

    engine = BreakBeatEngine(
        sample_dir="Audio Sample",
        bpm=140,
        sample_rate=44100
    )

    # Audio callback
    start_time = time.time()
    last_bpm_change = 0
    bpm_schedule = [
        (0, 140),
        (3, 180),
        (6, 120),
        (9, 160),
        (12, 140)
    ]
    schedule_index = 0

    def callback(outdata, frames, time_info, status):
        nonlocal schedule_index

        if status:
            print(f"Status: {status}")

        # Check if it's time for BPM change
        elapsed = time.time() - start_time
        if schedule_index < len(bpm_schedule) - 1:
            next_time, next_bpm = bpm_schedule[schedule_index + 1]
            if elapsed >= next_time:
                print(f"\n[{elapsed:.1f}s] Changing to {next_bpm} BPM (pending: {engine.pending_bpm})")
                engine.set_bpm(next_bpm)
                schedule_index += 1

        chunk = engine.get_audio_chunk(frames)
        outdata[:, 0] = chunk

    try:
        with sd.OutputStream(
            channels=1,
            callback=callback,
            samplerate=engine.sample_rate,
            blocksize=1024
        ):
            duration = 15
            for i in range(duration):
                time.sleep(1)
                print(f"[{i+1}s] Bar {engine.bar_count} | BPM: {engine.bpm} | Pending: {engine.pending_bpm}", end='\r')

            print("\n\nPlayback complete.")

    except Exception as e:
        print(f"\n✗ Playback failed: {e}")
        return False

    print("✓ Playback completed without errors")
    return True


def main():
    """Run all tests"""
    print("\nBreakBeat Engine - BPM Transition Tests")
    print("=" * 60)

    results = []

    # Test 1: BPM transition timing
    try:
        results.append(("BPM Transition Timing", test_bpm_transition_timing()))
    except Exception as e:
        print(f"✗ Test failed with exception: {e}")
        results.append(("BPM Transition Timing", False))

    # Test 2: Audio continuity
    try:
        results.append(("Audio Continuity", test_audio_continuity()))
    except Exception as e:
        print(f"✗ Test failed with exception: {e}")
        results.append(("Audio Continuity", False))

    # Test 3: Multiple BPM changes
    try:
        results.append(("Multiple BPM Changes", test_multiple_bpm_changes()))
    except Exception as e:
        print(f"✗ Test failed with exception: {e}")
        results.append(("Multiple BPM Changes", False))

    # Test 4: Live playback (optional)
    try:
        print("\n")
        response = input("Run live playback test? (y/n): ").strip().lower()
        if response == 'y':
            results.append(("Live Playback", test_live_playback()))
    except Exception as e:
        print(f"✗ Test failed with exception: {e}")
        results.append(("Live Playback", False))

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
    else:
        print(f"\n⚠ {total - passed} test(s) failed")


if __name__ == '__main__':
    main()
