#!/usr/bin/env python3
"""
Benchmark CPU vs GPU Multiverse Renderers WITH Stable Diffusion
測試開啟 SD img2img 時，CPU (11042100) vs GPU (11042318) 的性能差異
"""

import time
import numpy as np
import sys
from PyQt6.QtWidgets import QApplication

# Import renderers
try:
    from vav.visual.numba_renderer import NumbaMultiverseRenderer
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    print("⚠ Numba renderer not available")

try:
    from vav.visual.qt_opengl_renderer import QtMultiverseRenderer
    GPU_AVAILABLE = True
except ImportError:
    GPU_AVAILABLE = False
    print("⚠ GPU renderer not available")

# Import SD
try:
    from vav.visual.sd_img2img_process import SDImg2ImgProcess
    SD_AVAILABLE = True
except ImportError:
    SD_AVAILABLE = False
    print("⚠ SD img2img not available")


def generate_test_audio(num_samples=2400, num_channels=4):
    """生成測試音訊數據"""
    audio_data = []
    for ch in range(num_channels):
        freq = 100.0 * (ch + 1)  # 100Hz, 200Hz, 300Hz, 400Hz
        t = np.linspace(0, num_samples / 48000.0, num_samples)
        signal = 10.0 * np.sin(2 * np.pi * freq * t)
        audio_data.append(signal.astype(np.float32))
    return audio_data


def prepare_channels_data(audio_data, intensity=1.0, angles=[0, 45, 90, 135]):
    """準備通道數據"""
    channels_data = []
    for ch, audio in enumerate(audio_data):
        channels_data.append({
            'audio': audio,
            'frequency': 100.0 * (ch + 1),
            'intensity': intensity,
            'curve': 0.0,
            'angle': angles[ch],
            'enabled': True
        })
    return channels_data


def benchmark_with_sd(renderer, name, channels_data, sd_processor=None,
                     num_frames=100, warmup=10):
    """
    執行渲染器性能測試（帶 SD）

    Args:
        renderer: 渲染器實例
        name: 渲染器名稱
        channels_data: 通道數據
        sd_processor: SD img2img 處理器（可選）
        num_frames: 測試幀數
        warmup: 預熱幀數
    """
    print(f"\n{'='*70}")
    print(f"Testing {name}")
    if sd_processor:
        print(f"WITH Stable Diffusion img2img enabled")
    else:
        print(f"WITHOUT Stable Diffusion")
    print(f"{'='*70}")

    # Warmup
    print(f"Warmup: {warmup} frames...")
    for i in range(warmup):
        rgb = renderer.render(channels_data)
        if sd_processor:
            sd_processor.feed_frame(rgb)

    # 如果有 SD，等待至少一次生成完成
    if sd_processor:
        print("等待 SD 首次生成...")
        wait_start = time.time()
        timeout = 30.0
        while time.time() - wait_start < timeout:
            if sd_processor.get_current_output() is not None:
                print(f"✓ SD 首次生成完成 ({time.time() - wait_start:.1f}s)")
                break
            time.sleep(0.1)
        else:
            print("⚠ SD 首次生成超時")

    # Benchmark
    print(f"Benchmarking: {num_frames} frames...")
    render_times = []
    sd_feed_times = []
    sd_get_times = []
    total_times = []

    for i in range(num_frames):
        frame_start = time.perf_counter()

        # 渲染
        render_start = time.perf_counter()
        rgb = renderer.render(channels_data)
        render_end = time.perf_counter()
        render_time = (render_end - render_start) * 1000
        render_times.append(render_time)

        # SD 處理
        if sd_processor:
            # Feed frame to SD
            sd_feed_start = time.perf_counter()
            sd_processor.feed_frame(rgb)
            sd_feed_end = time.perf_counter()
            sd_feed_time = (sd_feed_end - sd_feed_start) * 1000
            sd_feed_times.append(sd_feed_time)

            # Get SD output
            sd_get_start = time.perf_counter()
            sd_output = sd_processor.get_current_output()
            sd_get_end = time.perf_counter()
            sd_get_time = (sd_get_end - sd_get_start) * 1000
            sd_get_times.append(sd_get_time)

        frame_end = time.perf_counter()
        total_time = (frame_end - frame_start) * 1000
        total_times.append(total_time)

        if (i + 1) % 20 == 0:
            avg_render = np.mean(render_times)
            avg_total = np.mean(total_times)
            print(f"  Frame {i+1}/{num_frames}: render={avg_render:.3f}ms, total={avg_total:.3f}ms")

    # Statistics
    render_times = np.array(render_times)
    total_times = np.array(total_times)

    print(f"\n{name} Results:")
    print(f"  Frames rendered: {num_frames}")
    print(f"\n  === Rendering Performance ===")
    print(f"  Average render time: {np.mean(render_times):.3f} ms/frame")
    print(f"  Median render time: {np.median(render_times):.3f} ms/frame")
    print(f"  Min render time: {np.min(render_times):.3f} ms/frame")
    print(f"  Max render time: {np.max(render_times):.3f} ms/frame")
    print(f"  Std deviation: {np.std(render_times):.3f} ms")
    print(f"  Average render FPS: {1000.0 / np.mean(render_times):.1f} fps")

    if sd_processor:
        sd_feed_times = np.array(sd_feed_times)
        sd_get_times = np.array(sd_get_times)

        print(f"\n  === SD Processing Performance ===")
        print(f"  Average SD feed time: {np.mean(sd_feed_times):.3f} ms")
        print(f"  Average SD get time: {np.mean(sd_get_times):.3f} ms")
        print(f"  SD overhead: {np.mean(sd_feed_times) + np.mean(sd_get_times):.3f} ms")

        print(f"\n  === Total Performance (Render + SD) ===")
        print(f"  Average total time: {np.mean(total_times):.3f} ms/frame")
        print(f"  Average total FPS: {1000.0 / np.mean(total_times):.1f} fps")
        print(f"  Total overhead: {np.mean(total_times) - np.mean(render_times):.3f} ms")

    return {
        'render_times': render_times,
        'total_times': total_times,
        'sd_feed_times': np.array(sd_feed_times) if len(sd_feed_times) > 0 else None,
        'sd_get_times': np.array(sd_get_times) if len(sd_get_times) > 0 else None
    }


