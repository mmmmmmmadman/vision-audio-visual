# GPU Multiverse 渲染器完整重構計劃

## 日期
2025-11-04 22:00

## 問題根源

現有 GPU 渲染器架構與 CPU 版本完全不同：

### 現有 GPU 架構（錯誤）
```
Shader 內部一次處理所有 4 個通道
└─> 在 shader 內部直接混合
    └─> Region map 過濾在 shader 內部
        └─> 輸出最終 RGB
```

### CPU 架構（正確）
```
For each channel:
  └─> 渲染單一通道到 RGBA layer
      └─> 應用旋轉（如果需要）
          └─> 使用 blend 函數混合到 buffer
              └─> 如果有 region_map，只在對應區域混合
```

## 新 GPU 架構設計

### 架構概覽
```
For each channel:
  └─> GPU: 渲染單一通道到 RGBA texture (channel_fbo)
      └─> GPU: 如果 angle != 0，渲染旋轉版本 (rotated_fbo)
          └─> GPU: 使用 blend shader 混合到 accumulation buffer
              └─> 支援 4 種 blend mode
              └─> 支援 region map 過濾
最後:
  └─> GPU: 應用亮度並轉換為 RGB
      └─> Read back 到 CPU
```

## Shader 設計

### 1. 單通道渲染 Shader

**用途**：渲染單一通道的波形到 RGBA texture

**輸入**：
- `audio_tex`: 單一通道的音訊數據 (1D texture, width samples)
- `frequency`: 通道頻率
- `intensity`: 通道強度
- `curve`: 彎曲參數
- `angle`: 旋轉角度（在此 shader 中 = 0，旋轉用另一個 shader）

**輸出**：
- RGBA texture，其中：
  - RGB: 顏色（從頻率計算 HSV -> RGB）
  - A: Alpha（= 正規化後的電壓值）

### 2. 旋轉 Shader

**用途**：將 RGBA texture 旋轉指定角度

**輸入**：
- `source_tex`: 要旋轉的 RGBA texture
- `angle`: 旋轉角度（度）

**輸出**：
- 旋轉後的 RGBA texture

### 3. Blend Shader

**用途**：將一個 layer 混合到 accumulation buffer

**輸入**：
- `buffer_tex`: 當前累積的 buffer (RGBA)
- `layer_tex`: 要混合的 layer (RGBA)
- `region_tex`: Region map (R8, optional)
- `channel_id`: 當前通道 ID (0-3)
- `blend_mode`: 混合模式 (0-3)
- `use_region_map`: 是否使用 region map

**輸出**：
- 混合後的 RGBA buffer

**Blend Modes**:
- 0: Add - `min(1.0, buffer + layer)`
- 1: Screen - `1.0 - (1.0 - buffer) * (1.0 - layer)`
- 2: Difference - `abs(buffer - layer)` (RGB only, A = max)
- 3: Color Dodge - `buffer / (1.0 - layer)` (RGB only, A = max)

### 4. 亮度+轉換 Shader

**用途**：應用亮度並轉換 RGBA float 到 RGB uint8

**輸入**：
- `buffer_tex`: RGBA float buffer
- `brightness`: 亮度係數

**輸出**：
- RGB uint8 texture

## OpenGL 資源配置

### Framebuffers (FBOs)
1. `channel_fbo`: 渲染單一通道 (RGBA32F texture)
2. `rotated_fbo`: 旋轉後的通道 (RGBA32F texture, 如需要)
3. `accumulation_fbo`: 累積 buffer (RGBA32F texture)
4. `final_fbo`: 最終輸出 (RGB8 texture)

### Textures
1. `audio_tex`: 音訊數據 (R32F, width x 1)
2. `region_tex`: Region map (R8, width x height)
3. `channel_tex`: 通道渲染結果 (RGBA32F)
4. `rotated_tex`: 旋轉結果 (RGBA32F)
5. `accumulation_tex`: 累積 buffer (RGBA32F)
6. `final_tex`: 最終 RGB (RGB8)

### Shader Programs
1. `channel_program`: 單通道渲染
2. `rotate_program`: 旋轉變換
3. `blend_program`: Layer 混合
4. `brightness_program`: 亮度+RGB 轉換

## 渲染流程

