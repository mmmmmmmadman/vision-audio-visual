#!/usr/bin/env python3
"""
視覺化測試 GPU Region Mode

顯示 brightness mode 和 quadrant mode 的視覺效果
"""

import sys
import numpy as np
import cv2
from PyQt6.QtWidgets import QApplication

# Add project path
sys.path.insert(0, '/Users/madzine/Documents/VAV')

from vav.visual.qt_opengl_renderer import QtMultiverseRenderer


def generate_gradient_audio(width=1920):
    """生成漸變波形（從左到右振幅遞增）"""
    gradient = np.linspace(0, 10, width, dtype=np.float32)
    return gradient


def test_visual_output():
    """測試視覺輸出並保存圖片"""
    print("=" * 60)
    print("GPU Region Mode 視覺化測試")
    print("=" * 60)

    # 創建 Qt Application
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    # 創建 renderer
    width, height = 1920, 1080
    renderer = QtMultiverseRenderer(width=width, height=height, display_mode=False)

    # 設定基本參數
    renderer.set_blend_mode(0)  # Add mode
    renderer.set_brightness(2.5)

    # 準備測試音訊 - 每個通道不同的頻率和強度
    channels_data = []
    test_frequencies = [220.0, 440.0, 880.0, 1760.0]

    for ch in range(4):
        # 使用正弦波，每個通道不同頻率
        t = np.linspace(0, 1, width, dtype=np.float32)
        freq = test_frequencies[ch]
        audio = 5.0 * np.sin(2 * np.pi * freq * t)

        channels_data.append({
            'enabled': True,
            'audio': audio,
            'frequency': freq,
            'intensity': 1.0,
            'curve': 0.1,  # 添加一點曲線效果
            'angle': ch * 30.0,  # 每個通道不同旋轉角度
        })

    # 測試配置
    test_configs = [
        ("no_region", 0, False, "無 Region 分割"),
        ("brightness", 1, True, "Brightness Mode (GPU)"),
        ("quadrant", 2, True, "Quadrant Mode (GPU)"),
    ]

    for config_id, region_mode, use_region, description in test_configs:
        print(f"\n生成圖片: {description}")

        # 設定 region mode
        renderer.set_region_mode(region_mode)
        renderer.use_region_map = 1 if use_region else 0

        # 渲染
        frame_rgb = renderer.render(channels_data, region_map=None)

        # 轉換為 BGR 供 OpenCV 使用
        frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)

        # 保存圖片
        output_path = f"/Users/madzine/Documents/VAV/test_output_{config_id}.png"
        cv2.imwrite(output_path, frame_bgr)
        print(f"  已保存: {output_path}")

        # 計算統計資訊
        avg_brightness = np.mean(frame_rgb)
        print(f"  平均亮度: {avg_brightness:.2f}")
        print(f"  最小/最大值: {np.min(frame_rgb)}/{np.max(frame_rgb)}")

    # 清理
    renderer.cleanup()
    app.quit()

    print("\n" + "=" * 60)
    print("視覺化測試完成！")
    print("請檢查生成的圖片:")
    print("  - test_output_no_region.png (baseline)")
    print("  - test_output_brightness.png (brightness regions)")
    print("  - test_output_quadrant.png (quadrant regions)")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_visual_output()
    except Exception as e:
        print(f"\n錯誤: {e}")
        import traceback
        traceback.print_exc()
