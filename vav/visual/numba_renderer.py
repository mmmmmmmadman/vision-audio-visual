"""
Numba JIT-Compiled Multiverse Renderer
Ultra-fast CPU rendering using Numba's LLVM JIT compilation
"""

import numpy as np
from typing import List
from numba import njit, prange
import math


@njit(fastmath=True, cache=True)
def get_hue_from_frequency(freq: float) -> float:
    """頻率映射到色相（基於八度）- JIT compiled"""
    freq = max(20.0, min(20000.0, freq))
    base_freq = 261.63
    octave_position = math.log2(freq / base_freq) % 1.0
    if octave_position < 0:
        octave_position += 1.0
    return octave_position


@njit(fastmath=True, cache=True)
def hsv_to_rgb(h: float, s: float, v: float) -> tuple:
    """HSV 轉 RGB - JIT compiled"""
    h_normalized = h % 1.0  # Ensure 0-1 range
    c = v * s
    x = c * (1.0 - abs((h_normalized * 6.0) % 2.0 - 1.0))

    h_sector = int(h_normalized * 6.0)

    if h_sector == 0:
        r, g, b = c, x, 0.0
    elif h_sector == 1:
        r, g, b = x, c, 0.0
    elif h_sector == 2:
        r, g, b = 0.0, c, x
    elif h_sector == 3:
        r, g, b = 0.0, x, c
    elif h_sector == 4:
        r, g, b = x, 0.0, c
    else:
        r, g, b = c, 0.0, x

    m = v - c
    return r + m, g + m, b + m


@njit(fastmath=True, cache=True)
def rotate_image(image: np.ndarray, angle_deg: float) -> np.ndarray:
    """
    旋轉圖像 - Numba JIT 編譯（基於原始 Multiverse C++ 實現）
    使用反向映射 + scale 填充避免黑邊

    Args:
        image: 輸入圖像 (height, width, channels)
        angle_deg: 旋轉角度（度，-180 到 +180）

    Returns:
        旋轉後的圖像
    """
    height, width = image.shape[:2]
    channels = image.shape[2]

    # Convert to radians
    angle_rad = angle_deg * math.pi / 180.0
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)

    # Calculate scale to fill canvas (avoid black borders)
    abs_cos_a = abs(cos_a)
    abs_sin_a = abs(sin_a)
    scale_x = (width * abs_cos_a + height * abs_sin_a) / width
    scale_y = (width * abs_sin_a + height * abs_cos_a) / height
    scale = max(scale_x, scale_y)

    # Center coordinates
    center_x = width / 2.0
    center_y = height / 2.0

    # Create output image
    rotated = np.zeros_like(image)

    # Inverse mapping (for each output pixel, find source pixel)
    for y in range(height):
        for x in range(width):
            # Scale offset from center
            dx = (x - center_x) / scale
            dy = (y - center_y) / scale

            # Rotate (inverse)
            src_x = int(center_x + dx * cos_a + dy * sin_a)
            src_y = int(center_y - dx * sin_a + dy * cos_a)

            # Copy pixel if within bounds
            if 0 <= src_x < width and 0 <= src_y < height:
                for c in range(channels):
                    rotated[y, x, c] = image[src_y, src_x, c]

    return rotated


