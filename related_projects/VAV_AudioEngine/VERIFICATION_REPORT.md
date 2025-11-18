# Alien4 C++ Extension 功能驗證報告

**驗證日期**: 2025-11-14
**驗證範圍**: VCV Rack 原始版本 vs. 重建 C++ Extension 版本

---

## 執行摘要

**重大發現**: 重建版本 **缺少核心功能**，未能 100% 實作 VCV Rack 版本的功能。

### 缺失的核心系統
1. ❌ **Slice 系統完全缺失**
2. ❌ **Polyphonic Voice 系統完全缺失**
3. ❌ **SCAN 參數功能未實作**
4. ❌ **MIN_SLICE_TIME 參數功能未實作**
5. ❌ **POLY 參數功能未實作**

### 實作完成度: ~40%

---

## 詳細驗證結果

## 1. Slice 系統 ❌ **完全缺失**

### VCV Rack 原始版本 (Alien4.cpp)

```cpp
// 第 46-51 行: Slice 結構體定義
struct Slice {
    int startSample = 0;
    int endSample = 0;
    float peakAmplitude = 0.0f;
    bool active = false;
};

// 第 351-399 行: rescanSlices() 方法
void rescanSlices(float threshold, float minSliceTime, float sampleRate) {
    if (recordedLength <= 0) return;

    slices.clear();
    int minSliceSamples = (int)(minSliceTime * sampleRate);
    float lastAmp = 0.0f;

    // 動態偵測 threshold crossing (threshold = 0.5)
    for (int pos = 0; pos < recordedLength; pos++) {
        float currentAmp = std::abs(loopBuffer[pos]);

        if (lastAmp < threshold && currentAmp >= threshold) {
            // 偵測到 onset，創建新 slice
            // 檢查 MIN_SLICE_TIME 限制
            if (!slices.empty() && slices.back().active) {
                int sliceLength = pos - slices.back().startSample;
                if (sliceLength >= minSliceSamples) {
                    slices.back().endSample = pos - 1;
                } else {
                    slices.pop_back();  // 移除過短的 slice
                }
            }

            // 創建新 slice
            Slice newSlice;
            newSlice.startSample = pos;
            newSlice.active = true;
            newSlice.peakAmplitude = 0.0f;
            slices.push_back(newSlice);
        }

        // 追蹤 peak amplitude
        if (!slices.empty() && slices.back().active) {
            slices.back().peakAmplitude = std::max(
                slices.back().peakAmplitude, currentAmp
            );
        }

        lastAmp = currentAmp;
    }
}
```

**核心功能**:
- ✅ 動態 onset detection (threshold = 0.5)
- ✅ MIN_SLICE_TIME 過濾（0.001-5.0 秒）
- ✅ Peak amplitude 追蹤
- ✅ 即時錄音中的 slice 偵測（第 510-547 行）
- ✅ 停止錄音時的 slice finalization（第 458-470 行）

### 重建版本 (alien4_engine.hpp)

```cpp
// ❌ 完全沒有 Slice 結構體
// ❌ 完全沒有 rescanSlices() 方法
// ❌ 只有簡單的 AudioLayer，沒有 slice 功能
```

**缺失影響**:
- 無法進行音訊內容的自動分段
- 無法使用 SCAN 參數選擇不同 slice
- 無法根據 MIN_SLICE_TIME 動態調整分段粒度

---

## 2. Polyphonic Voice 系統 ❌ **完全缺失**

### VCV Rack 原始版本

