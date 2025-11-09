# VAV 專案清理計劃 - 2025-11-04

## 清理目標
整理專案檔案，移除不需要的測試檔案與備份，統合文件，標記已停用功能。

---

## 一、需要刪除的檔案

### 1. 備份檔案 (7 個)
```
vav/core/controller.py.bak7
vav/gui/compact_main_window.py.backup
vav/gui/compact_main_window.py.bak2
vav/gui/compact_main_window.py.bak3
vav/gui/compact_main_window.py.bak4
vav/gui/compact_main_window.py.bak5
vav/gui/compact_main_window.py.bak6
```
**原因**: 已有 git 版本控制，不需要手動備份

### 2. 測試檔案 (13 個)
```
test_edge_cv.py
test_effects_functional_verification.py
test_effects_optimization.py
test_ellen_ripley_chaos.py
test_gpu_region_integration.py
test_gpu_region_mode.py
test_gpu_region_visual.py
test_grain_chaos.py
test_grain_performance.py
test_grain_stats.py
test_region_mode_gpu.py
verification_tests.py
verify_region_mode_code.py
```
**原因**: 開發測試完成，功能已整合到主程式

### 3. 已停用的模組檔案
```
vav/vision/cable_detector.py (已停用 - cables 檢測)
vav/visual/content_aware_regions.py (已停用 - region mapping)
vav/visual/numba_renderer.py (已替換為 gpu_renderer.py)
vav/cv_generator/saliency_cv.py (未使用)
```
**原因**: 功能已停用或被替代

---

## 二、需要移至 archived/ 的文件

### 1. 舊版文件 (移至 archived/docs/)
```
ANALYSIS_SUMMARY.md
CV_SEQ_EVOLUTION_ANALYSIS.md
CV_SEQ_QUICK_SUMMARY.md
DISCUSSION_PREPARATION.md
GPU_REGION_MODE_REPORT.md
GPU_REGION_MODE_TEST_REPORT.md
GRAIN_OPTIMIZATION_REPORT.md
GUI_MULTIVERSE_ARCHITECTURE_ANALYSIS.md
IMPLEMENTATION_SUMMARY.md
PBO_IMPLEMENTATION_SUMMARY.md
REGION_MODE_QUICK_REF.md
REGION_MODE_TEST_GUIDE.md
REGION_MODE_VERIFICATION_SUMMARY.md
```
**原因**: 歷史開發文件，保留但歸檔

### 2. 測試/實驗記錄 (移至 archived/experiments/)
```
ELLEN_RIPLEY_FIX_20251104.md
OPTIMIZATION_REPORT.md
```

---

## 三、需要保留的核心檔案

### 1. 主程式
```
main_compact.py - 啟動入口
```

### 2. 核心模組
```
vav/core/controller.py - 主控制器
vav/gui/compact_main_window.py - GUI 主視窗
vav/audio/io.py - 音訊 I/O (ES-8)
vav/visual/qt_opengl_renderer.py - 視覺渲染器
vav/visual/gpu_renderer.py - GPU Multiverse 渲染
vav/visual/sd_img2img_process.py - SD 圖像生成
vav/midi/midi_learn.py - MIDI Learn 系統
```

### 3. 音訊效果
```
vav/audio/effects/ellen_ripley.py - 效果鏈
vav/audio/effects/delay.py
vav/audio/effects/reverb.py
vav/audio/effects/grain.py
vav/audio/effects/chaos.py
```

### 4. CV 生成器
```
vav/cv_generator/envelope.py - 包絡線生成
vav/cv_generator/sequencer.py - 序列器
vav/cv_generator/contour_cv.py - 輪廓 CV
```

### 5. 當前文件
```
README.md - 專案說明
CHANGELOG.md - 更新日誌
FEATURE_VERIFICATION.md - 功能驗證
GUI_CONTROLS.md - GUI 控制說明
MIDI_LEARN_20251104.md - MIDI Learn 文件
SLIDER_STYLING_20251104.md - 推桿配色文件
GPU_RENDERER_SWITCH_20251104.md - GPU 渲染器切換記錄
LEVEL_MERGE_20251104.md - Level 合併記錄
```

---

## 四、需要標記為停用的功能

在相關檔案頂部加上停用標記：

### 1. vav/vision/cable_detector.py
```python
"""
Cable Detection System (已停用)
停用日期: 2025-11-03
停用原因: Multiverse 改為直接啟用 4 通道，不依賴 cables 檢測
保留原因: 未來可能重新啟用
"""
```

### 2. vav/visual/content_aware_regions.py
```python
"""
Content-Aware Region Mapping (已停用)
停用日期: 2025-11-04
停用原因: GPU 渲染器改用完整解析度渲染，不使用 region mapping
保留原因: 技術參考
"""
```

### 3. vav/visual/numba_renderer.py
```python
"""
Numba CPU Renderer (已替換)
替換日期: 2025-11-04
替換為: gpu_renderer.py (ModernGL + Metal)
保留原因: CPU 備用方案
"""
```

### 4. vav/cv_generator/saliency_cv.py
```python
"""
Saliency CV Generator (未使用)
狀態: 實驗性功能，未整合到主程式
保留原因: 未來可能開發
"""
```

---

## 五、文件統合

### 1. 創建 ARCHIVED_FEATURES.md
統合所有已停用功能的說明：
- Cable Detection (cables 檢測)
- Region Mapping (區域映射)
- Numba CPU Renderer (CPU 渲染器)
- Channel Intensity 獨立控制

### 2. 更新 README.md
- 移除已停用功能的說明
- 更新當前功能列表
- 更新系統架構圖

### 3. 更新 CHANGELOG.md
- 加入 2025-11-04 的變更記錄
- MIDI Learn 功能
- GUI 視覺改進

---

## 六、執行順序

1. 創建 archived/ 目錄結構
2. 移動文件到 archived/
3. 刪除測試檔案
4. 刪除備份檔案
5. 為停用功能加上標記
6. 創建 ARCHIVED_FEATURES.md
7. 更新 README.md 和 CHANGELOG.md
8. Git commit 所有變更

---

## 預期結果

### 清理前
- 根目錄: 26+ 個 .md 文件
- 根目錄: 13 個測試 .py 文件
- vav/: 7 個備份文件
- 4 個已停用模組無標記

### 清理後
- 根目錄: 10 個核心文件
- archived/docs/: 13 個歷史文件
- archived/experiments/: 2 個實驗記錄
- archived/tests/: 13 個測試文件
- archived/backups/: 7 個備份文件
- 4 個已停用模組加上清楚標記

---

**準備日期**: 2025-11-04
**執行前需確認**: 程式正常運行，git status 乾淨
