# Vision Narrator - 即時視覺描述與語音播報系統

> 完全離線、開源的視覺理解與中文語音播報應用程式

## 系統概述

本系統透過電腦視訊鏡頭即時捕捉畫面，使用本地 AI 視覺模型生成中文描述，並轉換為語音播放。所有處理完全在本地運行，不依賴任何線上 API。

## 技術架構

### 方案 A：Apple FastVLM + Coqui TTS (推薦)
- **視覺模型**: Apple FastVLM-7B (專為 Apple Silicon 優化)
- **語音合成**: Coqui XTTSv2 (支援中文)
- **優勢**: 原生優化、高效能

### 方案 B：MLX-VLM + edge-tts (輕量替代)
- **視覺模型**: mlx-vlm (LLaVA 的 MLX 實作)
- **語音合成**: edge-tts (Microsoft)
- **優勢**: 簡單易用、快速部署

## 系統需求

- macOS (Apple Silicon M1/M2/M3/M4)
- Python 3.10+
- 16GB+ RAM (建議 24GB 用於 7B 模型)
- 視訊鏡頭
- 音訊輸出設備

## 安裝指南

### 1. 創建專案目錄與虛擬環境

```bash
mkdir vision_narrator
cd vision_narrator
python3 -m venv venv
source venv/bin/activate
```

### 2. 安裝依賴套件

#### 方案 A 依賴 (FastVLM + Coqui)
```bash
# 基礎套件
pip install opencv-python numpy pillow

# MLX 框架 (Apple Silicon)
pip install mlx mlx-lm

# Coqui TTS
pip install coqui-tts

# Transformers 與 HuggingFace
pip install transformers torch torchvision
```

#### 方案 B 依賴 (MLX-VLM + edge-tts)
```bash
# 基礎套件
pip install opencv-python numpy pillow

# MLX VLM
pip install mlx-vlm

# Edge TTS (輕量)
pip install edge-tts

# 音訊播放
pip install pydub simpleaudio
```

### 3. 下載模型

#### 方案 A - FastVLM
模型會在首次運行時自動從 HuggingFace 下載：
- `apple/FastVLM-7B` (~14GB)
- 或 `apple/FastVLM-1.5B` (~3GB，較快)
- 或 `apple/FastVLM-0.5B` (~1GB，最快)

#### 方案 B - MLX-VLM
```bash
# 首次運行時自動下載
# 或手動預先下載
python -m mlx_vlm.download llava-hf/llava-1.5-7b-hf
```

## 使用方法

### 基本用法

```bash
# 啟動視覺描述系統
python narrator.py

# 指定更新頻率 (秒)
python narrator.py --interval 5

# 選擇模型大小
python narrator.py --model-size 1.5b

# 使用方案 B (MLX-VLM)
python narrator.py --backend mlx-vlm
```

### 熱鍵控制

運行時可用的鍵盤控制：
- `空白鍵`: 立即觸發描述
- `p`: 暫停/繼續自動描述
- `+/-`: 增加/減少更新間隔
- `q`: 退出程式

## 配置選項

編輯 `config.yaml` 自定義設定：

```yaml
# 視覺模型設定
vision:
  backend: "fastvlm"  # 或 "mlx-vlm"
  model_size: "7b"    # 7b, 1.5b, 0.5b
  prompt: "請用繁體中文詳細描述這個畫面中的內容。"

# TTS 設定
tts:
  backend: "coqui"    # 或 "edge"
  language: "zh-TW"   # zh-TW (繁中) 或 zh-CN (簡中)
  voice: "female"

# 更新頻率
capture:
  interval: 3         # 秒
  camera_id: 0
  resolution: [640, 480]

# 效能調整
performance:
  quantization: "int8"  # int8, fp16, fp32
  max_tokens: 256
```

## 專案結構

```
vision_narrator/
├── README.md
├── requirements.txt
├── config.yaml
├── narrator.py           # 主程式
├── modules/
│   ├── camera.py        # 視訊捕捉模組
│   ├── vision_model.py  # 視覺理解模組
│   ├── tts_engine.py    # 語音合成模組
│   └── utils.py         # 工具函數
└── models/              # 下載的模型檔案 (自動創建)
```

## 效能優化建議

### M4 Pro/Max/Ultra
- 使用 FastVLM-7B，啟用 FP16
- Coqui TTS CPU 模式
- 預期延遲: 2-4秒

### M4 基本款
- 使用 FastVLM-1.5B 或 0.5B
- 啟用 INT8 量化
- 預期延遲: 1-2秒

### 記憶體優化
```python
# 在 config.yaml 中設定
performance:
  quantization: "int8"
  batch_size: 1
  use_cache: true
```

## 與 VAV 專案整合

### 可能的整合方式

1. **作為獨立服務**
   - Vision Narrator 作為背景服務運行
   - 透過 OSC 或共享記憶體傳遞描述文字
   - VAV 可視覺化描述的語意或情感

2. **共享攝影機輸入**
   - 兩個系統讀取同一攝影機
   - Vision Narrator 提供高階語意理解
   - VAV 提供低階視覺特徵 (輪廓、顏色)

3. **語音作為音訊輸入**
   - TTS 輸出同時送到 VAV 的 audio_process
   - 語音的韻律可調變視覺效果
   - 創造視覺-語音的雙向對話

詳細整合方案需進一步討論與測試。

## 已知限制

- Coqui TTS 在 Apple Silicon 只能使用 CPU (MPS 不支援)
- 首次運行需下載大型模型檔案
- 中文描述品質取決於模型訓練資料
- 即時性受模型大小與硬體影響

## 疑難排解

### 常見問題

**Q: 模型下載失敗**
```bash
# 設定 HuggingFace 鏡像
export HF_ENDPOINT=https://hf-mirror.com
```

**Q: Coqui TTS 安裝錯誤**
```bash
# 使用相容版本
pip install coqui-tts==0.22.0
```

**Q: 攝影機無法開啟**
```bash
# 檢查攝影機權限
# 系統偏好設定 > 隱私權與安全性 > 相機
```

## 授權

本專案使用 MIT License。使用的模型遵循各自的授權條款：
- FastVLM: Apple 研究授權
- LLaVA: Apache 2.0
- Coqui TTS: MPL 2.0

## 致謝

- Apple Machine Learning Research (FastVLM)
- Haotian Liu et al. (LLaVA)
- Coqui AI Team (TTS)
- MLX Community

---

最後更新: 2025-01-17
