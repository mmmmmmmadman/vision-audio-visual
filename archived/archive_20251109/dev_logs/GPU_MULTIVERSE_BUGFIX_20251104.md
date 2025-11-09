# GPU Multiverse 重大 Bug 修復 - 2025-11-04

## 摘要

發現並修復 Qt OpenGL (GPU) Multiverse 渲染器的關鍵錯誤，該錯誤導致視覺輸出與 CPU 版本完全不同。

## 問題描述

使用者回報：GPU 版本的 Multiverse 渲染器視覺效果與 CPU 版本完全不同，且 region map 功能無法運作。

## 根本原因分析

### 關鍵錯誤：電壓正規化公式錯誤

**CPU 渲染器** (`vav/visual/numba_renderer.py` line 166):
```python
normalized = max(0.0, min(1.0, (waveform_val + 10.0) * 0.05 * intensity))
```

**GPU 渲染器** (`vav/visual/qt_opengl_renderer.py` line 152, 修復前):
```glsl
float normalized = clamp(abs(waveValue) * 0.05 * intensities[ch], 0.0, 1.0);
```

**關鍵差異**:
1. **CPU**: `(waveValue + 10.0) * 0.05` - 假設 waveValue 範圍為 -10V 到 +10V
2. **GPU**: `abs(waveValue) * 0.05` - 使用絕對值且缺少 `+ 10.0` 偏移

### 影響

GPU 渲染器只顯示半波整流的絕對值，而不是完整波形加上直流偏移。這導致:
- 視覺輸出亮度錯誤
- 波形形狀失真
- 與 Multiverse.cpp 原始實作不符
- 與 CPU 版本完全不同的視覺效果

## 修復方案

### 修改檔案: `vav/visual/qt_opengl_renderer.py`

**修復前** (line 149-152):
```glsl
float waveValue = texture(audio_tex, vec2(x_sample, float(ch) / 4.0)).r;
// Match Multiverse.cpp: (voltage + 10.0) * 0.05 * intensity
// Assuming waveValue is already normalized to ±10V range
float normalized = clamp(abs(waveValue) * 0.05 * intensities[ch], 0.0, 1.0);
```

**修復後** (line 149-152):
```glsl
float waveValue = texture(audio_tex, vec2(x_sample, float(ch) / 4.0)).r;
// Match Multiverse.cpp AND Numba renderer: (voltage + 10.0) * 0.05 * intensity
// waveValue is in ±10V range, normalize to 0-1
float normalized = clamp((waveValue + 10.0) * 0.05 * intensities[ch], 0.0, 1.0);
```

### 關鍵變更

1. **移除 `abs()`**: 不再使用絕對值，保留完整波形資訊
2. **加入 `+ 10.0`**: 正確地將 -10V~+10V 範圍偏移到 0~20V
3. **更新註解**: 明確指出與 Numba 渲染器和 Multiverse.cpp 的一致性

## 其他修復：Region Map 傳遞

### 修改檔案: `vav/core/controller.py`

**修復前** (lines 504-507):
```python
# Only Numba renderer supports region_map parameter
if region_map is not None and NUMBA_AVAILABLE and isinstance(self.renderer, NumbaMultiverseRenderer):
    rendered_rgb = self.renderer.render(channels_data, region_map=region_map)
else:
    rendered_rgb = self.renderer.render(channels_data)
```

**修復後** (lines 502-507):
```python
# Both Numba and Qt OpenGL renderers support region_map parameter
if region_map is not None:
    rendered_rgb = self.renderer.render(channels_data, region_map=region_map)
else:
    rendered_rgb = self.renderer.render(channels_data)
```

## 技術細節

### 電壓正規化原理

Multiverse.cpp 原始實作 (line 544):
```cpp
float normalizedVoltage = clamp((voltage + 10.0f) * 0.05f * intensity, 0.0f, 1.0f);
```

**數學原理**:
- 輸入範圍: -10V 到 +10V (Eurorack 標準)
- 加上 10.0 後: 0V 到 20V
- 乘以 0.05 (即除以 20): 0.0 到 1.0 (正規化)
- 乘以 intensity: 套用使用者強度控制

### 為什麼錯誤的公式會產生完全不同的視覺效果

**錯誤公式** `abs(waveValue) * 0.05`:
- 將負值轉為正值（半波整流）
- 失去相位資訊
- 視覺上看起來像是「脈衝」而非連續波形
- 亮度錯誤（沒有 +10.0 偏移，範圍只有 0~10 而非 0~20）

**正確公式** `(waveValue + 10.0) * 0.05`:
- 保留完整波形資訊
- 正確的電壓到亮度映射
- 與原始 Multiverse 行為一致

## 驗證清單

- [x] 修復 GPU shader 電壓正規化公式
- [x] 修復 region map 傳遞邏輯
- [x] 語法檢查通過
- [ ] 視覺輸出測試（與 CPU 版本比較）
- [ ] Region map 功能測試
- [ ] 效能測試

## 下一步

1. 執行程式並比較 GPU vs CPU 視覺輸出
2. 驗證 region map 功能正常運作
3. 確認所有 Multiverse 參數（curve, angle, intensity）正確作用

## 其他分析結果

### Ratio/Phase 不在修復範圍

**Ratio** (Pitch Shifting):
- 屬於 DSP 層級的音訊處理
- 需要 pitch buffer 和分數採樣
- 不是渲染器的責任
- Multiverse.cpp lines 286-314

**Phase** (水平偏移):
- 原始 Multiverse.cpp widget 顯示設定 `phaseOffset = 0.0f` (line 538)
- 未在原始實作中使用
- 低優先級功能

### Curve 實作已優於原版

**Multiverse.cpp** (lines 546-550):
- 無 curve 實作，只有垂直填充

**GPU 渲染器** (lines 140-147):
- 完整的 Y-based X-sampling offset
- 使用 sin 函數進行彎曲
- 比原始版本更先進

## 檔案修改記錄

### 修改檔案

1. `vav/visual/qt_opengl_renderer.py` - line 152: 修復電壓正規化公式
2. `vav/core/controller.py` - lines 502-507: 修復 region map 傳遞

### 受影響檔案（無需修改）

- `vav/visual/numba_renderer.py` - 已使用正確公式
- `Multiverse.cpp` - 參考實作

## 版本資訊

- 修復日期: 2025-11-04
- 修復版本: VAV_20251104_2200
- 修復者: Claude Code
- 問題回報: 使用者回饋視覺效果不同

---

**重要性**: 🔴 CRITICAL - 核心渲染邏輯錯誤
**影響範圍**: 所有使用 GPU 渲染器的視覺輸出
**修復難度**: ⭐ 簡單 - 單行公式修正
**測試狀態**: ⏳ 待驗證
