# VAV 系統變更日誌

---

## [2025-11-18] CV Meter Mute 功能與專案整理

### CV Meter Window 功能增強
- **新增 Mute 按鈕**:
  - 每個 CV meter 左側加入 M 按鈕
  - 點擊切換 mute 狀態
  - 視覺回饋: 灰色 (啟用) / 紅色 (靜音)
  - 支援 6 個通道: ENV1-4, SEQ1-2

### 實作細節
- **修改檔案**:
  - `vav/gui/meter_widget.py`: 加入 mute UI 與點擊處理
  - `vav/gui/cv_meter_window.py`: 處理 mute 訊號傳遞
  - `vav/core/controller.py`: 套用 mute 到 CV 輸出

- **Mute 邏輯**:
  - ENV1-4 mute 時: 不發送 trigger 事件
  - SEQ1-2 mute 時: 輸出值設為 0.0
  - 使用 numpy.bool 轉 Python bool 避免 PyQt signal 錯誤
  - 使用 QRect 處理點擊區域檢測

### 專案結構整理
- **建立新目錄結構**:
  - `related_projects/`: 存放 VAV_AudioEngine, VAV_variant
  - `docs/`: 整合所有 markdown 文件
  - `archived/`: 備份舊檔案

- **新增文件**:
  - `docs/FOLDER_STRUCTURE.md`: 資料夾結構說明
  - `start_narrator.command`: Vision Narrator 啟動腳本

- **啟動腳本改進**:
  - 使用 vision_narrator 獨立 venv
  - 背景執行不顯示 terminal 訊息
  - 自動關閉 terminal 視窗

---

## [2025-11-15] Ellen Ripley 效果器整合至 Alien4

### Alien4 音訊效果器架構升級
- **Ellen Ripley 效果器完整移植**:
  - 保留 Alien4 核心功能 (Loop buffer, Slice detection, Polyphonic playback)
  - 替換 Delay/Reverb 為 Ellen Ripley 完整版本
  - 新增 ChaosGenerator (Lorenz attractor)
  - 新增 GrainProcessor (16-grain granular synthesis)

### 效果器實作細節

#### 1. ChaosGenerator (混沌產生器)
- **Lorenz attractor 實作**: 三維混沌系統
- **兩種模式**:
  - Smooth mode: 0.01-1.0 (連續變化)
  - Stepped mode: 1.0-10.0 (階梯式變化)
- **調變目標**: Delay time, Reverb decay
- **位置**: `alien4_extension.cpp:126-156`

#### 2. GrainProcessor (顆粒合成)
- **16 並行 grains**: 獨立聲音顆粒處理
- **8192 樣本緩衝**: 循環緩衝設計
- **固定參數**:
  - Position: 50% (固定)
  - Chaos: Always on (固定)
- **可調參數**:
  - Size: 顆粒大小 (內建 50%)
  - Density/Break: 顆粒密度 (內建 50%)
  - Wet/Dry: 混合比例 (GUI 可調)
- **位置**: `alien4_extension.cpp:161-295`

#### 3. DelayProcessor (延遲效果)
- **L/R 獨立 buffer**: 立體聲分離處理
- **Chaos 調變**: 可選 chaos 調變 delay time
- **參數**:
  - Time L/R: 獨立左右延遲時間
  - Feedback: 回饋量
  - Chaos toggle: 開關 chaos 調變
  - Wet/Dry: 混合比例
- **位置**: `alien4_extension.cpp:476-524`

#### 4. ReverbProcessor (殘響效果)
- **8 comb filters**: 升級自原本的 4 個
- **4 allpass filters**: Freeverb-style 架構
- **Chaos 調變**: Chaos 影響 decay time
- **參數**:
  - Decay: 殘響時間
  - Room/Tone: 固定最大值 (不在 GUI 顯示)
  - Wet/Dry: 混合比例
- **位置**: `alien4_extension.cpp:300-471`

### 訊號鏈順序
```
Input → EQ → Chaos Generation → Delay (with chaos) → Grain → Reverb (with chaos) → Feedback → Output
```

