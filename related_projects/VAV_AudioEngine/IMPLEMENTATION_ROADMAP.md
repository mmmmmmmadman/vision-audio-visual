# Alien4 實作路徑圖

**目標**: 100% 實作 VCV Rack 版本功能

**目前完成度**: ~40%

**剩餘工作量**: 27-40 小時

---

## 階段 1: Slice 系統（8-12 小時）⭐ 最高優先級

### 1.1 建立 Slice 結構體（1 小時）

**檔案**: `src/slice.hpp`

```cpp
struct Slice {
    int startSample = 0;
    int endSample = 0;
    float peakAmplitude = 0.0f;
    bool active = false;
};
```

**驗收標準**:
- ✅ 結構體定義完成
- ✅ 可編譯通過

---

### 1.2 實作 rescanSlices() 方法（3-4 小時）

**檔案**: `src/alien4_engine.hpp`

**新增變數**:
```cpp
private:
    std::vector<Slice> slices;
    float lastMinSliceTime = 0.05f;
    int currentSliceIndex = 0;
```

**新增方法**:
```cpp
void rescanSlices(float threshold, float minSliceTime, float sampleRate) {
    if (recordedLength <= 0) return;

    slices.clear();
    int minSliceSamples = (int)(minSliceTime * sampleRate);
    float lastAmp = 0.0f;

    for (int pos = 0; pos < recordedLength; pos++) {
        float currentAmp = std::abs(loopBuffer[pos]);

        // Onset detection
        if (lastAmp < threshold && currentAmp >= threshold) {
            // Close previous slice if too short
            if (!slices.empty() && slices.back().active) {
                int sliceLength = pos - slices.back().startSample;
                if (sliceLength >= minSliceSamples) {
                    slices.back().endSample = pos - 1;
                } else {
                    slices.pop_back();
                }
            }

            // Create new slice
            if (slices.empty() || slices.back().endSample > 0) {
                Slice newSlice;
                newSlice.startSample = pos;
                newSlice.active = true;
                newSlice.peakAmplitude = 0.0f;
                slices.push_back(newSlice);
            }
        }

        // Track peak amplitude
        if (!slices.empty() && slices.back().active &&
            slices.back().endSample == 0) {
            slices.back().peakAmplitude =
                std::max(slices.back().peakAmplitude, currentAmp);
        }

        lastAmp = currentAmp;
    }

    // Finalize last slice
    if (!slices.empty() && slices.back().active &&
        slices.back().endSample == 0) {
        int sliceLength = recordedLength - slices.back().startSample;
        if (sliceLength >= minSliceSamples) {
            slices.back().endSample = recordedLength - 1;
        } else {
            slices.pop_back();
        }
    }
}
```

**驗收標準**:
- ✅ threshold = 0.5 onset detection 正常
- ✅ MIN_SLICE_TIME 過濾正常
- ✅ Peak amplitude 追蹤正常
- ✅ 單元測試通過

**單元測試**:
```cpp
// 生成 1 秒 440Hz + 0.5 秒靜音 + 1 秒 880Hz
// 應該偵測到 2 個 slices
```

---

### 1.3 即時錄音 Slice 偵測（2-3 小時）

**整合到 process() 方法**:

```cpp
if (recording && recordPosition < LOOP_BUFFER_SIZE) {
    loopBuffer[recordPosition] = input;
    recordedLength = recordPosition + 1;

    float currentAmp = std::abs(input);
    float threshold = 0.5f;
    int minSliceSamples = (int)(getMinSliceTime() * sampleRate);

    // Onset detection
    if (lastAmplitude < threshold && currentAmp >= threshold) {
        // Close previous slice if exists
        if (!slices.empty() && slices.back().active &&
            slices.back().endSample == 0) {
            int sliceLength = recordPosition - slices.back().startSample;
            if (sliceLength >= minSliceSamples) {
                slices.back().endSample = recordPosition - 1;
            } else {
                slices.pop_back();
            }
        }

        // Create new slice
        if (slices.empty() || slices.back().endSample > 0) {
            Slice newSlice;
            newSlice.startSample = recordPosition;
            newSlice.active = true;
            newSlice.peakAmplitude = 0.0f;
            slices.push_back(newSlice);
        }
    }

    // Track peak
    if (!slices.empty() && slices.back().active &&
        slices.back().endSample == 0) {
        slices.back().peakAmplitude =
            std::max(slices.back().peakAmplitude, currentAmp);
    }

    lastAmplitude = currentAmp;
    recordPosition++;
}
```

