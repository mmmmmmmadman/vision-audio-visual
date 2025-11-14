#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/madzine/Documents/VAV/vav/audio')

import numpy as np
from alien4 import AudioEngine

print("=" * 60)
print("完整 POLY 功能測試")
print("=" * 60)

engine = AudioEngine(48000)
buffer_size = 1024

# 步驟 1: 錄音 (長片段，確保超過預設 MIN)
print("\n步驟 1: 錄音 3 個長片段 (每個 1.5 秒)")
engine.set_recording(True)

for burst in range(3):
    # 靜音 0.5 秒
    silence_buffers = int(0.5 * 48000 / buffer_size)
    for _ in range(silence_buffers):
        silence = np.zeros(buffer_size, dtype=np.float32)
        engine.process(silence, silence)

    # 聲音 1.5 秒
    sound_buffers = int(1.5 * 48000 / buffer_size)
    freq = 200 + burst * 100  # 200, 300, 400 Hz
    for j in range(sound_buffers):
        t = np.arange(buffer_size) / 48000.0 + j * buffer_size / 48000.0
        signal = (0.8 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
        engine.process(signal, signal)

engine.set_recording(False)

print(f"錄音長度: {engine.get_recorded_length()} samples ({engine.get_recorded_length()/48000:.2f} 秒)")
print(f"檢測到 slices: {engine.get_num_slices()}")

if engine.get_num_slices() == 0:
    print("\n錯誤: 沒有檢測到 slice，無法測試 POLY")
    print("請檢查:")
    print("1. 錄音音量是否夠大 (threshold=0.05)")
    print("2. MIN_SLICE_TIME 是否太大")
    sys.exit(1)

# 步驟 2: 測試 POLY=1
print("\n步驟 2: 測試 POLY=1")
engine.set_poly(1)
engine.set_mix(1.0)  # 100% loop
print(f"Voices: {engine.get_num_voices()}")

# 收集輸出
outputs_poly1 = []
input_silence = np.zeros(buffer_size, dtype=np.float32)
for _ in range(10):
    left_out, right_out = engine.process(input_silence, input_silence)
    outputs_poly1.append((left_out.copy(), right_out.copy()))

rms_poly1_l = np.sqrt(np.mean([np.mean(l**2) for l, r in outputs_poly1]))
rms_poly1_r = np.sqrt(np.mean([np.mean(r**2) for l, r in outputs_poly1]))
print(f"POLY=1 RMS: L={rms_poly1_l:.6f}, R={rms_poly1_r:.6f}")

# 步驟 3: 測試 POLY=4
print("\n步驟 3: 測試 POLY=4")
engine.set_poly(4)
print(f"Voices: {engine.get_num_voices()}")

outputs_poly4 = []
for _ in range(10):
    left_out, right_out = engine.process(input_silence, input_silence)
    outputs_poly4.append((left_out.copy(), right_out.copy()))

rms_poly4_l = np.sqrt(np.mean([np.mean(l**2) for l, r in outputs_poly4]))
rms_poly4_r = np.sqrt(np.mean([np.mean(r**2) for l, r in outputs_poly4]))
print(f"POLY=4 RMS: L={rms_poly4_l:.6f}, R={rms_poly4_r:.6f}")

# 步驟 4: 測試 POLY=8
print("\n步驟 4: 測試 POLY=8")
engine.set_poly(8)
print(f"Voices: {engine.get_num_voices()}")

outputs_poly8 = []
for _ in range(10):
    left_out, right_out = engine.process(input_silence, input_silence)
    outputs_poly8.append((left_out.copy(), right_out.copy()))

rms_poly8_l = np.sqrt(np.mean([np.mean(l**2) for l, r in outputs_poly8]))
rms_poly8_r = np.sqrt(np.mean([np.mean(r**2) for l, r in outputs_poly8]))
print(f"POLY=8 RMS: L={rms_poly8_l:.6f}, R={rms_poly8_r:.6f}")

# 分析結果
print("\n" + "=" * 60)
print("結果分析")
print("=" * 60)

# 檢查 1: L/R 差異 (POLY > 1 時應該有差異)
lr_diff_poly1 = abs(rms_poly1_l - rms_poly1_r)
lr_diff_poly4 = abs(rms_poly4_l - rms_poly4_r)
lr_diff_poly8 = abs(rms_poly8_l - rms_poly8_r)

print(f"\nL/R 差異:")
print(f"  POLY=1: {lr_diff_poly1:.6f}")
print(f"  POLY=4: {lr_diff_poly4:.6f}")
print(f"  POLY=8: {lr_diff_poly8:.6f}")

if lr_diff_poly4 > 0.001 or lr_diff_poly8 > 0.001:
    print("  ✓ POLY 模式有產生 stereo 差異")
else:
    print("  ✗ 警告: POLY 模式沒有 stereo 差異")

# 檢查 2: 能量差異 (POLY > 1 時能量應該增加)
total_rms_poly1 = np.sqrt(rms_poly1_l**2 + rms_poly1_r**2)
total_rms_poly4 = np.sqrt(rms_poly4_l**2 + rms_poly4_r**2)
total_rms_poly8 = np.sqrt(rms_poly8_l**2 + rms_poly8_r**2)

print(f"\n總能量:")
print(f"  POLY=1: {total_rms_poly1:.6f}")
print(f"  POLY=4: {total_rms_poly4:.6f}")
print(f"  POLY=8: {total_rms_poly8:.6f}")

if total_rms_poly4 > total_rms_poly1 * 1.2:
    print("  ✓ POLY=4 能量明顯增加")
else:
    print("  ✗ POLY=4 能量沒有明顯增加")

if total_rms_poly8 > total_rms_poly4 * 1.1:
    print("  ✓ POLY=8 能量繼續增加")
else:
    print("  - POLY=8 能量增加不明顯 (可能正常，因為 normalize)")

# 最終判斷
print("\n" + "=" * 60)
if lr_diff_poly4 > 0.001 and total_rms_poly4 > total_rms_poly1:
    print("✓ POLY 功能正常運作")
else:
    print("✗ POLY 功能可能有問題")
print("=" * 60)