### GUI 控制配置 (Column 5)
**Delay 控制**:
- Delay Time L: 0.001-2.0s
- Delay Time R: 0.001-2.0s
- Delay Feedback: 0-95%
- Delay Wet: 0-100%

**Reverb 控制**:
- Reverb Decay: 0-100%
- Reverb Wet: 0-100%

**Chaos 控制**:
- Chaos Rate: 0-100% (調變速率)
- Chaos Shape: Smooth/Stepped toggle
- Delay Chaos: On/Off toggle

**Grain 控制**:
- Grain Wet: 0-100%

### 內建固定值
- Chaos Amount: 100% (固定)
- Grain Size: 50% (固定)
- Grain Density: 50% (固定)
- Grain Position: 50% (固定)
- Grain Chaos: Always on (固定)
- Reverb Room: 最大值 (固定)
- Reverb Tone: 最大值 (固定)

### Python Bindings 新增方法
```python
set_chaos_rate(rate)      # Chaos 速率
set_chaos_amount(amount)  # Chaos 強度
set_chaos_shape(shape)    # Chaos 模式
set_delay_chaos(enabled)  # Delay chaos 開關
set_reverb_chaos(enabled) # Reverb chaos 開關
set_grain_size(size)      # Grain 大小
set_grain_density(density)# Grain 密度
set_grain_wet_dry(wet)    # Grain 混合
```

### 修改檔案
- `alien4_extension.cpp`: C++ 效果器實作
- `vav/audio/alien4_wrapper.py`: Python 包裝層
- `vav/audio/audio_process.py`: 音訊處理整合
- `vav/core/controller.py`: 控制器方法
- `vav/gui/compact_main_window.py`: GUI 控制介面

### 技術備註
- 編譯輸出: `alien4.cpython-311-darwin.so` (216K)
- 立體聲處理: L/R 獨立 grain processors
- 音訊安全: 所有參數範圍檢查與 clamp

---

## [2025-11-15] 最低亮度調整與 Frequency Compress 參數

### 最低亮度調整
- **最暗值從 10% 提升至 25%**:
  - 原本最低亮度: 0.1 (10%)
  - 新最低亮度: 0.25 (25%)
  - 提升畫面整體對比度與視覺飽和度
  - Shader 位置: `qt_opengl_renderer.py:295`

### Frequency Compress 固定值
- **Compress 參數固定為 3.0**:
  - 原本計畫實作 compress slider 控制
  - 最終決定使用固定值 compress = 3.0
  - 降低條紋密度對頻率變化的敏感度
  - Shader 公式: `compressed_pitch_rate = pitch_rate / compress`

### Channel Ratios 預設值調整
- **預設值從 1.0 改為 0.1**:
  - 原本預設值: [1.0, 1.0, 1.0, 1.0] (條紋密集)
  - 新預設值: [0.1, 0.1, 0.1, 0.1] (條紋稀疏)
  - 對應 test_ratio_visualizer.py 測試程式中使用者偏好值
  - 讓初始條紋呈現更稀疏的視覺效果

### 修改檔案
- `vav/visual/qt_opengl_renderer.py`: 最低亮度 0.25, compress shader 實作
- `vav/core/controller.py`: channel_ratios 預設值, compress 固定值
- `vav/gui/compact_main_window.py`: 移除 compress slider

---

## [2025-11-15] Ratio 對數映射改進

### Multiverse Ratio 控制優化
- **改用對數映射取代線性映射**:
  - 原本線性映射: 0.01-10.0 (slider 0-100)
  - 改為對數映射: 0.0001-10.0 (log10 scale)
  - slider 分布: 0→0.0001, 20→0.001, 40→0.01, 60→0.1, 80→1.0, 100→10.0
  - 提供更均勻且細緻的條紋密度控制

- **測試工具開發**:
  - 建立 `test_ratio_visualizer.py` 獨立測試程式
  - 即時音訊輸入 (ES-8 Input-1) 視覺化
  - 波形顯示與條紋映射預覽
  - 對數 ratio 控制滑桿

- **實作細節**:
  - GUI: `_on_global_ratio_changed()` 使用 log10 mapping
  - Controller: ratio clip 範圍擴展到 0.0001-10.0
  - Label 顯示: <0.01 顯示 4 位小數, ≥0.01 顯示 2 位小數

