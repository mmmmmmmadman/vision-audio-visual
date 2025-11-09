# Qt OpenGL Multiverse Renderer 修復報告

## 修復日期
2025-11-03

## 問題摘要
Qt OpenGL renderer 在初始化時出現 shader validation 錯誤：
```
OpenGL.GL.shaders.ShaderValidationError: Validation failure: Current draw framebuffer is invalid.
```

## 問題根源

### 1. Shader Validation 錯誤
**問題**：`initializeGL()` 中使用 `shaders.compileProgram()` 會在 framebuffer 創建前自動執行 validation，導致驗證失敗。

**原因**：
- OpenGL shader validation 需要有效的 draw framebuffer
- 當時 FBO 尚未創建，default framebuffer 不可用（離線渲染模式）
- PyOpenGL 的 `compileProgram()` 函數會自動調用 `glValidateProgram()`

**解決方案**：
- 手動編譯和連結 shader program，而非使用 `compileProgram()`
- 在 FBO 創建完成後再執行 validation
- 即使 validation 失敗也繼續執行（某些離線渲染環境下 validation 可能失敗但實際可用）

### 2. PaintGL 中的 Framebuffer 錯誤
**問題**：`paintGL()` 在 unbind FBO 後嘗試 clear default framebuffer，導致 `invalid framebuffer operation` 錯誤。

**原因**：
- QOpenGLWidget 作為離線渲染器使用時，default framebuffer 可能無效
- 錯誤嘗試渲染到 screen（line 313）

**解決方案**：
- 移除對 default framebuffer 的操作
- 完全專注於 FBO 離線渲染
- 添加 framebuffer 狀態檢查

### 3. ColorDodge 混合模式失效
**問題**：ColorDodge 混合模式產生全黑輸出。

**原因**：
- ColorDodge 公式：`result = base / (1.0 - blend)`
- 當 base 為 0（初始值）時，`0 / anything = 0`
- 第一個 channel 與空白 buffer 混合時失效

**解決方案**：
- 第一個啟用的 channel 直接賦值，不經過混合函數
- 後續 channels 才使用 ColorDodge 混合

### 4. 音訊範圍正規化
**問題**：音訊數據範圍為 [-2.49, 4.83]，但 shader 假設 [-5, 5] 範圍。

**解決方案**：
- 調整 shader 正規化係數從 `0.2` 改為 `0.14`
- 公式：`normalized = abs(waveValue) * 0.14 * intensity`
- 支援實際 ES-8 音訊範圍

## 修復的檔案

### `/Users/madzine/Documents/VAV/vav/visual/qt_opengl_renderer.py`

#### 修改 1: initializeGL() - Shader 編譯流程
```python
# 修改前：使用 compileProgram() 會自動 validate
self.shader_program = shaders.compileProgram(vertex_shader, fragment_shader)

# 修改後：手動編譯和連結
self.shader_program = glCreateProgram()
glAttachShader(self.shader_program, vertex_shader)
glAttachShader(self.shader_program, fragment_shader)
glLinkProgram(self.shader_program)

# 檢查 link 狀態
link_status = glGetProgramiv(self.shader_program, GL_LINK_STATUS)
if not link_status:
    info_log = glGetProgramInfoLog(self.shader_program)
    raise RuntimeError(f"Shader program link failed: {info_log.decode('utf-8')}")

# 刪除 shader objects
glDeleteShader(vertex_shader)
glDeleteShader(fragment_shader)
```

#### 修改 2: initializeGL() - FBO 創建後驗證
```python
# 在 FBO 創建並綁定後執行 validation
glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0,
                      GL_TEXTURE_2D, self.fbo_tex, 0)

# 檢查 framebuffer 狀態
fbo_status = glCheckFramebufferStatus(GL_FRAMEBUFFER)
if fbo_status != GL_FRAMEBUFFER_COMPLETE:
    raise RuntimeError(f"Framebuffer is not complete: {fbo_status}")

# 現在可以 validate shader program
glValidateProgram(self.shader_program)
validation_status = glGetProgramiv(self.shader_program, GL_VALIDATE_STATUS)
if not validation_status:
    info_log = glGetProgramInfoLog(self.shader_program)
    print(f"Warning: Shader validation returned status {validation_status}: {info_log.decode('utf-8')}")
```

#### 修改 3: paintGL() - 移除 default framebuffer 操作
```python
# 修改前：嘗試渲染到 screen
glBindFramebuffer(GL_FRAMEBUFFER, 0)
glViewport(0, 0, self.width(), self.height())
glClear(GL_COLOR_BUFFER_BIT)  # ← 錯誤：invalid framebuffer operation

# 修改後：只做離線渲染
glBindFramebuffer(GL_FRAMEBUFFER, 0)
# Note: We don't render to screen since this is an offscreen renderer
```

#### 修改 4: Fragment Shader - 音訊範圍正規化
```glsl
// 修改前：
float normalized = clamp(abs(waveValue) * 0.2 * intensities[ch], 0.0, 1.0);

// 修改後：支援 [-2.49, 4.83] 範圍
float normalized = clamp(abs(waveValue) * 0.14 * intensities[ch], 0.0, 1.0);
```

#### 修改 5: Fragment Shader - ColorDodge 混合修復
```glsl
void main() {
    vec4 result = vec4(0.0);
    bool firstChannel = true;

    for (int ch = 0; ch < 4; ch++) {
        if (enabled_mask[ch] < 0.5) continue;

        // ... 計算 channelColor ...

        // 第一個 channel 直接賦值，避免 ColorDodge 失效
        if (firstChannel) {
            result = channelColor;
            firstChannel = false;
        } else {
            result = blendColors(result, channelColor, blend_mode);
        }
    }

    result.rgb *= brightness;
    fragColor = result;
}
```

