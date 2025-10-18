"""
Qt-native OpenGL Renderer using QOpenGLWidget
Optimized for PyQt6 on macOS with custom shaders
"""

import numpy as np
from typing import List
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QSurfaceFormat
try:
    from OpenGL.GL import *
    from OpenGL.GL import shaders
    OPENGL_AVAILABLE = True
except ImportError:
    OPENGL_AVAILABLE = False
    print("Warning: PyOpenGL not available")


class QtMultiverseRenderer(QOpenGLWidget):
    """
    Qt OpenGL Widget 渲染器
    使用 QOpenGLWidget 和 custom shaders 進行高性能渲染
    完全兼容 Qt 事件循環和 macOS
    """

    # Vertex shader
    VERTEX_SHADER = """
    #version 330 core
    layout(location = 0) in vec2 position;
    layout(location = 1) in vec2 texcoord;
    out vec2 v_texcoord;

    void main() {
        gl_Position = vec4(position, 0.0, 1.0);
        v_texcoord = texcoord;
    }
    """

    # Fragment shader
    FRAGMENT_SHADER = """
    #version 330 core
    uniform sampler2D audio_tex;
    uniform vec4 frequencies;
    uniform vec4 intensities;
    uniform vec4 enabled_mask;
    uniform int blend_mode;
    uniform float brightness;

    in vec2 v_texcoord;
    out vec4 fragColor;

    vec3 hsv2rgb(vec3 c) {
        vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
        vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
        return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
    }

    float getHueFromFrequency(float freq) {
        freq = clamp(freq, 20.0, 20000.0);
        float baseFreq = 261.63;
        float octavePosition = fract(log2(freq / baseFreq));
        return octavePosition;
    }

    vec4 blendColors(vec4 c1, vec4 c2, int mode) {
        if (mode == 0) {
            return min(vec4(1.0), c1 + c2);
        } else if (mode == 1) {
            return vec4(1.0) - (vec4(1.0) - c1) * (vec4(1.0) - c2);
        } else if (mode == 2) {
            return vec4(abs(c1.rgb - c2.rgb), max(c1.a, c2.a));
        } else {
            vec3 result;
            for (int i = 0; i < 3; i++) {
                result[i] = c2[i] < 0.999 ? min(1.0, c1[i] / max(0.001, 1.0 - c2[i])) : 1.0;
            }
            return vec4(result, max(c1.a, c2.a));
        }
    }

    void main() {
        vec4 result = vec4(0.0);

        for (int ch = 0; ch < 4; ch++) {
            if (enabled_mask[ch] < 0.5) continue;

            float waveValue = texture(audio_tex, vec2(v_texcoord.x, float(ch) / 4.0)).r;
            float normalized = clamp((waveValue + 10.0) * 0.05 * intensities[ch], 0.0, 1.0);

            if (normalized > 0.01) {
                float hue = getHueFromFrequency(frequencies[ch]);
                vec3 rgb = hsv2rgb(vec3(hue, 1.0, 1.0));
                vec4 channelColor = vec4(rgb * normalized, normalized);
                result = blendColors(result, channelColor, blend_mode);
            }
        }

        result.rgb *= brightness;
        fragColor = result;
    }
    """

    def __init__(self, width: int = 1920, height: int = 1080, parent=None):
        """
        初始化 Qt OpenGL 渲染器

        Args:
            width: 渲染寬度
            height: 渲染高度
            parent: Qt parent widget
        """
        # Set OpenGL format before calling super().__init__
        fmt = QSurfaceFormat()
        fmt.setVersion(3, 3)
        fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
        fmt.setSwapBehavior(QSurfaceFormat.SwapBehavior.DoubleBuffer)
        QSurfaceFormat.setDefaultFormat(fmt)

        super().__init__(parent)

        self.render_width = width
        self.render_height = height

        # OpenGL resources (will be initialized in initializeGL)
        self.shader_program = None
        self.vao = None
        self.vbo = None
        self.audio_tex = None
        self.fbo = None
        self.fbo_tex = None

        # Rendering parameters
        self.blend_mode = 0
        self.brightness = 2.5

        # Audio data
        self.audio_data = np.zeros((4, width), dtype=np.float32)
        self.frequencies = np.array([440.0, 440.0, 440.0, 440.0], dtype=np.float32)
        self.intensities = np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float32)
        self.enabled_mask = np.array([0.0, 0.0, 0.0, 0.0], dtype=np.float32)

        # Rendered output
        self.rendered_image = None

        self.setFixedSize(QSize(width, height))

        print(f"Qt OpenGL Multiverse renderer initialized: {width}x{height}")

    def minimumSizeHint(self):
        return QSize(self.render_width, self.render_height)

    def sizeHint(self):
        return QSize(self.render_width, self.render_height)

    def initializeGL(self):
        """Initialize OpenGL resources"""
        if not OPENGL_AVAILABLE:
            print("Error: OpenGL not available")
            return

        # Clear color
        glClearColor(0.0, 0.0, 0.0, 1.0)

        # Compile shaders
        vertex_shader = shaders.compileShader(self.VERTEX_SHADER, GL_VERTEX_SHADER)
        fragment_shader = shaders.compileShader(self.FRAGMENT_SHADER, GL_FRAGMENT_SHADER)
        self.shader_program = shaders.compileProgram(vertex_shader, fragment_shader)

        # Create fullscreen quad
        vertices = np.array([
            # Position    Texcoord
            -1.0,  1.0,   0.0, 1.0,
            -1.0, -1.0,   0.0, 0.0,
             1.0,  1.0,   1.0, 1.0,
             1.0, -1.0,   1.0, 0.0,
        ], dtype=np.float32)

        # Create VAO and VBO
        self.vao = glGenVertexArrays(1)
        glBindVertexArray(self.vao)

        self.vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)

        # Position attribute
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 16, ctypes.c_void_p(0))

        # Texcoord attribute
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 16, ctypes.c_void_p(8))

        glBindVertexArray(0)

        # Create audio texture
        self.audio_tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.audio_tex)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_R32F, self.render_width, 4, 0,
                     GL_RED, GL_FLOAT, None)

        # Create framebuffer for offscreen rendering
        self.fbo = glGenFramebuffers(1)
        self.fbo_tex = glGenTextures(1)

        glBindTexture(GL_TEXTURE_2D, self.fbo_tex)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, self.render_width, self.render_height,
                     0, GL_RGBA, GL_UNSIGNED_BYTE, None)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0,
                              GL_TEXTURE_2D, self.fbo_tex, 0)

        if glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE:
            print("Error: Framebuffer is not complete")

        glBindFramebuffer(GL_FRAMEBUFFER, 0)

        print("Qt OpenGL renderer initialized successfully")

    def resizeGL(self, w, h):
        """Handle window resize"""
        glViewport(0, 0, w, h)

    def paintGL(self):
        """Render the scene"""
        if not OPENGL_AVAILABLE or self.shader_program is None:
            return

        # Bind framebuffer for offscreen rendering
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
        glViewport(0, 0, self.render_width, self.render_height)

        glClear(GL_COLOR_BUFFER_BIT)

        # Use shader program
        glUseProgram(self.shader_program)

        # Update audio texture
        glBindTexture(GL_TEXTURE_2D, self.audio_tex)
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, self.render_width, 4,
                       GL_RED, GL_FLOAT, self.audio_data.T)

        # Set uniforms
        glUniform1i(glGetUniformLocation(self.shader_program, b"audio_tex"), 0)
        glUniform4fv(glGetUniformLocation(self.shader_program, b"frequencies"),
                    1, self.frequencies)
        glUniform4fv(glGetUniformLocation(self.shader_program, b"intensities"),
                    1, self.intensities)
        glUniform4fv(glGetUniformLocation(self.shader_program, b"enabled_mask"),
                    1, self.enabled_mask)
        glUniform1i(glGetUniformLocation(self.shader_program, b"blend_mode"),
                   self.blend_mode)
        glUniform1f(glGetUniformLocation(self.shader_program, b"brightness"),
                   self.brightness)

        # Draw
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.audio_tex)
        glBindVertexArray(self.vao)
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)

        # Read back pixels
        pixels = glReadPixels(0, 0, self.render_width, self.render_height,
                             GL_RGB, GL_UNSIGNED_BYTE)
        self.rendered_image = np.frombuffer(pixels, dtype=np.uint8).reshape(
            (self.render_height, self.render_width, 3))
        self.rendered_image = np.flipud(self.rendered_image)  # Flip Y

        # Render to screen (default framebuffer)
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        glViewport(0, 0, self.width(), self.height())
        glClear(GL_COLOR_BUFFER_BIT)

        # Here you could render the FBO texture to screen if needed

    def render(self, channels_data: List[dict]) -> np.ndarray:
        """
        Render all channels

        Args:
            channels_data: List of channel data

        Returns:
            RGB image (height, width, 3), uint8
        """
        # Prepare audio data
        self.audio_data.fill(0.0)
        self.enabled_mask.fill(0.0)

        for i in range(min(4, len(channels_data))):
            ch_data = channels_data[i]
            if not ch_data.get('enabled', False):
                continue

            audio = ch_data.get('audio', np.array([]))
            if len(audio) == 0:
                continue

            # Resample to width
            if len(audio) != self.render_width:
                indices = np.linspace(0, len(audio) - 1, self.render_width).astype(int)
                self.audio_data[i] = audio[indices]
            else:
                self.audio_data[i] = audio

            self.frequencies[i] = ch_data.get('frequency', 440.0)
            self.intensities[i] = ch_data.get('intensity', 1.0)
            self.enabled_mask[i] = 1.0

        # Trigger paintGL
        self.update()
        self.makeCurrent()
        self.paintGL()
        self.doneCurrent()

        # Return rendered image
        if self.rendered_image is not None:
            return self.rendered_image.copy()
        else:
            return np.zeros((self.render_height, self.render_width, 3), dtype=np.uint8)

    def set_blend_mode(self, mode: int):
        """Set blend mode (0-3)"""
        self.blend_mode = max(0, min(3, mode))

    def set_brightness(self, brightness: float):
        """Set brightness (0-4)"""
        self.brightness = max(0.0, min(4.0, brightness))

    def cleanup(self):
        """Clean up OpenGL resources"""
        if not OPENGL_AVAILABLE:
            return

        self.makeCurrent()

        if self.vao is not None:
            glDeleteVertexArrays(1, [self.vao])
        if self.vbo is not None:
            glDeleteBuffers(1, [self.vbo])
        if self.audio_tex is not None:
            glDeleteTextures([self.audio_tex])
        if self.fbo_tex is not None:
            glDeleteTextures([self.fbo_tex])
        if self.fbo is not None:
            glDeleteFramebuffers(1, [self.fbo])

        self.doneCurrent()


