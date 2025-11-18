# Vision Narrator 與 VAV 系統整合方案

## 專案狀態

**目前階段**: 獨立開發
**目標**: 整合至 VAV 主程式
**用途**: 為 VAV 系統提供即時視覺描述與多語言播報功能

## 開發時程

- **2025-01-17**: 獨立 Vision Narrator 開發完成
  - 實作音訊快取系統
  - 多語言模式並行音訊生成
  - 循環播放功能消除音訊間隙
  - MLX 視覺模型執行緒安全保護
  - GUI 完全英文化
  - 移除音量控制，改為阻塞式播放搭配音訊循環

- **下一階段**: VAV 整合規劃
  - 分析 VAV 主程式架構
  - 設計整合介面
  - 規劃模組相容性與依賴解析

## 概述

Vision Narrator 是一個獨立的視覺描述與語音播報系統，可與 VAV (Visual Audio Visualizer) 專案整合，創造多層次的視聽體驗。

## 整合策略

### 方案 1：獨立運行，共享攝影機

**架構**:
```
攝影機
├─> Vision Narrator (高階語意理解 + 語音)
└─> VAV (低階視覺特徵 + CV 輸出)
```

**優點**:
- 兩個系統獨立運作，不互相干擾
- 可分別調整參數
- 穩定性高

**缺點**:
- 攝影機可能無法同時被兩個程式存取
- 需要兩個終端視窗

**實作**:
```bash
# 終端 1: 啟動 VAV
cd /Users/madzine/Documents/VAV
source venv/bin/activate
python main_compact.py

# 終端 2: 啟動 Vision Narrator
cd /Users/madzine/Documents/VAV/vision_narrator
source venv/bin/activate
python narrator.py
```

### 方案 2：Vision Narrator 作為 VAV 的子模組

**架構**:
```
VAV 主程式
├─> 視覺處理 (輪廓掃描、CV 生成)
├─> 音訊處理 (Alien4 效果鏈)
└─> Vision Narrator (語意描述、語音播報)
```

**整合步驟**:

#### 1. 將 Vision Narrator 模組複製到 VAV

```bash
cp -r /Users/madzine/Documents/VAV/vision_narrator/modules \
      /Users/madzine/Documents/VAV/vav/vision_narrator
```

#### 2. 在 VAV 中創建整合類別

創建 `/Users/madzine/Documents/VAV/vav/vision_narrator/integrated_narrator.py`:

```python
"""
整合 Vision Narrator 到 VAV
"""
import time
import threading
from typing import Optional
import numpy as np

class IntegratedVisionNarrator:
    """整合到 VAV 的視覺描述器"""

    def __init__(self, vision_backend="mlx-vlm", tts_backend="edge-tts"):
        from .modules import VisionDescriptor, TTSEngine

        self.vision = VisionDescriptor(backend=vision_backend)
        self.tts = TTSEngine(backend=tts_backend, language="zh-TW")

        self.enabled = False
        self.last_description_time = 0
        self.description_interval = 10  # 秒

    def describe_frame(self, frame_rgb: np.ndarray) -> Optional[str]:
        """
        描述畫面（非阻塞）

        Args:
            frame_rgb: RGB 格式的畫面

        Returns:
            描述文字，如果尚未到間隔時間則回傳 None
        """
        if not self.enabled:
            return None

        current_time = time.time()

        if current_time - self.last_description_time < self.description_interval:
            return None

        # 生成描述（在背景執行緒）
        def generate_and_speak():
            description = self.vision.describe(frame_rgb)
            print(f"\n[Vision Narrator] {description}\n")
            self.tts.speak(description, blocking=False)

        thread = threading.Thread(target=generate_and_speak, daemon=True)
        thread.start()

        self.last_description_time = current_time
        return "Generating description..."

    def set_enabled(self, enabled: bool):
        """啟用/停用描述功能"""
        self.enabled = enabled

    def set_interval(self, seconds: int):
        """設定描述間隔"""
        self.description_interval = max(5, seconds)
```

#### 3. 在 VAV 主程式中整合

修改 `/Users/madzine/Documents/VAV/main_compact.py`:

```python
# 在 imports 區域新增
from vav.vision_narrator.integrated_narrator import IntegratedVisionNarrator

# 在 VAVApplication.__init__ 中新增
self.narrator = IntegratedVisionNarrator(
    vision_backend="mlx-vlm",
    tts_backend="edge-tts"
)

# 在處理影像的迴圈中新增
# (在 contour_scanner.process_frame 之後)
if hasattr(self, 'narrator'):
    self.narrator.describe_frame(frame_rgb)
```

#### 4. 在 GUI 中新增控制

在 `/Users/madzine/Documents/VAV/vav/gui/compact_main_window.py` 新增控制項：

