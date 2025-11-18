#!/usr/bin/env python3
"""
Test Alien4 audio engine Python bindings
"""

import sys
sys.path.insert(0, './build')

import numpy as np
import alien4

print("=== Alien4 Python Bindings Test ===")

# Create engine
engine = alien4.AudioEngine(48000.0)
print("Engine created at 48000 Hz")

# Configure parameters
engine.set_recording(True)
engine.set_looping(True)
engine.set_mix(0.5)
engine.set_feedback(0.3)
engine.set_speed(1.0)

# EQ
engine.set_eq_low(3.0)
engine.set_eq_mid(0.0)
engine.set_eq_high(-3.0)

# Ellen Ripley
engine.set_delay_time(0.25, 0.3)
engine.set_delay_feedback(0.4)
engine.set_reverb_room(0.7)
engine.set_reverb_damping(0.5)
engine.set_reverb_decay(0.6)
engine.set_send_amount(0.3)

print("Parameters configured")

# Generate test signal
buffer_size = 512
input_l = np.sin(2 * np.pi * 440 * np.arange(buffer_size) / 48000).astype(np.float32)
input_r = input_l.copy()

print(f"Processing buffer of {buffer_size} samples...")

# Process
output_l, output_r = engine.process(input_l, input_r)

print(f"Input:  L[0]={input_l[0]:.6f}, R[0]={input_r[0]:.6f}")
print(f"Output: L[0]={output_l[0]:.6f}, R[0]={output_r[0]:.6f}")
print(f"Output shape: L={output_l.shape}, R={output_r.shape}")
print(f"Output dtype: {output_l.dtype}")

# Process multiple buffers
print("\nProcessing 5 buffers...")
for i in range(5):
    output_l, output_r = engine.process(input_l, input_r)
    print(f"Buffer {i}: Output L[0]={output_l[0]:.6f}")

# Clear engine
engine.clear()
print("\nEngine cleared")
print("Test completed successfully!")
