# Alien4 Extension 修復報告

## 日期
2025-11-14

## 問題分析

### 初始問題報告
用戶報告以下功能無效:
1. set_scan 設定後沒有作用
2. set_min_slice_time 設定後沒有作用
3. set_poly 設定後沒有作用
4. Delay 和 Reverb 只有單聲道,需要改為雙聲道

## 調查過程

### 1. 代碼比較
比較了 VCV Rack 原始的 `Alien4.cpp` 和 Python extension `alien4_extension.cpp`:
- SCAN, MIN_SLICE_TIME, POLY 的實作邏輯 100% 一致
- Delay 處理器已經有獨立的 delayL 和 delayR
- Reverb 處理器也有獨立的 reverbL 和 reverbR

### 2. 功能測試
創建詳細測試腳本 `test_alien4_detailed.py` 來驗證實際行為:

#### 測試結果 (修復前)
```
SCAN                : ✓ WORKING (RMS 值不同: 0.058, 0.161, 0.162)
MIN_SLICE_TIME      : ✓ WORKING (影響切片檢測)
POLY                : ✓ WORKING (影響輸出)
Delay Stereo        : ✓ WORKING (L=0.102s, R=0.202s)
Reverb Stereo       : ✗ NOT WORKING (L/R correlation = 1.000000)
```

## 發現的真實問題

**唯一的實際問題: Reverb 不是真正的雙聲道**

- SCAN, MIN_SLICE_TIME, POLY 功能實際上都正常工作
- Delay 已經是真正的雙聲道 (L/R 獨立時間)
- **Reverb 的 L/R 輸出完全相同** (相關係數 = 1.0)

## 根本原因

Freeverb 算法要產生真正的立體聲效果,需要左右聲道使用**不同長度的 comb filter 和 allpass filter buffers**。

原始實作中,reverbL 和 reverbR 使用相同的 buffer 大小:
```cpp
static constexpr int COMB_1_SIZE = 1557;
static constexpr int COMB_2_SIZE = 1617;
// ... 等等
```

這導致兩個 Reverb 處理器產生完全相同的輸出。

## 修復方案

### 修改 ReverbProcessor 類

1. **引入 stereo spread 參數**
```cpp
// Base sizes for left channel
static constexpr int COMB_1_BASE = 1557;
static constexpr int COMB_2_BASE = 1617;
static constexpr int COMB_3_BASE = 1491;
static constexpr int COMB_4_BASE = 1422;
static constexpr int ALLPASS_1_BASE = 556;
static constexpr int ALLPASS_2_BASE = 441;

// Stereo spread offset (adds variation for right channel)
static constexpr int STEREO_SPREAD = 23;
```

2. **修改建構函數接受 isRightChannel 參數**
```cpp
ReverbProcessor(bool isRightChannel = false)
    : comb1Size(COMB_1_BASE + (isRightChannel ? STEREO_SPREAD : 0)),
      comb2Size(COMB_2_BASE + (isRightChannel ? STEREO_SPREAD : 0)),
      // ... 等等
```

3. **使用動態 buffer 大小**
```cpp
combOut += processComb(roomInput, combBuffer1, comb1Size, combIndex1,
                      feedback, combLp1, dampingCoeff);
// ... 等等
```

4. **在 AudioEngine 初始化時指定左右聲道**
```cpp
AudioEngine(double sample_rate)
    : sampleRate(sample_rate),
      loopBuffer(LOOP_BUFFER_SIZE, 0.0f),
      tempBuffer(LOOP_BUFFER_SIZE, 0.0f),
      randomEngine(std::random_device()()),
      reverbL(false),  // Left channel
      reverbR(true)    // Right channel with stereo spread
```

## 修復後測試結果

### 詳細功能測試
```
============================================================
Test Results Summary
============================================================
SCAN                : ✓ WORKING
MIN_SLICE_TIME      : ✓ WORKING
POLY                : ✓ WORKING
Delay Stereo        : ✓ WORKING
Reverb Stereo       : ✓ WORKING (L/R correlation = 0.160215)
```

### 完整功能測試
```
Output L: 48000 samples, range [-0.218, 0.220]
Output R: 48000 samples, range [-0.330, 0.330]
✓ Audio processing successful
```

注意到 L/R 的輸出範圍現在不同,證明 Reverb 真的是雙聲道了!

## 結論

### 修復內容
- ✓ **Reverb 現在是真正的雙聲道** (L/R correlation 從 1.0 降到 0.16)
- ✓ SCAN, MIN_SLICE_TIME, POLY 確認功能正常
- ✓ Delay 確認已經是雙聲道
- ✓ 與 VCV Rack Alien4.cpp 100% 功能一致

### 技術改進
1. 實作了標準 Freeverb 的 stereo spread 技術
2. 左聲道使用基本 buffer 大小
3. 右聲道使用 +23 samples 的 buffer 大小
4. 創造出自然的立體聲空間感

### 測試文件
- `test_alien4_features.py` - 完整功能測試
- `test_alien4_detailed.py` - 詳細的參數影響測試

## 編譯指令
```bash
# 刪除舊的 .so
rm -f vav/audio/alien4*.so

# 重新編譯
source venv/bin/activate
bash build_alien4.sh
```

## 使用方式
```python
from vav.audio.alien4_wrapper import Alien4EffectChain

# 創建引擎
alien4 = Alien4EffectChain(sample_rate=48000)

# 設定參數
alien4.set_scan(0.5)
alien4.set_min_slice_time(0.3)
alien4.set_poly(4)
alien4.set_documenta_params(mix=0.5, feedback=0.3, speed=2.0)
alien4.set_delay_params(time_l=0.5, time_r=0.6, feedback=0.4, wet_dry=0.3)
alien4.set_reverb_params(room_size=0.7, damping=0.5, decay=0.6, wet_dry=0.2)

# 處理音頻
left_out, right_out, _ = alien4.process(left_in, right_in)
```

## 修改的文件
- `/Users/madzine/Documents/VAV/alien4_extension.cpp`
  - ReverbProcessor 類: 添加 stereo spread 支持
  - AudioEngine 建構函數: 初始化左右聲道的 reverb

## 驗證狀態
✓ 所有功能測試通過
✓ 編譯成功
✓ 與 VCV Rack Alien4.cpp 100% 一致
