# 2025-11-03 版本 GUI 架構與 Multiverse 功能分析 - 執行摘要

## 快速回答

### 1. GUI 應該如何組織？

**正確的結構**：
```
主窗口 (1400×800)
├─ 控制按鈕行
├─ Splitter (40:60)
│  ├─ Scope (5 通道波形)
│  └─ Controls Grid (6 列 × N 行)
│      ├─ Column 1: CV Source ✓ (ENV衰減, SEQ設定, 邊緣檢測)
│      ├─ Column 2: Mixer
│      ├─ Column 3: Multiverse Main
│      ├─ Column 4: Multiverse Channels
│      ├─ Column 5: Ellen Ripley Delay+Grain
│      └─ Column 6: Ellen Ripley Reverb+Chaos
└─ 狀態欄

獨立視窗
├─ CV Meters (500×180) - 5 通道 Meter
├─ Video Window (960×540) - 攝影機 + 渲染結果
```

**CV 列表完整內容 (Column 1)**：
```
ENV 衰減 (3 個)
├─ ENV 1: 10-10000ms
├─ ENV 2: 10-10000ms
└─ ENV 3: 10-10000ms

Sequencer (統一時鐘)
├─ Clock Rate (BPM): 1-999 (同時驅動 SEQ1 + SEQ2)
├─ SEQ1 Steps: 4-32
└─ SEQ2 Steps: 4-32

Sobel 邊緣檢測參數
├─ Anchor X: 0-100% (可拖拉)
├─ Anchor Y: 0-100% (可拖拉)
├─ Range: 0-50%
├─ Edge Threshold: 0-255
└─ Temporal Smoothing: 0-100%

電纜檢測
└─ Min Length: 10-200
```

---

### 2. Multiverse 功能完整清單

**核心功能**：
- 4 個獨立音訊通道
- 自動頻率檢測 (主導頻率)
- Hue 色相映射 (八度循環)
- 3 個可調參數 per 通道：
  - Curve (0-1): 波形彎曲
  - Angle (-180° to +180°): 旋轉
  - Intensity (0-1.5): 強度

**渲染管線**：
```
Pass 1: Channel Rendering (應用 Curve)
  └─ 原始座標空間中彎曲波形

Pass 2: Rotation (應用 Angle)
  └─ Scale compensation 避免黑邊

Pass 3: Blending (應用 Blend Mode)
  └─ 4 種混合模式: Add/Screen/Diff/Dodge

Post-Processing:
  ├─ Brightness (0-4.0)
  ├─ Camera Mix (0-1)
  └─ Region-based 分區 (可選)
```

**進階功能**：
- Region-Based Rendering (4 種分區模式)
  - Brightness: 根據亮度分 4 級
  - Color: 根據顏色 (紅/綠/藍/黃) 分配
  - Quadrant: 4 象限固定分割
  - Edge: 邊界檢測動態分配
- Virtual Camera 輸出 (pyvirtualcam)
- 相機混合 (Camera Mix)

---

### 3. GPU Rendering 的實作方式

**三層選擇架構**：

| 方案 | 性能 | 優點 | 缺點 | 用途 |
|------|------|------|------|------|
| **Numba JIT** | 60+ FPS | 快速, 簡單, 無額外依賴 | CPU only, 首次編譯 2s | ✓ 默認首選 |
| **Qt OpenGL** | 30-45 FPS | GPU 加速, 區域映射, 線程安全 | 複雜, 信號開銷 | 完整功能 |
| **ModernGL** | 60+ FPS | 純 GPU, 最快 | 額外依賴, 無 Qt 整合 | 獨立測試 |

**選擇邏輯** (controller.py):
```python
if NUMBA_AVAILABLE:
    renderer = NumbaMultiverseRenderer()      # ← 首選
else:
    renderer = QtMultiverseRenderer()         # ← 備選
```

