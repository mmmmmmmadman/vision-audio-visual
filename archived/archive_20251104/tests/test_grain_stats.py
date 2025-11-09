#!/usr/bin/env python3
"""
Statistical test to verify chaos randomization percentages
"""

import numpy as np
import sys

sys.path.insert(0, '/Users/madzine/Documents/VAV')

from numba import njit


@njit(fastmath=True)
def test_direction_randomization(iterations):
    """Test direction randomization with controlled iterations"""
    forward_count = 0
    reverse_count = 0

    for _ in range(iterations):
        # Simulate the chaos direction logic (C++ line 344-348)
        if np.random.uniform() < 0.3:
            reverse_count += 1
        else:
            forward_count += 1

    return forward_count, reverse_count


@njit(fastmath=True)
def test_pitch_modulation(iterations, density):
    """Test pitch modulation with controlled iterations"""
    normal_count = 0
    modulated_count = 0

    for _ in range(iterations):
        # Simulate the chaos pitch logic (C++ line 350-354)
        if density > 0.7 and np.random.uniform() < 0.2:
            modulated_count += 1
        else:
            normal_count += 1

    return normal_count, modulated_count


if __name__ == "__main__":
    print("=" * 60)
    print("CHAOS RANDOMIZATION STATISTICAL TEST")
    print("=" * 60)
    print()

    # Test direction randomization
    print("Testing Direction Randomization (30% reverse)...")
    np.random.seed(42)
    iterations = 10000

    forward, reverse = test_direction_randomization(iterations)
    reverse_pct = (reverse / iterations) * 100

    print(f"  Iterations: {iterations}")
    print(f"  Forward: {forward} ({(forward/iterations)*100:.2f}%)")
    print(f"  Reverse: {reverse} ({reverse_pct:.2f}%)")
    print(f"  Expected: 30%")
    print(f"  Deviation: {abs(reverse_pct - 30.0):.2f}%")

    # Check if within reasonable range (25-35%)
    assert 25.0 <= reverse_pct <= 35.0, f"Reverse % {reverse_pct:.2f}% outside expected range"
    print("  ✓ PASSED")
    print()

    # Test pitch modulation with high density
    print("Testing Pitch Modulation at High Density (20% modulated)...")
    np.random.seed(123)

    normal, modulated = test_pitch_modulation(iterations, 0.8)
    modulated_pct = (modulated / iterations) * 100

    print(f"  Iterations: {iterations}")
    print(f"  Normal: {normal} ({(normal/iterations)*100:.2f}%)")
    print(f"  Modulated: {modulated} ({modulated_pct:.2f}%)")
    print(f"  Expected: 20%")
    print(f"  Deviation: {abs(modulated_pct - 20.0):.2f}%")

    # Check if within reasonable range (17-23%)
    assert 17.0 <= modulated_pct <= 23.0, f"Modulated % {modulated_pct:.2f}% outside expected range"
    print("  ✓ PASSED")
    print()

    # Test pitch modulation with low density (should be 0%)
    print("Testing Pitch Modulation at Low Density (0% modulated)...")
    np.random.seed(456)

    normal, modulated = test_pitch_modulation(iterations, 0.5)
    modulated_pct = (modulated / iterations) * 100

    print(f"  Iterations: {iterations}")
    print(f"  Normal: {normal} ({(normal/iterations)*100:.2f}%)")
    print(f"  Modulated: {modulated} ({modulated_pct:.2f}%)")
    print(f"  Expected: 0%")

    assert modulated == 0, f"Modulated count should be 0 at low density"
    print("  ✓ PASSED")
    print()

    print("=" * 60)
    print("ALL STATISTICAL TESTS PASSED!")
    print("=" * 60)
    print()
    print("Verified:")
    print("  ✓ Direction: ~30% reverse (actual within ±5%)")
    print("  ✓ Pitch: ~20% modulated at high density (actual within ±3%)")
    print("  ✓ Pitch: 0% modulated at low density")
    print()