```cpp
// 第 54-59 行: Voice 結構體定義
struct Voice {
    int sliceIndex = 0;
    int playbackPosition = 0;
    float playbackPhase = 0.0f;
    float speedMultiplier = 1.0f;  // -2.0 到 +2.0 的隨機速度
};

// 第 262-263 行: 變數定義
std::vector<Voice> voices;
int numVoices = 1;

// 第 417-444 行: redistributeVoices() 方法
void redistributeVoices() {
    if (slices.empty() || numVoices <= 1 || voices.empty()) return;

    std::uniform_int_distribution<int> sliceDist(0, slices.size() - 1);
    std::uniform_real_distribution<float> speedDist(-2.0f, 2.0f);

    for (int i = 1; i < numVoices; i++) {
        // 隨機選擇 slice
        int targetSliceIndex = sliceDist(randomEngine);

        // 確保選擇有效的 active slice
        int attempts = 0;
        while (attempts < 20 &&
               (!slices[targetSliceIndex].active ||
                slices[targetSliceIndex].startSample >= recordedLength)) {
            targetSliceIndex = sliceDist(randomEngine);
            attempts++;
        }

        voices[i].sliceIndex = targetSliceIndex;
        voices[i].playbackPosition = slices[targetSliceIndex].startSample;
        voices[i].playbackPhase = 0.0f;
        voices[i].speedMultiplier = speedDist(randomEngine);  // ⭐ 關鍵特徵
    }
}

// 第 692-771 行: Polyphonic 播放邏輯
// Multiple voices mode
for (int i = 0; i < numVoices; i++) {
    float voiceSpeed = playbackSpeed * voices[i].speedMultiplier;
    voiceSpeed = clamp(voiceSpeed, -16.0f, 16.0f);

    // 每個 voice 獨立播放不同 slice
    // ...

    // L/R 聲道交替分配
    if (i % 2 == 0) {
        loopL += sample;
    } else {
        loopR += sample;
    }
}

// 正規化（每個聲道的 voice 數量不同時）
int leftVoices = (numVoices + 1) / 2;
int rightVoices = numVoices / 2;
if (leftVoices > 0) loopL /= std::sqrt((float)leftVoices);
if (rightVoices > 0) loopR /= std::sqrt((float)rightVoices);
```

**核心功能**:
- ✅ 1-8 個獨立 voice（第 550-599 行）
- ✅ 每個 voice 隨機分配不同 slice
- ✅ 每個 voice 隨機 speed multiplier (-2.0 到 +2.0)
- ✅ L/R 聲道交替輸出（奇偶分配）
- ✅ 根據每聲道 voice 數量自動正規化（sqrt）
- ✅ SCAN 變化時自動 redistribute（第 605-608 行）

### 重建版本

```cpp
// ❌ 完全沒有 Voice 結構體
// ❌ 完全沒有 redistributeVoices() 方法
// ❌ 只有 4 個 AudioLayer，但沒有 polyphonic voice 邏輯
// ❌ 沒有隨機 speed multiplier
// ❌ 沒有 L/R 交替輸出
```

**缺失影響**:
- 無法產生 polyphonic 質感
- 無法產生隨機速度變化的複雜音色
- 無法利用立體聲場創造空間感

---

## 3. 參數範圍驗證

### ✅ SCAN 參數

**VCV Rack 版本**:
```cpp
// 第 288 行
configParam(SCAN_PARAM, 0.0f, 1.0f, 0.0f, "Slice Scan", "%", 0.f, 100.f);

// 第 602-632 行: SCAN 功能實作
float scanValue = params[SCAN_PARAM].getValue();

// 檢測 SCAN 值變化時 redistribute voices
if (std::abs(scanValue - lastScanValue) > 0.001f) {
    redistributeVoices();  // ⭐ 關鍵功能
    lastScanValue = scanValue;
}

// 將 0.0-1.0 映射到 slice index
if (slices.size() > 1 && scanValue > 0.01f) {
    int targetSliceIndex = (int)std::round(scanValue * (slices.size() - 1));
    targetSliceIndex = clamp(targetSliceIndex, 0, (int)slices.size() - 1);

    if (targetSliceIndex != lastScanTargetIndex && slices[targetSliceIndex].active) {
        currentSliceIndex = targetSliceIndex;
        playbackPosition = slices[targetSliceIndex].startSample;
        playbackPhase = 0.0f;

        // 更新 voice 0
        if (numVoices > 1 && !voices.empty()) {
            voices[0].sliceIndex = targetSliceIndex;
            voices[0].playbackPosition = slices[targetSliceIndex].startSample;
            voices[0].playbackPhase = 0.0f;
        }
    }
}
```

**重建版本**:
```cpp
// ❌ 沒有 set_scan(float) 方法
// ❌ Python binding 有 set_scan(int)，但實作錯誤（應該是 float）
// ❌ 實作只是設定 scanIndex，沒有任何功能邏輯
void setScan(int index) {
    scanIndex = std::max(0, std::min(MAX_LAYERS - 1, index));
}
```

**結論**: ❌ **SCAN 參數完全無功能**

---

### ✅ MIN_SLICE_TIME 參數

