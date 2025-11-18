# Level 控制項合併 - 2025-11-04

## 修改摘要

將三組 Level 控制項合併為單一控制，實現音畫同步控制。

---

## 背景

### 原有的三組 Level

1. **Track 1-4 Vol** (COL1, Lines 241-256)
   - 位置：Column 1
   - 用途：Mixer 音量控制（舊系統）

2. **Ch1-4 Intensity** (COL3, Lines 437-451)
   - 位置：Column 3
   - 用途：Multiverse 視覺強度

3. **Channel Levels** (COL4, Lines 456-478)
   - 位置：Column 4
   - 用途：Ellen Ripley 輸入混音

### 問題

- 功能重疊，介面複雜
- Track Vol 和 Channel Levels 作用相同
- 音訊和視覺分離控制，不符合系統設計理念

---

## 修改內容

### 1. 合併功能到 COL1 Track Vol

**檔案**: `vav/gui/compact_main_window.py`

**修改位置**: Lines 1061-1070

```python
def _on_mixer_volume(self, track: int, value: float):
    """Track volume changed - affects BOTH Multiverse intensity and Ellen Ripley mix level"""
    # Set Multiverse visual intensity
    if self.controller:
        self.controller.set_renderer_channel_intensity(track, value)
        # Set Ellen Ripley mix level
        self.controller.set_channel_level(track, value)
    # Update label
    _, label = self.mixer_sliders[track]
    label.setText(f"{value:.1f}")
```

**功能**：
- 同時控制 Multiverse 視覺強度
- 同時控制 Ellen Ripley 混音音量
- 實現音畫同步

### 2. 移除 COL3 Intensity 控制項

**刪除內容**：
- Lines 437-451: 4×Intensity 滑桿
- Line 400: `self.channel_intensity_sliders` 初始化
- Lines 1268-1273: `_on_channel_intensity_changed()` 回調函數

**保留內容**：
- Ch1-4 Curve（彎曲）
- Ch1-4 Angle（角度）

### 3. 移除 COL4 Channel Levels 控制項

**刪除內容**：
- Lines 439-463: Channel Levels 區塊
- Lines 443-444: `self.channel_level_sliders` 和 `self.channel_level_labels` 初始化
- Lines 1385-1390: `_on_channel_level_changed()` 回調函數

---

## 最終 GUI 配置

### COL1: 基礎音訊控制
- Clock Rate
- Range
- Threshold
- Smoothing
- **Track 1-4 Vol** (0.0-1.0) ← 統一控制音訊+視覺

### COL2: Multiverse 全局設定
- Blend mode
- Brightness
- Camera Mix
- Time Window
- Global Intensity

### COL3: Multiverse 每通道參數
- Ch1-4 Curve（彎曲）
- Ch1-4 Angle（角度）

### COL4: Ellen Ripley 效果
- Ellen Ripley Enable
- Delay Time L/R
- Delay FB
- Delay Mix
- Delay Chaos
- Grain Density
- Grain Size
- Reverb Room Size
- Reverb Damping
- Reverb Mix

---

## 訊號流程

```
ES-8 Input (4 channels)
    ↓
[COL1: Track 1-4 Vol] (0.0-1.0)
    ↓
    ├─→ × Intensity → Multiverse 視覺化
    │                 + Curve, Angle 調整
    │
    └─→ × Level → Mix → Ellen Ripley → Output
```

**效果**：
- 調高 Track Vol → 聲音變大 + 畫面變亮
- 調低 Track Vol → 聲音變小 + 畫面變暗
- 音畫完全同步

---

## 其他修改

### 移除視覺左下角綠色文字

**檔案**: `vav/core/controller.py`

**修改位置**: Lines 557-559

**刪除內容**：
```python
# 移除前
cv2.putText(rendered_bgr, f"Multiverse {renderer_type} | {mode_name}",
           (20, height - 20),
           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

# 移除後
# Text overlay removed for clean output
```

**原因**：保持視覺輸出乾淨

---

## 技術細節

### 方法名稱修正

**問題**：初始實作使用錯誤的方法名稱
```python
self.controller.set_channel_intensity(track, value)  # 錯誤
```

**修正**：
```python
self.controller.set_renderer_channel_intensity(track, value)  # 正確
```

### 範圍統一

所有 Track Vol 使用統一範圍：
- 滑桿：0-100
- 實際值：0.0-1.0
- 無「超亮」模式（原 Intensity 可到 1.5）
- 如需整體增亮，使用 COL2 Brightness (0-4.0)

---

## 測試結果

**語法檢查**: 通過
```bash
venv/bin/python3 -m py_compile vav/gui/compact_main_window.py
venv/bin/python3 -m py_compile vav/core/controller.py
```

**程式啟動**: 成功
- Process ID: 77041
- CPU: 112.6%
- Memory: 1.4GB
- 無錯誤訊息

**功能驗證**:
- Track Vol 滑桿正常運作
- 音訊和視覺同步控制
- Ellen Ripley 效果正常
- Multiverse 渲染正常

---

## 優點

1. **介面簡化**
   - 從三組 Level 簡化為一組
   - 減少 8 個滑桿（4×Intensity + 4×Channel Levels）

2. **操作直覺**
   - 一個滑桿控制一個通道的整體存在感
   - 音畫同步，符合視覺系統設計理念

3. **表演友善**
   - 快速調整單一通道
   - 無需分別調整音訊和視覺

4. **保持彈性**
   - Curve 和 Angle 仍可獨立調整
   - Brightness 可整體增亮
   - Ellen Ripley 效果獨立控制

---

## 後續可能優化

1. 重新命名 "Track Vol" 為 "Ch Level" 或 "Channel"
2. 調整 GUI 布局以利用釋放的空間
3. 新增全局 Mute/Solo 功能

---

**修改日期**: 2025-11-04
**狀態**: 完成並測試通過
**修改類型**: GUI simplification + Audio/Visual sync
