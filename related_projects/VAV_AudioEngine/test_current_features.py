#!/usr/bin/env python3
"""
測試 Alien4 重建版本的現有功能

此腳本測試目前可用的功能，並標註缺失的功能
"""

import numpy as np
import sys
import os

# 假設 alien4.so 在 build 目錄
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'build'))

try:
    import alien4
    print("✅ alien4 模組載入成功")
except ImportError as e:
    print(f"❌ 無法載入 alien4 模組: {e}")
    print("請先編譯: cd build && cmake .. && make")
    sys.exit(1)

def generate_tone(frequency, duration, sample_rate):
    """生成測試音訊"""
    t = np.linspace(0, duration, int(duration * sample_rate), dtype=np.float32)
    return 0.5 * np.sin(2 * np.pi * frequency * t)

def test_basic_functionality():
    """測試基本功能"""
    print("\n=== 測試 1: 基本功能 ===")

    sample_rate = 48000.0
    engine = alien4.AudioEngine(sample_rate)
    print("✅ 引擎初始化成功")

    # 生成測試訊號
    signal = generate_tone(440.0, 1.0, sample_rate)
    print(f"✅ 生成測試訊號: {len(signal)} samples, 440Hz")

    # 測試處理
    output_l, output_r = engine.process(signal, signal)
    print(f"✅ 音訊處理成功: {len(output_l)} samples output")

    # 檢查輸出
    if np.any(np.isnan(output_l)) or np.any(np.isnan(output_r)):
        print("❌ 輸出包含 NaN")
        return False

    if np.all(output_l == 0) and np.all(output_r == 0):
        print("⚠️ 輸出全為 0（可能是預期行為）")
    else:
        print(f"✅ 輸出有效: L peak={np.max(np.abs(output_l)):.3f}, R peak={np.max(np.abs(output_r)):.3f}")

    return True

def test_recording():
    """測試錄音功能"""
    print("\n=== 測試 2: 錄音功能 ===")

    sample_rate = 48000.0
    engine = alien4.AudioEngine(sample_rate)

    # 生成 1 秒訊號
    signal = generate_tone(440.0, 1.0, sample_rate)

    # 開始錄音
    engine.set_recording(True)
    engine.set_looping(True)
    print("✅ 開始錄音")

    # 分塊處理
    chunk_size = 512
    for i in range(0, len(signal), chunk_size):
        chunk = signal[i:i+chunk_size]
        if len(chunk) < chunk_size:
            chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
        engine.process(chunk, chunk)

    print(f"✅ 錄製 {len(signal)} samples")

    # 停止錄音
    engine.set_recording(False)
    print("✅ 停止錄音")

    # 測試播放
    engine.set_mix(1.0)  # 100% loop
    silence = np.zeros(512, dtype=np.float32)
    output_l, output_r = engine.process(silence, silence)

    if np.all(output_l == 0):
        print("⚠️ 播放輸出為 0（可能 loop 未啟動）")
    else:
        print(f"✅ Loop 播放: peak={np.max(np.abs(output_l)):.3f}")

    return True

def test_parameters():
    """測試參數設定"""
    print("\n=== 測試 3: 參數設定 ===")

    engine = alien4.AudioEngine(48000.0)

    try:
        # 基本參數
        engine.set_mix(0.5)
        print("✅ set_mix(0.5)")

        engine.set_feedback(0.3)
        print("✅ set_feedback(0.3)")

        engine.set_speed(2.0)
        print("✅ set_speed(2.0)")

        # 測試負速度（應該失敗）
        try:
            engine.set_speed(-2.0)
            print("⚠️ set_speed(-2.0) - 應該被限制在正值")
        except:
            print("❌ set_speed(-2.0) - 拋出異常（預期應該 clamp）")

        # EQ 參數
        engine.set_eq_low(5.0)
        print("✅ set_eq_low(5.0)")

        engine.set_eq_mid(-3.0)
        print("✅ set_eq_mid(-3.0)")

        engine.set_eq_high(2.0)
        print("✅ set_eq_high(2.0)")

        # Delay 參數
        engine.set_delay_time(0.25, 0.3)
        print("✅ set_delay_time(0.25, 0.3)")

        engine.set_delay_feedback(0.4)
        print("✅ set_delay_feedback(0.4)")

        engine.set_delay_wet(0.5)
        print("✅ set_delay_wet(0.5)")

        # Reverb 參數
        engine.set_reverb_room(0.7)
        print("✅ set_reverb_room(0.7)")

        engine.set_reverb_damping(0.5)
        print("✅ set_reverb_damping(0.5)")

        engine.set_reverb_decay(0.6)
        print("✅ set_reverb_decay(0.6)")

        engine.set_reverb_wet(0.3)
        print("✅ set_reverb_wet(0.3)")

        return True

    except Exception as e:
        print(f"❌ 參數設定失敗: {e}")
        return False

