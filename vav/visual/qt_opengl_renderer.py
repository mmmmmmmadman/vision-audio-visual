"""
Qt-native OpenGL Renderer using QOpenGLWidget
Optimized for PyQt6 on macOS with custom shaders
"""

import numpy as np
from typing import List
import threading
import cv2
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

    # Overlay vertex shader (2D pixel coordinates -> NDC)
    OVERLAY_VERTEX_SHADER = """
    #version 330 core
    layout(location = 0) in vec2 position;  // Pixel coordinates
    uniform mat4 projection;  // Orthographic projection matrix

    void main() {
        gl_Position = projection * vec4(position, 0.0, 1.0);
    }
    """

    # Overlay fragment shader (solid color with alpha)
    OVERLAY_FRAGMENT_SHADER = """
    #version 330 core
    uniform vec4 color;  // RGBA color
    out vec4 fragColor;

    void main() {
        fragColor = color;
    }
    """

    # Fragment shader with curve, angle, region map support
    FRAGMENT_SHADER = """
    #version 330 core
    uniform sampler2D audio_tex;
    uniform sampler2D region_tex;
    uniform sampler2D camera_tex;  // Camera input for GPU region calculation
    uniform sampler2D camera_blend_tex;  // Camera/SD frame for final blending
    uniform vec4 frequencies;
    uniform vec4 intensities;
    uniform vec4 curves;
    uniform vec4 angles;
    uniform vec4 ratios;
    uniform vec4 enabled_mask;
    uniform float blend_mode;  // 0.0-1.0 continuous blend between modes
    uniform float brightness;
    uniform int use_region_map;
    uniform int use_gpu_region;  // 0=use region_tex, 1=calculate in shader
    uniform float base_hue;
    uniform vec3 envelope_offsets;  // env1-3 values (0.0-1.0)
    uniform float camera_mix;  // 0.0-1.0, blend strength for camera/SD input
    uniform float color_scheme;  // 0.0-1.0 continuous blend between color schemes

    in vec2 v_texcoord;
    out vec4 fragColor;

    #define PI 3.14159265359

    vec3 hsv2rgb(vec3 c) {
        vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
        vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
        return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
    }

    vec3 getChannelColor(int ch) {
        float hue = base_hue;
        float saturation = 1.0;
        float value = 1.0;

        // ENV1 控制整體色相旋轉 (0-360°)
        float hue_rotation = envelope_offsets.x;

        // 計算三種方案的顏色
        vec3 scheme1_hue, scheme2_hue, scheme3_hue;

        // 方案1: 90度四色系統
        if (ch == 0) {
            scheme1_hue = vec3(fract(base_hue + hue_rotation), 1.0, 1.0);
        } else if (ch == 1) {
            scheme1_hue = vec3(fract(base_hue + hue_rotation + 0.25), 0.5 + 0.5 * envelope_offsets.y, 1.0);
        } else if (ch == 2) {
            scheme1_hue = vec3(fract(base_hue + hue_rotation + 0.5), 0.5 + 0.5 * envelope_offsets.z, 1.0);
        } else {
            scheme1_hue = vec3(fract(base_hue + hue_rotation + 0.75), 1.0, 1.0);
        }

        // 方案2: 三色+對比
        if (ch == 0) {
            scheme2_hue = vec3(fract(base_hue + hue_rotation), 1.0, 1.0);
        } else if (ch == 1) {
            scheme2_hue = vec3(fract(base_hue + hue_rotation + 0.333), 0.5 + 0.5 * envelope_offsets.y, 1.0);
        } else if (ch == 2) {
            scheme2_hue = vec3(fract(base_hue + hue_rotation + 0.667), 0.5 + 0.5 * envelope_offsets.z, 1.0);
        } else {
            scheme2_hue = vec3(fract(base_hue + hue_rotation + 0.5), 1.0, 1.0);
        }

        // 方案3: 三色+中間色
        if (ch == 0) {
            scheme3_hue = vec3(fract(base_hue + hue_rotation), 1.0, 1.0);
        } else if (ch == 1) {
            scheme3_hue = vec3(fract(base_hue + hue_rotation + 0.333), 0.5 + 0.5 * envelope_offsets.y, 1.0);
        } else if (ch == 2) {
            scheme3_hue = vec3(fract(base_hue + hue_rotation + 0.667), 0.5 + 0.5 * envelope_offsets.z, 1.0);
        } else {
            scheme3_hue = vec3(fract(base_hue + hue_rotation + 0.167), 1.0, 1.0);
        }

        // 根據 color_scheme 值在三個方案之間混合
        vec3 hsv_result;
        if (color_scheme < 0.5) {
            // 0.0-0.5: 在方案1和方案2之間混合
            float t = color_scheme * 2.0;  // 0.0-1.0
            hsv_result = mix(scheme1_hue, scheme2_hue, t);
        } else {
            // 0.5-1.0: 在方案2和方案3之間混合
            float t = (color_scheme - 0.5) * 2.0;  // 0.0-1.0
            hsv_result = mix(scheme2_hue, scheme3_hue, t);
        }

        return hsv2rgb(hsv_result);
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

    vec4 blendColors(vec4 c1, vec4 c2, float mode) {
        // 計算四種混合模式的結果
        vec3 add_result = min(vec3(1.0), c1.rgb + c2.rgb);

        vec3 screen_result = vec3(1.0) - (vec3(1.0) - c1.rgb) * (vec3(1.0) - c2.rgb);

        vec3 diff_result = abs(c1.rgb - c2.rgb);

        vec3 dodge_result = vec3(0.0);
        for (int i = 0; i < 3; i++) {
            if (c2[i] >= 0.999) {
                dodge_result[i] = 1.0;
            } else if (c1[i] <= 0.001) {
                dodge_result[i] = 0.0;
            } else {
                dodge_result[i] = min(1.0, c1[i] / (1.0 - c2[i]));
            }
        }

        // 根據 mode 值在四種模式之間混合
        // 0.0-0.33: Add -> Screen
        // 0.33-0.66: Screen -> Difference
        // 0.66-1.0: Difference -> Dodge
        vec3 result;
        if (mode < 0.33) {
            float t = mode / 0.33;
            result = mix(add_result, screen_result, t);
        } else if (mode < 0.66) {
            float t = (mode - 0.33) / 0.33;
            result = mix(screen_result, diff_result, t);
        } else {
            float t = (mode - 0.66) / 0.34;
            result = mix(diff_result, dodge_result, t);
        }

        return vec4(result, max(c1.a, c2.a));
    }

    void main() {
        // Get region ID
        int currentRegion = -1;
        if (use_region_map > 0) {
            if (use_gpu_region > 0) {
                // GPU-based region calculation from camera texture
                vec3 cameraColor = texture(camera_tex, vec2(v_texcoord.x, 1.0 - v_texcoord.y)).rgb;
                float brightness_val = dot(cameraColor, vec3(0.299, 0.587, 0.114));  // RGB to grayscale

                // Brightness-based region (4 levels)
                if (brightness_val < 0.25) {
                    currentRegion = 0;  // CH1: very dark
                } else if (brightness_val < 0.5) {
                    currentRegion = 1;  // CH2: medium dark
                } else if (brightness_val < 0.75) {
                    currentRegion = 2;  // CH3: medium bright
                } else {
                    currentRegion = 3;  // CH4: very bright
                }
            } else {
                // CPU-based region map from texture
                float regionVal = texture(region_tex, vec2(v_texcoord.x, 1.0 - v_texcoord.y)).r;
                currentRegion = int(regionVal * 255.0);
            }
        }

        // Render and blend all channels
        vec4 result = vec4(0.0);
        bool firstChannel = true;

        for (int ch = 0; ch < 4; ch++) {
            if (enabled_mask[ch] < 0.5) continue;

            // Apply region filtering: skip channels not in this region
            if (use_region_map > 0 && ch != currentRegion) {
                continue;  // Skip this channel entirely, don't blend with black
            }

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

                // Don't skip - let texture wrapping handle out-of-bounds
                // (Needed for ratio > 1 to work correctly with rotation)
            }

            // Apply ratio (stripe density control)
            float ratio = ratios[ch];
            float x_sample = uv.x * ratio;

            // Apply curve (Y-based X-sampling offset)
            if (curve > 0.001) {
                float y_from_center = (uv.y - 0.5) * 2.0;
                // Use unscaled uv.x for bend shape to keep curve stable
                float bend_shape = sin(uv.x * PI);
                float bend_amount = y_from_center * bend_shape * curve * 2.0;
                x_sample = x_sample + bend_amount;
            }

            // Texture wraps automatically (GL_REPEAT)
            float waveValue = texture(audio_tex, vec2(x_sample, float(ch) / 4.0)).r;
            // waveValue is in ±10V range, only use positive values (0-10V maps to 0.0-1.0)
            float normalized = clamp(waveValue * 0.1 * intensities[ch], 0.0, 1.0);

            // Apply minimum brightness of 10% when voltage is low
            float displayValue = max(normalized, 0.1);

            vec3 rgb = getChannelColor(ch);
            vec4 channelColor = vec4(rgb * displayValue, displayValue);

            // Blend channels together
            if (channelColor.a > 0.001) {
                if (firstChannel) {
                    result = channelColor;
                    firstChannel = false;
                } else {
                    result = blendColors(result, channelColor, blend_mode);
                }
            }
        }

        // GPU Blend: Blend with camera/SD input if camera_mix > 0
        // This is ESSENTIAL for region map mode where each pixel only has 1 channel
        if (camera_mix > 0.001) {
            // Sample camera blend texture (flip Y to match OpenCV coordinate system)
            vec3 camera_color = texture(camera_blend_tex, vec2(v_texcoord.x, 1.0 - v_texcoord.y)).rgb;

            // Create camera "channel" - scale color by camera_mix to control intensity
            vec4 cameraChannel = vec4(camera_color * camera_mix, camera_mix);

            // Blend camera with multiverse result using blend mode
            if (result.a > 0.001) {
                result = blendColors(result, cameraChannel, blend_mode);
            } else {
                // If no multiverse channels, just use camera
                result = cameraChannel;
            }
        }

        // Apply brightness after all blending
        result.rgb *= brightness;

        fragColor = vec4(result.rgb, 1.0);
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
        self.camera_tex = None  # Camera input for GPU region calculation
        self.camera_blend_tex = None  # Camera/SD frame for final blending
        self.fbo = None
        self.fbo_tex = None

        # Overlay rendering resources
        self.overlay_shader_program = None
        self.overlay_vao = None
        self.overlay_vbo = None
        self.overlay_projection_matrix = None

        # Rendering parameters
        self.blend_mode = 0.0  # 0.0-1.0 continuous blend
        self.brightness = 2.5
        self.base_hue = 0.0  # Base hue in range 0.0-1.0
        self.envelope_offsets = np.array([0.0, 0.0, 0.0], dtype=np.float32)  # env1-3 values (0.0-1.0)
        self.camera_mix = 0.0  # GPU blend strength (0.0-1.0)
        self.color_scheme = 0.5  # 0.0-1.0 continuous (0.5 = Tri+Contrast)

        # Audio data
        self.audio_data = np.zeros((4, width), dtype=np.float32)
        self.frequencies = np.array([440.0, 440.0, 440.0, 440.0], dtype=np.float32)
        self.intensities = np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float32)
        self.curves = np.array([0.0, 0.0, 0.0, 0.0], dtype=np.float32)
        self.angles = np.array([0.0, 0.0, 0.0, 0.0], dtype=np.float32)
        self.ratios = np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float32)
        self.enabled_mask = np.array([0.0, 0.0, 0.0, 0.0], dtype=np.float32)

        # Region map data
        self.region_map_data = None
        self.use_region_map = 0
        self.use_gpu_region = 0  # 0=CPU region (region_tex), 1=GPU region (camera_tex)
        self.camera_frame_data = None  # Camera frame for GPU region calculation
        self.camera_blend_frame_data = None  # Camera/SD frame for GPU blending

        # Overlay data (contours, scan point, rings)
        self.overlay_contour_points = []  # List of (x, y) in pixel coordinates
        self.overlay_scan_point = None  # (x, y) in pixel coordinates
        self.overlay_rings = []  # List of {pos: (x,y), radius: float, color: (r,g,b), alpha: float}

        # Rendered output (thread-safe access)
        self.rendered_image = None
        self.rendered_image_mutex = QMutex()

        # Thread synchronization for render requests
        self.render_complete_event = threading.Event()
        self.pending_channels_data = None
        self.pending_region_map = None
        self.pending_camera_frame = None
        self.pending_use_gpu_region = False
        self.pending_overlay_data = None
        self.pending_blend_frame = None
        self.pending_camera_mix = 0.0
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
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)  # Changed for ratio support
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)  # Changed for ratio support
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

        # Create camera texture (for GPU region calculation)
        self.camera_tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.camera_tex)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, self.render_width, self.render_height, 0,
                     GL_RGB, GL_UNSIGNED_BYTE, None)

        # Create camera blend texture (for final GPU blending with camera/SD input)
        self.camera_blend_tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.camera_blend_tex)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, self.render_width, self.render_height, 0,
                     GL_RGB, GL_UNSIGNED_BYTE, None)

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

        # Compile overlay shaders
        overlay_vertex_shader = shaders.compileShader(self.OVERLAY_VERTEX_SHADER, GL_VERTEX_SHADER)
        overlay_fragment_shader = shaders.compileShader(self.OVERLAY_FRAGMENT_SHADER, GL_FRAGMENT_SHADER)

        self.overlay_shader_program = glCreateProgram()
        glAttachShader(self.overlay_shader_program, overlay_vertex_shader)
        glAttachShader(self.overlay_shader_program, overlay_fragment_shader)
        glLinkProgram(self.overlay_shader_program)

        # Check link status
        link_status = glGetProgramiv(self.overlay_shader_program, GL_LINK_STATUS)
        if not link_status:
            info_log = glGetProgramInfoLog(self.overlay_shader_program)
            raise RuntimeError(f"Overlay shader program link failed: {info_log.decode('utf-8')}")

        glDeleteShader(overlay_vertex_shader)
        glDeleteShader(overlay_fragment_shader)

        # Create overlay VAO and VBO (dynamic buffer for line vertices)
        self.overlay_vao = glGenVertexArrays(1)
        glBindVertexArray(self.overlay_vao)

        self.overlay_vbo = glGenBuffers(1)
        glBindBuffer(GL_ARRAY_BUFFER, self.overlay_vbo)
        # Allocate buffer for max 50000 vertices (for 100% resolution contours)
        glBufferData(GL_ARRAY_BUFFER, 50000 * 2 * 4, None, GL_DYNAMIC_DRAW)  # vec2 * float32

        # Position attribute (location 0)
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 8, ctypes.c_void_p(0))

        glBindVertexArray(0)

        # Create orthographic projection matrix (pixel coordinates to NDC)
        # Screen coordinates: (0,0) = top-left, (width,height) = bottom-right
        # Parameters: left, right, bottom, top, near, far
        self.overlay_projection_matrix = self._create_ortho_matrix(
            0, self.render_width, 0, self.render_height, -1, 1
        )

        # Create PBOs for asynchronous pixel readback
        self.pbo = glGenBuffers(2)
        pbo_size = self.render_width * self.render_height * 3  # RGB
        for i in range(2):
            glBindBuffer(GL_PIXEL_PACK_BUFFER, self.pbo[i])
            glBufferData(GL_PIXEL_PACK_BUFFER, pbo_size, None, GL_STREAM_READ)
        glBindBuffer(GL_PIXEL_PACK_BUFFER, 0)

        self.current_pbo = 0
        self.pbo_ready = [False, False]

        print("Qt OpenGL renderer initialized successfully (with overlay support)")

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

        # Specify draw buffer for FBO
        glDrawBuffer(GL_COLOR_ATTACHMENT0)

        # Verify framebuffer is complete
        if glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE:
            print("Error: Framebuffer not complete in paintGL")
            glBindFramebuffer(GL_FRAMEBUFFER, 0)
            return

        # Set viewport to render resolution
        glViewport(0, 0, self.render_width, self.render_height)

        # Clear to black and reset depth
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        # Render Multiverse
        skip_multiverse = False

        if not skip_multiverse:
            # Use shader program
            glUseProgram(self.shader_program)

            # Update audio texture
            glActiveTexture(GL_TEXTURE0)
            glBindTexture(GL_TEXTURE_2D, self.audio_tex)
            glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, self.render_width, 4,
                           GL_RED, GL_FLOAT, self.audio_data)

            # Update region texture if available (CPU region mode)
            if self.region_map_data is not None:
                glActiveTexture(GL_TEXTURE1)
                glBindTexture(GL_TEXTURE_2D, self.region_tex)
                glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, self.render_width, self.render_height,
                               GL_RED, GL_UNSIGNED_BYTE, self.region_map_data)

            # Update camera texture if available (GPU region mode)
            if self.camera_frame_data is not None:
                glActiveTexture(GL_TEXTURE2)
                glBindTexture(GL_TEXTURE_2D, self.camera_tex)
                glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, self.render_width, self.render_height,
                               GL_RGB, GL_UNSIGNED_BYTE, self.camera_frame_data)

            # Update camera blend texture if available (GPU blend mode)
            if self.camera_blend_frame_data is not None:
                glActiveTexture(GL_TEXTURE3)
                glBindTexture(GL_TEXTURE_2D, self.camera_blend_tex)
                glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, self.render_width, self.render_height,
                               GL_RGB, GL_UNSIGNED_BYTE, self.camera_blend_frame_data)

            # Set uniforms
            glUniform1i(glGetUniformLocation(self.shader_program, b"audio_tex"), 0)
            glUniform1i(glGetUniformLocation(self.shader_program, b"region_tex"), 1)
            glUniform1i(glGetUniformLocation(self.shader_program, b"camera_tex"), 2)
            glUniform1i(glGetUniformLocation(self.shader_program, b"camera_blend_tex"), 3)
            glUniform4fv(glGetUniformLocation(self.shader_program, b"frequencies"),
                        1, self.frequencies)
            glUniform4fv(glGetUniformLocation(self.shader_program, b"intensities"),
                        1, self.intensities)
            glUniform4fv(glGetUniformLocation(self.shader_program, b"curves"),
                        1, self.curves)
            glUniform4fv(glGetUniformLocation(self.shader_program, b"angles"),
                        1, self.angles)
            glUniform4fv(glGetUniformLocation(self.shader_program, b"ratios"),
                        1, self.ratios)
            glUniform4fv(glGetUniformLocation(self.shader_program, b"enabled_mask"),
                        1, self.enabled_mask)
            glUniform1f(glGetUniformLocation(self.shader_program, b"blend_mode"),
                       self.blend_mode)
            glUniform1f(glGetUniformLocation(self.shader_program, b"brightness"),
                       self.brightness)
            glUniform1i(glGetUniformLocation(self.shader_program, b"use_region_map"),
                       self.use_region_map)
            glUniform1i(glGetUniformLocation(self.shader_program, b"use_gpu_region"),
                       self.use_gpu_region)
            glUniform1f(glGetUniformLocation(self.shader_program, b"base_hue"),
                       self.base_hue)
            glUniform3f(glGetUniformLocation(self.shader_program, b"envelope_offsets"),
                       self.envelope_offsets[0], self.envelope_offsets[1], self.envelope_offsets[2])
            glUniform1f(glGetUniformLocation(self.shader_program, b"camera_mix"),
                       self.camera_mix)
            glUniform1f(glGetUniformLocation(self.shader_program, b"color_scheme"),
                       self.color_scheme)

            # Bind textures and draw Multiverse
            glActiveTexture(GL_TEXTURE0)
            glBindTexture(GL_TEXTURE_2D, self.audio_tex)
            glActiveTexture(GL_TEXTURE1)
            glBindTexture(GL_TEXTURE_2D, self.region_tex)
            glBindVertexArray(self.vao)
            glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)

            # Reset OpenGL state for overlay
            glBindVertexArray(0)
            glUseProgram(0)

            # Unbind all textures
            glActiveTexture(GL_TEXTURE0)
            glBindTexture(GL_TEXTURE_2D, 0)
            glActiveTexture(GL_TEXTURE1)
            glBindTexture(GL_TEXTURE_2D, 0)
            glActiveTexture(GL_TEXTURE2)
            glBindTexture(GL_TEXTURE_2D, 0)
            glActiveTexture(GL_TEXTURE3)
            glBindTexture(GL_TEXTURE_2D, 0)
            glActiveTexture(GL_TEXTURE0)

        # Disable blending for overlay
        glDisable(GL_BLEND)

        # Draw overlay on top (contours, scan point, rings) - GPU rendering
        self._draw_overlay_gpu()

        # Verify FBO is still bound before reading
        current_fbo_before_read = glGetIntegerv(GL_FRAMEBUFFER_BINDING)
        if current_fbo_before_read != self.fbo:
            print(f"[ERROR] FBO changed before glReadPixels! Expected {self.fbo}, got {current_fbo_before_read}")

        # Specify read buffer for FBO
        glReadBuffer(GL_COLOR_ATTACHMENT0)

        # PBO asynchronous readback
        # 1. Start async read to current PBO
        glBindBuffer(GL_PIXEL_PACK_BUFFER, self.pbo[self.current_pbo])
        glReadPixels(0, 0, self.render_width, self.render_height,
                    GL_RGB, GL_UNSIGNED_BYTE, 0)  # offset=0 writes to PBO
        self.pbo_ready[self.current_pbo] = True

        # 2. Read from previous PBO if ready
        prev_pbo = 1 - self.current_pbo
        if self.pbo_ready[prev_pbo]:
            glBindBuffer(GL_PIXEL_PACK_BUFFER, self.pbo[prev_pbo])
            data_ptr = glMapBuffer(GL_PIXEL_PACK_BUFFER, GL_READ_ONLY)
            if data_ptr:
                # Copy data from PBO
                buffer_size = self.render_width * self.render_height * 3
                pixels = ctypes.string_at(data_ptr, buffer_size)
                self.rendered_image = np.frombuffer(pixels, dtype=np.uint8).reshape(
                    (self.render_height, self.render_width, 3)).copy()
                self.rendered_image = np.flipud(self.rendered_image)
                glUnmapBuffer(GL_PIXEL_PACK_BUFFER)
            self.pbo_ready[prev_pbo] = False

        glBindBuffer(GL_PIXEL_PACK_BUFFER, 0)

        # 3. Switch PBO
        self.current_pbo = 1 - self.current_pbo

        # Unbind FBO (return to default framebuffer)
        glBindFramebuffer(GL_FRAMEBUFFER, 0)

        # Note: We don't render to screen since this is an offscreen renderer

    def render(self, channels_data: List[dict], region_map: np.ndarray = None, camera_frame: np.ndarray = None, use_gpu_region: bool = False,
               overlay_data: dict = None, blend_frame: np.ndarray = None, camera_mix: float = 0.0) -> np.ndarray:
        """
        Render all channels (THREAD-SAFE)

        This method can be called from any thread. It will marshal the rendering
        to the GUI thread and block until the rendering is complete.

        Args:
            channels_data: List of channel data
            region_map: Optional region map (height, width), uint8, values 0-3 for regions (CPU mode)
            camera_frame: Optional camera frame (height, width, 3), uint8, BGR (GPU region mode)
            use_gpu_region: If True, use GPU to calculate regions from camera_frame
            overlay_data: Optional dict with 'contour_points', 'scan_point', 'rings' for GPU overlay
            blend_frame: Optional camera/SD frame (height, width, 3), uint8, BGR for GPU blending
            camera_mix: Blend strength (0.0-1.0) for GPU blending

        Returns:
            RGB image (height, width, 3), uint8
        """
        # Check if we're already in the GUI thread
        if threading.current_thread() == self.gui_thread:
            # Direct rendering in GUI thread
            return self._render_direct(channels_data, region_map, camera_frame, use_gpu_region, overlay_data, blend_frame, camera_mix)
        else:
            # Marshal to GUI thread via signal
            return self._render_via_signal(channels_data, region_map, camera_frame, use_gpu_region, overlay_data, blend_frame, camera_mix)

    def _render_direct(self, channels_data: List[dict], region_map: np.ndarray = None, camera_frame: np.ndarray = None, use_gpu_region: bool = False,
                       overlay_data: dict = None, blend_frame: np.ndarray = None, camera_mix: float = 0.0) -> np.ndarray:
        """
        Render directly in GUI thread (internal use only)
        """
        # Prepare audio data
        self.audio_data.fill(0.0)
        self.enabled_mask.fill(0.0)
        self.curves.fill(0.0)
        self.angles.fill(0.0)
        self.ratios.fill(1.0)

        # Handle overlay data
        if overlay_data is not None:
            self.overlay_contour_points = overlay_data.get('contour_points', [])
            self.overlay_scan_point = overlay_data.get('scan_point', None)
            self.overlay_rings = overlay_data.get('rings', [])

            # DEBUG overlay data
            if not hasattr(self, '_overlay_debug_counter'):
                self._overlay_debug_counter = 0
            self._overlay_debug_counter += 1
            if self._overlay_debug_counter == 100:
                print(f"[Overlay DEBUG] contour_points: {len(self.overlay_contour_points)}, scan_point: {self.overlay_scan_point}, rings: {len(self.overlay_rings)}")
                self._overlay_debug_counter = 0
        else:
            self.overlay_contour_points = []
            self.overlay_scan_point = None
            self.overlay_rings = []

        # Handle GPU blend frame (camera/SD input for blending)
        if blend_frame is not None and camera_mix > 0.0:
            # Resize blend_frame to match renderer output if needed
            if blend_frame.shape[:2] != (self.render_height, self.render_width):
                blend_frame_resized = cv2.resize(blend_frame, (self.render_width, self.render_height))
            else:
                blend_frame_resized = blend_frame
            # Convert BGR to RGB for OpenGL
            self.camera_blend_frame_data = cv2.cvtColor(blend_frame_resized, cv2.COLOR_BGR2RGB).astype(np.uint8)
            self.camera_mix = camera_mix
        else:
            self.camera_blend_frame_data = None
            self.camera_mix = 0.0

        # Handle region calculation mode
        if use_gpu_region and camera_frame is not None:
            # GPU region mode: upload camera frame
            if camera_frame.shape[:2] == (self.render_height, self.render_width):
                # Convert BGR to RGB for OpenGL
                self.camera_frame_data = cv2.cvtColor(camera_frame, cv2.COLOR_BGR2RGB).astype(np.uint8)
                self.use_region_map = 1
                self.use_gpu_region = 1
                self.region_map_data = None
            else:
                # Fallback if size mismatch
                self.use_region_map = 0
                self.use_gpu_region = 0
        elif region_map is not None and region_map.shape == (self.render_height, self.render_width):
            # CPU region mode: use pre-calculated region map
            self.region_map_data = region_map.astype(np.uint8)
            self.use_region_map = 1
            self.use_gpu_region = 0
            self.camera_frame_data = None
        else:
            # No region rendering
            self.region_map_data = None
            self.camera_frame_data = None
            self.use_region_map = 0
            self.use_gpu_region = 0

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

            # Resample to width and scale to ±10V range (shader expects ±10V)
            # Use 25x scaling to make audio waveforms more visible
            if len(audio) != self.render_width:
                indices = np.linspace(0, len(audio) - 1, self.render_width).astype(int)
                self.audio_data[i] = audio[indices] * 25.0  # Scale ±1.0 to ±25.0 (clamped in shader)
            else:
                self.audio_data[i] = audio * 25.0  # Scale ±1.0 to ±25.0 (clamped in shader)

            self.frequencies[i] = ch_data.get('frequency', 440.0)
            self.intensities[i] = ch_data.get('intensity', 1.0)
            self.curves[i] = ch_data.get('curve', 0.0)
            self.angles[i] = ch_data.get('angle', 0.0)
            self.ratios[i] = ch_data.get('ratio', 1.0)
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

    def _render_via_signal(self, channels_data: List[dict], region_map: np.ndarray = None, camera_frame: np.ndarray = None, use_gpu_region: bool = False,
                           overlay_data: dict = None, blend_frame: np.ndarray = None, camera_mix: float = 0.0) -> np.ndarray:
        """
        Render via signal/slot to GUI thread (cross-thread safe)
        NON-BLOCKING: Returns previous frame immediately without waiting
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
                    'ratio': ch.get('ratio', 1.0),
                }
                for ch in channels_data
            ]
            # Store region map (deep copy if present)
            self.pending_region_map = region_map.copy() if region_map is not None else None
            # Store camera frame (deep copy if present)
            self.pending_camera_frame = camera_frame.copy() if camera_frame is not None else None
            self.pending_use_gpu_region = use_gpu_region
            # Store overlay data (deep copy if present)
            if overlay_data is not None:
                self.pending_overlay_data = {
                    'contour_points': list(overlay_data.get('contour_points', [])),
                    'scan_point': overlay_data.get('scan_point', None),
                    'rings': list(overlay_data.get('rings', []))
                }
            else:
                self.pending_overlay_data = None
            # Store blend frame (deep copy if present)
            self.pending_blend_frame = blend_frame.copy() if blend_frame is not None else None
            self.pending_camera_mix = camera_mix

        # Emit signal to GUI thread (queued connection)
        # 不等待完成 讓 GUI thread 在背景處理
        self.render_requested.emit()

        # 立即返回上一幀的渲染結果 (non-blocking)
        # 這樣 vision thread 可以持續運行不被阻塞
        with QMutexLocker(self.rendered_image_mutex):
            if self.rendered_image is not None:
                return self.rendered_image.copy()
            else:
                return np.zeros((self.render_height, self.render_width, 3), dtype=np.uint8)

    def _do_render_in_gui_thread(self):
        """
        Slot called in GUI thread to perform actual rendering
        """
        import time
        t_start = time.perf_counter()

        # Get pending channels data and region map
        t0 = time.perf_counter()
        with QMutexLocker(self.channels_data_mutex):
            if self.pending_channels_data is None:
                self.render_complete_event.set()
                return
            channels_data = self.pending_channels_data
            region_map = self.pending_region_map
            camera_frame = self.pending_camera_frame
            use_gpu_region = self.pending_use_gpu_region
            overlay_data = self.pending_overlay_data
            blend_frame = self.pending_blend_frame
            camera_mix = self.pending_camera_mix
            self.pending_channels_data = None
            self.pending_region_map = None
            self.pending_camera_frame = None
            self.pending_use_gpu_region = False
            self.pending_overlay_data = None
            self.pending_blend_frame = None
            self.pending_camera_mix = 0.0
        t_mutex = (time.perf_counter() - t0) * 1000

        # Perform rendering (we're now in GUI thread)
        t1 = time.perf_counter()
        result = self._render_direct(channels_data, region_map, camera_frame, use_gpu_region, overlay_data, blend_frame, camera_mix)
        t_render = (time.perf_counter() - t1) * 1000

        # Store result with mutex
        t2 = time.perf_counter()
        with QMutexLocker(self.rendered_image_mutex):
            self.rendered_image = result
        t_store = (time.perf_counter() - t2) * 1000

        # Signal completion
        self.render_complete_event.set()

        t_total = (time.perf_counter() - t_start) * 1000

        # Performance logging every 100 frames
        if not hasattr(self, '_perf_frame_count'):
            self._perf_frame_count = 0
        self._perf_frame_count += 1

        if self._perf_frame_count % 100 == 0:
            print(f"[PERF] GUI thread render: total={t_total:.2f}ms (mutex={t_mutex:.2f}ms, render={t_render:.2f}ms, store={t_store:.2f}ms)")

    def set_blend_mode(self, mode: float):
        """Set blend mode (0.0-1.0 continuous)"""
        self.blend_mode = max(0.0, min(1.0, mode))

    def set_base_hue(self, hue: float):
        """Set base hue (0.0-1.0 range)"""
        self.base_hue = max(0.0, min(1.0, hue))

    def set_envelope_offsets(self, env1: float, env2: float, env3: float):
        """Set envelope offsets (0.0-1.0 range for each)"""
        self.envelope_offsets[0] = max(0.0, min(1.0, env1))
        self.envelope_offsets[1] = max(0.0, min(1.0, env2))
        self.envelope_offsets[2] = max(0.0, min(1.0, env3))

    def set_brightness(self, brightness: float):
        """Set brightness (0-4)"""
        self.brightness = max(0.0, min(4.0, brightness))

    def set_color_scheme(self, scheme: float):
        """Set color scheme (0.0-1.0 continuous)"""
        self.color_scheme = max(0.0, min(1.0, scheme))

    def _create_ortho_matrix(self, left, right, bottom, top, near, far):
        """Create orthographic projection matrix (OpenGL column-major)"""
        matrix = np.eye(4, dtype=np.float32)
        matrix[0, 0] = 2.0 / (right - left)
        matrix[1, 1] = 2.0 / (top - bottom)
        matrix[2, 2] = -2.0 / (far - near)
        matrix[3, 0] = -(right + left) / (right - left)
        matrix[3, 1] = -(top + bottom) / (top - bottom)
        matrix[3, 2] = -(far + near) / (far - near)
        return matrix

    def _draw_overlay_gpu(self):
        """Draw overlay elements using modern OpenGL (VBO + shaders)"""
        if not OPENGL_AVAILABLE or self.overlay_shader_program is None:
            return

        # Ensure critical OpenGL states for fragment writing
        glDrawBuffer(GL_COLOR_ATTACHMENT0)
        glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE)

        # DEBUG: Check if function is called and log coordinates
        if not hasattr(self, '_overlay_gpu_call_counter'):
            self._overlay_gpu_call_counter = 0
        self._overlay_gpu_call_counter += 1
        if self._overlay_gpu_call_counter == 100:
            print(f"[GPU Overlay] _draw_overlay_gpu called, contours={len(self.overlay_contour_points)}, scan={self.overlay_scan_point is not None}, rings={len(self.overlay_rings)}")
            if len(self.overlay_contour_points) > 0:
                contour_arr = np.array(self.overlay_contour_points)
                print(f"[GPU Overlay DEBUG] Contour X range: [{contour_arr[:, 0].min():.1f}, {contour_arr[:, 0].max():.1f}], Y range: [{contour_arr[:, 1].min():.1f}, {contour_arr[:, 1].max():.1f}]")
                print(f"[GPU Overlay DEBUG] Render size: {self.render_width}x{self.render_height}")
            if self.overlay_scan_point is not None:
                print(f"[GPU Overlay DEBUG] Scan point: {self.overlay_scan_point}")
            # Check current OpenGL state
            current_vao = glGetIntegerv(GL_VERTEX_ARRAY_BINDING)
            current_program = glGetIntegerv(GL_CURRENT_PROGRAM)
            current_fbo = glGetIntegerv(GL_FRAMEBUFFER_BINDING)
            blend_enabled = glIsEnabled(GL_BLEND)
            depth_enabled = glIsEnabled(GL_DEPTH_TEST)
            print(f"[GPU Overlay DEBUG] GL State before overlay: VAO={current_vao}, Program={current_program}, FBO={current_fbo} (expected={self.fbo}), Blend={blend_enabled}, Depth={depth_enabled}")
            self._overlay_gpu_call_counter = 0

        # Disable blending and depth test - draw overlay directly on top
        glDisable(GL_BLEND)
        glDisable(GL_DEPTH_TEST)

        # DEBUG: Verify FBO is still bound before drawing overlay
        current_fbo_before_draw = glGetIntegerv(GL_FRAMEBUFFER_BINDING)
        if current_fbo_before_draw != self.fbo:
            print(f"[GPU Overlay ERROR] FBO changed! Expected {self.fbo}, got {current_fbo_before_draw}")
            # Re-bind FBO
            glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)

        # Use overlay shader
        glUseProgram(self.overlay_shader_program)

        # Set projection matrix uniform
        proj_loc = glGetUniformLocation(self.overlay_shader_program, b"projection")
        glUniformMatrix4fv(proj_loc, 1, GL_FALSE, self.overlay_projection_matrix.flatten())

        # Bind overlay VAO and explicitly reconfigure attributes
        glBindVertexArray(self.overlay_vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.overlay_vbo)
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 8, ctypes.c_void_p(0))

        # NDC test removed - was interfering with normal projection matrix

        # Draw contour lines (match CPU version: white base + black top)
        # CPU version: white 6px + black 2px (contour_scanner.py:438-445)
        # GPU workaround: Draw multiple offset lines to simulate thickness (macOS limitation: glLineWidth = 1.0)
        if len(self.overlay_contour_points) > 1:
            # Flip Y: screen coords (Y down) -> OpenGL coords (Y up)
            vertices = np.array([
                [x, self.render_height - y] for x, y in self.overlay_contour_points
            ], dtype=np.float32)

            color_loc = glGetUniformLocation(self.overlay_shader_program, b"color")
            glBindBuffer(GL_ARRAY_BUFFER, self.overlay_vbo)

            # Layer 1: White base (4x thickness - simulate 24px)
            glUniform4f(color_loc, 1.0, 1.0, 1.0, 1.0)  # White
            offsets = [
                (0, 0),   # Center
                (-1, 0), (1, 0), (0, -1), (0, 1),  # Cross
                (-2, 0), (2, 0), (0, -2), (0, 2),  # Outer cross
                (-3, 0), (3, 0), (0, -3), (0, 3),  # Outer cross 2
                (-4, 0), (4, 0), (0, -4), (0, 4),  # Outer cross 3
                (-1, -1), (1, -1), (-1, 1), (1, 1),  # Diagonals
                (-2, -2), (2, -2), (-2, 2), (2, 2),  # Diagonals 2
            ]
            for dx, dy in offsets:
                offset_vertices = vertices + np.array([dx, dy], dtype=np.float32)
                glBufferSubData(GL_ARRAY_BUFFER, 0, offset_vertices.nbytes, offset_vertices)
                glDrawArrays(GL_LINE_STRIP, 0, len(offset_vertices))

            # Layer 2: Black top (4x thickness - simulate 8px)
            glUniform4f(color_loc, 0.0, 0.0, 0.0, 1.0)  # Black
            for dx, dy in [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1), (-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, -1), (-1, 1), (1, 1)]:
                offset_vertices = vertices + np.array([dx, dy], dtype=np.float32)
                glBufferSubData(GL_ARRAY_BUFFER, 0, offset_vertices.nbytes, offset_vertices)
                glDrawArrays(GL_LINE_STRIP, 0, len(offset_vertices))

        # Draw scan point cross (match CPU version: 3 layers)
        # CPU version: black 10px + white 6px + pink 3px (contour_scanner.py:447-481)
        if self.overlay_scan_point is not None:
            x, y = self.overlay_scan_point
            y = self.render_height - y  # Flip Y
            cross_size = 20.0

            # Create cross vertices (horizontal + vertical lines)
            cross_vertices = np.array([
                # Horizontal line
                [x - cross_size, y],
                [x + cross_size, y],
                # Vertical line
                [x, y - cross_size],
                [x, y + cross_size],
            ], dtype=np.float32)

            glBindBuffer(GL_ARRAY_BUFFER, self.overlay_vbo)
            color_loc = glGetUniformLocation(self.overlay_shader_program, b"color")

            # 3-layer cross (2x thickness: black 20px + white 12px + pink 6px)
            # Layer 1: Black outer border (simulate 20px)
            glUniform4f(color_loc, 0.0, 0.0, 0.0, 1.0)  # Black
            black_offsets = [
                (0, 0),
                (-1, 0), (1, 0), (0, -1), (0, 1),
                (-2, 0), (2, 0), (0, -2), (0, 2),
                (-3, 0), (3, 0), (0, -3), (0, 3),
                (-1, -1), (1, -1), (-1, 1), (1, 1),
            ]
            for dx, dy in black_offsets:
                offset_vertices = cross_vertices + np.array([dx, dy], dtype=np.float32)
                glBufferSubData(GL_ARRAY_BUFFER, 0, offset_vertices.nbytes, offset_vertices)
                glDrawArrays(GL_LINES, 0, 4)

            # Layer 2: White middle (simulate 12px)
            glUniform4f(color_loc, 1.0, 1.0, 1.0, 1.0)  # White
            white_offsets = [
                (0, 0),
                (-1, 0), (1, 0), (0, -1), (0, 1),
                (-2, 0), (2, 0), (0, -2), (0, 2),
            ]
            for dx, dy in white_offsets:
                offset_vertices = cross_vertices + np.array([dx, dy], dtype=np.float32)
                glBufferSubData(GL_ARRAY_BUFFER, 0, offset_vertices.nbytes, offset_vertices)
                glDrawArrays(GL_LINES, 0, 4)

            # Layer 3: Pink center (simulate 6px)
            glUniform4f(color_loc, 1.0, 0.52, 0.52, 1.0)  # Pink (BGR 133,133,255)
            pink_offsets = [
                (0, 0),
                (-1, 0), (1, 0), (0, -1), (0, 1),
            ]
            for dx, dy in pink_offsets:
                offset_vertices = cross_vertices + np.array([dx, dy], dtype=np.float32)
                glBufferSubData(GL_ARRAY_BUFFER, 0, offset_vertices.nbytes, offset_vertices)
                glDrawArrays(GL_LINES, 0, 4)

        # Draw trigger rings (match CPU version: 3px line with alpha blending)
        # CPU version: cv2.circle with thickness=3 + alpha blending (contour_scanner.py:516-517)
        for ring in self.overlay_rings:
            pos_x, pos_y = ring['pos']
            pos_y = self.render_height - pos_y  # Flip Y
            radius = ring['radius']
            color = ring['color']  # BGR tuple
            alpha = ring['alpha']

            # Convert BGR to RGB
            r, g, b = color[2] / 255.0, color[1] / 255.0, color[0] / 255.0

            color_loc = glGetUniformLocation(self.overlay_shader_program, b"color")
            glBindBuffer(GL_ARRAY_BUFFER, self.overlay_vbo)
            glUniform4f(color_loc, r, g, b, alpha)

            # Generate circle vertices and draw multiple times to simulate 3px thickness
            num_segments = 32
            ring_offsets = [
                0.0,      # Center
                -1.0, 1.0, # Inner/outer offset
            ]
            for r_offset in ring_offsets:
                circle_vertices = []
                adjusted_radius = radius + r_offset
                for i in range(num_segments):
                    theta = 2.0 * np.pi * i / num_segments
                    cx = pos_x + adjusted_radius * np.cos(theta)
                    cy = pos_y + adjusted_radius * np.sin(theta)
                    circle_vertices.append([cx, cy])
                circle_vertices = np.array(circle_vertices, dtype=np.float32)

                # Upload and draw
                glBufferSubData(GL_ARRAY_BUFFER, 0, circle_vertices.nbytes, circle_vertices)
                glDrawArrays(GL_LINE_LOOP, 0, num_segments)

        # Restore state
        glBindVertexArray(0)
        glUseProgram(0)

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
        if self.region_tex is not None:
            glDeleteTextures([self.region_tex])
        if self.camera_tex is not None:
            glDeleteTextures([self.camera_tex])
        if self.camera_blend_tex is not None:
            glDeleteTextures([self.camera_blend_tex])
        if self.fbo_tex is not None:
            glDeleteTextures([self.fbo_tex])
        if self.fbo is not None:
            glDeleteFramebuffers(1, [self.fbo])

        # Clean up overlay resources
        if self.overlay_vao is not None:
            glDeleteVertexArrays(1, [self.overlay_vao])
        if self.overlay_vbo is not None:
            glDeleteBuffers(1, [self.overlay_vbo])

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
