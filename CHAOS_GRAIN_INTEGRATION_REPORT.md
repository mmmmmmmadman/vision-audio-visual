# Alien4 Chaos & Grain Integration Report

## 概要

成功完成 AudioEngine 類別的 ChaosGenerator 和 GrainProcessor 整合。

## 修改的檔案

**主要檔案**: `/Users/madzine/Documents/VAV/alien4_extension.cpp`

---

## 1. 新增的成員變數 (Private Section)

### Chaos 和 Grain Processors
```cpp
// Chaos and Grain processors
ChaosGenerator chaos;
GrainProcessor leftGrainProcessor;
GrainProcessor rightGrainProcessor;
```

### Chaos 參數
```cpp
// Chaos parameters
float chaosRate = 0.01f;           // Chaos rate (0.0-1.0)
float chaosAmount = 1.0f;          // Chaos amount (0.0-1.0)
bool chaosShape = false;           // false = smooth (0.01-1.0), true = stepped (1.0-10.0)
bool delayChaosMod = false;        // Delay chaos modulation enable
bool grainChaosMod = true;         // Grain chaos modulation (固定 on)
bool reverbChaosMod = false;       // Reverb chaos modulation enable
```

### Grain 參數
```cpp
// Grain parameters
float grainSize = 0.3f;            // Grain size (0.0-1.0)
float grainDensity = 0.4f;         // Break parameter (0.0-1.0)
float grainPosition = 0.5f;        // Shift parameter (固定 50% = 0.5)
float grainWetDry = 0.0f;          // Dry/Wet mix (0.0-1.0)
```

---

## 2. 新增的 Setter 方法 (Public Section)

### Chaos Control Methods
```cpp
void set_chaos_rate(float rate);              // Set chaos rate (0.0-1.0)
void set_chaos_amount(float amount);          // Set chaos amount (0.0-1.0)
void set_chaos_shape(bool shape);             // Set chaos shape mode
void set_delay_chaos(bool enabled);           // Enable/disable delay chaos modulation
void set_reverb_chaos(bool enabled);          // Enable/disable reverb chaos modulation
```

### Grain Control Methods
```cpp
void set_grain_size(float size);              // Set grain size (0.0-1.0)
void set_grain_density(float density);        // Set grain density/break (0.0-1.0)
void set_grain_wet_dry(float wet);            // Set grain wet/dry mix (0.0-1.0)
```

---

## 3. Process() 方法修改細節

### 處理流程順序
```
Input → EQ → Chaos Generation → Delay (with chaos) → Grain → Reverb (with chaos) → Feedback
```

### 3.1 Stage 1: Chaos 訊號生成 (line 1168-1197)

```cpp
// Calculate chaos rate based on shape mode
float chaosRateValue;
if (chaosShape) {
    // Shape ON: 1.0-10.0 range
    chaosRateValue = 1.0f + chaosRate * 9.0f;
} else {
    // Shape OFF: 0.01-1.0 range
    chaosRateValue = 0.01f + chaosRate * 0.99f;
}

// Generate raw chaos signal
float chaosRaw = chaos.process(chaosRateValue) * chaosAmount;

// Apply step function if chaosShape is true
static float lastStep = 0.0f;
static float stepPhase = 0.0f;
float chaosOutput;

if (chaosShape) {
    float stepRate = chaosRateValue * 10.0f;
    stepPhase += stepRate / sampleRate;
    if (stepPhase >= 1.0f) {
        lastStep = chaosRaw;
        stepPhase = 0.0f;
    }
    chaosOutput = lastStep;
} else {
    chaosOutput = chaosRaw;
}
```

**重點**:
- 支援兩種 chaos 模式:
  - `chaosShape = false`: 平滑模式 (0.01-1.0 range)
  - `chaosShape = true`: 階躍模式 (1.0-10.0 range, with step function)
- Static 變數 `lastStep` 和 `stepPhase` 用於階躍功能

### 3.2 Stage 2: Delay 處理 with Chaos Modulation (line 1199-1218)