**驗收標準**:
- ✅ 錄音時即時偵測 slices
- ✅ 停止錄音時 finalize 最後一個 slice
- ✅ slice 數量正確

---

### 1.4 MIN_SLICE_TIME 指數曲線（1-2 小時）

**新增方法**:
```cpp
float getMinSliceTime() const {
    float knobValue = minSliceTime;  // 0.0-1.0 from parameter

    if (knobValue <= 0.5f) {
        // Left half: exponential 0.001 to 1.0
        float t = knobValue * 2.0f;
        return 0.001f * std::pow(1000.0f, t);
    } else {
        // Right half: linear 1.0 to 5.0
        float t = (knobValue - 0.5f) * 2.0f;
        return 1.0f + t * 4.0f;
    }
}
```

**更新 setMinSliceTime()**:
```cpp
void setMinSliceTime(float knobValue) {
    minSliceTime = std::max(0.0f, std::min(1.0f, knobValue));
}
```

**驗收標準**:
- ✅ 0.0 → 0.001s
- ✅ 0.25 → ~0.03s
- ✅ 0.5 → 1.0s
- ✅ 0.75 → 3.0s
- ✅ 1.0 → 5.0s

---

### 1.5 自動 Rescan 功能（1-2 小時）

**在 process() 中加入**:
```cpp
// Check if minSliceTime changed
float currentMinSliceTime = getMinSliceTime();
if (!recording && recordedLength > 0 &&
    std::abs(currentMinSliceTime - lastMinSliceTime) > 0.001f) {
    rescanSlices(0.5f, currentMinSliceTime, sampleRate);
    // TODO: redistributeVoices() (階段 2)
    lastMinSliceTime = currentMinSliceTime;
}
```

**驗收標準**:
- ✅ MIN_SLICE_TIME 變化時自動 rescan
- ✅ slice 數量正確更新

---

### 1.6 Python Binding 擴充（0.5 小時）

**python_bindings.cpp**:
```cpp
.def("get_num_slices", [](Alien4Wrapper& self) {
    return self.engine.getNumSlices();
})
.def("get_slice_info", [](Alien4Wrapper& self, int index) {
    auto slice = self.engine.getSliceInfo(index);
    py::dict info;
    info["start"] = slice.startSample;
    info["end"] = slice.endSample;
    info["peak"] = slice.peakAmplitude;
    info["active"] = slice.active;
    return info;
})
```

**驗收標準**:
- ✅ Python 可查詢 slice 數量
- ✅ Python 可讀取 slice 資訊

---

## 階段 2: Polyphonic Voice 系統（10-15 小時）⭐ 核心功能

### 2.1 建立 Voice 結構體（0.5 小時）

**檔案**: `src/voice.hpp`

```cpp
struct Voice {
    int sliceIndex = 0;
    int playbackPosition = 0;
    float playbackPhase = 0.0f;
    float speedMultiplier = 1.0f;
};
```

---

### 2.2 整合 Voice 變數（1 小時）

**alien4_engine.hpp**:
```cpp
private:
    std::vector<Voice> voices;
    int numVoices = 1;
    std::default_random_engine randomEngine;
    float lastScanValue = -1.0f;

public:
    Alien4AudioEngine() {
        // ...
        randomEngine.seed(std::random_device()());
    }
```

---

### 2.3 實作 redistributeVoices()（2-3 小時）

