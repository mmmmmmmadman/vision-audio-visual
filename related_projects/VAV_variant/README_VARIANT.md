# VAV Variant - 輪廓掃描版本

## 變更內容

這是 VAV 的變化版，主要修改了 Seq1/2 和 Env1-3 的產生邏輯。

### 原版 (VAV)
- 使用 Sample & Hold 離散採樣
- BPM 驅動步進
- 階梯式電壓變化

### 變化版 (VAV_variant)
- **連續掃描輪廓線**
- **掃描時間**控制（取代 BPM）
- **連續變化**的電壓輸出

## 新的 CV 邏輯

### SEQ1 (X 座標 CV)
- 連續輸出當前掃描點的 X 座標
- 範圍：0-10V（對應畫面寬度）
- 變化方式：沿著輪廓線平滑移動

### SEQ2 (Y 座標 CV)
- 連續輸出當前掃描點的 Y 座標
- 範圍：0-10V（對應畫面高度）
- 變化方式：沿著輪廓線平滑移動

### ENV1 (X > Y 區域)
- 當 SEQ1 > SEQ2 時輸出差值，否則輸出 0
- 範圍：0-10V
- 意義：掃描點在畫面右上區域時有值
- 公式：ENV1 = max(0, SEQ1 - SEQ2)

### ENV2 (Y > X 區域)
- 當 SEQ2 > SEQ1 時輸出差值，否則輸出 0
- 範圍：0-10V
- 意義：掃描點在畫面左下區域時有值
- 公式：ENV2 = max(0, SEQ2 - SEQ1)

### ENV3 (對角線檢測)
- 當 X 和 Y 座標接近時輸出高值
- 範圍：0-10V（10V = 完全在對角線上）
- 意義：偵測掃描點是否在左上到右下的對角線上
- 公式：ENV3 = 10V × (1 - |SEQ1 - SEQ2|)

## 核心參數

### 掃描時間
- 預設：2.0 秒
- 範圍：0.1-60 秒
- 意義：掃過完整輪廓線所需的時間
- 類比原版的 BPM，但控制的是連續掃描速度

### 錨點位置
- X: 0-100%
- Y: 0-100%
- 功能：掃描範圍的中心點

### 掃描範圍
- 範圍：0-50%
- 功能：從錨點向四周延伸的範圍

## 測試程式

```bash
cd /Users/madzine/Documents/VAV_variant
venv/bin/python3 test_scanner.py
```

### 按鍵控制
- `q`: 退出
- `s`: 增加掃描時間（+0.5s）
- `f`: 減少掃描時間（-0.5s）

## 視覺化

### 畫面顯示
- **白色輪廓線**：偵測到的邊界
- **紅色大圓圈**：當前掃描位置
- **粉白圓圈**：錨點位置
- **綠色進度條**：掃描進度（底部）
- **數據面板**：CV 即時數值（左上角）

### 終端輸出
```
SEQ1: 4.19V  SEQ2: 2.12V  ENV1: 3.45V  ENV2: 0.00V  ENV3: 1.58V  Points: 2262
```

## 技術實作

### 新增模組
- `vav/cv_generator/contour_scanner.py`：輪廓掃描器

### 核心方法
1. `detect_and_extract_contour()`: 偵測並提取輪廓
2. `update_scan()`: 更新掃描位置和 CV 值
3. `_calculate_curvature()`: 計算輪廓曲率

### 輪廓提取
- 使用 Canny 邊緣檢測
- 選擇錨點範圍內最長的輪廓
- 保留所有點（CHAIN_APPROX_NONE）
- 支援數千個點的平滑掃描

### 曲率計算
- 使用前後各 2 個點
- 計算向量夾角
- 正規化到 0-1 範圍

## 與原版的差異

| 特性 | 原版 VAV | 變化版 VAV_variant |
|------|----------|-------------------|
| 採樣方式 | Sample & Hold | 連續掃描 |
| 時間控制 | BPM (步進) | Scan Time (連續) |
| 輸出特性 | 階梯波 | 平滑連續 |
| 輪廓點數 | 8-32 點 | 數千點 |
| ENV 觸發 | 電壓比較觸發 | 連續輸出 |
| 視覺化 | 階梯線 | 平滑線 |

## 保留的概念

- 錨點位置
- 掃描範圍
- 輪廓偵測方式（Canny + Sobel）
- 時間平滑
- CV 顏色編碼

## 下一步

要整合到完整的 VAV 系統：

1. 修改 `controller.py` 使用 `ContourScanner`
2. 更新 GUI 控制：BPM → Scan Time
3. 移除 envelope trigger 邏輯（改為連續輸出）
4. 調整音訊處理鏈以接受連續 CV

## 檔案位置

```
/Users/madzine/Documents/VAV_variant/
├── vav/cv_generator/contour_scanner.py   # 新的掃描器
├── test_scanner.py                        # 測試程式
└── README_VARIANT.md                      # 本文件
```

## 注意事項

- 此版本僅實作輪廓掃描器
- 尚未整合到完整 VAV 系統
- 需要修改 controller 和 GUI 才能完整運作
- 保留原版 VAV 於 `/Users/madzine/Documents/VAV`

## 建立日期

2025-11-08

## 狀態

測試中 - 輪廓掃描器已驗證可運作
