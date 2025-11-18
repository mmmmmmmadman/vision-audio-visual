# GPU Multiverse Renderer 重寫計劃

**日期**: 2025-11-03
**狀態**: 準備重寫
**方案**: Multi-Pass 架構

---

## 📋 背景

### 問題描述

現有的 Qt OpenGL GPU renderer 有 **15 個錯誤**，導致視覺效果與 CPU 版本完全不同（"醜，完全與原本的效果不一樣"）。

### 錯誤清單

#### 🔴 Critical Errors (必須修復)

1. **Error #10**: Voltage normalization 使用 `abs(waveValue) * 0.14` 而非 `(waveValue + 10.0) * 0.05`
   - 影響：整個波形視覺化錯誤
   - 位置：line 150

2. **Error #11**: Region map 在 rotation 之前採樣
   - 影響：region map 無法跟隨 rotation
   - 位置：lines 117-121

3. **Error #13**: Curve 在 rotation 之後應用（順序錯誤）
   - 影響：curve + rotation 同時啟用時效果完全錯誤
   - 位置：lines 132-147
   - **這是架構層級問題**

4. **Error #14**: Curve 計算使用 rotated 座標而非 original 座標
   - 影響：curve 效果方向錯誤
   - 位置：line 143

5. **Error #3**: Rotation 缺少 scale compensation
   - 影響：rotation 時出現黑邊
   - 位置：lines 132-138

#### 🟡 High Priority Errors

6. **Error #2**: Texture Y 座標採樣錯誤 (`float(ch) / 4.0` 應為 `(float(ch) + 0.5) / 4.0`)
7. **Error #4**: Hue 輸出範圍 0-1 而非 0-360
8. **Error #5**: HSV to RGB 算法不同
9. **Error #6**: Rotation 方向可能相反

#### 🟢 Medium Priority Errors

10. **Error #12**: Region map 四捨五入錯誤
11. **Error #15**: Color Dodge 多餘邊界檢查
12. **Error #9**: Audio texture Y 座標採樣（同 Error #2）

### 系統整合問題

- **Issue #2**: Region map 未傳遞給 Qt OpenGL renderer（controller.py）
- **Issue #4**: SD img2img 色彩空間轉換效率低

---

## 🎯 解決方案：Multi-Pass 重寫

### 為什麼選擇重寫而非修復？

| 項目 | 修復現有版本 | Multi-Pass 重寫 |
|------|-------------|----------------|
| 工作量 | 修改 15 處錯誤 | 重寫 ~200 行 shader |
| 風險 | 高（錯誤互相糾纏） | 中（邏輯清晰） |
| 架構問題 | 難以解決 | 從設計解決 |
| 測試難度 | 高 | 中（可逐步驗證） |
| 可維護性 | 低（補丁堆疊） | 高（從頭設計） |
| 完成信心 | 60% | 90% |

**結論：重寫是更好的選擇。**

---

## 🏗️ Multi-Pass 架構設計

### Pass 1: Channel Rendering (應用 Curve)

**目的**: 渲染每個 channel 的原始視覺效果，應用 curve bending

**輸入**:
- Audio texture (1920×4, GL_R32F)
- Frequency values (vec4)
- Intensity values (vec4)
- Curve values (vec4)
- Enabled mask (vec4)

**處理流程**:
```glsl
for each pixel (x, y):
    for each channel:
        // 1. Calculate original coordinates
        x_normalized = x / width
        y_normalized = y / height
        y_from_center = (y_normalized - 0.5) * 2.0

        // 2. Apply curve in original space
        x_sample = x_normalized
        if (curve > 0.001):
            bend_shape = sin(x_normalized * PI)
            bend_amount = y_from_center * bend_shape * curve * 2.0
            x_sample = fract(x_sample + bend_amount)

        // 3. Sample audio (CORRECT Y coordinate)
        waveValue = texture(audio_tex, vec2(x_sample, (float(ch) + 0.5) / 4.0)).r

        // 4. Voltage normalization (CORRECT formula)
        normalized = clamp((waveValue + 10.0) * 0.05 * intensity, 0.0, 1.0)

        // 5. Get hue from frequency (0-360 degrees)
        hue = getHueFromFrequency(frequency) * 360.0

        // 6. HSV to RGB (match C++ algorithm)
        color = hsv2rgb(vec3(hue / 360.0, 1.0, normalized))
```

**輸出**: 4 個 temp FBOs (每個 channel 一個)

**參考**: `numba_renderer.py` lines 139-173

---

### Pass 2: Rotation (應用 Angle)