```cpp
void redistributeVoices() {
    if (slices.empty() || numVoices <= 1 || voices.empty()) return;

    std::uniform_int_distribution<int> sliceDist(0, slices.size() - 1);
    std::uniform_real_distribution<float> speedDist(-2.0f, 2.0f);

    for (int i = 1; i < numVoices; i++) {
        // Find valid active slice
        int targetSliceIndex = sliceDist(randomEngine);
        int attempts = 0;
        while (attempts < 20 &&
               (!slices[targetSliceIndex].active ||
                slices[targetSliceIndex].startSample >= recordedLength)) {
            targetSliceIndex = sliceDist(randomEngine);
            attempts++;
        }

        // Safety check
        if (!slices[targetSliceIndex].active ||
            slices[targetSliceIndex].startSample >= recordedLength) {
            continue;
        }

        voices[i].sliceIndex = targetSliceIndex;
        voices[i].playbackPosition = slices[targetSliceIndex].startSample;
        voices[i].playbackPhase = 0.0f;
        voices[i].speedMultiplier = speedDist(randomEngine);
    }
}
```

**驗收標準**:
- ✅ 隨機選擇 active slices
- ✅ 隨機 speed multiplier (-2.0 ~ +2.0)
- ✅ 安全性檢查正常

---

### 2.4 動態 Voice 管理（2-3 小時）

**新增 setNumVoices()**:
```cpp
void setNumVoices(int newNumVoices) {
    newNumVoices = std::max(1, std::min(8, newNumVoices));

    if (newNumVoices != numVoices) {
        numVoices = newNumVoices;
        voices.resize(numVoices);

        if (!slices.empty() && numVoices > 1) {
            // Initialize all voices
            for (int i = 0; i < numVoices; i++) {
                if (i == 0) {
                    voices[i].sliceIndex = currentSliceIndex;
                    voices[i].playbackPosition = playbackPosition;
                    voices[i].playbackPhase = playbackPhase;
                    voices[i].speedMultiplier = 1.0f;
                } else {
                    // Random assignment
                    std::uniform_int_distribution<int> dist(0, slices.size()-1);
                    std::uniform_real_distribution<float> speedDist(-2.0f, 2.0f);

                    int targetSlice = dist(randomEngine);
                    voices[i].sliceIndex = targetSlice;
                    voices[i].playbackPosition =
                        slices[targetSlice].startSample;
                    voices[i].playbackPhase = 0.0f;
                    voices[i].speedMultiplier = speedDist(randomEngine);
                }
            }
        }
    }
}
```

**驗收標準**:
- ✅ 1-8 voices 支援
- ✅ Voice 0 使用當前 slice
- ✅ Voice 1-7 隨機分配

---

### 2.5 Polyphonic 播放邏輯（4-6 小時）⭐ 關鍵實作

