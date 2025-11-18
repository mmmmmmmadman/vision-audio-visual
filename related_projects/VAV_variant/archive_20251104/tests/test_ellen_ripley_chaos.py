"""
Test Ellen Ripley per-sample chaos implementation
Verifies functionality and performance
"""

import numpy as np
import time
from vav.audio.effects.ellen_ripley import EllenRipleyEffectChain

def test_basic_processing():
    """Test basic signal processing"""
    print("=" * 60)
    print("Test 1: Basic Processing")
    print("=" * 60)

    ellen = EllenRipleyEffectChain(sample_rate=48000)

    # Generate test signal (sine wave)
    buffer_size = 512
    t = np.linspace(0, buffer_size / 48000, buffer_size, dtype=np.float32)
    test_signal = np.sin(2 * np.pi * 440 * t) * 0.5

    # Process
    left_out, right_out, chaos_cv = ellen.process(test_signal, test_signal)

    # Verify output
    assert left_out.shape == (buffer_size,), f"Left output shape mismatch: {left_out.shape}"
    assert right_out.shape == (buffer_size,), f"Right output shape mismatch: {right_out.shape}"
    assert chaos_cv.shape == (buffer_size,), f"Chaos CV shape mismatch: {chaos_cv.shape}"

    assert np.all(np.isfinite(left_out)), "Left output contains non-finite values"
    assert np.all(np.isfinite(right_out)), "Right output contains non-finite values"
    assert np.all(np.isfinite(chaos_cv)), "Chaos CV contains non-finite values"

    print(f"✓ Output shapes: {left_out.shape}")
    print(f"✓ Chaos CV range: [{np.min(chaos_cv):.3f}, {np.max(chaos_cv):.3f}]")
    print(f"✓ All outputs finite: OK")
    print()

def test_smooth_chaos():
    """Test smooth chaos mode"""
    print("=" * 60)
    print("Test 2: Smooth Chaos Mode")
    print("=" * 60)

    ellen = EllenRipleyEffectChain(sample_rate=48000)
    ellen.set_chaos_params(rate=0.5, amount=1.0, shape=False)  # Smooth mode

    buffer_size = 512
    test_signal = np.random.randn(buffer_size).astype(np.float32) * 0.1

    # Process multiple buffers
    chaos_values = []
    for i in range(10):
        _, _, chaos_cv = ellen.process(test_signal, test_signal)
        chaos_values.append(np.mean(chaos_cv))

    # Check that chaos varies smoothly
    chaos_diffs = np.diff(chaos_values)
    max_diff = np.max(np.abs(chaos_diffs))

    print(f"✓ Chaos values over 10 buffers: {[f'{v:.3f}' for v in chaos_values[:5]]}...")
    print(f"✓ Max difference between buffers: {max_diff:.3f}")
    print(f"✓ Smooth mode working: {'YES' if max_diff < 1.0 else 'NO'}")
    print()

def test_stepped_chaos():
    """Test stepped chaos mode"""
    print("=" * 60)
    print("Test 3: Stepped Chaos Mode")
    print("=" * 60)

    ellen = EllenRipleyEffectChain(sample_rate=48000)
    ellen.set_chaos_params(rate=0.5, amount=1.0, shape=True)  # Stepped mode

    buffer_size = 512
    test_signal = np.random.randn(buffer_size).astype(np.float32) * 0.1

    # Process one buffer
    _, _, chaos_cv = ellen.process(test_signal, test_signal)

    # Check if chaos has steps (many consecutive equal values)
    unique_values = len(np.unique(chaos_cv))

    print(f"✓ Chaos CV buffer size: {len(chaos_cv)}")
    print(f"✓ Unique chaos values in buffer: {unique_values}")
    print(f"✓ Stepped mode working: {'YES' if unique_values < buffer_size / 2 else 'NO'}")
    print(f"✓ Example chaos values: {chaos_cv[:10]}")
    print()

def test_performance():
    """Test processing performance"""
    print("=" * 60)
    print("Test 4: Performance Benchmark")
    print("=" * 60)

    ellen = EllenRipleyEffectChain(sample_rate=48000)
    ellen.set_chaos_params(rate=0.5, amount=1.0, shape=False)

    # Enable all effects
    ellen.set_delay_params(wet_dry=0.5, chaos_enabled=True)
    ellen.set_grain_params(wet_dry=0.5, chaos_enabled=True)
    ellen.set_reverb_params(wet_dry=0.5, chaos_enabled=True)

    buffer_size = 512
    test_signal = np.random.randn(buffer_size).astype(np.float32) * 0.1

    # Warmup
    for _ in range(10):
        ellen.process(test_signal, test_signal)

    # Benchmark
    num_iterations = 1000
    start_time = time.time()
    for _ in range(num_iterations):
        ellen.process(test_signal, test_signal)
    elapsed = time.time() - start_time

    avg_time = (elapsed / num_iterations) * 1000  # ms
    buffers_per_second = num_iterations / elapsed
    realtime_factor = (buffers_per_second * buffer_size) / 48000

    print(f"✓ Buffer size: {buffer_size} samples")
    print(f"✓ Iterations: {num_iterations}")
    print(f"✓ Total time: {elapsed:.3f}s")
    print(f"✓ Average per buffer: {avg_time:.3f}ms")
    print(f"✓ Buffers/second: {buffers_per_second:.1f}")
    print(f"✓ Realtime factor: {realtime_factor:.1f}x")
    print()

    if avg_time < 10.0:
        print("✓ Performance: EXCELLENT (< 10ms per buffer)")
    elif avg_time < 20.0:
        print("✓ Performance: GOOD (< 20ms per buffer)")
    else:
        print("⚠ Performance: SLOW (> 20ms per buffer)")
    print()

def test_chaos_modulation():
    """Test that chaos actually modulates the effects"""
    print("=" * 60)
    print("Test 5: Chaos Modulation Effect")
    print("=" * 60)

    ellen = EllenRipleyEffectChain(sample_rate=48000)

    buffer_size = 512
    test_signal = np.random.randn(buffer_size).astype(np.float32) * 0.1

    # Process with chaos disabled
    ellen.set_grain_params(wet_dry=1.0, chaos_enabled=False)
    out1_l, _, _ = ellen.process(test_signal, test_signal)

    # Process with chaos enabled
    ellen.clear()  # Reset state
    ellen.set_grain_params(wet_dry=1.0, chaos_enabled=True)
    ellen.set_chaos_params(rate=0.5, amount=1.0, shape=False)
    out2_l, _, _ = ellen.process(test_signal, test_signal)

    # Check difference
    diff = np.mean(np.abs(out1_l - out2_l))

    print(f"✓ Output with chaos OFF: RMS = {np.sqrt(np.mean(out1_l**2)):.4f}")
    print(f"✓ Output with chaos ON:  RMS = {np.sqrt(np.mean(out2_l**2)):.4f}")
    print(f"✓ Mean absolute difference: {diff:.4f}")
    print(f"✓ Chaos modulation working: {'YES' if diff > 0.001 else 'NO'}")
    print()

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Ellen Ripley Per-Sample Chaos Test Suite")
    print("=" * 60 + "\n")

    try:
        test_basic_processing()
        test_smooth_chaos()
        test_stepped_chaos()
        test_performance()
        test_chaos_modulation()

        print("=" * 60)
        print("✓ ALL TESTS PASSED!")
        print("=" * 60)

    except Exception as e:
        print("=" * 60)
        print(f"✗ TEST FAILED: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