**目的**: 對每個 channel 的渲染結果應用 rotation（with scale compensation）

**輸入**:
- 4 個 temp FBOs (from Pass 1)
- Angle values (vec4)

**處理流程**:
```glsl
for each channel:
    for each pixel (x, y):
        // 1. Calculate scale compensation
        rad = radians(angle)
        absCosA = abs(cos(rad))
        absSinA = abs(sin(rad))
        scaleX = (width * absCosA + height * absSinA) / width
        scaleY = (width * absSinA + height * absCosA) / height
        scale = max(scaleX, scaleY)

        // 2. Apply rotation with scale
        uv = (x, y) / (width, height)
        centered = uv - 0.5
        centered /= scale  // Apply scale BEFORE rotation
        rotated = rotate(centered, angle)
        uv_rotated = rotated + 0.5

        // 3. Sample from temp FBO
        if (uv_rotated in bounds):
            color = texture(temp_fbo[ch], uv_rotated)
        else:
            color = vec4(0.0)  // Black outside bounds
```

**輸出**: 4 個 rotated FBOs

**參考**:
- C++ `Multiverse.cpp` lines 559-575
- `numba_renderer.py` line 366

---

### Pass 3: Blending (應用 Region Map)

**目的**: 混合所有 channels，應用 blend mode 和 region map

**輸入**:
- 4 個 rotated FBOs (from Pass 2)
- Region map texture (H×W, GL_R8)
- Blend mode (int)
- Brightness (float)
- use_region_map (bool)

**處理流程**:
```glsl
for each pixel (x, y):
    result = vec4(0.0)
    firstChannel = true

    // Check region map ONCE per pixel (using final coordinates)
    currentRegion = -1
    if (use_region_map):
        regionVal = texture(region_tex, (x, y) / (width, height)).r
        currentRegion = int(regionVal * 255.0 + 0.5)  // Proper rounding

    for each channel:
        if (!enabled[ch]) continue
        if (use_region_map && currentRegion != ch) continue

        // Sample from rotated FBO
        channelColor = texture(rotated_fbo[ch], (x, y) / (width, height))

        // Apply blend mode
        if (firstChannel):
            result = channelColor
            firstChannel = false
        else:
            result = blend(result, channelColor, blend_mode)

    // Apply brightness
    result *= brightness
    result = clamp(result, 0.0, 1.0)
```

**輸出**: Final blended result

**參考**: `numba_renderer.py` lines 363-379

---

## 📐 Shader 程式碼結構

### 共用函數（所有 passes 使用）

```glsl
// Frequency to Hue (0-360 degrees)
float getHueFromFrequency(float freq) {
    freq = clamp(freq, 20.0, 20000.0);
    const float baseFreq = 261.63;
    float octavePosition = fract(log2(freq / baseFreq));
    if (octavePosition < 0.0) octavePosition += 1.0;
    return octavePosition * 360.0;  // 0-360 degrees
}

// HSV to RGB (C++ sector-based algorithm)
vec3 hsv2rgb(vec3 c) {
    float h = c.x * 360.0;  // Convert to degrees
    float s = c.y;
    float v = c.z;

    // 6-sector algorithm (match C++ version)
    float C = v * s;
    float X = C * (1.0 - abs(mod(h / 60.0, 2.0) - 1.0));
    float m = v - C;

    vec3 rgb;
    if (h < 60.0) rgb = vec3(C, X, 0.0);
    else if (h < 120.0) rgb = vec3(X, C, 0.0);
    else if (h < 180.0) rgb = vec3(0.0, C, X);
    else if (h < 240.0) rgb = vec3(0.0, X, C);
    else if (h < 300.0) rgb = vec3(X, 0.0, C);
    else rgb = vec3(C, 0.0, X);

    return rgb + m;
}

// Rotation matrix
vec2 rotate(vec2 pos, float angle) {
    float rad = radians(angle);
    float cosA = cos(rad);
    float sinA = sin(rad);
    return vec2(
        pos.x * cosA - pos.y * sinA,
        pos.x * sinA + pos.y * cosA
    );
}

// Blend modes
vec3 blendAdd(vec3 base, vec3 blend) {
    return min(base + blend, vec3(1.0));
}

vec3 blendScreen(vec3 base, vec3 blend) {
    return vec3(1.0) - (vec3(1.0) - base) * (vec3(1.0) - blend);
}

vec3 blendDifference(vec3 base, vec3 blend) {
    return abs(base - blend);
}

vec3 blendColorDodge(vec3 base, vec3 blend) {
    vec3 result;
    for (int i = 0; i < 3; i++) {
        if (blend[i] >= 0.999) {
            result[i] = 1.0;
        } else {
            result[i] = min(1.0, base[i] / max(0.001, 1.0 - blend[i]));
        }
    }
    return result;
}

vec3 blend(vec3 base, vec3 blend, int mode) {
    if (mode == 0) return blendAdd(base, blend);
    else if (mode == 1) return blendScreen(base, blend);
    else if (mode == 2) return blendDifference(base, blend);
    else return blendColorDodge(base, blend);
}
```

