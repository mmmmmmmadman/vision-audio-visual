#!/usr/bin/env python3
"""
Benchmark CPU (Numba) vs GPU (Qt OpenGL) Multiverse Renderers
比較 CPU 版本 (11042100) 與 GPU 版本 (11042318) 的運算速度
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


def generate_test_audio(num_samples=2400, num_channels=4):
    """生成測試音訊數據"""
    audio_data = []
    for ch in range(num_channels):
        # 生成 -10V 到 +10V 範圍的正弦波
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


def benchmark_renderer(renderer, name, channels_data, num_frames=100, warmup=10):
    """執行渲染器性能測試"""
    print(f"\n{'='*60}")
    print(f"Testing {name}")
    print(f"{'='*60}")

    # Warmup
    print(f"Warmup: {warmup} frames...")
    for _ in range(warmup):
        renderer.render(channels_data)

    # Benchmark
    print(f"Benchmarking: {num_frames} frames...")
    times = []

    for i in range(num_frames):
        start = time.perf_counter()
        rgb = renderer.render(channels_data)
        end = time.perf_counter()

        frame_time = (end - start) * 1000  # Convert to ms
        times.append(frame_time)

        if (i + 1) % 10 == 0:
            avg_so_far = np.mean(times)
            print(f"  Frame {i+1}/{num_frames}: {frame_time:.3f}ms (avg: {avg_so_far:.3f}ms)")

    # Statistics
    times = np.array(times)
    print(f"\n{name} Results:")
    print(f"  Frames rendered: {num_frames}")
    print(f"  Average time: {np.mean(times):.3f} ms/frame")
    print(f"  Median time: {np.median(times):.3f} ms/frame")
    print(f"  Min time: {np.min(times):.3f} ms/frame")
    print(f"  Max time: {np.max(times):.3f} ms/frame")
    print(f"  Std deviation: {np.std(times):.3f} ms")
    print(f"  Average FPS: {1000.0 / np.mean(times):.1f} fps")

    return times


def benchmark_with_region_map(renderer, name, channels_data, num_frames=50):
    """測試使用 region map 的性能"""
    print(f"\n{'='*60}")
    print(f"Testing {name} with Region Map")
    print(f"{'='*60}")

    # Create a simple region map (1920x1080, R8)
    width, height = 1920, 1080
    region_map = np.zeros((height, width), dtype=np.uint8)

    # Divide screen into 4 quadrants
    region_map[:height//2, :width//2] = 0  # Top-left: Channel 0
    region_map[:height//2, width//2:] = 1  # Top-right: Channel 1
    region_map[height//2:, :width//2] = 2  # Bottom-left: Channel 2
    region_map[height//2:, width//2:] = 3  # Bottom-right: Channel 3

    # Warmup
    print(f"Warmup: 5 frames...")
    for _ in range(5):
        renderer.render(channels_data, region_map=region_map)

    # Benchmark
    print(f"Benchmarking: {num_frames} frames...")
    times = []

    for i in range(num_frames):
        start = time.perf_counter()
        rgb = renderer.render(channels_data, region_map=region_map)
        end = time.perf_counter()

        frame_time = (end - start) * 1000
        times.append(frame_time)

        if (i + 1) % 10 == 0:
            avg_so_far = np.mean(times)
            print(f"  Frame {i+1}/{num_frames}: {frame_time:.3f}ms (avg: {avg_so_far:.3f}ms)")

    # Statistics
    times = np.array(times)
    print(f"\n{name} with Region Map Results:")
    print(f"  Average time: {np.mean(times):.3f} ms/frame")
    print(f"  Average FPS: {1000.0 / np.mean(times):.1f} fps")

    return times


def main():
    print("="*60)
    print("VAV Multiverse Renderer Performance Benchmark")
    print("CPU (Numba v11042100) vs GPU (Qt OpenGL v11042318)")
    print("="*60)

    # Check availability
    if not NUMBA_AVAILABLE and not GPU_AVAILABLE:
        print("❌ No renderers available!")
        return

    # Initialize Qt Application (required for GPU renderer)
    app = QApplication(sys.argv)

    # Generate test data
    print("\nGenerating test audio data...")
    audio_data = generate_test_audio(num_samples=2400, num_channels=4)
    channels_data = prepare_channels_data(audio_data)
    print(f"✓ Generated {len(audio_data)} channels, {len(audio_data[0])} samples each")

    results = {}

    # Test CPU (Numba) Renderer
    if NUMBA_AVAILABLE:
        print("\n" + "="*60)
        print("Initializing CPU (Numba) Renderer...")
        print("="*60)
        cpu_renderer = NumbaMultiverseRenderer(width=1920, height=1080)
        cpu_renderer.set_blend_mode(0)  # Add mode
        cpu_renderer.set_brightness(1.0)
        print("✓ CPU renderer initialized")

        # Test without region map
        cpu_times = benchmark_renderer(
            cpu_renderer,
            "CPU (Numba JIT)",
            channels_data,
            num_frames=100,
            warmup=10
        )
        results['CPU'] = cpu_times

        # Test with region map
        cpu_region_times = benchmark_with_region_map(
            cpu_renderer,
            "CPU (Numba JIT)",
            channels_data,
            num_frames=50
        )
        results['CPU_region'] = cpu_region_times

    # Test GPU Renderer
    if GPU_AVAILABLE:
        print("\n" + "="*60)
        print("Initializing GPU (Qt OpenGL Metal) Renderer...")
        print("="*60)
        gpu_renderer = QtMultiverseRenderer(width=1920, height=1080)
        gpu_renderer.set_blend_mode(0)  # Add mode
        gpu_renderer.set_brightness(1.0)
        print("✓ GPU renderer initialized")

        # Test without region map
        gpu_times = benchmark_renderer(
            gpu_renderer,
            "GPU (Qt OpenGL Metal)",
            channels_data,
            num_frames=100,
            warmup=10
        )
        results['GPU'] = gpu_times

        # Test with region map
        gpu_region_times = benchmark_with_region_map(
            gpu_renderer,
            "GPU (Qt OpenGL Metal)",
            channels_data,
            num_frames=50
        )
        results['GPU_region'] = gpu_region_times

    # Comparison
    print("\n" + "="*60)
    print("PERFORMANCE COMPARISON")
    print("="*60)

    if 'CPU' in results and 'GPU' in results:
        cpu_avg = np.mean(results['CPU'])
        gpu_avg = np.mean(results['GPU'])
        speedup = cpu_avg / gpu_avg

        print(f"\nWithout Region Map:")
        print(f"  CPU Average: {cpu_avg:.3f} ms/frame ({1000.0/cpu_avg:.1f} fps)")
        print(f"  GPU Average: {gpu_avg:.3f} ms/frame ({1000.0/gpu_avg:.1f} fps)")
        print(f"  Speedup: {speedup:.2f}x {'(GPU faster)' if speedup > 1 else '(CPU faster)'}")

    if 'CPU_region' in results and 'GPU_region' in results:
        cpu_region_avg = np.mean(results['CPU_region'])
        gpu_region_avg = np.mean(results['GPU_region'])
        speedup_region = cpu_region_avg / gpu_region_avg

        print(f"\nWith Region Map:")
        print(f"  CPU Average: {cpu_region_avg:.3f} ms/frame ({1000.0/cpu_region_avg:.1f} fps)")
        print(f"  GPU Average: {gpu_region_avg:.3f} ms/frame ({1000.0/gpu_region_avg:.1f} fps)")
        print(f"  Speedup: {speedup_region:.2f}x {'(GPU faster)' if speedup_region > 1 else '(CPU faster)'}")

    print("\n" + "="*60)
    print("Benchmark Complete!")
    print("="*60)


if __name__ == "__main__":
    main()
