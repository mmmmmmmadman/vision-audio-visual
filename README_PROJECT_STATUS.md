# VAV 專案狀態 - 2025-11-04

## 當前版本

**GPU Multiverse Renderer**: v11042318 (預設)
**CPU Numba Renderer**: v11042100 (備用)
**專案狀態**: ✅ GPU 渲染器完全驗證並投入生產

---

## 快速索引

### 核心文件

| 文件 | 說明 | 更新日期 |
|------|------|---------|
| `VAV_20251104_GPU_MILESTONE.md` | **GPU 里程碑總覽** | 2025-11-04 |
| `GPU_REFACTOR_20251104_2318.md` | GPU 修復技術詳情 | 2025-11-04 |
| `BENCHMARK_RESULTS_20251104.md` | 性能測試 (無 SD) | 2025-11-04 |
| `BENCHMARK_SD_RESULTS_20251104.md` | 性能測試 (有 SD) | 2025-11-04 |
| `GPU_MULTIVERSE_BUGFIX_20251104.md` | Bug 分析與修復 | 2025-11-04 |
| `CHANGELOG.md` | 完整變更記錄 | 持續更新 |

### 工作記錄

| 文件 | 說明 | 日期 |
|------|------|------|
| `VAV_20251104_進度紀錄.md` | 11-04 工作日誌 | 2025-11-04 |
| `VAV_20251104_2100_工作日誌.md` | 11-04 早期記錄 | 2025-11-04 |
| `LEVEL_MERGE_20251104.md` | Track Vol 整合 | 2025-11-04 |
| `GPU_RENDERER_SWITCH_20251104.md` | 渲染器切換記錄 | 2025-11-04 |

### 歸檔區

已清理的過時文件移至: `archive_20251104/`
- 過時計劃文件 (5 個)
- 過時功能文件 (2 個)
- 過時最佳化報告 (2 個)
- 測試程式 (8 個)

---

## 專案結構

```
VAV/
├── vav/                        # 核心程式碼
│   ├── core/
│   │   └── controller.py      # 主控制器 (GPU 優先)
│   ├── visual/
│   │   ├── qt_opengl_renderer.py      # GPU 渲染器 (v11042318)
│   │   ├── numba_renderer.py          # CPU 渲染器 (v11042100)
│   │   └── sd_img2img_process.py      # SD 處理器
│   ├── gui/
│   │   └── compact_main_window.py     # 主 GUI
│   └── ...
├── benchmark_renderers.py      # 性能測試 (無 SD)
├── benchmark_with_sd.py        # 性能測試 (有 SD)
├── main_compact.py             # 主程式入口
├── archive_20251104/           # 歸檔區
│   ├── docs/                   # 過時文件
│   └── tests/                  # 舊測試程式
└── [文件]
```

---

## 核心功能狀態

### Multiverse 渲染器

| 功能 | CPU | GPU | 狀態 |
|------|-----|-----|------|
| 4 通道渲染 | ✅ | ✅ | 完全一致 |
| 電壓正規化 (-10V~+10V) | ✅ | ✅ | 完全一致 |
| 旋轉 + 動態縮放 | ✅ | ✅ | 完全一致 |
| Curve (彎曲效果) | ✅ | ✅ | 完全一致 |
| Region Map 空間分離 | ✅ | ✅ | 完全支援 |
| Blend Modes (無 region) | ✅ | ✅ | 4 種模式 |
| Blend Modes (有 region) | ✅ | ⚠️ | 架構限制 |
| Brightness 控制 | ✅ | ✅ | 完全一致 |
| Camera Y-flip | ✅ | ✅ | 完全一致 |

### SD img2img 整合

- **模型**: SD 1.5 + LCM LoRA + TAESD
- **架構**: 獨立進程 (multiprocessing)
- **參數**: 2 steps, strength 0.5, guidance 1.0
- **影響**: CPU +7.2%, GPU +21.5%
- **狀態**: ✅ 完全整合並測試

### Ellen Ripley 效果鏈

- **Numba JIT 預熱**: ✅ 系統初始化時完成
- **效果**: Distortion, Echo, Feedback, Glitch
- **狀態**: ✅ 無斷音，平滑運作

---

## 性能數據摘要

### 無 SD 環境

| 渲染器 | 渲染時間 | FPS | 加速比 |
|--------|---------|-----|--------|
| CPU | 27.3 ms | 36.6 fps | - |
| GPU | 4.5 ms | 223.2 fps | **6.09x** |

### 有 SD 環境