---

## 🔧 實作步驟

### 階段 1: 備份和準備
- [x] 備份現有 `qt_opengl_renderer.py` 為 `qt_opengl_renderer_old.py`
- [x] 創建新的 `qt_opengl_renderer.py`
- [x] 保留 Qt OpenGL 框架程式碼（class 定義、初始化、texture upload）

### 階段 2: 實作 Pass 1 (Channel Rendering)
- [ ] 創建 Pass 1 vertex shader
- [ ] 創建 Pass 1 fragment shader
- [ ] 實作 curve effect
- [ ] 實作 voltage normalization (正確公式)
- [ ] 實作 frequency to hue (0-360)
- [ ] 實作 HSV to RGB (C++ algorithm)
- [ ] 創建 4 個 temp FBOs
- [ ] 測試：單 channel 無 curve 渲染

### 階段 3: 實作 Pass 2 (Rotation)
- [ ] 創建 Pass 2 vertex shader
- [ ] 創建 Pass 2 fragment shader
- [ ] 實作 scale compensation
- [ ] 實作 rotation transform
- [ ] 創建 4 個 rotated FBOs
- [ ] 測試：單 channel 有 rotation 渲染

### 階段 4: 實作 Pass 3 (Blending)
- [ ] 創建 Pass 3 vertex shader
- [ ] 創建 Pass 3 fragment shader
- [ ] 實作 4 種 blend modes
- [ ] 實作 region map filtering
- [ ] 實作 brightness adjustment
- [ ] 測試：多 channel blend

### 階段 5: 整合和測試
- [ ] 整合三個 passes 到 `render()` method
- [ ] 測試：curve + rotation 同時啟用
- [ ] 測試：region map + rotation
- [ ] 測試：與 CPU 版本視覺對比
- [ ] 性能測試（確保 30+ FPS）

### 階段 6: Controller 整合
- [ ] 修改 `controller.py` 啟用 region map 傳遞給 Qt OpenGL
- [ ] 測試：完整系統測試
- [ ] 文件更新

---

## 📊 驗證計劃

### 功能驗證（與 CPU 版本對比）

#### Test Case 1: Basic Rendering (無 curve, 無 rotation)
- 輸入：單一 channel, intensity=1.0, frequency=440Hz
- 預期：垂直彩色條紋
- 驗證：顏色和亮度與 CPU 版本一致

#### Test Case 2: Curve Effect
- 輸入：單一 channel, curve=0.5
- 預期：波形彎曲（Y 軸方向）
- 驗證：彎曲方向和幅度與 CPU 版本一致

#### Test Case 3: Rotation Effect
- 輸入：單一 channel, angle=45°
- 預期：旋轉 45 度，無黑邊
- 驗證：旋轉方向和 scale 與 CPU 版本一致

#### Test Case 4: Curve + Rotation
- 輸入：單一 channel, curve=0.5, angle=45°
- 預期：先彎曲後旋轉
- 驗證：最終效果與 CPU 版本一致 ⚠️ **關鍵測試**

#### Test Case 5: Multi-Channel Blending
- 輸入：4 channels, blend mode=Add
- 預期：4 個 channel 疊加
- 驗證：顏色混合與 CPU 版本一致

#### Test Case 6: Region Map
- 輸入：4 channels, region map enabled
- 預期：每個 channel 只在指定 region 渲染
- 驗證：region 分布與 CPU 版本一致

#### Test Case 7: Region Map + Rotation
- 輸入：4 channels, region map enabled, angle=30°
- 預期：region map 跟隨 rotation
- 驗證：region 在 rotation 後正確 ⚠️ **關鍵測試**

---

## 🎯 成功標準

### 視覺一致性
- ✅ 所有 7 個 test cases 通過
- ✅ 與 CPU 版本視覺對比無明顯差異
- ✅ 用戶確認「效果與原本的 CPU 版本一樣」

### 性能要求
- ✅ 1920×1080 維持 30+ FPS
- ✅ SD img2img 啟用時不影響 Multiverse FPS
- ✅ 無明顯延遲或卡頓