**VCV Rack 版本**:
```cpp
// 第 62-87 行: 自訂 ParamQuantity（指數+線性曲線）
struct MinSliceTimeParamQuantity : ParamQuantity {
    float getDisplayValue() override {
        float knobValue = getValue();  // 0.0-1.0
        if (knobValue <= 0.5f) {
            // 左半: 0.001 到 1.0 秒（指數）
            float t = knobValue * 2.0f;
            return 0.001f * std::pow(1000.0f, t);
        } else {
            // 右半: 1.0 到 5.0 秒（線性）
            float t = (knobValue - 0.5f) * 2.0f;
            return 1.0f + t * 4.0f;
        }
    }
};

// 第 290 行: 使用自訂 ParamQuantity
configParam<MinSliceTimeParamQuantity>(MIN_SLICE_TIME_PARAM,
    0.0f, 1.0f, 0.5f, "Min Slice Time", " s");

// 第 404-415 行: getMinSliceTime() 方法
float getMinSliceTime() {
    float knobValue = params[MIN_SLICE_TIME_PARAM].getValue();
    if (knobValue <= 0.5f) {
        float t = knobValue * 2.0f;
        return 0.001f * std::pow(1000.0f, t);
    } else {
        float t = (knobValue - 0.5f) * 2.0f;
        return 1.0f + t * 4.0f;
    }
}

// 第 501-508 行: MIN_SLICE_TIME 變化時自動 rescan
float minSliceTime = getMinSliceTime();
if (!isRecording && recordedLength > 0 &&
    std::abs(minSliceTime - lastMinSliceTime) > 0.001f) {
    rescanSlices(threshold, minSliceTime, args.sampleRate);
    redistributeVoices();  // ⭐ 自動重新分配 voices
    lastMinSliceTime = minSliceTime;
}
```

**重建版本**:
```cpp
// ❌ 只有簡單的線性 clamp
void setMinSliceTime(float time) {
    minSliceTime = std::max(0.01f, time);
}
// ❌ 沒有指數曲線
// ❌ 沒有自動 rescan 功能
```

**結論**: ❌ **MIN_SLICE_TIME 缺少核心功能（指數曲線、自動 rescan）**

---

### ✅ SPEED 參數

**VCV Rack 版本**: -8.0 到 +8.0
**重建版本**: 0.25 到 4.0

**結論**: ❌ **範圍不一致，缺少反向播放（負值）**

---

### ✅ POLY 參數

**VCV Rack 版本**:
```cpp
// 第 297-298 行
configParam(POLY_PARAM, 1.0f, 8.0f, 1.0f, "Polyphonic Voices");
paramQuantities[POLY_PARAM]->snapEnabled = true;  // 整數捕捉

// 第 549-599 行: 動態 voice 管理
int newNumVoices = (int)params[POLY_PARAM].getValue();
newNumVoices = clamp(newNumVoices, 1, 8);

if (newNumVoices != numVoices) {
    numVoices = newNumVoices;
    voices.resize(numVoices);

    // 為每個 voice 初始化
    for (int i = 0; i < numVoices; i++) {
        if (i == 0) {
            voices[i].sliceIndex = currentSliceIndex;
            voices[i].playbackPosition = playbackPosition;
            voices[i].playbackPhase = playbackPhase;
            voices[i].speedMultiplier = 1.0f;
        } else {
            // 隨機分配 slice 和 speed
            int targetSliceIndex = sliceDist(randomEngine);
            voices[i].sliceIndex = targetSliceIndex;
            voices[i].playbackPosition = slices[targetSliceIndex].startSample;
            voices[i].playbackPhase = 0.0f;
            voices[i].speedMultiplier = speedDist(randomEngine);
        }
    }
}
```

**重建版本**:
```cpp
// ❌ 完全沒有 POLY 參數
// ❌ 沒有 set_poly() 方法
```

**結論**: ❌ **POLY 參數完全缺失**

---

## 4. 音訊處理流程驗證

### VCV Rack 版本信號鏈

```
Input → REC (with Slice Detection) → SCAN → Polyphonic Playback → MIX → FDBK → EQ → Delay → Reverb → Output
         |                                                           ↑
         └─────────────── Loop Buffer with Slices ──────────────────┘
```

**關鍵特徵**:
1. ✅ 錄音時即時 slice 偵測（第 510-547 行）
2. ✅ 停止錄音時 finalize slices（第 458-470 行）
3. ✅ SCAN 控制 slice 選擇
4. ✅ Polyphonic voices 同時播放多個 slices
5. ✅ MIX 混合輸入和 loop
6. ✅ FDBK 從效果鏈末端回授（第 774-785 行）
7. ✅ EQ → Delay → Reverb 串聯
8. ✅ Feedback 使用 tanh 軟限制（第 781-782 行）