```python
# 新增 Vision Narrator Tab
narrator_tab = QWidget()
narrator_layout = QVBoxLayout()

# 啟用/停用
self.narrator_enabled_cb = QCheckBox("啟用語音描述")
self.narrator_enabled_cb.stateChanged.connect(self._on_narrator_toggle)
narrator_layout.addWidget(self.narrator_enabled_cb)

# 描述間隔
narrator_layout.addWidget(QLabel("描述間隔 (秒):"))
self.narrator_interval_slider = QSlider(Qt.Horizontal)
self.narrator_interval_slider.setRange(5, 60)
self.narrator_interval_slider.setValue(10)
self.narrator_interval_slider.valueChanged.connect(self._on_narrator_interval)
narrator_layout.addWidget(self.narrator_interval_slider)

narrator_tab.setLayout(narrator_layout)
self.tabs.addTab(narrator_tab, "語音描述")

# 處理函數
def _on_narrator_toggle(self, state):
    if hasattr(self.app, 'narrator'):
        self.app.narrator.set_enabled(state == Qt.Checked)

def _on_narrator_interval(self, value):
    if hasattr(self.app, 'narrator'):
        self.app.narrator.set_interval(value)
```

### 方案 3：語音輸出作為音訊調變源

**架構**:
```
Vision Narrator
    ├─> 生成語音檔案
    └─> 傳遞給 VAV audio_process
            └─> 語音韻律調變視覺效果
```

**實作**:

#### 1. 修改 TTS 引擎儲存音訊

在 `tts_engine.py` 新增：

```python
def generate_audio_array(self, text: str) -> np.ndarray:
    """
    生成語音但不播放，回傳音訊陣列

    Returns:
        np.ndarray: 音訊陣列 (sample_rate, channels)
    """
    audio_file = os.path.join(self.temp_dir, "speech.wav")

    # 生成語音
    if self.backend == "edge-tts":
        # ... 生成到檔案
        pass
    elif self.backend == "coqui":
        # ... 生成到檔案
        pass

    # 讀取音訊檔案
    import scipy.io.wavfile as wav
    sample_rate, audio_data = wav.read(audio_file)

    return audio_data, sample_rate
```

#### 2. 在 VAV 中接收音訊

```python
# 在 audio_process.py 新增
speech_audio, speech_sr = narrator.tts.generate_audio_array(description)

# 重新取樣到 VAV 的 sample rate
from scipy.signal import resample
speech_resampled = resample(speech_audio,
                            int(len(speech_audio) * sample_rate / speech_sr))

# 混合到主音訊輸出
# 或用語音的包絡調變 Alien4 參數
envelope = np.abs(speech_resampled)
alien4.set_reverb_wet(envelope_to_cv(envelope))
```

### 方案 4：OSC 通訊

**架構**:
```
Vision Narrator (OSC Server)
    └─> /vision/description "畫面中有一個人"
    └─> /vision/sentiment 0.8 (正向情感)

VAV (OSC Client)
    └─> 接收描述
    └─> 根據情感調整視覺參數
```

**實作**:

#### 1. Vision Narrator 發送 OSC

```bash
pip install python-osc
```

```python
from pythonosc import udp_client

# 在 IntegratedVisionNarrator 中
self.osc_client = udp_client.SimpleUDPClient("127.0.0.1", 5005)

def send_description(self, description: str):
    self.osc_client.send_message("/vision/description", description)

    # 分析情感（簡單版本）
    positive_words = ["美好", "明亮", "快樂"]
    sentiment = sum(1 for word in positive_words if word in description) / 10
    self.osc_client.send_message("/vision/sentiment", sentiment)
```

#### 2. VAV 接收 OSC

```python
from pythonosc import dispatcher, osc_server

def handle_description(unused_addr, description):
    print(f"收到描述: {description}")

def handle_sentiment(unused_addr, sentiment):
    # 根據情感調整參數
    if sentiment > 0.5:
        # 正向 - 明亮的顏色
        set_color_palette("bright")
    else:
        # 負向 - 暗沉的顏色
        set_color_palette("dark")

disp = dispatcher.Dispatcher()
disp.map("/vision/description", handle_description)
disp.map("/vision/sentiment", handle_sentiment)

server = osc_server.ThreadingOSCUDPServer(("127.0.0.1", 5005), disp)
server.serve_forever()
```

## 推薦方案

根據不同需求選擇：

1. **簡單測試**：方案 1 (獨立運行)
2. **深度整合**：方案 2 (子模組)
3. **音訊調變**：方案 3 (語音作為調變源)
4. **靈活通訊**：方案 4 (OSC)

或組合使用：**方案 2 + 方案 4**，既整合又保持模組間的鬆耦合。

## 下一步

選擇一個方案後，可以：

1. 測試獨立運行
2. 實作基礎整合
3. 調整參數優化體驗
4. 記錄最佳配置

---

需要協助實作特定方案請告知。