@njit(parallel=True, fastmath=True, cache=True)
def render_channel_numba(audio_buffer: np.ndarray,
                        frequency: float,
                        intensity: float,
                        curve: float,
                        angle: float,
                        width: int,
                        height: int) -> np.ndarray:
    """
    渲染單一通道 - Numba JIT 編譯，使用平行化

    Args:
        audio_buffer: 音訊緩衝（波形數據，範圍 -10 到 +10V）
        frequency: 主導頻率 (Hz)
        intensity: 強度 (0-1.5)
        curve: 曲線 (0-1, 0=無彎曲, 1=最大彎曲，基於 Y 軸位置偏移 X 採樣)
        angle: 旋轉角度（度，-180 到 +180）
        width: 輸出寬度
        height: 輸出高度

    Returns:
        通道圖層 (height, width, 4) RGBA
    """
    # 獲取頻率對應的顏色（固定顏色，不隨波形變化）
    hue = get_hue_from_frequency(frequency)
    r, g, b = hsv_to_rgb(hue, 1.0, 1.0)

    # 重新採樣到寬度
    buffer_len = len(audio_buffer)
    if buffer_len == 0:
        return np.zeros((height, width, 4), dtype=np.float32)

    # 創建 RGBA 圖層
    rgba_layer = np.zeros((height, width, 4), dtype=np.float32)

    # 並行處理每一行（使用 prange）
    for y in prange(height):
        # Y 軸位置（用於 curve 效果）
        y_from_center = (y / float(height) - 0.5) * 2.0  # -1 to 1 range

        for x in range(width):
            # 初始 X 採樣位置
            x_normalized = x / float(width)
            x_sample = x_normalized

            # 應用 curve（基於 Y 位置彎曲 X 採樣）
            if curve > 0.001:
                # 使用 sin 創建拋物線彎曲（中間彎曲最大，兩側不彎曲）
                bend_shape = math.sin(x_normalized * math.pi)  # 0 to 1 to 0
                bend_amount = y_from_center * bend_shape * curve * 2.0
                x_sample = (x_sample + bend_amount) % 1.0
                if x_sample < 0:
                    x_sample += 1.0

            # 採樣波形
            idx = int(x_sample * (buffer_len - 1))
            if idx < 0:
                idx = 0
            if idx >= buffer_len:
                idx = buffer_len - 1
            waveform_val = audio_buffer[idx]

            # 正規化電壓 (-10V ~ +10V -> 0-1)
            normalized = max(0.0, min(1.0, (waveform_val + 10.0) * 0.05 * intensity))

            # 設置顏色（顏色固定，只有亮度變化）
            rgba_layer[y, x, 0] = r * normalized  # R
            rgba_layer[y, x, 1] = g * normalized  # G
            rgba_layer[y, x, 2] = b * normalized  # B
            rgba_layer[y, x, 3] = normalized      # A

    return rgba_layer


@njit(parallel=True, fastmath=True, cache=True)
def blend_add(buffer: np.ndarray, layer: np.ndarray):
    """加法混合 - Numba JIT 並行化"""
    height, width = buffer.shape[:2]
    for y in prange(height):
        for x in range(width):
            for c in range(4):
                buffer[y, x, c] = min(1.0, buffer[y, x, c] + layer[y, x, c])


@njit(parallel=True, fastmath=True, cache=True)
def blend_screen(buffer: np.ndarray, layer: np.ndarray):
    """濾色混合 - Numba JIT 並行化"""
    height, width = buffer.shape[:2]
    for y in prange(height):
        for x in range(width):
            for c in range(4):
                buffer[y, x, c] = 1.0 - (1.0 - buffer[y, x, c]) * (1.0 - layer[y, x, c])


@njit(parallel=True, fastmath=True, cache=True)
def blend_difference(buffer: np.ndarray, layer: np.ndarray):
    """差異混合 - Numba JIT 並行化"""
    height, width = buffer.shape[:2]
    for y in prange(height):
        for x in range(width):
            for c in range(3):  # RGB
                buffer[y, x, c] = abs(buffer[y, x, c] - layer[y, x, c])
            # Alpha: max
            buffer[y, x, 3] = max(buffer[y, x, 3], layer[y, x, 3])


@njit(parallel=True, fastmath=True, cache=True)
def blend_color_dodge(buffer: np.ndarray, layer: np.ndarray):
    """顏色加深 - Numba JIT 並行化"""
    height, width = buffer.shape[:2]
    for y in prange(height):
        for x in range(width):
            for c in range(3):  # RGB
                if layer[y, x, c] < 0.999:
                    result = buffer[y, x, c] / max(0.001, 1.0 - layer[y, x, c])
                    buffer[y, x, c] = min(1.0, result)
                else:
                    buffer[y, x, c] = 1.0
            # Alpha: max
            buffer[y, x, 3] = max(buffer[y, x, 3], layer[y, x, 3])