```cpp
// Apply chaos modulation to delay times if enabled
float modDelayTimeL = smoothDelayTimeL;
float modDelayTimeR = smoothDelayTimeR;
float modDelayFeedback = smoothDelayFeedback;

if (delayChaosMod) {
    modDelayTimeL += chaosOutput * 0.1f;
    modDelayTimeR += chaosOutput * 0.1f;
    modDelayTimeL = clamp(modDelayTimeL, 0.001f, 2.0f);
    modDelayTimeR = clamp(modDelayTimeR, 0.001f, 2.0f);

    modDelayFeedback += chaosOutput * 0.1f;
    modDelayFeedback = clamp(modDelayFeedback, 0.0f, 0.95f);
}

auto delayResult = delay.process(eqL, eqR, modDelayTimeL, modDelayTimeR,
                                modDelayFeedback, sampleRate);
```

**重點**:
- Chaos 可調變 delay time (L/R) 和 feedback
- 調變量為 `chaosOutput * 0.1f`
- 確保參數在安全範圍內

### 3.3 Stage 3: Grain 處理 (line 1226-1238)

```cpp
// Process grain with chaos modulation
float leftGrainOutput = leftGrainProcessor.process(delayMixL, grainSize, grainDensity,
                                                  grainPosition, grainChaosMod,
                                                  chaosOutput, sampleRate);
float rightGrainOutput = rightGrainProcessor.process(delayMixR, grainSize, grainDensity,
                                                     grainPosition, grainChaosMod,
                                                     chaosOutput * -1.0f, sampleRate);

// Grain wet/dry mix
float leftStage2 = delayMixL * (1.0f - grainWetDry) + leftGrainOutput * grainWetDry;
float rightStage2 = delayMixR * (1.0f - grainWetDry) + rightGrainOutput * grainWetDry;
```

**重點**:
- 左右聲道使用獨立的 GrainProcessor
- 右聲道使用反轉的 chaos 訊號 (`chaosOutput * -1.0f`) 增加立體感
- `grainChaosMod` 固定為 true
- `grainPosition` 固定為 0.5 (50%)

### 3.4 Stage 4: Reverb 處理 with Chaos Modulation (line 1240-1248)

```cpp
float reverbedL = reverbL.process(leftStage2, rightStage2, grainDensity,
                                 smoothReverbRoom, smoothReverbDamping, smoothReverbDecay,
                                 true, reverbChaosMod, chaosOutput, sampleRate);
float reverbedR = reverbR.process(leftStage2, rightStage2, grainDensity,
                                 smoothReverbRoom, smoothReverbDamping, smoothReverbDecay,
                                 false, reverbChaosMod, chaosOutput, sampleRate);

float outputL = leftStage2 * (1.0f - smoothReverbWet) + reverbedL * smoothReverbWet;
float outputR = rightStage2 * (1.0f - smoothReverbWet) + reverbedR * smoothReverbWet;
```

**重點**:
- Reverb 接收 `grainDensity` 參數
- Chaos modulation 可選 (由 `reverbChaosMod` 控制)
- 使用 grain 處理後的訊號 (`leftStage2`, `rightStage2`)

---

## 4. Clear() 方法修改

新增處理器重置:
```cpp
// Reset Chaos and Grain processors
chaos.reset();
leftGrainProcessor.reset();
rightGrainProcessor.reset();
```

---

## 5. Python Bindings 新增

### Chaos Methods
```python
.def("set_chaos_rate", &AudioEngine::set_chaos_rate,
     py::arg("rate"),
     "Set chaos rate (0.0-1.0)")
.def("set_chaos_amount", &AudioEngine::set_chaos_amount,
     py::arg("amount"),
     "Set chaos amount (0.0-1.0)")
.def("set_chaos_shape", &AudioEngine::set_chaos_shape,
     py::arg("shape"),
     "Set chaos shape (false=smooth, true=stepped)")
.def("set_delay_chaos", &AudioEngine::set_delay_chaos,
     py::arg("enabled"),
     "Enable/disable delay chaos modulation")
.def("set_reverb_chaos", &AudioEngine::set_reverb_chaos,
     py::arg("enabled"),
     "Enable/disable reverb chaos modulation")
```