### 功能完整性
- ✅ 所有 CPU 版本功能都支援（curve, angle, region map, 4 blend modes）
- ✅ Region map 可以傳遞給 Qt OpenGL renderer
- ✅ 所有 GUI 參數都有效

---

## 📚 參考文件

### 核心參考
1. **`numba_renderer.py`** - 正確的 CPU 實作（主要參考）
2. **`Multiverse.cpp`** - 原始 VCV Rack C++ 實作（次要參考）
3. **`qt_opengl_renderer_old.py`** - 現有 GPU 實作（錯誤參考，避免重複錯誤）

### 關鍵程式碼位置

#### Numba CPU 版本 (`numba_renderer.py`)
- Voltage normalization: line 166
- Frequency to hue: line 293-304
- HSV to RGB: line 271-289
- Curve effect: line 149-155
- Per-pixel rendering: line 139-173
- Rotation: line 366
- Blend modes: line 183-228
- Region map: line 370-379

#### C++ 原始版本 (`Multiverse.cpp`)
- Voltage normalization: line 544
- Frequency to hue: line 388-398
- HSV to RGB: line 516-532
- Rotation with scale: line 559-575

---

## ⚠️ 常見陷阱（避免重複錯誤）

1. **❌ 不要使用 `abs(waveValue)`** - 應該是 signed conversion
2. **❌ 不要在 rotation 後應用 curve** - 順序：curve → rotation → blend
3. **❌ 不要在 rotation 前檢查 region map** - 應該在最終位置檢查
4. **❌ 不要忘記 texture Y 座標的 +0.5** - 應該是 `(ch + 0.5) / 4.0`
5. **❌ 不要忘記 rotation 的 scale compensation** - 避免黑邊
6. **❌ 不要輸出 hue 0-1** - 應該是 0-360 度（內部可以用 0-1，但要注意轉換）
7. **❌ 不要在 Color Dodge 中額外檢查 c1 <= 0.001** - 應該直接計算公式

---

## 🚀 預期效能

### 理論分析

**Single Pass (現有錯誤版本):**
- 1 pass × 1920×1080 = ~2M pixels

**Multi-Pass (新版本):**
- Pass 1: 4 renders × 1920×1080 = ~8M pixels
- Pass 2: 4 renders × 1920×1080 = ~8M pixels
- Pass 3: 1 render × 1920×1080 = ~2M pixels
- **Total: ~18M pixels** (9x more)

**但實際效能：**
- GPU 高度並行化
- 每個 pass 的 shader 都比較簡單
- FBO 切換開銷小
- 預期只慢 2-3 倍
- **仍然比 CPU Numba 快 5-10 倍**

### 實測目標

- 1920×1080 @ 30+ FPS ✅
- 與 SD img2img 同時運行無衝突 ✅
- CPU 使用率 < 50% ✅

---

## 📝 文件更新

重寫完成後需要更新的文件：

1. **README.md**
   - 更新 "Multiverse Visual Engine" 章節
   - 說明 Multi-Pass GPU 架構

2. **CHANGELOG.md**
   - 新增 "2025-11-03: GPU Multiverse Multi-Pass Rewrite"
   - 列出所有修復的錯誤

3. **GUI_CONTROLS.md**
   - 確認 Region Map 控制項說明正確

4. **SD_FPS_ISSUE_RESOLVED.md**
   - 更新 GPU renderer 相關說明

5. **創建新文件：GPU_MULTIVERSE_REWRITE_COMPLETED.md**
   - 記錄重寫過程
   - 測試結果
   - 性能對比

---

## ✅ Agents 任務分配

### Agent 1: 重寫實作
**任務**: 執行重寫計劃，實作 Multi-Pass GPU renderer

**工作內容**:
1. 備份現有檔案
2. 實作 Pass 1, 2, 3 shaders
3. 整合到 Qt OpenGL 框架
4. 基本功能測試
5. 修改 controller.py 啟用 region map

**輸出**:
- 新的 `qt_opengl_renderer.py`
- 測試報告

### Agent 2: 驗證監控
**任務**: 驗證新版本與 CPU 版本功能一致性

**工作內容**:
1. 監控 Agent 1 的實作進度
2. 執行 7 個 test cases
3. 視覺對比 GPU vs CPU
4. 性能測試
5. 找出任何不一致之處

**輸出**:
- 驗證報告
- 錯誤清單（如果有）
- 視覺對比截圖（如果需要）

---

**狀態**: ✅ 計劃完成，準備開始實作
**預計完成時間**: 2-3 小時
**風險等級**: 低（架構清晰，參考完整）
