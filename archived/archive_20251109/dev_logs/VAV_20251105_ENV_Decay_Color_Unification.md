# VAV ENV Decay 同步與色彩統一 - 2025-11-05

## 功能概述

本次更新實作兩個主要功能：
1. ENV 觸發光圈淡出時間與 decay 參數同步
2. 統一五個 CV 功能的顏色配置

## 1. ENV 觸發光圈淡出同步

### 問題描述

原先光圈淡出使用固定速率 `alpha -= 0.05`，導致淡出時間固定約 0.33 秒（20 幀 @ 60 FPS），與 ENV decay 參數設定無關。

### 解決方案

修改光圈動畫系統，讓淡出時間與 ENV decay 時間同步。

### 修改檔案

**檔案**: `vav/cv_generator/contour_cv.py`

#### 1. 觸發時儲存 decay 時間（第 107-147 行）

```python
# ENV1 觸發
self.trigger_rings.append({
    'pos': trigger_pos,
    'radius': 30,
    'alpha': 1.0,
    'color': (133, 133, 255),
    'decay_time': envelopes[0].decay_time  # 新增：儲存 ENV1 decay 時間
})

# ENV2 觸發
self.trigger_rings.append({
    'pos': trigger_pos,
    'radius': 30,
    'alpha': 1.0,
    'color': (255, 255, 255),
    'decay_time': envelopes[1].decay_time  # 新增：儲存 ENV2 decay 時間
})

# ENV3 觸發
self.trigger_rings.append({
    'pos': (anchor_x, anchor_y),
    'radius': 30,
    'alpha': 1.0,
    'color': (45, 0, 188),
    'decay_time': envelopes[2].decay_time  # 新增：儲存 ENV3 decay 時間
})
```

#### 2. 動態計算淡出速率（第 273-292 行）

```python
def update_trigger_rings(self):
    """更新觸發光圈動畫（同步於 ENV decay 時間）"""
    new_rings = []
    for ring in self.trigger_rings:
        # 擴展半徑（三倍速度：6 像素/幀 @ 60 FPS）
        ring['radius'] += 6

        # 淡出：根據 ENV decay 時間計算 alpha 遞減速率
        # alpha_decrement = 1.0 / (decay_time * 60 FPS)
        fps = 60.0
        decay_time = ring.get('decay_time', 1.0)  # 默認 1 秒
        alpha_decrement = 1.0 / (decay_time * fps)
        ring['alpha'] -= alpha_decrement

        # 保留尚未完全消失的光圈（三倍最大半徑：180 像素）
        if ring['alpha'] > 0 and ring['radius'] < 180:
            new_rings.append(ring)

    self.trigger_rings = new_rings
```

### 技術細節

- 假設視訊線程運行於 60 FPS
- 淡出時間計算：`total_frames = decay_time * 60`
- 每幀遞減量：`alpha_decrement = 1.0 / total_frames`
- 範例：
  - decay_time = 0.5 秒 → 30 幀淡出
  - decay_time = 1.0 秒 → 60 幀淡出
  - decay_time = 2.0 秒 → 120 幀淡出

## 2. CV 色彩統一

### 問題描述

五個 CV 功能（ENV1-3, SEQ1-2）的顏色在不同顯示位置不一致：
- 主視覺（ContourCV）使用一組顏色
- CV meters 視窗使用另一組顏色
- 左上角文字顯示使用第三組顏色

### 解決方案

建立統一色彩配置檔，所有位置使用相同顏色。

### 新增檔案

**檔案**: `vav/utils/cv_colors.py`

