"""
GPU Multiverse Verification Tests
Agent 2: Quality Assurance and Verification

This script contains all 7 test cases to verify GPU renderer matches CPU renderer.
"""

import numpy as np
import sys
import os
sys.path.insert(0, '/Users/madzine/Documents/VAV')

from vav.visual.numba_renderer import NumbaMultiverseRenderer
from vav.visual.qt_opengl_renderer import QtMultiverseRenderer


def compare_images(cpu_result, gpu_result, test_name):
    """Compare two images and return statistics"""
    if cpu_result.shape != gpu_result.shape:
        print(f"❌ {test_name}: Shape mismatch! CPU={cpu_result.shape}, GPU={gpu_result.shape}")
        return False

    diff = np.abs(cpu_result.astype(float) - gpu_result.astype(float))
    max_diff = np.max(diff)
    mean_diff = np.mean(diff)
    std_diff = np.std(diff)

    # Count pixels with difference > 5
    significant_diff = np.sum(diff > 5)
    total_pixels = cpu_result.shape[0] * cpu_result.shape[1] * cpu_result.shape[2]
    percent_diff = (significant_diff / total_pixels) * 100

    print(f"\n{test_name}:")
    print(f"  Max pixel diff: {max_diff:.2f}")
    print(f"  Mean pixel diff: {mean_diff:.2f}")
    print(f"  Std pixel diff: {std_diff:.2f}")
    print(f"  Pixels with diff > 5: {significant_diff} ({percent_diff:.2f}%)")

    # Success criteria: max diff < 5 (accounting for float precision)
    if max_diff < 5.0:
        print(f"  ✅ PASS")
        return True
    else:
        print(f"  ❌ FAIL (max diff {max_diff} >= 5)")
        return False


def test_1_basic_rendering():
    """Test 1: Basic Rendering (No curve, no rotation)"""
    print("\n" + "="*80)
    print("TEST 1: Basic Rendering (No curve, no rotation)")
    print("="*80)

    # Create simple sine wave
    audio = np.sin(np.linspace(0, 10*np.pi, 4800)).astype(np.float32)

    channels_data = [{
        'enabled': True,
        'audio': audio,
        'frequency': 440.0,
        'intensity': 1.0,
        'curve': 0.0,
        'angle': 0.0
    }]

    # Initialize renderers
    cpu_renderer = NumbaMultiverseRenderer(width=1920, height=1080)
    # GPU renderer will be initialized by caller

    # Render
    cpu_result = cpu_renderer.render(channels_data)

    print("\nExpected: Vertical colored stripes")
    print("CPU result shape:", cpu_result.shape)
    print("CPU result range:", cpu_result.min(), "-", cpu_result.max())

    return cpu_result, channels_data


def test_2_curve_effect():
    """Test 2: Curve Effect"""
    print("\n" + "="*80)
    print("TEST 2: Curve Effect")
    print("="*80)

    audio = np.sin(np.linspace(0, 10*np.pi, 4800)).astype(np.float32)

    channels_data = [{
        'enabled': True,
        'audio': audio,
        'frequency': 440.0,
        'intensity': 1.0,
        'curve': 0.5,  # Apply curve
        'angle': 0.0
    }]

    cpu_renderer = NumbaMultiverseRenderer(width=1920, height=1080)
    cpu_result = cpu_renderer.render(channels_data)

    print("\nExpected: Bent stripes (Y-axis dependent bending)")
    print("CPU result shape:", cpu_result.shape)

    return cpu_result, channels_data


def test_3_rotation_effect():
    """Test 3: Rotation Effect"""
    print("\n" + "="*80)
    print("TEST 3: Rotation Effect")
    print("="*80)

    audio = np.sin(np.linspace(0, 10*np.pi, 4800)).astype(np.float32)

    channels_data = [{
        'enabled': True,
        'audio': audio,
        'frequency': 440.0,
        'intensity': 1.0,
        'curve': 0.0,
        'angle': 45.0  # 45 degree rotation
    }]

    cpu_renderer = NumbaMultiverseRenderer(width=1920, height=1080)
    cpu_result = cpu_renderer.render(channels_data)

    print("\nExpected: Rotated stripes, NO black borders")
    print("CPU result shape:", cpu_result.shape)

    return cpu_result, channels_data


