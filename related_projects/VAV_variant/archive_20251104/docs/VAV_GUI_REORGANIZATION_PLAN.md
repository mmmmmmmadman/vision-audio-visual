# VAV GUI 重新組織計畫

日期: 2025-11-04
目標: 重新排列 GUI 控制項布局，加入 SD img2img 功能

---

## 用戶需求

1. 把第二列（Mixer）移動到第一列（CV Source）下方
2. Multiverse 單軌控制（Curve, Angle, Intensity）合併在同一列（目前的第四列）
3. AI SD 功能放在目前的第三列下方

---

## 當前布局 (6列)

```
COL1: CV Source (CV 生成參數)
├─ ENV Global Decay
├─ SEQ 1/2 Steps
├─ Clock BPM
├─ Range, Edge Threshold, Temporal Smoothing
└─ Min Length

COL2: Mixer (4 軌音量)
├─ Track 1 Vol
├─ Track 2 Vol
├─ Track 3 Vol
└─ Track 4 Vol

COL3: Multiverse Main (全局控制)
├─ Enable Multiverse
├─ Blend Mode
├─ Brightness
└─ Camera Mix

COL4: Multiverse Channels (分軌控制)
├─ Ch1 Curve, Angle, Intensity
├─ Ch2 Curve, Angle, Intensity
├─ Ch3 Curve, Angle, Intensity
└─ Ch4 Curve, Angle, Intensity

COL5: Ellen Ripley Delay+Grain
├─ Delay Time L/R, FB
├─ Dly Chaos, Dly Mix
├─ Grain Size, Density, Position
└─ Grn Chaos, Grn Mix

COL6: Ellen Ripley Reverb+Chaos
├─ Reverb Room, Damp, Decay
├─ Rev Chaos, Rev Mix
├─ Chaos Rate, Amount, Shape
└─ Anchor XY Pad
```

---

## 新布局 (5列)

```
COL1: CV Source + Mixer (合併)
├─ ENV Global Decay
├─ SEQ 1/2 Steps
├─ Clock BPM
├─ Range, Edge Threshold, Temporal Smoothing
├─ Min Length
├─ --- Mixer (分隔) ---
├─ Track 1 Vol
├─ Track 2 Vol
├─ Track 3 Vol
└─ Track 4 Vol

COL2: Multiverse Main
├─ Enable Multiverse
├─ Blend Mode
├─ Brightness
└─ Camera Mix

COL3: Multiverse Channels (合併 4 軌，每軌 3 控制項在同一列)
├─ Ch1: Curve [━━] Angle [━━] Intensity [━━]
├─ Ch2: Curve [━━] Angle [━━] Intensity [━━]
├─ Ch3: Curve [━━] Angle [━━] Intensity [━━]
├─ Ch4: Curve [━━] Angle [━━] Intensity [━━]
├─ --- SD img2img (分隔) ---
├─ SD Enable [✓]
├─ SD Prompt: [________________]
│             [________________]  (多行文字框)
├─ Steps [━━━━━━] "2"
├─ Strength [━━━━━━] "0.50"
├─ Guidance [━━━━━━] "1.0"
└─ Gen Interval [0.5] (秒)

COL4: Ellen Ripley Delay+Grain
├─ Delay Time L/R, FB
├─ Dly Chaos, Dly Mix
├─ Grain Size, Density, Position
└─ Grn Chaos, Grn Mix

COL5: Ellen Ripley Reverb+Chaos
├─ Reverb Room, Damp, Decay
├─ Rev Chaos, Rev Mix
├─ Chaos Rate, Amount, Shape
└─ Anchor XY Pad
```

---

## 修改計畫

### Phase 1: 分析 SD img2img 實現

- [x] 找到 SD 相關模組
  - `vav/visual/sd_img2img_process.py` (10/20 創建)
  - `vav/visual/sd_shape_generator.py` (10/19 創建)
- [ ] 分析 SD img2img 的 API 接口
- [ ] 檢查 controller 中是否有 SD 整合

### Phase 2: 重新排列現有控制項

- [ ] COL1: 移除 Mixer 相關代碼
- [ ] COL1: 在 CV Source 下方添加 Mixer 控制項
- [ ] COL4: 修改 Multiverse Channels 布局
  - 目前：每軌垂直排列 (Curve, Angle, Intensity)
  - 新：每軌水平排列在同一列