```python
def render(channels_data, region_map):
    # 1. 清空累積 buffer
    clear_accumulation_buffer()

    # 2. 處理每個通道
    for ch_idx, ch_data in enumerate(channels_data):
        if not ch_data['enabled']:
            continue

        # 2a. 渲染單一通道到 channel_fbo
        render_single_channel(
            audio=ch_data['audio'],
            frequency=ch_data['frequency'],
            intensity=ch_data['intensity'],
            curve=ch_data['curve']
        )

        # 2b. 如果需要旋轉，渲染到 rotated_fbo
        if abs(ch_data['angle']) > 0.1:
            rotate_texture(
                source=channel_tex,
                angle=ch_data['angle'],
                output=rotated_fbo
            )
            source_tex = rotated_tex
        else:
            source_tex = channel_tex

        # 2c. 混合到累積 buffer
        blend_layer(
            buffer=accumulation_tex,
            layer=source_tex,
            region_map=region_tex if region_map else None,
            channel_id=ch_idx,
            blend_mode=self.blend_mode
        )

    # 3. 應用亮度並轉換為 RGB
    apply_brightness_and_convert(
        source=accumulation_tex,
        brightness=self.brightness,
        output=final_fbo
    )

    # 4. Read back RGB data
    rgb = read_pixels(final_fbo)
    return rgb
```

## Region Map 運作方式

在 blend shader 中：

```glsl
// Blend shader fragment code
void main() {
    vec4 buffer_color = texture(buffer_tex, v_texcoord);
    vec4 layer_color = texture(layer_tex, v_texcoord);

    // 檢查 region map
    if (use_region_map > 0) {
        float region_val = texture(region_tex, v_texcoord).r;
        int region_id = int(region_val * 255.0);

        // 如果不是此通道的區域，直接返回 buffer 不變
        if (region_id != channel_id) {
            fragColor = buffer_color;
            return;
        }
    }

    // 執行混合
    if (blend_mode == 0) {
        // Add
        fragColor = min(vec4(1.0), buffer_color + layer_color);
    } else if (blend_mode == 1) {
        // Screen
        fragColor = vec4(1.0) - (vec4(1.0) - buffer_color) * (vec4(1.0) - layer_color);
    }
    // ... 其他 blend modes
}
```

## 與 CPU 版本的對應關係

| CPU 版本 (Numba) | GPU 版本 (OpenGL) |
|------------------|-------------------|
| `render_channel_numba()` | Channel Shader |
| `rotate_image()` | Rotate Shader |
| `blend_add()` | Blend Shader (mode=0) |
| `blend_screen()` | Blend Shader (mode=1) |
| `blend_difference()` | Blend Shader (mode=2) |
| `blend_color_dodge()` | Blend Shader (mode=3) |
| `blend_xxx_region()` | Blend Shader + region map |
| `apply_brightness_and_convert()` | Brightness Shader |

## 優勢

1. **100% 匹配 CPU 行為**：逐層渲染+混合
2. **Region map 正確運作**：在混合階段檢查區域
3. **Blend mode 正確**：每個 mode 獨立實作
4. **可維護性高**：架構清晰，與 CPU 版本對應
5. **GPU 加速**：所有計算都在 GPU 上完成

## 效能考量

每幀需要的 GPU operations:
- 4x 單通道渲染 (如果 4 個通道都啟用)
- 0-4x 旋轉 (取決於 angle 設定)
- 4x Blend (逐層混合)
- 1x 亮度轉換
- 1x Read back

總計: ~10-13 個 render passes per frame

這對現代 GPU 來說非常輕鬆，Metal backend 效能優異。

## 實作步驟

1. ✓ 備份現有檔案
2. ⏳ 實作 Channel Shader
3. ⏳ 實作 Rotate Shader
4. ⏳ 實作 Blend Shader
5. ⏳ 實作 Brightness Shader
6. ⏳ 重寫 QtMultiverseRenderer class
7. ⏳ 測試各個功能
8. ⏳ 與 CPU 版本比較驗證

## 備註

- 保持向後兼容的 API
- `render()` 函數簽名不變
- 所有參數含義與 CPU 版本一致
- 支援 thread-safe 調用

---

**狀態**: 設計完成，開始實作
**預計完成時間**: 2025-11-04 23:00
