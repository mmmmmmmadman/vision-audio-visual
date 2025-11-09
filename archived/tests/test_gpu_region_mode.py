#!/usr/bin/env python3
"""
測試 GPU Region Mode 效能與視覺效果

比較 CPU region mode vs GPU region mode 的效能差異
"""

import sys
import numpy as np
import time
from PyQt6.QtWidgets import QApplication

# Add project path
sys.path.insert(0, '/Users/madzine/Documents/VAV')

from vav.visual.qt_opengl_renderer import QtMultiverseRenderer


def generate_test_audio(width=1920, frequency=440.0):
    """生成測試音訊波形"""
    t = np.linspace(0, 1, width, dtype=np.float32)
    # 生成正弦波，振幅 ±5V
    audio = 5.0 * np.sin(2 * np.pi * frequency * t)
    return audio


def test_region_modes():
    """測試不同 region modes 的效能"""
    print("=" * 60)
    print("GPU Region Mode 效能測試")
    print("=" * 60)

    # 創建 Qt Application（OpenGL 需要）
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    # 創建 renderer
    width, height = 1920, 1080
    renderer = QtMultiverseRenderer(width=width, height=height, display_mode=False)

    # 設定基本參數
    renderer.set_blend_mode(0)  # Add mode
    renderer.set_brightness(2.5)

    # 準備測試音訊
    channels_data = []
    for ch in range(4):
        audio = generate_test_audio(width, frequency=440.0 * (ch + 1))
        channels_data.append({
            'enabled': True,
            'audio': audio,
            'frequency': 440.0 * (ch + 1),
            'intensity': 1.0,
            'curve': 0.0,
            'angle': ch * 45.0,
        })

    # 測試設定
    test_configs = [
        ("Disabled (no region)", 0, False),
        ("GPU Brightness Mode", 1, True),
        ("GPU Quadrant Mode", 2, True),
    ]

    results = {}

    for config_name, region_mode, use_region in test_configs:
        print(f"\n測試配置: {config_name}")
        print("-" * 60)

        # 設定 region mode
        renderer.set_region_mode(region_mode)
        renderer.use_region_map = 1 if use_region else 0

        # 預熱（避免首次渲染的初始化開銷）
        for _ in range(5):
            renderer.render(channels_data, region_map=None)

        # 效能測試（100 frames）
        num_frames = 100
        start_time = time.time()

        for _ in range(num_frames):
            frame = renderer.render(channels_data, region_map=None)

        elapsed = time.time() - start_time
        fps = num_frames / elapsed
        avg_frame_time = (elapsed / num_frames) * 1000  # ms

        results[config_name] = {
            'fps': fps,
            'avg_frame_time_ms': avg_frame_time,
            'total_time': elapsed,
        }

        print(f"  渲染 {num_frames} frames")
        print(f"  總耗時: {elapsed:.3f} 秒")
        print(f"  平均 FPS: {fps:.1f}")
        print(f"  平均 frame time: {avg_frame_time:.2f} ms")

    # 效能比較
    print("\n" + "=" * 60)
    print("效能比較")
    print("=" * 60)

    baseline_fps = results["Disabled (no region)"]['fps']

    for config_name, data in results.items():
        fps = data['fps']
        speedup = fps / baseline_fps
        print(f"\n{config_name}:")
        print(f"  FPS: {fps:.1f}")
        print(f"  相對 baseline: {speedup:.2f}x")
        print(f"  Frame time: {data['avg_frame_time_ms']:.2f} ms")

    # 計算 GPU vs CPU 的效能提升
    if "GPU Brightness Mode" in results:
        gpu_fps = results["GPU Brightness Mode"]['fps']
        gpu_frame_time = results["GPU Brightness Mode"]['avg_frame_time_ms']

        print("\n" + "=" * 60)
        print("GPU Region Mode 效能提升")
        print("=" * 60)
        print(f"GPU Brightness Mode FPS: {gpu_fps:.1f}")
        print(f"GPU Frame Time: {gpu_frame_time:.2f} ms")
        print(f"\n預期效能提升:")
        print(f"  消除 CPU region 計算開銷 (20-30ms)")
        print(f"  GPU 並行計算 (< 1ms)")
        print(f"  目標: 從 16-21 FPS 提升至接近 24 FPS")

    # 清理
    renderer.cleanup()
    app.quit()

    return results


if __name__ == "__main__":
    try:
        results = test_region_modes()
        print("\n測試完成！")
    except Exception as e:
        print(f"\n錯誤: {e}")
        import traceback
        traceback.print_exc()
