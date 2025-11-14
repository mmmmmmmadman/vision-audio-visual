#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/madzine/Documents/VAV/vav/audio')

import numpy as np
from alien4 import AudioEngine

engine = AudioEngine(48000)

print("=== 初始狀態 ===")
print(f"Slices: {engine.get_num_slices()}")
print(f"Voices: {engine.get_num_voices()}")
print(f"Recorded length: {engine.get_recorded_length()}")

print("\n=== 設定 MIN_SLICE_TIME 最小值 ===")
engine.set_min_slice_time(0.0)  # 0.001 秒

print("\n=== 開始錄音 ===")
engine.set_recording(True)

# 產生 3 個爆發聲音
buffer_size = 1024
for burst in range(3):
    # 靜音
    for _ in range(10):
        silence = np.zeros(buffer_size, dtype=np.float32)
        engine.process(silence, silence)

    # 爆發 (振幅 0.8，應該超過 threshold 0.05)
    for _ in range(20):
        t = np.arange(buffer_size) / 48000.0
        burst_signal = (0.8 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        engine.process(burst_signal, burst_signal)

engine.set_recording(False)

print("\n=== 錄音後狀態 ===")
print(f"Slices: {engine.get_num_slices()}")
print(f"Voices: {engine.get_num_voices()}")
print(f"Recorded length: {engine.get_recorded_length()}")

print("\n=== 設定 POLY=4 ===")
engine.set_poly(4)
print(f"Voices: {engine.get_num_voices()}")

print("\n=== 播放測試 (POLY=1 vs POLY=4) ===")
input_silence = np.zeros(buffer_size, dtype=np.float32)

# POLY=1
engine.set_poly(1)
left_out, right_out = engine.process(input_silence, input_silence)
rms1 = np.sqrt(np.mean(left_out**2 + right_out**2))
print(f"POLY=1 RMS: {rms1:.6f}")

# POLY=4
engine.set_poly(4)
left_out, right_out = engine.process(input_silence, input_silence)
rms4 = np.sqrt(np.mean(left_out**2 + right_out**2))
print(f"POLY=4 RMS: {rms4:.6f}")

if engine.get_num_slices() == 0:
    print("\n警告: 沒有檢測到 slice！可能是 threshold 太高或錄音音量太小")
elif rms1 == rms4:
    print("\n警告: POLY=1 和 POLY=4 輸出相同，POLY 功能可能沒有作用")
else:
    print("\n成功: POLY 功能正常")
