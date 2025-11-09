# VAV Hue Rotation 色彩方案實作 - 2025-11-05

## 功能概述

實作方案1 (Hue Rotation)：三層 Multiverse 色彩維持 120° 互補關係，同時保留 ENV 調變功能。

### 設計目標

解決原始問題：
- **問題**：三層顏色都被 ENV 獨立控制，失去互補色關聯
- **解法**：ENV 控制色彩參數（色相旋轉、飽和度），而非直接控制顏色

## 方案1: Hue Rotation (色相旋轉)

### 核心概念

- **三層互補色**：Ch0/1/2 維持固定 120° 間距（三角互補色）
- **ENV1 旋轉色盤**：控制整體色相旋轉 (0-360°)
- **ENV2/3 調變飽和度**：控制 Ch1/Ch2 的飽和度 (50%-100%)

### 色彩映射表

| Channel | 色相 (Hue) | 飽和度 (Saturation) | 亮度 (Value) | 功能說明 |
|---------|-----------|-------------------|-------------|---------|
| **Ch0** | `base_hue + ENV1` | 100% | 100% | 基礎色層，ENV1 控制旋轉 |
| **Ch1** | `base_hue + ENV1 + 120°` | `50% + 50% × ENV2` | 100% | 互補色層1，ENV2 控制飽和度 |
| **Ch2** | `base_hue + ENV1 + 240°` | `50% + 50% × ENV3` | 100% | 互補色層2，ENV3 控制飽和度 |
| **Ch3** | `base_hue + ENV1` | 80% | 90% | 備用通道 |

### 視覺效果

1. **互補色維持**：
   - 三層永遠維持 120° 間距
   - 形成三角互補色 (Triadic Harmony)
   - 色彩協調性強

2. **ENV1 色相旋轉**：
   - 三層同步旋轉色盤
   - 可製造平滑的彩虹循環效果
   - 範圍：0-360°（完整色環）

3. **ENV2/3 飽和度調變**：
   - 飽和度低 (50%) → 偏白色/灰色（柔和）
   - 飽和度高 (100%) → 純色（鮮豔）
   - 可創造色彩濃淡變化

## 實作細節

### 修改檔案

**檔案**: `vav/visual/qt_opengl_renderer.py`

**位置**: 第 74-106 行 (`getChannelColor` 函數)

### Shader 程式碼

```glsl
vec3 getChannelColor(int ch) {
    // 方案1 (Hue Rotation): 三層維持 120° 互補色，ENV1 控制 base hue 旋轉
    float hue = base_hue;
    float saturation = 1.0;
    float value = 1.0;

    // ENV1 控制整體色相旋轉 (0-360°)
    float hue_rotation = envelope_offsets.x;

    if (ch == 0) {
        // Channel 1: Layer 1 (base hue + ENV1 rotation)
        hue = fract(base_hue + hue_rotation);
        saturation = 1.0;
        value = 1.0;
    } else if (ch == 1) {
        // Channel 2: Layer 2 (+120° offset, ENV2 控制飽和度)
        hue = fract(base_hue + hue_rotation + 0.333);  // +120° = +1/3
        saturation = 0.5 + 0.5 * envelope_offsets.y;   // ENV2 控制飽和度 (0.5-1.0)
        value = 1.0;
    } else if (ch == 2) {
        // Channel 3: Layer 3 (+240° offset, ENV3 控制飽和度)
        hue = fract(base_hue + hue_rotation + 0.667);  // +240° = +2/3
        saturation = 0.5 + 0.5 * envelope_offsets.z;   // ENV3 控制飽和度 (0.5-1.0)
        value = 1.0;
    } else {
        // Channel 4: 額外通道（如有需要）
        hue = fract(base_hue + hue_rotation);
        saturation = 0.8;
        value = 0.9;
    }

    return hsv2rgb(vec3(hue, saturation, value));
}
```

### 技術要點

1. **HSV 色彩空間**：
   - Hue (色相): 0.0-1.0 對應 0-360°
   - Saturation (飽和度): 0.0-1.0
   - Value (亮度): 0.0-1.0

2. **120° 間距計算**：
   - 0° → 基礎色
   - +120° → `+0.333` (1/3)
   - +240° → `+0.667` (2/3)

3. **fract() 函數**：
   - 確保色相值循環在 0.0-1.0 範圍內
   - 例：`fract(1.2)` = 0.2