**重寫 playback 部分**:
```cpp
if (numVoices == 1 || voices.empty()) {
    // Single voice mode (現有邏輯)
    // ...
} else {
    // Multiple voices mode
    loopL = 0.0f;
    loopR = 0.0f;

    for (int i = 0; i < numVoices; i++) {
        float voiceSpeed = playbackSpeed * voices[i].speedMultiplier;
        voiceSpeed = std::clamp(voiceSpeed, -16.0f, 16.0f);

        voices[i].playbackPhase += voiceSpeed;
        int positionDelta = (int)voices[i].playbackPhase;
        voices[i].playbackPhase -= (float)positionDelta;
        voices[i].playbackPosition += positionDelta;

        // Loop current slice
        if (!slices.empty() &&
            voices[i].sliceIndex < (int)slices.size() &&
            slices[voices[i].sliceIndex].active) {

            int sliceStart = slices[voices[i].sliceIndex].startSample;
            int sliceEnd = slices[voices[i].sliceIndex].endSample;

            bool voiceReverse = voiceSpeed < 0.0f;
            if (voiceReverse) {
                if (voices[i].playbackPosition < sliceStart) {
                    voices[i].playbackPosition = sliceEnd;
                }
            } else {
                if (voices[i].playbackPosition > sliceEnd) {
                    voices[i].playbackPosition = sliceStart;
                }
            }
        }

        // Read with interpolation
        if (recordedLength > 0) {
            voices[i].playbackPosition =
                std::clamp(voices[i].playbackPosition, 0, recordedLength - 1);

            int pos0 = voices[i].playbackPosition;
            int pos1 = (recordedLength > 1) ?
                       ((pos0 + 1) % recordedLength) : pos0;

            pos0 = std::clamp(pos0, 0, LOOP_BUFFER_SIZE - 1);
            pos1 = std::clamp(pos1, 0, LOOP_BUFFER_SIZE - 1);

            float frac = std::clamp(
                std::abs(voices[i].playbackPhase), 0.0f, 1.0f
            );

            float sample = loopBuffer[pos0] * (1.0f - frac) +
                          loopBuffer[pos1] * frac;

            if (std::isfinite(sample)) {
                // Alternate L/R
                if (i % 2 == 0) {
                    loopL += sample;
                } else {
                    loopR += sample;
                }
            }
        }
    }

    // Normalize by sqrt of voices per channel
    int leftVoices = (numVoices + 1) / 2;
    int rightVoices = numVoices / 2;
    if (leftVoices > 0) loopL /= std::sqrt((float)leftVoices);
    if (rightVoices > 0) loopR /= std::sqrt((float)rightVoices);

    // Update layer position to voice 0
    if (!voices.empty()) {
        playbackPosition = voices[0].playbackPosition;
        playbackPhase = voices[0].playbackPhase;
        currentSliceIndex = voices[0].sliceIndex;
    }
}
```

**驗收標準**:
- ✅ 多 voice 同時播放
- ✅ 每個 voice 播放不同 slice
- ✅ 每個 voice 不同速度
- ✅ L/R 交替分配（偶數→L，奇數→R）
- ✅ 正規化正確（sqrt）
- ✅ 反向播放支援

---

### 2.6 Python Binding（0.5 小時）

```cpp
.def("set_poly", &Alien4Wrapper::set_poly, py::arg("voices"),
     "Set polyphonic voices (1-8)")
.def("get_num_voices", [](Alien4Wrapper& self) {
    return self.engine.getNumVoices();
})
```

---

## 階段 3: SCAN 功能（2-3 小時）

### 3.1 SCAN 參數整合（1 小時）

**修改 setScan()**:
```cpp
void setScan(float value) {
    scanValue = std::clamp(value, 0.0f, 1.0f);
}
```

**在 process() 中**:
```cpp
// Check if SCAN value changed
if (std::abs(scanValue - lastScanValue) > 0.001f) {
    redistributeVoices();
    lastScanValue = scanValue;
}

// Manual scan mode
if (slices.size() > 1 && scanValue > 0.01f) {
    int targetSliceIndex =
        (int)std::round(scanValue * (slices.size() - 1));
    targetSliceIndex =
        std::clamp(targetSliceIndex, 0, (int)slices.size() - 1);

    if (targetSliceIndex != lastScanTargetIndex &&
        slices[targetSliceIndex].active) {
        currentSliceIndex = targetSliceIndex;
        playbackPosition = slices[targetSliceIndex].startSample;
        playbackPhase = 0.0f;
        lastScanTargetIndex = targetSliceIndex;

        // Update voice 0
        if (numVoices > 1 && !voices.empty()) {
            voices[0].sliceIndex = targetSliceIndex;
            voices[0].playbackPosition =
                slices[targetSliceIndex].startSample;
            voices[0].playbackPhase = 0.0f;
        }
    }
}
```

**驗收標準**:
- ✅ SCAN 0.0 → slice 0
- ✅ SCAN 1.0 → 最後一個 slice
- ✅ SCAN 變化時 redistribute voices
- ✅ Voice 0 跟隨 SCAN

---

### 3.2 Python Binding（0.5 小時）

```cpp
// 修正型別
.def("set_scan", &Alien4Wrapper::set_scan, py::arg("value"),
     "Set slice scan position (0.0-1.0)")
.def("get_current_slice", [](Alien4Wrapper& self) {
    return self.engine.getCurrentSliceIndex();
})
```

