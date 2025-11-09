# VAV 變更日誌 - 2025-10-19

## Sequencer CV 邏輯重構

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
問題：X 和 Y 座標分離後無法保留 2D 空間關係，導致對角線分布問題

**修改後（正確）：**
```python
self.seq_point_positions = [(x1,y1), (x2,y2), ..., (x16,y16)]  # 統一的特徵點列表
```
優點：保留完整的 2D 位置資訊

### Sequencer 運作邏輯
- **SEQ1**：垂直掃描線
  - 使用 `point_positions[current_step].x` 作為 X 座標
  - CV 值控制掃描線亮度（160-255 灰階）

- **SEQ2**：水平掃描線
  - 使用 `point_positions[current_step].y` 作為 Y 座標
  - CV 值控制掃描線亮度（160-255 灰階）

- **獨立時鐘**：兩個 sequencer 各自獨立運行
  - 可設定不同的 BPM
  - 可設定相同的 steps 數量（統一控制）

### 背景執行緒優化
```python
# 執行緒參數
update_interval = 0.5s          # 每 0.5 秒更新一次
resolution_scale = 4            # 1920x1080 → 480x270
smoothing_alpha = 0.3           # 30% 新數據 + 70% 舊數據
```

效能提升：
- Multiverse 渲染維持 30-60 fps
- 特徵點偵測不會阻塞主執行緒
- 移動平均平滑化避免點位跳動

### CV Overlay 視覺化
新增 `/vav/visual/cv_overlay.py`

**顯示元素：**
1. **白色方格**：標記偵測到的特徵點位置（16x16 像素）
2. **垂直掃描線**（SEQ1）：灰色，亮度受 CV 值調變
3. **水平掃描線**（SEQ2）：灰色，亮度受 CV 值調變
4. **交叉點標記**：白色圓圈（半徑 16px）
5. **CV 數值顯示**：顯示 SEQ1 和 SEQ2 的 CV 值

---

## Region Mode 簡化

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

## GUI 布局優化

### 從 6 列改為 5 列

**舊布局（6 列）：**
1. CV Source (ENV, SEQ)
2. Mixer (Track 1-4 Vol)
3. Multiverse Main
4. Multiverse Channels
5. Ellen Ripley Delay+Grain
6. Ellen Ripley Reverb+Chaos

**新布局（5 列）：**
1. **CV Source + Mixer**
   - ENV 1-3 Decay
   - SEQ Steps（統一控制）
   - SEQ Freq（統一控制）
   - Corner Quality
   - Track 1-4 Vol ← 移動到這裡

2. **Multiverse Main**
   - Multiverse checkbox
   - Blend mode
   - Brightness
   - Camera Mix
   - Region Map + CV Overlay（同一行）← 合併
   - Ch1-2 controls（Curve, Angle, Intensity）

3. **Multiverse Channels**
   - Ch3-4 controls（Curve, Angle, Intensity）

4. **Ellen Ripley Delay+Grain**
   - （保持不變）

5. **Ellen Ripley Reverb+Chaos**
   - （保持不變）

### Grid 配置變更
```python
# 舊：6 visual columns x 3 grid columns = 18 + 1 stretch
# 新：5 visual columns x 3 grid columns = 15 + 1 stretch
for i in range(15):
    controls_grid.setColumnStretch(i, 0)
controls_grid.setColumnStretch(15, 1)
```

---

## 檔案清理

### 刪除的檔案
1. `/vav/vision/cable_detector.py` - MediaPipe cable detection（已棄用）
2. `/vav/vision/analyzer.py` - Cable analysis for CV（已棄用）
3. `/vav/visual/region_mapper.py` - 靜態 region patterns（已棄用）
4. `REGION_RENDERING_GUIDE.md` - 過時的文檔

### 新增的檔案
1. `/vav/visual/cv_overlay.py` - CV 視覺化疊加層

---

## 技術細節

### Corner Detection 演算法
```python
corners = cv2.goodFeaturesToTrack(
    gray_image,
    maxCorners=num_steps * 2,
    qualityLevel=0.01 + (threshold/200.0) * 0.49,  # 10-200 → 0.01-0.5
    minDistance=min(width, height) // (num_steps + 2),
    blockSize=7
)
```

### 平滑化演算法
```python
alpha = 0.3
smoothed_x = alpha * new_x + (1 - alpha) * old_x
smoothed_y = alpha * new_y + (1 - alpha) * old_y
```

### 執行緒安全
```python
# controller.py
self.seq_point_positions_lock = threading.Lock()

# 寫入（背景執行緒）
with self.seq_point_positions_lock:
    self.seq_point_positions = smoothed_points

# 讀取（主執行緒）
with self.seq_point_positions_lock:
    points = self.seq_point_positions.copy()
```

---

## 測試結果

### 效能
- ✓ Multiverse 渲染：30-60 fps（無下降）
- ✓ Corner detection：0.5s 更新間隔（背景執行緒）
- ✓ GUI 回應性：無延遲

### 功能
- ✓ Sequencer CV 正常輸出
- ✓ 特徵點平滑追蹤
- ✓ CV Overlay 正確顯示
- ✓ Region Brightness 正常運作
- ✓ GUI 布局緊湊無錯位

### 已知問題
- 無新問題

---

## 後續工作建議

1. 考慮加入特徵點持續性追蹤（optical flow）
2. 可調整的平滑化參數（目前固定 alpha=0.3）
3. 特徵點視覺化選項（顯示/隱藏方格）
4. Corner Quality 參數的即時反饋

---

**記錄日期：2025-10-19**
**版本：VAV_20251019**
