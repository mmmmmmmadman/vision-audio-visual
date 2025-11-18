# VAV 啟動指南

## 快速啟動

### 1. 啟動完整程式（推薦）

在專案根目錄執行：

```bash
cd /Users/madzine/Documents/VAV
venv/bin/python3 main_compact.py
```

### 2. 系統需求

- Python 3.x（已配置虛擬環境）
- macOS（Darwin 24.6.0）
- 攝像頭（用於 ContourCV 視覺輸入）
- 音訊輸出設備（用於合成器輸出）

### 3. 啟動後的視窗

程式啟動後會出現以下視窗：

1. **主視窗**：Multiverse GPU 渲染視覺效果
2. **ContourCV 視窗**：攝像頭輪廓檢測與 CV 生成
3. **控制面板**：
   - ENV1/2/3 參數控制（Attack, Decay, Sustain, Release）
   - SEQ1/2 步進編輯器與 BPM 控制
   - Multiverse 渲染參數調整

### 4. 可選視窗

透過主視窗選單開啟：

- **CV Meters**：五個 CV 通道的波形示波器
- **其他調試視窗**：根據需求開啟

## 主要功能

### CV 系統（5 個通道）

| CV 通道 | 功能 | 顏色 | 觸發來源 |
|---------|------|------|----------|
| **ENV1** | X 軸 Envelope | Light Vermillion (淡朱) | SEQ1 電壓 > SEQ2 |
| **ENV2** | Y 軸 Envelope | Silver White (銀白) | SEQ2 電壓 ≥ SEQ1 |
| **ENV3** | Anchor Envelope | Deep Crimson (深紅) | SEQ1 & SEQ2 < 5V |
| **SEQ1** | X 軸 Sequencer | Flame Vermillion (炎朱) | 步進序列 |
| **SEQ2** | Y 軸 Sequencer | Snow White (雪白) | 步進序列 |

配色靈感：日本神社除災避邪（紅白配色）

### 視覺系統

- **Multiverse**：GPU 加速的多層次視覺渲染
  - 三層互補色（120° 色相間距）
  - ENV1 控制整體色相旋轉
  - ENV2/3 控制各層飽和度

- **ContourCV**：攝像頭輪廓偵測
  - 即時邊緣檢測
  - 採樣點網格（9x7 預設）
  - CV 觸發光圈動畫（與 decay 同步）

### 音訊系統

- **採樣率**：48 kHz
- **聲道**：2（立體聲）
- **緩衝區**：512 samples
- **架構**：多線程（音訊線程 + 視訊線程）

## 停止程式

按 `Cmd+Q` 或關閉主視窗即可退出。

## 相關文件

- `VAV_20251105_ENV_Decay_Color_Unification.md` - ENV decay 同步與色彩統一
- `VAV_20251105_Hue_Rotation_Color_Scheme.md` - Multiverse 色彩方案
- `GPU_MULTIVERSE_BUGFIX_20251104.md` - GPU 渲染器修復
- `VAV_20251104_GPU_MILESTONE.md` - GPU 里程碑

## 故障排除

### 問題：攝像頭無法啟動

確認攝像頭權限已授予 Python：
- 系統偏好設定 > 隱私權與安全性 > 攝像頭

### 問題：音訊無輸出

檢查音訊設備設定：
- 確認輸出設備已連接
- 檢查系統音量設定

### 問題：視窗未出現

檢查終端輸出訊息，確認無錯誤提示。

---

**版本**：2025-11-05
**狀態**：已測試驗證
