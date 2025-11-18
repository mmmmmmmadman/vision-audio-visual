# 深入分析：2025-11-03 版本 GUI 架構與 Multiverse 功能

**分析日期**: 2025-11-04
**分析對象**: VAV 系統 2025-11-03 版本
**分析深度**: Very Thorough
**版本號**: b53ab96 (Initial release) + 6994988 (Region Rendering feature)

---

## 第一部分：GUI 架構詳解

### 1.1 整體窗口結構

```
┌─────────────────────────────────────────────────────────┐
│  VAV Control (1400×800)                                 │
├─────────────────────────────────────────────────────────┤
│ [Start] [Stop] [Video] [Devices] [Virtual Cam]         │  Control Buttons
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Scope (5 通道示波器)                             │  │  40% 高度
│  │  - pyqtgraph 實現                                │  │  (可調整)
│  │  - 300 樣本波形                                  │  │
│  │  - 細網格                                        │  │
│  └──────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────┐  │
│  │ COLUMN 1 │COLUMN 2│COLUMN 3│COLUMN 4│ COLUMN 5 6│  │
│  │ CV Src   │ Mixer │Multi-│ Multi-  │Ellen   │    │  │  60% 高度
│  │ Controls │ Vol   │verse │ Channels│Ripley  │    │  │  (可調整)
│  │          │       │Main  │ Ch 3-4  │Delay   │    │  │
│  │          │       │      │         │Grain   │    │  │
│  │          │       │      │         │Reverb  │    │  │
│  │          │       │      │         │Chaos   │    │  │
│  └──────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│ Status: Ready  │  In: Audio Input | Out: Audio Output  │  Status Bar
└─────────────────────────────────────────────────────────┘

獨立視窗 ────────────────────────────────────────────────
│  CV Meters (500×180)                                    │
│  ┌─────────────────────────────────────────────────┐   │
│  │ [CV1] [CV2] [CV3] [CV4] [CV5]                  │   │
│  │ 水平 meter，實時更新                            │   │
│  └─────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────

│  Video Window (獨立，默認隱藏)                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │ 攝影機 + Multiverse 渲染結果 (960×540)          │   │
│  │ 實時顯示視頻輸出                                │   │
│  └─────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────
```

### 1.2 6 列佈局詳解

#### **COLUMN 1: CV Source Controls** (COL=0)
```
ENV 衰減時間
├─ ENV 1 Decay: 10-10000ms [━━━━] "1.0s"
├─ ENV 2 Decay: 10-10000ms [━━━━] "1.0s"
└─ ENV 3 Decay: 10-10000ms [━━━━] "1.0s"

Sequencer 設定 (邊緣檢測)
├─ SEQ 1 Steps: 4-32 步 [━━━━] "16"
├─ SEQ 1 Freq: 30-300 BPM [━━━━] "120"
├─ SEQ 2 Steps: 4-32 步 [━━━━] "16"
└─ SEQ 2 Freq: 30-300 BPM [━━━━] "120"

邊緣檢測參數
├─ Min Length: 10-200 [━━━━] "50"

（2025-11-04 更新）
├─ Clock Rate (統一): 1-999 BPM [━━━━] "120"
├─ Anchor X: 0-100% [━━━━] "50%"
├─ Anchor Y: 0-100% [━━━━] "50%"
├─ Range: 0-50% [━━━━] "50%"
├─ Edge Threshold: 0-255 [━━━━] "50"
└─ Temporal Smoothing: 0-100 [━━━━] "50"
```

**最新 CV 架構** (2025-11-04):
- SEQ1 和 SEQ2 使用**統一時鐘** (單一 BPM 控制)
- 基於 **Sobel 邊緣檢測** (而非 Canny)
- **錨點位置**可拖拉設定（在攝影機視圖中）
- **採樣線掃描**: 水平掃描尋邊（SEQ1）+ 垂直掃描尋邊（SEQ2）

#### **COLUMN 2: Mixer** (COL=3)
```
音訊 Mixer（4 軌）
├─ Track 1 Vol: 0-100 [━━━━] "0.8"
├─ Track 2 Vol: 0-100 [━━━━] "0.8"
├─ Track 3 Vol: 0-100 [━━━━] "0.8"
└─ Track 4 Vol: 0-100 [━━━━] "0.8"
```