@njit(parallel=True, fastmath=True, cache=True)
def apply_brightness_and_convert(buffer: np.ndarray, brightness: float) -> np.ndarray:
    """應用亮度並轉換為 uint8 RGB - Numba JIT 並行化"""
    height, width = buffer.shape[:2]
    rgb = np.zeros((height, width, 3), dtype=np.uint8)

    for y in prange(height):
        for x in range(width):
            for c in range(3):
                val = buffer[y, x, c] * brightness * 255.0
                rgb[y, x, c] = max(0, min(255, int(val)))

    return rgb


class NumbaMultiverseRenderer:
    """
    Numba JIT 編譯的 Multiverse 渲染器
    使用 LLVM JIT 編譯和平行化達到極致性能
    """

    def __init__(self, width: int = 1920, height: int = 1080):
        """
        初始化渲染器

        Args:
            width: 輸出寬度
            height: 輸出高度
        """
        self.width = width
        self.height = height

        # 渲染緩衝（RGBA）
        self.buffer = np.zeros((height, width, 4), dtype=np.float32)

        # 參數
        self.blend_mode = 0  # 0=Add, 1=Screen, 2=Difference, 3=Color Dodge
        self.brightness = 2.5  # 預設較高亮度以確保視覺化可見

        # 預熱 JIT 編譯（首次調用會觸發編譯）
        print("Warming up Numba JIT compiler...")
        dummy_audio = np.zeros(100, dtype=np.float32)
        dummy_layer = render_channel_numba(dummy_audio, 440.0, 1.0, 0.0, 0.0, 100, 100)
        _ = rotate_image(dummy_layer, 45.0)
        print(f"Numba Multiverse renderer initialized: {width}x{height}")

    def render(self, channels_data: List[dict]) -> np.ndarray:
        """
        渲染所有通道並混合

        Args:
            channels_data: 通道資料列表，每個元素包含：
                - 'audio': 音訊緩衝 (numpy array)
                - 'frequency': 頻率 (Hz)
                - 'intensity': 強度 (0-1.5)
                - 'angle': 旋轉角度 (度，-180 到 +180)
                - 'enabled': 是否啟用 (bool)

        Returns:
            渲染結果 RGB 圖像 (height, width, 3), uint8
        """
        # 清空緩衝
        self.buffer.fill(0.0)

        # 渲染並混合所有通道
        for idx, ch_data in enumerate(channels_data):
            if not ch_data.get('enabled', False):
                continue

            audio = ch_data.get('audio', np.array([]))
            if len(audio) == 0:
                continue

            # 渲染通道（JIT 編譯）
            channel_layer = render_channel_numba(
                audio_buffer=audio.astype(np.float32),
                frequency=ch_data.get('frequency', 440.0),
                intensity=ch_data.get('intensity', 1.0),
                curve=ch_data.get('curve', 0.0),
                angle=ch_data.get('angle', 0.0),
                width=self.width,
                height=self.height
            )

            # 應用旋轉（如果 angle 不為 0）
            angle = ch_data.get('angle', 0.0)
            if abs(angle) > 0.1:  # 避免不必要的旋轉運算
                channel_layer = rotate_image(channel_layer, angle)

            # 混合（JIT 編譯）
            if self.blend_mode == 0:
                blend_add(self.buffer, channel_layer)
            elif self.blend_mode == 1:
                blend_screen(self.buffer, channel_layer)
            elif self.blend_mode == 2:
                blend_difference(self.buffer, channel_layer)
            elif self.blend_mode == 3:
                blend_color_dodge(self.buffer, channel_layer)

        # 應用亮度並轉換為 uint8（JIT 編譯）
        rgb = apply_brightness_and_convert(self.buffer, self.brightness)

        return rgb

    def set_blend_mode(self, mode: int):
        """設置混合模式 (0-3)"""
        self.blend_mode = max(0, min(3, mode))

    def set_brightness(self, brightness: float):
        """設置亮度 (0-4)"""
        self.brightness = max(0.0, min(4.0, brightness))
