# Region Map Debug 指南

## 問題現象
在 Multiverse 模式下，開啟或關閉 Region Map checkbox，畫面沒有明顯變化。

## 診斷結果

### ✅ 確認正常的部分
1. GUI 正確初始化並啟用 region rendering
2. Controller 正確傳遞 `use_gpu_region=True` 給 renderer
3. Renderer 正確設置 `use_region_map=1` 和 `use_gpu_region=1`
4. Camera frame 正確上傳到 GPU texture
5. Shader uniforms 正確傳遞到 GPU

### ⚠️ 可能的問題原因

#### 1. 所有 channels 同時啟用導致 blend 後無法區分
當 4 個 channels 全部啟用時，經過 blend mode 混合後，region 效果會被稀釋：
- 暗區：顯示 CH1
- 亮區：顯示 CH4
- 中間：顯示 CH2/CH3
- **問題**: Blend 後顏色混合，視覺上無法區分

#### 2. Camera texture 亮度分布不均
如果 camera 畫面亮度集中在某個範圍（例如都在 0.5-0.75），所有像素都被分配到同一個 region。

#### 3. Blend mode 影響
不同的 blend mode (Add/Screen/Difference/Divide) 會影響 region 效果的可見度。

## Debug 方法

### 方法 1: 視覺化 Region Map (推薦)

編輯 `/Users/madzine/Documents/VAV/vav/visual/qt_opengl_renderer.py` line 179-184，取消註解以下代碼：

```glsl
// DEBUG: Visualize region map by coloring pixels (uncomment to test)
if (brightness_val < 0.25) fragColor = vec4(1.0, 0.0, 0.0, 1.0);  // Red = CH1
else if (brightness_val < 0.5) fragColor = vec4(0.0, 1.0, 0.0, 1.0);  // Green = CH2
else if (brightness_val < 0.75) fragColor = vec4(0.0, 0.0, 1.0, 1.0);  // Blue = CH3
else fragColor = vec4(1.0, 1.0, 0.0, 1.0);  // Yellow = CH4
return;
```

**預期結果**:
- 畫面應該顯示 4 種顏色區域
- 用手遮蔽鏡頭時，顏色應該從 Yellow (亮) → Blue → Green → Red (暗)
- 如果整個畫面只有單一顏色，代表 camera texture 有問題

### 方法 2: 簡化測試配置

只啟用 2 個 channels，設置極端對比：

```python
# 停用 CH2 和 CH3
controller.toggle_channel(1, False)
controller.toggle_channel(2, False)

# CH1: 0° (垂直), CH4: 90° (水平)
controller.set_channel_angle(0, 0.0)
controller.set_channel_angle(3, 90.0)
```

**預期結果**:
- Region ON: 暗區=垂直波形，亮區=水平波形
- Region OFF: 全畫面=垂直+水平混合

### 方法 3: 檢查 Camera Texture 資料

查看 debug log (每 100 幀):
```
[Qt OpenGL] Region state: use_region_map=1, use_gpu_region=1
[Qt OpenGL] Camera frame: True, Region map: False
```

如果 `Camera frame: True`，代表資料已上傳。

可以添加更詳細的 debug：

```python
# 在 qt_opengl_renderer.py:878 之後添加
if self._debug_frame_count % 100 == 0 and self.camera_frame_data is not None:
    # Sample center pixel brightness
    h, w = self.render_height, self.render_width
    center_pixel = self.camera_frame_data[h//2, w//2]
    brightness = 0.299 * center_pixel[0] + 0.587 * center_pixel[1] + 0.114 * center_pixel[2]
    print(f"[Qt OpenGL] Camera center pixel: RGB={center_pixel}, brightness={brightness/255.0:.3f}")
```

## 快速驗證步驟

1. **啟動應用程式**
   ```bash
   cd /Users/madzine/Documents/VAV
   /Users/madzine/Documents/VAV/venv/bin/python3 main_compact.py
   ```

2. **停用 CH2 和 CH3** (GUI 中取消勾選)

3. **設置極端角度對比**:
   - CH1 Angle: 0°
   - CH4 Angle: 90°

4. **製造明暗對比**:
   - 用手遮蔽鏡頭左半部
   - 或用黑色紙片遮蔽一半

5. **切換 Region Map checkbox**:
   - ON: 應該看到暗區和亮區有不同的波形方向
   - OFF: 全畫面應該是混合波形

6. **如果還是看不到差異** → 使用「方法 1: 視覺化 Region Map」來確認 camera texture 是否正常

## 已添加的 Debug Log

執行時會看到：
```
[Region DEBUG] use_region_rendering=True, region_mapper=True, region_mode=brightness, using_gpu=True
[Qt OpenGL] Region state: use_region_map=1, use_gpu_region=1
[Qt OpenGL] Camera frame: True, Region map: False
```

這些 log 每 100 幀輸出一次。

## 下一步

如果「方法 1」顯示整個畫面是單一顏色，代表：
- Camera texture 可能是黑色或白色
- Texture 綁定有問題
- Camera frame 資料沒有正確傳遞

如果「方法 1」顯示正確的顏色分區，但實際 rendering 時看不到效果，代表：
- Blend mode 稀釋了 region 效果
- 需要調整 channel 配置或 blend mode