4. **飽和度範圍**：
   - 最低：50%（避免完全灰階）
   - 最高：100%（純色）
   - 映射：`0.5 + 0.5 × ENV_value`

## 使用方式

### ENV 控制對應

- **ENV1 觸發**：SEQ1 > 5V 時
  - 功能：旋轉整體色盤
  - 效果：三層同步改變色相

- **ENV2 觸發**：SEQ2 > 5V 時
  - 功能：調變 Ch1 飽和度
  - 效果：Ch1 在柔和↔鮮豔之間變化

- **ENV3 觸發**：SEQ1 ≤ 5V 且 SEQ2 ≤ 5V 時
  - 功能：調變 Ch2 飽和度
  - 效果：Ch2 在柔和↔鮮豔之間變化

### 建議參數設定

1. **彩虹循環效果**：
   - 提高 ENV1 attack/release 時間
   - 觀察三層同步旋轉色環

2. **色彩濃淡變化**：
   - 調整 ENV2/3 的 attack/decay 時間
   - 觀察飽和度淡入淡出

3. **靜態互補色**：
   - 將 ENV1 固定在某個值
   - 只調變 ENV2/3 的飽和度

## 對比分析

### 原始方案 vs. 方案1

| 特性 | 原始方案 | 方案1 (Hue Rotation) |
|------|---------|---------------------|
| **色彩關係** | 獨立、無關聯 | 120° 互補色 |
| **ENV1 功能** | 直接控制 Ch1 色相 | 旋轉整體色盤 |
| **ENV2 功能** | 直接控制 Ch2 色相 | 調變 Ch1 飽和度 |
| **ENV3 功能** | 直接控制 Ch3 色相 | 調變 Ch2 飽和度 |
| **視覺效果** | 色彩跳躍、不協調 | 色彩和諧、流暢 |
| **調變自由度** | 完全自由 | 參數化調變 |

### 優勢

1. **色彩和諧**：永遠維持互補關係
2. **平滑過渡**：ENV 調變產生漸進效果
3. **藝術性**：三角互補色有強烈視覺衝擊
4. **可預測性**：色彩變化有規律

### 限制

1. **色相不獨立**：三層永遠保持 120° 間距
2. **飽和度範圍**：Ch1/Ch2 最低只到 50%
3. **亮度固定**：目前所有 channel 都是 100% 亮度

## 後續優化建議

### 可選方案

1. **可調間距**：
   - 允許使用者設定互補色間距（不限 120°）
   - 例：90° (四角互補)、144° (五角互補)

2. **亮度調變**：
   - 讓 ENV 也能控制亮度
   - 創造明暗變化

3. **飽和度下限調整**：
   - 允許飽和度降至 0%（完全灰階）
   - 或提高下限至 70%（更鮮豔）

4. **方案切換**：
   - 在 GUI 加入色彩方案選擇器
   - 支援多種預設方案：
     - 方案1：Hue Rotation
     - 方案2：Saturation Modulation
     - 方案3：Dual-axis Mapping
     - 等等...

5. **即時預覽**：
   - GUI 顯示當前三層顏色的色環位置
   - 視覺化互補關係

## 測試確認

### 功能驗證

- ✅ 程式正常啟動
- ✅ Shader 編譯成功
- ✅ 三層互補色顯示正確
- ✅ ENV1 旋轉效果正常
- ✅ ENV2/3 飽和度調變正常
- ✅ 色彩過渡平滑

### 視覺測試

1. 啟動程式
2. 觀察主視窗 Multiverse 輸出
3. 確認三層顏色維持互補關係
4. 調整 ENV1-3 推桿觀察變化
5. 確認色彩變化平滑協調

## 相關檔案

### 修改檔案

- `vav/visual/qt_opengl_renderer.py` (第 74-106 行)

### 相關文件

- `VAV_20251105_Sequential_Switch實作.md` - Sequential Switch 功能
- `GPU_MULTIVERSE_BUGFIX_20251104.md` - Multiverse 渲染器修復
- `VAV_20251104_GPU_MILESTONE.md` - GPU 渲染里程碑

## 技術棧

- **Renderer**: OpenGL Shader (GLSL 410)
- **Color Space**: HSV → RGB 轉換
- **Modulation**: ENV1-3 (0.0-1.0 範圍)
- **Framework**: PyQt6 + OpenGL

---

**實作日期**: 2025-11-05
**版本**: v1.0
**狀態**: ✅ 完成並驗證
**標籤**: `1105_multi_mod`