### 修改檔案
- `vav/gui/compact_main_window.py`: Ratio 對數映射
- `vav/core/controller.py`: ratio clip 範圍 0.0001-10.0
- `test_ratio_visualizer.py`: 新增測試工具

---

## [2025-11-15] MIDI Button 支援與 ENV Decay 範圍擴展

### MIDI Learn 按鈕支援
- **擴展 MIDI Learn 系統支援按鈕控制**:
  - 原本只支援 CC 映射到 slider
  - 新增 Note 和 CC 映射到按鈕 toggle
  - `register_button()` 方法支援 bool toggle 回調

- **REC 按鈕 MIDI 映射**:
  - 右鍵選單支援 MIDI Learn
  - 支援 MIDI CC 和 Note On 訊息
  - CC 訊息自動轉換為 toggle (任何值都觸發)
  - 200ms 防抖動避免快速重複 toggle

- **實作細節**:
  - `MIDILearnManager.note_mappings` 儲存 note 映射
  - `button_states` 追蹤 toggle 狀態
  - `last_button_cc_time` 防抖動機制
  - 支援任意 MIDI channel 和 CC/Note 號碼
  - JSON 同時儲存 cc_mappings 和 note_mappings

### ENV Decay 範圍調整
- **最小值從 0.1s 改為 0.01s** (10ms):
  - 第一段: 0.01s ~ 1s (指數: 0.01 * 100^t)
  - 第二段: 1s ~ 5s (指數: 1.0 * 5^t)
  - 預設值設為 0 (0.01s 最快衰減)

### Alien4 Seq1 控制整合
- **Seq1 CV 同時控制 Scan 和 Len**:
  - Scan: 控制掃描位置 (0-100%)
  - Len: 透過 `set_gate_threshold()` 控制 slice length (1ms-5s)
  - GUI 即時更新兩個 slider 和 label 顯示
  - 使用指數曲線: `0.001 * 5000^value` 計算 slice length

### 其他調整
- **Scene Threshold 預設值**: 2% → 1%
- **Scan Time 最大值**: 30s → 300s (5分鐘)

### 修改檔案
- `vav/midi/midi_learn.py`: 新增 note mapping 和 button 支援
- `vav/gui/compact_main_window.py`: REC 按鈕 MIDI 支援, ENV Decay 範圍調整, Seq1 更新 Len slider
- `vav/audio/audio_process.py`: Seq1 控制 Alien4 Scan 和 Len
- `vav/cv_generator/contour_scanner.py`: Scene threshold 預設 1%

---

## [2025-11-14] CV Meters 視窗整合與 Multiverse Ratio 功能實作

### CV Meters 視窗重新設計
- **整合 Anchor XY Pad 到 Visual Preview**:
  - 移除獨立的 AnchorXYPad widget
  - 在 Visual Preview (546x230) 上直接繪製 anchor crosshair 和 ROI circle
  - 支援滑鼠拖曳直接控制 anchor 位置
  - 保留完整 MIDI Learn 功能 (Anchor X/Y)

- **Range 控制移至 CV Meters 視窗**:
  - 從 main controller 移動 Range slider 到 CV Meters 視窗
  - 垂直 slider (1-120%, default 50%) 位於 Visual Preview 左側
  - 同步更新 visual preview 的 ROI circle 和 controller

- **視窗佈局優化**:
  - Meter widget 高度增加到 200px 最小高度
  - Visual Preview 從 306 降到 230 高度
  - 視窗預設大小 560x480
  - 元件間距優化為 10px

### Scene Change Threshold 參數
- **新增可調整門檻**: Col1 Timer 下方新增 Scene 參數
  - 範圍 1-10%, 預設 2%
  - 控制輪廓重新掃描的場景變化靈敏度
  - 使用 cv2.absdiff() 偵測幀間差異

### Multiverse Ratio 功能修復與調整
- **問題分析**: Ratio 功能無作用
  - 原版 Multiverse 在 audio processing 階段做 pitch shifting
  - VAV 架構是 buffer-based 而非 sample-by-sample
  - 無法直接實作原版的 circular pitch buffer 機制