**功能**: 獨立控制 4 個音訊軌的音量
**連接**: 直接映射到 `StereoMixer`

#### **COLUMN 3: Multiverse Main** (COL=6)

核心 Multiverse 控制：

```
☑ Multiverse              ← 啟用/禁用整個渲染系統

Blend: [Add ▼]            ← 混合模式
├─ Add (加法)
├─ Screen (濾色)
├─ Diff (差異)
└─ Dodge (顏色減淡)

Brightness: [━━━━] "2.5"  ← 整體亮度 (0.0-4.0)

Camera Mix: [━━━━] "0.0"  ← 相機與 Multiverse 混合
                          ← 0.0=純 Multiverse
                          ← 1.0=純相機

☐ Region Map             ← NEW (2025-10-18)
                          ← 啟用基於內容的分區渲染

Region Mode: [Bright ▼]   ← 分區模式
├─ Bright (亮度分區)
├─ Color (顏色分區)
├─ Quad (四象限)
└─ Edge (邊緣檢測)

Ch1 Curve: [━━━━] "0.0"   ← 曲線彎曲 (0-1)
Ch1 Angle: [━━━━] "180°"  ← 旋轉角度 (-180 to +180)
Ch1 Intensity: [━━━━] "1.0"← 通道強度 (0.0-1.5)

Ch2 Curve: [━━━━] "0.0"
Ch2 Angle: [━━━━] "225°"
Ch2 Intensity: [━━━━] "1.0"
```

**Multiverse 原理**:
- 4 個獨立音訊通道
- 每個通道有自己的 Curve (波形彎曲), Angle (旋轉), Intensity (強度)
- Curve: 基於 Y 位置偏移 X 採樣，產生波形彎曲效果
- Angle: 整個視覺旋轉
- Blend Mode: 控制通道混合方式

#### **COLUMN 4: Multiverse Channels** (COL=9)

Ch3 和 Ch4 的相同控制（延續 Column 3）：
```
Ch3 Curve/Angle/Intensity
Ch4 Curve/Angle/Intensity
```

#### **COLUMN 5: Ellen Ripley Delay+Grain** (COL=12)

Ellen Ripley 是音訊效果鏈：

```
☑ Ellen Ripley            ← 啟用/禁用

Delay 時間 L: [━━━] "0.25s"
Delay 時間 R: [━━━] "0.25s"
Delay Feedback: [━━━] "0.30"
☐ Dly Chaos              ← 延遲混沌
Dly Mix: [━━━] "0.0"     ← 延遲 Wet/Dry Mix

Grain Size: [━━━] "0.30"
Grain Density: [━━━] "0.40"
Grain Position: [━━━] "0.50"
☐ Grn Chaos             ← 顆粒混沌
Grn Mix: [━━━] "0.0"    ← 顆粒 Wet/Dry Mix
```

**Ellen Ripley 架構**:
- 延遲 + 顆粒 + 混沌 三層效果
- 每層可獨立啟用/禁用
- 每層有 Wet/Dry Mix 控制

#### **COLUMN 6: Ellen Ripley Reverb+Chaos** (COL=15)

```
Reverb Room: [━━━] "0.50"
Reverb Damping: [━━━] "0.40"
Reverb Decay: [━━━] "0.60"
☐ Rev Chaos              ← 混沌
Rev Mix: [━━━] "0.0"     ← Reverb Wet/Dry Mix

Chaos Rate: [━━━] "0.01"
Chaos Amount: [━━━] "1.00"
☐ Chaos Shape            ← 混沌形狀選擇
```

### 1.3 CV Meter Window (獨立視窗)

位置: `vav/gui/cv_meter_window.py`

```python
class CVMeterWindow(QMainWindow):
    def __init__(self):
        self.setWindowTitle("CV Meters")
        self.resize(500, 180)
        
        # 5 通道 Meter Widget
        self.meter_widget = MeterWidget(num_channels=5)
        # ↓ 顯示 ENV1, ENV2, ENV3, SEQ1, SEQ2
```

**特點**:
- 獨立可調整大小的窗口
- 實時更新 5 個通道值
- 彩色條狀圖表示
- Peak hold 功能（可選）

### 1.4 視頻顯示窗口

```python
self.video_window = QWidget()
self.video_window.setWindowTitle("VAV - Video")
self.video_label = QLabel()
self.video_label.setMinimumSize(960, 540)
```