| 渲染器 | 渲染時間 | FPS | 加速比 | SD 影響 |
|--------|---------|-----|--------|---------|
| CPU | 29.1 ms | 34.3 fps | - | +7.2% |
| GPU | 5.9 ms | 169.5 fps | **4.96x** | +21.5% |

### 結論

GPU 版本在所有場景下都有壓倒性優勢：
- 無 SD: 6.09x 加速，223 fps
- 有 SD: 4.96x 加速，169 fps (仍遠超 60 fps 需求)

---

## 系統需求

### 硬體

- **最低**: Apple Silicon M1 或更新
- **建議**: M1 Pro/Max/Ultra, M2 或更新
- **GPU**: Metal 支援 (macOS 原生)
- **記憶體**: 8GB+ (16GB+ 建議)

### 軟體

- **作業系統**: macOS 12.0+ (Monterey 或更新)
- **Python**: 3.11
- **主要套件**:
  - PyQt6 (GUI + OpenGL)
  - NumPy (數值運算)
  - Numba (JIT 編譯)
  - PyTorch + Diffusers (SD)
  - OpenCV (影像處理)

---

## 使用說明

### 啟動程式

```bash
cd /Users/madzine/Documents/VAV
venv/bin/python3 main_compact.py
```

### 效能測試

```bash
# 測試 CPU vs GPU (無 SD)
venv/bin/python3 benchmark_renderers.py

# 測試 CPU vs GPU (有 SD)
venv/bin/python3 benchmark_with_sd.py
```

### 切換渲染器

預設使用 GPU 渲染器。如需強制使用 CPU：

修改 `vav/core/controller.py:141-161`：
```python
# 將 GPU 初始化區塊註解掉
# 或在 GPU 初始化前設置 renderer_initialized = True
```

---

## 已知問題與限制

### 1. Blend Modes with Region Map (GPU)

**問題**: GPU 單次渲染架構下，blend modes 在 region map 啟用時效果有限。

**原因**: 每個像素只渲染一個通道，沒有多個顏色可混合。

**狀態**: 可接受的限制，region map 主要用於空間分離。

**解決方案**: 未來可實作 multi-pass 渲染架構。

### 2. SD 資源競爭

**問題**: SD 使用 Metal backend 與 GPU 渲染器競爭資源。

**影響**: GPU 渲染性能下降 21.5% (仍有 169 fps)。

**狀態**: 可接受，性能仍遠超需求。

**優化**:
- 調整 SD Send Interval (1.5s → 2-3s)
- 減少 SD Steps (2 → 1)
- 未來支援雙 GPU 架構

### 3. Shader Validation Warning

```
Warning: Shader validation returned status 0: Validation Failed: No vertex array object bound.
```

**影響**: 無實際影響，僅為 OpenGL 驗證警告。

**狀態**: 可忽略，渲染正常運作。

---

## 下一步計劃

### 短期 (1-2 週)

- [ ] 實作 Ratio (pitch shifting) 功能
- [ ] 實作 Phase (horizontal offset) 功能
- [ ] 新增更多 blend modes
- [ ] SD 參數 GUI 控制

### 中期 (1-2 月)

- [ ] Multi-pass 渲染架構
- [ ] 完整 blend modes with region map
- [ ] 效能進一步優化
- [ ] 跨平台測試 (Linux with NVIDIA)

### 長期 (3+ 月)

- [ ] Vulkan backend (跨平台)
- [ ] 雙 GPU 支援
- [ ] 更多視覺效果
- [ ] 即時參數自動化

---

## 維護指南

### 更新 GPU 渲染器

1. 修改 `vav/visual/qt_opengl_renderer.py`
2. 執行效能測試確認無退化
3. 更新版本號和文件
4. Commit 到 git

### 新增功能

1. 在 CPU 版本實作並測試
2. 移植到 GPU 版本
3. 執行效能和功能測試
4. 更新文件

### 問題排查

1. 檢查 GPU 初始化輸出
2. 確認 Metal backend 可用
3. 檢查記憶體使用
4. 查看 shader 編譯錯誤

---

## Git 狀態

- **最後 Commit**: GPU Refactor 20251104_2318
- **Branch**: main (假設)
- **Remote**: 本地 git repository (無遠端推送)

---

## 聯絡與支援

- **專案位置**: `/Users/madzine/Documents/VAV`
- **文件索引**: 本文件
- **問題回報**: 查看相關技術文件或 CHANGELOG.md

---

**文件版本**: v1.0
**建立日期**: 2025-11-04 23:40
**最後更新**: 2025-11-04 23:40
**維護者**: Claude Code + User

