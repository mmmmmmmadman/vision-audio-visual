# VAV 區域渲染功能使用指南

**版本：VAV_20251018 + Region Rendering**
**日期：2025-10-18**

## 新增功能概述

現在 VAV 支援**基於畫面內容的分散式區域渲染**！每個音訊通道（CH1-4）可以根據攝影機畫面的不同區域分別顯示 Multiverse 視覺化。

## 功能特色

- ✅ **4 種分區模式**：亮度、顏色、四象限、邊緣檢測
- ✅ **即時動態**：根據攝影機畫面即時更新分區
- ✅ **Numba JIT 優化**：保持高性能渲染（30-60 FPS）
- ✅ **GUI 控制**：簡單的 CheckBox 和下拉選單

## GUI 控制位置

在主視窗的 **Multiverse 控制欄**（COLUMN 3）中：

```
┌─────────────────────────┐
│ ☑ Multiverse            │
│ Blend: [Add ▼]          │
│ Brightness: [━━━━━]     │
│ Camera Mix: [━━━━━]     │
│                         │
│ ☐ Region Map  ← 新增！  │
│ Region Mode: [Bright ▼] │
└─────────────────────────┘
```

### 控制項說明

1. **Region Map CheckBox**
   - ☐ 關閉：全畫面顯示所有通道（原始模式）
   - ☑ 開啟：根據選擇的模式分區渲染

2. **Region Mode 下拉選單**
   - **Bright**（亮度）：根據畫面亮度分成 4 個級別
   - **Color**（顏色）：根據顏色（紅/綠/藍/黃）分配
   - **Quad**（四象限）：簡單的四分割
   - **Edge**（邊緣）：自動檢測物體邊界分區

## 分區模式詳解

### 1. 亮度模式 (Brightness)

**最推薦用於即時表演！**

```
畫面亮度    →  對應通道
────────────────────────
很暗 (<64)   →  CH1 (紅色)
中暗 (64-128) →  CH2 (綠色)
中亮 (128-192)→  CH3 (藍色)
很亮 (≥192)   →  CH4 (黃色)
```

**應用場景：**
- 打燈表演：燈光亮處顯示特定通道
- 手影互動：手部遮擋產生暗區，觸發不同視覺
- 自然光影：利用環境光影變化控制視覺

### 2. 顏色模式 (Color)

```
畫面顏色    →  對應通道
────────────────────────
紅色區域     →  CH1
綠色區域     →  CH2
藍色區域     →  CH3
黃色區域     →  CH4
```

**應用場景：**
- 彩色 Patch Cables：不同顏色電纜觸發不同視覺
- 彩色物件互動：使用彩色道具控制
- 舞台燈光：彩色燈光映射到視覺

### 3. 四象限模式 (Quadrant)

```
┌─────────┬─────────┐
│   CH1   │   CH2   │
│  左上   │  右上   │
├─────────┼─────────┤
│   CH3   │   CH4   │
│  左下   │  右下   │
└─────────┴─────────┘
```

**應用場景：**
- 固定位置互動：不同位置觸發不同音訊
- 多人協作：不同人控制不同象限
- 簡單分區：快速測試

### 4. 邊緣模式 (Edge)

**最有機、最藝術！**

使用 OpenCV Watershed 演算法自動檢測畫面中的物體邊界，動態分配區域。

**應用場景：**
- 物體檢測：自動識別並分配區域
- 自然分區：根據實際畫面內容分區
- 藝術效果：不規則、流動的視覺

## 使用步驟

### 快速開始

1. **啟動 VAV**
   ```bash
   cd /Users/madzine/Documents/VAV
   source venv/bin/activate
   python3 main_compact.py
   ```

2. **配置音訊設備**
   - 點擊 "Devices" 按鈕
   - 選擇您的 ES-8 或其他音訊介面
   - 確保有 4 個輸入通道

3. **開始系統**
   - 點擊 "Start" 按鈕
   - 確認攝影機畫面顯示

4. **啟用 Multiverse**
   - 勾選 "Multiverse" CheckBox

5. **啟用區域渲染**
   - 勾選 "Region Map" CheckBox
   - 選擇分區模式（建議從 "Bright" 開始）

6. **即時調整**
   - 改變攝影機畫面（移動手、物件、改變光線）
   - 觀察不同區域顯示不同通道的視覺化
   - 切換不同分區模式查看效果

## 技術細節

### 性能

- **亮度分區**：~3-5ms 額外開銷
- **顏色分區**：~5-10ms 額外開銷
- **四象限**：幾乎無開銷（預計算）
- **邊緣檢測**：~20-30ms 額外開銷

總體 FPS：30-60 fps（取決於模式和系統）

### 實現原理

1. **區域映射生成**：
   - 每幀根據攝影機畫面生成 region_map (height×width 陣列)
   - 每個像素標記為 0-3（對應 CH1-4）

2. **區域混合**：
   - 使用 Numba JIT 編譯的區域混合函數
   - 只在對應區域混合該通道的視覺
   - 保持原有的 4 種混合模式（Add/Screen/Diff/Dodge）

### 檔案修改

```
已修改：
├── vav/core/controller.py          # 添加區域渲染控制
├── vav/visual/numba_renderer.py    # 添加區域混合函數
└── vav/gui/compact_main_window.py  # 添加 GUI 控制

新增：
├── vav/visual/content_aware_regions.py  # 內容感知分區
└── vav/visual/region_mapper.py          # 靜態分區映射

備份：
└── backups/before_region_rendering_20251018_235357/
    ├── controller.py.backup
    └── numba_renderer.py.backup
```

## 還原到原始版本

如果需要還原到沒有區域渲染的版本：

```bash
cd /Users/madzine/Documents/VAV

# 還原原始文件
cp backups/before_region_rendering_20251018_235357/controller.py.backup vav/core/controller.py
cp backups/before_region_rendering_20251018_235357/numba_renderer.py.backup vav/visual/numba_renderer.py

# 或使用 Git
git restore vav/core/controller.py vav/visual/numba_renderer.py vav/gui/compact_main_window.py
```

## 故障排除

### 問題：啟用 Region Map 後畫面全黑

**原因**：可能沒有檢測到對應亮度/顏色的區域

**解決方法**：
1. 切換到 "Quad" 模式（固定分區）
2. 調整攝影機光線
3. 檢查 Multiverse 的 Brightness 和 Intensity 設定

### 問題：性能下降、FPS 降低

**原因**：邊緣檢測模式較耗資源

**解決方法**：
1. 切換到 "Bright" 或 "Quad" 模式
2. 降低攝影機解析度
3. 關閉 Region Map（使用原始全畫面模式）

### 問題：區域分配不理想

**原因**：自動檢測可能不符合預期

**解決方法**：
1. 調整攝影機位置和光線
2. 切換不同的分區模式
3. 使用 "Quad" 固定分區模式

## 未來擴展

可能的改進方向：

- [ ] 自定義亮度範圍（可調整 threshold）
- [ ] 更多分區模式（對角線、條紋、Voronoi）
- [ ] 手勢檢測分區（需要 MediaPipe）
- [ ] 電纜檢測分區（使用現有 cable_detector）
- [ ] 區域視覺化預覽（顯示分區邊界）

## 建議與反饋

如有任何問題或建議，請記錄在 VAV 開發筆記中。

---

**MADZINE © 2025**
**VAV - Vision-Audio-Visual System**
