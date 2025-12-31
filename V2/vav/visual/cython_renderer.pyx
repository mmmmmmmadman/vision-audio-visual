# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: cdivision=True
# cython: initializedcheck=False
"""
Cython-optimized Multiverse Renderer
C-level performance for audio visualization
"""

import numpy as np
cimport numpy as np
from libc.math cimport log2, fabs, fmax, fmin
from libc.stdlib cimport malloc, free
cimport cython

# Type definitions
ctypedef np.float32_t FLOAT32
ctypedef np.uint8_t UINT8

@cython.cdivision(True)
@cython.boundscheck(False)
@cython.wraparound(False)
cdef inline float get_hue_from_frequency(float freq) nogil:
    """頻率映射到色相（基於八度）"""
    cdef float base_freq = 261.63
    cdef float octave_position

    # Clamp frequency
    if freq < 20.0:
        freq = 20.0
    elif freq > 20000.0:
        freq = 20000.0

    octave_position = log2(freq / base_freq)
    octave_position = octave_position - <int>octave_position  # Modulo 1.0
    if octave_position < 0.0:
        octave_position += 1.0

    return octave_position


@cython.cdivision(True)
@cython.boundscheck(False)
@cython.wraparound(False)
cdef inline void hsv_to_rgb(float h, float s, float v, float* r, float* g, float* b) nogil:
    """HSV 轉 RGB"""
    cdef float c, x, m
    cdef int h_sector

    # Normalize h to 0-1
    h = h - <int>h
    if h < 0.0:
        h += 1.0

    c = v * s
    h_sector = <int>(h * 6.0)
    x = c * (1.0 - fabs((h * 6.0) - <float>(h_sector * 2) - 1.0))

    if h_sector == 0:
        r[0] = c
        g[0] = x
        b[0] = 0.0
    elif h_sector == 1:
        r[0] = x
        g[0] = c
        b[0] = 0.0
    elif h_sector == 2:
        r[0] = 0.0
        g[0] = c
        b[0] = x
    elif h_sector == 3:
        r[0] = 0.0
        g[0] = x
        b[0] = c
    elif h_sector == 4:
        r[0] = x
        g[0] = 0.0
        b[0] = c
    else:
        r[0] = c
        g[0] = 0.0
        b[0] = x

    m = v - c
    r[0] += m
    g[0] += m
    b[0] += m


@cython.boundscheck(False)
@cython.wraparound(False)
cdef void render_channel_cython(FLOAT32[:] audio_buffer,
                               float frequency,
                               float intensity,
                               FLOAT32[:, :, :] rgba_layer) nogil:
    """
    渲染單一通道 - Cython 優化版本

    Args:
        audio_buffer: 音訊緩衝
        frequency: 頻率
        intensity: 強度
        rgba_layer: 輸出 RGBA 圖層 (height, width, 4)
    """
    cdef int height = rgba_layer.shape[0]
    cdef int width = rgba_layer.shape[1]
    cdef int buffer_len = audio_buffer.shape[0]
    cdef int x, y, idx
    cdef float hue, r, g, b
    cdef float waveform_val, normalized

    if buffer_len == 0:
        return

    # 獲取頻率對應的顏色
    hue = get_hue_from_frequency(frequency)
    hsv_to_rgb(hue, 1.0, 1.0, &r, &g, &b)

    # 處理每個像素列
    for x in range(width):
        # 重新採樣索引
        idx = <int>(((<float>x / <float>width) * (<float>buffer_len - 1.0)))
        waveform_val = audio_buffer[idx]

        # 正規化電壓 (-10V ~ +10V -> 0-1)
        normalized = (waveform_val + 10.0) * 0.05 * intensity
        if normalized < 0.0:
            normalized = 0.0
        elif normalized > 1.0:
            normalized = 1.0

        # 設置所有行的顏色
        for y in range(height):
            rgba_layer[y, x, 0] = r * normalized
            rgba_layer[y, x, 1] = g * normalized
            rgba_layer[y, x, 2] = b * normalized
            rgba_layer[y, x, 3] = normalized


@cython.boundscheck(False)
@cython.wraparound(False)
cdef void blend_add_cython(FLOAT32[:, :, :] buffer, FLOAT32[:, :, :] layer) nogil:
    """加法混合"""
    cdef int height = buffer.shape[0]
    cdef int width = buffer.shape[1]
    cdef int y, x, c
    cdef float val

    for y in range(height):
        for x in range(width):
            for c in range(4):
                val = buffer[y, x, c] + layer[y, x, c]
                if val > 1.0:
                    val = 1.0
                buffer[y, x, c] = val


@cython.boundscheck(False)
@cython.wraparound(False)
cdef void blend_screen_cython(FLOAT32[:, :, :] buffer, FLOAT32[:, :, :] layer) nogil:
    """濾色混合"""
    cdef int height = buffer.shape[0]
    cdef int width = buffer.shape[1]
    cdef int y, x, c

    for y in range(height):
        for x in range(width):
            for c in range(4):
                buffer[y, x, c] = 1.0 - (1.0 - buffer[y, x, c]) * (1.0 - layer[y, x, c])