### 重建版本信號鏈

```
Input → REC → Simple Playback → MIX → FDBK → EQ → Delay → Reverb → Output
         |                        ↑
         └── Simple AudioLayer ───┘
```

**缺失功能**:
1. ❌ 沒有 slice 偵測
2. ❌ 沒有 SCAN 功能
3. ❌ 沒有 polyphonic voices
4. ✅ MIX 功能正確
5. ⚠️ FDBK 實作簡化（沒有 tanh）
6. ✅ EQ → Delay → Reverb 正確
7. ❌ Feedback 缺少軟限制

---

## 5. Python Binding 驗證

### 缺失的方法

```python
# ❌ 以下方法在重建版本中缺失或功能不完整：

# Slice 系統
engine.get_num_slices()          # 缺失
engine.get_slice_info(index)     # 缺失
engine.rescan_slices()           # 缺失

# SCAN 參數
engine.set_scan(0.5)             # 存在但無功能（應該是 float，不是 int）

# MIN_SLICE_TIME
engine.set_min_slice_time(0.1)   # 存在但功能簡化（缺少指數曲線）

# Polyphonic
engine.set_poly(4)               # 完全缺失
engine.get_num_voices()          # 缺失

# SPEED 範圍
engine.set_speed(-2.0)           # 無法設定（限制在 0.25-4.0）
```

### 已實作的方法

```python
# ✅ 以下方法已正確實作：

# 基本控制
engine.set_recording(True)
engine.set_looping(True)
engine.set_mix(0.5)
engine.set_feedback(0.3)
engine.set_speed(1.0)  # 但範圍錯誤

# EQ
engine.set_eq_low(3.0)
engine.set_eq_mid(0.0)
engine.set_eq_high(-3.0)

# Effects
engine.set_delay_time(0.25, 0.3)
engine.set_delay_feedback(0.4)
engine.set_delay_wet(0.3)
engine.set_reverb_room(0.7)
engine.set_reverb_damping(0.5)
engine.set_reverb_decay(0.6)
engine.set_reverb_wet(0.3)

# 音訊處理
output_l, output_r = engine.process(input_l, input_r)
engine.clear()
```

---

## 6. EQ 實作對比

### VCV Rack 版本

```cpp
// 使用 VCV Rack 的 TBiquadFilter
dsp::TBiquadFilter<> eqLowL, eqLowR;
dsp::TBiquadFilter<> eqMidL, eqMidR;
dsp::TBiquadFilter<> eqHighL, eqHighR;

// 頻率: 80Hz (Low), 2500Hz (Mid), 12000Hz (High)
eqLowL.setParameters(dsp::TBiquadFilter<>::LOWSHELF,
    80.0f / args.sampleRate, 0.707f,
    std::pow(10.0f, eqLowGain / 20.0f));
eqMidL.setParameters(dsp::TBiquadFilter<>::PEAK,
    2500.0f / args.sampleRate, 0.707f,
    std::pow(10.0f, eqMidGain / 20.0f));
eqHighL.setParameters(dsp::TBiquadFilter<>::HIGHSHELF,
    12000.0f / args.sampleRate, 0.707f,
    std::pow(10.0f, eqHighGain / 20.0f));
```

### 重建版本

```cpp
// 自訂 ThreeBandEQ 類別
// 頻率: 250Hz (Low), 1000Hz (Mid), 4000Hz (High)
calculateLowShelf(250.0f, lowGain);
calculatePeaking(1000.0f, midGain, 1.0f);
calculateHighShelf(4000.0f, highGain);
```

**結論**: ⚠️ **EQ 頻率不一致，音色會有差異**

| Band | VCV Rack | 重建版本 | 影響 |
|------|----------|---------|------|
| Low  | 80 Hz    | 250 Hz  | 低頻響應不同 |
| Mid  | 2500 Hz  | 1000 Hz | 中頻特性不同 |
| High | 12000 Hz | 4000 Hz | 高頻響應不同 |

---

## 7. Delay/Reverb 實作對比

### ✅ Delay 實作

**VCV Rack**:
```cpp
struct DelayProcessor {
    static constexpr int DELAY_BUFFER_SIZE = 96000;  // 2秒 @ 48kHz
    float buffer[DELAY_BUFFER_SIZE];
    // ...
};
```

**重建版本**:
```cpp
class StereoDelay {
    float maxDelay = 2.0f;
    int bufferSize = (int)(maxDelay * sampleRate);
    std::vector<float> leftBuffer;
    std::vector<float> rightBuffer;
    // ...
};
```

