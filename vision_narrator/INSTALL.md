# Vision Narrator - 安裝指南

## 快速開始 (推薦配置)

### 1. 創建專案目錄

```bash
cd /Users/madzine/Documents/VAV
cd vision_narrator
```

### 2. 創建並啟動虛擬環境

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. 安裝依賴套件

#### 選項 A：最簡單方案 (MLX-VLM + Edge-TTS)

```bash
pip install opencv-python numpy pillow
pip install mlx mlx-lm mlx-vlm
pip install edge-tts
```

#### 選項 B：高品質方案 (Transformers + Coqui)

```bash
pip install opencv-python numpy pillow
pip install transformers torch torchvision
pip install coqui-tts
```

#### 選項 C：最小方案 (使用 macOS 內建 TTS)

```bash
pip install opencv-python numpy pillow
pip install mlx mlx-lm mlx-vlm
# macOS say 指令已內建，無需額外安裝
```

### 4. 測試各模組

#### 測試攝影機

```bash
cd modules
python camera.py
```

#### 測試視覺模型

```bash
python vision_model.py
```

#### 測試 TTS

```bash
python tts_engine.py
```

### 5. 運行主程式

```bash
cd ..
python narrator.py
```

## 詳細安裝步驟

### 系統需求檢查

```bash
# 檢查 Python 版本
python3 --version  # 應該 >= 3.10

# 檢查 macOS 版本
sw_vers

# 檢查晶片型號
sysctl -n machdep.cpu.brand_string
```

### 模型下載

首次運行會自動下載模型，時間取決於網路速度：

- **LLaVA-1.5-7B**: ~14GB
- **LLaVA-1.5-1.5B**: ~3GB
- **Edge-TTS**: 無需下載
- **Coqui XTTS-v2**: ~2GB

### 加速下載 (選用)

如果下載速度慢，可使用 HuggingFace 鏡像：

```bash
export HF_ENDPOINT=https://hf-mirror.com
```

### 攝影機權限設定

1. 開啟「系統偏好設定」
2. 前往「隱私權與安全性」
3. 點選「相機」
4. 勾選「終端機」或你使用的終端程式

## 常見問題

### Q1: 無法開啟攝影機

**解決方案**:
- 檢查攝影機是否被其他程式佔用
- 確認已授予相機權限
- 嘗試不同的 camera_id (0, 1, 2...)

### Q2: MLX-VLM 安裝失敗

**解決方案**:
```bash
# 確保使用最新 pip
pip install --upgrade pip

# 單獨安裝 MLX
pip install mlx mlx-lm

# 再安裝 mlx-vlm
pip install mlx-vlm
```

### Q3: Edge-TTS 無法播放聲音

**解決方案**:
- 確認音量未靜音
- 檢查音訊輸出設備
- 嘗試使用 macOS 後端: `--tts macos`

### Q4: Coqui TTS 安裝在 Apple Silicon 失敗

**解決方案**:
```bash
# Coqui 可能需要特定版本
pip install coqui-tts==0.22.0

# 或使用 edge-tts 替代
pip install edge-tts
```

### Q5: 記憶體不足

**解決方案**:
- 使用較小的模型
- 啟用 INT8 量化
- 關閉其他應用程式

### Q6: 推理速度太慢

**優化建議**:

```bash
# 使用較小模型
python narrator.py --model llava-hf/llava-v1.6-mistral-7b-hf

# 增加描述間隔
python narrator.py --interval 10

# 使用 edge-tts (比 coqui 快)
python narrator.py --tts edge-tts
```

## 進階配置

### 自定義提示詞

```bash
python narrator.py --prompt "請用詩意的語言描述畫面"
```

### 使用不同語言

```bash
# 簡體中文
python narrator.py --language zh-CN

# 繁體中文 (預設)
python narrator.py --language zh-TW
```

### 調整更新頻率

```bash
# 每 10 秒描述一次
python narrator.py --interval 10

# 互動模式 (手動觸發)
python narrator.py --mode interactive
```

## 解除安裝

```bash
# 刪除虛擬環境
rm -rf venv

# 刪除下載的模型 (可選)
rm -rf ~/.cache/huggingface

# 刪除專案目錄 (可選)
cd ..
rm -rf vision_narrator
```

## 取得幫助

```bash
# 查看所有選項
python narrator.py --help

# 查看模組測試說明
python modules/camera.py --help
python modules/vision_model.py --help
python modules/tts_engine.py --help
```

---

如有任何問題，請參考 README.md 或提出 Issue。
