# Ellen Ripley Audio Effects 修復紀錄
日期: 2025-11-04

## 問題描述
1. Ellen Ripley啟動後音訊一直斷續
2. 三個效果器mix推桿消失
3. 沒選擇device就按開始會當機

## 修復內容

### 1. Numba JIT 優化 (根據11/3文件)
**問題**: delay.py和reverb.py使用Python for-loop處理音訊導致CPU過載

**修復文件**:
- `vav/audio/effects/delay.py` (lines 11-49)
- `vav/audio/effects/reverb.py` (lines 12-125)

**修改內容**:
- 添加 `@njit(fastmath=True, cache=True)` 裝飾器
- 將Python for-loop改為Numba優化函數
- delay.py: 新增 `process_stereo_delay_numba()` 函數
- reverb.py: 新增 3個Numba函數
  - `process_comb_filter()`
  - `process_allpass_filter()`
  - `process_reverb_numba()`

**性能提升**:
- Delay: 3546x realtime (0.28ms per second)
- Reverb: 113x realtime (8.87ms per second)

### 2. Mix推桿顯示修復
**問題**: 三個mix推桿被chaos checkbox擠壓，沒有獨立標籤

**修復文件**:
- `vav/gui/compact_main_window.py` (lines 523-542, 589-608, 658-677)

**修改內容**:
1. Delay Mix (line 523-536)
   - 添加 "Dly Mix" 標籤
   - 添加數值顯示label (0.00格式)
   - 將Chaos checkbox移到下一行

2. Grain Mix (line 589-602)
   - 添加 "Grn Mix" 標籤
   - 添加數值顯示label
   - 將Chaos checkbox移到下一行

3. Reverb Mix (line 658-671)
   - 添加 "Rev Mix" 標籤
   - 添加數值顯示label
   - 將Chaos checkbox移到下一行

4. Callback更新 (lines 1303-1306, 1327-1330, 1351-1354)
   - `_on_er_delay_mix_changed()`: 更新label文字
   - `_on_er_grain_mix_changed()`: 更新label文字
   - `_on_er_reverb_mix_changed()`: 更新label文字

### 3. Device選擇檢查
**問題**: 沒選擇device就按Start會導致程式當機

**修復文件**:
- `vav/gui/compact_main_window.py` (lines 1019-1041)

**修改內容**:
- `_on_start()` 函數添加device檢查
- 檢查 `self.controller.audio_io` 是否存在
- 檢查 `input_device` 和 `output_device` 是否已配置
- 如果沒有配置，自動調用 `_on_select_device()`
- 設備選擇後再次檢查，確認設備已配置才啟動
- 如果用戶取消或沒選擇設備，顯示"No devices selected"並停止啟動

## 測試狀態
- [x] Numba JIT優化實施完成
- [x] Mix推桿顯示修復完成
- [x] Device選擇檢查修復完成
- [ ] 音訊效果測試 (待用戶測試)
- [ ] Mix推桿功能測試 (待用戶測試)

## 4. SD img2img功能修復（根據10/20歷史文件）
**問題**:
1. SD process啟動但沒有處理frame
2. 初次修復時處理順序錯誤（處理Multiverse渲染結果而非camera frame）

**修復文件**:
- `vav/core/controller.py` (lines 491-564)

**根本問題**（參考 SD_FPS_ISSUE_RESOLVED.md）:
- 錯誤順序：Camera → Multiverse渲染 → SD處理 ❌
- 正確順序：Camera → SD處理 → Region mapping → Multiverse渲染 → 第五層疊加 ✓

**正確架構**（10/20文件）:
1. SD處理camera原始frame（不是渲染結果）
2. 選擇input_frame（SD結果或camera）
3. 用input_frame做region mapping
4. Multiverse渲染4層音頻視覺化
5. 將input_frame作為第五層疊加

