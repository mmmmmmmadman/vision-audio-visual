# VAV 資料夾結構說明

整理日期: 2025-11-18

## 主要目錄結構

```
VAV/
├── vav/                    # VAV 核心系統
│   ├── audio/             # 音訊處理
│   ├── cv_generator/      # CV 訊號生成
│   ├── core/              # 核心控制器
│   ├── gui/               # GUI 介面
│   ├── vision/            # 視覺輸入
│   └── visual/            # 視覺輸出渲染
│
├── related_projects/       # 相關專案
│   ├── VAV_AudioEngine/   # Audio Engine 開發版本
│   └── VAV_variant/       # VAV 變體版本
│
├── docs/                   # 文件
│   ├── README.md          # 主要說明
│   ├── CHANGELOG.md       # 變更記錄
│   ├── BREAKBEAT_CHANGELOG.md  # Breakbeat 變更記錄
│   ├── CLEANUP_REPORT.md  # 清理報告
│   ├── FIX_REPORT.md      # 修復報告
│   ├── ISSUES_FOR_NEXT_SESSION.md  # 待處理問題
│   ├── PROJECT_HANDOFF.md # 專案交接文件
│   ├── REBUILD_INTRO.md   # 重建說明
│   └── VAV_AI_Integration_Research_Round2.md  # AI 整合研究
│
├── archived/               # 舊版本備份
│   └── *.backup           # 備份檔案
│
├── Audio Sample/          # 音訊樣本
├── breakbeat_cpp/         # Breakbeat C++ 實作
├── sndfilter/            # 音訊濾波器
├── vision_narrator/      # 視覺敘述模組
├── assets/               # 資源檔案
├── models/               # ML 模型
├── venv/                 # Python 虛擬環境
│
├── breakbeat_engine.py   # Breakbeat 引擎
├── breakbeat_gui.py      # Breakbeat GUI
├── breakbeat_gui_test.py # Breakbeat 測試
├── voice_segmenter.py    # 語音分段器
├── vision_rhythm_complete_gui.py  # 視覺節奏 GUI
├── main_compact.py       # 主程式 (精簡版)
│
├── alien4_extension.cpp  # Alien4 擴充功能
├── CMakeLists.txt        # CMake 建構設定
├── build_alien4.sh       # Alien4 建構腳本
│
├── start_vav.command     # VAV 啟動腳本
├── start_breakbeat.command  # Breakbeat 啟動腳本
│
└── requirements.txt      # Python 依賴套件
```

## 說明

### vav/ (核心系統)
VAV 主要系統的 Python 套件，包含:
- 視覺輸入處理 (camera)
- CV 訊號生成 (cv_generator)
- 音訊處理 (audio)
- 視覺渲染 (visual)
- GUI 介面 (gui)
- 核心控制器 (core)

### related_projects/ (相關專案)
- **VAV_AudioEngine**: Audio Engine 的獨立開發版本
- **VAV_variant**: VAV 的變體實驗版本

### docs/ (文件)
所有專案相關文件，包含:
- 使用說明
- 變更記錄
- 開發報告
- 待處理事項

### archived/ (備份)
舊版本的備份檔案

## 最近更新

### 2025-11-18
- 加入 CV Meter Window 的 mute 按鈕功能
  - 每個 CV 通道左側有 M 按鈕
  - 點擊切換 mute 狀態 (灰色=啟用, 紅色=靜音)
  - Mute 後該通道不輸出 CV 訊號

修改檔案:
- `vav/gui/meter_widget.py` - 加入 mute UI 和邏輯
- `vav/gui/cv_meter_window.py` - 處理 mute 訊號
- `vav/core/controller.py` - 套用 mute 到 CV 輸出