- **Shader 端實作方案**:
  - 在 shader 中用 texture coordinate 變換模擬視覺效果
  - `x_sample = uv.x * pitch_rate * 10.0`
  - **注意**: 視覺行為與原版相反但功能正常
    - ratio 小 (slider 左) → 條紋稀疏
    - ratio 大 (slider 右) → 條紋密集

- **參數範圍調整**:
  - Controller clip 範圍: 0.25-10.0 改為 0.01-10.0
  - 允許更小的 pitch_rate 值以達到更稀疏的條紋
  - 預設值改為 0.0 (最稀疏狀態)
  - Shader 係數: ×10.0 讓稀疏範圍更明顯

- **實作限制說明**:
  - 這不是真正的 pitch shifting, 只是視覺模擬
  - 方向性與原版相反 (除法/乘法理解困難)
  - 需要 GL_REPEAT texture wrapping 支援

### 修改檔案
- `vav/gui/cv_meter_window.py` - 整合 Range slider, 移除 XY Pad, 連接 controller
- `vav/gui/visual_preview_widget.py` - 整合 anchor 控制, 滑鼠事件, overlay 繪製
- `vav/gui/compact_main_window.py` - Scene threshold slider, ratio 預設值 0.0
- `vav/cv_generator/contour_scanner.py` - Scene threshold 預設 2.0
- `vav/visual/qt_opengl_renderer.py` - Ratio shader 實作, debug print
- `vav/core/controller.py` - Ratio clip 範圍 0.01-10.0

---

## [2025-11-14] Alien4 參數優化與 Seq1 控制整合

### Alien4 Poly 隨機分布優化
- **隨機 Speed 範圍擴大**: -2.0~+2.0 擴大到 -4.0~+4.0
- **Redistributive 觸發邏輯調整**:
  - Scan 改變: 觸發 redistributeVoices (支援 Seq1 控制)
  - Len 改變: 不觸發 redistributeVoices (保持穩定性)
  - Poly 改變: 觸發 redistributeVoices (原有功能)

### Seq1 控制 Alien4 Scan
- **即時控制**: Seq1 電壓 (0-1V) 直接對應 Alien4 Scan 位置
- **GUI 同步顯示**: Scan slider 即時顯示 Seq1 控制值
  - 使用 blockSignals 防止回饋迴路
  - 透過 cv_values[4] 讀取 seq1_value

### EQ 功能調整
- **Cut-only 模式**: 三頻段 EQ 改為只支援衰減
  - Low: 200Hz lowshelf, 0 到 -20dB
  - Mid: 2kHz peak, 0 到 -20dB
  - High: 8kHz highshelf, 0 到 -20dB
- **GUI 範圍更新**: Slider 範圍從 -20~+20 改為 -20~0

### Feedback 參數調整
- **最大值**: 從 0.5 改回 0.8
- **GUI 範圍**: Slider 0-80 對應 0.0-0.8
- **安全係數**: 保留 0.8x safety scaling

### Delay Time Smoothing 增強
- **Smoothing 係數**: 從 0.2 降到 0.05 (變化速度降為 1/4)
- **目的**: 防止快速調整 Delay Time 時產生破音

### 修改檔案
- `alien4_extension.cpp` - EQ cut-only, feedback 0.8, delay smoothing, redistribution 邏輯
- `vav/audio/audio_process.py` - Seq1 控制 Scan
- `vav/gui/compact_main_window.py` - EQ/Feedback slider 範圍, Scan GUI 同步

---

## [2025-11-13] 輪廓掃描變速系統與 CV 輸出優化

### 變速掃描系統
- **曲率感應變速掃描**：十字在輪廓線上移動時根據曲率動態調整速度
  - 直線段加速至 4 倍速
  - 彎道減速至 0.33 倍速
  - 使用指數映射增強曲率敏感度 (平方根)
  - 總循環時間保持在設定的 scan_time

- **速度權重計算**：
  - 計算每個點的曲率值 (0-1)
  - 增強曲率 = curvature^0.5
  - 權重範圍 0.25-3.0 對應速度 4x-0.33x
  - 使用累積時間映射確保精確時間分配

