# Alien4 Audio Engine - 完整功能文檔

## 概述

Alien4 是從 VCV Rack Alien4 模組完整移植到 Python 的音頻引擎，包含動態 slice 偵測、polyphonic 播放系統、3-band EQ 和完整的 delay/reverb 效果器。

## 核心功能

### 1. 動態 Slice 偵測系統

**來源**: VCV Rack Alien4.cpp lines 351-399

**特性**:
- 自動偵測音頻中的瞬態（transients）
- 基於振幅閾值的 slice 分割
- 支援最小 slice 時間設定（0.001-5.0 秒）
- 實時重掃描功能

**使用方法**:
```python
import alien4

engine = alien4.AudioEngine(48000.0)

# 設置最小 slice 時間（0.0-1.0 knob value）
# 0.0-0.5: 指數映射 0.001-1.0 秒
# 0.5-1.0: 線性映射 1.0-5.0 秒
engine.set_min_slice_time(0.5)  # 約 1.0 秒

# 開始錄音
engine.set_recording(True)
output_l, output_r = engine.process(input_l, input_r)

# 停止錄音（自動偵測 slices）
engine.set_recording(False)

# 查詢偵測到的 slices
num_slices = engine.get_num_slices()
print(f"偵測到 {num_slices} 個 slices")
```

### 2. SCAN 功能（0.0-1.0）

**來源**: VCV Rack Alien4.cpp lines 602-632

**特性**:
- 浮點數掃描所有 slices（0.0 = 第一個，1.0 = 最後一個）
- 自動跳轉到目標 slice
- 支援 CV 調變

**使用方法**:
```python
# 掃描到中間的 slice
engine.set_scan(0.5)

# 掃描到最後一個 slice
engine.set_scan(1.0)

# 取得當前播放的 slice
current = engine.get_current_slice()
```

### 3. Polyphonic 播放系統（1-8 voices）

**來源**: VCV Rack Alien4.cpp lines 692-771

**特性**:
- 支援 1-8 個同時播放的 voices
- 每個 voice 自動分配到不同的 slice
- 每個 voice 有獨立的播放速度乘數（-2.0 到 +2.0）
- Voices 交替輸出到左右聲道
- 自動正規化音量（除以 sqrt(voices_per_channel)）

**使用方法**:
```python
# 設置 polyphonic voices
engine.set_poly(4)  # 1-8 voices

# 查詢當前 voice 數量
num_voices = engine.get_num_voices()
```

**Voice 分配邏輯**:
- Voice 0: 主 voice，跟隨 SCAN 參數
- Voice 1-7: 隨機分配到不同 slices，隨機速度乘數
- L/R 分配: 偶數 voice → 左聲道，奇數 voice → 右聲道

### 4. SPEED 範圍（-8.0 到 +8.0）

**來源**: VCV Rack Alien4.cpp line 296

**特性**:
- 正值: 正向播放，速度 0.25x 到 8x
- 負值: 反向播放
- 0.0: 停止播放
- Polyphonic 模式下，每個 voice 的實際速度 = SPEED × speedMultiplier

**使用方法**:
```python
# 正常速度
engine.set_speed(1.0)

# 雙倍速度
engine.set_speed(2.0)

# 反向播放
engine.set_speed(-1.0)

# 高速反向
engine.set_speed(-8.0)
```

### 5. 重掃描功能（rescanSlices）

**來源**: VCV Rack Alien4.cpp lines 351-399

**特性**:
- 當 MIN_SLICE_TIME 改變時自動重掃描
- 保留原始錄音內容
- 重新計算所有 slice 邊界
- 自動重分配 voices

**觸發條件**:
- MIN_SLICE_TIME 參數改變超過 0.001 秒
- 僅在非錄音狀態下執行

### 6. Voice 重分配（redistributeVoices）

**來源**: VCV Rack Alien4.cpp lines 417-444

**特性**:
- SCAN 值改變時觸發
- Voice 數量改變時觸發
- MIN_SLICE_TIME 改變時觸發
- 隨機分配 voices 到不同 slices
- 安全檢查確保 slice 有效

## 參數範圍

### 錄音與播放
- `set_recording(bool)`: 開始/停止錄音
- `set_looping(bool)`: 啟用/禁用循環
- `set_min_slice_time(0.0-1.0)`: 最小 slice 時間
  - 0.0-0.5: 指數 0.001-1.0 秒
  - 0.5-1.0: 線性 1.0-5.0 秒
- `set_scan(0.0-1.0)`: 掃描 slices
- `set_speed(-8.0 到 +8.0)`: 播放速度
- `set_poly(1-8)`: Polyphonic voices

### 混音
- `set_mix(0.0-1.0)`: Input/Loop 混音（0=input, 1=loop）
- `set_feedback(0.0-0.95)`: 反饋量

### EQ
- `set_eq_low(-20 到 +20)`: 低頻增益（dB）
- `set_eq_mid(-20 到 +20)`: 中頻增益（dB）
- `set_eq_high(-20 到 +20)`: 高頻增益（dB）

### Delay
- `set_delay_time(0.001-2.0, 0.001-2.0)`: L/R delay 時間（秒）
- `set_delay_feedback(0.0-0.95)`: Delay 反饋
- `set_delay_wet(0.0-1.0)`: Wet/Dry 混音

