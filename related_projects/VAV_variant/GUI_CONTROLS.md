# VAV GUI 控制項目清單

**最後更新：2025-10-21**

本文件記錄 VAV 系統的所有 GUI 控制項目。

---

## 主視窗布局

主視窗採用 5 欄水平布局：
1. **Column 1**: CV Source + Mixer（11 個 CV 控制 + 4 個 Track Vol）
2. **Column 2**: Multiverse Main（1 checkbox, 1 dropdown, 4 sliders, 6 channel sliders）
3. **Column 3**: Multiverse Channels + SD img2img（6 channel sliders, 1 text area, 4 SD 參數）
4. **Column 4**: Ellen Ripley Delay + Grain（9 個控制項）
5. **Column 5**: Ellen Ripley Reverb + Chaos（8 個控制項）

---

## 頂部控制按鈕（5 個）

| 編號 | 名稱 | 類型 | 功能 | 檔案位置 |
|------|------|------|------|----------|
| 1 | Start | Button | 啟動系統 | compact_main_window.py:71-73 |
| 2 | Stop | Button | 停止系統 | compact_main_window.py:75-78 |
| 3 | Video | Button | 顯示/隱藏視訊視窗 | compact_main_window.py:80-82 |
| 4 | Devices | Button | 選擇音訊/視訊裝置 | compact_main_window.py:84-86 |
| 5 | Virtual Cam | Button (Toggle) | 開啟/關閉虛擬攝影機 | compact_main_window.py:88-91 |

---

## Column 1: CV Source + Mixer（15 個）

### CV Generation - Contour-based（6 個）

| 編號 | 名稱 | 類型 | 範圍 | 預設值 | 功能 | 檔案位置 |
|------|------|------|------|--------|------|----------|
| 6 | ENV Decay | Slider | 10-10000ms | 1000ms (1.0s) | 統一控制 ENV1-3 decay 時間 | compact_main_window.py:142-154 |
| 7 | Contour Thres | Slider | 0-255 | 100 | Canny edge detection 閾值 | compact_main_window.py:159-170 |
| 8 | Contour Smooth | Slider | 0-100 | 50 | Contour 平滑化程度 | compact_main_window.py:173-184 |
| 9 | Scan X Speed | Slider | 1-100 | 50 | X 軸掃描速度 | compact_main_window.py:187-198 |
| 10 | Scan Y Speed | Slider | 1-100 | 50 | Y 軸掃描速度 | compact_main_window.py:201-212 |
| 11 | Line Thick | Text Input | 無限制 (px) | 1 | X/Y 掃描線粗細（統一） | compact_main_window.py:216-222 |

### Mixer - Track Volume（4 個）

| 編號 | 名稱 | 類型 | 範圍 | 預設值 | 功能 | 檔案位置 |
|------|------|------|------|--------|------|----------|
| 12 | Track 1 Vol | Slider | 0-100 | 80 (0.8) | Track 1 音量 | compact_main_window.py:228-240 |
| 13 | Track 2 Vol | Slider | 0-100 | 80 (0.8) | Track 2 音量 | 同上 |
| 14 | Track 3 Vol | Slider | 0-100 | 80 (0.8) | Track 3 音量 | 同上 |
| 15 | Track 4 Vol | Slider | 0-100 | 80 (0.8) | Track 4 音量 | 同上 |

---

## Column 2: Multiverse Main（12 個）

### Multiverse Global（5 個）

| 編號 | 名稱 | 類型 | 選項/範圍 | 預設值 | 功能 | 檔案位置 |
|------|------|------|----------|--------|------|----------|
| 16 | Multiverse | Checkbox | ON/OFF | OFF | 啟用 Multiverse 渲染模式 | compact_main_window.py:247-250 |
| 17 | Blend | Dropdown | Add/Scrn/Diff/Dodg | Add | 混合模式選擇 | compact_main_window.py:254-260 |
| 18 | Brightness | Slider | 0-400 (→ 0.0-4.0) | 250 (2.5) | 整體亮度 | compact_main_window.py:264-275 |
| 19 | Camera Intensity | Slider | 0-100 | 0 (0.0) | 攝影機強度（第五層） | compact_main_window.py:279-290 |
| 20 | Region Map | Checkbox | ON/OFF | OFF | 啟用 Region Rendering | compact_main_window.py:294-297 |
| 21 | SD img2img | Checkbox | ON/OFF | OFF | 啟用 Stable Diffusion | compact_main_window.py:299-302 |

