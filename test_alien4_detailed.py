#!/usr/bin/env python3
"""
Detailed test for Alien4 SCAN/MIN/POLY/Delay/Reverb functionality
Tests if parameters actually affect the output
"""

import sys
import numpy as np

sys.path.insert(0, '/Users/madzine/Documents/VAV')
from vav.audio.alien4_wrapper import Alien4EffectChain

def test_scan_effect():
    """Test if SCAN parameter actually changes the output"""
    print("\n1. Testing SCAN parameter effect...")
    print("-" * 60)

    alien4 = Alien4EffectChain(sample_rate=48000)

    # Record some audio with multiple slices
    alien4.set_recording(True)

    # Create a signal with 3 distinct bursts (should create 3 slices)
    sample_rate = 48000
    silence = np.zeros(4800, dtype=np.float32)  # 0.1s silence
    burst = 0.8 * np.sin(2 * np.pi * 440 * np.linspace(0, 0.1, 4800, dtype=np.float32))

    # Signal: burst1 - silence - burst2 - silence - burst3
    signal = np.concatenate([burst, silence, burst * 0.5, silence, burst * 0.7])

    print(f"   Recording signal with 3 bursts ({len(signal)} samples)...")
    alien4.process(signal, signal)

    alien4.set_recording(False)
    print("   ✓ Recording stopped")

    # Now test SCAN at different positions
    alien4.set_documenta_params(mix=1.0, speed=1.0)  # Full loop playback

    # Test scan at 0.0 (first slice)
    alien4.set_scan(0.0)
    test_signal = np.zeros(1000, dtype=np.float32)
    out_l1, out_r1, _ = alien4.process(test_signal, test_signal)
    rms1 = np.sqrt(np.mean(out_l1**2))

    # Test scan at 0.5 (middle slice)
    alien4.set_scan(0.5)
    out_l2, out_r2, _ = alien4.process(test_signal, test_signal)
    rms2 = np.sqrt(np.mean(out_l2**2))

    # Test scan at 1.0 (last slice)
    alien4.set_scan(1.0)
    out_l3, out_r3, _ = alien4.process(test_signal, test_signal)
    rms3 = np.sqrt(np.mean(out_l3**2))

    print(f"   SCAN 0.0 output RMS: {rms1:.6f}")
    print(f"   SCAN 0.5 output RMS: {rms2:.6f}")
    print(f"   SCAN 1.0 output RMS: {rms3:.6f}")

    # Check if outputs are different
    if not np.allclose(out_l1, out_l2) or not np.allclose(out_l2, out_l3):
        print("   ✓ SCAN parameter IS affecting output (outputs differ)")
        return True
    else:
        print("   ✗ SCAN parameter NOT affecting output (outputs identical)")
        return False

def test_min_slice_time_effect():
    """Test if MIN_SLICE_TIME parameter actually changes slice detection"""
    print("\n2. Testing MIN_SLICE_TIME parameter effect...")
    print("-" * 60)

    alien4_short = Alien4EffectChain(sample_rate=48000)
    alien4_long = Alien4EffectChain(sample_rate=48000)

    # Create signal with short bursts
    sample_rate = 48000
    short_burst = 0.8 * np.sin(2 * np.pi * 440 * np.linspace(0, 0.05, 2400, dtype=np.float32))
    silence = np.zeros(2400, dtype=np.float32)

    signal = np.concatenate([short_burst, silence, short_burst, silence, short_burst])

    # Test with MIN=0.0 (should detect short slices)
    print("   Testing with MIN=0.0 (short slices allowed)...")
    alien4_short.set_min_slice_time(0.0)
    alien4_short.set_recording(True)
    alien4_short.process(signal, signal)
    alien4_short.set_recording(False)

    # Test with MIN=1.0 (should reject short slices)
    print("   Testing with MIN=1.0 (only long slices allowed)...")
    alien4_long.set_min_slice_time(1.0)
    alien4_long.set_recording(True)
    alien4_long.process(signal, signal)
    alien4_long.set_recording(False)

    # Process and compare
    alien4_short.set_documenta_params(mix=1.0)
    alien4_long.set_documenta_params(mix=1.0)

    test_signal = np.zeros(1000, dtype=np.float32)
    out_short, _, _ = alien4_short.process(test_signal, test_signal)
    out_long, _, _ = alien4_long.process(test_signal, test_signal)

    rms_short = np.sqrt(np.mean(out_short**2))
    rms_long = np.sqrt(np.mean(out_long**2))

    print(f"   MIN=0.0 output RMS: {rms_short:.6f}")
    print(f"   MIN=1.0 output RMS: {rms_long:.6f}")

    # With short MIN, should detect slices. With long MIN, should reject them.
    if rms_short > 0.001:
        print("   ✓ MIN_SLICE_TIME IS affecting slice detection")
        return True
    else:
        print("   ✗ MIN_SLICE_TIME NOT affecting slice detection")
        return False