**內容**:
- 攝影機輸入 + Multiverse 渲染結果
- 或純攝影機輸入（取決於 Multiverse 開關）
- 可通過 "Video" 按鈕顯示/隱藏

---

## 第二部分：Multiverse Renderer 完整功能

### 2.1 Multiverse 渲染架構

```
音訊輸入 (4 通道 × 48kHz)
        ↓
┌──────────────────────────────────────────┐
│   Audio Analyzer (頻率檢測)               │
│   - 48kHz → 4 個通道波形緩衝              │
│   - Dominant frequency 檢測              │
└──────────────────────────────────────────┘
        ↓
        ┌─ Channel 1: freq=X, audio_data=[]
        ├─ Channel 2: freq=Y, audio_data=[]
        ├─ Channel 3: freq=Z, audio_data=[]
        └─ Channel 4: freq=W, audio_data=[]
        ↓
┌──────────────────────────────────────────┐
│   Renderer (Numba/Qt OpenGL/GPU)         │
│   - 渲染 4 個通道的視覺                   │
│   - 應用 Curve, Angle, Intensity         │
│   - 應用 Blend Mode 混合                 │
│   - 應用亮度調整                          │
└──────────────────────────────────────────┘
        ↓
   1920×1080 RGBA
        ↓
   相機混合 (Camera Mix)
        ↓
   顯示 / 虛擬相機輸出
```

### 2.2 Renderer 實現 (三層選擇)

#### **選項 1: Numba JIT Renderer** (默認，推薦)

文件: `vav/visual/numba_renderer.py`

```python
class NumbaMultiverseRenderer:
    # 使用 Numba 的 LLVM JIT 編譯
    # 性能: 60+ FPS @ 1920×1080 (macOS)
    
    def render(self, channels_data):
        # 並行渲染 4 通道
        for ch in range(4):
            # Pass 1: 渲染單通道 + Curve
            rgba_layer = render_channel_numba(
                audio_buffer,
                frequency,
                intensity,
                curve,
                angle,
                width, height
            )
            
            # Pass 2: 旋轉 (如果 angle != 0)
            if angle != 0:
                rotated = rotate_image(rgba_layer, angle)
            
            # Pass 3: 混合到結果
            blend_func(result, rotated, blend_mode)
        
        # 應用亮度
        result *= brightness
        
        return result
```

**性能特性**:
- Numba `@njit` 編譯為機器碼
- `prange` 並行化行處理
- 快速數學操作 (fastmath=True)
- 適合實時 30-60 FPS

#### **選項 2: Qt OpenGL Renderer**

文件: `vav/visual/qt_opengl_renderer.py`

```python
class QtMultiverseRenderer(QOpenGLWidget):
    # Qt 原生 OpenGL 實現
    # 性能: 30-45 FPS (background thread)
    # 優點: 完整 GPU 加速，區域映射支持
    
    FRAGMENT_SHADER = """
        uniform sampler2D audio_tex;      # 音訊數據 (width × 4)
        uniform vec4 frequencies;         # 4 個通道頻率
        uniform vec4 intensities;         # 4 個通道強度
        ...
    """
```

**特點**:
- 多 pass 設計（Pass 1: Curve，Pass 2: Rotation，Pass 3: Blending）
- Region map 支持
- Thread-safe 設計（信號/槽機制）
- 1s 超時保護

#### **選項 3: GPU (ModernGL) Renderer**

文件: `vav/visual/gpu_renderer.py`

```python
class GPUMultiverseRenderer:
    # Standalone OpenGL context (ModernGL)
    # 性能: 60+ FPS
    # 用途: 測試、獨立渲染
```

**選擇邏輯** (`controller.py`):
```python
if NUMBA_AVAILABLE:
    renderer = NumbaMultiverseRenderer()  # ← 首選 (最快)
else:
    renderer = QtMultiverseRenderer()      # ← 備選 (功能完整)
    # 或
    # renderer = GPUMultiverseRenderer()
```

### 2.3 Multiverse 渲染管線詳解

#### **Pass 1: Channel Rendering (應用 Curve)**