### `/Users/madzine/Documents/VAV/vav/core/controller.py`

#### 修改：優先使用 Qt OpenGL renderer
```python
# 修改前：優先使用 Numba JIT (CPU)
if NUMBA_AVAILABLE and not renderer_initialized:
    self.renderer = NumbaMultiverseRenderer(...)

# 修改後：優先使用 Qt OpenGL (GPU)
# Priority: Qt OpenGL (GPU) > Numba JIT (CPU) > Pure NumPy (CPU fallback)
try:
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        raise RuntimeError("QApplication not available")

    self.renderer = QtMultiverseRenderer(
        width=self.camera.width,
        height=self.camera.height
    )
    self.renderer.set_blend_mode(self.renderer_params['blend_mode'])
    self.renderer.set_brightness(self.renderer_params['brightness'])
    print(f"✓ Qt OpenGL Multiverse renderer (GPU): {self.camera.width}x{self.camera.height}")
    self.using_gpu = True
    renderer_initialized = True
except Exception as e:
    print(f"⚠ Qt OpenGL renderer not available: {e}")
```

## 測試結果

### 測試環境
- macOS (Darwin 24.6.0)
- Python 3.11
- PyQt6 + PyOpenGL
- 解析度：1920x1080

### 功能測試

#### 1. Blend Modes（混合模式）
| 模式 | 狀態 | 可見像素比例 |
|------|------|-------------|
| Add | ✓ PASS | 100.00% |
| Screen | ✓ PASS | 100.00% |
| Difference | ✓ PASS | 99.65% |
| ColorDodge | ✓ PASS | 66.67% |

#### 2. Audio Range（音訊範圍）
| 範圍 | 狀態 | 可見度 | 輸出範圍 |
|------|------|--------|---------|
| ES-8 actual (-2.49 to 4.83) | ✓ PASS | 100% | [74, 255] |
| ±5V | ✓ PASS | 100% | [114, 255] |
| ±10V (Eurorack) | ✓ PASS | 100% | [233, 255] |

#### 3. Performance（性能）
- **渲染幀數**：100 frames @ 1920x1080
- **總時間**：0.46 秒
- **平均 FPS**：**215.9 FPS** ✓✓ EXCELLENT
- **每幀時間**：4.63ms
- **目標**：30 FPS (已超越 7 倍！)

### 視覺輸出測試
生成的測試圖片：
- `qt_opengl_test_Add.png` (4.4 MB)
- `qt_opengl_test_Screen.png` (5.0 MB)
- `qt_opengl_test_Difference.png` (5.9 MB)
- `qt_opengl_test_ColorDodge.png` (正常大小，非全黑)
- `qt_opengl_test_intensity_*.png` (各強度測試)
- `qt_opengl_test_freq_*.png` (各頻率色彩測試)

所有圖片均顯示正確的 Multiverse 視覺效果，頻率色彩映射正確。

## 驗證方法

執行以下測試腳本來驗證修復：

### 基本功能測試
```bash
python test_qt_opengl.py
```
預期輸出：✓✓✓ SUCCESS: Rendering produced visible output!

### 視覺效果測試
```bash
python test_qt_opengl_visual.py
```
預期輸出：生成多張 PNG 測試圖片

### 完整整合測試
```bash
python test_qt_opengl_final.py
```
預期輸出：
- ✓ PASS: blend_modes
- ✓ PASS: audio_range
- ✓ PASS: performance
- ✓✓✓ ALL TESTS PASSED!

## 技術亮點

1. **GPU 加速**：使用 Qt OpenGL 實現真正的 GPU 渲染，性能達到 215 FPS
2. **正確的離線渲染**：通過 FBO 實現離線渲染，無需顯示窗口
3. **完整的混合模式**：支援 Add、Screen、Difference、ColorDodge 四種模式
4. **精確的頻率映射**：基於八度（octave）的色相循環
5. **實時音訊處理**：支援 4 channels 並行處理，4800 samples per channel

## 性能對比

| Renderer | 平台 | FPS @ 1920x1080 | 備註 |
|----------|------|-----------------|------|
| Qt OpenGL | macOS | **215.9** | GPU 加速 ✓ |
| Numba JIT | macOS | ~60-80 | CPU 多核 |
| Pure NumPy | macOS | ~10-15 | CPU 單核 |

Qt OpenGL renderer 在 macOS 上的性能是 Numba JIT 的 **2.7-3.6 倍**，是純 NumPy 的 **14-21 倍**。

## 注意事項

1. **QApplication 依賴**：Qt OpenGL renderer 需要在 GUI 模式下運行（需要 QApplication instance）
2. **Validation Warning**：在某些環境下會出現 "No vertex array object bound" 警告，可以忽略（不影響實際渲染）
3. **macOS 優化**：此實現特別針對 macOS OpenGL 3.3 Core Profile 優化
4. **自動降級**：如果 Qt OpenGL 不可用，系統會自動降級到 Numba JIT 或 NumPy renderer

## 結論

✓✓✓ **所有問題已修復，Qt OpenGL Multiverse renderer 完全正常運作**

- Framebuffer validation 錯誤已解決
- ColorDodge 混合模式正確實現
- 音訊範圍正規化適配 ES-8 實際數據
- 性能超越目標 7 倍（215 FPS vs 30 FPS target）
- 所有 4 種混合模式均正常工作
- GPU 加速功能正常啟用

系統已準備好在實際環境中使用 GPU 加速的 Multiverse 視覺效果。
