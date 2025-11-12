# VAV 系統變更日誌

---

## [2025-11-12] 色彩方案與混合模式連續化改進

### 新增功能

**1. 色彩方案連續調整**
- 將色彩方案下拉選單改為連續性滑桿（Fader）
- 支援三種方案之間的平滑漸變混合：
  - 0.0-0.5: Quad90（90度四色）→ Tri+Contrast（三色+對比）
  - 0.5-1.0: Tri+Contrast → Tri+Between（三色+中間色）
- 移除色彩方案標籤，保持介面簡潔
- 支援 MIDI Learn 即時控制

**2. Blend 模式連續調整**
- 將 Blend 模式下拉選單改為連續性滑桿
- 支援四種混合模式之間的平滑漸變：
  - 0.0-0.33: Add → Screen
  - 0.33-0.66: Screen → Difference
  - 0.66-1.0: Difference → Color Dodge
- 保留 "Blend" 標籤
- 支援 MIDI Learn 即時控制

**3. Shader 實作漸變混合邏輯**
- 色彩方案：計算三種方案的 HSV 值，使用 mix() 在 HSV 空間插值
- Blend 模式：計算四種模式的結果，使用 mix() 在 RGB 空間插值
- 參數類型從 int 改為 float (0.0-1.0)

### 修改內容

**GUI (compact_main_window.py)**
- 移除 color_scheme_combo 和 blend_mode_combo
- 新增 color_scheme_slider 和 blend_mode_slider
- 範圍：0-100，映射到 0.0-1.0
- 預設值：color_scheme=50 (Tri+Contrast), blend_mode=0 (Add)

**Controller (controller.py)**
- set_renderer_blend_mode(): 參數從 int 改為 float
- set_color_scheme(): 參數從 int 改為 float
- 移除 blend mode 名稱索引，改為顯示數值

**Renderer (qt_opengl_renderer.py)**
- blend_mode 和 color_scheme 從 int 改為 float
- getChannelColor(): 實作三種色彩方案的漸變混合
- blendColors(): 實作四種混合模式的漸變混合
- Shader uniform 類型更新為 float

### 視覺效果改進

**1. Multiverse 最低亮度調整**
- 從 0.2 (20%) 降低到 0.1 (10%)
- 減少過度飽和，讓 blend 模式效果更明顯
- 避免多層疊加時快速變白

**2. Base Hue 範圍調整**
- 最大值從 360 改為 333
- 轉換公式：value / 333.0

**3. Camera Mix 範圍限制**
- 最大值從 100 改為 30 (0.0-0.3)
- 降低敏感度，避免 camera 過亮
- 標籤顯示精度提升到小數點後兩位

### Region Map 與 Blend 模式整合

**問題修正**
- Region Map 開啟時，每個像素只有一個通道，無法展現 blend 效果
- 修改邏輯：不屬於 region 的通道直接跳過 (continue)，而非設為黑色
- Camera/SD 畫面參與 blend 混合，作為第二個混合對象
- 確保 blend 模式在 region map 模式下仍然有效

**實作細節**
- Shader 中提前過濾 region（第 229-231 行）
- Camera/SD 使用相同的 blendColors 函數
- Camera mix 控制混合強度

### 效能優化

**SD Img2Img 加速**
- Resize 演算法：LANCZOS → BILINEAR
- 輸入 resize (512x512): 改用 BILINEAR
- 輸出 resize (1280x720): 改用 BILINEAR
- 速度提升：0.45-0.47s → 0.39s (約快 60-80ms)
- 當前 fps: ~2.56 fps

### 技術細節

**Shader 漸變混合實作**
```glsl
// 色彩方案混合
vec3 hsv_result;
if (color_scheme < 0.5) {
    float t = color_scheme * 2.0;
    hsv_result = mix(scheme1_hue, scheme2_hue, t);
} else {
    float t = (color_scheme - 0.5) * 2.0;
    hsv_result = mix(scheme2_hue, scheme3_hue, t);
}

// Blend 模式混合
if (mode < 0.33) {
    float t = mode / 0.33;
    result = mix(add_result, screen_result, t);
} else if (mode < 0.66) {
    float t = (mode - 0.33) / 0.33;
    result = mix(screen_result, diff_result, t);
} else {
    float t = (mode - 0.66) / 0.34;
    result = mix(diff_result, dodge_result, t);
}
```

### 檔案修改
- vav/gui/compact_main_window.py: GUI 介面改為滑桿
- vav/core/controller.py: 參數類型更新、blend mode 顯示調整
- vav/visual/qt_opengl_renderer.py: Shader 漸變混合實作
- vav/visual/sd_img2img_process.py: Resize 演算法優化

### 已知限制
- SD 速度受 GPU 和模型限制，目前約 2.5 fps
- 要達到 20 fps 需要更激進的優化（降低解析度、TensorRT 等）

---

## [2025-11-11] Region Map 開關失效問題修復

### 問題修復

**Region Map 無法關閉的 bug**
- 使用者反應開關 Region Map checkbox 時畫面沒有變化
- 經診斷發現 controller.py:599 預設值設為 True 導致 region map 無法關閉
- 即使 use_region_rendering=False 仍會傳 camera_frame 給 renderer

**修正內容**
- controller.py:599 use_gpu_region 預設值改為 False
- controller.py:616 CPU region mode 明確設為 False
- 確保 region map 關閉時不會傳遞 region 相關資料給 renderer

**測試確認**
- Region Map ON 正常顯示分區效果
- Region Map OFF 正常顯示全畫面混合效果
- 開關切換即時生效

---

## [2025-11-11] Region Map 診斷與除錯工具添加

### 問題診斷

**Region Map 開關失效問題調查**
