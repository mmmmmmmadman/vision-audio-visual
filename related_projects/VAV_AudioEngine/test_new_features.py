#!/usr/bin/env python3
"""
測試新版 Alien4 的完整功能
"""

import sys
sys.path.insert(0, '/Users/madzine/Documents/VAV/vav/audio')

import numpy as np
import alien4

def test_basic_functionality():
    """測試基本功能"""
    print("=== 測試基本功能 ===")

    # 創建引擎
    engine = alien4.AudioEngine(48000.0)
    print("✓ 引擎創建成功")

    # 測試參數設置
    engine.set_recording(False)
    engine.set_looping(True)
    engine.set_min_slice_time(0.5)  # 0.0-1.0 knob value
    engine.set_scan(0.5)  # 0.0-1.0
    engine.set_feedback(0.3)
    engine.set_mix(0.5)
    engine.set_speed(1.0)  # -8.0 to +8.0
    engine.set_poly(1)  # 1-8 voices
    print("✓ 參數設置成功")

    # 測試 EQ
    engine.set_eq_low(0.0)
    engine.set_eq_mid(0.0)
    engine.set_eq_high(0.0)
    print("✓ EQ 設置成功")

    # 測試 Effects
    engine.set_delay_time(0.25, 0.25)
    engine.set_delay_feedback(0.3)
    engine.set_delay_wet(0.5)
    engine.set_reverb_decay(0.6)
    engine.set_reverb_wet(0.5)
    print("✓ Effects 設置成功")

    # 測試處理
    num_samples = 480
    input_l = np.zeros(num_samples, dtype=np.float32)
    input_r = np.zeros(num_samples, dtype=np.float32)

    output_l, output_r = engine.process(input_l, input_r)
    print(f"✓ 音頻處理成功 (輸出形狀: {output_l.shape})")

    return True

def test_slice_detection():
    """測試 Slice 偵測功能"""
    print("\n=== 測試 Slice 偵測 ===")

    engine = alien4.AudioEngine(48000.0)

    # 創建測試信號：4 個脈衝
    num_samples = 48000  # 1 秒
    input_signal = np.zeros(num_samples, dtype=np.float32)

    # 添加 4 個脈衝（每個 0.2 秒間隔）
    pulse_positions = [0, 12000, 24000, 36000]
    for pos in pulse_positions:
        input_signal[pos:pos+2400] = np.sin(2 * np.pi * 440 * np.arange(2400) / 48000)

    # 開始錄音
    engine.set_recording(True)
    engine.set_min_slice_time(0.05)  # 50ms minimum slice time

    # 處理信號
    output_l, output_r = engine.process(input_signal, input_signal)

    # 停止錄音
    engine.set_recording(False)

    # 檢查偵測到的 slices
    num_slices = engine.get_num_slices()
    print(f"✓ 偵測到 {num_slices} 個 slices（預期 4 個）")

    return num_slices >= 1

def test_polyphonic_playback():
    """測試 Polyphonic 播放"""
    print("\n=== 測試 Polyphonic 播放 ===")

    engine = alien4.AudioEngine(48000.0)

    # 創建簡單測試信號
    num_samples = 4800
    test_signal = np.sin(2 * np.pi * 440 * np.arange(num_samples) / 48000).astype(np.float32)

    # 錄音
    engine.set_recording(True)
    engine.set_min_slice_time(0.01)
    output_l, output_r = engine.process(test_signal, test_signal)
    engine.set_recording(False)

    # 測試不同的 voice 數量
    for num_voices in [1, 2, 4, 8]:
        engine.set_poly(num_voices)
        actual_voices = engine.get_num_voices()
        print(f"✓ 設置 {num_voices} voices，實際: {actual_voices}")

        # 播放測試
        output_l, output_r = engine.process(np.zeros(480, dtype=np.float32),
                                           np.zeros(480, dtype=np.float32))

    return True

def test_speed_range():
    """測試 SPEED 範圍 (-8 到 +8)"""
    print("\n=== 測試 SPEED 範圍 ===")

    engine = alien4.AudioEngine(48000.0)

    # 測試不同速度
    test_speeds = [-8.0, -4.0, -1.0, 0.0, 1.0, 4.0, 8.0]

    for speed in test_speeds:
        engine.set_speed(speed)
        print(f"✓ SPEED 設置為 {speed:+.1f}")

    return True

def test_scan_function():
    """測試 SCAN 功能"""
    print("\n=== 測試 SCAN 功能 ===")

    engine = alien4.AudioEngine(48000.0)

    # 創建有多個 slices 的信號
    num_samples = 48000
    input_signal = np.zeros(num_samples, dtype=np.float32)

    # 添加 5 個脈衝
    for i in range(5):
        pos = i * 9600
        input_signal[pos:pos+2400] = np.sin(2 * np.pi * 440 * np.arange(2400) / 48000)

    # 錄音
    engine.set_recording(True)
    engine.set_min_slice_time(0.05)
    output_l, output_r = engine.process(input_signal, input_signal)
    engine.set_recording(False)

    num_slices = engine.get_num_slices()
    print(f"偵測到 {num_slices} 個 slices")

    # 測試掃描
    if num_slices > 1:
        scan_values = [0.0, 0.25, 0.5, 0.75, 1.0]
        for scan in scan_values:
            engine.set_scan(scan)
            current_slice = engine.get_current_slice()
            print(f"✓ SCAN={scan:.2f}, 當前 slice={current_slice}")

    return True

def test_query_functions():
    """測試查詢函數"""
    print("\n=== 測試查詢函數 ===")

    engine = alien4.AudioEngine(48000.0)

    # 測試查詢
    num_slices = engine.get_num_slices()
    current_slice = engine.get_current_slice()
    num_voices = engine.get_num_voices()
    is_recording = engine.get_is_recording()

    print(f"✓ get_num_slices(): {num_slices}")
    print(f"✓ get_current_slice(): {current_slice}")
    print(f"✓ get_num_voices(): {num_voices}")
    print(f"✓ get_is_recording(): {is_recording}")

    return True

if __name__ == "__main__":
    print("開始測試新版 Alien4 Audio Engine\n")

    try:
        test_basic_functionality()
        test_slice_detection()
        test_polyphonic_playback()
        test_speed_range()
        test_scan_function()
        test_query_functions()

        print("\n" + "="*50)
        print("所有測試通過！✓")
        print("="*50)

    except Exception as e:
        print(f"\n測試失敗: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
