#!/usr/bin/env python3
"""
Test script for optimized audio effects
Tests delay.py and reverb.py Numba optimizations
"""

import numpy as np
import sys
import time

# Add vav to path
sys.path.insert(0, '/Users/madzine/Documents/VAV')

from vav.audio.effects.delay import StereoDelay
from vav.audio.effects.reverb import ReverbProcessor

def test_stereo_delay():
    """Test StereoDelay with Numba optimization"""
    print("Testing StereoDelay...")

    # Create delay processor
    delay = StereoDelay(sample_rate=48000, max_delay=2.0)
    delay.set_delay_time(0.25, 0.3)
    delay.set_feedback(0.4)

    # Generate test signal (1 second of noise)
    duration = 1.0
    sample_rate = 48000
    n_samples = int(duration * sample_rate)

    left_in = np.random.randn(n_samples).astype(np.float32) * 0.1
    right_in = np.random.randn(n_samples).astype(np.float32) * 0.1

    # Process
    start_time = time.time()
    left_out, right_out = delay.process(left_in, right_in)
    elapsed = time.time() - start_time

    # Verify output
    assert left_out.shape == (n_samples,), "Left output shape mismatch"
    assert right_out.shape == (n_samples,), "Right output shape mismatch"
    assert np.isfinite(left_out).all(), "Left output contains NaN or Inf"
    assert np.isfinite(right_out).all(), "Right output contains NaN or Inf"

    print(f"  ✓ Processed {n_samples} samples in {elapsed:.4f}s")
    print(f"  ✓ Throughput: {n_samples/elapsed/1e6:.2f} Msamples/s")
    print(f"  ✓ Output RMS: L={np.sqrt(np.mean(left_out**2)):.6f}, R={np.sqrt(np.mean(right_out**2)):.6f}")

    # Test with reverb feedback
    reverb_feedback_l = np.random.randn(n_samples).astype(np.float32) * 0.05
    reverb_feedback_r = np.random.randn(n_samples).astype(np.float32) * 0.05

    left_out2, right_out2 = delay.process(left_in, right_in, reverb_feedback_l, reverb_feedback_r)
    assert np.isfinite(left_out2).all(), "Left output with reverb feedback contains NaN or Inf"
    assert np.isfinite(right_out2).all(), "Right output with reverb feedback contains NaN or Inf"

    print("  ✓ Reverb feedback test passed")

    return elapsed


def test_reverb_processor():
    """Test ReverbProcessor with Numba optimization"""
    print("\nTesting ReverbProcessor...")

    # Create reverb processor
    reverb = ReverbProcessor(sample_rate=48000)
    reverb.set_parameters(room_size=0.7, damping=0.5, decay=0.6)

    # Generate test signal (1 second of noise)
    duration = 1.0
    sample_rate = 48000
    n_samples = int(duration * sample_rate)

    left_in = np.random.randn(n_samples).astype(np.float32) * 0.1
    right_in = np.random.randn(n_samples).astype(np.float32) * 0.1

    # Warm-up pass (Numba JIT compilation)
    print("  Warming up Numba JIT...")
    _ = reverb.process(left_in[:100], right_in[:100])

    # Process
    start_time = time.time()
    left_out, right_out = reverb.process(left_in, right_in)
    elapsed = time.time() - start_time

    # Verify output
    assert left_out.shape == (n_samples,), "Left output shape mismatch"
    assert right_out.shape == (n_samples,), "Right output shape mismatch"
    assert np.isfinite(left_out).all(), "Left output contains NaN or Inf"
    assert np.isfinite(right_out).all(), "Right output contains NaN or Inf"

    print(f"  ✓ Processed {n_samples} samples in {elapsed:.4f}s")
    print(f"  ✓ Throughput: {n_samples/elapsed/1e6:.2f} Msamples/s")
    print(f"  ✓ Output RMS: L={np.sqrt(np.mean(left_out**2)):.6f}, R={np.sqrt(np.mean(right_out**2)):.6f}")

    # Test with chaos modulation
    left_out2, right_out2 = reverb.process(left_in, right_in, chaos_enabled=True, chaos_value=0.5)
    assert np.isfinite(left_out2).all(), "Left output with chaos contains NaN or Inf"
    assert np.isfinite(right_out2).all(), "Right output with chaos contains NaN or Inf"

    print("  ✓ Chaos modulation test passed")

    return elapsed


def benchmark_performance():
    """Benchmark performance with multiple runs"""
    print("\n" + "="*60)
    print("PERFORMANCE BENCHMARK")
    print("="*60)

    n_runs = 5
    duration = 1.0
    sample_rate = 48000
    n_samples = int(duration * sample_rate)

    # Benchmark Delay
    print("\nDelay Effect:")
    delay = StereoDelay(sample_rate=48000, max_delay=2.0)
    delay.set_delay_time(0.25, 0.3)
    delay.set_feedback(0.4)

    delay_times = []
    for i in range(n_runs):
        left_in = np.random.randn(n_samples).astype(np.float32) * 0.1
        right_in = np.random.randn(n_samples).astype(np.float32) * 0.1

        start = time.time()
        left_out, right_out = delay.process(left_in, right_in)
        elapsed = time.time() - start
        delay_times.append(elapsed)
        print(f"  Run {i+1}: {elapsed:.4f}s ({n_samples/elapsed/1e6:.2f} Msamples/s)")

    avg_delay = np.mean(delay_times)
    print(f"  Average: {avg_delay:.4f}s ({n_samples/avg_delay/1e6:.2f} Msamples/s)")

    # Benchmark Reverb
    print("\nReverb Effect:")
    reverb = ReverbProcessor(sample_rate=48000)
    reverb.set_parameters(room_size=0.7, damping=0.5, decay=0.6)

    # Warm-up
    left_in = np.random.randn(100).astype(np.float32) * 0.1
    right_in = np.random.randn(100).astype(np.float32) * 0.1
    _ = reverb.process(left_in, right_in)

    reverb_times = []
    for i in range(n_runs):
        left_in = np.random.randn(n_samples).astype(np.float32) * 0.1
        right_in = np.random.randn(n_samples).astype(np.float32) * 0.1

        start = time.time()
        left_out, right_out = reverb.process(left_in, right_in)
        elapsed = time.time() - start
        reverb_times.append(elapsed)
        print(f"  Run {i+1}: {elapsed:.4f}s ({n_samples/elapsed/1e6:.2f} Msamples/s)")

    avg_reverb = np.mean(reverb_times)
    print(f"  Average: {avg_reverb:.4f}s ({n_samples/avg_reverb/1e6:.2f} Msamples/s)")

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Delay:  {avg_delay*1000:.2f}ms per second of audio")
    print(f"Reverb: {avg_reverb*1000:.2f}ms per second of audio")
    print(f"Real-time factor (Delay):  {1.0/avg_delay:.1f}x")
    print(f"Real-time factor (Reverb): {1.0/avg_reverb:.1f}x")


if __name__ == "__main__":
    print("="*60)
    print("ELLEN RIPLEY AUDIO EFFECTS - NUMBA OPTIMIZATION TEST")
    print("="*60)

    try:
        # Run tests
        test_stereo_delay()
        test_reverb_processor()

        # Run benchmark
        benchmark_performance()

        print("\n" + "="*60)
        print("ALL TESTS PASSED!")
        print("="*60)

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
