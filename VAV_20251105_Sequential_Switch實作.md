# VAV Sequential Switch 實作記錄 - 2025-11-05

## 功能概述

實作 Sequential Switch 功能：讓兩個 sequencer (SEQ1 和 SEQ2) 輪流控制四個視覺通道的參數。

### 設計規格

- **SEQ1** → 控制 **Curve** 參數 (0-5 範圍)
  - 每個步進輪流更新 Channel 0 → 1 → 2 → 3 → 0...

- **SEQ2** → 控制 **Angle** 參數 (0-720° 範圍，兩圈)
  - 每個步進輪流更新 Channel 0 → 1 → 2 → 3 → 0...

## 問題診斷過程

### 初始問題

用戶反映：
1. Curve 和 Angle 參數沒有在變動
2. GUI 推桿沒有跟著移動
3. 獨立 CV meters 視窗中 seq1/seq2 完全沒有訊號
4. 但主視窗左上角的 seq1/seq2 數值有在移動
5. ES-8 輸出也沒有 seq1/seq2 訊號

### 根本原因分析

發現系統中存在 **兩套獨立的 SEQ1/SEQ2 系統**：

#### 系統 A：ContourCV Generator (有數據)
- **位置**: `vav/cv_generator/contour_cv.py`
- **數據來源**: 從畫面邊緣檢測生成序列
- **更新位置**: 視訊線程 (60Hz) 的 `update_sequencer_and_triggers()`
- **儲存位置**:
  - `contour_cv_generator.seq1_value` (0-1 範圍)
  - `contour_cv_generator.seq2_value` (0-1 範圍)
- **用途**: 主視窗左上角文字顯示

#### 系統 B：Internal Sequencers (無數據)
- **位置**: `controller.sequencers[0]` 和 `controller.sequencers[1]`
- **數據來源**: 內部 `SequenceCV` 類別
- **更新位置**: 音訊線程 (48kHz) 的 `_audio_callback()`
- **儲存位置**:
  - `controller.cv_values[3]` → SEQ1
  - `controller.cv_values[4]` → SEQ2
- **用途**:
  - CV meters 顯示
  - ES-8 輸出
  - Sequential switch 邏輯讀取來源

**問題核心**：Sequential switch 讀取 `cv_values[3]/[4]`，但這兩個值一直是 0，因為內部 sequencers 的 sequence 陣列從未被初始化數據。真正的序列數據在 ContourCV 中。

## 解決方案

### 方案概述

統一數據流：讓 `cv_values[3]/[4]` 直接從 ContourCV 讀取，而不使用內部 sequencers。

### 實作步驟

#### 1. 修改 Audio Callback 的 SEQ 更新邏輯

**檔案**: `vav/core/controller.py:680-693`

**原始邏輯** (錯誤):
```python
# Update sequencers
for j, seq in enumerate(self.sequencers):
    self.cv_values[3 + j] = seq.process()
```

**新邏輯** (正確):
```python
# Update SEQ1/SEQ2 from ContourCV generator (直接使用 ContourCV 的值)
if self.contour_cv_generator:
    self.cv_values[3] = self.contour_cv_generator.seq1_value  # SEQ1
    self.cv_values[4] = self.contour_cv_generator.seq2_value  # SEQ2
else:
    # Fallback: use internal sequencers if ContourCV not available
    for j, seq in enumerate(self.sequencers):
        self.cv_values[3 + j] = seq.process()
```

**效果**: CV meters 和 ES-8 現在會顯示正確的 seq1/seq2 數值。

#### 2. 在 ContourCV 加入步進變化標記

**檔案**: `vav/cv_generator/contour_cv.py`

**新增成員變數** (第 46-48 行):
```python
# 步進變化標記（供 sequential switch 使用）
self.seq1_step_changed = False
self.seq2_step_changed = False
```

**更新步進邏輯** (第 83-99 行):
```python
# 統一時鐘步進邏輯（SEQ1 和 SEQ2 同步）
self.step_timer += dt
step_interval = 60.0 / self.clock_rate if self.clock_rate > 0 else 0.5

# 重置步進標記
self.seq1_step_changed = False
self.seq2_step_changed = False

if self.step_timer >= step_interval:
    self.step_timer = 0.0
    # 同步步進
    self.current_step_x = (self.current_step_x + 1) % self.num_steps_x
    self.current_step_y = (self.current_step_y + 1) % self.num_steps_y

    # 讀取當前步的值（0-1）
    self.seq1_value = self.seq1_values[self.current_step_x]
    self.seq2_value = self.seq2_values[self.current_step_y]

    # 設置步進變化標記
    self.seq1_step_changed = True
    self.seq2_step_changed = True
```

**效果**: Sequential switch 可以偵測到步進變化時機。

#### 3. 實作 Sequential Switch 邏輯

**檔案**: `vav/core/controller.py:600-620`

**原始狀態** (空函數):
```python
def _update_cv_values(self):
    """Update CV generator values (NOTE: sequencers are processed in audio callback)"""
    pass
```

