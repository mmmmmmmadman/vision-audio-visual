"""
GPU-Accelerated Multiverse Renderer using ModernGL
完整性能的 GPU 渲染，保持完整解析度
"""

import numpy as np
import moderngl as mgl
from typing import List, Tuple
import struct


class GPUMultiverseRenderer:
    """GPU 加速的 Multiverse 渲染器"""

    # Fragment shader - 在 GPU 上執行 Multiverse 算法
    FRAGMENT_SHADER = """
    #version 330

    uniform sampler2D audio_tex;  // 音訊波形數據 (4 通道)
    uniform vec4 frequencies;      // 4 個通道的頻率
    uniform vec4 intensities;      // 4 個通道的強度
    uniform int blend_mode;        // 混合模式 (0-3)
    uniform float brightness;      // 亮度

    in vec2 v_texcoord;
    out vec4 fragColor;

    // HSV to RGB 轉換
    vec3 hsv2rgb(vec3 c) {
        vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
        vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
        return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
    }

    // 頻率到色相映射（八度循環）
    float getHueFromFrequency(float freq) {
        freq = clamp(freq, 20.0, 20000.0);
        float baseFreq = 261.63;  // C4
        float octavePosition = fract(log2(freq / baseFreq));
        return octavePosition;  // 0-1 範圍
    }

    // 混合模式
    vec4 blendColors(vec4 c1, vec4 c2, int mode) {
        if (mode == 0) {  // Add
            return min(vec4(1.0), c1 + c2);
        } else if (mode == 1) {  // Screen
            return vec4(1.0) - (vec4(1.0) - c1) * (vec4(1.0) - c2);
        } else if (mode == 2) {  // Difference
            return vec4(abs(c1.rgb - c2.rgb), max(c1.a, c2.a));
        } else {  // Color Dodge
            vec3 result;
            for (int i = 0; i < 3; i++) {
                result[i] = c2[i] < 0.999 ? min(1.0, c1[i] / max(0.001, 1.0 - c2[i])) : 1.0;
            }
            return vec4(result, max(c1.a, c2.a));
        }
    }

    void main() {
        vec4 result = vec4(0.0);

        // 對每個通道進行渲染
        for (int ch = 0; ch < 4; ch++) {
            // 從音訊 texture 採樣波形值
            float waveValue = texture(audio_tex, vec2(v_texcoord.x, float(ch) / 4.0)).r;

            // 正規化 (-10V to +10V -> 0-1)
            float normalized = clamp((waveValue + 10.0) * 0.05 * intensities[ch], 0.0, 1.0);

            if (normalized > 0.01) {
                // 頻率到顏色
                float hue = getHueFromFrequency(frequencies[ch]);
                vec3 rgb = hsv2rgb(vec3(hue, 1.0, 1.0));

                // 創建垂直條紋效果
                vec4 channelColor = vec4(rgb * normalized, normalized);

                // 混合到結果
                result = blendColors(result, channelColor, blend_mode);
            }
        }

        // 應用亮度
        result.rgb *= brightness;

        fragColor = result;
    }
    """

    VERTEX_SHADER = """
    #version 330

    in vec2 in_position;
    in vec2 in_texcoord;
    out vec2 v_texcoord;

    void main() {
        gl_Position = vec4(in_position, 0.0, 1.0);
        v_texcoord = in_texcoord;
    }
    """

    def __init__(self, width: int = 1920, height: int = 1080):
        """初始化 GPU 渲染器"""
        self.width = width
        self.height = height

        # 創建 OpenGL context (standalone, 不需要窗口)
        # 在 macOS 上需要特殊處理以避免與 Qt 衝突
        import platform
        if platform.system() == 'Darwin':  # macOS
            # macOS with Qt: use require parameter for better compatibility
            self.ctx = mgl.create_standalone_context(require=330)
        else:
            self.ctx = mgl.create_standalone_context()

        # 編譯 shader
        self.prog = self.ctx.program(
            vertex_shader=self.VERTEX_SHADER,
            fragment_shader=self.FRAGMENT_SHADER
        )

        # 創建全屏四邊形
        vertices = np.array([
            # Position    Texcoord
            -1.0,  1.0,   0.0, 1.0,
            -1.0, -1.0,   0.0, 0.0,
             1.0,  1.0,   1.0, 1.0,
             1.0, -1.0,   1.0, 0.0,
        ], dtype='f4')

        self.vbo = self.ctx.buffer(vertices)
        self.vao = self.ctx.vertex_array(
            self.prog,
            [(self.vbo, '2f 2f', 'in_position', 'in_texcoord')]
        )

        # 創建音訊數據 texture (4 通道 x width)
        self.audio_tex = self.ctx.texture((width, 4), 1, dtype='f4')
        self.audio_tex.filter = (mgl.LINEAR, mgl.LINEAR)

        # 創建 framebuffer 用於離屏渲染
        self.fbo_tex = self.ctx.texture((width, height), 4)
        self.fbo = self.ctx.framebuffer(color_attachments=[self.fbo_tex])

        # 設置 uniforms
        self.prog['audio_tex'].value = 0
        self.prog['blend_mode'].value = 0
        self.prog['brightness'].value = 2.5

        print(f"GPU Multiverse renderer initialized: {width}x{height}")
        print(f"OpenGL version: {self.ctx.version_code}")

    def render(self, channels_data: List[dict]) -> np.ndarray:
        """
        在 GPU 上渲染所有通道

        Args:
            channels_data: 4 個通道的數據，每個包含：
                - 'enabled': bool
                - 'audio': np.ndarray (波形數據)
                - 'frequency': float (Hz)
                - 'intensity': float

        Returns:
            RGB 圖像 (height, width, 3), uint8
        """
        # 準備音訊數據上傳到 GPU
        audio_data = np.zeros((4, self.width), dtype=np.float32)
        frequencies = np.zeros(4, dtype=np.float32)
        intensities = np.zeros(4, dtype=np.float32)

        for i in range(4):
            if i < len(channels_data) and channels_data[i].get('enabled', False):
                # 重新採樣音訊數據到寬度
                audio = channels_data[i].get('audio', np.array([]))
                if len(audio) > 0:
                    if len(audio) != self.width:
                        indices = np.linspace(0, len(audio) - 1, self.width).astype(int)
                        audio_data[i] = audio[indices]
                    else:
                        audio_data[i] = audio

                frequencies[i] = channels_data[i].get('frequency', 440.0)
                intensities[i] = channels_data[i].get('intensity', 1.0)

        # 上傳音訊數據到 GPU texture
        self.audio_tex.write(audio_data.T.tobytes())

        # 設置 uniforms
        self.prog['frequencies'].value = tuple(frequencies)
        self.prog['intensities'].value = tuple(intensities)

        # 綁定 texture
        self.audio_tex.use(0)

        # 渲染到 framebuffer
        self.fbo.use()
        self.ctx.clear(0.0, 0.0, 0.0, 1.0)
        self.vao.render(mgl.TRIANGLE_STRIP)

        # 讀回 GPU 數據
        data = self.fbo_tex.read()
        img = np.frombuffer(data, dtype=np.uint8).reshape((self.height, self.width, 4))

        # 翻轉 Y 軸（OpenGL 座標系統）
        img = np.flipud(img)

        # 返回 RGB（去掉 alpha）
        return img[:, :, :3].copy()

    def set_blend_mode(self, mode: int):
        """設置混合模式 (0-3)"""
        self.prog['blend_mode'].value = int(np.clip(mode, 0, 3))

    def set_brightness(self, brightness: float):
        """設置亮度"""
        self.prog['brightness'].value = float(np.clip(brightness, 0.0, 4.0))

    def __del__(self):
        """清理 GPU 資源"""
        if hasattr(self, 'ctx'):
            self.ctx.release()
