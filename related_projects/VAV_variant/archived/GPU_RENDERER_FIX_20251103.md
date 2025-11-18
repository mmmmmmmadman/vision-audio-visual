# GPU Multiverse 渲染器修復 - 2025-11-03

## 問題總結

GPU (Qt OpenGL) 渲染器出現兩個問題：
1. **Time window 不匹配**：視覺 ratio 與原始 Multiverse.cpp 不同
2. **線條問題**：畫面出現密集垂直線條，而非連續色塊

## 修復過程

### 問題 1: Time Window 不匹配

**症狀**：
- 波形水平縮放比例與原始 VCV Rack Multiverse 不同

**診斷**：
- 原始 Multiverse.cpp 使用 50ms time window (line 317: `msPerScreen = 50.0f`)
- VAV 使用 100ms (4800 samples @ 48kHz)
- 2x 差異導致視覺 ratio 不正確

**修復**：
```python
# /Users/madzine/Documents/VAV/vav/core/controller.py line 91
# BEFORE:
self.audio_buffer_size = 4800  # ~100ms at 48kHz

# AFTER:
self.audio_buffer_size = 2400  # 50ms at 48kHz (matches Multiverse.cpp)
```

### 問題 2: 線條問題 (主要問題)

**症狀**：
- GPU 渲染器顯示密集垂直線條
- CPU (Numba) 渲染器畫面正常
- 線條隨波形滾動

**診斷過程**：
1. 確認 CPU 版本正常 → 問題在 GPU 端
2. 檢查 texture filtering → GL_LINEAR 設定正確
3. 檢查 resampling → 已使用 linear interpolation
4. **找到根本原因**：texture 數據上傳時使用了 `.T` 轉置

**根本原因**：
```python
# qt_opengl_renderer.py line 541-542 (錯誤版本)
glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, self.render_width, 4,
               GL_RED, GL_FLOAT, self.audio_data.T)  # ← .T 轉置破壞了記憶體布局
```

**問題分析**：
- `audio_data` shape: `(4, 1920)` - 4 channels, 1920 samples each
- C-contiguous 記憶體布局：`[ch0_s0, ch0_s1, ..., ch0_s1919, ch1_s0, ..., ch3_s1919]`
- 這正是 OpenGL 期望的 row-major 布局！
- 轉置 `.T` 會破壞記憶體連續性，導致 OpenGL 讀取到錯誤的 stride
- Metal backend 在讀取非連續記憶體時會產生線條 artifacts

**修復**：
```python
# /Users/madzine/Documents/VAV/vav/visual/qt_opengl_renderer.py lines 538-544
# Update audio texture
# NOTE: audio_data is (4, 1920) C-contiguous, which matches OpenGL row-major layout
# Row 0 = Channel 0, Row 1 = Channel 1, etc. - NO transpose needed!
glActiveTexture(GL_TEXTURE0)
glBindTexture(GL_TEXTURE_2D, self.audio_tex)
glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, self.render_width, 4,
               GL_RED, GL_FLOAT, self.audio_data)  # 移除 .T
```

## 修改的文件

1. **controller.py** (line 91)
   - 修改 audio buffer size: 4800 → 2400 samples

2. **qt_opengl_renderer.py** (lines 538-544)
   - 移除 texture upload 的 `.T` 轉置
   - 添加註解說明記憶體布局

## 測試結果

### 修復前
- CPU 版本：正常
- GPU 版本：密集垂直線條

### 修復後
- CPU 版本：正常
- GPU 版本：正常（與 CPU 版本一致）

## 技術要點

### OpenGL Texture 記憶體布局
- OpenGL 期望 row-major 布局
- `(4, 1920)` C-contiguous array 已經是正確的布局
- Row 0 = Channel 0, Row 1 = Channel 1, etc.
- 不需要轉置

### NumPy Array 記憶體
```python
# C-contiguous (4, 1920)
[ch0_s0, ch0_s1, ..., ch0_s1919,  # Row 0
 ch1_s0, ch1_s1, ..., ch1_s1919,  # Row 1
 ch2_s0, ch2_s1, ..., ch2_s1919,  # Row 2
 ch3_s0, ch3_s1, ..., ch3_s1919]  # Row 3

# 轉置後 .T 會破壞連續性
# Metal backend 讀取非連續記憶體時產生 artifacts
```

### Shader Sampling
```glsl
// Pass 1 Fragment Shader (正確版本)
float y_audio = (float(current_channel) + 0.5) / 4.0;  // 0.125, 0.375, 0.625, 0.875
float waveValue = texture(audio_tex, vec2(x_sample, y_audio)).r;
```

## 教訓

1. **記憶體布局很重要**：OpenGL/Metal 對記憶體連續性敏感
2. **不要亂轉置**：確認 OpenGL 期望的布局後再決定是否需要轉置
3. **CPU vs GPU 測試**：當 CPU 正常但 GPU 有問題時，通常是記憶體布局或 API 使用問題
4. **Linear interpolation 不是萬能的**：texture filtering 正確，但 data upload 錯誤仍會有問題

## 性能

修復後性能與之前相同：
- GPU 渲染：30-60 FPS @ 1920x1080
- 無額外 overhead
- Metal backend 正常工作

---

**修復日期**: 2025-11-03
**狀態**: ✅ 已解決
**修復類型**: Memory layout fix (removed unnecessary transpose)
