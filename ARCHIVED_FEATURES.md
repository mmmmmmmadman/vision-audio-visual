# VAV 已停用功能文件 - 2025-11-04

本文件記錄 VAV 專案中已停用或替換的功能，保留技術參考與未來可能重新啟用的說明。

---

## 1. Cable Detection (電纜檢測)

**檔案**: `vav/vision/cable_detector.py`

**停用日期**: 2025-11-03

**停用原因**:
- Multiverse 渲染器改為直接啟用 4 通道
- 通道啟用判斷改為基於 user_intensity (音訊強度)
- 不再依賴視覺檢測到的電纜數量來決定啟用通道

**技術說明**:
- 使用 OpenCV Canny 邊緣檢測 + Hough Line Transform
- 可檢測畫面中的線段（模擬模組化合成器的電纜）
- 支援最多 32 條電纜檢測
- 提供電纜長度、角度、位置等屬性

**保留原因**:
未來可能重新啟用視覺互動式通道啟用功能

**相關 GUI 控制項**:
- Min Length 滑桿已移除

---

## 2. Content-Aware Region Mapping (內容感知區域映射)

**檔案**: `vav/visual/content_aware_regions.py`

**停用日期**: 2025-11-04

**停用原因**:
- GPU 渲染器 (gpu_renderer.py) 改用完整解析度渲染
- 效能提升後不再需要區域映射優化
- 簡化渲染邏輯，移除複雜的區域分配機制

**技術說明**:
提供多種區域分割策略：
1. **Color-based**: 根據 HSV 色相分割（紅/綠/藍/黃 對應 4 通道）
2. **Brightness-based**: 根據亮度分割（4 個亮度級別）
3. **Quadrant**: 簡單四象限分割（左上/右上/左下/右下）
4. **Edge-based**: 使用 Watershed 根據邊緣分割
5. **Cable-based**: 根據檢測到的電纜位置分割

**保留原因**:
技術參考，未來可能用於其他視覺分析功能

**相關變更**:
- `gpu_renderer.py` 不再接受 region_map 參數
- 所有渲染使用完整畫面

---

## 3. Numba CPU Renderer (Numba CPU 渲染器)

**檔案**: `vav/visual/numba_renderer.py`

**替換日期**: 2025-11-04

**替換為**: `vav/visual/gpu_renderer.py` (ModernGL + Metal)

**替換原因**:
- GPU 渲染器效能遠超 CPU 渲染
- ModernGL + Metal 在 Apple Silicon 上有硬體加速
- 減少 CPU 負載，留給音訊處理使用

**技術說明**:
- 使用 Numba JIT 編譯的 LLVM 優化 CPU 渲染
- 支援多核並行處理 (prange)
- 實現 4 種混合模式：Add, Screen, Difference, Color Dodge
- 包含旋轉、曲線彎曲等效果

**保留原因**:
CPU 備用方案，當 GPU 不可用時可切換回來

**相關效能數據**:
- Numba CPU: ~30-50 FPS (1920x1080)
- GPU (ModernGL): ~60 FPS (1920x1080, 垂直同步)

---

## 4. Channel Intensity 獨立控制

**停用日期**: 2025-11-04

**停用原因**:
- 功能與 Track Vol 重複
- 合併為單一控制項 (Track Vol) 簡化 GUI
- Track Vol 同時控制音訊混音與視覺強度

**技術說明**:
- 原實現: 獨立的 Channel Intensity 滑桿 (4 個)
- 新實現: Track Vol 滑桿同時調用 `set_renderer_channel_intensity()` 和 `set_channel_level()`

**保留原因**:
無需保留程式碼，已完全整合到 Track Vol

**相關文件**:
`LEVEL_MERGE_20251104.md`

---

## 5. Saliency CV Generator (顯著性 CV 生成器)

**檔案**: `vav/cv_generator/saliency_cv.py`

**狀態**: 實驗性功能，未整合到主程式

**技術說明**:
- 使用 OpenCV Spectral Residual Saliency 檢測
- 從畫面提取顯著點（替代 Corner Detection）
- 計算顯著性能量（用於 Envelope 觸發判斷）
- 支援提取 N 個最顯著的點

**未整合原因**:
- 當前系統使用 Contour CV (輪廓 CV) 已足夠
- Saliency 檢測計算成本較高
- 未發現明顯優於現有方案的優勢

**保留原因**:
未來可能開發更進階的視覺分析功能

---

## 停用功能清單摘要

| 功能 | 檔案 | 停用日期 | 狀態 |
|------|------|----------|------|
| Cable Detection | `vav/vision/cable_detector.py` | 2025-11-03 | 已停用 |
| Region Mapping | `vav/visual/content_aware_regions.py` | 2025-11-04 | 已停用 |
| Numba Renderer | `vav/visual/numba_renderer.py` | 2025-11-04 | 已替換 |
| Channel Intensity | GUI 控制項 | 2025-11-04 | 已合併 |
| Saliency CV | `vav/cv_generator/saliency_cv.py` | - | 未使用 |

---

## 當前啟用的核心功能

### 視覺渲染
- GPU Renderer (ModernGL + Metal) - `vav/visual/gpu_renderer.py`
- Qt OpenGL Renderer (主渲染器) - `vav/visual/qt_opengl_renderer.py`
- SD img2img (圖像生成) - `vav/visual/sd_img2img_process.py`

### 音訊處理
- Ellen Ripley Effect Chain - `vav/audio/effects/ellen_ripley.py`
  - Delay, Reverb, Grain, Chaos
- ES-8 音訊 I/O - `vav/audio/io.py`

### CV 生成
- Envelope Generator - `vav/cv_generator/envelope.py`
- Sequencer - `vav/cv_generator/sequencer.py`
- Contour CV - `vav/cv_generator/contour_cv.py`

### GUI 功能
- Compact Main Window - `vav/gui/compact_main_window.py`
- MIDI Learn System - `vav/midi/midi_learn.py`
- 38 個 MIDI 可學習推桿
- 粉色系 MUJI 配色

---

**建檔日期**: 2025-11-04
**維護狀態**: 持續更新
**相關文件**: CLEANUP_PLAN_20251104.md