```glsl
// 對每個像素，對每個通道：

// 1. 計算原始座標
x_normalized = x / width           // 0-1
y_normalized = y / height          // 0-1
y_from_center = (y - 0.5) * 2.0   // -1 到 +1

// 2. 應用 Curve（基於 Y 位置彎曲 X 採樣）
x_sample = x_normalized
if (curve > 0.001):
    bend_shape = sin(x_normalized * PI)  // 拋物線
    bend_amount = y_from_center * bend_shape * curve * 2.0
    x_sample = fract(x_sample + bend_amount)

// 3. 採樣波形音訊
waveValue = texture(audio_tex, (x_sample, (ch + 0.5) / 4.0))

// 4. 正規化電壓 (-10V ~ +10V → 0-1)
normalized = clamp((waveValue + 10.0) * 0.05 * intensity, 0, 1)

// 5. 頻率 → 色相 (八度循環)
hue = getHueFromFrequency(frequency)

// 6. HSV → RGB
color = hsv2rgb(vec3(hue, 1.0, normalized))
```

**Key Point**: Curve 應用在**原始座標空間**，不受旋轉影響。

#### **Pass 2: Rotation (應用 Angle)**

```glsl
// 對每個通道的渲染結果應用旋轉

// 1. 計算 scale 補償 (避免黑邊)
rad = radians(angle)
cos_a = cos(rad)
sin_a = sin(rad)
scale_x = (width * abs(cos_a) + height * abs(sin_a)) / width
scale_y = (width * abs(sin_a) + height * abs(cos_a)) / height
scale = max(scale_x, scale_y)

// 2. 應用旋轉 + Scale
uv = normalize_coords(x, y)
centered = uv - 0.5
centered /= scale
rotated = rotate(centered, angle)
uv_rotated = rotated + 0.5

// 3. 從 temp FBO 採樣
result = sample_temp_fbo(uv_rotated, ch)
```

**Key Point**: Scale compensation 使用反向映射確保無黑邊。

#### **Pass 3: Blending (應用 Blend Mode)**

```glsl
// 混合 4 個通道

// 支援的混合模式:
// 0: Add (加法)
result = min(1.0, c1 + c2)

// 1: Screen (濾色)
result = 1.0 - (1.0 - c1) * (1.0 - c2)

// 2: Difference (差異)
result = abs(c1 - c2)

// 3: Color Dodge (顏色減淡)
result = c1 / (1.0 - c2) if c2 < 1.0 else 1.0
```

#### **Post-Processing**

```glsl
// 應用亮度
result.rgb *= brightness  // 0.0 ~ 4.0

// 應用相機混合
if (camera_mix > 0.0):
    result = mix(result, camera_frame, camera_mix)

// 輸出 RGB
fragColor = vec4(result.rgb, 1.0)
```

### 2.4 區域渲染 (Region Rendering)

新增功能 (2025-10-18): `vav/visual/content_aware_regions.py`

```python
class ContentAwareRegionMapper:
    """根據畫面內容動態分配區域"""
    
    def create_brightness_based_regions(frame):
        """亮度分區 (推薦用於即時表演)"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        region_map = zeros((height, width))
        region_map[gray < 64] = 0      # CH1: 很暗
        region_map[64-128] = 1         # CH2: 中暗
        region_map[128-192] = 2        # CH3: 中亮
        region_map[gray >= 192] = 3    # CH4: 很亮
        
        return region_map  # 0-3 的陣列
```

**集成方式** (Qt OpenGL):
```glsl
// Fragment Shader
uniform sampler2D region_tex;
uniform int use_region_map;

void main():
    if (use_region_map > 0):
        int region = int(texture(region_tex, v_texcoord).r * 255.0)
        
        // 只在對應區域混合該通道
        if (currentRegion != channel_id) continue;
```

### 2.5 完整 Multiverse 功能清單

#### **核心參數**
- [ ] 4 個音訊通道獨立控制
- [ ] Curve (波形彎曲)
- [ ] Angle (旋轉角度)
- [ ] Intensity (強度)
- [ ] Blend Mode (4 種混合模式)
- [ ] Brightness (全局亮度)
- [ ] Camera Mix (相機與渲染混合)

#### **高級功能**
- [ ] Region-based Rendering (4 種分區模式)
- [ ] Frequency Detection (主導頻率自動檢測)
- [ ] Hue Mapping (八度循環色相)
- [ ] Scale Compensation (旋轉無黑邊)
- [ ] Temporal Smoothing (時間平滑)