---

## 階段 4: 參數修正（2-3 小時）

### 4.1 SPEED 範圍修正（1 小時）

```cpp
void setSpeed(float spd) {
    speed = std::clamp(spd, -8.0f, 8.0f);  // 改為 -8~+8
}
```

**測試**:
- ✅ 正向播放（+1.0）
- ✅ 反向播放（-1.0）
- ✅ 極限測試（±8.0）

---

### 4.2 EQ 頻率修正（1 小時）

**three_band_eq.hpp**:
```cpp
ThreeBandEQ(float sr = 48000.0f) : sampleRate(sr) {
    calculateLowShelf(80.0f, 0.0f);     // 250 → 80
    calculatePeaking(2500.0f, 0.0f, 1.0f);  // 1000 → 2500
    calculateHighShelf(12000.0f, 0.0f);     // 4000 → 12000
}

void setLowGain(float gain) {
    lowGain = std::clamp(gain, -20.0f, 20.0f);
    calculateLowShelf(80.0f, lowGain);
}
// ... 同樣修正 Mid/High
```

---

### 4.3 Feedback 軟限制（0.5 小時）

```cpp
// 在效果鏈之前
float fbL = std::tanh(lastOutputL * 0.3f) / 0.3f;
float fbR = std::tanh(lastOutputR * 0.3f) / 0.3f;

float fbMixL = mixL + fbL * feedbackAmount;
float fbMixR = mixR + fbR * feedbackAmount;
```

---

## 階段 5: 測試與驗證（4-6 小時）

### 5.1 單元測試（2-3 小時）

**test_slices.cpp**:
```cpp
void test_slice_detection() {
    // Generate tone with silence gaps
    // Verify slice count and positions
}

void test_min_slice_time() {
    // Verify exponential curve
    // Verify filtering
}

void test_rescan() {
    // Change MIN_SLICE_TIME
    // Verify slice count changes
}
```

**test_polyphonic.cpp**:
```cpp
void test_voice_distribution() {
    // Set POLY=4
    // Verify 4 voices active
    // Verify different slices
}

void test_lr_alternation() {
    // Verify L/R output difference
}

void test_speed_multiplier() {
    // Verify random speed range
}
```

---

### 5.2 整合測試（1-2 小時）

**Python 測試腳本**:
```python
def test_complete_workflow():
    engine = alien4.AudioEngine(48000.0)

    # 1. Record
    engine.set_recording(True)
    # ... record audio with transients ...
    engine.set_recording(False)

    # 2. Verify slices
    num_slices = engine.get_num_slices()
    assert num_slices > 0

    # 3. Test SCAN
    for scan in [0.0, 0.5, 1.0]:
        engine.set_scan(scan)
        output = engine.process(silence, silence)
        # Verify different output

    # 4. Test POLY
    for poly in [1, 4, 8]:
        engine.set_poly(poly)
        output_l, output_r = engine.process(silence, silence)
        # Verify stereo width increases with poly

    # 5. Test MIN_SLICE_TIME
    for mst in [0.0, 0.5, 1.0]:
        engine.set_min_slice_time(mst)
        num = engine.get_num_slices()
        # Verify slice count changes
```

---

### 5.3 性能測試（0.5 小時）

```python
def test_performance():
    engine = alien4.AudioEngine(48000.0)

    # Set POLY=8 (worst case)
    engine.set_poly(8)

    # Measure processing time
    import time
    buffer_size = 512
    num_iterations = 1000

    start = time.time()
    for _ in range(num_iterations):
        output = engine.process(input_l, input_r)
    elapsed = time.time() - start

    samples_processed = buffer_size * num_iterations
    realtime_duration = samples_processed / 48000.0
    realtime_ratio = realtime_duration / elapsed

    print(f"Realtime ratio: {realtime_ratio:.1f}x")
    assert realtime_ratio > 10  # Should be at least 10x realtime
```

---

