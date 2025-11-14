# VAV 系統變更日誌

---

## [2025-11-14] Alien4 參數優化與 Seq1 控制整合

### Alien4 Poly 隨機分布優化
- **隨機 Speed 範圍擴大**: -2.0~+2.0 擴大到 -4.0~+4.0
- **Redistributive 觸發邏輯調整**:
  - Scan 改變: 觸發 redistributeVoices (支援 Seq1 控制)
  - Len 改變: 不觸發 redistributeVoices (保持穩定性)
  - Poly 改變: 觸發 redistributeVoices (原有功能)

### Seq1 控制 Alien4 Scan
- **即時控制**: Seq1 電壓 (0-1V) 直接對應 Alien4 Scan 位置
- **GUI 同步顯示**: Scan slider 即時顯示 Seq1 控制值
  - 使用 blockSignals 防止回饋迴路
  - 透過 cv_values[4] 讀取 seq1_value

### EQ 功能調整
- **Cut-only 模式**: 三頻段 EQ 改為只支援衰減
  - Low: 200Hz lowshelf, 0 到 -20dB
  - Mid: 2kHz peak, 0 到 -20dB
  - High: 8kHz highshelf, 0 到 -20dB
- **GUI 範圍更新**: Slider 範圍從 -20~+20 改為 -20~0

### Feedback 參數調整
- **最大值**: 從 0.5 改回 0.8
- **GUI 範圍**: Slider 0-80 對應 0.0-0.8
- **安全係數**: 保留 0.8x safety scaling

### Delay Time Smoothing 增強
- **Smoothing 係數**: 從 0.2 降到 0.05 (變化速度降為 1/4)
- **目的**: 防止快速調整 Delay Time 時產生破音

### 修改檔案
- `alien4_extension.cpp` - EQ cut-only, feedback 0.8, delay smoothing, redistribution 邏輯
- `vav/audio/audio_process.py` - Seq1 控制 Scan
- `vav/gui/compact_main_window.py` - EQ/Feedback slider 範圍, Scan GUI 同步

---

## [2025-11-13] 輪廓掃描變速系統與 CV 輸出優化

### 變速掃描系統
- **曲率感應變速掃描**：十字在輪廓線上移動時根據曲率動態調整速度
  - 直線段加速至 4 倍速
  - 彎道減速至 0.33 倍速
  - 使用指數映射增強曲率敏感度 (平方根)
  - 總循環時間保持在設定的 scan_time

- **速度權重計算**：
  - 計算每個點的曲率值 (0-1)
  - 增強曲率 = curvature^0.5
  - 權重範圍 0.25-3.0 對應速度 4x-0.33x
  - 使用累積時間映射確保精確時間分配

### SEQ1/2 輸出重新設計
- **改為距離 Anchor 輸出**：
  - SEQ1: X 座標到 Anchor 的距離 (0-10V)
  - SEQ2: Y 座標到 Anchor 的距離 (0-10V)

- **Range 控制放大倍數 (指數映射)**：
  - Range 1% → 8 倍放大
  - Range 120% → 2 倍放大
  - 使用反向指數曲線讓前半段快速降低
  - 輸出限制在 0-10V

### Envelope 觸發邏輯優化
- **ENV1**: X 到 Anchor 距離 > Y 到 Anchor 距離時觸發
- **ENV2**: Y 到 Anchor 距離 > X 到 Anchor 距離時觸發
- **ENV3**: 加速瞬間觸發 (速度權重降低 > 0.3)
- **ENV4**: 減速瞬間觸發 (速度權重增加 > 0.3)
- 四個 Envelope 都有 retrigger 保護

### 技術細節
- 曲率計算使用前後 2 點窗口
- 速度閾值 0.3 避免微小變化誤觸發
- 變速系統降級機制：無曲率數據時退回等速掃描

### 修改檔案
- `vav/cv_generator/contour_scanner.py` - 變速掃描、SEQ 輸出、ENV 觸發邏輯

---

## [2025-11-13] UI Layout 重構與視覺預覽功能

### UI Layout 完全重構
- **修正跨列對齊問題**：從 QGridLayout 改為 5 個獨立的 QVBoxLayout
  - 每個 column 獨立管理自己的控制項
  - 消除跨列高度干擾問題
  - 新增 `_create_control_row()` helper 確保一致的 label+control 佈局
  - 固定 label 寬度為 80px (LABEL_WIDTH) 確保 slider 對齊

- **優化視窗高度**：初始高度從 480px 降為 420px
  - 消除底部空白
  - 更好地符合內容大小

- **統一控制項高度**：所有控制項標準化為 16px 高度
  - Timer 按鈕提升至 24px 以改善可用性
  - 一致的垂直間距（控制項間 8px）

