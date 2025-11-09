#!/usr/bin/env python3
"""
Performance test for optimized grain.py
"""

import numpy as np
import sys
import time

sys.path.insert(0, '/Users/madzine/Documents/VAV')

from vav.audio.effects.grain import GrainProcessor


def benchmark_chaos_disabled():
    """Benchmark without chaos"""
    print("Benchmarking: Chaos DISABLED")
    processor = GrainProcessor(sample_rate=48000)
    processor.set_parameters(
        size=0.3,
        density=0.7,
        position=0.5,
        chaos_enabled=False,
        chaos_value=0.0
    )

    # Generate 1 second of audio
    test_signal = np.random.randn(48000).astype(np.float32) * 0.1

    # Warmup (JIT compilation)
    _ = processor.process(test_signal[:1000])

    # Benchmark
    iterations = 10
    start = time.perf_counter()
    for _ in range(iterations):
        output = processor.process(test_signal)
    elapsed = time.perf_counter() - start

    avg_time = elapsed / iterations
    realtime_factor = 1.0 / avg_time  # How many times faster than realtime

    print(f"  Average time: {avg_time*1000:.2f} ms/sec")
    print(f"  Realtime factor: {realtime_factor:.1f}x")
    print(f"  Output range: [{output.min():.4f}, {output.max():.4f}]")
    print()

    return avg_time


def benchmark_chaos_enabled():
    """Benchmark with chaos enabled"""
    print("Benchmarking: Chaos ENABLED")
    processor = GrainProcessor(sample_rate=48000)
    processor.set_parameters(
        size=0.3,
        density=0.8,  # High density for pitch modulation
        position=0.5,
        chaos_enabled=True,
        chaos_value=0.6
    )

    # Generate 1 second of audio
    test_signal = np.random.randn(48000).astype(np.float32) * 0.1

    # Warmup
    _ = processor.process(test_signal[:1000])

    # Benchmark
    iterations = 10
    start = time.perf_counter()
    for _ in range(iterations):
        output = processor.process(test_signal)
    elapsed = time.perf_counter() - start

    avg_time = elapsed / iterations
    realtime_factor = 1.0 / avg_time

    print(f"  Average time: {avg_time*1000:.2f} ms/sec")
    print(f"  Realtime factor: {realtime_factor:.1f}x")
    print(f"  Output range: [{output.min():.4f}, {output.max():.4f}]")
    print()

    return avg_time


def test_chaos_features():
    """Test that chaos features are actually working"""
    print("Verifying chaos features in action...")

    np.random.seed(42)

    processor = GrainProcessor(sample_rate=48000)
    processor.set_parameters(
        size=0.05,  # Small grains
        density=0.95,  # Very high density for more grains
        position=0.5,
        chaos_enabled=True,
        chaos_value=0.5
    )

    # Process enough samples to trigger many grains
    test_signal = np.random.randn(240000).astype(np.float32) * 0.1  # 5 seconds
    output = processor.process(test_signal)

    # Count statistics
    directions = processor.grain_direction
    pitches = processor.grain_pitch

    forward = np.sum(directions == 1.0)
    reverse = np.sum(directions == -1.0)
    normal_pitch = np.sum(pitches == 1.0)
    half_pitch = np.sum(pitches == 0.5)
    double_pitch = np.sum(pitches == 2.0)

    total_dir = forward + reverse
    total_pitch = normal_pitch + half_pitch + double_pitch

    reverse_pct = (reverse / total_dir * 100) if total_dir > 0 else 0
    modulated_pct = ((half_pitch + double_pitch) / total_pitch * 100) if total_pitch > 0 else 0

    print(f"  Direction stats:")
    print(f"    Forward: {forward}, Reverse: {reverse}")
    print(f"    Reverse %: {reverse_pct:.1f}% (expected ~30%)")
    print()
    print(f"  Pitch stats:")
    print(f"    Normal: {normal_pitch}, Half: {half_pitch}, Double: {double_pitch}")
    print(f"    Modulated %: {modulated_pct:.1f}% (expected ~20%)")
    print()


if __name__ == "__main__":
    print("=" * 60)
    print("GRAIN.PY PERFORMANCE & FEATURE TEST")
    print("=" * 60)
    print()

    time_no_chaos = benchmark_chaos_disabled()
    time_with_chaos = benchmark_chaos_enabled()

    overhead = ((time_with_chaos - time_no_chaos) / time_no_chaos) * 100
    print(f"Chaos overhead: {overhead:+.1f}%")
    print()

    test_chaos_features()

    print("=" * 60)
    print("PERFORMANCE TEST COMPLETE")
    print("=" * 60)
    print()
    print("Optimization features:")
    print("  ✓ @njit(fastmath=True, cache=True)")
    print("  ✓ Numba-compatible random generation")
    print("  ✓ Manual clamping (not np.clip)")
    print("  ✓ Efficient boundary handling")
    print()