class StandaloneQtRenderer:
    """
    Standalone Qt renderer (non-widget version)
    Uses QOffscreenSurface for rendering without displaying a window
    """

    def __init__(self, width: int = 1920, height: int = 1080):
        """Initialize standalone renderer"""
        from PyQt6.QtGui import QOffscreenSurface, QOpenGLContext

        self.width = width
        self.height = height

        # Create offscreen surface
        fmt = QSurfaceFormat()
        fmt.setVersion(3, 3)
        fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)

        self.surface = QOffscreenSurface()
        self.surface.setFormat(fmt)
        self.surface.create()

        # Create OpenGL context
        self.context = QOpenGLContext()
        self.context.setFormat(fmt)
        if not self.context.create():
            raise RuntimeError("Failed to create OpenGL context")

        # Make context current
        self.context.makeCurrent(self.surface)

        # Initialize OpenGL resources (similar to QtMultiverseRenderer)
        # ... (implementation would be similar to initializeGL above)

        print(f"Standalone Qt OpenGL renderer initialized: {width}x{height}")

    def render(self, channels_data: List[dict]) -> np.ndarray:
        """Render channels"""
        # Implementation similar to QtMultiverseRenderer.render
        pass

    def cleanup(self):
        """Clean up resources"""
        if hasattr(self, 'context'):
            self.context.doneCurrent()