### Channel 1 Controls（3 個）

| 編號 | 名稱 | 類型 | 範圍 | 預設值 | 功能 | 檔案位置 |
|------|------|------|------|--------|------|----------|
| 22 | Ch1 Curve | Slider | 0-100 (→ 0.0-1.0) | 0 (0.0) | 通道 1 曲線效果 | compact_main_window.py:315-327 |
| 23 | Ch1 Angle | Slider | 0-360° (→ -180 to +180) | 180 (0°) | 通道 1 旋轉角度 | compact_main_window.py:331-343 |
| 24 | Ch1 Intensity | Slider | 0-150 (→ 0.0-1.5) | 100 (1.0) | 通道 1 強度 | compact_main_window.py:347-359 |

### Channel 2 Controls（3 個）

| 編號 | 名稱 | 類型 | 範圍 | 預設值 | 功能 | 檔案位置 |
|------|------|------|------|--------|------|----------|
| 25 | Ch2 Curve | Slider | 0-100 (→ 0.0-1.0) | 0 (0.0) | 通道 2 曲線效果 | compact_main_window.py:315-327 |
| 26 | Ch2 Angle | Slider | 0-360° (→ -180 to +180) | 225 (45°) | 通道 2 旋轉角度 | compact_main_window.py:331-343 |
| 27 | Ch2 Intensity | Slider | 0-150 (→ 0.0-1.5) | 100 (1.0) | 通道 2 強度 | compact_main_window.py:347-359 |

---

## Column 3: Multiverse Channels + SD img2img（11 個）

### Channel 3 Controls（3 個）

| 編號 | 名稱 | 類型 | 範圍 | 預設值 | 功能 | 檔案位置 |
|------|------|------|------|--------|------|----------|
| 28 | Ch3 Curve | Slider | 0-100 (→ 0.0-1.0) | 0 (0.0) | 通道 3 曲線效果 | compact_main_window.py:368-380 |
| 29 | Ch3 Angle | Slider | 0-360° (→ -180 to +180) | 270 (90°) | 通道 3 旋轉角度 | compact_main_window.py:384-396 |
| 30 | Ch3 Intensity | Slider | 0-150 (→ 0.0-1.5) | 100 (1.0) | 通道 3 強度 | compact_main_window.py:400-412 |

### Channel 4 Controls（3 個）

| 編號 | 名稱 | 類型 | 範圍 | 預設值 | 功能 | 檔案位置 |
|------|------|------|------|--------|------|----------|
| 31 | Ch4 Curve | Slider | 0-100 (→ 0.0-1.0) | 0 (0.0) | 通道 4 曲線效果 | compact_main_window.py:368-380 |
| 32 | Ch4 Angle | Slider | 0-360° (→ -180 to +180) | 315 (135°) | 通道 4 旋轉角度 | compact_main_window.py:384-396 |
| 33 | Ch4 Intensity | Slider | 0-150 (→ 0.0-1.5) | 100 (1.0) | 通道 4 強度 | compact_main_window.py:400-412 |

### SD img2img Parameters（5 個）

| 編號 | 名稱 | 類型 | 範圍 | 預設值 | 功能 | 檔案位置 |
|------|------|------|------|--------|------|----------|
| 34 | SD Prompt | Text Area | 多行文字 | "artistic style, abstract, monochrome ink painting" | Stable Diffusion 提示詞 | compact_main_window.py:416-423 |
| 35 | Steps | Slider | 1-20 | 2 | 生成步數 | compact_main_window.py:428-439 |
| 36 | Strength | Slider | 50-100 (→ 0.50-1.00) | 50 (0.50) | 轉換強度 | compact_main_window.py:443-454 |
| 37 | Guidance | Slider | 10-150 (→ 1.0-15.0) | 10 (1.0) | Guidance Scale | compact_main_window.py:458-469 |
| 38 | Gen Interval | Text Input | 無限制 (秒) | 0.5 | 生成間隔 | compact_main_window.py:473-479 |