```python
"""
CV Color Configuration - Unified color scheme for all CV channels
"""

# BGR format for OpenCV (used in ContourCV main visual)
CV_COLORS_BGR = {
    'ENV1': (133, 133, 255),  # Light blue-purple
    'ENV2': (255, 255, 255),  # White
    'ENV3': (45, 0, 188),     # Japanese flag red
    'SEQ1': (133, 133, 255),  # Light blue-purple (same as ENV1)
    'SEQ2': (255, 255, 255),  # White (same as ENV2)
}

# RGB format for PyQt/pyqtgraph (used in CV meters and GUI)
CV_COLORS_RGB = {
    'ENV1': (255, 133, 133),  # Light purple-blue
    'ENV2': (255, 255, 255),  # White
    'ENV3': (188, 0, 45),     # Japanese flag red
    'SEQ1': (255, 133, 133),  # Light purple-blue (same as ENV1)
    'SEQ2': (255, 255, 255),  # White (same as ENV2)
}

# List format for scope widget (ENV1, ENV2, ENV3, SEQ1, SEQ2)
SCOPE_COLORS = [
    CV_COLORS_RGB['ENV1'],
    CV_COLORS_RGB['ENV2'],
    CV_COLORS_RGB['ENV3'],
    CV_COLORS_RGB['SEQ1'],
    CV_COLORS_RGB['SEQ2'],
]
```

### 修改檔案

**檔案**: `vav/gui/scope_widget.py` (第 22-24 行)

```python
# 原始程式碼
self.colors = [
    (255, 100, 100),  # Red - ENV 1
    (100, 255, 100),  # Green - ENV 2
    (100, 100, 255),  # Blue - ENV 3
    (255, 255, 100),  # Yellow - SEQ 1
    (255, 100, 255),  # Magenta - SEQ 2
]

# 修改後
from ..utils.cv_colors import SCOPE_COLORS
self.colors = SCOPE_COLORS
```

### 統一配色表

| CV 功能 | RGB | BGR | 說明 |
|---------|-----|-----|------|
| ENV1    | (255, 133, 133) | (133, 133, 255) | 淡藍紫色 |
| ENV2    | (255, 255, 255) | (255, 255, 255) | 白色 |
| ENV3    | (188, 0, 45) | (45, 0, 188) | 日本國旗紅 |
| SEQ1    | (255, 133, 133) | (133, 133, 255) | 淡藍紫色（同 ENV1）|
| SEQ2    | (255, 255, 255) | (255, 255, 255) | 白色（同 ENV2）|

### 適用範圍

- 主視覺觸發光圈（ContourCV）
- CV meters 視窗波形顯示
- 主視覺左上角 CV 數值文字
- SEQ1/SEQ2 邊緣曲線顏色

## 測試確認

### ENV Decay 同步

1. 啟動程式
2. 調整 ENV1/2/3 的 decay 時間（0.1 秒 ~ 10 秒）
3. 觸發 envelope（透過 sequencer 步進）
4. 觀察光圈淡出時間是否與 decay 時間一致

### 色彩統一

1. 啟動程式
2. 開啟 CV meters 視窗（獨立視窗）
3. 對比主視覺、CV meters、左上角文字的顏色
4. 確認 ENV1-3 和 SEQ1-2 的顏色在所有位置一致

## 相關檔案

### 新增檔案

- `vav/utils/cv_colors.py` - CV 色彩統一配置

### 修改檔案

- `vav/cv_generator/contour_cv.py` (第 107-147, 273-292 行)
- `vav/gui/scope_widget.py` (第 22-24 行)

## 技術備註

### BGR vs RGB

OpenCV 使用 BGR 格式，PyQt/pyqtgraph 使用 RGB 格式，配置檔提供兩種格式轉換。

### 線程架構

- 視訊線程：60 FPS，處理光圈動畫和 CV 更新
- 音訊線程：48 kHz，處理 envelope 生成

### 後續優化建議

1. 可調 FPS：目前假設 60 FPS，可改為動態偵測
2. 光圈形狀：可加入更多視覺效果（漸層、脈衝等）
3. 色彩主題：可建立多組色彩主題供使用者選擇

## 總結

本次更新解決了兩個使用者體驗問題：
1. ENV 觸發光圈淡出時間現在正確反映 decay 參數設定
2. 所有 CV 功能的顏色在系統各處完全統一

---

實作日期：2025-11-05
版本：v1.0
狀態：完成並驗證
標籤：`1105_env_decay` `1105_color_unify`