#### **性能特性**
- [ ] Numba JIT 編譯 (60+ FPS @ 1920×1080)
- [ ] Qt OpenGL 加速 (30-45 FPS，線程安全)
- [ ] GPU ModernGL (60+ FPS，獨立上下文)
- [ ] 虛擬相機輸出 (pyvirtualcam)

#### **視覺化支持**
- [ ] Video Window (即時預覽)
- [ ] CV Meter Window (5 通道監控)
- [ ] Scope Widget (波形顯示)
- [ ] 攝影機疊加 (CV 採樣線, 觸發光圈)

---

## 第三部分：GPU Rendering 實現方式

### 3.1 GPU Rendering 選項對比

| 方案 | 文件 | 編程語言 | 優點 | 缺點 | 用途 |
|------|------|--------|------|------|------|
| **Numba JIT** | numba_renderer.py | Python + LLVM | 快速, 簡單, 無依賴 | CPU 只, 無並行 GPU | 默認首選 |
| **Qt OpenGL** | qt_opengl_renderer.py | GLSL + PyQt6 | GPU 加速, 區域映射, 線程安全 | 複雜, 信號開銷 | 完整功能 |
| **ModernGL** | gpu_renderer.py | GLSL + ModernGL | 純 GPU, 獨立 context | 額外依賴, 無 Qt 整合 | 測試/獨立 |

### 3.2 Qt OpenGL 線程安全設計

```python
class QtMultiverseRenderer(QOpenGLWidget):
    render_requested = pyqtSignal()
    
    def render(self, data):
        # 可被任何線程調用
        
        if threading.current_thread() == threading.main_thread():
            # GUI 線程: 直接渲染
            return _render_direct(data)
        else:
            # 背景線程: 通過信號 marshal 到 GUI
            self.render_requested.emit()
            
            # 等待 GUI 線程完成 (1s 超時)
            result = event.wait(timeout=1000)
            
            if result:
                return rendered_image
            else:
                return zeros((height, width, 3))  # 超時，返回黑幀
```

**性能開銷**:
- GUI 線程: 0ms 額外開銷
- 背景線程: 0.2-0.6ms 信號 + 同步開銷
- 超時保護: 防止死鎖

### 3.3 Numba JIT 性能特性

```python
@njit(parallel=True, fastmath=True, cache=True)
def render_channel_numba(...):
    """並行渲染 4 通道"""
    
    # prange 自動並行化
    for y in prange(height):
        for x in range(width):
            # JIT 編譯為機器碼
            # fastmath: 信任浮點計算 (faster)
            # parallel: 自動多線程
```

**基準測試**:
- 1920×1080 @ 30 FPS: 33ms / 幀 = 100% CPU
- 實際: 16-20ms / 幀 = 充足的容量
- Warm-up: 首次呼叫 ~2s (JIT 編譯)

---

## 第四部分：CV Output 獨立視窗呈現

### 4.1 CV Meter Window 架構

位置: `vav/gui/cv_meter_window.py` + `vav/gui/meter_widget.py`

```python
class CVMeterWindow(QMainWindow):
    def __init__(self):
        self.setWindowTitle("CV Meters")
        self.resize(500, 180)
        
        # 建立中央 widget
        central = QWidget()
        layout = QVBoxLayout(central)
        
        # Meter widget (5 通道)
        self.meter_widget = MeterWidget(num_channels=5)
        layout.addWidget(self.meter_widget)
    
    def update_values(self, samples: np.ndarray):
        # samples 是 (5,) 陣列: [ENV1, ENV2, ENV3, SEQ1, SEQ2]
        self.meter_widget.update_values(samples)
```

### 4.2 CV 值更新流程

```
Controller._on_cv(cv_values: np.ndarray)
    ↓
cv_updated.emit(cv_values)  [信號]
    ↓
    [GUI 線程接收]
    ↓
_update_cv_display(cv_values)
    ├─ scope_widget.add_samples(cv_values)    [波形圖]
    └─ cv_meter_window.update_values(cv_values) [獨立視窗]
```

### 4.3 CV 數據流

```
Contour CV Generator (每幀更新)
├─ ENV1 value (0-1)
├─ ENV2 value (0-1)
├─ ENV3 value (0-1)
├─ SEQ1 value (0-1)
└─ SEQ2 value (0-1)
    ↓
轉換為 CV 輸出值
├─ 0-10V 電壓映射
├─ ES-8 DAC 輸出
└─ GUI 顯示 (meter + scope)
```