---

## Column 4: Ellen Ripley Delay + Grain（11 個）

### Ellen Ripley Enable（1 個）

| 編號 | 名稱 | 類型 | 選項 | 預設值 | 功能 | 檔案位置 |
|------|------|------|------|--------|------|----------|
| 39 | Ellen Ripley | Checkbox | ON/OFF | OFF | 啟用 Ellen Ripley 效果鏈 | compact_main_window.py:486-489 |

### Delay Parameters（5 個）

| 編號 | 名稱 | 類型 | 範圍 | 預設值 | 功能 | 檔案位置 |
|------|------|------|------|--------|------|----------|
| 40 | Delay Time L | Slider | 1-2000ms | 250ms (0.25s) | 左聲道延遲時間 | compact_main_window.py:493-504 |
| 41 | Delay Time R | Slider | 1-2000ms | 250ms (0.25s) | 右聲道延遲時間 | compact_main_window.py:508-519 |
| 42 | Delay FB | Slider | 0-95 (→ 0.00-0.95) | 30 (0.30) | Delay feedback | compact_main_window.py:523-534 |
| 43 | Dly Chaos | Checkbox | ON/OFF | OFF | Delay chaos 調變 | compact_main_window.py:538-540 |
| 44 | Dly Mix | Slider | 0-100 (→ 0.0-1.0) | 0 (0.0) | Delay wet/dry mix | compact_main_window.py:542-553 |

### Grain Parameters（5 個）

| 編號 | 名稱 | 類型 | 範圍 | 預設值 | 功能 | 檔案位置 |
|------|------|------|------|--------|------|----------|
| 45 | Grain Size | Slider | 0-100 (→ 0.00-1.00) | 30 (0.30) | Grain 大小 | compact_main_window.py:557-568 |
| 46 | Grain Density | Slider | 0-100 (→ 0.00-1.00) | 40 (0.40) | Grain 密度 | compact_main_window.py:572-583 |
| 47 | Grain Position | Slider | 0-100 (→ 0.00-1.00) | 50 (0.50) | Grain 播放位置 | compact_main_window.py:587-598 |
| 48 | Grn Chaos | Checkbox | ON/OFF | OFF | Grain chaos 調變 | compact_main_window.py:602-604 |
| 49 | Grn Mix | Slider | 0-100 (→ 0.0-1.0) | 0 (0.0) | Grain wet/dry mix | compact_main_window.py:606-617 |

---

## Column 5: Ellen Ripley Reverb + Chaos（8 個）

### Reverb Parameters（5 個）

| 編號 | 名稱 | 類型 | 範圍 | 預設值 | 功能 | 檔案位置 |
|------|------|------|------|--------|------|----------|
| 50 | Reverb Room | Slider | 0-100 (→ 0.00-1.00) | 50 (0.50) | Room size | compact_main_window.py:624-635 |
| 51 | Reverb Damp | Slider | 0-100 (→ 0.00-1.00) | 40 (0.40) | Damping | compact_main_window.py:639-650 |
| 52 | Reverb Decay | Slider | 0-100 (→ 0.00-1.00) | 60 (0.60) | Decay time | compact_main_window.py:654-665 |
| 53 | Rev Chaos | Checkbox | ON/OFF | OFF | Reverb chaos 調變 | compact_main_window.py:669-671 |
| 54 | Rev Mix | Slider | 0-100 (→ 0.0-1.0) | 0 (0.0) | Reverb wet/dry mix | compact_main_window.py:673-684 |

### Chaos Generator（3 個）

