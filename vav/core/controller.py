"""
VAV System Controller - Integrates all subsystems
"""

import numpy as np
from typing import Optional, Callable, List, Dict
import threading
import time
import cv2

from ..vision.camera import AsyncCamera
from ..cv_generator.contour_scanner import ContourScanner
from ..cv_generator.envelope import DecayEnvelope
from ..audio.io import AudioIO
from ..audio.audio_process import AudioProcess
from ..visual.gpu_renderer import GPUMultiverseRenderer
from ..visual.qt_opengl_renderer import QtMultiverseRenderer
from ..visual.content_aware_regions import ContentAwareRegionMapper
from ..visual.sd_img2img_process import SDImg2ImgProcess

# Try Numba JIT renderer (best performance on macOS)
try:
    from ..visual.numba_renderer import NumbaMultiverseRenderer
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False

try:
    import pyvirtualcam
    PYVIRTUALCAM_AVAILABLE = True
except ImportError:
    PYVIRTUALCAM_AVAILABLE = False
    print("Warning: pyvirtualcam not available. Virtual camera output will be disabled.")


class VAVController:
    """Main system controller integrating Vision → CV → Audio → Visual"""

    def __init__(self, config: dict = None):
        self.config = config or {}

        # System state
        self.running = False
        self.vision_thread: Optional[threading.Thread] = None

        # Audio configuration
        self.sample_rate = self.config.get("sample_rate", 48000)
        self.buffer_size = self.config.get("buffer_size", 128)

        # Vision system
        self.camera: Optional[Camera] = None
        self.contour_cv_generator: Optional[ContourScanner] = None
        self.current_frame: Optional[np.ndarray] = None

        # Virtual camera output
        self.virtual_camera = None
        self.virtual_camera_enabled = False

        # Multiverse renderer (Qt OpenGL on macOS, ModernGL on others)
        self.renderer = None
        self.use_multiverse_rendering = False  # Toggle between simple/advanced rendering
        self.using_gpu = False  # Will be set during initialization
        self.renderer_params = {
            'blend_mode': 0,  # 0=Add, 1=Screen, 2=Difference, 3=Color Dodge
            'brightness': 2.5,  # 提高預設亮度讓視覺化更明顯
            'channel_curves': [0.0, 0.0, 0.0, 0.0],  # Curve for 4 channels (0-1)
            'channel_angles': [0.0, 45.0, 90.0, 135.0],  # Rotation angles for 4 channels
            'channel_intensities': [1.0, 1.0, 1.0, 1.0],  # Intensity for 4 channels
            'channel_ratios': [1.0, 1.0, 1.0, 1.0],  # Ratio for 4 channels (stripe density)
            'camera_mix': 0.0,  # 0.0=pure multiverse, 1.0=pure camera, blend in between
        }

        # LFO modulation 參數
        self.base_angles = [0.0, 45.0, 90.0, 135.0]  # 基礎 angle 值
        self.base_curves = [0.0, 0.0, 0.0, 0.0]  # 基礎 curve 值
        self.angle_mod_amounts = [1.0, 1.0, 1.0, 1.0]  # Angle modulation 幅度 (0-1) 預設全滿
        self.curve_mod_amounts = [1.0, 1.0, 1.0, 1.0]  # Curve modulation 幅度 (0-1) 預設全滿
        self.current_angles = [0.0, 45.0, 90.0, 135.0]  # 當前實際 angle 值 (用於 GUI 顯示)
        self.current_curves = [0.0, 0.0, 0.0, 0.0]  # 當前實際 curve 值 (用於 GUI 顯示)
        self.gui_update_counter = 0  # GUI 更新計數器 每 3 幀更新一次標籤

        # Region-based rendering
        self.use_region_rendering = False  # Enable/disable region-based rendering
        self.region_mapper: Optional[ContentAwareRegionMapper] = None
        self.region_mode = 'brightness'  # 'brightness', 'color', 'quadrant', 'edge'

        # CV Overlay display
        self.cv_overlay_enabled = True  # Show CV values on main visual (default enabled)

        # Channel levels for audio mixing (before Ellen Ripley)
        self.channel_levels = [1.0, 1.0, 1.0, 1.0]  # 4 channel levels (0.0-1.0)

        # Audio buffers for Multiverse rendering (circular buffers)
        self.audio_buffer_size = 2400  # 50ms at 48kHz (matches Multiverse.cpp)
        self.audio_buffers = [np.zeros(self.audio_buffer_size, dtype=np.float32) for _ in range(4)]
        self.audio_buffer_lock = threading.Lock()
        self.audio_frequencies = np.array([440.0, 440.0, 440.0, 440.0], dtype=np.float32)
        # No pitch shifting (fixed ratio=1.0, original Multiverse default)

        # CV generators (4 decay envelopes: ENV1-4)
        self.envelopes: List[DecayEnvelope] = []
        self.cv_values = np.zeros(6, dtype=np.float32)  # 6 CV outputs: ENV1-4, SEQ1-2

        # Envelope decay times (shadow copy for visual trigger rings)
        cv_config = self.config.get("cv", {})
        self.env_decay_times = [
            cv_config.get("decay_0_time", 1.0),
            cv_config.get("decay_1_time", 1.0),
            cv_config.get("decay_2_time", 1.0),
            cv_config.get("decay_3_time", 1.0)
        ]

        # Sequential switch tracking for seq1/seq2
        self.seq1_current_channel = 0  # 0-3 for curve control
        self.seq2_current_channel = 0  # 0-3 for angle control

        # Audio system (使用獨立 process)
        self.audio_process: Optional[AudioProcess] = None
        self.audio_io: Optional[AudioIO] = None  # 保留用於裝置選擇

        # Ellen Ripley effect chain (在 audio process 中)
        self.ellen_ripley_enabled = False


        # SD img2img integration
        self.sd_img2img: Optional[SDImg2ImgProcess] = None
        self.sd_enabled = False
        # Visual parameters (from audio analysis)
        self.visual_params = {
            "brightness": 0.5,
            "color_shift": 0.5,
            "bass_intensity": 0.0,
            "mid_intensity": 0.0,
            "high_intensity": 0.0,
            "energy": 0.0,
        }

        # Callbacks for GUI updates
        self.frame_callback: Optional[Callable] = None
        self.cv_callback: Optional[Callable] = None
        self.visual_callback: Optional[Callable] = None
        self.param_callback: Optional[Callable] = None

    def initialize(self) -> bool:
        """Initialize all subsystems"""
        print("Initializing VAV system...")

        # Vision system
        camera_config = self.config.get("camera", {})
        self.camera = AsyncCamera(
            device_id=camera_config.get("device_id", 0),
            width=camera_config.get("width", 1920),
            height=camera_config.get("height", 1080),
            fps=camera_config.get("fps", 30),
        )

        if not self.camera.open():
            print("Failed to open camera")
            return False

        # Initialize Contour CV Generator (replaces cable detection)
        self.contour_cv_generator = ContourScanner()

        # Initialize Multiverse renderer (GPU > Numba JIT > CPU) - TESTING GPU
        import platform
        is_macos = platform.system() == 'Darwin'
        renderer_initialized = False

        # Try Qt OpenGL (Metal) renderer first on macOS for GPU testing
        if is_macos and not renderer_initialized:
            try:
                self.renderer = QtMultiverseRenderer(
                    width=self.camera.width,
                    height=self.camera.height
                )
                self.renderer.set_blend_mode(self.renderer_params['blend_mode'])
                self.renderer.set_brightness(self.renderer_params['brightness'])
                print(f"✓ Qt OpenGL (Metal) Multiverse renderer: {self.camera.width}x{self.camera.height} (GPU accelerated)")
                self.using_gpu = True
                renderer_initialized = True
            except Exception as e:
                print(f"⚠ Qt OpenGL renderer failed: {e}")

        # Try Numba JIT renderer (CPU fallback)
        if NUMBA_AVAILABLE and not renderer_initialized:
            try:
                self.renderer = NumbaMultiverseRenderer(
                    width=self.camera.width,
                    height=self.camera.height
                )
                self.renderer.set_blend_mode(self.renderer_params['blend_mode'])
                self.renderer.set_brightness(self.renderer_params['brightness'])
                print(f"✓ Numba JIT Multiverse renderer: {self.camera.width}x{self.camera.height} (30-60 fps)")
                self.using_gpu = False  # JIT compiled, not GPU
                renderer_initialized = True
            except Exception as e:
                print(f"⚠ Numba renderer failed: {e}")

        # Try GPU renderers on other platforms
        if not renderer_initialized and not is_macos:
            # ModernGL on Linux/Windows
            try:
                self.renderer = GPUMultiverseRenderer(
                    width=self.camera.width,
                    height=self.camera.height
                )
                self.renderer.set_blend_mode(self.renderer_params['blend_mode'])
                self.renderer.set_brightness(self.renderer_params['brightness'])
                print(f"✓ ModernGL Multiverse renderer: {self.camera.width}x{self.camera.height}")
                self.using_gpu = True
                renderer_initialized = True
            except Exception as e:
                print(f"⚠ ModernGL renderer failed: {e}")

        # Final fallback: Pure NumPy CPU renderer
        if not renderer_initialized:
            self.renderer = MultiverseRenderer(
                width=self.camera.width,
                height=self.camera.height
            )
            self.renderer.set_blend_mode(self.renderer_params['blend_mode'])
            self.renderer.set_brightness(self.renderer_params['brightness'])
            print(f"✓ CPU Multiverse renderer: {self.camera.width}x{self.camera.height} (fallback)")
            self.using_gpu = False

        # CV generators (不再在這裡創建，移到 AudioProcess 中)
        # cv_config = self.config.get("cv", {})

        # Audio system (改用 AudioProcess)
        audio_config = self.config.get("audio", {})

        # 僅保留 AudioIO 用於裝置選擇（GUI 需要）
        # Output channels: 2 (audio L/R) + 6 (ENV1-4, SEQ1-2) = 8
        self.audio_io = AudioIO(
            sample_rate=self.sample_rate,
            buffer_size=self.buffer_size,
            input_channels=audio_config.get("input_channels", 4),
            output_channels=audio_config.get("output_channels", 8),
        )

        # Set devices if specified
        if "input_device" in audio_config or "output_device" in audio_config:
            self.audio_io.set_devices(
                input_device=audio_config.get("input_device"),
                output_device=audio_config.get("output_device"),
            )

        # AudioProcess 將在 start() 時創建（需要先選擇裝置）
        self.audio_process = None

        # Initialize region mapper
        self.region_mapper = ContentAwareRegionMapper(
            width=self.camera.width,
            height=self.camera.height
        )

        print("VAV system initialized")
        return True

    def start(self):
        """Start all subsystems"""
        if self.running:
            return

        # Validate audio devices are configured
        if not self.audio_io:
            raise RuntimeError("Audio I/O not initialized")
        if self.audio_io.input_device is None or self.audio_io.output_device is None:
            raise RuntimeError("Audio devices not configured. Please select devices first.")

        print("Starting VAV system...")
        self.running = True

        # Ensure camera is open before starting vision thread
        if self.camera and not self.camera.is_opened:
            print("  Opening camera...")
            if not self.camera.open():
                print("  ERROR: Failed to open camera!")
                self.running = False
                return
            print(f"  Camera opened successfully: device {self.camera.device_id}")

        # 更新 config 中的 channel 數量和裝置 ID（AudioIO 已根據裝置調整）
        self.config["audio"]["input_channels"] = self.audio_io.input_channels
        self.config["audio"]["output_channels"] = self.audio_io.output_channels
        self.config["audio"]["input_device"] = self.audio_io.input_device
        self.config["audio"]["output_device"] = self.audio_io.output_device

        # 創建並啟動 AudioProcess（使用更新後的 config）
        print("  Creating audio process...")
        self.audio_process = AudioProcess(self.config)
        self.audio_process.start()

        # Start vision thread
        self.vision_thread = threading.Thread(target=self._vision_loop, daemon=True)
        self.vision_thread.start()

        print("VAV system started")

    def stop(self):
        """Stop all subsystems"""
        if not self.running:
            return

        print("Stopping VAV system...")
        self.running = False

        # Stop virtual camera
        if self.virtual_camera_enabled:
            self.disable_virtual_camera()

        # Stop audio process
        if self.audio_process:
            self.audio_process.stop()

        # Wait for vision thread
        if self.vision_thread:
            self.vision_thread.join(timeout=2.0)

        # Close camera
        if self.camera:
            self.camera.close()

        print("VAV system stopped")

    def _vision_loop(self):
        """Vision processing loop (runs in separate thread)"""
        frame_time = 1.0 / self.camera.fps
        cv_update_time = 1.0 / 60.0  # Update CV at 60Hz for smooth scope
        last_cv_update = time.time()
        last_frame_time = 0.0

        # Skip frames for performance
        frame_skip = 2  # Process every 2nd frame
        frame_counter = 0

        # Track consecutive failures for error detection
        consecutive_failures = 0
        max_failures = 10

        while self.running:
            start_time = time.time()

            # Check if camera is still open
            if not self.camera.is_opened:
                print("ERROR: Camera closed during vision loop!")
                consecutive_failures += 1
                if consecutive_failures >= max_failures:
                    print(f"ERROR: Camera failed {max_failures} times, stopping vision loop")
                    self.running = False
                    break
                time.sleep(0.1)
                continue

            # Capture frame
            ret, frame = self.camera.read()
            if not ret:
                consecutive_failures += 1
                if consecutive_failures >= max_failures:
                    print(f"ERROR: Failed to read {max_failures} frames, camera may be disconnected")
                    self.running = False
                    break
                continue

            # Reset failure counter on successful read
            consecutive_failures = 0

            frame_counter += 1

            # Skip frames for performance
            if frame_counter % frame_skip != 0:
                # Still update CV, scan and rings even on skipped frames
                current_time = time.time()
                dt_since_last_update = current_time - last_cv_update
                if dt_since_last_update >= cv_update_time:
                    self.contour_cv_generator.update_scan(
                        dt_since_last_update,
                        frame.shape[1],
                        frame.shape[0],
                        envelopes=None,
                        env_decay_times=self.env_decay_times
                    )
                    self._update_cv_values()
                    last_cv_update = current_time

                # Update trigger rings animation
                frame_dt = current_time - last_frame_time if last_frame_time > 0 else 1.0/60.0
                self.contour_cv_generator.update_trigger_rings(frame_dt)
                last_frame_time = current_time
                continue

            self.current_frame = frame

            # Timing for detailed profiling
            t_sd = 0.0
            t_gray = 0.0
            t_contour = 0.0
            t_update_cv = 0.0
            t_rings = 0.0
            t_draw = 0.0
            t_callback = 0.0
            t_vcam = 0.0

            # Determine CV detection source: SD output (if available) or camera
            t0 = time.time()
            cv_input_frame = frame  # Default: use camera frame
            if self.sd_enabled and self.sd_img2img:
                sd_output = self.sd_img2img.get_current_output()
                if sd_output is not None:
                    # Ensure size matches
                    if sd_output.shape[:2] != frame.shape[:2]:
                        cv_input_frame = cv2.resize(sd_output, (frame.shape[1], frame.shape[0]))
                    else:
                        cv_input_frame = sd_output
            t_sd = (time.time() - t0) * 1000

            # Convert to grayscale for edge detection (from SD or camera, not multiverse)
            t0 = time.time()
            gray = cv2.cvtColor(cv_input_frame, cv2.COLOR_BGR2GRAY)
            t_gray = (time.time() - t0) * 1000

            # Detect and extract contour (每10幀執行一次，內部有 early return 優化)
            t0 = time.time()
            if not hasattr(self, '_contour_frame_skip'):
                self._contour_frame_skip = 0
            self._contour_frame_skip = (self._contour_frame_skip + 1) % 10
            if self._contour_frame_skip == 0:
                self.contour_cv_generator.detect_and_extract_contour(gray)
            t_contour = (time.time() - t0) * 1000

            # Update scan progress and CV values
            t0 = time.time()
            current_time = time.time()
            dt_since_last_update = current_time - last_cv_update
            if dt_since_last_update >= cv_update_time:
                self.contour_cv_generator.update_scan(
                    dt_since_last_update,
                    frame.shape[1],
                    frame.shape[0],
                    envelopes=None,  # 不再使用 envelope 物件
                    env_decay_times=self.env_decay_times  # 傳入 decay times 供視覺化
                )
                self._update_cv_values()
                last_cv_update = current_time
            t_update_cv = (time.time() - t0) * 1000

            # Update trigger ring animations (每幀都要更新以保持流暢)
            t0 = time.time()
            frame_dt = current_time - last_frame_time if last_frame_time > 0 else 1.0/60.0
            self.contour_cv_generator.update_trigger_rings(frame_dt)
            last_frame_time = current_time
            t_rings = (time.time() - t0) * 1000

            # Generate visualization frame
            t0 = time.time()
            display_frame = self._draw_visualization(frame)
            t_draw = (time.time() - t0) * 1000

            # Callback for GUI frame update
            t0 = time.time()
            if self.frame_callback:
                self.frame_callback(display_frame)
            t_callback = (time.time() - t0) * 1000

            # Output to virtual camera if enabled
            t0 = time.time()
            if self.virtual_camera_enabled and self.virtual_camera is not None:
                try:
                    # Convert BGR to RGB for virtual camera (fast method)
                    vcam_frame = display_frame[:, :, ::-1]
                    self.virtual_camera.send(vcam_frame)
                except Exception as e:
                    print(f"Virtual camera output error: {e}")
                    # Disable virtual camera on error
                    self.virtual_camera_enabled = False
                    self.virtual_camera = None
            t_vcam = (time.time() - t0) * 1000

            # Maintain frame rate
            elapsed = time.time() - start_time
            elapsed_ms = elapsed * 1000

            # Performance logging every 100 processed frames
            if not hasattr(self, '_vision_perf_counter'):
                self._vision_perf_counter = 0
                self._vision_render_time = 0.0

            self._vision_perf_counter += 1
            if hasattr(self, 't_render'):
                self._vision_render_time = self.t_render  # Store latest render time

            if self._vision_perf_counter % 100 == 0:
                overhead = elapsed_ms - self._vision_render_time
                print(f"[PERF] Vision loop: total={elapsed_ms:.2f}ms (render={self._vision_render_time:.2f}ms, overhead={overhead:.2f}ms), target={frame_time*1000:.2f}ms")
                print(f"[PERF] Breakdown: SD={t_sd:.2f}ms, gray={t_gray:.2f}ms, contour={t_contour:.2f}ms, update_cv={t_update_cv:.2f}ms, rings={t_rings:.2f}ms, draw={t_draw:.2f}ms, callback={t_callback:.2f}ms, vcam={t_vcam:.2f}ms")

            sleep_time = frame_time - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _draw_visualization(self, frame):
        """Draw visualization using ContourCVGenerator overlay"""
        # Process SD img2img first (if enabled) - applies to both simple and multiverse modes
        input_frame = frame  # Default: use camera frame
        if self.sd_enabled and self.sd_img2img:
            # Feed camera frame to SD process
            self.sd_img2img.feed_frame(frame)

            # Get SD processed result
            sd_output = self.sd_img2img.get_current_output()

            # If SD has output, use it as base frame
            if sd_output is not None:
                # Ensure size matches
                if sd_output.shape[:2] != frame.shape[:2]:
                    sd_output = cv2.resize(sd_output, (frame.shape[1], frame.shape[0]))
                input_frame = sd_output

        # Now render based on mode (both modes use input_frame which may be SD output)
        if self.use_multiverse_rendering:
            return self._render_multiverse(input_frame, original_frame=frame)
        else:
            return self._render_simple(input_frame)

    def _render_simple(self, frame):
        """Simple visualization: use ContourScanner overlay on camera/SD frame"""
        # Use ContourScanner's draw_overlay method (frame may be SD output)
        display_frame = self.contour_cv_generator.draw_overlay(frame, self.cv_values)
        return display_frame

    def _render_multiverse(self, frame, original_frame=None):
        """
        Multiverse rendering: frequency-based color mapping with blend modes

        Args:
            frame: Input frame (may be SD output)
            original_frame: Original camera frame (for blend if needed)
        """
        if self.renderer is None:
            return self._render_simple(frame)

        # Timing for detailed profiling
        t_sd_proc = 0.0  # SD processing now done in _draw_visualization
        t_contour_dup = 0.0
        t_prepare_ch = 0.0
        t_region = 0.0
        t_render_call = 0.0
        t_rgb2bgr = 0.0
        t_blend = 0.0
        t_overlay = 0.0
        t_text = 0.0

        # frame is already processed by SD (if enabled) in _draw_visualization
        input_frame = frame
        if original_frame is None:
            original_frame = frame  # Fallback

        # Prepare channel data for Multiverse renderer
        t0 = time.time()
        channels_data = []

        # Read audio from shared memory (無鎖，可能有 tearing 但視覺可接受)
        audio_buffers_copy = []
        if self.audio_process and hasattr(self.audio_process, 'shared_audio_buffers'):
            for i in range(4):
                shared_np = np.frombuffer(self.audio_process.shared_audio_buffers[i], dtype=np.float32)
                audio_buffer = shared_np.copy()

                # TODO: ratio resampling需要實作類似cpp的circular display buffer機制
                # 目前direct copy避免閃爍
                audio_buffers_copy.append(audio_buffer)
        else:
            # Fallback: zeros
            audio_buffers_copy = [np.zeros(self.audio_buffer_size, dtype=np.float32) for _ in range(4)]

        frequencies_copy = self.audio_frequencies.copy()

        # Enable all 4 channels based on user intensity (CV modulation disabled)
        for ch_idx in range(4):
            # Check if user intensity is near zero (disable channel)
            user_intensity = self.renderer_params['channel_intensities'][ch_idx]
            if user_intensity < 0.01:
                channels_data.append({'enabled': False})
            else:
                # 直接使用 user_intensity，不使用 envelope 調變
                intensity = float(user_intensity)

                # DEBUG: 每 500 幀記錄一次 (降低頻率提升效能)
                if hasattr(self, '_multiverse_debug_counter'):
                    self._multiverse_debug_counter += 1
                else:
                    self._multiverse_debug_counter = 0

                if self._multiverse_debug_counter == 500:
                    print(f"[Multiverse DEBUG] Ch{ch_idx}: audio_len={len(audio_buffers_copy[ch_idx])}, audio_range=[{audio_buffers_copy[ch_idx].min():.2f}, {audio_buffers_copy[ch_idx].max():.2f}]")

                channels_data.append({
                    'enabled': True,
                    'audio': audio_buffers_copy[ch_idx],  # Real audio from ES-8!
                    'frequency': float(frequencies_copy[ch_idx]),  # Detected frequency
                    'intensity': intensity,
                    'curve': self.renderer_params['channel_curves'][ch_idx],
                    'angle': self.renderer_params['channel_angles'][ch_idx],
                    'ratio': self.renderer_params['channel_ratios'][ch_idx],
                })
        t_prepare_ch = (time.time() - t0) * 1000

        # Generate region map using input_frame (SD or camera) if region rendering is enabled
        t0 = time.time()
        region_map = None
        use_gpu_region = False  # Default to no region

        if self.use_region_rendering and self.region_mapper:
            # GPU region mode: default for brightness mode with Qt OpenGL renderer
            if self.region_mode == 'brightness' and self.using_gpu:
                # GPU calculates regions from camera frame directly
                use_gpu_region = True
                region_map = None  # No CPU region map needed
            else:
                # CPU region mode: calculate region map on CPU
                use_gpu_region = False
                if self.region_mode == 'brightness':
                    region_map = self.region_mapper.create_brightness_based_regions(input_frame)
                elif self.region_mode == 'color':
                    region_map = self.region_mapper.create_color_based_regions(input_frame)
                elif self.region_mode == 'quadrant':
                    region_map = self.region_mapper.create_quadrant_regions(input_frame)
                elif self.region_mode == 'edge':
                    region_map = self.region_mapper.create_edge_based_regions(input_frame)
        t_region = (time.time() - t0) * 1000

        # Prepare overlay data for GPU rendering (if using Qt OpenGL)
        overlay_data = None
        if self.using_gpu:
            # Extract overlay data from contour_cv_generator
            overlay_data = {
                'contour_points': self.contour_cv_generator.contour_points,
                'scan_point': self.contour_cv_generator.current_scan_pos,
                'rings': self.contour_cv_generator.trigger_rings,
                'roi_center': (self.contour_cv_generator.anchor_x_pct / 100.0,
                              self.contour_cv_generator.anchor_y_pct / 100.0),
                'roi_radius': self.contour_cv_generator.range_pct / 100.0 / 2.0,
                'cv_values': self.cv_values if self.cv_overlay_enabled else None  # CV overlay可選
            }

        # Render using Multiverse engine with GPU blend (33-42ms CPU blend eliminated!)
        t0 = time.time()

        # Blend logic: if input_frame is SD output, show SD directly
        # Otherwise, blend original camera with Multiverse based on camera_mix
        if input_frame is not original_frame:
            # SD is active: show SD output directly (no blend with Multiverse)
            # Multiverse will be rendered, then SD will be blended at 100%
            blend_frame = input_frame
            camera_mix = 1.0  # Full replacement
        else:
            # SD not active: use camera_mix for normal camera blending
            blend_frame = original_frame
            camera_mix = self.renderer_params['camera_mix']

        if use_gpu_region:
            # GPU region: pass camera frame for GPU calculation
            rendered_rgb = self.renderer.render(
                channels_data,
                camera_frame=input_frame,
                use_gpu_region=True,
                overlay_data=overlay_data,
                blend_frame=blend_frame,
                camera_mix=camera_mix
            )
        elif region_map is not None:
            # CPU region: pass pre-calculated region map
            rendered_rgb = self.renderer.render(
                channels_data,
                region_map=region_map,
                overlay_data=overlay_data,
                blend_frame=blend_frame,
                camera_mix=camera_mix
            )
        else:
            # No region rendering
            rendered_rgb = self.renderer.render(
                channels_data,
                overlay_data=overlay_data,
                blend_frame=blend_frame,
                camera_mix=camera_mix
            )
        self.t_render = (time.time() - t0) * 1000  # ms
        t_render_call = self.t_render

        # Convert RGB to BGR for OpenCV
        t0 = time.time()
        rendered_bgr = cv2.cvtColor(rendered_rgb, cv2.COLOR_RGB2BGR)
        t_rgb2bgr = (time.time() - t0) * 1000

        # GPU blend is now done inside the renderer (33-42ms CPU blend saved!)
        t_blend = 0.0  # GPU blend time is included in t_render

        # Draw CV overlays (contour line, scan position, progress bar) - must be on top
        # NOTE: If using GPU renderer, overlays are already drawn in GPU. Skip CPU overlay.
        t0 = time.time()
        if not self.using_gpu:
            # CPU rendering: draw overlays on CPU
            rendered_bgr = self.contour_cv_generator.draw_overlay(rendered_bgr, self.cv_values)
        # GPU rendering: overlays already drawn in GPU, skip this step
        t_overlay = (time.time() - t0) * 1000

        # Add info text
        t0 = time.time()
        height, width = rendered_bgr.shape[:2]
        # Blend mode is now continuous 0.0-1.0
        blend_value = self.renderer_params['blend_mode']
        mode_name = f"Blend:{blend_value:.2f}"
        if NUMBA_AVAILABLE and isinstance(self.renderer, NumbaMultiverseRenderer):
            renderer_type = "Numba JIT"
        elif self.using_gpu and isinstance(self.renderer, QtMultiverseRenderer):
            renderer_type = "Qt OpenGL"
        elif self.using_gpu:
            renderer_type = "GPU"
        else:
            renderer_type = "CPU"
        # Text overlay removed for clean output
        t_text = (time.time() - t0) * 1000

        # Debug log (every 100 frames)
        if not hasattr(self, '_render_multiverse_counter'):
            self._render_multiverse_counter = 0
        self._render_multiverse_counter += 1
        if self._render_multiverse_counter % 100 == 0:
            total = t_sd_proc + t_contour_dup + t_prepare_ch + t_region + t_render_call + t_rgb2bgr + t_blend + t_overlay + t_text
            print(f"[PERF] _render_multiverse breakdown: total={total:.2f}ms")
            print(f"  SD={t_sd_proc:.2f}ms, contour_dup={t_contour_dup:.2f}ms, prepare_ch={t_prepare_ch:.2f}ms, region={t_region:.2f}ms")
            print(f"  render_call={t_render_call:.2f}ms, rgb2bgr={t_rgb2bgr:.2f}ms, blend={t_blend:.2f}ms, overlay={t_overlay:.2f}ms, text={t_text:.2f}ms")

        return rendered_bgr

    def _update_cv_values(self):
        """Update CV values - 發送 SEQ 到 audio process，接收 CV 值用於 GUI"""
        if self.contour_cv_generator and self.audio_process:
            # 發送 SEQ1/SEQ2 和觸發事件到獨立的 audio process (normalized 0-1)
            seq1_normalized = self.contour_cv_generator.seq1_value / 10.0
            seq2_normalized = self.contour_cv_generator.seq2_value / 10.0
            scan_loop_completed = self.contour_cv_generator.get_scan_loop_completed()

            # 讀取觸發事件標記
            env1_trigger = self.contour_cv_generator.env1_triggered
            env2_trigger = self.contour_cv_generator.env2_triggered
            env3_trigger = self.contour_cv_generator.env3_triggered
            env4_trigger = self.contour_cv_generator.env4_triggered

            self.audio_process.send_cv_values(
                seq1_normalized, seq2_normalized, scan_loop_completed,
                env1_trigger, env2_trigger, env3_trigger, env4_trigger
            )

            # 從 audio process 接收 CV 值用於 GUI 顯示
            cv_from_audio = self.audio_process.get_cv_values()
            if cv_from_audio is not None:
                self.cv_values = cv_from_audio
            else:
                # Fallback: audio process 未回傳資料時，至少更新 SEQ1/SEQ2
                # cv_values format: [ENV1, ENV2, ENV3, ENV4, SEQ1, SEQ2]
                self.cv_values[4] = seq1_normalized  # SEQ1
                self.cv_values[5] = seq2_normalized  # SEQ2

            # 更新 LFO modulation
            self._update_lfo_modulation()

            # Trigger CV callback for GUI updates
            if self.cv_callback:
                self.cv_callback(self.cv_values)

    def _update_lfo_modulation(self):
        """更新 LFO modulation 並計算最終 angle/curve 值"""
        if not self.contour_cv_generator:
            return

        # 讀取 8 個 LFO 變種訊號
        lfo_variants = self.contour_cv_generator.get_lfo_variants()

        # 讀取 8 個隨機 modulation amounts (從 ContourScanner)
        random_mod_amounts = self.contour_cv_generator.get_modulation_amounts()

        # 計算 4 個通道的最終 angle 值
        for i in range(4):
            # LFO 變種 0-3 用於 angle
            lfo_signal = lfo_variants[i]  # 範圍約 -1.1 到 +1.1
            # 組合隨機值和 GUI fader 值 (相乘)
            random_amount = random_mod_amounts[i]  # 0.5-1.0 (從 ContourScanner)
            user_amount = self.angle_mod_amounts[i]  # 0-1 (從 GUI fader)
            mod_amount = random_amount * user_amount  # 最終 modulation amount
            base_angle = self.base_angles[i]  # -180 到 +180

            # 計算 modulation 偏移量 (±180 度範圍)
            angle_modulation = lfo_signal * mod_amount * 180.0

            # 最終 angle 值
            final_angle = base_angle + angle_modulation
            # 限制範圍 -180 到 +180
            final_angle = np.clip(final_angle, -180.0, 180.0)

            self.current_angles[i] = final_angle
            self.renderer_params['channel_angles'][i] = final_angle

        # 計算 4 個通道的最終 curve 值
        for i in range(4):
            # LFO 變種 4-7 用於 curve
            lfo_signal = lfo_variants[i + 4]  # 範圍約 -1.1 到 +1.1
            # 組合隨機值和 GUI fader 值 (相乘)
            random_amount = random_mod_amounts[i + 4]  # 0.5-1.0 (從 ContourScanner)
            user_amount = self.curve_mod_amounts[i]  # 0-1 (從 GUI fader)
            mod_amount = random_amount * user_amount  # 最終 modulation amount
            base_curve = self.base_curves[i]  # 0 到 1

            # 將 LFO 訊號轉換到 0-1 範圍
            curve_normalized = (lfo_signal + 1.1) / 2.2  # -1.1~+1.1 -> 0~1

            # 計算 modulation 偏移量
            curve_modulation = curve_normalized * mod_amount

            # 最終 curve 值
            final_curve = base_curve + curve_modulation
            # 限制範圍 0 到 1
            final_curve = np.clip(final_curve, 0.0, 1.0)

            self.current_curves[i] = final_curve
            self.renderer_params['channel_curves'][i] = final_curve

        # 每 3 幀更新一次 GUI 標籤 (降低 GUI 更新頻率)
        self.gui_update_counter += 1
        if self.gui_update_counter >= 3:
            self.gui_update_counter = 0
            if self.param_callback:
                for i in range(4):
                    self.param_callback('angle', i, self.current_angles[i])
                    self.param_callback('curve', i, self.current_curves[i])

    # Contour CV controls (replacing cable analysis)
    def set_anchor_position(self, x_pct: float, y_pct: float):
        """Set anchor position for edge detection (0-100%)"""
        if self.contour_cv_generator:
            self.contour_cv_generator.set_anchor_position(x_pct, y_pct)

    def set_cv_range(self, range_pct: float):
        """Set sampling range from anchor (0-50%)"""
        if self.contour_cv_generator:
            self.contour_cv_generator.set_range(range_pct)

    def set_edge_threshold(self, threshold: int):
        """Set edge detection threshold (0-255)"""
        if self.contour_cv_generator:
            self.contour_cv_generator.set_threshold(threshold)

    def set_cv_smoothing(self, smoothing: int):
        """Set temporal smoothing (0-100)"""
        if self.contour_cv_generator:
            self.contour_cv_generator.set_smoothing(smoothing)

    def set_scan_time(self, scan_time: float):
        """Set contour scan time in seconds (0.1-300s, 5 minutes max)"""
        if self.contour_cv_generator:
            self.contour_cv_generator.set_scan_time(scan_time)

    def set_chaos_ratio(self, ratio: float):
        """Set chaos LFO speed ratio (0.1-1.0, relative to scan time)"""
        if self.contour_cv_generator:
            self.contour_cv_generator.set_chaos_ratio(ratio)

    # Audio callback 已移至 AudioProcess (獨立 process)
    # def _update_audio_buffers(...)
    # def _audio_callback(...)


    # Envelope decay 控制透過 AudioProcess 跨 process 通訊
    def set_envelope_decay(self, env_idx: int, decay_time: float):
        """設定特定 envelope 的 decay time"""
        # Update shadow copy for visual trigger rings
        if 0 <= env_idx < 4:
            self.env_decay_times[env_idx] = decay_time

        # Send to audio process
        if self.audio_process:
            self.audio_process.set_envelope_decay(env_idx, decay_time)

    def set_global_env_decay(self, decay_time: float):
        """設定所有 envelope 的 decay time"""
        # Update shadow copy for visual trigger rings
        self.env_decay_times = [decay_time, decay_time, decay_time, decay_time]

        # Send to audio process
        if self.audio_process:
            for i in range(4):
                self.audio_process.set_envelope_decay(i, decay_time)

    def get_cv_values(self) -> np.ndarray:
        """Get current CV values"""
        return self.cv_values.copy()

    def get_current_frame(self) -> Optional[np.ndarray]:
        """Get current camera frame"""
        return self.current_frame

    def get_visual_params(self) -> dict:
        """Get current visual parameters"""
        return self.visual_params.copy()

    def set_frame_callback(self, callback: Callable):
        """Set callback for frame updates"""
        self.frame_callback = callback

    def set_cv_callback(self, callback: Callable):
        """Set callback for CV updates"""
        self.cv_callback = callback

    def set_visual_callback(self, callback: Callable):
        """Set callback for visual parameter updates"""
        self.visual_callback = callback

    def set_param_callback(self, callback: Callable):
        """Set callback for parameter updates (param_name, channel, value)"""
        self.param_callback = callback

    def enable_virtual_camera(self) -> bool:
        """Enable virtual camera output"""
        if not PYVIRTUALCAM_AVAILABLE:
            print("Error: pyvirtualcam not available")
            return False

        if self.virtual_camera_enabled:
            print("Virtual camera already enabled")
            return True

        if not self.running:
            print("Error: System must be running to enable virtual camera")
            return False

        try:
            # Get camera resolution
            width = self.camera.width
            height = self.camera.height
            fps = self.camera.fps

            print(f"Creating virtual camera: {width}x{height} @ {fps}fps")

            # Create virtual camera
            self.virtual_camera = pyvirtualcam.Camera(
                width=width,
                height=height,
                fps=fps,
                fmt=pyvirtualcam.PixelFormat.RGB
            )

            self.virtual_camera_enabled = True
            print(f"✓ Virtual camera enabled: {self.virtual_camera.device}")
            return True

        except Exception as e:
            print(f"Failed to enable virtual camera: {e}")
            import traceback
            traceback.print_exc()
            self.virtual_camera = None
            self.virtual_camera_enabled = False
            return False

    def disable_virtual_camera(self):
        """Disable virtual camera output"""
        if not self.virtual_camera_enabled:
            return

        try:
            if self.virtual_camera is not None:
                self.virtual_camera.close()
                self.virtual_camera = None

            self.virtual_camera_enabled = False
            print("Virtual camera disabled")

        except Exception as e:
            print(f"Error disabling virtual camera: {e}")

    def enable_multiverse_rendering(self, enabled: bool = True):
        """Enable/disable Multiverse rendering"""
        self.use_multiverse_rendering = enabled
        mode = "Multiverse" if enabled else "Simple"
        print(f"Rendering mode: {mode}")

    def set_renderer_blend_mode(self, mode: float):
        """Set Multiverse blend mode (0.0-1.0 continuous)"""
        mode = np.clip(mode, 0.0, 1.0)
        self.renderer_params['blend_mode'] = mode
        if self.renderer:
            self.renderer.set_blend_mode(mode)

    def set_renderer_brightness(self, brightness: float):
        """Set Multiverse brightness (0-4)"""
        brightness = np.clip(brightness, 0.0, 4.0)
        self.renderer_params['brightness'] = brightness
        if self.renderer:
            self.renderer.set_brightness(brightness)

    def set_renderer_base_hue(self, hue: float):
        """Set Multiverse base hue (0.0-1.0)"""
        hue = np.clip(hue, 0.0, 1.0)
        self.renderer_params['base_hue'] = hue
        if self.renderer:
            self.renderer.set_base_hue(hue)

    def set_color_scheme(self, scheme: float):
        """Set color scheme (0.0-1.0 continuous blend between schemes)"""
        scheme = np.clip(scheme, 0.0, 1.0)
        self.renderer_params['color_scheme'] = scheme
        if self.renderer:
            self.renderer.set_color_scheme(scheme)

    def set_renderer_channel_curve(self, channel: int, curve: float):
        """Set curve modulation amount for a specific channel (0-1)

        現在這個方法設定 modulation amount 而非絕對值
        最終 curve 值 = base_curve + (LFO × mod_amount)
        """
        if 0 <= channel < 4:
            mod_amount = np.clip(curve, 0.0, 1.0)
            self.curve_mod_amounts[channel] = mod_amount

    def set_renderer_channel_angle(self, channel: int, angle: float):
        """Set angle modulation amount for a specific channel (0-180 mapped to 0-1)

        現在這個方法設定 modulation amount 而非絕對值
        GUI 傳入 0-360 範圍 這裡轉換為 0-1 的 modulation amount
        最終 angle 值 = base_angle + (LFO × mod_amount × 180)
        """
        if 0 <= channel < 4:
            # 將 GUI 的 0-360 範圍映射到 0-1 的 modulation amount
            # angle 輸入範圍假設是 0-360 (從 GUI slider)
            mod_amount = np.clip(angle / 360.0, 0.0, 1.0)
            self.angle_mod_amounts[channel] = mod_amount

    def set_base_curve(self, channel: int, curve: float):
        """設定基礎 curve 值 (0-1)"""
        if 0 <= channel < 4:
            curve = np.clip(curve, 0.0, 1.0)
            self.base_curves[channel] = curve

    def set_base_angle(self, channel: int, angle: float):
        """設定基礎 angle 值 (-180 to 180)"""
        if 0 <= channel < 4:
            angle = np.clip(angle, -180.0, 180.0)
            self.base_angles[channel] = angle

    def set_renderer_channel_intensity(self, channel: int, intensity: float):
        """Set intensity for a specific channel (0-1.5)"""
        if 0 <= channel < 4:
            intensity = np.clip(intensity, 0.0, 1.5)
            self.renderer_params['channel_intensities'][channel] = intensity

    def set_renderer_channel_ratio(self, channel: int, ratio: float):
        """Set ratio for a specific channel (0.01-10.0, stripe density)"""
        if 0 <= channel < 4:
            ratio = np.clip(ratio, 0.01, 10.0)
            self.renderer_params['channel_ratios'][channel] = ratio

    def set_renderer_camera_mix(self, camera_mix: float):
        """Set camera mix amount (0.0=pure multiverse, 1.0=pure camera)"""
        camera_mix = np.clip(camera_mix, 0.0, 1.0)
        self.renderer_params['camera_mix'] = camera_mix

    # Channel level controls (轉發到 audio process)
    def set_channel_level(self, channel: int, level: float):
        """Set level for a specific channel (0.0-1.0)"""
        if 0 <= channel < 4:
            level = np.clip(level, 0.0, 1.0)
            self.channel_levels[channel] = level
            if self.audio_process:
                self.audio_process.set_channel_level(channel, level)

    # Ellen Ripley effect chain controls (轉發到 audio process)
    def enable_ellen_ripley(self, enabled: bool):
        """Enable/disable Ellen Ripley effect chain"""
        self.ellen_ripley_enabled = enabled

    def set_ellen_ripley_delay_params(self, time_l: float = None, time_r: float = None,
                                     feedback: float = None, chaos_enabled: bool = None,
                                     wet_dry: float = None):
        """Set Ellen Ripley delay parameters"""
        if self.audio_process:
            self.audio_process.set_ellen_ripley_delay_params(
                time_l, time_r, feedback, chaos_enabled, wet_dry)

    def set_ellen_ripley_grain_params(self, size: float = None, density: float = None,
                                     position: float = None, chaos_enabled: bool = None,
                                     wet_dry: float = None):
        """Set Ellen Ripley grain parameters"""
        if self.audio_process:
            self.audio_process.set_ellen_ripley_grain_params(
                size, density, position, chaos_enabled, wet_dry)

    def set_ellen_ripley_reverb_params(self, room_size: float = None, damping: float = None,
                                      decay: float = None, chaos_enabled: bool = None,
                                      wet_dry: float = None):
        """Set Ellen Ripley reverb parameters"""
        if self.audio_process:
            self.audio_process.set_ellen_ripley_reverb_params(
                room_size, damping, decay, chaos_enabled, wet_dry)

    def set_ellen_ripley_chaos_params(self, rate: float = None, amount: float = None,
                                     shape: bool = None):
        """Set Ellen Ripley chaos parameters"""
        if self.audio_process:
            self.audio_process.set_ellen_ripley_chaos_params(rate, amount, shape)

    # Alien4 effect controls
    def set_alien4_documenta_params(self, mix: float = None, feedback: float = None,
                                   speed: float = None, eq_low: float = None,
                                   eq_mid: float = None, eq_high: float = None,
                                   poly: int = None):
        """Set Alien4 Documenta (Loop+EQ) parameters"""
        if self.audio_process:
            self.audio_process.set_alien4_documenta_params(
                mix=mix, feedback=feedback, speed=speed,
                eq_low=eq_low, eq_mid=eq_mid, eq_high=eq_high, poly=poly)

    def set_alien4_recording(self, enabled: bool):
        """Set Alien4 recording state"""
        if self.audio_process:
            self.audio_process.set_alien4_recording(enabled)

    def set_alien4_delay_params(self, time_l: float = None, time_r: float = None,
                               feedback: float = None, wet_dry: float = None):
        """Set Alien4 delay parameters"""
        if self.audio_process:
            self.audio_process.set_alien4_delay_params(
                time_l=time_l, time_r=time_r, feedback=feedback, wet_dry=wet_dry)

    def set_alien4_reverb_params(self, decay: float = None, wet_dry: float = None):
        """Set Alien4 reverb parameters"""
        if self.audio_process:
            self.audio_process.set_alien4_reverb_params(decay=decay, wet_dry=wet_dry)

    def set_alien4_scan(self, value: float):
        """Set Alien4 scan position (0.0-1.0)"""
        if self.audio_process:
            self.audio_process.set_alien4_scan(value)

    def set_alien4_gate_threshold(self, value: float):
        """Set Alien4 gate threshold (0.0-1.0, lower=more sensitive)"""
        if self.audio_process:
            self.audio_process.set_alien4_gate_threshold(value)

    # Region-based rendering controls
    def enable_region_rendering(self, enabled: bool):
        """Enable/disable region-based rendering"""
        self.use_region_rendering = enabled

    def enable_cv_overlay(self, enabled: bool):
        """Enable/disable CV overlay display on main visual"""
        self.cv_overlay_enabled = enabled
        status = "enabled" if enabled else "disabled"
        print(f"CV overlay {status}")

    def set_region_mode(self, mode: str):
        """Set region rendering mode ('brightness', 'color', 'quadrant', 'edge')"""
        if mode in ['brightness', 'color', 'quadrant', 'edge']:
            self.region_mode = mode
            print(f"Region mode set to: {mode}")
        else:
            print(f"Invalid region mode: {mode}. Valid modes: brightness, color, quadrant, edge")
    # SD img2img controls
    def set_sd_enabled(self, enabled: bool):
        """Enable/disable SD img2img"""
        if enabled:
            if not self.sd_img2img:
                print("[Controller] Initializing SD img2img...")

                # 在背景線程延遲啟動以避免阻塞音頻
                import threading
                import time
                def _start_sd():
                    # 等待 100ms 讓音頻處理穩定
                    time.sleep(0.1)
                    self.sd_img2img = SDImg2ImgProcess(
                        output_width=1280,
                        output_height=720,
                        fps_target=30
                    )
                    self.sd_img2img.start()
                    # 啟動完成後才啟用
                    self.sd_enabled = True
                    print("[Controller] SD img2img started")

                start_thread = threading.Thread(target=_start_sd, daemon=True)
                start_thread.start()
        else:
            if self.sd_img2img:
                print("[Controller] Stopping SD img2img...")
                self.sd_img2img.stop()
                self.sd_img2img = None
                print("[Controller] SD img2img stopped")

    def set_sd_prompt(self, prompt: str):
        """Set SD prompt"""
        if self.sd_img2img:
            self.sd_img2img.set_prompt(prompt)
        else:
            print("[Controller] SD img2img not initialized")

    def set_sd_parameters(self, strength: float = None, guidance_scale: float = None,
                         num_steps: int = None):
        """Set SD generation parameters"""
        if self.sd_img2img:
            self.sd_img2img.set_parameters(strength, guidance_scale, num_steps)
        else:
            print("[Controller] SD img2img not initialized")

    def set_sd_interval(self, interval: float):
        """Set SD generation interval"""
        if self.sd_img2img:
            self.sd_img2img.send_interval = interval
            print(f"[Controller] SD generation interval set to {interval}s")
        else:
            print("[Controller] SD img2img not initialized")
