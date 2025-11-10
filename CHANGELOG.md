# VAV 系統變更日誌

---

## [2025-11-11] Multiverse 視覺跳動修復與 ENV 圈圈恢復

### 修復內容

#### 1. Multiverse 視覺跳動問題修復
**問題**: Multiverse 畫面劇烈跳動閃爍 音訊輸出正常

**根本原因**:
- 錯誤的 display buffer 實作引用未定義變數 導致 Multiverse 損壞
- 缺少 shared memory buffers 用於跨 process 音訊資料傳遞
- 缺少 circular buffer 和 downsampling 機制

**解決方案** (參考 Multiverse.cpp):
- 實作 circular display buffer with downsampling
- 50ms 視窗 2400 samples @ 48kHz downsampled to 1920 pixels
- 使用 multiprocessing.RawArray 實作跨 process shared memory
- Buffer size 使用 camera width (1920) 而非 audio buffer size (128)

**修改檔案**:
- `vav/audio/audio_process.py`
  - Lines 25-59: 新增 display buffer 參數和 per-channel state
  - Lines 251-273: 實作 circular buffer with downsampling
  - Lines 307-314: 修正 shared_audio_buffers size 使用 display_width

**技術特點**:
- GPU-based 完全在 GPU shader 中渲染
- 無鎖設計 視覺 thread 直接讀取 shared memory
- Downsampling 每 samplesPerPixel 寫入一次
- 與 Multiverse.cpp 邏輯一致

#### 2. Ratio 參數分析
**問題**: Channel 3/4 視覺上 ratio 看起來較高

**分析結果**:
- Shader 中所有 channel ratio 處理邏輯完全相同
- 預設 rotation angle 不同: Ch1=0° Ch2=45° Ch3=90° Ch4=135°
- 90° 和 135° 旋轉讓波形視覺上 stripe density 更高
- Ratio 實作無誤 視覺差異來自 rotation angle

#### 3. ENV 觸發圈圈恢復
**變更**: 恢復 ENV1/ENV2/ENV3 觸發時的彩色擴張圓圈動畫

**效能影響**: 增加約 3-5ms 不影響 30fps

**修改檔案**:
- `vav/cv_generator/contour_scanner.py` (lines 472-484)

---

## [2025-11-10] 視覺優化、程式碼清理與 MIDI 控制強化

### 視覺優化
- ROI 圓圈改為白色半透明 1px 線條
- 移除主視覺的 Anchor 十字標記

### MIDI 控制強化
- Anchor X/Y 支援 MIDI Mapping
  - 右鍵點擊 XY Pad 可選擇 "MIDI Learn Anchor X" 或 "MIDI Learn Anchor Y"
  - Y 軸方向已反轉：MIDI 值 0-100 對應 GUI 100-0

### 效果器預設值調整
- Grain Chaos 預設開啟
- Buffer Size 預設值改為 128 samples

### 程式碼清理
**移除未使用的模組**：
- `vav/vision/cable_detector.py` - Cable 偵測功能
- `vav/vision/analyzer.py` - Cable 分析功能
- `vav/visual/sd_shape_generator.py` - Stable Diffusion 形狀生成
- `vav/io/` - 空目錄

**移除未使用的功能**：
- Controller 中的主程序 Mixer（audio_process 的 Mixer 仍保留使用）
- Controller 中的 AudioAnalyzer
- `set_mixer_params()` 方法

**修改檔案**：
- `vav/cv_generator/contour_scanner.py` (lines 431-442)
- `vav/audio/effects/ellen_ripley.py` (line 46)
- `vav/gui/anchor_xy_pad.py` (lines 5, 30-38)
- `vav/gui/compact_main_window.py` (lines 8, 780, 817-850)
- `vav/utils/config.py` (line 16)
- `vav/core/controller.py` (lines 15-17, 48, 98-102, 229-233, 634-645 removed)
- `vav/gui/device_dialog.py` (lines 110, 116)

---

## [2025-11-04] GPU 渲染器優化與程式碼清理

### 優化內容

#### 1. Frame Skip 優化（方案 A）

**變更**：
- 將 frame_skip 從 2 改為 1
- 處理每一幀而非跳幀

**修改檔案**：
```python
# vav/core/controller.py line 348
frame_skip = 1  # Process all frames (FPS optimization test)
```

**效果**：
- 無 Region mode：24 FPS（從原始 10 FPS 提升 2.4 倍）
- 有 Region mode：16-21 FPS（Region 處理仍為瓶頸）

---

#### 2. 移除 PBO 優化（方案 C）

**決策理由**：
- PBO (Pixel Buffer Object) 雙緩衝在 macOS 統一記憶體架構上效果不佳
- 測試結果顯示 PBO 反而比直接 readback 慢 35.8%
  - Direct readback: 204.7 FPS
  - PBO readback: 133.8 FPS
- macOS Metal backend 與 PBO 不相容，無明顯效能提升