| 編號 | 名稱 | 類型 | 範圍 | 預設值 | 功能 | 檔案位置 |
|------|------|------|------|--------|------|----------|
| 55 | Chaos Rate | Slider | 0-100 (→ 0.00-1.00) | 1 (0.01) | Chaos 演化速率 | compact_main_window.py:688-699 |
| 56 | Chaos Amount | Slider | 0-100 (→ 0.00-1.00) | 100 (1.00) | Chaos 調變強度 | compact_main_window.py:703-714 |
| 57 | Chaos Shape | Checkbox | ON/OFF | OFF | Chaos 波形塑形 | compact_main_window.py:718-720 |

---

## 獨立視窗

### CV Meters Window（自動顯示）

**位置**：`vav/gui/cv_meter_window.py`
**預設大小**：500x180（可調整）
**內容**：
- 5 個 CV 通道即時顯示（horizontal meters）
  - ENV 1: 粉色 (255, 133, 133)
  - ENV 2: 白色 (255, 255, 255)
  - ENV 3: 日本國旗紅 (188, 0, 45)
  - SEQ 1: 白色 (255, 255, 255)
  - SEQ 2: 白色 (255, 255, 255)
- Peak hold 功能（10 frames）
- Meter 寬度隨視窗調整

### Video Window（可切換）

**位置**：`compact_main_window.py:115-123`
**最小尺寸**：960x540
**內容**：渲染後的視訊輸出（Simple mode 或 Multiverse mode）

---

## 控制項目統計

| 類型 | 數量 |
|------|------|
| Slider | 42 |
| Checkbox | 9 |
| Button | 5 |
| Dropdown | 1 |
| Text Input | 2 |
| Text Area | 1 |
| **總計** | **60** |

---

## 音訊路由架構

```
Input 1 (mono) → Track 0 ─┐
Input 2 (mono) → Track 1 ─┤
Input 3 (mono) → Track 2 ─┼→ Mixer (4 tracks) → Mono sum → Ellen Ripley → Stereo Out (1-2)
Input 4 (mono) → Track 3 ─┘                                              ↓
                                                                    CV Out (3-7):
                                                                    - ENV 1
                                                                    - ENV 2
                                                                    - ENV 3
                                                                    - SEQ 1
                                                                    - SEQ 2
```

---

## 視覺渲染架構

### Simple Mode（Multiverse OFF）
- Camera feed → 直接輸出

### Multiverse Mode（Multiverse ON）
```
Layer 1-4: Audio-reactive visuals (4 channels)
Layer 5: Camera/SD (controlled by Camera Intensity)
  ↓
Blend Mode (Add/Screen/Diff/Dodge)
  ↓
Brightness adjustment
  ↓
Final output
```

**Region Rendering**（可選）：
- Brightness mode: 根據畫面亮度將不同區域分配給不同通道
  - Dark → CH1
  - Medium Dark → CH2
  - Medium Bright → CH3
  - Bright → CH4

---

## 版本歷史

### 2025-10-21
- SD Generation Interval 改為文字輸入（無範圍限制）
- CV Meters 移至獨立視窗（500x180）
- SEQ1/2 顏色改為白色
- 新增 Line Thick 統一控制（X/Y 掃描線粗細）
- 音訊路由重構：Input 1-4 (mono) → Track 0-3 → Mono mix → Ellen Ripley

### 2025-10-20
- SD img2img 即時參數更新
- SD img2img 預設參數優化（Steps: 2, Guidance: 1.0, Interval: 0.5s）
- Camera 改為第五層（與 Multiverse 四層平行）

### 2025-10-19
- Corner Detection for Sequencer CV
- Region Mode 簡化（只保留 Brightness mode）
- GUI 布局從 6 欄縮減為 5 欄
- Track 1-4 Vol 移至 Column 1

---

**注意事項**：
1. 所有 slider 都會顯示即時數值
2. 所有參數變更都會立即生效（除了 SD img2img 需要載入時間）
3. Ellen Ripley 效果鏈使用參數平滑器避免 zipper noise
4. Chaos 使用 Lorenz attractor 演算法（σ=7.5, ρ=30.9, β=1.02）