def test_4_curve_and_rotation():
    """Test 4: Curve + Rotation (CRITICAL TEST)"""
    print("\n" + "="*80)
    print("TEST 4: Curve + Rotation ⭐ CRITICAL")
    print("="*80)

    audio = np.sin(np.linspace(0, 10*np.pi, 4800)).astype(np.float32)

    channels_data = [{
        'enabled': True,
        'audio': audio,
        'frequency': 440.0,
        'intensity': 1.0,
        'curve': 0.5,   # Apply curve
        'angle': 45.0   # Apply rotation
    }]

    cpu_renderer = NumbaMultiverseRenderer(width=1920, height=1080)
    cpu_result = cpu_renderer.render(channels_data)

    print("\nExpected: Bent THEN rotated (order matters!)")
    print("This tests correct order of operations: curve → rotation")
    print("CPU result shape:", cpu_result.shape)

    return cpu_result, channels_data


def test_5_multi_channel_blending():
    """Test 5: Multi-Channel Blending"""
    print("\n" + "="*80)
    print("TEST 5: Multi-Channel Blending")
    print("="*80)

    # Create 4 channels with different frequencies
    channels_data = []
    for i in range(4):
        audio = np.sin(np.linspace(0, (5+i*2)*np.pi, 4800)).astype(np.float32)
        channels_data.append({
            'enabled': True,
            'audio': audio,
            'frequency': 440.0 * (2 ** (i * 0.25)),  # Different frequencies
            'intensity': 1.0,
            'curve': 0.0,
            'angle': 0.0
        })

    cpu_renderer = NumbaMultiverseRenderer(width=1920, height=1080)
    cpu_renderer.set_blend_mode(0)  # Add mode
    cpu_result = cpu_renderer.render(channels_data)

    print("\nExpected: 4 channels blended with Add mode")
    print("CPU result shape:", cpu_result.shape)

    return cpu_result, channels_data


def test_6_region_map():
    """Test 6: Region Map"""
    print("\n" + "="*80)
    print("TEST 6: Region Map")
    print("="*80)

    # Create region map: divide screen into 4 quadrants
    region_map = np.zeros((1080, 1920), dtype=np.uint8)
    region_map[0:540, 0:960] = 0      # Top-left: channel 0
    region_map[0:540, 960:1920] = 1   # Top-right: channel 1
    region_map[540:1080, 0:960] = 2   # Bottom-left: channel 2
    region_map[540:1080, 960:1920] = 3 # Bottom-right: channel 3

    # Create 4 channels with different frequencies
    channels_data = []
    for i in range(4):
        audio = np.sin(np.linspace(0, (5+i*2)*np.pi, 4800)).astype(np.float32)
        channels_data.append({
            'enabled': True,
            'audio': audio,
            'frequency': 440.0 * (2 ** (i * 0.25)),
            'intensity': 1.0,
            'curve': 0.0,
            'angle': 0.0
        })

    cpu_renderer = NumbaMultiverseRenderer(width=1920, height=1080)
    cpu_renderer.set_blend_mode(0)
    cpu_result = cpu_renderer.render(channels_data, region_map=region_map)

    print("\nExpected: Each channel only in its designated quadrant")
    print("CPU result shape:", cpu_result.shape)

    return cpu_result, channels_data, region_map