- **Multiverse slider 對齊修正**：修正 color scheme slider 位置
  - 在 checkbox 後添加 9px spacing 對齊其他 sliders
  - Column 2 所有 sliders 現在完美對齊

### 視覺預覽功能
- **新增 VisualPreviewWidget** (`vav/gui/visual_preview_widget.py`)
  - 在 CV Meter 視窗顯示主視覺輸出
  - 固定大小：273×153（與 Anchor XY Pad 相同）
  - 使用 texture 共享，CPU/GPU 負擔極小
  - 修正 RGB 顏色轉換確保正確顯示

- **更新 CV Meter Window layout**
  - Anchor XY Pad 與 Visual Preview 並排顯示
  - 使用 QHBoxLayout 水平排列
  - 視窗寬度維持 600px

### CV Overlay 控制
- **新增 CV Overlay checkbox**
  - 位於 Column 1 Track 4 vol 下方
  - 可切換主視覺上的 CV 數值顯示
  - 不影響輪廓線和圓圈顯示
  - 預設：啟用

### Audio Processing 修正
- **Sample-accurate CV output**
  - 修正 CV 輸出為逐 sample 寫入，而非填滿整個 buffer
  - Env 輸出現在正確顯示 inactive 時為 0V
  - 正確的 0-1 範圍映射到 0-10V (ES-8)

### 預設參數調整
- **Reverb Room**: 0.50 → 1.00 (最大值)
- **Reverb Damp**: 0.40 → 1.00 (最大值)
- **Reverb Decay**: 0.60 → 0.80 (80%)
- **Delay Time R**: 250ms → 300ms
- **Grain Size**: 0.30 → 0.50 (50%)

### 修改檔案
- `vav/gui/compact_main_window.py` - 主要 layout 重構
- `vav/gui/cv_meter_window.py` - 新增視覺預覽
- `vav/gui/visual_preview_widget.py` - 新 widget（新建）
- `vav/gui/meter_widget.py` - 文件更新
- `vav/core/controller.py` - CV overlay 控制
- `vav/audio/audio_process.py` - Sample-accurate CV 輸出
- `vav/visual/qt_opengl_renderer.py` - CV overlay 條件渲染

### 技術改進
- 更好的關注點分離（獨立 column layouts）
- 一致的 UI 元素大小與間距
- 減少 audio callback 的記憶體配置
- 主視窗與預覽間更有效率的 frame 共享

---

## [2025-11-12] GUI 佈局優化與錯誤修正

### GUI 改進

**1. SD 區塊垂直間距修正**
- 修正 SD Prompt QTextEdit 影響 grid 行高的問題
- 為 SD Prompt 設定 `QSizePolicy.Fixed` 避免影響下方 sliders 間距
- SD 區塊 sliders (Steps, Strength, Guidance, Gen Interval) 現在與 Multiverse sliders 使用相同垂直間距
- 檔案：`vav/gui/compact_main_window.py:503`

**2. Anchor XY Pad 移動到 CV Meters 視窗**
- 將 Anchor XY Pad 從主控制視窗移至獨立的 CV Meters 視窗
- CV Meters 視窗高度從 210 增加到 370 (增加 160px)
- 完整保留 MIDI Learn 功能：
  - Anchor X/Y 參數註冊
  - Y 軸反轉邏輯 (MIDI 0-100 → GUI 100-0)
  - 右鍵選單支援 MIDI Learn X/Y、清除映射
- `position_changed` signal 正常連接到 controller
- Range slider 更新 XY Pad 的 ROI 圓圈顯示
- 檔案：
  - `vav/gui/cv_meter_window.py`: 新增 `setup_midi_learn()` 方法
  - `vav/gui/compact_main_window.py`: 移除主視窗 XY Pad，連接到 CV Meter Window

### Bug 修正

**LFO Pattern IndexError 修正**
- 問題：`_update_lfo()` 在初始化過程中可能存取未生成的 patterns
- 錯誤：`IndexError: list index out of range` at `contour_scanner.py:790`
- 解決：在 `_update_lfo()` 加入防禦性檢查
- 檢查 `len(self.lfo_patterns) != 8` 時立即重新生成 patterns
- 避免初始化過程的競態條件
- 檔案：`vav/cv_generator/contour_scanner.py:783-786`

### 技術細節

**QSizePolicy 修正**
```python
self.sd_prompt_edit.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
```
- 防止 40px 高的 TextEdit 影響 QGridLayout 的行高分配
- 確保所有 slider 行使用統一的垂直間距 (10px)

**CV Meter Window MIDI 整合**
```python
def setup_midi_learn(self, midi_learn):
    self.midi_learn = midi_learn
    # 註冊 anchor_x, anchor_y 參數
    # 設定 context menu 與 callbacks
```

**LFO 防禦性檢查**
```python
if len(self.lfo_patterns) != 8:
    self._generate_lfo_patterns()
    return
```

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