**Numba JIT 管線**：
```python
@njit(parallel=True, fastmath=True, cache=True)
def render_channel_numba(audio_buffer, frequency, intensity, curve, angle, ...):
    # Pass 1: 渲染 + Curve (1920×1080)
    for y in prange(height):  # 並行化
        for x in range(width):
            # Curve 彎曲採樣 X
            # 採樣波形，正規化電壓
            # HSV → RGB 色彩映射
    
    # Pass 2: 旋轉 (如果 angle != 0)
    rotated = rotate_image(layer, angle)  # Scale compensation
    
    # Pass 3: 混合到結果
    blend_func(result, rotated, blend_mode)
```

**性能特性**：
- 首幀編譯：~2s (JIT warm-up)
- 後續幀速：16-20ms @ 1920×1080 (充足容量)
- 總體 FPS：60+ @ 30 FPS 目標

---

### 4. CV Output 獨立視窗呈現

**窗口組成**：
```
CVMeterWindow (500×180, 獨立可調大小)
├─ MeterWidget (5 通道)
│  ├─ ENV1 [███░░] 5.0V Peak: 10V (粉色)
│  ├─ ENV2 [██░░░] 3.0V Peak: 10V (白色)
│  ├─ ENV3 [██░░░] 2.0V Peak: 10V (紅色)
│  ├─ SEQ1 [████░] 4.5V Peak: 10V (粉色)
│  └─ SEQ2 [█████] 5.2V Peak: 10V (白色)
```

**數據流**：
```
ContourCVGenerator (30 FPS)
├─ ENV1/2/3 value (0-1)
└─ SEQ1/2 value (0-1)
    ↓
Controller._on_cv()
    ├─ emit cv_updated signal
    └─ 映射到 [ENV1, ENV2, ENV3, SEQ1, SEQ2]
        ↓
    [GUI Thread]
    ├─ ScopeWidget.add_samples()  (波形圖表)
    └─ CVMeterWindow.update_values()  (Meter 條)
```

**視覺化層**：
1. **CV Meter** (獨立): 實時 meter 條
2. **Scope Widget** (主窗口): 波形顯示 (300 樣本)
3. **CV Overlay** (攝影機畫面):
   - Sobel 邊緣線 (白色, 半透明)
   - SEQ1 邊緣曲線 (粉色)
   - SEQ2 邊緣曲線 (白色)
   - ENV 觸發光圈 (擴展+淡出動畫)
   - 數據儀表板 (左上角面板)

---

### 5. 與現在版本的主要差異

**進化時間線**：
```
2025-10-18: Initial Release
└─ 基本 Multiverse + 雙渲染器

2025-10-18→11-03: Region Rendering
└─ 區域分區 + 4 種分區模式 + Content-aware

2025-11-03 (現在): Contour CV Maturity
├─ 統一 BPM 時鐘 (SEQ1 + SEQ2 同步)
├─ Sobel 邊緣檢測 (改進自 Canny)
├─ 錨點拖拉控制 + 視覺反饋
├─ CV Meter 獨立視窗
├─ 完整視覺疊加 (邊緣線, 光圈, 面板)
└─ Qt OpenGL Multi-pass 穩定性
```

**關鍵改進**：

| 項目 | 舊版 | 新版 |
|------|------|------|
| SEQ 時鐘 | 獨立 (SEQ1 ≠ SEQ2) | 統一 BPM (同步) |
| 邊緣檢測 | Canny (粗) | Sobel (精細) |
| 錨點控制 | 滑桿 | 拖拉 + 視覺反饋 |
| CV 顯示 | Embedded meter | 獨立視窗 |
| 視覺化 | 基本線條 | 邊緣線+光圈+面板 |
| 線程安全 | 部分 | 完整 (1s 超時) |

---

## 視窗佈局規範