### Phase 3: 添加 SD img2img 控制項

- [ ] COL3: 在 Multiverse Channels 下方添加分隔
- [ ] COL3: 添加 SD Enable checkbox
- [ ] COL3: 添加 SD Prompt 多行文字框 (QTextEdit)
- [ ] COL3: 添加 Steps slider (1-20)
- [ ] COL3: 添加 Strength slider (50-100 → 0.50-1.00)
- [ ] COL3: 添加 Guidance slider (10-150 → 1.0-15.0)
- [ ] COL3: 添加 Gen Interval 文字輸入框

### Phase 4: Controller 整合

- [ ] 檢查 controller 是否已有 SD 整合
- [ ] 添加 SD img2img 初始化
- [ ] 連接 GUI 控制項到 SD 參數更新
- [ ] 實現 SD 輸出混合到 Multiverse 渲染

### Phase 5: 測試驗證

- [ ] 測試新布局顯示正確
- [ ] 測試 SD 控制項功能
- [ ] 驗證參數範圍
- [ ] 確認無錯誤

---

## SD img2img 控制項規格

根據 GUI_CONTROLS.md:

| 名稱 | 類型 | 範圍 | 預設值 | 功能 |
|------|------|------|--------|------|
| SD img2img | Checkbox | ON/OFF | OFF | 啟用 Stable Diffusion |
| SD Prompt | Text Area | 多行文字 | "artistic style, abstract, monochrome ink painting" | 提示詞 |
| Steps | Slider | 1-20 | 2 | 生成步數 |
| Strength | Slider | 50-100 (→ 0.50-1.00) | 50 (0.50) | 轉換強度 |
| Guidance | Slider | 10-150 (→ 1.0-15.0) | 10 (1.0) | Guidance Scale |
| Gen Interval | Text Input | 秒數 | 0.5 | 生成間隔 |

---

## SD img2img 實現細節

### 模組: `sd_img2img_process.py`

**功能**：
- 使用 multiprocessing 將 SD 推理隔離到獨立進程
- LCM + TAESD 快速生成 (2 steps, ~2s per frame)
- 支援即時更新 prompt 和參數

**API**：
```python
class SDImg2ImgProcess:
    def __init__(self, output_width=1280, output_height=720, fps_target=30)
    def start()  # 啟動 SD 進程
    def stop()   # 停止 SD 進程
    def feed_frame(input_frame)  # 餵入 frame
    def get_current_output() -> np.ndarray  # 取得結果
    def set_prompt(prompt: str)  # 更新 prompt
    def set_parameters(strength, guidance_scale, num_steps)  # 更新參數
```

**參數**：
- `prompt`: 提示詞
- `strength`: 0.5-1.0 (轉換強度)
- `guidance_scale`: 1.0-15.0
- `num_steps`: 1-20 (LCM 優化為 2 steps)
- `send_interval`: 控制發送頻率 (預設 1.5s)

---

## 問題與考慮

### 1. SD 進程資源

SD img2img 需要大量 GPU 資源：
- 載入模型: ~2GB VRAM
- 推理時間: ~2s per frame (512×512)
- 可能與 Multiverse 渲染競爭資源

**解決方案**：
- 使用獨立進程隔離 (已實現)
- 調整 Gen Interval 避免過度生成
- 可選功能，預設關閉

### 2. 控制項空間

COL3 需要容納：
- 4 軌 × 3 控制項 = 12 個控制項
- SD 6 個控制項
- 總共 18 個控制項

**解決方案**：
- 每軌 3 控制項水平排列（節省垂直空間）
- SD Prompt 使用多行文字框（高度 ~60px）
- 適當調整行高

### 3. Controller 整合

需要確認 controller 是否已有 SD 整合：
- 檢查 `controller.py` 中是否有 `sd_img2img` 實例
- 檢查渲染管線是否支援 SD 輸出混合

---

## 參考文件

- GUI_CONTROLS.md (10/21) - 原始控制項規格
- vav/visual/sd_img2img_process.py - SD 實現
- vav/visual/sd_shape_generator.py - SD 形狀生成
- ANALYSIS_SUMMARY.md - GUI 架構分析

---

## 下一步

1. 用戶確認新布局設計
2. 檢查 controller 中 SD 整合狀態
3. 開始實現 Phase 2（重新排列控制項）
4. 實現 Phase 3（添加 SD 控制項）

