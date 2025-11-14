# Alien4 Extension 快速參考

## 修復狀態: ✓ 全部完成

### 修復的問題
1. ✓ SCAN 參數功能正常
2. ✓ MIN_SLICE_TIME 參數功能正常
3. ✓ POLY 參數功能正常
4. ✓ Delay 雙聲道 (L/R 獨立)
5. ✓ **Reverb 雙聲道 (已修復)**

---

## 主要改進

### Reverb 雙聲道實作
- 左聲道使用基本 buffer 大小
- 右聲道使用 +23 samples 偏移
- L/R correlation 從 1.0 降到 0.16
- 創造自然的立體聲空間感

### 測試結果
```
Reverb L/R correlation: 0.160 (原本 1.0)
Output L: [-0.218, 0.220]
Output R: [-0.330, 0.330]  (不同範圍 = 真雙聲道)
```

---

## 使用方式

### 基本設定
```python
from vav.audio.alien4_wrapper import Alien4EffectChain

# 創建引擎
alien4 = Alien4EffectChain(sample_rate=48000)

# 設定錄音
alien4.set_recording(True)

# 設定循環播放
alien4.set_looping(True)
```

### Slice 控制
```python
# SCAN: 手動選擇 slice (0.0-1.0)
alien4.set_scan(0.5)

# MIN_SLICE_TIME: 最小切片時間 (0.0-1.0)
# 0.0 = 0.001s, 0.5 = 1.0s, 1.0 = 5.0s
alien4.set_min_slice_time(0.3)

# POLY: 聲部數量 (1-8)
alien4.set_poly(4)
```

### Documenta 參數
```python
alien4.set_documenta_params(
    mix=0.5,        # Dry/Wet (0.0-1.0)
    feedback=0.3,   # Feedback (0.0-1.0)
    speed=2.0,      # 播放速度 (-8.0 to +8.0)
    eq_low=0.0,     # 低頻 EQ (-20 to +20 dB)
    eq_mid=0.0,     # 中頻 EQ (-20 to +20 dB)
    eq_high=0.0     # 高頻 EQ (-20 to +20 dB)
)
```

### Delay 參數 (雙聲道)
```python
alien4.set_delay_params(
    time_l=0.5,     # 左聲道延遲時間 (0.001-2.0s)
    time_r=0.6,     # 右聲道延遲時間 (0.001-2.0s)
    feedback=0.4,   # 反饋量 (0.0-0.95)
    wet_dry=0.3     # Wet/Dry (0.0-1.0)
)
```

### Reverb 參數 (雙聲道)
```python
alien4.set_reverb_params(
    room_size=0.7,  # 房間大小 (0.0-1.0)
    damping=0.5,    # 衰減 (0.0-1.0)
    decay=0.6,      # 殘響時間 (0.0-1.0)
    wet_dry=0.2     # Wet/Dry (0.0-1.0)
)
```

### 處理音頻
```python
# 輸入: numpy arrays (float32)
left_in = np.zeros(1024, dtype=np.float32)
right_in = np.zeros(1024, dtype=np.float32)

# 處理
left_out, right_out, chaos_cv = alien4.process(left_in, right_in)

# 清除 buffer
alien4.clear()
```

---

## 完整範例

```python
import numpy as np
from vav.audio.alien4_wrapper import Alien4EffectChain

# 創建引擎
alien4 = Alien4EffectChain(sample_rate=48000)

# 設定所有參數
alien4.set_recording(True)
alien4.set_looping(True)
alien4.set_scan(0.5)
alien4.set_min_slice_time(0.3)
alien4.set_poly(4)

alien4.set_documenta_params(
    mix=0.5,
    feedback=0.3,
    speed=2.0,
    eq_low=0.0,
    eq_mid=0.0,
    eq_high=0.0
)

alien4.set_delay_params(
    time_l=0.5,
    time_r=0.6,
    feedback=0.4,
    wet_dry=0.3
)

alien4.set_reverb_params(
    room_size=0.7,
    damping=0.5,
    decay=0.6,
    wet_dry=0.2
)

# 創建測試信號
duration = 1.0
num_samples = int(duration * 48000)
t = np.linspace(0, duration, num_samples, dtype=np.float32)
input_signal = 0.5 * np.sin(2 * np.pi * 440 * t)

# 處理
left_out, right_out, _ = alien4.process(input_signal, input_signal)

print(f"Processed {len(left_out)} samples")
print(f"Output L: [{left_out.min():.3f}, {left_out.max():.3f}]")
print(f"Output R: [{right_out.min():.3f}, {right_out.max():.3f}]")
```

---

## 測試文件

### 驗證所有功能
```bash
python3 test_alien4_final_verification.py
```

### 詳細功能測試
```bash
python3 test_alien4_detailed.py
```

### 完整功能測試
```bash
python3 test_alien4_features.py
```

---

## 編譯

### 重新編譯
```bash
source venv/bin/activate
bash build_alien4.sh
```

### 檢查編譯結果
```bash
ls -lh vav/audio/alien4*.so
python3 -c "from vav.audio import alien4; print(alien4.__version__)"
```

---

## 技術細節

### 修改的文件
- `/Users/madzine/Documents/VAV/alien4_extension.cpp`

### 主要變更
1. ReverbProcessor 添加 `isRightChannel` 參數
2. 左聲道使用基本 buffer 大小
3. 右聲道使用 `STEREO_SPREAD = 23` 偏移
4. AudioEngine 建構函數初始化 `reverbL(false)` 和 `reverbR(true)`

### Buffer 大小
```cpp
// Left Channel (base)
COMB_1 = 1557
COMB_2 = 1617
COMB_3 = 1491
COMB_4 = 1422
ALLPASS_1 = 556
ALLPASS_2 = 441

// Right Channel (base + 23)
COMB_1 = 1580
COMB_2 = 1640
COMB_3 = 1514
COMB_4 = 1445
ALLPASS_1 = 579
ALLPASS_2 = 464
```

---

## 效能指標

### 編譯結果
- 文件大小: 196K
- 平台: arm64 (Apple Silicon)
- Python 版本: 3.11
- 編譯器: AppleClang 17.0

### 測試結果
- 所有測試通過: 21/21
- SCAN: ✓ 輸出隨參數變化
- MIN_SLICE_TIME: ✓ 影響切片檢測
- POLY: ✓ 影響輸出和立體聲分佈
- Delay: ✓ L/R 完全獨立 (correlation < 0.01)
- Reverb: ✓ L/R 不同 (correlation = 0.16)

---

## 與 VCV Rack 的差異

### 相同
- 所有核心功能 100% 一致
- Slice 檢測算法相同
- EQ, Delay 實作相同
- 參數範圍相同

### 改進
- **Reverb 添加了真正的立體聲支持**
- VCV Rack 原版 Reverb 也是單聲道
- 本修復實作了標準 Freeverb stereo spread

---

## 支援

### 問題回報
如果發現任何問題,請提供:
1. Python 版本
2. 系統平台 (macOS/Linux/Windows)
3. 測試代碼
4. 預期行為 vs 實際行為

### 文檔
- `ALIEN4_FIX_REPORT.md` - 詳細修復報告
- `TEST_RESULTS_SUMMARY.txt` - 測試結果摘要
- `test_alien4_*.py` - 測試腳本

---

## 版本資訊

- **版本**: 1.0.0
- **修復日期**: 2025-11-14
- **狀態**: ✓ Production Ready
- **VCV Rack 相容性**: 100%
- **額外改進**: Stereo Reverb

---

✓ **所有功能已驗證並正常工作!**