**結論**: ✅ **Delay 實作基本一致**

### ✅ Reverb 實作

**VCV Rack**:
```cpp
struct ReverbProcessor {
    // Freeverb style
    static constexpr int COMB_1_SIZE = 1557;
    static constexpr int COMB_2_SIZE = 1617;
    // ... 4 comb filters
    static constexpr int ALLPASS_1_SIZE = 556;
    static constexpr int ALLPASS_2_SIZE = 441;
    // ... 2 allpass filters
};
```

**重建版本**:
```cpp
class ReverbProcessor {
    static constexpr int COMB_SIZES[8] = {
        1557, 1617, 1491, 1422, 1277, 1356, 1188, 1116
    };
    static constexpr int ALLPASS_SIZES[4] = {
        556, 441, 341, 225
    };
    // 4 comb filters per channel + 4 allpass filters
};
```

**結論**: ⚠️ **Reverb 架構類似，但 filter 數量不同（VCV: 4+2, 重建: 8+4）**

---

## 測試驗證方案

以下是建議的測試腳本（**目前無法完整執行，因為缺少核心功能**）:

### 測試 1: Slice 系統（❌ 無法測試）

```python
import numpy as np
import alien4

# 創建引擎
engine = alien4.AudioEngine(48000.0)

# 生成 1 秒 440Hz 正弦波
t = np.linspace(0, 1, 48000, dtype=np.float32)
signal = 0.5 * np.sin(2 * np.pi * 440 * t)

# 錄音
engine.set_recording(True)
for i in range(0, len(signal), 512):
    chunk_l = signal[i:i+512]
    chunk_r = signal[i:i+512]
    engine.process(chunk_l, chunk_r)
engine.set_recording(False)

# ❌ 缺失: 無法檢查 slice 數量
# num_slices = engine.get_num_slices()
# print(f"Detected {num_slices} slices")

# ❌ 缺失: 無法測試 SCAN
# engine.set_scan(0.5)

# ❌ 缺失: 無法測試 MIN_SLICE_TIME
# engine.set_min_slice_time(0.1)
# engine.rescan_slices()
```

### 測試 2: Polyphonic 系統（❌ 無法測試）

```python
# ❌ 缺失: 無法設定 poly voices
# engine.set_poly(4)

# ❌ 缺失: 無法驗證 L/R 交替輸出
# output_l, output_r = engine.process(silence, silence)
# assert output_l != output_r  # 應該有立體聲差異
```

### 測試 3: 參數範圍（⚠️ 部分可測試）

```python
# ✅ 可測試: EQ
engine.set_eq_low(10.0)   # +10dB
engine.set_eq_mid(-5.0)   # -5dB
engine.set_eq_high(3.0)   # +3dB

# ⚠️ 範圍錯誤: SPEED
engine.set_speed(-2.0)  # ❌ 應該支援，但被限制在 0.25-4.0

# ✅ 可測試: Effects
engine.set_delay_time(0.25, 0.3)
engine.set_delay_feedback(0.4)
engine.set_delay_wet(0.5)
engine.set_reverb_decay(0.6)
engine.set_reverb_wet(0.3)
```

---

## 功能對照表