### 5.4 音色驗證（1 小時）

**比較 VCV Rack 和 C++ Extension 輸出**:
```python
def test_audio_equivalence():
    # 1. Load same audio in VCV Rack and Python
    # 2. Set same parameters
    # 3. Process same input
    # 4. Compare outputs (允許小誤差)

    correlation = np.corrcoef(vcv_output, cpp_output)[0, 1]
    assert correlation > 0.95  # 95% 相似度
```

---

## 時程規劃

### 快速路徑（27 小時）

| 階段 | 時數 | 累計 |
|------|------|------|
| 1. Slice 系統 | 8 | 8 |
| 2. Polyphonic Voice | 10 | 18 |
| 3. SCAN 功能 | 2 | 20 |
| 4. 參數修正 | 2 | 22 |
| 5. 測試驗證 | 5 | 27 |

**目標**: 2-3 個工作天（全職）或 1-2 週（兼職）

### 完整路徑（40 小時）

| 階段 | 時數 | 累計 |
|------|------|------|
| 1. Slice 系統 | 12 | 12 |
| 2. Polyphonic Voice | 15 | 27 |
| 3. SCAN 功能 | 3 | 30 |
| 4. 參數修正 | 3 | 33 |
| 5. 測試驗證 | 6 | 39 |
| 6. 文件撰寫 | 1 | 40 |

**目標**: 1 週（全職）或 2-3 週（兼職）

---

## 里程碑

### 🏁 Milestone 1: Slice 系統可用
- ✅ rescanSlices() 正常
- ✅ 即時錄音 slice 偵測
- ✅ MIN_SLICE_TIME 指數曲線
- ✅ Python 可查詢 slices

**驗收**: 錄音後可看到正確的 slice 數量

---

### 🏁 Milestone 2: Polyphonic 可用
- ✅ redistributeVoices() 正常
- ✅ 1-8 voices 支援
- ✅ L/R 交替輸出
- ✅ 隨機 speed multiplier

**驗收**: 設定 POLY=4 時聽到豐富的 polyphonic 音色

---

### 🏁 Milestone 3: SCAN 可用
- ✅ SCAN 可選擇 slice
- ✅ SCAN 變化時 redistribute
- ✅ Voice 0 跟隨 SCAN

**驗收**: 旋轉 SCAN 時聽到不同 slice

---

### 🏁 Milestone 4: 100% 功能對等
- ✅ 所有參數範圍正確
- ✅ EQ 頻率正確
- ✅ Feedback 軟限制
- ✅ 測試通過

**驗收**: 與 VCV Rack 版本音色 95% 相似

---

## 風險與緩解

### 風險 1: 性能問題
**描述**: 8 個 voices 同時播放可能超過即時性能要求

**緩解**:
- 使用 SIMD 加速插值運算
- 優化 slice 查找演算法
- 考慮使用 voice stealing

---

### 風險 2: 音色差異
**描述**: 浮點運算精度差異導致音色不同

**緩解**:
- 使用相同的演算法和常數
- 進行 bit-exact 對比測試
- 接受合理的浮點誤差（< 0.1%）

---

### 風險 3: 記憶體使用
**描述**: 60 秒 buffer + 8 voices 可能佔用過多記憶體

**緩解**:
- 使用 `std::vector` 動態分配
- 考慮可調整的 buffer 大小
- 監控記憶體使用

---

## 下一步行動

1. **閱讀本路徑圖**
2. **從階段 1.1 開始實作** Slice 結構體
3. **逐步完成每個小節**，確保驗收標準達成
4. **每完成一個階段**，執行相應測試
5. **達成所有里程碑**後，發布 v1.0

---

**預祝實作順利！**

如有問題，請參閱:
- [VERIFICATION_REPORT.md](./VERIFICATION_REPORT.md) - 詳細功能對比
- [VERIFICATION_SUMMARY.md](./VERIFICATION_SUMMARY.md) - 快速摘要
- VCV Rack 原始碼: `/Users/madzine/Documents/VAV/Alien4.cpp`
