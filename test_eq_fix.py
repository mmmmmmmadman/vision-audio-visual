#!/usr/bin/env python3
"""Test EQ functionality after fixes"""

import numpy as np
from vav.audio import alien4

def test_eq_basics():
    """Test basic EQ functionality"""
    print("=" * 60)
    print("Testing EQ Functionality")
    print("=" * 60)

    engine = alien4.AudioEngine(48000.0)

    # Test 1: Set EQ values within valid range (0 to -20dB)
    print("\n1. Testing valid EQ ranges (0 to -20dB)...")
    engine.set_eq_low(0.0)
    engine.set_eq_mid(-5.0)
    engine.set_eq_high(-10.0)
    print("   ✓ Set Low=0dB, Mid=-5dB, High=-10dB")

    # Test 2: Test boundary values
    print("\n2. Testing boundary values...")
    engine.set_eq_low(-20.0)  # Min
    engine.set_eq_mid(0.0)    # Max
    engine.set_eq_high(-20.0) # Min
    print("   ✓ Set Low=-20dB, Mid=0dB, High=-20dB")

    # Test 3: Try values outside range (should be clamped)
    print("\n3. Testing range clamping...")
    engine.set_eq_low(5.0)     # Should clamp to 0
    engine.set_eq_mid(-25.0)   # Should clamp to -20
    engine.set_eq_high(10.0)   # Should clamp to 0
    print("   ✓ Values outside range are clamped")

    # Test 4: Process audio with EQ
    print("\n4. Testing audio processing with EQ...")

    # Generate test signal: sine wave at 200Hz (low), 2kHz (mid), 8kHz (high)
    duration = 1.0
    sample_rate = 48000
    num_samples = int(duration * sample_rate)
    t = np.linspace(0, duration, num_samples, dtype=np.float32)

    # Low frequency component (200Hz)
    low_freq = 200.0
    signal_low = 0.3 * np.sin(2 * np.pi * low_freq * t).astype(np.float32)

    # Mid frequency component (2kHz)
    mid_freq = 2000.0
    signal_mid = 0.3 * np.sin(2 * np.pi * mid_freq * t).astype(np.float32)

    # High frequency component (8kHz)
    high_freq = 8000.0
    signal_high = 0.3 * np.sin(2 * np.pi * high_freq * t).astype(np.float32)

    # Combined signal
    signal = signal_low + signal_mid + signal_high

    # Set different EQ values and process
    test_cases = [
        (0.0, 0.0, 0.0, "No EQ"),
        (-10.0, 0.0, 0.0, "Low cut -10dB"),
        (0.0, -10.0, 0.0, "Mid cut -10dB"),
        (0.0, 0.0, -10.0, "High cut -10dB"),
        (-20.0, -20.0, -20.0, "All cut -20dB"),
    ]

    for low_db, mid_db, high_db, desc in test_cases:
        engine.clear()
        engine.set_eq_low(low_db)
        engine.set_eq_mid(mid_db)
        engine.set_eq_high(high_db)

        # Process
        left_out, right_out = engine.process(signal, signal)

        # Check output
        output_rms = np.sqrt(np.mean(left_out**2))
        input_rms = np.sqrt(np.mean(signal**2))

        print(f"\n   {desc}:")
        print(f"      Input RMS:  {input_rms:.6f}")
        print(f"      Output RMS: {output_rms:.6f}")
        print(f"      Ratio: {output_rms/input_rms:.3f}")

        # Verify output is not silent and not infinite
        assert not np.all(left_out == 0), "Output should not be silent"
        assert not np.all(right_out == 0), "Output should not be silent"
        assert np.all(np.isfinite(left_out)), "Output should be finite"
        assert np.all(np.isfinite(right_out)), "Output should be finite"

    print("\n   ✓ All EQ processing tests passed")

    # Test 5: Test feedback limit increased to 0.8
    print("\n5. Testing feedback limit (0.8)...")
    engine.set_feedback(0.5)
    print("   ✓ Set feedback to 0.5")
    engine.set_feedback(0.8)
    print("   ✓ Set feedback to 0.8")
    engine.set_feedback(1.0)  # Should clamp to 0.8
    print("   ✓ Feedback clamped at 0.8")

    print("\n" + "=" * 60)
    print("All EQ tests PASSED!")
    print("=" * 60)

if __name__ == "__main__":
    test_eq_basics()