**修改內容**:
```python
# 1. SD處理camera frame（如果啟用）
input_frame = frame
if self.sd_enabled and self.sd_img2img:
    self.sd_img2img.feed_frame(frame)  # 餵入camera frame
    sd_output = self.sd_img2img.get_current_output()
    if sd_output is not None:
        input_frame = sd_output  # 使用SD結果

# 2. 用input_frame做region mapping
if self.use_region_rendering:
    region_map = self.region_mapper.create_xxx_regions(input_frame)

# 3. Multiverse渲染
rendered = self.renderer.render(channels_data, region_map)

# 4. 疊加第五層（SD或camera）
if camera_mix > 0.0:
    result = blend(rendered, input_frame, blend_mode, camera_mix)

# 5. CV overlay
result = draw_overlay(result, edges, envelopes)
```

**處理順序**:
```
Camera frame → SD img2img → Region mapping → Multiverse渲染(4層) → 第五層疊加(SD/camera) → CV overlay → Info text
```

## 5. CV Overlay顯示修復
**問題**: 5個CV狀態在Multiverse模式下完全消失

**修復文件**:
- `vav/core/controller.py` (lines 565-570)

**修改內容**:
- 刪除錯誤註釋（原lines 549-550）
- 在相機混合後添加CV overlay繪製
- 調用 `self.contour_cv_generator.draw_overlay()`
- 傳入rendered_bgr、edges和envelopes
- CV overlay現在正確顯示在最上層（除了info text）

**包含的5個CV狀態**:
1. 邊緣檢測結果（白色半透明）
2. SEQ1線條（粉色 #FF8585）+ 當前步驟圓圈
3. SEQ2線條（白色）+ 當前步驟圓圈
4. ENV觸發光圈（粉色/白色/紅色，擴散動畫）
5. 數據儀表板（左上角：Clock BPM、SEQ1/2、ENV1/2/3）

## 6. SD處理順序重大修復
**問題**: 初次修復時SD處理順序錯誤

**調查文件**:
- `archived/SD_FPS_ISSUE_RESOLVED.md` (2025-10-20)
- CHANGELOG.md

**發現**:
- 10/20文件明確定義了正確的SD處理架構
- SD應該處理camera原始frame，不是Multiverse渲染結果
- SD結果用於region mapping輸入
- SD/camera作為第五層疊加到Multiverse上

**最終修復** (controller.py:491-577):
- 將SD處理移到Multiverse渲染**之前**
- **邊緣檢測基於SD處理後的畫面**（用於CV生成）
- Region mapping使用SD結果（如果啟用）
- 第五層疊加正確使用input_frame（SD或camera）

**邊緣檢測順序修復** (controller.py:382-391, 507-512):
```python
# 1. 移除主循環中對原始camera的邊緣檢測（line 382-391）
# 原本 line 383-384:
#   contours, edges = self.contour_cv_generator.detect_contours(gray)
#   self.edges = edges  # 基於原始camera → 這會產生跟camera活動的邊緣 ❌

# 2. 只保留Multiverse內部對SD處理後的邊緣檢測（line 507-512）
gray_input = cv2.cvtColor(input_frame, cv2.COLOR_BGR2GRAY)  # input_frame是SD處理後
contours_new, edges_new = self.contour_cv_generator.detect_contours(gray_input)
self.edges = edges_new  # 基於SD處理後的內容 ✓
```

**問題**：原本有兩個邊緣檢測，導致：
- 白色半透明邊緣：跟隨原始camera活動（不正確）
- CV線條、光圈：跟隨SD處理後的內容（正確）

**解決**：移除主循環中的邊緣檢測，只保留Multiverse內部的檢測。

這確保所有CV視覺化（edges overlay、SEQ線條、ENV光圈）都基於SD風格化後的視覺內容。

## 測試狀態
- [x] Numba JIT優化實施完成
- [x] Mix推桿顯示修復完成
- [x] Device選擇檢查修復完成
- [x] SD img2img處理順序修復完成（根據10/20歷史文件）
- [x] CV overlay繪製邏輯添加完成
- [ ] 音訊效果測試 (待用戶測試)
- [ ] Mix推桿功能測試 (待用戶測試)
- [ ] SD img2img功能測試 (待用戶測試) - 處理順序已修正
- [ ] CV overlay顯示測試 (待用戶測試)
