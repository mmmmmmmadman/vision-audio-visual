"""
Qt-native OpenGL Renderer using QOpenGLWidget
Optimized for PyQt6 on macOS with custom shaders
"""

import numpy as np
from typing import List
import threading
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtCore import QSize, Qt, pyqtSignal, QMutex, QMutexLocker
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

    Thread-safe: render() can be called from any thread.
    OpenGL operations are always executed in the GUI thread via Qt signals.
    """

    # Signal to request rendering from GUI thread
    render_requested = pyqtSignal()

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

    # Fragment shader with curve, angle, region map support
    FRAGMENT_SHADER = """
    #version 330 core
    uniform sampler2D audio_tex;
    uniform sampler2D region_tex;
    uniform vec4 frequencies;
    uniform vec4 intensities;
    uniform vec4 curves;
    uniform vec4 angles;
    uniform vec4 enabled_mask;
    uniform int blend_mode;
    uniform float brightness;
    uniform int use_region_map;

    in vec2 v_texcoord;
    out vec4 fragColor;

    #define PI 3.14159265359

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

    vec2 rotate(vec2 pos, float angle) {
        float rad = radians(angle);
        float cosA = cos(rad);
        float sinA = sin(rad);
        return vec2(
            pos.x * cosA - pos.y * sinA,
            pos.x * sinA + pos.y * cosA
        );
    }

    vec4 blendColors(vec4 c1, vec4 c2, int mode) {
        if (mode == 0) {
            return min(vec4(1.0), c1 + c2);
        } else if (mode == 1) {
            return vec4(1.0) - (vec4(1.0) - c1) * (vec4(1.0) - c2);
        } else if (mode == 2) {
            return vec4(abs(c1.rgb - c2.rgb), max(c1.a, c2.a));
        } else if (mode == 3) {
            vec3 result;
            for (int i = 0; i < 3; i++) {
                if (c2[i] >= 0.999) {
                    result[i] = 1.0;
                } else if (c1[i] <= 0.001) {
                    result[i] = 0.0;
                } else {
                    result[i] = min(1.0, c1[i] / (1.0 - c2[i]));
                }
            }
            return vec4(result, max(c1.a, c2.a));
        } else {
            return min(vec4(1.0), c1 + c2);
        }
    }

    void main() {
        // Get region ID if using region map
        int currentRegion = -1;
        if (use_region_map > 0) {
            // Flip Y coordinate for region map (OpenGL texture coordinates)
            float regionVal = texture(region_tex, vec2(v_texcoord.x, 1.0 - v_texcoord.y)).r;
            currentRegion = int(regionVal * 255.0);
        }

        // Render and blend all channels
        vec4 result = vec4(0.0);
        bool firstChannel = true;

        for (int ch = 0; ch < 4; ch++) {
            if (enabled_mask[ch] < 0.5) continue;

            vec2 uv = v_texcoord;
            float curve = curves[ch];
            float angle = angles[ch];

            // Apply rotation with dynamic scaling (match CPU's rotate_image)
            if (abs(angle) > 0.1) {
                // Calculate scale to fill canvas and avoid black borders
                float rad = radians(angle);
                float abs_cos = abs(cos(rad));
                float abs_sin = abs(sin(rad));
                // Assuming square texture (width == height)
                float scale_x = abs_cos + abs_sin;
                float scale_y = abs_sin + abs_cos;
                float scale = max(scale_x, scale_y);

                // Apply inverse rotation with scaling
                vec2 centered = (uv - 0.5) / scale;  // Scale before rotation
                centered = rotate(centered, angle);
                uv = centered + 0.5;

                // Skip only if truly out of bounds after scaling
                if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) continue;
            }

            // Apply curve (Y-based X-sampling offset)
            float x_sample = uv.x;
            if (curve > 0.001) {
                float y_from_center = (uv.y - 0.5) * 2.0;
                float bend_shape = sin(uv.x * PI);
                float bend_amount = y_from_center * bend_shape * curve * 2.0;
                x_sample = fract(x_sample + bend_amount);
            }

            float waveValue = texture(audio_tex, vec2(x_sample, float(ch) / 4.0)).r;
            // Match Multiverse.cpp AND Numba renderer: (voltage + 10.0) * 0.05 * intensity
            // waveValue is in ±10V range, normalize to 0-1
            float normalized = clamp((waveValue + 10.0) * 0.05 * intensities[ch], 0.0, 1.0);

            if (normalized > 0.01) {
                float hue = getHueFromFrequency(frequencies[ch]);
                vec3 rgb = hsv2rgb(vec3(hue, 1.0, 1.0));
                vec4 channelColor = vec4(rgb * normalized, normalized);

                // Apply region filtering: zero out if not in this channel's region
                if (use_region_map > 0 && ch != currentRegion) {
                    channelColor = vec4(0.0);
                }

                // Only blend non-zero colors
                if (channelColor.a > 0.001) {
                    if (firstChannel) {
                        result = channelColor;
                        firstChannel = false;
                    } else {
                        result = blendColors(result, channelColor, blend_mode);
                    }
                }
            }
        }

        // Apply brightness
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
        self.region_tex = None
        self.fbo = None
        self.fbo_tex = None

        # Rendering parameters
        self.blend_mode = 0
        self.brightness = 2.5

        # Audio data
        self.audio_data = np.zeros((4, width), dtype=np.float32)
        self.frequencies = np.array([440.0, 440.0, 440.0, 440.0], dtype=np.float32)
        self.intensities = np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float32)
        self.curves = np.array([0.0, 0.0, 0.0, 0.0], dtype=np.float32)
        self.angles = np.array([0.0, 0.0, 0.0, 0.0], dtype=np.float32)
        self.enabled_mask = np.array([0.0, 0.0, 0.0, 0.0], dtype=np.float32)

        # Region map data
        self.region_map_data = None
        self.use_region_map = 0

        # Rendered output (thread-safe access)
        self.rendered_image = None
        self.rendered_image_mutex = QMutex()

        # Thread synchronization for render requests
        self.render_complete_event = threading.Event()
        self.pending_channels_data = None
        self.pending_region_map = None
        self.channels_data_mutex = QMutex()

        # Store the thread that created this renderer (GUI thread)
        self.gui_thread = threading.current_thread()

        self.setFixedSize(QSize(width, height))

        # Connect signal to render slot (Qt will use queued connection for cross-thread)
        self.render_requested.connect(self._do_render_in_gui_thread, Qt.ConnectionType.QueuedConnection)

        # Force OpenGL initialization by showing and hiding widget
        self.show()
        self.hide()

        print(f"Qt OpenGL Multiverse renderer initialized: {width}x{height} (thread-safe)")

    def minimumSizeHint(self):
        return QSize(self.render_width, self.render_height)

    def sizeHint(self):
        return QSize(self.render_width, self.render_height)

    def initializeGL(self):
        """Initialize OpenGL resources"""
        print("[Qt OpenGL] initializeGL called")
        if not OPENGL_AVAILABLE:
            print("Error: OpenGL not available")
            return

        # Clear color
        glClearColor(0.0, 0.0, 0.0, 1.0)

        # Compile shaders WITHOUT validation (we'll validate after FBO creation)
        vertex_shader = shaders.compileShader(self.VERTEX_SHADER, GL_VERTEX_SHADER)
        fragment_shader = shaders.compileShader(self.FRAGMENT_SHADER, GL_FRAGMENT_SHADER)

        # Create program but don't validate yet
        self.shader_program = glCreateProgram()
        glAttachShader(self.shader_program, vertex_shader)
        glAttachShader(self.shader_program, fragment_shader)
        glLinkProgram(self.shader_program)

        # Check link status
        link_status = glGetProgramiv(self.shader_program, GL_LINK_STATUS)
        if not link_status:
            info_log = glGetProgramInfoLog(self.shader_program)
            raise RuntimeError(f"Shader program link failed: {info_log.decode('utf-8')}")

        # Delete shader objects (no longer needed after linking)
        glDeleteShader(vertex_shader)
        glDeleteShader(fragment_shader)

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

        # Create region texture (for region map rendering)
        self.region_tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.region_tex)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_R8, self.render_width, self.render_height, 0,
                     GL_RED, GL_UNSIGNED_BYTE, None)

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

        # Check framebuffer status
        fbo_status = glCheckFramebufferStatus(GL_FRAMEBUFFER)
        if fbo_status != GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError(f"Framebuffer is not complete: {fbo_status}")

        # NOW we can validate the shader program (after FBO is created)
        glValidateProgram(self.shader_program)
        validation_status = glGetProgramiv(self.shader_program, GL_VALIDATE_STATUS)
        if not validation_status:
            info_log = glGetProgramInfoLog(self.shader_program)
            print(f"Warning: Shader validation returned status {validation_status}: {info_log.decode('utf-8')}")
            # Note: We continue anyway as validation can fail in some contexts but still work

        # Unbind framebuffer
        glBindFramebuffer(GL_FRAMEBUFFER, 0)

        print("Qt OpenGL renderer initialized successfully")

    def resizeGL(self, w, h):
        """Handle window resize"""
        glViewport(0, 0, w, h)

    def paintGL(self):
        """Render the scene (offscreen only)"""
        if not OPENGL_AVAILABLE or self.shader_program is None:
            return

        # Check if FBO is valid
        if self.fbo is None:
            print("Error: FBO not initialized")
            return

        # Bind framebuffer for offscreen rendering
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)

        # Verify framebuffer is complete
        if glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE:
            print("Error: Framebuffer not complete in paintGL")
            glBindFramebuffer(GL_FRAMEBUFFER, 0)
            return

        # Set viewport to render resolution
        glViewport(0, 0, self.render_width, self.render_height)

        # Clear to black
        glClear(GL_COLOR_BUFFER_BIT)

        # Use shader program
        glUseProgram(self.shader_program)

        # Update audio texture
        # NOTE: audio_data is (4, width) C-contiguous, which matches OpenGL row-major layout
        # Row 0 = Channel 0, Row 1 = Channel 1, etc. - NO transpose needed!
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.audio_tex)
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, self.render_width, 4,
                       GL_RED, GL_FLOAT, self.audio_data)

        # Update region texture if available
        if self.region_map_data is not None:
            glActiveTexture(GL_TEXTURE1)
            glBindTexture(GL_TEXTURE_2D, self.region_tex)
            glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, self.render_width, self.render_height,
                           GL_RED, GL_UNSIGNED_BYTE, self.region_map_data)

        # Set uniforms
        glUniform1i(glGetUniformLocation(self.shader_program, b"audio_tex"), 0)
        glUniform1i(glGetUniformLocation(self.shader_program, b"region_tex"), 1)
        glUniform4fv(glGetUniformLocation(self.shader_program, b"frequencies"),
                    1, self.frequencies)
        glUniform4fv(glGetUniformLocation(self.shader_program, b"intensities"),
                    1, self.intensities)
        glUniform4fv(glGetUniformLocation(self.shader_program, b"curves"),
                    1, self.curves)
        glUniform4fv(glGetUniformLocation(self.shader_program, b"angles"),
                    1, self.angles)
        glUniform4fv(glGetUniformLocation(self.shader_program, b"enabled_mask"),
                    1, self.enabled_mask)
        glUniform1i(glGetUniformLocation(self.shader_program, b"blend_mode"),
                   self.blend_mode)
        glUniform1f(glGetUniformLocation(self.shader_program, b"brightness"),
                   self.brightness)
        glUniform1i(glGetUniformLocation(self.shader_program, b"use_region_map"),
                   self.use_region_map)

        # Bind textures and draw
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.audio_tex)
        glActiveTexture(GL_TEXTURE1)
        glBindTexture(GL_TEXTURE_2D, self.region_tex)
        glBindVertexArray(self.vao)
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)

        # Read back pixels from FBO
        pixels = glReadPixels(0, 0, self.render_width, self.render_height,
                             GL_RGB, GL_UNSIGNED_BYTE)
        self.rendered_image = np.frombuffer(pixels, dtype=np.uint8).reshape(
            (self.render_height, self.render_width, 3))
        self.rendered_image = np.flipud(self.rendered_image)  # Flip Y axis

        # Unbind FBO (return to default framebuffer)
        glBindFramebuffer(GL_FRAMEBUFFER, 0)

        # Note: We don't render to screen since this is an offscreen renderer

    def render(self, channels_data: List[dict], region_map: np.ndarray = None) -> np.ndarray:
        """
        Render all channels (THREAD-SAFE)

        This method can be called from any thread. It will marshal the rendering
        to the GUI thread and block until the rendering is complete.

        Args:
            channels_data: List of channel data
            region_map: Optional region map (height, width), uint8, values 0-3 for regions

        Returns:
            RGB image (height, width, 3), uint8
        """
        # Check if we're already in the GUI thread
        if threading.current_thread() == self.gui_thread:
            # Direct rendering in GUI thread
            return self._render_direct(channels_data, region_map)
        else:
            # Marshal to GUI thread via signal
            return self._render_via_signal(channels_data, region_map)

    def _render_direct(self, channels_data: List[dict], region_map: np.ndarray = None) -> np.ndarray:
        """
        Render directly in GUI thread (internal use only)
        """
        # Prepare audio data
        self.audio_data.fill(0.0)
        self.enabled_mask.fill(0.0)
        self.curves.fill(0.0)
        self.angles.fill(0.0)

        # Handle region map
        if region_map is not None and region_map.shape == (self.render_height, self.render_width):
            self.region_map_data = region_map.astype(np.uint8)
            self.use_region_map = 1
        else:
            self.region_map_data = None
            self.use_region_map = 0

        # Debug: 每 100 幀輸出一次
        if not hasattr(self, '_debug_frame_count'):
            self._debug_frame_count = 0
        self._debug_frame_count += 1

        if self._debug_frame_count % 100 == 0:
            print(f"[Qt OpenGL] Rendering frame {self._debug_frame_count} (thread: {threading.current_thread().name})")
            for i in range(min(4, len(channels_data))):
                ch_data = channels_data[i]
                audio = ch_data.get('audio', np.array([]))
                audio_min = float(np.min(audio)) if len(audio) > 0 else 0.0
                audio_max = float(np.max(audio)) if len(audio) > 0 else 0.0
                print(f"  Ch{i}: enabled={ch_data.get('enabled', False)}, "
                      f"audio_len={len(audio)}, "
                      f"audio_range=[{audio_min:.2f}, {audio_max:.2f}], "
                      f"intensity={ch_data.get('intensity', 0.0):.3f}, "
                      f"freq={ch_data.get('frequency', 0.0):.1f}Hz, "
                      f"curve={ch_data.get('curve', 0.0):.3f}, "
                      f"angle={ch_data.get('angle', 0.0):.1f}")

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
            self.curves[i] = ch_data.get('curve', 0.0)
            self.angles[i] = ch_data.get('angle', 0.0)
            self.enabled_mask[i] = 1.0

        # Trigger paintGL (OpenGL calls in GUI thread)
        self.update()
        self.makeCurrent()
        self.paintGL()
        self.doneCurrent()

        # Return rendered image (thread-safe copy)
        with QMutexLocker(self.rendered_image_mutex):
            if self.rendered_image is not None:
                return self.rendered_image.copy()
            else:
                return np.zeros((self.render_height, self.render_width, 3), dtype=np.uint8)

    def _render_via_signal(self, channels_data: List[dict], region_map: np.ndarray = None) -> np.ndarray:
        """
        Render via signal/slot to GUI thread (cross-thread safe)
        """
        # Store channels data for GUI thread to process
        with QMutexLocker(self.channels_data_mutex):
            # Deep copy to avoid race conditions
            self.pending_channels_data = [
                {
                    'enabled': ch.get('enabled', False),
                    'audio': ch.get('audio', np.array([])).copy() if 'audio' in ch else np.array([]),
                    'frequency': ch.get('frequency', 440.0),
                    'intensity': ch.get('intensity', 1.0),
                    'curve': ch.get('curve', 0.0),
                    'angle': ch.get('angle', 0.0),
                }
                for ch in channels_data
            ]
            # Store region map (deep copy if present)
            self.pending_region_map = region_map.copy() if region_map is not None else None

        # Reset completion event
        self.render_complete_event.clear()

        # Emit signal to GUI thread (queued connection)
        self.render_requested.emit()

        # Wait for rendering to complete (with timeout to avoid deadlock)
        if not self.render_complete_event.wait(timeout=1.0):
            print("Warning: Qt OpenGL render timeout (1s)")
            return np.zeros((self.render_height, self.render_width, 3), dtype=np.uint8)

        # Return rendered image
        with QMutexLocker(self.rendered_image_mutex):
            if self.rendered_image is not None:
                return self.rendered_image.copy()
            else:
                return np.zeros((self.render_height, self.render_width, 3), dtype=np.uint8)

    def _do_render_in_gui_thread(self):
        """
        Slot called in GUI thread to perform actual rendering
        """
        # Get pending channels data and region map
        with QMutexLocker(self.channels_data_mutex):
            if self.pending_channels_data is None:
                self.render_complete_event.set()
                return
            channels_data = self.pending_channels_data
            region_map = self.pending_region_map
            self.pending_channels_data = None
            self.pending_region_map = None

        # Perform rendering (we're now in GUI thread)
        result = self._render_direct(channels_data, region_map)

        # Store result with mutex
        with QMutexLocker(self.rendered_image_mutex):
            self.rendered_image = result

        # Signal completion
        self.render_complete_event.set()

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