| 功能項目 | VCV Rack | 重建版本 | 完成度 | 備註 |
|---------|----------|---------|--------|------|
| **Slice 系統** |
| Slice 結構體 | ✅ | ❌ | 0% | 完全缺失 |
| rescanSlices() | ✅ | ❌ | 0% | 完全缺失 |
| 動態 threshold detection | ✅ | ❌ | 0% | threshold=0.5 |
| MIN_SLICE_TIME 過濾 | ✅ | ❌ | 0% | 0.001-5.0s |
| 即時錄音 slice 偵測 | ✅ | ❌ | 0% | 完全缺失 |
| **Polyphonic 系統** |
| Voice 結構體 | ✅ | ❌ | 0% | 完全缺失 |
| redistributeVoices() | ✅ | ❌ | 0% | 完全缺失 |
| 1-8 voices 支援 | ✅ | ❌ | 0% | 完全缺失 |
| 隨機 slice 分配 | ✅ | ❌ | 0% | 完全缺失 |
| 隨機 speed multiplier | ✅ | ❌ | 0% | -2.0~+2.0 |
| L/R 交替輸出 | ✅ | ❌ | 0% | 完全缺失 |
| **參數系統** |
| SCAN (0.0-1.0) | ✅ | ❌ | 10% | 參數存在但無功能 |
| MIN_SLICE_TIME (指數曲線) | ✅ | ❌ | 30% | 有參數但無曲線 |
| SPEED (-8~+8) | ✅ | ⚠️ | 50% | 範圍錯誤(0.25~4) |
| POLY (1-8) | ✅ | ❌ | 0% | 完全缺失 |
| MIX (0-1) | ✅ | ✅ | 100% | ✓ |
| FDBK (0-1) | ✅ | ⚠️ | 70% | 缺少 tanh 限制 |
| **音訊處理** |
| 錄音 | ✅ | ✅ | 100% | ✓ |
| Loop 播放 | ✅ | ✅ | 90% | 缺少 slice 功能 |
| 3-Band EQ | ✅ | ⚠️ | 80% | 頻率不一致 |
| Delay | ✅ | ✅ | 95% | ✓ |
| Reverb | ✅ | ⚠️ | 85% | Filter 數量不同 |
| **Python Binding** |
| 基本參數 | ✅ | ✅ | 90% | ✓ |
| Slice 查詢方法 | ✅ | ❌ | 0% | 完全缺失 |
| Poly 控制 | ✅ | ❌ | 0% | 完全缺失 |
| NumPy 整合 | ✅ | ✅ | 100% | ✓ |

**總體完成度: ~40%**

---

## 結論與建議

### 嚴重缺陷

1. **Slice 系統完全缺失** - 這是 Alien4 的核心功能
2. **Polyphonic Voice 系統完全缺失** - 無法產生特色音色
3. **SCAN 參數無功能** - 無法選擇 slice
4. **POLY 參數缺失** - 無法控制 polyphony

### 建議行動

#### 優先級 1（必須實作）

1. **實作 Slice 系統**
   - 創建 `Slice` 結構體
   - 實作 `rescanSlices()` 方法
   - 在錄音時即時 slice 偵測
   - 實作 MIN_SLICE_TIME 的指數曲線

2. **實作 Polyphonic Voice 系統**
   - 創建 `Voice` 結構體
   - 實作 `redistributeVoices()` 方法
   - 實作 L/R 交替輸出
   - 實作隨機 speed multiplier

3. **實作 SCAN 功能**
   - 將 scanIndex 從 int 改為 float (0.0-1.0)
   - 實作 slice 選擇邏輯
   - SCAN 變化時觸發 redistributeVoices()

#### 優先級 2（應該修正）

1. **修正參數範圍**
   - SPEED: 改為 -8.0 到 +8.0
   - 加入 POLY: 1 到 8（整數）

2. **修正 EQ 頻率**
   - Low: 250Hz → 80Hz
   - Mid: 1000Hz → 2500Hz
   - High: 4000Hz → 12000Hz

3. **加入 Feedback 軟限制**
   - 使用 `tanh(x * 0.3) / 0.3`

#### 優先級 3（建議加強）

1. **Python Binding 擴充**
   ```python
   engine.get_num_slices() -> int
   engine.get_slice_info(index) -> dict
   engine.set_poly(voices: int)
   engine.get_current_slice() -> int
   ```

2. **測試腳本**
   - 建立完整的單元測試
   - 驗證 slice 偵測準確性
   - 驗證 polyphonic 輸出

---

## 附錄: 關鍵程式碼缺失清單

### 需要從 VCV Rack 版本移植的程式碼

1. **Slice 結構體** (第 46-51 行)
2. **Voice 結構體** (第 54-59 行)
3. **MinSliceTimeParamQuantity** (第 62-87 行)
4. **rescanSlices() 方法** (第 351-399 行)
5. **redistributeVoices() 方法** (第 417-444 行)
6. **錄音時 slice 偵測** (第 510-547 行)
7. **停止錄音時 slice finalization** (第 458-470 行)
8. **SCAN 功能邏輯** (第 602-632 行)
9. **Polyphonic 播放邏輯** (第 692-771 行)
10. **Voice 動態管理** (第 549-599 行)

### 估計工作量

- **Slice 系統**: 8-12 小時
- **Polyphonic Voice 系統**: 10-15 小時
- **參數整合與測試**: 4-6 小時
- **Python Binding 擴充**: 2-3 小時
- **總計**: **24-36 小時**

---

**驗證人員**: Claude (Sonnet 4.5)
**文件版本**: 1.0
**最後更新**: 2025-11-14
