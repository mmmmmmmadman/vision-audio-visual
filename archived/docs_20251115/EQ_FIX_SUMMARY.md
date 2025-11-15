# EQ 功能修復完成報告

## 日期
2025-11-14

## 修復內容

已完成 `alien4_extension.cpp` 中 EQ 功能的所有修復工作:

### 1. 建構函式初始化 (line 323-326)
```cpp
// Initialize EQ parameters (cut-only: 0 to -20dB)
eqLowDb = 0.0f;
eqMidDb = 0.0f;
eqHighDb = 0.0f;
```

### 2. Smoothed EQ 變數初始化 (line 332-334)
```cpp
smoothEqLow = eqLowDb;
smoothEqMid = eqMidDb;
smoothEqHigh = eqHighDb;
```

### 3. Reset 函數加入 EQ filter reset (line 420-426)
```cpp
// Reset EQ filters
eqLowL.reset();
eqLowR.reset();
eqMidL.reset();
eqMidR.reset();
eqHighL.reset();
eqHighR.reset();
```

### 4. EQ Setter 函數 (line 502-515)
新增三個 setter 函數,範圍限制在 -20.0dB 到 0.0dB (只能 cut 不能 boost):
```cpp
void set_eq_low(double db) {
    eqLowDb = clamp(static_cast<float>(db), -20.0f, 0.0f);
}

void set_eq_mid(double db) {
    eqMidDb = clamp(static_cast<float>(db), -20.0f, 0.0f);
}

void set_eq_high(double db) {
    eqHighDb = clamp(static_cast<float>(db), -20.0f, 0.0f);
}
```

### 5. Parameter Smoothing (line 649-651)
在 process() 函數中加入 EQ parameter smoothing:
```cpp
smoothEqLow += (eqLowDb - smoothEqLow) * smoothFactor;
smoothEqMid += (eqMidDb - smoothEqMid) * smoothFactor;
smoothEqHigh += (eqHighDb - smoothEqHigh) * smoothFactor;
```

### 6. EQ 參數設定 (line 661-680)
在 sample loop 外設定 EQ 參數 (避免不穩定):
```cpp
// Clamp EQ gains to safe range (cut-only: 0 to -20dB) and convert dB to linear gain
float clampedEqLow = clamp(smoothEqLow, -20.0f, 0.0f);
float clampedEqMid = clamp(smoothEqMid, -20.0f, 0.0f);
float clampedEqHigh = clamp(smoothEqHigh, -20.0f, 0.0f);

float eqLowGain = std::pow(10.0f, clampedEqLow / 20.0f);
float eqMidGain = std::pow(10.0f, clampedEqMid / 20.0f);
float eqHighGain = std::pow(10.0f, clampedEqHigh / 20.0f);

// Update filter coefficients once per buffer
// Low: 200Hz lowshelf, Mid: 2kHz peaking, High: 8kHz highshelf
eqLowL.setParameters(BiquadFilter::LOWSHELF, 200.0f / sampleRate, 0.707f, eqLowGain);
eqLowR.setParameters(BiquadFilter::LOWSHELF, 200.0f / sampleRate, 0.707f, eqLowGain);
eqMidL.setParameters(BiquadFilter::PEAK, 2000.0f / sampleRate, 0.707f, eqMidGain);
eqMidR.setParameters(BiquadFilter::PEAK, 2000.0f / sampleRate, 0.707f, eqMidGain);
eqHighL.setParameters(BiquadFilter::HIGHSHELF, 8000.0f / sampleRate, 0.707f, eqHighGain);
eqHighR.setParameters(BiquadFilter::HIGHSHELF, 8000.0f / sampleRate, 0.707f, eqHighGain);
```

### 7. Feedback 最大值修改 (line 494-495)
將 Feedback 最大值從 0.5 改回 0.8:
```cpp
void set_feedback(double value) {
    // Limit to 0.8 with additional safety scaling in process()
    feedbackValue = clamp(static_cast<float>(value), 0.0f, 0.8f);
}
```

## EQ 處理程式碼 (line 877-884)
EQ 處理程式碼已存在並正常運作,在 sample loop 內處理音訊:
```cpp
// 3-Band EQ - just process, parameters are set outside loop
float eqL = eqLowL.process(mixedL);
eqL = eqMidL.process(eqL);
eqL = eqHighL.process(eqL);

float eqR = eqLowR.process(mixedR);
eqR = eqMidR.process(eqR);
eqR = eqHighR.process(eqR);
```

## EQ 頻率設定
- **Low**: 200Hz (lowshelf)
- **Mid**: 2kHz (peaking)
- **High**: 8kHz (highshelf)
- **Q**: 0.707 (Butterworth response)

## 測試結果

已通過完整測試 (`test_eq_fix.py`):

1. ✓ 設定 EQ 值在有效範圍內 (0 to -20dB)
2. ✓ 邊界值測試 (0dB, -20dB)
3. ✓ 範圍限制測試 (超出範圍的值會被 clamp)
4. ✓ 音訊處理測試 (各頻段 cut 效果正確)
   - No EQ: Ratio 1.000
   - Low cut -10dB: Ratio 0.936
   - Mid cut -10dB: Ratio 0.813
   - High cut -10dB: Ratio 0.773
   - All cut -20dB: Ratio 0.443
5. ✓ Feedback 限制測試 (最大值 0.8)

## 編譯狀態
✓ 編譯成功 (無警告、無錯誤)
✓ Python 匯入測試通過
✓ 功能測試全部通過

## 檔案位置
- 原始碼: `/Users/madzine/Documents/VAV/alien4_extension.cpp`
- 編譯檔: `/Users/madzine/Documents/VAV/vav/audio/alien4.cpython-311-darwin.so`
- 測試腳本: `/Users/madzine/Documents/VAV/test_eq_fix.py`

## 注意事項
- EQ 只支援 cut (0 to -20dB),不支援 boost
- EQ 參數設定在 sample loop 外面,確保穩定性
- Feedback 最大值已改回 0.8,在 process() 中有額外的 0.8x safety scaling
