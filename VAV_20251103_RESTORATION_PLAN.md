# VAV 11/3 版本控制項修復計畫

日期: 2025-11-04
目標: 恢復 11/3 23:00 ~ 11/4 03:01 的正確 GUI 配置

---

## 發現的問題

### 1. ENV Decay 控制錯誤

**目前狀態**:
- ENV 1 Decay (獨立滑桿)
- ENV 2 Decay (獨立滑桿)
- ENV 3 Decay (獨立滑桿)

**應該是**:
- ENV Global Decay (單一指數推桿)
  - 前半段: 0.1s ~ 1s
  - 後半段: 1s ~ 5s
  - 指數映射曲線

**理由**:
- GUI_CONTROLS.md (10/21) 記載統一控制
- 11/3 修改為指數推桿

---

### 2. Anchor XY 控制錯誤

**目前狀態**:
- Anchor X (滑桿，第一列)
- Anchor Y (滑桿，第一列)

**應該是**:
- Anchor XY Pad (2D 拖曳方框)
  - 位置: 第六列下方
  - 功能: 可拖拉的 2D 控件
  - 視覺反饋: 在攝影機畫面顯示錨點位置

**理由**:
- ANALYSIS_SUMMARY.md 記載「可拖拉 + 視覺反饋」
- GUI_MULTIVERSE_ARCHITECTURE_ANALYSIS.md 確認 2D 控件

---

### 3. Ellen Ripley 缺少 Chaos 開關

**目前狀態**:
- Delay: 無 Chaos 開關
- Grain: 無 Chaos 開關
- Reverb: 無 Chaos 開關

**應該有**:
- Dly Chaos (checkbox)
- Grn Chaos (checkbox)
- Rev Chaos (checkbox)

**理由**:
- 10/18 初始版本 (b53ab96) 有完整實現
- archived/CHANGELOG_EllenRipley_Fix.md 詳細記載

---

### 4. Ellen Ripley 缺少 Mix 控制

**目前狀態**:
- Delay: 無 Mix 控制
- Grain: 無 Mix 控制
- Reverb: 無 Mix 控制

**應該有**:
- Dly Mix (slider, 0-100 → 0.0-1.0)
- Grn Mix (slider, 0-100 → 0.0-1.0)
- Rev Mix (slider, 0-100 → 0.0-1.0)

**理由**:
- 10/18 初始版本有完整實現
- archived/CHANGELOG_EllenRipley_Fix.md 記載完整規格

---

### 5. CV Meter Window 不應存在

**目前狀態**:
- compact_main_window.py 第 49-50 行創建並顯示

**應該是**:
- 移除 CV Meter Window
- 只保留主視窗的 Scope Widget

**理由**:
- 10/18 和 10/19 初始版本都沒有 CV Meter Window
- GUI_CONTROLS.md 記載 CV Meters 在主視窗內

---

## 修復計畫

### Phase 1: 文檔記錄
- [x] 創建修復計畫文檔
- [ ] 記錄所有發現的問題

### Phase 2: ENV Decay 修改
- [ ] 移除 ENV 1/2/3 Decay 滑桿
- [ ] 創建單一 ENV Global Decay 滑桿
- [ ] 實現指數映射 (0.1~1s, 1~5s)
- [ ] 連接到 controller 方法

### Phase 3: Anchor XY Pad
- [ ] 創建 2D 拖曳控件 class
- [ ] 放置在第六列下方
- [ ] 實現滑鼠拖曳邏輯
- [ ] 添加視覺反饋到攝影機畫面

### Phase 4: Ellen Ripley Chaos
- [ ] 添加 Dly Chaos checkbox
- [ ] 添加 Grn Chaos checkbox
- [ ] 添加 Rev Chaos checkbox
- [ ] 連接到 controller 方法

### Phase 5: Ellen Ripley Mix
- [ ] 添加 Dly Mix slider (與 Chaos 同行)
- [ ] 添加 Grn Mix slider (與 Chaos 同行)
- [ ] 添加 Rev Mix slider (與 Chaos 同行)
- [ ] 連接到 controller 方法

### Phase 6: 移除 CV Meter Window
- [ ] 移除 compact_main_window.py 中的 CV Meter Window 初始化
- [ ] 移除相關 import
- [ ] 移除 update_values 調用

### Phase 7: 測試驗證
- [ ] 測試所有新控制項功能
- [ ] 驗證參數範圍
- [ ] 確認無錯誤

---

## 控制項布局規格

### 第一列 (COL1) - CV 生成

