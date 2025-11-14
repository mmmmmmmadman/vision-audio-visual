#!/usr/bin/env python3
"""
Test SCAN parameter slice jumping functionality
"""
import sys
sys.path.insert(0, '/Users/madzine/Documents/VAV/vav/audio')

import numpy as np
from alien4 import AudioEngine

def test_scan_slice_jumping():
    """Test that SCAN parameter correctly jumps between slices"""
    print("=" * 60)
    print("SCAN Slice Jumping Test")
    print("=" * 60)

    # Create engine
    engine = AudioEngine()
    engine.set_sample_rate(48000)

    # Create input with 3 distinct bursts (slices)
    buffer_size = 1024
    num_bursts = 3
    burst_length = 4800  # 0.1s @ 48kHz
    silence_length = 4800

    print(f"\n1. Recording {num_bursts} bursts...")
    engine.set_rec(True)

    for burst_idx in range(num_bursts):
        # Silence
        silence = np.zeros(silence_length, dtype=np.float32)
        left_out = np.zeros(buffer_size, dtype=np.float32)
        right_out = np.zeros(buffer_size, dtype=np.float32)

        for i in range(0, len(silence), buffer_size):
            chunk = silence[i:i+buffer_size]
            if len(chunk) < buffer_size:
                chunk = np.pad(chunk, (0, buffer_size - len(chunk)))
            engine.process(chunk, chunk, left_out, right_out, buffer_size)

        # Burst with different frequency for each slice
        freq = 200 + burst_idx * 100  # 200, 300, 400 Hz
        t = np.arange(burst_length) / 48000.0
        burst = (0.8 * np.sin(2 * np.pi * freq * t)).astype(np.float32)

        for i in range(0, len(burst), buffer_size):
            chunk = burst[i:i+buffer_size]
            if len(chunk) < buffer_size:
                chunk = np.pad(chunk, (0, buffer_size - len(chunk)))
            engine.process(chunk, chunk, left_out, right_out, buffer_size)

    engine.set_rec(False)
    print("   ✓ Recording stopped")

    # Set MIN_SLICE_TIME low to detect all slices
    engine.set_min_slice_time(0.01)  # 10ms minimum

    # Test SCAN parameter
    print("\n2. Testing SCAN parameter slice jumping...")

    scan_values = [0.0, 0.5, 1.0]
    results = []

    for scan in scan_values:
        engine.set_scan(scan)

        # Process a few buffers to let it settle
        left_in = np.zeros(buffer_size, dtype=np.float32)
        right_in = np.zeros(buffer_size, dtype=np.float32)
        left_out = np.zeros(buffer_size, dtype=np.float32)
        right_out = np.zeros(buffer_size, dtype=np.float32)

        # Collect output
        outputs = []
        for _ in range(20):  # Process 20 buffers
            engine.process(left_in, right_in, left_out, right_out, buffer_size)
            outputs.append(left_out.copy())

        output = np.concatenate(outputs)

        # Analyze frequency content using FFT
        fft = np.fft.rfft(output)
        freqs = np.fft.rfftfreq(len(output), 1/48000.0)
        magnitude = np.abs(fft)

        # Find peak frequency
        peak_idx = np.argmax(magnitude)
        peak_freq = freqs[peak_idx]

        results.append({
            'scan': scan,
            'peak_freq': peak_freq,
            'rms': np.sqrt(np.mean(output**2))
        })

        print(f"   SCAN={scan:.1f}: Peak freq={peak_freq:.0f}Hz, RMS={results[-1]['rms']:.6f}")

    # Verify that different SCAN values produce different outputs
    print("\n3. Verification...")

    # Check if outputs differ
    rmss = [r['rms'] for r in results]
    freqs = [r['peak_freq'] for r in results]

    rms_differ = not all(abs(rmss[0] - r) < 0.01 for r in rmss)
    freq_differ = len(set([int(f/50)*50 for f in freqs])) > 1  # Group freqs by 50Hz

    if rms_differ or freq_differ:
        print("   ✓ SCAN parameter successfully jumps between slices!")
        print("   ✓ Different SCAN values produce different outputs")
        return True
    else:
        print("   ✗ SCAN parameter NOT working - all outputs are the same")
        return False

if __name__ == '__main__':
    success = test_scan_slice_jumping()
    sys.exit(0 if success else 1)