def main():
    print("="*70)
    print("VAV Multiverse Renderer Performance Benchmark WITH SD")
    print("CPU (Numba v11042100) vs GPU (Qt OpenGL v11042318)")
    print("="*70)

    # Check availability
    if not NUMBA_AVAILABLE and not GPU_AVAILABLE:
        print("❌ No renderers available!")
        return

    if not SD_AVAILABLE:
        print("❌ SD img2img not available!")
        return

    # Initialize Qt Application
    app = QApplication(sys.argv)

    # Generate test data
    print("\nGenerating test audio data...")
    audio_data = generate_test_audio(num_samples=2400, num_channels=4)
    channels_data = prepare_channels_data(audio_data)
    print(f"✓ Generated {len(audio_data)} channels, {len(audio_data[0])} samples each")

    results = {}

    # Test 1: CPU WITHOUT SD (baseline)
    if NUMBA_AVAILABLE:
        print("\n" + "="*70)
        print("Test 1: CPU (Numba) WITHOUT SD")
        print("="*70)
        cpu_renderer = NumbaMultiverseRenderer(width=1920, height=1080)
        cpu_renderer.set_blend_mode(0)
        cpu_renderer.set_brightness(1.0)

        results['CPU_no_SD'] = benchmark_with_sd(
            cpu_renderer,
            "CPU (Numba JIT)",
            channels_data,
            sd_processor=None,
            num_frames=100,
            warmup=10
        )

    # Test 2: CPU WITH SD
    if NUMBA_AVAILABLE:
        print("\n" + "="*70)
        print("Test 2: CPU (Numba) WITH SD")
        print("="*70)
        cpu_renderer_sd = NumbaMultiverseRenderer(width=1920, height=1080)
        cpu_renderer_sd.set_blend_mode(0)
        cpu_renderer_sd.set_brightness(1.0)

        print("初始化 SD img2img...")
        sd_cpu = SDImg2ImgProcess(output_width=1920, output_height=1080, fps_target=30)
        sd_cpu.start()
        print("✓ SD 啟動中...")

        results['CPU_with_SD'] = benchmark_with_sd(
            cpu_renderer_sd,
            "CPU (Numba JIT)",
            channels_data,
            sd_processor=sd_cpu,
            num_frames=100,
            warmup=10
        )

        print("停止 SD...")
        sd_cpu.stop()
        time.sleep(2)

    # Test 3: GPU WITHOUT SD (baseline)
    if GPU_AVAILABLE:
        print("\n" + "="*70)
        print("Test 3: GPU (Qt OpenGL Metal) WITHOUT SD")
        print("="*70)
        gpu_renderer = QtMultiverseRenderer(width=1920, height=1080)
        gpu_renderer.set_blend_mode(0)
        gpu_renderer.set_brightness(1.0)

        results['GPU_no_SD'] = benchmark_with_sd(
            gpu_renderer,
            "GPU (Qt OpenGL Metal)",
            channels_data,
            sd_processor=None,
            num_frames=100,
            warmup=10
        )

    # Test 4: GPU WITH SD
    if GPU_AVAILABLE:
        print("\n" + "="*70)
        print("Test 4: GPU (Qt OpenGL Metal) WITH SD")
        print("="*70)
        gpu_renderer_sd = QtMultiverseRenderer(width=1920, height=1080)
        gpu_renderer_sd.set_blend_mode(0)
        gpu_renderer_sd.set_brightness(1.0)

        print("初始化 SD img2img...")
        sd_gpu = SDImg2ImgProcess(output_width=1920, output_height=1080, fps_target=30)
        sd_gpu.start()
        print("✓ SD 啟動中...")

        results['GPU_with_SD'] = benchmark_with_sd(
            gpu_renderer_sd,
            "GPU (Qt OpenGL Metal)",
            channels_data,
            sd_processor=sd_gpu,
            num_frames=100,
            warmup=10
        )

        print("停止 SD...")
        sd_gpu.stop()
        time.sleep(2)

    # Final Comparison
    print("\n" + "="*70)
    print("FINAL PERFORMANCE COMPARISON")
    print("="*70)

    if 'CPU_no_SD' in results and 'CPU_with_SD' in results:
        cpu_no_sd_render = np.mean(results['CPU_no_SD']['render_times'])
        cpu_with_sd_render = np.mean(results['CPU_with_SD']['render_times'])
        cpu_with_sd_total = np.mean(results['CPU_with_SD']['total_times'])

        print(f"\n=== CPU (Numba JIT) ===")
        print(f"  Without SD: {cpu_no_sd_render:.3f} ms/frame ({1000.0/cpu_no_sd_render:.1f} fps)")
        print(f"  With SD (render only): {cpu_with_sd_render:.3f} ms/frame ({1000.0/cpu_with_sd_render:.1f} fps)")
        print(f"  With SD (total): {cpu_with_sd_total:.3f} ms/frame ({1000.0/cpu_with_sd_total:.1f} fps)")
        print(f"  SD impact on render: {cpu_with_sd_render - cpu_no_sd_render:.3f} ms ({((cpu_with_sd_render/cpu_no_sd_render - 1) * 100):.1f}%)")
        print(f"  SD total overhead: {cpu_with_sd_total - cpu_no_sd_render:.3f} ms")

    if 'GPU_no_SD' in results and 'GPU_with_SD' in results:
        gpu_no_sd_render = np.mean(results['GPU_no_SD']['render_times'])
        gpu_with_sd_render = np.mean(results['GPU_with_SD']['render_times'])
        gpu_with_sd_total = np.mean(results['GPU_with_SD']['total_times'])

        print(f"\n=== GPU (Qt OpenGL Metal) ===")
        print(f"  Without SD: {gpu_no_sd_render:.3f} ms/frame ({1000.0/gpu_no_sd_render:.1f} fps)")
        print(f"  With SD (render only): {gpu_with_sd_render:.3f} ms/frame ({1000.0/gpu_with_sd_render:.1f} fps)")
        print(f"  With SD (total): {gpu_with_sd_total:.3f} ms/frame ({1000.0/gpu_with_sd_total:.1f} fps)")
        print(f"  SD impact on render: {gpu_with_sd_render - gpu_no_sd_render:.3f} ms ({((gpu_with_sd_render/gpu_no_sd_render - 1) * 100):.1f}%)")
        print(f"  SD total overhead: {gpu_with_sd_total - gpu_no_sd_render:.3f} ms")

    if 'CPU_with_SD' in results and 'GPU_with_SD' in results:
        cpu_sd_render = np.mean(results['CPU_with_SD']['render_times'])
        gpu_sd_render = np.mean(results['GPU_with_SD']['render_times'])
        speedup = cpu_sd_render / gpu_sd_render

        print(f"\n=== GPU vs CPU (WITH SD) ===")
        print(f"  GPU render speedup: {speedup:.2f}x")
        print(f"  GPU advantage: {cpu_sd_render - gpu_sd_render:.3f} ms faster per frame")

    print("\n" + "="*70)
    print("Benchmark Complete!")
    print("="*70)


if __name__ == "__main__":
    main()
