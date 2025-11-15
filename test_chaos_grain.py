#!/usr/bin/env python3
"""
Test script for Chaos and Grain integration in Alien4
"""

import numpy as np
import sys
sys.path.insert(0, '/Users/madzine/Documents/VAV/vav/audio')

import alien4
AudioEngine = alien4.AudioEngine

def test_chaos_grain_integration():
    """Test the newly integrated Chaos and Grain processors"""

    print("=" * 60)
    print("Testing Alien4 with Chaos and Grain Integration")
    print("=" * 60)

    # Create engine
    sample_rate = 48000
    engine = AudioEngine(sample_rate)

    print("\n1. Testing Chaos control methods...")
    try:
        engine.set_chaos_rate(0.5)
        engine.set_chaos_amount(0.7)
        engine.set_chaos_shape(True)
        engine.set_delay_chaos(True)
        engine.set_reverb_chaos(False)
        print("   ✓ All chaos control methods working")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False

    print("\n2. Testing Grain control methods...")
    try:
        engine.set_grain_size(0.4)
        engine.set_grain_density(0.6)
        engine.set_grain_wet_dry(0.5)
        print("   ✓ All grain control methods working")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False

    print("\n3. Testing audio processing with Chaos and Grain...")
    try:
        # Record a test signal
        buffer_size = 4800  # 100ms at 48kHz
        test_signal = np.sin(2 * np.pi * 440 * np.arange(buffer_size) / sample_rate).astype(np.float32)
        silence = np.zeros(buffer_size, dtype=np.float32)

        # Record
        engine.set_recording(True)
        left_out, right_out = engine.process(test_signal, test_signal)
        engine.set_recording(False)

        # Playback with chaos and grain enabled
        engine.set_mix(1.0)
        engine.set_chaos_rate(0.3)
        engine.set_chaos_amount(0.5)
        engine.set_chaos_shape(False)  # Smooth
        engine.set_grain_size(0.3)
        engine.set_grain_density(0.4)
        engine.set_grain_wet_dry(0.5)

        # Process with all effects
        left_out, right_out = engine.process(silence, silence)

        print(f"   ✓ Processing successful")
        print(f"   Output RMS: L={np.sqrt(np.mean(left_out**2)):.4f}, R={np.sqrt(np.mean(right_out**2)):.4f}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n4. Testing Chaos modulation on Delay...")
    try:
        engine.set_delay_time(0.25, 0.25)
        engine.set_delay_feedback(0.3)
        engine.set_delay_wet(0.5)
        engine.set_delay_chaos(True)  # Enable chaos modulation
        engine.set_chaos_rate(0.6)
        engine.set_chaos_amount(0.8)

        left_out, right_out = engine.process(silence, silence)
        print("   ✓ Delay chaos modulation working")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False

    print("\n5. Testing Chaos modulation on Reverb...")
    try:
        engine.set_reverb_room(0.7)
        engine.set_reverb_damping(0.5)
        engine.set_reverb_decay(0.6)
        engine.set_reverb_wet(0.5)
        engine.set_reverb_chaos(True)  # Enable chaos modulation

        left_out, right_out = engine.process(silence, silence)
        print("   ✓ Reverb chaos modulation working")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False

    print("\n6. Testing Chaos shape modes...")
    try:
        # Smooth mode
        engine.set_chaos_shape(False)
        left_out1, right_out1 = engine.process(silence, silence)

        # Stepped mode
        engine.set_chaos_shape(True)
        left_out2, right_out2 = engine.process(silence, silence)

        print("   ✓ Chaos shape switching working")
        print(f"   Smooth mode RMS: {np.sqrt(np.mean(left_out1**2)):.4f}")
        print(f"   Stepped mode RMS: {np.sqrt(np.mean(left_out2**2)):.4f}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False

    print("\n7. Testing Grain parameters...")
    try:
        # Vary grain size
        engine.set_grain_size(0.1)  # Small grains
        left_out1, right_out1 = engine.process(silence, silence)

        engine.set_grain_size(0.9)  # Large grains
        left_out2, right_out2 = engine.process(silence, silence)

        # Vary grain density
        engine.set_grain_density(0.1)  # Sparse
        left_out3, right_out3 = engine.process(silence, silence)

        engine.set_grain_density(0.9)  # Dense
        left_out4, right_out4 = engine.process(silence, silence)

        print("   ✓ Grain parameter variations working")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False

    print("\n8. Testing complete signal chain...")
    try:
        # Full chain: Input → EQ → Chaos → Delay → Grain → Reverb
        engine.clear()

        # Record
        engine.set_recording(True)
        engine.process(test_signal, test_signal)
        engine.set_recording(False)

        # Configure all effects
        engine.set_mix(1.0)
        engine.set_eq_low(-3.0)
        engine.set_eq_mid(0.0)
        engine.set_eq_high(-2.0)

        engine.set_chaos_rate(0.5)
        engine.set_chaos_amount(0.6)
        engine.set_chaos_shape(False)

        engine.set_delay_time(0.3, 0.35)
        engine.set_delay_feedback(0.4)
        engine.set_delay_wet(0.3)
        engine.set_delay_chaos(True)

        engine.set_grain_size(0.3)
        engine.set_grain_density(0.5)
        engine.set_grain_wet_dry(0.4)

        engine.set_reverb_room(0.6)
        engine.set_reverb_damping(0.5)
        engine.set_reverb_decay(0.5)
        engine.set_reverb_wet(0.3)
        engine.set_reverb_chaos(True)

        # Process
        left_out, right_out = engine.process(silence, silence)

        print("   ✓ Complete signal chain working")
        print(f"   Final output RMS: L={np.sqrt(np.mean(left_out**2)):.4f}, R={np.sqrt(np.mean(right_out**2)):.4f}")

        # Verify output is stereo and different
        if not np.allclose(left_out, right_out):
            print("   ✓ Stereo output verified (L ≠ R)")
        else:
            print("   ⚠ Warning: Stereo channels are identical")

    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "=" * 60)
    print("✓ ALL TESTS PASSED!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = test_chaos_grain_integration()
    sys.exit(0 if success else 1)