### Grain Methods
```python
.def("set_grain_size", &AudioEngine::set_grain_size,
     py::arg("size"),
     "Set grain size (0.0-1.0)")
.def("set_grain_density", &AudioEngine::set_grain_density,
     py::arg("density"),
     "Set grain density/break (0.0-1.0)")
.def("set_grain_wet_dry", &AudioEngine::set_grain_wet_dry,
     py::arg("wet"),
     "Set grain wet/dry mix (0.0-1.0)")
```

---

## 6. 測試結果

### 編譯狀態
- ✅ **編譯成功** (無錯誤、無警告)
- 輸出檔案: `vav/audio/alien4.cpython-311-darwin.so` (216K)

### 功能測試 (test_chaos_grain.py)
所有測試項目均通過:

1. ✅ Chaos control methods - 所有參數設定方法正常
2. ✅ Grain control methods - 所有參數設定方法正常
3. ✅ Audio processing - 完整訊號處理鏈運作正常
4. ✅ Delay chaos modulation - Chaos 調變 delay 功能正常
5. ✅ Reverb chaos modulation - Chaos 調變 reverb 功能正常
6. ✅ Chaos shape modes - 平滑/階躍模式切換正常
7. ✅ Grain parameters - Size/Density 參數變化正常
8. ✅ Complete signal chain - 完整效果鏈運作正常,立體聲輸出驗證通過

### 輸出範例
```
Output RMS: L=0.1495, R=0.1971
Smooth mode RMS: 0.1549
Stepped mode RMS: 0.1567
Final output RMS: L=0.1516, R=0.1485
✓ Stereo output verified (L ≠ R)
```

---

## 7. 重要提醒與設計決策

### 固定參數
1. **grainPosition = 0.5** (固定 50%)
   - 不提供 setter 方法
   - 在 grain processing 中始終使用 0.5

2. **grainChaosMod = true** (固定 on)
   - Grain 始終接受 chaos modulation
   - 不提供開關控制

### Static 變數使用
- `lastStep` 和 `stepPhase` 為 static 變數
- 用於 chaos stepped mode 的狀態保存
- 確保在不同 process() 呼叫之間保持狀態

### 立體聲處理
- 左右聲道使用獨立的 GrainProcessor
- 右聲道 chaos 訊號反轉 (`* -1.0f`)
- 增加立體聲分離度

### 處理順序
嚴格遵循: **EQ → Delay (chaos) → Grain → Reverb (chaos) → Feedback**

---

## 8. 使用範例

```python
import alien4

# Create engine
engine = alien4.AudioEngine(48000)

# Configure chaos
engine.set_chaos_rate(0.5)       # 50% rate
engine.set_chaos_amount(0.7)     # 70% amount
engine.set_chaos_shape(False)    # Smooth mode
engine.set_delay_chaos(True)     # Enable delay modulation
engine.set_reverb_chaos(True)    # Enable reverb modulation

# Configure grain
engine.set_grain_size(0.3)       # Small-medium grains
engine.set_grain_density(0.5)    # Medium density
engine.set_grain_wet_dry(0.4)    # 40% wet

# Process audio
left_out, right_out = engine.process(left_in, right_in)
```

---

## 總結

✅ **所有要求的功能均已成功實現並測試通過**

### 新增功能
- 8 個新的成員變數 (chaos + grain 參數)
- 3 個新的處理器實例
- 8 個新的 setter 方法
- 完整的 chaos/grain 訊號處理鏈
- Python bindings

### 測試狀態
- 編譯: ✅ 成功
- 單元測試: ✅ 8/8 項目通過
- 整合測試: ✅ 完整訊號鏈運作正常

### 檔案
- 主要實作: `alien4_extension.cpp` (1577 行)
- 測試腳本: `test_chaos_grain.py`
- 編譯輸出: `vav/audio/alien4.cpython-311-darwin.so`

---

**日期**: 2025-11-15
**狀態**: ✅ 完成並測試通過
