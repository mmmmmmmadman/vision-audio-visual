# VAV

**Vision-Audio-Visual System for Eurorack**

---

## EN

Real-time visual synthesis system. Camera and audio input, CV output.

### Install
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 main_compact.py
```

### Requirements
- macOS 12+ only (Windows not supported)
- Python 3.11+
- DC-coupled output audio interface (for CV output)
- Webcam or video file

### Audio
- 4-channel mixer
- Stereo Delay
- Granular Sampler
- Reverb
- Glitch
- Chaos modulation

### Visual
- OpenGL real-time rendering
- 4-channel audio-reactive visuals (V2: load 4 images to fill camera regions)
- Glitch Shader (Region Tear / Scanline Jitter / Block Shuffle)
- Stable Diffusion Img2Img real-time AI generation
- Camera / video file switching

### CV Output
- Contour detection driven 2-channel CV generation
- 3-channel Decay Envelope generation

### Control
- MIDI Learn (right-click any control)
- MIDI CC / Note Toggle support

---

## 中文

即時視覺合成系統。攝影機與音訊輸入，CV 輸出。

### 安裝
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 main_compact.py
```

### 需求
- 僅支援 macOS 12+（不支援 Windows）
- Python 3.11+
- DC-coupled 輸出音訊介面（用於 CV 輸出）
- 攝影機或影片檔案

### 音訊功能
- 4 通道混音器
- Stereo Delay
- Granular Sampler
- Reverb
- Glitch
- Chaos 調變

### 視覺功能
- OpenGL 即時渲染
- 4 通道音訊反應視覺（V2: 載入 4 個影像填入攝影機畫面）
- Glitch Shader（Region Tear / Scanline Jitter / Block Shuffle）
- Stable Diffusion Img2Img 即時 AI 生圖
- 攝影機 / 影片檔案切換

### CV 輸出
- 輪廓偵測驅動 2 軌 CV 生成
- 3 軌 Decay Envelope 生成

### 控制
- MIDI Learn（右鍵任意控制項）
- 支援 MIDI CC / Note Toggle

---

## 日本語

リアルタイム映像合成システム。カメラとオーディオ入力、CV 出力。

### インストール
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 main_compact.py
```

### 必要環境
- macOS 12+ のみ（Windows 非対応）
- Python 3.11+
- DC-coupled 出力対応オーディオインターフェース（CV 出力用）
- ウェブカメラまたは動画ファイル

### オーディオ
- 4チャンネルミキサー
- ステレオディレイ
- グラニュラーサンプラー
- リバーブ
- グリッチ
- Chaos モジュレーション

### ビジュアル
- OpenGL リアルタイムレンダリング
- 4チャンネル オーディオリアクティブ映像（V2: 4つの画像をカメラ領域に充填）
- グリッチシェーダー（Region Tear / Scanline Jitter / Block Shuffle）
- Stable Diffusion Img2Img リアルタイム AI 画像生成
- カメラ / 動画ファイル切替

### CV 出力
- 輪郭検出による 2チャンネル CV 生成
- 3チャンネル Decay Envelope 生成

### コントロール
- MIDI Learn（右クリックで割り当て）
- MIDI CC / Note Toggle 対応

---

## Demo

Live performance in Osaka: https://youtu.be/C0OXfQM1N-o

---

## License

MIT License - MADZINE 2025