### SEQ1/2 輸出重新設計
- **改為距離 Anchor 輸出**：
  - SEQ1: X 座標到 Anchor 的距離 (0-10V)
  - SEQ2: Y 座標到 Anchor 的距離 (0-10V)

- **Range 控制放大倍數 (指數映射)**：
  - Range 1% → 8 倍放大
  - Range 120% → 2 倍放大
  - 使用反向指數曲線讓前半段快速降低
  - 輸出限制在 0-10V

### Envelope 觸發邏輯優化
- **ENV1**: X 到 Anchor 距離 > Y 到 Anchor 距離時觸發
- **ENV2**: Y 到 Anchor 距離 > X 到 Anchor 距離時觸發
- **ENV3**: 加速瞬間觸發 (速度權重降低 > 0.3)
- **ENV4**: 減速瞬間觸發 (速度權重增加 > 0.3)
- 四個 Envelope 都有 retrigger 保護

### 技術細節
- 曲率計算使用前後 2 點窗口
- 速度閾值 0.3 避免微小變化誤觸發
- 變速系統降級機制：無曲率數據時退回等速掃描

### 修改檔案
- `vav/cv_generator/contour_scanner.py` - 變速掃描、SEQ 輸出、ENV 觸發邏輯

---

## [2025-11-13] UI Layout 重構與視覺預覽功能

### UI Layout 完全重構
- **修正跨列對齊問題**：從 QGridLayout 改為 5 個獨立的 QVBoxLayout
  - 每個 column 獨立管理自己的控制項
  - 消除跨列高度干擾問題
  - 新增 `_create_control_row()` helper 確保一致的 label+control 佈局
  - 固定 label 寬度為 80px (LABEL_WIDTH) 確保 slider 對齊

- **優化視窗高度**：初始高度從 480px 降為 420px
  - 消除底部空白
  - 更好地符合內容大小

- **統一控制項高度**：所有控制項標準化為 16px 高度
  - Timer 按鈕提升至 24px 以改善可用性
  - 一致的垂直間距（控制項間 8px）

- **Multiverse slider 對齊修正**：修正 color scheme slider 位置
  - 在 checkbox 後添加 9px spacing 對齊其他 sliders
  - Column 2 所有 sliders 現在完美對齊

### 視覺預覽功能
- **新增 VisualPreviewWidget** (`vav/gui/visual_preview_widget.py`)
  - 在 CV Meter 視窗顯示主視覺輸出
  - 固定大小：273×153（與 Anchor XY Pad 相同）
  - 使用 texture 共享，CPU/GPU 負擔極小
  - 修正 RGB 顏色轉換確保正確顯示

- **更新 CV Meter Window layout**
  - Anchor XY Pad 與 Visual Preview 並排顯示
  - 使用 QHBoxLayout 水平排列
  - 視窗寬度維持 600px

### CV Overlay 控制
- **新增 CV Overlay checkbox**
  - 位於 Column 1 Track 4 vol 下方
  - 可切換主視覺上的 CV 數值顯示
  - 不影響輪廓線和圓圈顯示
  - 預設：啟用

### Audio Processing 修正
- **Sample-accurate CV output**
  - 修正 CV 輸出為逐 sample 寫入，而非填滿整個 buffer
  - Env 輸出現在正確顯示 inactive 時為 0V
  - 正確的 0-1 範圍映射到 0-10V (ES-8)

### 預設參數調整
- **Reverb Room**: 0.50 → 1.00 (最大值)
- **Reverb Damp**: 0.40 → 1.00 (最大值)
- **Reverb Decay**: 0.60 → 0.80 (80%)
- **Delay Time R**: 250ms → 300ms
- **Grain Size**: 0.30 → 0.50 (50%)

### 修改檔案
- `vav/gui/compact_main_window.py` - 主要 layout 重構
- `vav/gui/cv_meter_window.py` - 新增視覺預覽
- `vav/gui/visual_preview_widget.py` - 新 widget（新建）
- `vav/gui/meter_widget.py` - 文件更新
- `vav/core/controller.py` - CV overlay 控制
- `vav/audio/audio_process.py` - Sample-accurate CV 輸出
- `vav/visual/qt_opengl_renderer.py` - CV overlay 條件渲染