**移除內容**：
1. `__init__` 的 `enable_pbo` 參數
2. PBO 成員變數（`self.pbos`, `self.pbo_index`, `self.pbo_next_index`）
3. `_create_pbos()` 方法
4. `_readback_with_pbo()` 方法
5. `_readback_direct()` 方法（整合回 paintGL）
6. `paintGL()` 中的 PBO 條件邏輯
7. `cleanup()` 中的 PBO 清理程式碼

**簡化後的 paintGL**：
```python
# vav/visual/qt_opengl_renderer.py paintGL
if not self.display_mode:
    # Readback mode: Read pixels from FBO to CPU memory
    try:
        glBindFramebuffer(GL_FRAMEBUFFER, self.final_fbo)
        pixels = glReadPixels(0, 0, self.render_width, self.render_height,
                             GL_RGB, GL_UNSIGNED_BYTE)
        self.rendered_image = np.frombuffer(pixels, dtype=np.uint8).reshape(
            (self.render_height, self.render_width, 3))
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
    except Exception as e:
        print(f"[Qt OpenGL] Readback error: {e}, returning black screen")
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        self.rendered_image = np.zeros((self.render_height, self.render_width, 3), dtype=np.uint8)
```

**效果**：
- 程式碼更簡潔（移除 100+ 行 PBO 相關程式碼）
- FPS 維持在 24 FPS（與 PBO 版本相同）
- 移除不必要的複雜度

---

### 檔案清理

**刪除的測試檔案**：
- `test_pbo_optimization.py` - PBO 效能測試（已過時）
- `test_display_mode.py` - Display mode FPS 測試（已過時）

**修改的檔案**：
- `vav/visual/qt_opengl_renderer.py` - 移除 PBO 相關程式碼，簡化 readback 邏輯
- `vav/core/controller.py` (line 348) - Frame skip 優化

---

### 效能測試結果

| 測試場景 | 方案 A (frame_skip=1) | 備註 |
|---------|---------------------|------|
| 無 Region mode | 24 FPS | 2.4x 提升（原始 10 FPS） |
| 有 Region mode | 16-21 FPS | Region 處理瓶頸（cv2.cvtColor） |

**結論**：
- 方案 A 達成優化目標（24 FPS）
- 方案 C (PBO) 在 macOS 上無效，已移除
- Region mode 仍為主要瓶頸（CPU-bound）

---

## [2025-11-03] GPU Multiverse 渲染器修復

### 修復內容

#### 1. Time Window 不匹配修正

**問題**：
- VAV 使用 100ms time window (4800 samples @ 48kHz)
- 原始 Multiverse.cpp 使用 50ms time window
- 導致視覺 ratio 與原始版本不同

**修復**：
```python
# vav/core/controller.py line 91
self.audio_buffer_size = 2400  # 50ms at 48kHz (matches Multiverse.cpp)
```

#### 2. GPU 渲染器線條問題修正（主要修復）

**問題**：
- GPU (Qt OpenGL) 渲染器顯示密集垂直線條
- CPU (Numba) 渲染器正常
- 線條隨波形滾動

**根本原因**：
- Texture 上傳時使用了不必要的 `.T` 轉置
- `audio_data` shape `(4, 1920)` 的 C-contiguous 布局已經符合 OpenGL row-major 格式
- 轉置破壞了記憶體連續性，導致 Metal backend 產生 artifacts

**修復**：
```python
# vav/visual/qt_opengl_renderer.py lines 538-544
# 移除 .T 轉置
glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, self.render_width, 4,
               GL_RED, GL_FLOAT, self.audio_data)  # 不需要轉置
```

### 測試結果

- ✓ CPU 渲染器：正常
- ✓ GPU 渲染器：正常（與 CPU 一致）
- ✓ 性能：30-60 FPS @ 1920x1080

### 修改的文件

1. `vav/core/controller.py` (line 91) - Audio buffer size
2. `vav/visual/qt_opengl_renderer.py` (lines 538-544) - Texture upload

### 文件整理

**新增**：
- `archived/GPU_RENDERER_FIX_20251103.md` - 詳細修復記錄