### 4.4 Meter Widget 呈現

```
┌─────────────────────────────────────────┐
│ CV Meters                               │
├─────────────────────────────────────────┤
│ ENV1    [█████░░░░] 5.0V  Peak: 10V    │
│ ENV2    [███░░░░░░] 3.0V  Peak: 10V    │
│ ENV3    [██░░░░░░░] 2.0V  Peak: 10V    │
│ SEQ1    [████░░░░░] 4.5V  Peak: 10V    │
│ SEQ2    [█████░░░░] 5.2V  Peak: 10V    │
└─────────────────────────────────────────┘
```

**特點**:
- 水平條狀圖表示 0-10V
- Peak Hold (可選)
- 實時更新 (30 FPS 同步)
- 彩色編碼 (ENV1/2/3 vs SEQ1/2)

---

## 第五部分：與當前版本的主要差異

### 5.1 架構進化時間線

```
2025-10-18 (Initial Release)
├─ 基本 Multiverse 渲染
├─ Numba JIT + Qt OpenGL 雙渲染器
├─ 4 個音訊通道 + CV 生成
├─ Ellen Ripley 效果鏈

2025-10-18 → 2025-11-03 (Region Rendering)
├─ Region-based 分區渲染
├─ 4 種分區模式 (Bright/Color/Quad/Edge)
├─ 內容感知區域映射
└─ Qt OpenGL multi-pass 架構

2025-11-03 (當前版本)
├─ 完整 Contour CV Generator
├─ 統一 BPM 時鐘 (SEQ1 + SEQ2 同步)
├─ Sobel 邊緣檢測 (改進自 Canny)
├─ 錨點拖拉控制
├─ CV Meter 獨立視窗
└─ 完整的視覺疊加 (邊緣線, 光圈, 面板)
```

### 5.2 2025-11-03 版本新增功能

#### **CV 系統升級**

| 項目 | 舊版 | 新版 |
|------|------|------|
| SEQ 時鐘 | 獨立 (SEQ1, SEQ2 不同步) | 統一 BPM (同步) |
| 邊緣檢測 | Canny | Sobel (更精細) |
| 採樣方式 | 固定網格 | 錨點 + 範圍 |
| 參數控制 | GUI slider | GUI slider + 拖拉 |
| 視覺化 | 基本線條 | 邊緣線 + 光圈 + 面板 |

#### **GUI 改進**

1. **CV 參數統一**
   - 移除分別的 "Anchor X" / "Anchor Y" slider
   - 改為攝影機視圖中的拖拉控制
   - 保留 Range 參數

2. **新增 CV 面板顯示**
   - 攝影機疊加: 邊緣線 (粉/白), 光圈 (擴展動畫), 數據面板
   - 面板顯示: Clock BPM, SEQ1/2 電壓, ENV1/2/3 狀態

3. **Meter 獨立視窗**
   - 從主窗口分離，可獨立移動/調整
   - 實時監控 5 個 CV 值

#### **Multiverse 穩定性改進**

1. **多 Pass 架構**
   - Pass 1: Channel Rendering (Curve 應用)
   - Pass 2: Rotation (Angle 應用)
   - Pass 3: Blending (混合)
   - 清晰的執行順序，避免 15 個錯誤

2. **區域渲染成熟**
   - 4 種分區模式完全實現
   - 與 4 種混合模式正交組合 (16 種組合)
   - 高性能 (3-30ms 額外開銷)

3. **Thread-Safe 設計**
   - Qt OpenGL renderer 信號/槽機制
   - 背景線程可安全呼叫 render()
   - 1s 超時保護

---

## 第六部分：正確的視窗佈局描述

### 6.1 窗口層次結構