@cython.boundscheck(False)
@cython.wraparound(False)
cdef void blend_difference_cython(FLOAT32[:, :, :] buffer, FLOAT32[:, :, :] layer) nogil:
    """差異混合"""
    cdef int height = buffer.shape[0]
    cdef int width = buffer.shape[1]
    cdef int y, x

    for y in range(height):
        for x in range(width):
            # RGB: absolute difference
            buffer[y, x, 0] = fabs(buffer[y, x, 0] - layer[y, x, 0])
            buffer[y, x, 1] = fabs(buffer[y, x, 1] - layer[y, x, 1])
            buffer[y, x, 2] = fabs(buffer[y, x, 2] - layer[y, x, 2])
            # Alpha: max
            buffer[y, x, 3] = fmax(buffer[y, x, 3], layer[y, x, 3])


@cython.boundscheck(False)
@cython.wraparound(False)
cdef void blend_color_dodge_cython(FLOAT32[:, :, :] buffer, FLOAT32[:, :, :] layer) nogil:
    """顏色加深混合"""
    cdef int height = buffer.shape[0]
    cdef int width = buffer.shape[1]
    cdef int y, x, c
    cdef float result, denominator

    for y in range(height):
        for x in range(width):
            for c in range(3):  # RGB only
                if layer[y, x, c] < 0.999:
                    denominator = 1.0 - layer[y, x, c]
                    if denominator < 0.001:
                        denominator = 0.001
                    result = buffer[y, x, c] / denominator
                    if result > 1.0:
                        result = 1.0
                    buffer[y, x, c] = result
                else:
                    buffer[y, x, c] = 1.0
            # Alpha: max
            buffer[y, x, 3] = fmax(buffer[y, x, 3], layer[y, x, 3])


@cython.boundscheck(False)
@cython.wraparound(False)
cdef void apply_brightness_and_convert_cython(FLOAT32[:, :, :] buffer,
                                              float brightness,
                                              UINT8[:, :, :] rgb) nogil:
    """應用亮度並轉換為 uint8 RGB"""
    cdef int height = buffer.shape[0]
    cdef int width = buffer.shape[1]
    cdef int y, x, c
    cdef float val
    cdef int int_val

    for y in range(height):
        for x in range(width):
            for c in range(3):
                val = buffer[y, x, c] * brightness * 255.0
                if val < 0.0:
                    int_val = 0
                elif val > 255.0:
                    int_val = 255
                else:
                    int_val = <int>val
                rgb[y, x, c] = <UINT8>int_val


# Python wrapper class
class CythonMultiverseRenderer:
    """
    Cython 優化的 Multiverse 渲染器
    提供 C-level 性能的音訊視覺化
    """

    def __init__(self, int width=1920, int height=1080):
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

        # 臨時通道緩衝
        self.channel_buffer = np.zeros((height, width, 4), dtype=np.float32)

        # 參數
        self.blend_mode = 0  # 0=Add, 1=Screen, 2=Difference, 3=Color Dodge
        self.brightness = 1.0

        print(f"Cython Multiverse renderer initialized: {width}x{height}")

    def render(self, channels_data):
        """
        渲染所有通道並混合

        Args:
            channels_data: 通道資料列表

        Returns:
            渲染結果 RGB 圖像 (height, width, 3), uint8
        """
        # Type declarations
        cdef FLOAT32[:, :, :] buffer_view = self.buffer
        cdef FLOAT32[:, :, :] channel_view = self.channel_buffer

        # 清空緩衝
        self.buffer.fill(0.0)

        # 渲染並混合所有通道
        for idx, ch_data in enumerate(channels_data):
            if not ch_data.get('enabled', False):
                continue

            audio = ch_data.get('audio', np.array([]))
            if len(audio) == 0:
                continue

            # 確保 audio 是 float32
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)

            # 清空通道緩衝
            self.channel_buffer.fill(0.0)

            # 渲染通道（釋放 GIL 以允許真正的多線程）
            cdef FLOAT32[:] audio_view = audio
            cdef float frequency = ch_data.get('frequency', 440.0)
            cdef float intensity = ch_data.get('intensity', 1.0)

            with nogil:
                render_channel_cython(audio_view, frequency, intensity, channel_view)

                # 混合
                if self.blend_mode == 0:
                    blend_add_cython(buffer_view, channel_view)
                elif self.blend_mode == 1:
                    blend_screen_cython(buffer_view, channel_view)
                elif self.blend_mode == 2:
                    blend_difference_cython(buffer_view, channel_view)
                elif self.blend_mode == 3:
                    blend_color_dodge_cython(buffer_view, channel_view)

        # 應用亮度並轉換為 uint8
        rgb = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        cdef UINT8[:, :, :] rgb_view = rgb
        cdef float brightness = self.brightness

        with nogil:
            apply_brightness_and_convert_cython(buffer_view, brightness, rgb_view)

        return rgb

    def set_blend_mode(self, int mode):
        """設置混合模式 (0-3)"""
        self.blend_mode = max(0, min(3, mode))

    def set_brightness(self, float brightness):
        """設置亮度 (0-4)"""
        self.brightness = max(0.0, min(4.0, brightness))