### 尺寸與間距
```
主窗口: 1400×800
├─ 按鈕行: 30px
├─ Splitter: 200+600px (40:60)
│  ├─ Scope: 自動延伸
│  └─ Controls: 自動佈局
└─ 狀態欄: 20px

Grid 規範:
├─ 列數: 18 + 1 伸縮
├─ 行高: 18px (9× 標準 2px)
├─ 列寬: 標籤(自動) + 滑桿(140px) + 數值(25-35px)
├─ 水平間距: 10px
└─ 垂直間距: 18px

Slider 統一規格:
├─ 高度: 16px
├─ 寬度: 120-140px
└─ 字體: Qt default, 0.5pt
```

### 控制項標準化
```
Label + Slider + Value
例: "Clock Rate" [━━━━━] "120"

標籤 (Label):
├─ 寬度: 自動 (~80px)
├─ 對齐: 左
└─ 字體: 標準

滑桿 (Slider):
├─ 寬度: 140px
├─ 高度: 16px
├─ 方向: 水平
└─ 步進: 1

數值 (Value Label):
├─ 寬度: 25-35px
├─ 對齐: 右
├─ 字體: 0.5pt
└─ 精度: 3 位小數 或 整數
```

---

## Multiverse 功能完整清單

### ✓ 已實現功能
- [x] 4 個音訊通道獨立控制
- [x] Curve (波形彎曲)
- [x] Angle (旋轉角度)
- [x] Intensity (強度)
- [x] 4 種混合模式 (Add/Screen/Diff/Dodge)
- [x] 全局亮度調整
- [x] 相機混合
- [x] 頻率自動檢測
- [x] 八度循環色相映射
- [x] Scale compensation (無黑邊旋轉)
- [x] Region-based 渲染 (4 種分區)
- [x] 虛擬相機輸出
- [x] Thread-safe 設計 (1s 超時)

### 性能指標
- Numba JIT: **60+ FPS** @ 1920×1080
- Qt OpenGL: **30-45 FPS** (背景線程)
- ModernGL: **60+ FPS** (獨立 context)
- Region 分區開銷: **3-30ms** (取決於模式)
- 信號編送開銷: **0.2-0.6ms** (背景線程)

---

## 開發參考

**主要文件**：
```
vav/gui/
├─ compact_main_window.py     (主 GUI, 6 列佈局)
├─ cv_meter_window.py         (獨立 CV Meter 窗口)
├─ meter_widget.py            (5 通道 meter 實現)
└─ scope_widget.py            (波形顯示)

vav/cv_generator/
└─ contour_cv.py              (完整 CV 生成 + 視覺疊加)

vav/visual/
├─ numba_renderer.py          (JIT 渲染)
├─ qt_opengl_renderer.py      (OpenGL 渲染 + 線程安全)
├─ gpu_renderer.py            (ModernGL 渲染)
├─ content_aware_regions.py   (區域映射)
└─ region_mapper.py           (靜態分區)

vav/core/
└─ controller.py              (系統整合)
```

**測試檔案**：
```
test_edge_cv.py               (獨立 CV 測試，包含視覺化)
test_region_mode_gpu.py       (區域渲染測試)
verify_region_mode_code.py    (驗證腳本)
```

---

## 結論

**2025-11-03 版本特點**：
1. **完整的 GUI 架構**: 響應式 6 列佈局，邏輯清晰
2. **成熟的 CV 系統**: 統一時鐘，邊緣檢測，視覺反饋
3. **高性能渲染**: 三層選擇 (Numba/Qt/ModernGL)
4. **獨立視窗設計**: CV Meter, Scope, Video 分離
5. **線程安全**: 背景線程渲染無死鎖風險

**推薦用於**：
- 實時舞台表演
- 視聽藝術裝置
- 音訊視覺化系統
- Eurorack 集成控制

---

完整分析文檔已保存至：
`/Users/madzine/Documents/VAV/GUI_MULTIVERSE_ARCHITECTURE_ANALYSIS.md` (1011 行)