```
QApplication
└── CompactMainWindow (1400×800)
    ├── Central Widget
    │   └── Main Layout (QVBoxLayout)
    │       ├── Control Buttons (QHBoxLayout)
    │       │   ├── [Start]
    │       │   ├── [Stop]
    │       │   ├── [Video]
    │       │   ├── [Devices]
    │       │   └── [Virtual Cam]
    │       │
    │       └── Splitter (QSplitter, 可調整)
    │           ├── Scope Group (40% 高度)
    │           │   └── ScopeWidget (5 通道)
    │           │
    │           └── Controls Grid (60% 高度)
    │               └── QGridLayout (18 列 × N 行)
    │                   ├── COLUMN 1: CV Source
    │                   ├── COLUMN 2: Mixer
    │                   ├── COLUMN 3: Multiverse Main
    │                   ├── COLUMN 4: Multiverse Channels
    │                   ├── COLUMN 5: Ellen Ripley Delay+Grain
    │                   └── COLUMN 6: Ellen Ripley Reverb+Chaos
    │
    ├── Status Bar
    │   ├── Status Label (左)
    │   └── Device Status Label (右)
    │
    └── Video Window (獨立，默認隱藏)
        └── Video Label (960×540)

++ CVMeterWindow (獨立窗口, 500×180)
   └── MeterWidget (5 通道)
```

### 6.2 列配置詳解

```python
# 列位置映射
COL1 = 0   # CV Source (0-2 共 3 列)
COL2 = 3   # Mixer (3-5)
COL3 = 6   # Multiverse Main (6-8)
COL4 = 9   # Multiverse Channels (9-11)
COL5 = 12  # Ellen Ripley Delay+Grain (12-14)
COL6 = 15  # Ellen Ripley Reverb+Chaos (15-17)

# 每列內部結構
每列 = 3 個 grid 列:
└── COL + 0: 標籤 (Label)
    COL + 1: 滑桿 (Slider, 140px 寬)
    COL + 2: 數值 (Value Label, 25-35px 寬)

# 最後一列伸縮
col 18: Stretch (填充剩餘空間)
```

### 6.3 Slider 標準化

```python
# 所有 Slider 的統一規格

# 滑桿規格
height: 16px (固定)
width: 120-140px (通道控制), 100px (mixer)

# 數值標籤規格
width: 25-35px (根據內容)
right-aligned

# 間距
horizontal: 10px (列間距)
vertical: 18px (行間距, 9× 標準)

# 文字
font: Qt default
size: 0.5 point (小)
```

### 6.4 響應式佈局

```python
# Splitter 配置
splitter.setSizes([200, 200])      # 初始 40:60 分割
splitter.setStretchFactor(0, 2)    # Scope 可伸縮
splitter.setStretchFactor(1, 1)    # Controls 保持緊湊

# 窗口調整時的行為
窗口擴展 → Scope 優先擴展 (更多視圖空間)
窗口縮小 → Scope 和 Controls 同時縮小
```

---

## 第七部分：CV 列表佈局建議

### 7.1 CV 應該在哪裡？

**當前位置 (2025-11-03)**:
```
COLUMN 1 (最左邊)
├─ CV Source (所有 CV 生成參數)
├─ Envelope 衰減
├─ Sequencer 參數
└─ 邊緣檢測參數
```

**優點**:
- 邏輯清晰 (CV 源在最左)
- 易於理解 (從左到右: CV → Mixer → Render → Effects)
- 與音訊信號流一致

**可選改進**:
```
方案 A: 獨立 CV 面板 (新增)
├─ CV Source (現有)
└─ CV Monitor (新增)
    ├─ Meter 顯示
    ├─ Scope 顯示
    └─ History 圖表

方案 B: 迷你版 CV 控制 (右下角, 類似 Anchor 控制框)
├─ 可拖拉的 CV 點
├─ 實時電壓數值
└─ 快速調整界面
```

### 7.2 CV 列表的完整內容

```
┌─ ENV (Decay 時間) ────────────────────┐
│  ENV1 Decay: [━━━━━] 1.0s             │
│  ENV2 Decay: [━━━━━] 1.0s             │
│  ENV3 Decay: [━━━━━] 1.0s             │
│                                       │
├─ SEQ (Sequencer) ─────────────────────┤
│  Clock (BPM): [━━━━━] 120 BPM        │  ← 統一時鐘
│  SEQ1 Steps: [━━━━━] 16              │
│  SEQ2 Steps: [━━━━━] 16              │
│                                       │
├─ Edge Detection (Sobel) ──────────────┤
│  Anchor X: [━━━━━] 50%               │  ← 可拖拉
│  Anchor Y: [━━━━━] 50%               │  ← 可拖拉
│  Range: [━━━━━] 50%                  │
│  Threshold: [━━━━━] 50               │
│  Smoothing: [━━━━━] 50%              │
│                                       │
└─ Cable Detection ─────────────────────┘
   Min Length: [━━━━━] 50
```