**移動到 archived/**：
- `QT_OPENGL_FIX_REPORT.md`
- `QT_OPENGL_THREADING_FIX.md`
- `THREADING_FIX_SUMMARY.md`
- `RENDERER_USAGE.md`
- `TESTING_CHECKLIST.md`
- `GPU_MULTIVERSE_REWRITE_PLAN.md`
- `shader_verification_checklist.md`

**刪除**：
- `test_qt_opengl.py`
- `test_qt_opengl_visual.py`
- `test_qt_opengl_final.py`
- `test_qt_opengl_threading.py`

### Git Tag

```
VAV_20251103 - GPU Multiverse Renderer 修復完成
```

---

## [2025-10-21] GUI 控制優化與音訊路由重構

### 改進內容

#### 1. SD Generation Interval 文字輸入（無範圍限制）

**變更**：
- 從 slider（0.5-3.0s）改為文字輸入框（QLineEdit）
- 無範圍限制（可輸入任意數值，例如 180s = 3 分鐘）
- 按下 Enter 更新數值
- 無效輸入時保留文字但不更新後端

**修改檔案**：
- `vav/gui/compact_main_window.py` - 移除 slider，新增 QLineEdit

**程式碼**：
```python
# SD Generation Interval (text input)
grid.addWidget(QLabel("Gen Interval"), row3, COL3)
self.sd_interval_input = QLineEdit()
self.sd_interval_input.setText("0.5")
self.sd_interval_input.setFixedWidth(60)
self.sd_interval_input.returnPressed.connect(self._on_sd_interval_changed)
grid.addWidget(self.sd_interval_input, row3, COL3 + 1)
grid.addWidget(QLabel("s"), row3, COL3 + 2)

def _on_sd_interval_changed(self):
    try:
        interval = float(self.sd_interval_input.text())
        self.controller.set_sd_img2img_interval(interval)
    except ValueError:
        pass  # 無效輸入，不更新後端
```

**效果**：
- 使用者可設定任意長的生成間隔（如 60s、180s 等）
- 適合慢速生成或省電模式

---

#### 2. CV Meters 獨立視窗

**變更**：
- CV Meters 從主視窗移除，改為獨立可調整大小的視窗
- 視窗標題：「CV Meters」
- 預設大小：500x180
- 自動顯示（程式啟動時自動開啟）
- SEQ1/2 色條顏色從黃色/洋紅改為白色

**新增檔案**：
- `vav/gui/cv_meter_window.py` (36 行) - 獨立 CV Meters 視窗

**修改檔案**：
- `vav/gui/meter_widget.py` - 顏色變更、QSizePolicy.Expanding、動態寬度計算
- `vav/gui/compact_main_window.py` - 移除 meter widget，創建獨立視窗
- `vav/core/controller.py` - 更新 CV Meters 視窗引用

**cv_meter_window.py**：
```python
class CVMeterWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CV Meters")
        self.resize(500, 180)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self.meter_widget = MeterWidget(num_channels=5)
        layout.addWidget(self.meter_widget)
```

**meter_widget.py 顏色變更**：
```python
self.colors = [
    QColor(255, 133, 133),  # ENV 1 - 粉色
    QColor(255, 255, 255),  # ENV 2 - 白色
    QColor(188, 0, 45),     # ENV 3 - 日本國旗紅
    QColor(255, 255, 255),  # SEQ 1 - 白色（原為黃色）
    QColor(255, 255, 255),  # SEQ 2 - 白色（原為洋紅）
]
```

**meter_widget.py 動態寬度**：
```python
# 設置 size policy 讓 widget 可以水平擴展
self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

# 寬度計算
value_text_width = 50
margin = 10
available_width = width - label_width - value_text_width - margin
meter_width = max(100, available_width)  # 填滿可用空間
```

**效果**：
- CV Meters 可獨立調整大小
- Meter 寬度跟隨視窗寬度變化
- 主視窗更簡潔

---

#### 3. 掃描線粗細統一控制

**變更**：
- 新增「Line Thick」文字輸入框（單位：px）
- 統一控制 X 和 Y 軸掃描線粗細
- 按下 Enter 更新數值
- 無效輸入時不更新後端

**修改檔案**：
- `vav/gui/compact_main_window.py` - 新增 Line Thick 輸入框
- `vav/cv_generator/contour_cv.py` - 新增 thickness 參數
- `vav/core/controller.py` - 新增統一設定方法

**compact_main_window.py**：
```python
# Scan Line Thickness
grid.addWidget(QLabel("Line Thick"), row1, COL1)
self.scan_thick_input = QLineEdit()
self.scan_thick_input.setText("1")
self.scan_thick_input.setFixedWidth(60)
self.scan_thick_input.returnPressed.connect(self._on_scan_thick_changed)
grid.addWidget(self.scan_thick_input, row1, COL1 + 1)
grid.addWidget(QLabel("px"), row1, COL1 + 2)

def _on_scan_thick_changed(self):
    try:
        thickness = int(self.scan_thick_input.text())
        self.controller.set_contour_scan_line_thickness(thickness)
    except ValueError:
        pass
```

**contour_cv.py**：
```python
# In __init__
self.scan_line_thickness_x = 1
self.scan_line_thickness_y = 1

def set_scan_line_thickness_x(self, thickness: int):
    self.scan_line_thickness_x = max(1, int(thickness))

def set_scan_line_thickness_y(self, thickness: int):
    self.scan_line_thickness_y = max(1, int(thickness))

# Drawing
cv2.line(output, (scan_x_pixel, 0), (scan_x_pixel, height - 1),
         scan_color, self.scan_line_thickness_x)
cv2.line(output, (0, scan_y_pixel), (width - 1, scan_y_pixel),
         scan_color, self.scan_line_thickness_y)
```

**controller.py**：
```python
def set_contour_scan_line_thickness(self, thickness: int):
    """統一設定 X/Y 掃描線粗細"""
    if self.contour_cv_generator:
        self.contour_cv_generator.set_scan_line_thickness_x(thickness)
        self.contour_cv_generator.set_scan_line_thickness_y(thickness)
```

**效果**：
- 使用者可調整掃描線粗細（1px - 任意粗細）
- X/Y 軸同步變化

---

#### 4. 音訊路由重構（4 Mono Inputs → Mono Mix → Stereo Effects）

**變更**：
- **輸入**：Input 1-4（mono each）→ Track 0-3
- **Mixer**：4 個 mono tracks 混音後輸出 mono sum
- **效果器**：Ellen Ripley 接收 mono input，輸出 stereo
- **輸出**：Output 1-2（stereo）

**舊架構**：
- Input 1-2（stereo）→ Track 0
- Input 3-4（unused）
- Mixer 輸出 stereo → Ellen Ripley（stereo to stereo）

**新架構**：
```
Input 1 → Track 0
Input 2 → Track 1
Input 3 → Track 2
Input 4 → Track 3
    ↓
Mixer (4 mono tracks, 各有 volume/pan)
    ↓
Mono sum (left_mix + right_mix) * 0.5
    ↓
Ellen Ripley (mono in → stereo out + chaos CV)
    ↓
Output 1-2 (stereo)
Output 3-7 (CV: ENV1, ENV2, ENV3, SEQ1, SEQ2)
```

**修改檔案**：
- `vav/core/controller.py` - 音訊路由邏輯

**controller.py audio_callback**：
```python
# 準備 4 個 track 的輸入（mono → stereo per track）
track_inputs = []
for i in range(4):
    if i < indata.shape[1]:
        mono_in = indata[:, i]
        track_l = mono_in
        track_r = mono_in
    else:
        track_l = np.zeros(frames, dtype=np.float32)
        track_r = np.zeros(frames, dtype=np.float32)
    track_inputs.append((track_l, track_r))

# Mixer 處理 4 個 track
left_mix, right_mix = self.mixer.process(track_inputs)

# 混音到 mono
mono_mix = (left_mix + right_mix) * 0.5

# Ellen Ripley (mono → stereo)
if self.ellen_ripley_enabled and self.ellen_ripley:
    left_out, right_out, chaos_cv = self.ellen_ripley.process(mono_mix, mono_mix)
else:
    left_out = mono_mix
    right_out = mono_mix

# 輸出
outdata[:, 0] = left_out
outdata[:, 1] = right_out
```

**效果**：
- 4 個獨立 mono 輸入可分別調整 volume/pan
- Mixer 輸出 mono sum 送入 Ellen Ripley
- Ellen Ripley 將 mono 展開為 stereo（delay/grain/reverb 效果）

---

### 修改檔案清單

#### 新增檔案
- `vav/gui/cv_meter_window.py` (36 行) - 獨立 CV Meters 視窗
- `GUI_CONTROLS.md` - 完整的 GUI 控制項目清單文件（60 個控制項）

#### 修改檔案
- `vav/gui/compact_main_window.py` - SD interval 文字輸入、移除 CV meters、新增 Line Thick 輸入
- `vav/gui/meter_widget.py` - SEQ1/2 顏色變更、QSizePolicy.Expanding、動態寬度
- `vav/cv_generator/contour_cv.py` - 新增 scan line thickness 參數
- `vav/core/controller.py` - 音訊路由重構、CV meters 視窗管理、統一 thickness 設定
- `CHANGELOG.md` - 記錄今日所有修改
- `README.md` - 更新音訊路由描述、Recent Updates 和 For Developers 章節（包含完整開發指南）

---

### 技術規格

#### GUI 控制
- SD Generation Interval：QLineEdit（無範圍限制）
- Scan Line Thickness：QLineEdit（整數輸入，單位 px）
- CV Meters 視窗：500x180（可調整大小）

#### 音訊路由
- 輸入通道：4 個 mono
- Track 數量：4 個
- Mixer 輸出：Mono sum
- Ellen Ripley：Mono in → Stereo out
- 輸出通道：2 stereo + 5 CV

---

## [2025-10-20] SD img2img 參數優化與即時更新

### 改進內容

#### 1. SD img2img 即時參數更新

**問題**：
- 修改 prompt 或參數後，需要等待舊的 queue 中的 frame 全部處理完才會看到新參數效果
- 導致使用者體驗不佳，需要等待數秒才能看到變更

**解決方案**：
在 `set_prompt()` 和 `set_parameters()` 方法中，發送新參數前先清空 input_queue

```python
# sd_img2img_process.py
def set_prompt(self, prompt: str):
    # 清空 input_queue 中的舊 frame（避免積壓）
    while not self.input_queue.empty():
        try:
            self.input_queue.get_nowait()
        except:
            break

    # 發送新參數到 control_queue
    self.control_queue.put_nowait({'prompt': prompt})
    # 強制觸發立即生成（重置 send 計時器）
    self.last_send_time = 0
```

**效果**：
- Prompt 和參數修改後立即生效（下一次生成就會使用新參數）
- 無需等待舊 queue 清空

---

#### 2. SD img2img 預設參數優化

**變更**：
根據使用者反饋，將預設參數調整為更快、更輕量的配置

| 參數 | 舊值 | 新值 | 說明 |
|------|------|------|------|
| Steps | 4 | 2 | LCM 可用更少步數達到相似效果 |
| Guidance Scale | 1.5 | 1.0 | 降低 guidance 提高生成速度 |
| Gen Interval | 1.5s | 0.5s | 更頻繁的生成更新 |
| Strength | 0.5 | 0.5 | 維持不變 |
| Prompt | (不變) | "artistic style, abstract, monochrome ink painting, high quality" |

**修改檔案**：
- `vav/visual/sd_img2img_process.py` - 後端預設值（lines 72-73, 183-184）
- `vav/gui/compact_main_window.py` - GUI slider 初始位置（lines 438, 441, 468, 471, 483, 486）

**效果**：
- 生成速度更快（約 0.4-0.5s/幀）
- GPU 負擔更低
- 視覺效果更接近原始素材

---

### 技術細節

#### Queue 管理
- Input Queue: maxsize=2（只保留最新的 frame）
- Output Queue: maxsize=2（只保留最新的生成結果）
- Control Queue: 無大小限制（確保參數更新不丟失）

#### 參數同步
```python
# 兩個位置的預設值需要同步：
# 1. Worker process 中的 params.get() 預設值
guidance_scale = params.get('guidance_scale', 1.0)
num_steps = params.get('num_steps', 2)

# 2. SDImg2ImgProcess class 的初始化值
self.guidance_scale = 1.0
self.num_steps = 2
```

---

## [2025-10-20] SD img2img 進程隔離架構 + Camera 第五層

### 重大改進

#### 1. SD img2img 進程隔離 - 解決 Multiverse FPS 暫停問題

**問題**：
- SD img2img 啟用後，Multiverse 在 SD 生成時會暫停（每 0.8-1.5 秒一次）
- 影響視覺流暢度

**根本原因**：
- M4 Pro MPS 是共享 GPU 架構
- SD 推理佔用大量 GPU 資源時，Multiverse OpenGL 渲染被暫停
- 線程隔離無法解決 GPU 層級的資源競爭

**解決方案**：
使用 `multiprocessing` 將 SD 推理完全隔離到獨立進程

```python
# 新文件：vav/visual/sd_img2img_process.py
class SDImg2ImgProcess:
    def start(self):
        # 創建 Queue 進行進程間通訊
        self.input_queue = mp.Queue(maxsize=2)
        self.output_queue = mp.Queue(maxsize=2)

        # 啟動獨立 SD 進程
        self.process = mp.Process(
            target=_sd_worker_process,
            args=(self.input_queue, self.output_queue, ...),
            daemon=True
        )
        self.process.start()

# SD 工作進程（完全獨立）
def _sd_worker_process(input_queue, output_queue, ...):
    pipe = StableDiffusionImg2ImgPipeline.from_pretrained(...)
    while running:
        frame = input_queue.get()
        result = pipe(prompt, image=frame, ...)
        output_queue.put(result)
```

**效果**：
- Multiverse 穩定 30 FPS（SD 啟用/關閉均不受影響）
- SD 生成：0.7-0.8 秒/幀（獨立進程）
- 完全消除視覺卡頓

**相關文件**：
- 新增：`vav/visual/sd_img2img_process.py`
- 刪除：`vav/visual/sd_img2img_realtime.py`（舊的線程版本）
- 修改：`vav/core/controller.py`（使用新的進程版本）

---

#### 2. Camera 作為第五層 - 統一混合架構

**改進**：
將 Camera 改為與 Multiverse 四層平行的第五層，使用相同的 blend mode。

**舊設計問題**：
- `camera_mix` 參數在 SD 啟用/關閉時行為不一致
- SD 開關會混合 SD 和 camera

**新架構**：
```
5 層平行混合：
├─ Layer 1-4: Multiverse 音頻視覺化（4 個音頻通道）
└─ Layer 5: SD 或 Camera（由 Camera Intensity 控制強度）

SD 開關：
├─ SD ON: 顯示/疊加 SD 畫面
└─ SD OFF: 顯示/疊加 camera 畫面

所有 5 層使用相同 blend mode（Add/Screen/Diff/Dodge）
```

**修改內容**：
- `renderer_params['camera_mix']` → `renderer_params['camera_intensity']`
- `set_renderer_camera_mix()` → `set_renderer_camera_intensity()`
- GUI: "Camera Mix" → "Camera Intensity"
- Simple 模式：純粹切換 SD/Camera（不混合）
- Multiverse 模式：Camera/SD 作為第五層疊加

**相關文件**：
- 修改：`vav/core/controller.py`
- 修改：`vav/gui/compact_main_window.py`

---

#### 3. 測試的其他方案

**❌ SD-Turbo**：
- 嘗試使用更輕量的 SD-Turbo 模型
- 問題：MPS 上有兼容性問題（VAE decode 階段產生空張量）
- 結論：不適用於當前環境

**✅ 增加生成間隔**：
- 從 0.8s → 1.5s
- 配合進程隔離，進一步降低 GPU 資源競爭

---

#### 4. 文檔更新

**新增**：
- `SD_FPS_ISSUE_RESOLVED.md`：完整的問題分析和解決方案文檔

**刪除**：
- `SD_FPS_ISSUE.md`：舊的問題分析（已被新文檔取代）
- `test_cv_overlay_sd.py`：測試文件
- `test_sd_shape_speed.py`：測試文件

---

### 技術指標

**修改前**：
- Multiverse：30 FPS（SD 關閉），不穩定（SD 啟用，每 0.8s 暫停）

**修改後**：
- Multiverse：穩定 30 FPS（SD 啟用/關閉均穩定）
- SD 生成：0.7-0.8s/幀（獨立進程）
- 更新頻率：1.5s
- 進程通訊開銷：<5ms

---

## [2025-10-19] Ellen Ripley 效果器完整修復

### 問題修復

#### 1. 音訊斷續 (Audio Stuttering)
**問題**：
- 啟用 Ellen Ripley 後聲音會跳針、斷斷續續
- CPU 使用率異常高

**根本原因**：
- CV 生成器每個 buffer (256 samples) 被呼叫 256 次
- 總計每個 buffer：5 個 CV × 256 = 1280 次呼叫（應該只呼叫 5 次）
- Ellen Ripley chaos 在每個 sample 都重新計算

**解決方案**：
```python
# controller.py - 移除不必要的迴圈
# 修改前：
for i in range(frames):
    for j, env in enumerate(self.envelopes):
        self.cv_values[j] = env.process()

# 修改後：
for j, env in enumerate(self.envelopes):
    self.cv_values[j] = env.process()

# ellen_ripley.py - chaos 每個 buffer 只生成一次
chaos_value = self._get_chaos_value()
chaos_cv = np.full(buffer_size, chaos_value * 5.0, dtype=np.float32)
```

**效果**：CPU 使用率大幅降低，音訊處理穩定

---

#### 2. Fader 破音 (Zipper Noise)
**問題**：
- 調整任何參數（delay time、feedback、mix 等）時產生破音

**根本原因**：
- 參數值直接變化，未經平滑處理

**解決方案**：
- 實作指數平滑器 `ParamSmoother` class
- 所有參數變化經過平滑處理

```python
# param_smoother.py (新增檔案)
class ParamSmoother:
    def __init__(self, initial_value: float = 0.0, lambda_factor: float = 0.005):
        self.current = initial_value
        self.lambda_factor = lambda_factor

    def process(self, target: float) -> float:
        self.current += (target - self.current) * self.lambda_factor
        return self.current
```

**使用配置**：
- Delay time: λ = 0.002 (較慢，避免音高變化)
- 其他參數: λ = 0.005 (標準速度)
- 總計 12 個參數平滑器

**效果**：完全消除 zipper noise，參數變化平順自然

---

#### 3. 缺少 Mix Faders
**問題**：
- Delay、Grain、Reverb 三種效果缺少混合控制
- 使用者無法調整 wet/dry 比例

**解決方案**：
```python
# compact_main_window.py
# 新增三個 Mix faders 與數值顯示
grid.addWidget(QLabel("Dly Mix"), row4 + 1, COL4)
self.er_delay_mix_slider = QSlider(Qt.Orientation.Horizontal)
self.er_delay_mix_label = QLabel("0.0")  # 數值顯示

# 同樣方式新增 Grain Mix 和 Reverb Mix
```

**效果**：使用者可精確控制每個效果的混合比例

---

#### 4. Chaos 生成器錯誤
**問題**：
- Chaos 調變效果與原版 C++ 不同
- 數值範圍不正確

**根本原因**：
- Lorenz attractor β 係數錯誤（2.666 應為 1.02）
- 輸出縮放錯誤（`(x-0.1)/20.0` 應為 `x*0.1`）

**解決方案**：
```python
# chaos.py
# 修改前：
dz = self.x * self.y - 2.666 * self.z
return (self.x - 0.1) / 20.0

# 修改後：
dx = 7.5 * (self.y - self.x)           # σ = 7.5
dy = self.x * (30.9 - self.z) - self.y # ρ = 30.9
dz = self.x * self.y - 1.02 * self.z   # β = 1.02
return np.clip(self.x * 0.1, -1.0, 1.0)
```

**效果**：Chaos 調變行為與 C++ 原版完全一致

---

#### 5. Reverb 功能不完整
**問題**：
- Reverb 缺少四項關鍵功能：
  1. Reverb → Delay Feedback
  2. Room Offset 計算
  3. Room Reflection (早期反射)
  4. Chaos 調變目標錯誤（應調變 feedback，而非 decay）

**解決方案**：

##### 5.1 Reverb → Delay Feedback
```python
# ellen_ripley.py
# 儲存上一幀的 reverb 輸出
self.last_reverb_l = None
self.last_reverb_r = None

# 處理 delay 前準備 reverb feedback
if self.last_reverb_l is not None and self.last_reverb_r is not None:
    reverb_decay_smooth = self.reverb_decay_smoother.current
    feedback_amount = reverb_decay_smooth * 0.3
    reverb_fb_l = self.last_reverb_l * feedback_amount
    reverb_fb_r = self.last_reverb_r * feedback_amount

# 將 reverb feedback 送入 delay
delay_l, delay_r = self.delay.process(left_out, right_out,
                                      reverb_fb_l, reverb_fb_r)

# 儲存 reverb 輸出供下一幀使用
self.last_reverb_l = reverb_l.copy()
self.last_reverb_r = reverb_r.copy()
```

##### 5.2 Room Offset 計算
```python
# reverb.py
# 四個獨立的 room offset
room_offset_1 = max(0, int(self.room_size * 400 + chaos_value * 50))  # 0-450
room_offset_2 = max(0, int(self.room_size * 350 + chaos_value * 40))  # 0-390
room_offset_5 = max(0, int(self.room_size * 380 + chaos_value * 45))  # 0-425
room_offset_6 = max(0, int(self.room_size * 420 + chaos_value * 55))  # 0-475
```

##### 5.3 Room Reflection (早期反射)
```python
# reverb.py
# 左聲道早期反射
read_idx_1 = ((self.comb_indices_l[0] - room_offset_1) % len(...)) % len(...)
read_idx_2 = ((self.comb_indices_l[1] - room_offset_2) % len(...)) % len(...)
comb_out_l += self.comb_buffers_l[0][read_idx_1] * self.room_size * 0.15
comb_out_l += self.comb_buffers_l[1][read_idx_2] * self.room_size * 0.12

# 右聲道早期反射
read_idx_5 = ((self.comb_indices_r[0] - room_offset_5) % len(...)) % len(...)
read_idx_6 = ((self.comb_indices_r[1] - room_offset_6) % len(...)) % len(...)
comb_out_r += self.comb_buffers_r[0][read_idx_5] * self.room_size * 0.13
comb_out_r += self.comb_buffers_r[1][read_idx_6] * self.room_size * 0.11
```

##### 5.4 Chaos 調變 Feedback
```python
# reverb.py
# 計算 feedback
feedback = 0.5 + self.decay * 0.485  # 0.5 到 0.985

# Chaos 調變 feedback (增強 10 倍)
if chaos_enabled:
    feedback += chaos_value * 0.5  # 原版為 0.05

feedback = np.clip(feedback, 0.0, 0.995)
```

**效果**：
- Reverb 空間感更真實
- Room size 參數影響明顯
- Chaos 調變創造動態空間
- 更長的 decay tail

---

### 修改檔案清單

#### 新增檔案
- `vav/audio/effects/param_smoother.py` (46 行) - 參數平滑器

#### 修改檔案
- `vav/audio/effects/chaos.py` - 修正 Lorenz attractor 參數
- `vav/audio/effects/grain.py` - 加入 chaos 支援
- `vav/audio/effects/delay.py` - 接受 reverb feedback 輸入
- `vav/audio/effects/reverb.py` - 實作 room offset/reflection、chaos 調變 feedback
- `vav/audio/effects/ellen_ripley.py` - 實作 reverb→delay feedback、12 個參數平滑器
- `vav/core/controller.py` - 優化 CV 處理迴圈
- `vav/gui/compact_main_window.py` - 新增 Mix faders

---

### 技術規格

#### 音訊處理
- 取樣率：48,000 Hz
- Buffer size：256 samples
- 通道數：立體聲 (L/R)

#### Lorenz Attractor 參數
- σ (sigma)：7.5
- ρ (rho)：30.9
- β (beta)：1.02
- 輸出範圍：-1.0 到 1.0

#### 參數平滑
- Delay time λ：0.002 (慢速，避免音高變化)
- 其他參數 λ：0.005 (標準速度)

#### Reverb 架構
- Comb filters：8 個 (左4個、右4個)
- Allpass filters：4 個 (串聯)
- Room offsets：4 個獨立值
- Early reflections：左右各2個

#### Reverb Feedback
- 回饋量：decay × 0.3
- 目標：Delay 輸入
- 延遲：1 個 buffer (256 samples ≈ 5.3ms)

---

### 驗證結果
- ✅ Reverb → Delay Feedback 正確實作
- ✅ Room Offset 計算正確
- ✅ Room Reflection 實作正確
- ✅ Chaos 調變 Feedback (非 Decay)
- ✅ 無破音 (zipper noise)
- ✅ 無斷續 (stuttering)
- ✅ CPU 使用率正常
- ✅ 所有參數範圍符合原版

---

## [2025-10-19] Sequencer CV 邏輯重構

### 核心變更
- **移除 Cable Detection**：刪除了 MediaPipe cable detection 功能
- **導入 Corner Detection**：使用 OpenCV Shi-Tomasi 演算法偵測特徵點
  - 演算法：`cv2.goodFeaturesToTrack()`
  - 偵測數量：4-32 個特徵點（根據 SEQ Steps 參數）
  - 品質參數：可透過 Corner Quality slider 調整（10-200 映射到 0.01-0.5）

### 資料結構重構
**修改前（錯誤）：**
```python
self.seq_point_positions_x = [x1, x2, ..., x16]  # SEQ1 的 X 座標
self.seq_point_positions_y = [y1, y2, ..., y16]  # SEQ2 的 Y 座標
```
問題：X 和 Y 座標分離後無法保留 2D 空間關係

**修改後（正確）：**
```python
self.seq_point_positions = [(x1,y1), (x2,y2), ..., (x16,y16)]  # 統一的特徵點列表
```
優點：保留完整的 2D 位置資訊

### Sequencer 運作邏輯
- **SEQ1**：垂直掃描線（X 座標）
- **SEQ2**：水平掃描線（Y 座標）
- **獨立時鐘**：兩個 sequencer 各自獨立運行

### 背景執行緒優化
```python
update_interval = 0.5s          # 每 0.5 秒更新一次
resolution_scale = 4            # 1920x1080 → 480x270
smoothing_alpha = 0.3           # 30% 新數據 + 70% 舊數據
```

### CV Overlay 視覺化
新增 `/vav/visual/cv_overlay.py`

**顯示元素：**
1. 白色方格：標記偵測到的特徵點位置（16x16 像素）
2. 垂直掃描線（SEQ1）：灰色，亮度受 CV 值調變
3. 水平掃描線（SEQ2）：灰色，亮度受 CV 值調變
4. 交叉點標記：白色圓圈（半徑 16px）
5. CV 數值顯示：顯示 SEQ1 和 SEQ2 的 CV 值

---

## [2025-10-19] Region Mode 簡化

### 變更內容
- **移除**：Color、Quadrant、Edge 三種模式
- **保留**：Brightness 模式（唯一選項）
- **GUI 變更**：移除 Region Mode 下拉選單
- **自動設定**：啟用 Region Map 時自動使用 Brightness 模式

### 刪除的檔案
- `REGION_RENDERING_GUIDE.md` - 過時的多模式指南
- `/vav/visual/region_mapper.py` - 靜態 region pattern 生成器

### 保留的檔案
- `/vav/visual/content_aware_regions.py` - Brightness-based 動態映射

---

## [2025-10-19] GUI 布局優化

### 從 6 列改為 5 列

**舊布局（6 列）：**
1. CV Source (ENV, SEQ)
2. Mixer (Track 1-4 Vol)
3. Multiverse Main
4. Multiverse Channels
5. Ellen Ripley Delay+Grain
6. Ellen Ripley Reverb+Chaos

**新布局（5 列）：**
1. **CV Source + Mixer** - ENV 1-3 Decay, SEQ Steps/Freq, Corner Quality, Track 1-4 Vol
2. **Multiverse Main** - Blend, Brightness, Camera Mix, Region Map, CV Overlay, Ch1-2
3. **Multiverse Channels** - Ch3-4 controls
4. **Ellen Ripley Delay+Grain**
5. **Ellen Ripley Reverb+Chaos**

### Grid 配置變更
```python
# 舊：6 visual columns x 3 grid columns = 18 + 1 stretch
# 新：5 visual columns x 3 grid columns = 15 + 1 stretch
for i in range(15):
    controls_grid.setColumnStretch(i, 0)
controls_grid.setColumnStretch(15, 1)
```

---

## 檔案清理記錄

### 已刪除（2025-10-19 Sequencer 重構）
1. `/vav/vision/cable_detector.py` - MediaPipe cable detection（已棄用）
2. `/vav/vision/analyzer.py` - Cable analysis for CV（已棄用）
3. `/vav/visual/region_mapper.py` - 靜態 region patterns（已棄用）
4. `REGION_RENDERING_GUIDE.md` - 過時的文檔

### 新增（2025-10-19）
1. `/vav/visual/cv_overlay.py` - CV 視覺化疊加層
2. `/vav/audio/effects/param_smoother.py` - 參數平滑器

---

## 效能測試結果

### Sequencer CV 重構後
- ✅ Multiverse 渲染：30-60 fps（無下降）
- ✅ Corner detection：0.5s 更新間隔（背景執行緒）
- ✅ GUI 回應性：無延遲

### Ellen Ripley 修復後
- ✅ 無音訊斷續
- ✅ 無參數破音
- ✅ CPU 使用率正常
- ✅ 音色與 C++ 原版一致

---

## 已知問題
無

---

## 未來改進方向

### Sequencer CV
1. 考慮加入特徵點持續性追蹤（optical flow）
2. 可調整的平滑化參數（目前固定 alpha=0.3）
3. 特徵點視覺化選項（顯示/隱藏方格）
4. Corner Quality 參數的即時反饋

### Ellen Ripley
1. 考慮 Reverb wet/dry mix 是否應影響回饋量
2. 可選的 Reverb feedback 路由（目前固定到 Delay）
3. 可調整的 Reverb feedback 量（目前固定 decay × 0.3）

---

## 參考資料

### Ellen Ripley
- 原始程式碼：`/Users/madzine/Documents/VCV-Dev/MADZINE/src/EllenRipley.cpp`
- Freeverb 演算法文件
- Lorenz Attractor 數學模型

### Sequencer CV
- OpenCV Shi-Tomasi Corner Detection
- Threading and Lock mechanisms in Python

---

**最後更新：2025-10-19**
**當前版本：VAV_20251019_EllenRipley_Complete**