def test_7_region_map_with_rotation():
    """Test 7: Region Map + Rotation (CRITICAL TEST)"""
    print("\n" + "="*80)
    print("TEST 7: Region Map + Rotation ⭐ CRITICAL")
    print("="*80)

    # Create region map: vertical split
    region_map = np.zeros((1080, 1920), dtype=np.uint8)
    region_map[:, 0:960] = 0    # Left half: channel 0
    region_map[:, 960:1920] = 1  # Right half: channel 1

    channels_data = []
    for i in range(2):
        audio = np.sin(np.linspace(0, (5+i*3)*np.pi, 4800)).astype(np.float32)
        channels_data.append({
            'enabled': True,
            'audio': audio,
            'frequency': 440.0 * (2 ** (i * 0.5)),
            'intensity': 1.0,
            'curve': 0.0,
            'angle': 30.0  # Apply rotation
        })

    cpu_renderer = NumbaMultiverseRenderer(width=1920, height=1080)
    cpu_renderer.set_blend_mode(0)
    cpu_result = cpu_renderer.render(channels_data, region_map=region_map)

    print("\nExpected: Regions follow rotation (sampled AFTER rotation)")
    print("This tests that region_map is checked at final coordinates")
    print("CPU result shape:", cpu_result.shape)

    return cpu_result, channels_data, region_map


def run_all_tests():
    """Run all 7 verification tests"""
    print("\n" + "="*80)
    print("GPU MULTIVERSE VERIFICATION TEST SUITE")
    print("Agent 2: Quality Assurance")
    print("="*80)

    results = []

    # Test 1
    try:
        cpu_result, channels_data = test_1_basic_rendering()
        results.append(("Test 1: Basic Rendering", True, None))
    except Exception as e:
        print(f"❌ Test 1 FAILED: {e}")
        results.append(("Test 1: Basic Rendering", False, str(e)))

    # Test 2
    try:
        cpu_result, channels_data = test_2_curve_effect()
        results.append(("Test 2: Curve Effect", True, None))
    except Exception as e:
        print(f"❌ Test 2 FAILED: {e}")
        results.append(("Test 2: Curve Effect", False, str(e)))

    # Test 3
    try:
        cpu_result, channels_data = test_3_rotation_effect()
        results.append(("Test 3: Rotation Effect", True, None))
    except Exception as e:
        print(f"❌ Test 3 FAILED: {e}")
        results.append(("Test 3: Rotation Effect", False, str(e)))

    # Test 4 (CRITICAL)
    try:
        cpu_result, channels_data = test_4_curve_and_rotation()
        results.append(("Test 4: Curve + Rotation ⭐", True, None))
    except Exception as e:
        print(f"❌ Test 4 FAILED: {e}")
        results.append(("Test 4: Curve + Rotation ⭐", False, str(e)))

    # Test 5
    try:
        cpu_result, channels_data = test_5_multi_channel_blending()
        results.append(("Test 5: Multi-Channel Blending", True, None))
    except Exception as e:
        print(f"❌ Test 5 FAILED: {e}")
        results.append(("Test 5: Multi-Channel Blending", False, str(e)))

    # Test 6
    try:
        cpu_result, channels_data, region_map = test_6_region_map()
        results.append(("Test 6: Region Map", True, None))
    except Exception as e:
        print(f"❌ Test 6 FAILED: {e}")
        results.append(("Test 6: Region Map", False, str(e)))

    # Test 7 (CRITICAL)
    try:
        cpu_result, channels_data, region_map = test_7_region_map_with_rotation()
        results.append(("Test 7: Region Map + Rotation ⭐", True, None))
    except Exception as e:
        print(f"❌ Test 7 FAILED: {e}")
        results.append(("Test 7: Region Map + Rotation ⭐", False, str(e)))

    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)

    passed = sum(1 for _, success, _ in results if success)
    total = len(results)

    for test_name, success, error in results:
        status = "✅ PASS" if success else f"❌ FAIL ({error})"
        print(f"{test_name}: {status}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✅ ALL TESTS PASSED - Ready for GPU comparison")
    else:
        print(f"\n⚠️  {total - passed} tests failed - CPU renderer setup issues")

    return results


if __name__ == "__main__":
    # Run CPU-only tests first to verify test setup
    print("Running CPU-only tests to verify test suite...")
    run_all_tests()