### 技術改進
- 更好的關注點分離（獨立 column layouts）
- 一致的 UI 元素大小與間距
- 減少 audio callback 的記憶體配置
- 主視窗與預覽間更有效率的 frame 共享

---

## [2025-11-12] GUI 佈局優化與錯誤修正

### GUI 改進

**1. SD 區塊垂直間距修正**
- 修正 SD Prompt QTextEdit 影響 grid 行高的問題
- 為 SD Prompt 設定 `QSizePolicy.Fixed` 避免影響下方 sliders 間距
- SD 區塊 sliders (Steps, Strength, Guidance, Gen Interval) 現在與 Multiverse sliders 使用相同垂直間距
- 檔案：`vav/gui/compact_main_window.py:503`

**2. Anchor XY Pad 移動到 CV Meters 視窗**
- 將 Anchor XY Pad 從主控制視窗移至獨立的 CV Meters 視窗
- CV Meters 視窗高度從 210 增加到 370 (增加 160px)
- 完整保留 MIDI Learn 功能：
  - Anchor X/Y 參數註冊
  - Y 軸反轉邏輯 (MIDI 0-100 → GUI 100-0)
  - 右鍵選單支援 MIDI Learn X/Y、清除映射
- `position_changed` signal 正常連接到 controller
- Range slider 更新 XY Pad 的 ROI 圓圈顯示
- 檔案：
  - `vav/gui/cv_meter_window.py`: 新增 `setup_midi_learn()` 方法
  - `vav/gui/compact_main_window.py`: 移除主視窗 XY Pad，連接到 CV Meter Window

### Bug 修正

**LFO Pattern IndexError 修正**
- 問題：`_update_lfo()` 在初始化過程中可能存取未生成的 patterns
- 錯誤：`IndexError: list index out of range` at `contour_scanner.py:790`
- 解決：在 `_update_lfo()` 加入防禦性檢查
- 檢查 `len(self.lfo_patterns) != 8` 時立即重新生成 patterns
- 避免初始化過程的競態條件
- 檔案：`vav/cv_generator/contour_scanner.py:783-786`

### 技術細節

**QSizePolicy 修正**
```python
self.sd_prompt_edit.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
```
- 防止 40px 高的 TextEdit 影響 QGridLayout 的行高分配
- 確保所有 slider 行使用統一的垂直間距 (10px)

**CV Meter Window MIDI 整合**
```python
def setup_midi_learn(self, midi_learn):
    self.midi_learn = midi_learn
    # 註冊 anchor_x, anchor_y 參數
    # 設定 context menu 與 callbacks
```

**LFO 防禦性檢查**
```python
if len(self.lfo_patterns) != 8:
    self._generate_lfo_patterns()
    return
```

---

## [2025-11-12] 色彩方案與混合模式連續化改進

### 新增功能

**1. 色彩方案連續調整**
- 將色彩方案下拉選單改為連續性滑桿（Fader）
- 支援三種方案之間的平滑漸變混合：
  - 0.0-0.5: Quad90（90度四色）→ Tri+Contrast（三色+對比）
  - 0.5-1.0: Tri+Contrast → Tri+Between（三色+中間色）
- 移除色彩方案標籤，保持介面簡潔
- 支援 MIDI Learn 即時控制

**2. Blend 模式連續調整**
- 將 Blend 模式下拉選單改為連續性滑桿
- 支援四種混合模式之間的平滑漸變：
  - 0.0-0.33: Add → Screen
  - 0.33-0.66: Screen → Difference
  - 0.66-1.0: Difference → Color Dodge
- 保留 "Blend" 標籤
- 支援 MIDI Learn 即時控制

**3. Shader 實作漸變混合邏輯**
- 色彩方案：計算三種方案的 HSV 值，使用 mix() 在 HSV 空間插值
- Blend 模式：計算四種模式的結果，使用 mix() 在 RGB 空間插值
- 參數類型從 int 改為 float (0.0-1.0)

### 修改內容

**GUI (compact_main_window.py)**
- 移除 color_scheme_combo 和 blend_mode_combo
- 新增 color_scheme_slider 和 blend_mode_slider
- 範圍：0-100，映射到 0.0-1.0
- 預設值：color_scheme=50 (Tri+Contrast), blend_mode=0 (Add)