**新實作** (完整邏輯):
```python
def _update_cv_values(self):
    """Update CV generator values and handle sequential switch"""
    # Sequential switch logic: check if ContourCV seq1/seq2 stepped
    if self.contour_cv_generator:
        # SEQ1 -> Curve (輪流控制 channel 0-3 的 curve, 擴大範圍 0-5)
        if self.contour_cv_generator.seq1_step_changed:
            seq1_value = self.contour_cv_generator.seq1_value
            curve_value = seq1_value * 5.0
            self.renderer_params['channel_curves'][self.seq1_current_channel] = curve_value
            if self.param_callback:
                self.param_callback("curve", self.seq1_current_channel, curve_value)
            self.seq1_current_channel = (self.seq1_current_channel + 1) % 4

        # SEQ2 -> Angle (輪流控制 channel 0-3 的 angle, 擴大範圍多圈)
        if self.contour_cv_generator.seq2_step_changed:
            seq2_value = self.contour_cv_generator.seq2_value
            angle_value = seq2_value * 720.0
            self.renderer_params['channel_angles'][self.seq2_current_channel] = angle_value
            if self.param_callback:
                self.param_callback("angle", self.seq2_current_channel, angle_value)
            self.seq2_current_channel = (self.seq2_current_channel + 1) % 4
```

**邏輯說明**:
- 在視訊線程 (60Hz) 中運行
- 檢測 ContourCV 的步進變化標記
- SEQ1 步進時：更新當前 channel 的 curve，然後輪轉到下一個 channel
- SEQ2 步進時：更新當前 channel 的 angle，然後輪轉到下一個 channel
- 通過 `param_callback` 通知 GUI 更新推桿位置

## 技術細節

### 線程架構

- **視訊線程 (60Hz)**:
  - `_update_cv_values()` - Sequential switch 邏輯
  - `ContourCV.update_sequencer_and_triggers()` - 步進更新

- **音訊線程 (48kHz)**:
  - `_audio_callback()` - 讀取 ContourCV 數值到 `cv_values[3]/[4]`
  - Envelope 處理

### 數據映射

| ContourCV | cv_values[] | 用途 | 範圍 |
|-----------|-------------|------|------|
| seq1_value | cv_values[3] | SEQ1 輸出 | 0.0 - 1.0 |
| seq2_value | cv_values[4] | SEQ2 輸出 | 0.0 - 1.0 |
| - | curve_value | Curve 參數 | 0.0 - 5.0 |
| - | angle_value | Angle 參數 | 0.0 - 720.0 |

### 參數範圍擴展

```python
# SEQ1 → Curve (0-1 擴展到 0-5)
curve_value = seq1_value * 5.0

# SEQ2 → Angle (0-1 擴展到 0-720°，兩圈)
angle_value = seq2_value * 720.0
```

## 驗證結果

### ✅ 功能確認

1. **CV Meters 顯示**: seq1/seq2 現在有數值顯示
2. **ES-8 輸出**: seq1/seq2 正常輸出到硬體
3. **Sequential Switch**: 每個步進時正確更新對應 channel 的參數
4. **GUI 同步**: 推桿位置隨參數變化移動
5. **視覺效果**: 四個通道的 curve 和 angle 輪流變化

### 測試方法

1. 啟動程式
2. 確認主視窗左上角 seq1/seq2 有數值
3. 開啟獨立 CV meters 視窗，確認 seq1/seq2 有訊號
4. 觀察四個通道的 curve 和 angle 推桿是否輪流移動
5. 確認視覺輸出有對應變化

## 相關檔案

### 修改檔案

1. `vav/core/controller.py`
   - 第 680-693 行: Audio callback SEQ 更新邏輯
   - 第 600-620 行: Sequential switch 實作

2. `vav/cv_generator/contour_cv.py`
   - 第 46-48 行: 步進變化標記定義
   - 第 83-99 行: 步進變化標記更新邏輯

### 相關檔案 (未修改)

- `vav/cv_generator/sequencer.py` - 保留作為 fallback
- `vav/gui/compact_main_window.py` - 已有 `param_updated` signal 支援

## 後續優化建議

### 可選功能

1. **獨立步進控制**: SEQ1 和 SEQ2 使用不同的 BPM
2. **可調範圍**: 讓使用者自訂 curve 和 angle 的範圍
3. **步進模式**:
   - 循環模式 (0→1→2→3→0)
   - 往返模式 (0→1→2→3→2→1→0)
   - 隨機模式
4. **步進目標選擇**: 可選擇控制其他參數 (如 scale, brightness 等)

### 效能優化

- 目前 sequential switch 在視訊線程 (60Hz)，時序已足夠精確
- 如需更精確時序，可考慮移至音訊線程，但需處理線程安全

## 總結

成功實作 Sequential Switch 功能，解決了兩套獨立 sequencer 系統的數據同步問題。核心解法是讓所有系統統一使用 ContourCV 作為唯一數據來源，並在視訊線程中實作步進檢測和參數輪轉邏輯。

---

**實作日期**: 2025-11-05
**版本**: v1.0
**狀態**: ✅ 完成並驗證