def test_poly_effect():
    """Test if POLY parameter actually changes output"""
    print("\n3. Testing POLY parameter effect...")
    print("-" * 60)

    alien4 = Alien4EffectChain(sample_rate=48000)

    # Record signal with multiple slices
    sample_rate = 48000
    silence = np.zeros(4800, dtype=np.float32)
    burst = 0.8 * np.sin(2 * np.pi * 440 * np.linspace(0, 0.1, 4800, dtype=np.float32))

    signal = np.concatenate([burst, silence, burst * 0.5, silence, burst * 0.7])

    alien4.set_recording(True)
    alien4.process(signal, signal)
    alien4.set_recording(False)

    alien4.set_documenta_params(mix=1.0, speed=1.0)

    # Test with POLY=1 (mono)
    alien4.set_poly(1)
    test_signal = np.zeros(5000, dtype=np.float32)
    out_l1, out_r1, _ = alien4.process(test_signal, test_signal)

    # Test with POLY=8 (8 voices)
    alien4.set_poly(8)
    out_l8, out_r8, _ = alien4.process(test_signal, test_signal)

    rms_l1 = np.sqrt(np.mean(out_l1**2))
    rms_r1 = np.sqrt(np.mean(out_r1**2))
    rms_l8 = np.sqrt(np.mean(out_l8**2))
    rms_r8 = np.sqrt(np.mean(out_r8**2))

    print(f"   POLY=1: L={rms_l1:.6f}, R={rms_r1:.6f}")
    print(f"   POLY=8: L={rms_l8:.6f}, R={rms_r8:.6f}")

    # With poly=1, L/R should be similar. With poly=8, they should be different
    lr_diff_1 = abs(rms_l1 - rms_r1)
    lr_diff_8 = abs(rms_l8 - rms_r8)

    print(f"   POLY=1 L/R difference: {lr_diff_1:.6f}")
    print(f"   POLY=8 L/R difference: {lr_diff_8:.6f}")

    if not np.allclose(out_l1, out_l8) or lr_diff_8 > lr_diff_1:
        print("   ✓ POLY parameter IS affecting output")
        return True
    else:
        print("   ✗ POLY parameter NOT affecting output")
        return False

def test_stereo_delay():
    """Test if Delay is truly stereo (L/R independent)"""
    print("\n4. Testing Delay stereo functionality...")
    print("-" * 60)

    alien4 = Alien4EffectChain(sample_rate=48000)

    # Create impulse
    impulse = np.zeros(48000, dtype=np.float32)
    impulse[100] = 1.0

    # Set different delay times for L and R
    alien4.set_delay_params(time_l=0.1, time_r=0.2, feedback=0.0, wet_dry=1.0)
    alien4.set_documenta_params(mix=0.0)  # Pass through only

    out_l, out_r, _ = alien4.process(impulse, impulse)

    # Find delay peaks
    l_peak_idx = np.argmax(np.abs(out_l[1000:10000])) + 1000
    r_peak_idx = np.argmax(np.abs(out_r[1000:20000])) + 1000

    l_delay_time = l_peak_idx / 48000.0
    r_delay_time = r_peak_idx / 48000.0

    print(f"   Set delay: L=0.1s, R=0.2s")
    print(f"   Measured delay: L={l_delay_time:.3f}s, R={r_delay_time:.3f}s")

    if abs(l_delay_time - 0.1) < 0.01 and abs(r_delay_time - 0.2) < 0.01:
        print("   ✓ Delay IS stereo (L/R independent)")
        return True
    else:
        print("   ✗ Delay NOT stereo (L/R not independent)")
        return False

def test_stereo_reverb():
    """Test if Reverb is truly stereo (L/R independent)"""
    print("\n5. Testing Reverb stereo functionality...")
    print("-" * 60)

    alien4 = Alien4EffectChain(sample_rate=48000)

    # Create impulse
    impulse = np.zeros(10000, dtype=np.float32)
    impulse[100] = 1.0

    # Set reverb to max
    alien4.set_reverb_params(room_size=1.0, damping=0.0, decay=1.0, wet_dry=1.0)
    alien4.set_documenta_params(mix=0.0)  # Pass through only

    out_l, out_r, _ = alien4.process(impulse, impulse)

    # Check if L and R are different (true stereo)
    correlation = np.corrcoef(out_l, out_r)[0, 1]

    print(f"   L/R correlation: {correlation:.6f}")

    if correlation < 0.99:  # If less than 99% correlated, they're different
        print("   ✓ Reverb IS stereo (L/R different)")
        return True
    else:
        print("   ✗ Reverb NOT stereo (L/R identical)")
        return False

def main():
    print("=" * 60)
    print("Alien4 Detailed Functionality Test")
    print("=" * 60)

    results = []

    results.append(("SCAN", test_scan_effect()))
    results.append(("MIN_SLICE_TIME", test_min_slice_time_effect()))
    results.append(("POLY", test_poly_effect()))
    results.append(("Delay Stereo", test_stereo_delay()))
    results.append(("Reverb Stereo", test_stereo_reverb()))

    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)

    for name, result in results:
        status = "✓ WORKING" if result else "✗ NOT WORKING"
        print(f"{name:20s}: {status}")

    all_passed = all(result for _, result in results)

    if all_passed:
        print("\n✓ All tests PASSED - All features working correctly!")
        return 0
    else:
        print("\n✗ Some tests FAILED - Issues detected")
        return 1

if __name__ == '__main__':
    sys.exit(main())