**Controller (controller.py)**
- set_renderer_blend_mode(): 參數從 int 改為 float
- set_color_scheme(): 參數從 int 改為 float
- 移除 blend mode 名稱索引，改為顯示數值

**Renderer (qt_opengl_renderer.py)**
- blend_mode 和 color_scheme 從 int 改為 float
- getChannelColor(): 實作三種色彩方案的漸變混合
- blendColors(): 實作四種混合模式的漸變混合
- Shader uniform 類型更新為 float

### 視覺效果改進

**1. Multiverse 最低亮度調整**
- 從 0.2 (20%) 降低到 0.1 (10%)
- 減少過度飽和，讓 blend 模式效果更明顯
- 避免多層疊加時快速變白

**2. Base Hue 範圍調整**
- 最大值從 360 改為 333
- 轉換公式：value / 333.0

**3. Camera Mix 範圍限制**
- 最大值從 100 改為 30 (0.0-0.3)
- 降低敏感度，避免 camera 過亮
- 標籤顯示精度提升到小數點後兩位

### Region Map 與 Blend 模式整合

**問題修正**
- Region Map 開啟時，每個像素只有一個通道，無法展現 blend 效果
- 修改邏輯：不屬於 region 的通道直接跳過 (continue)，而非設為黑色
- Camera/SD 畫面參與 blend 混合，作為第二個混合對象
- 確保 blend 模式在 region map 模式下仍然有效

**實作細節**
- Shader 中提前過濾 region（第 229-231 行）
- Camera/SD 使用相同的 blendColors 函數
- Camera mix 控制混合強度

### 效能優化

**SD Img2Img 加速**
- Resize 演算法：LANCZOS → BILINEAR
- 輸入 resize (512x512): 改用 BILINEAR
- 輸出 resize (1280x720): 改用 BILINEAR
- 速度提升：0.45-0.47s → 0.39s (約快 60-80ms)
- 當前 fps: ~2.56 fps

### 技術細節

**Shader 漸變混合實作**
```glsl
// 色彩方案混合
vec3 hsv_result;
if (color_scheme < 0.5) {
    float t = color_scheme * 2.0;
    hsv_result = mix(scheme1_hue, scheme2_hue, t);
} else {
    float t = (color_scheme - 0.5) * 2.0;
    hsv_result = mix(scheme2_hue, scheme3_hue, t);
}

// Blend 模式混合
if (mode < 0.33) {
    float t = mode / 0.33;
    result = mix(add_result, screen_result, t);
} else if (mode < 0.66) {
    float t = (mode - 0.33) / 0.33;
    result = mix(screen_result, diff_result, t);
} else {
    float t = (mode - 0.66) / 0.34;
    result = mix(diff_result, dodge_result, t);
}
```

### 檔案修改
- vav/gui/compact_main_window.py: GUI 介面改為滑桿
- vav/core/controller.py: 參數類型更新、blend mode 顯示調整
- vav/visual/qt_opengl_renderer.py: Shader 漸變混合實作
- vav/visual/sd_img2img_process.py: Resize 演算法優化

### 已知限制
- SD 速度受 GPU 和模型限制，目前約 2.5 fps
- 要達到 20 fps 需要更激進的優化（降低解析度、TensorRT 等）

---

## [2025-11-11] Region Map 開關失效問題修復

### 問題修復

**Region Map 無法關閉的 bug**
- 使用者反應開關 Region Map checkbox 時畫面沒有變化
- 經診斷發現 controller.py:599 預設值設為 True 導致 region map 無法關閉
- 即使 use_region_rendering=False 仍會傳 camera_frame 給 renderer

**修正內容**
- controller.py:599 use_gpu_region 預設值改為 False
- controller.py:616 CPU region mode 明確設為 False
- 確保 region map 關閉時不會傳遞 region 相關資料給 renderer

**測試確認**
- Region Map ON 正常顯示分區效果
- Region Map OFF 正常顯示全畫面混合效果
- 開關切換即時生效

---

## [2025-11-11] Region Map 診斷與除錯工具添加

### 問題診斷

**Region Map 開關失效問題調查**