---

## 第八部分：Multiverse 功能完整清單

### 8.1 核心功能 (4 個通道)

```
┌─ Channel 1 (CH1) ─────────────────────┐
│ Curve: 0-1 (波形彎曲)                 │
│ Angle: -180 to +180° (旋轉)           │
│ Intensity: 0-1.5 (強度)               │
│ Auto Frequency Detection              │
│ Color: 自動根據頻率生成               │
│ Status: Enable/Disable                │
│
├─ Channel 2 (CH2)
├─ Channel 3 (CH3)
└─ Channel 4 (CH4)
```

### 8.2 全局控制

```
Multiverse Enable/Disable
├─ Blend Mode
│  ├─ Add (加法)
│  ├─ Screen (濾色)
│  ├─ Difference (差異)
│  └─ Color Dodge (減淡)
│
├─ Brightness: 0-4.0 (全局亮度)
│
├─ Camera Mix: 0-1 (相機 vs 渲染)
│
└─ Output
    ├─ Video Window (960×540)
    └─ Virtual Camera (pyvirtualcam)
```

### 8.3 進階功能

```
Region-Based Rendering
├─ Enable/Disable
├─ Region Mode:
│  ├─ Brightness (亮度分區)
│  ├─ Color (顏色分區)
│  ├─ Quadrant (四象限)
│  └─ Edge (邊緣檢測)
└─ Effect: 4 × 4 = 16 組合

Frequency Detection
├─ Auto dominant frequency per channel
├─ Octave-based hue mapping
└─ HSV to RGB conversion

Performance
├─ Numba JIT: 60+ FPS
├─ Qt OpenGL: 30-45 FPS
└─ Virtual Camera: 30-60 FPS
```

### 8.4 視覺化支持

```
Video Window
├─ 攝影機輸入 (可選)
├─ Multiverse 渲染
├─ Camera Mix 混合
└─ 全屏預覽

CV Overlay (攝影機畫面上)
├─ Sobel 邊緣線 (白色, 半透明)
├─ SEQ1 邊緣曲線 (粉色)
├─ SEQ2 邊緣曲線 (白色)
├─ ENV 觸發光圈 (擴展+淡出)
└─ 數據儀表板 (左上角)

Independent Windows
├─ CV Meters (5 通道)
├─ Scope (波形顯示)
└─ Video Preview (960×540)
```

---

## 總結

### 要點 1: GUI 組織

**CV 控制應該在 COLUMN 1 (最左邊)**，包含：
- 3 × ENV 衰減
- Sequencer 設定 (統一時鐘 + 步數)
- 邊緣檢測參數 (Sobel, 錨點, 範圍, 閾值, 平滑)
- 電纜檢測 (最小長度)

### 要點 2: Multiverse 功能

**完整的 Multiverse 系統包含**：
- 4 個獨立音訊通道
- Curve (波形彎曲), Angle (旋轉), Intensity (強度)
- 4 種混合模式
- 區域渲染 (4 種分區模式)
- 相機混合
- 虛擬相機輸出

### 要點 3: GPU Rendering

**三層選擇**：
- **Numba JIT** (默認, 最快): 60+ FPS @ 1920×1080
- **Qt OpenGL** (完整, 線程安全): 30-45 FPS
- **ModernGL** (獨立, 純 GPU): 60+ FPS

### 要點 4: CV 顯示

**獨立視窗策略**：
- CV Meter Window (500×180): 5 通道 meter + peak hold
- Scope Widget: 波形顯示 (300 樣本)
- CV Overlay: 攝影機上的視覺化 (邊緣線, 光圈, 面板)

### 要點 5: 視窗佈局

**響應式 6 列佈局**：
- Splitter 40:60 分割 (Scope vs Controls)
- 每列 3 grid 列 (標籤 + 滑桿 + 數值)
- 18 個 grid 列 + 1 伸縮列
- 垂直間距 18px (9× 標準)

---

**分析完成** ✓  
**分析日期**: 2025-11-04  
**分析工具**: Claude Code File Search  
**版本**: b53ab96 + 6994988 + 2025-11-03 updates