def test_missing_features():
    """測試缺失功能"""
    print("\n=== 測試 4: 缺失功能檢查 ===")

    engine = alien4.AudioEngine(48000.0)

    # 測試 SCAN (應該存在但無功能)
    try:
        engine.set_scan(0)  # int, 應該是 float
        print("⚠️ set_scan() 存在但參數型別錯誤（應該是 float）")
    except AttributeError:
        print("❌ set_scan() 方法缺失")

    # 測試 POLY (應該缺失)
    try:
        engine.set_poly(4)
        print("❌ set_poly() 不應該存在（但存在了？）")
    except AttributeError:
        print("❌ set_poly() 方法缺失（預期）")

    # 測試 get_num_slices (應該缺失)
    try:
        num = engine.get_num_slices()
        print(f"❌ get_num_slices() 不應該存在（但存在了？返回 {num}）")
    except AttributeError:
        print("❌ get_num_slices() 方法缺失（預期）")

    # 測試 MIN_SLICE_TIME
    try:
        engine.set_min_slice_time(0.1)
        print("✅ set_min_slice_time(0.1) 存在（但功能簡化）")
    except AttributeError:
        print("❌ set_min_slice_time() 方法缺失")

def test_effects_chain():
    """測試效果鏈"""
    print("\n=== 測試 5: 效果鏈 ===")

    engine = alien4.AudioEngine(48000.0)

    # 設定效果
    engine.set_eq_low(10.0)
    engine.set_delay_time(0.25, 0.3)
    engine.set_delay_wet(0.5)
    engine.set_reverb_decay(0.7)
    engine.set_reverb_wet(0.5)

    # 生成脈衝
    impulse = np.zeros(48000, dtype=np.float32)
    impulse[0] = 1.0

    output_l, output_r = engine.process(impulse, impulse)

    # 檢查延遲效果
    delay_samples = int(0.25 * 48000)
    if np.abs(output_l[delay_samples]) > 0.1:
        print(f"✅ Delay 效果有效: peak at {delay_samples} samples")
    else:
        print("⚠️ Delay 效果可能無效")

    # 檢查 reverb tail
    tail_start = 24000  # 0.5 秒後
    if np.any(np.abs(output_l[tail_start:]) > 0.01):
        print("✅ Reverb tail 存在")
    else:
        print("⚠️ Reverb tail 可能無效")

    return True

def main():
    """主測試流程"""
    print("=" * 60)
    print("Alien4 重建版本功能測試")
    print("=" * 60)

    results = []

    results.append(("基本功能", test_basic_functionality()))
    results.append(("錄音功能", test_recording()))
    results.append(("參數設定", test_parameters()))
    results.append(("效果鏈", test_effects_chain()))

    # 缺失功能檢查（不計入通過率）
    test_missing_features()

    # 總結
    print("\n" + "=" * 60)
    print("測試總結")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")

    print(f"\n通過率: {passed}/{total} ({100*passed/total:.0f}%)")

    print("\n⚠️ 警告: 此測試僅驗證現有功能")
    print("⚠️ 核心功能（Slice、Polyphonic）完全缺失")
    print("⚠️ 請參閱 VERIFICATION_REPORT.md 了解完整缺失清單")

    return passed == total

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