```
ENV Global Decay: [━━━━━━] "1.0s"    # 指數推桿
SEQ 1 Steps: [━━━━━━] "8"
SEQ 2 Steps: [━━━━━━] "8"
Clock BPM: [━━━━━━] "120"
Range: [━━━━━━] "50%"
Edge Threshold: [━━━━━━] "50"
Temporal Smoothing: [━━━━━━] "50"
Min Length: [━━━━━━] "50"
```

### 第五列 (COL5) - Ellen Ripley Delay+Grain

```
Delay Time L: [━━━━━━] "0.25"
Delay Time R: [━━━━━━] "0.25"
Delay FB: [━━━━━━] "0.30"
[✓] Dly Chaos  [━━━━━━━━━━] Dly Mix    # 同一行
Grain Size: [━━━━━━] "0.30"
Grain Density: [━━━━━━] "0.40"
Grain Position: [━━━━━━] "0.50"
[✓] Grn Chaos  [━━━━━━━━━━] Grn Mix    # 同一行
```

### 第六列 (COL6) - Ellen Ripley Reverb+Chaos

```
Reverb Room: [━━━━━━] "0.50"
Reverb Damp: [━━━━━━] "0.40"
Reverb Decay: [━━━━━━] "0.60"
[✓] Rev Chaos  [━━━━━━━━━━] Rev Mix    # 同一行
Chaos Rate: [━━━━━━] "0.01"
Chaos Amount: [━━━━━━] "1.00"
[✓] Chaos Shape

--- 以下為新增區域 ---

Anchor XY Pad:
┌─────────────┐
│             │
│      ●      │  # 可拖曳的錨點
│             │
└─────────────┘
X: 50%  Y: 50%
```

---

## 指數推桿實現

### ENV Global Decay 映射公式

```python
# Slider 範圍: 0-100
# 前半段 (0-50): 0.1s ~ 1s
# 後半段 (50-100): 1s ~ 5s

def slider_to_decay_time(value: int) -> float:
    """將滑桿值映射到 decay 時間（指數）"""
    if value <= 50:
        # 前半段: 指數映射 0.1 ~ 1.0
        t = value / 50.0  # 0 ~ 1
        return 0.1 * (10.0 ** t)  # 0.1 ~ 1.0
    else:
        # 後半段: 指數映射 1.0 ~ 5.0
        t = (value - 50) / 50.0  # 0 ~ 1
        return 1.0 * (5.0 ** t)  # 1.0 ~ 5.0

def decay_time_to_slider(time: float) -> int:
    """將 decay 時間映射回滑桿值"""
    if time <= 1.0:
        # 前半段
        t = np.log10(time / 0.1)  # 0 ~ 1
        return int(t * 50)
    else:
        # 後半段
        t = np.log(time / 1.0) / np.log(5.0)  # 0 ~ 1
        return int(50 + t * 50)
```

---

## 2D Anchor XY Pad 實現

### Widget 規格

```python
class AnchorXYPad(QWidget):
    """2D 拖曳方框控件"""

    # 信號
    position_changed = pyqtSignal(float, float)  # x_pct, y_pct

    def __init__(self):
        super().__init__()
        self.x_pct = 50.0  # 0-100
        self.y_pct = 50.0  # 0-100
        self.setMinimumSize(140, 140)
        self.setMaximumSize(140, 140)

    def paintEvent(self, event):
        """繪製 pad 和錨點"""
        painter = QPainter(self)
        # 繪製邊框
        # 繪製網格
        # 繪製錨點（圓形）

    def mousePressEvent(self, event):
        """滑鼠按下"""
        self._update_position(event.pos())

    def mouseMoveEvent(self, event):
        """滑鼠拖曳"""
        self._update_position(event.pos())

    def _update_position(self, pos):
        """更新錨點位置"""
        # 計算百分比
        # emit position_changed
        # update()
```

---

## Controller 方法需求

### 新增方法

```python
# vav/core/controller.py

def set_global_env_decay(self, time: float):
    """設定所有 envelope 的 decay 時間"""
    for env in self.envelopes:
        env.set_decay_time(time)

def set_er_delay_chaos(self, enabled: bool):
    """設定 Delay chaos 開關"""
    if self.ellen_ripley:
        self.ellen_ripley.set_delay_chaos_enabled(enabled)

def set_er_delay_mix(self, mix: float):
    """設定 Delay wet/dry mix"""
    if self.ellen_ripley:
        self.ellen_ripley.set_delay_wet_dry(mix)

# ... 同樣方法給 Grain 和 Reverb
```

---

## 參考文件

- GUI_CONTROLS.md (10/21)
- ANALYSIS_SUMMARY.md (11/4)
- archived/CHANGELOG_EllenRipley_Fix.md
- 10/18 初始版本 (b53ab96)

---

完成後標籤: VAV_20251103_RESTORED