### Reverb
- `set_reverb_room(0.0-1.0)`: 房間大小
- `set_reverb_damping(0.0-1.0)`: 阻尼
- `set_reverb_decay(0.0-1.0)`: 衰減時間
- `set_reverb_wet(0.0-1.0)`: Wet/Dry 混音

## 查詢函數

```python
# 取得偵測到的 slices 數量
num_slices = engine.get_num_slices()

# 取得當前播放的 slice 索引
current_slice = engine.get_current_slice()

# 取得當前 voice 數量
num_voices = engine.get_num_voices()

# 檢查是否正在錄音
is_recording = engine.get_is_recording()
```

## 信號流程

```
Input (Mono)
    ↓
REC/LOOP (動態 slice 偵測)
    ↓
MIX (Input ← → Loop)
    ↓
FDBK (Feedback)
    ↓
3-Band EQ (Low/Mid/High)
    ↓
Delay (L/R with feedback)
    ↓
Reverb (Freeverb algorithm)
    ↓
Output (Stereo)
```

## Polyphonic 播放細節

### Single Voice 模式（POLY=1）
- 簡單的單聲道播放
- 輸出複製到左右聲道

### Multiple Voices 模式（POLY>1）
```
Voice 0 (主 voice):
  - 跟隨 SCAN 參數
  - speedMultiplier = 1.0
  - 輸出到左聲道

Voice 1:
  - 隨機 slice
  - 隨機 speedMultiplier (-2.0 到 +2.0)
  - 輸出到右聲道

Voice 2:
  - 隨機 slice
  - 隨機 speedMultiplier
  - 輸出到左聲道

... 以此類推
```

### 音量正規化
```python
leftVoices = (numVoices + 1) / 2   # 向上取整
rightVoices = numVoices / 2         # 向下取整

loopL /= sqrt(leftVoices)
loopR /= sqrt(rightVoices)
```

## 與 VCV Rack 版本的對應

| VCV Rack Alien4.cpp | Python API | 說明 |
|---------------------|------------|------|
| Lines 45-51 | `Slice` struct | Slice 結構體 |
| Lines 54-59 | `Voice` struct | Voice 結構體 |
| Lines 351-399 | `rescanSlices()` | 重掃描 slices |
| Lines 417-444 | `redistributeVoices()` | 重分配 voices |
| Lines 602-632 | `set_scan()` | SCAN 功能 |
| Lines 692-771 | Polyphonic 播放邏輯 | 多聲部播放 |
| Line 296 | `set_speed(-8, +8)` | 速度範圍 |

## 完整範例

```python
import alien4
import numpy as np

# 初始化
engine = alien4.AudioEngine(48000.0)

# 設置參數
engine.set_min_slice_time(0.3)  # 約 0.1 秒
engine.set_mix(0.8)             # 80% loop
engine.set_speed(1.0)           # 正常速度
engine.set_poly(4)              # 4 voices

# EQ 設置
engine.set_eq_low(3.0)          # +3dB 低頻
engine.set_eq_mid(0.0)
engine.set_eq_high(-2.0)        # -2dB 高頻

# Effects
engine.set_delay_time(0.25, 0.375)
engine.set_delay_feedback(0.4)
engine.set_delay_wet(0.3)
engine.set_reverb_decay(0.7)
engine.set_reverb_wet(0.4)

# 錄音
engine.set_recording(True)
# ... 處理音頻 ...
engine.set_recording(False)

print(f"偵測到 {engine.get_num_slices()} 個 slices")

# SCAN 控制
engine.set_scan(0.5)  # 跳到中間
print(f"當前 slice: {engine.get_current_slice()}")

# 處理音頻
output_l, output_r = engine.process(input_l, input_r)
```

## 技術細節

### Slice 偵測算法
```
1. 設置閾值 threshold = 0.5
2. 掃描錄音緩衝區
3. 偵測振幅從 < threshold 到 >= threshold 的上升沿
4. 檢查 slice 長度 >= minSliceSamples
5. 如果太短，移除該 slice
6. 記錄 slice 的 startSample, endSample, peakAmplitude
```

### MIN_SLICE_TIME 映射
```python
if knobValue <= 0.5:
    # 左半部: 指數 0.001 到 1.0
    t = knobValue * 2.0
    time = 0.001 * pow(1000.0, t)
else:
    # 右半部: 線性 1.0 到 5.0
    t = (knobValue - 0.5) * 2.0
    time = 1.0 + t * 4.0
```

## 注意事項

1. **記憶體使用**: 最大 60 秒錄音（2,880,000 samples @ 48kHz）
2. **Slice 數量**: 無限制，取決於偵測結果
3. **Voice 限制**: 最多 8 個同時播放的 voices
4. **速度限制**: 總速度限制在 -16.0 到 +16.0（包含 speedMultiplier）
5. **輸入格式**: Mono input, Stereo output

## 更新日誌

### 2025-11-14
- 完整移植 VCV Rack Alien4.cpp 功能
- 新增動態 slice 偵測
- 新增 polyphonic 播放（1-8 voices）
- 新增 SCAN 功能（0.0-1.0）
- 擴展 SPEED 範圍（-8 到 +8）
- 實作 rescanSlices() 和 redistributeVoices()
- 保留現有 EQ/Delay/Reverb 功能
