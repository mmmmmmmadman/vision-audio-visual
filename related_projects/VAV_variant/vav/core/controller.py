"""
VAV System Controller - Integrates all subsystems
"""

import numpy as np
from typing import Optional, Callable, List, Dict
import threading
import time
import cv2

from ..vision.camera import Camera
from ..cv_generator.contour_cv import ContourCVGenerator
from ..cv_generator.envelope import DecayEnvelope
from ..cv_generator.sequencer import SequenceCV
from ..audio.io import AudioIO
from ..audio.mixer import StereoMixer
from ..audio.effects.ellen_ripley import EllenRipleyEffectChain
from ..audio.analysis import AudioAnalyzer
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
        self.buffer_size = self.config.get("buffer_size", 256)

        # Vision system
        self.camera: Optional[Camera] = None
        self.contour_cv_generator: Optional[ContourCVGenerator] = None
        self.current_frame: Optional[np.ndarray] = None
        self.edges: Optional[np.ndarray] = None  # Edge detection results

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
            'camera_mix': 0.0,  # 0.0=pure multiverse, 1.0=pure camera, blend in between
        }

        # Region-based rendering
        self.use_region_rendering = False  # Enable/disable region-based rendering
        self.region_mapper: Optional[ContentAwareRegionMapper] = None
        self.region_mode = 'brightness'  # 'brightness', 'color', 'quadrant', 'edge'

        # Channel levels for audio mixing (before Ellen Ripley)
        self.channel_levels = [1.0, 1.0, 1.0, 1.0]  # 4 channel levels (0.0-1.0)

        # Audio buffers for Multiverse rendering (circular buffers)
        self.audio_buffer_size = 2400  # 50ms at 48kHz (matches Multiverse.cpp)
        self.audio_buffers = [np.zeros(self.audio_buffer_size, dtype=np.float32) for _ in range(4)]
        self.audio_buffer_lock = threading.Lock()
        self.audio_frequencies = np.array([440.0, 440.0, 440.0, 440.0], dtype=np.float32)
        # No pitch shifting (fixed ratio=1.0, original Multiverse default)

        # CV generators (3 decay envelopes + 2 sequencers)
        self.envelopes: List[DecayEnvelope] = []
        self.sequencers: List[SequenceCV] = []
        self.cv_values = np.zeros(5, dtype=np.float32)  # 5 CV outputs

        # Sequential switch tracking for seq1/seq2
        self.seq1_current_channel = 0  # 0-3 for curve control
        self.seq2_current_channel = 0  # 0-3 for angle control

        # Audio system
        self.audio_io: Optional[AudioIO] = None
        self.mixer: Optional[StereoMixer] = None
        self.audio_analyzer: Optional[AudioAnalyzer] = None

        # Ellen Ripley effect chain (master effects)
        self.ellen_ripley: Optional[EllenRipleyEffectChain] = None
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
        self.camera = Camera(
            device_id=camera_config.get("device_id", 0),
            width=camera_config.get("width", 1920),
            height=camera_config.get("height", 1080),
            fps=camera_config.get("fps", 30),
        )

        if not self.camera.open():
            print("Failed to open camera")
            return False

        # Initialize Contour CV Generator (replaces cable detection)
        self.contour_cv_generator = ContourCVGenerator()

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

        # CV generators
        cv_config = self.config.get("cv", {})

        # 3 decay envelopes
        for i in range(3):
            env = DecayEnvelope(
                sample_rate=self.sample_rate,
                decay_time=cv_config.get(f"decay_{i}_time", 1.0),
            )
            self.envelopes.append(env)

        # 2 sequencers
        for i in range(2):
            seq = SequenceCV(
                sample_rate=self.sample_rate,
                num_steps=cv_config.get(f"seq_{i}_steps", 16),
                clock_rate=cv_config.get(f"seq_{i}_bpm", 120.0),
            )
            self.sequencers.append(seq)

        # Audio system
        audio_config = self.config.get("audio", {})

        # Default output channels: try for 7 (stereo + 5 CV), fallback to device max
        # Default input channels: 4 for Multiverse (Ch1-4)
        self.audio_io = AudioIO(
            sample_rate=self.sample_rate,
            buffer_size=self.buffer_size,
            input_channels=audio_config.get("input_channels", 4),
            output_channels=audio_config.get("output_channels", 7),  # Will be adjusted by device selection
        )

        # Set devices if specified
        if "input_device" in audio_config or "output_device" in audio_config:
            self.audio_io.set_devices(
                input_device=audio_config.get("input_device"),
                output_device=audio_config.get("output_device"),
            )

        self.mixer = StereoMixer(num_channels=4)
        self.audio_analyzer = AudioAnalyzer(
            sample_rate=self.sample_rate,
            buffer_size=self.buffer_size,
        )

        # Initialize Ellen Ripley effect chain
        print("Warming up Ellen Ripley Numba JIT...")
        self.ellen_ripley = EllenRipleyEffectChain(sample_rate=self.sample_rate)

        # Pre-warm Numba JIT compilation (prevent first-use audio glitch)
        dummy_audio = np.zeros((256, 2), dtype=np.float32)
        _ = self.ellen_ripley.process(dummy_audio[:, 0], dummy_audio[:, 1])
        print("Ellen Ripley effect chain initialized")

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

        # Start vision thread
        self.vision_thread = threading.Thread(target=self._vision_loop, daemon=True)
        self.vision_thread.start()

        # Start audio I/O
        self.audio_io.start(self._audio_callback)

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

        # Stop audio
        if self.audio_io:
            self.audio_io.stop()

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
                # Still update CV even on skipped frames
                current_time = time.time()
                if current_time - last_cv_update >= cv_update_time:
                    self._update_cv_values()
                    last_cv_update = current_time
                continue

            self.current_frame = frame

            # Determine CV detection source: SD output (if available) or camera
            cv_input_frame = frame  # Default: use camera frame
            if self.sd_enabled and self.sd_img2img:
                sd_output = self.sd_img2img.get_current_output()
                if sd_output is not None:
                    # Ensure size matches
                    if sd_output.shape[:2] != frame.shape[:2]:
                        cv_input_frame = cv2.resize(sd_output, (frame.shape[1], frame.shape[0]))
                    else:
                        cv_input_frame = sd_output

            # Convert to grayscale for edge detection (from SD or camera, not multiverse)
            gray = cv2.cvtColor(cv_input_frame, cv2.COLOR_BGR2GRAY)

            # Generate sequence values from edge detection
            self.contour_cv_generator.sample_edge_sequences(gray)

            # Update CV sequencer and trigger envelopes
            current_time = time.time()
            if current_time - last_cv_update >= cv_update_time:
                dt = current_time - last_cv_update
                self.contour_cv_generator.update_sequencer_and_triggers(
                    dt, frame.shape[1], frame.shape[0], self.envelopes
                )
                self._update_cv_values()
                last_cv_update = current_time

            # Update trigger ring animations
            self.contour_cv_generator.update_trigger_rings()

            # Generate visualization frame (for both GUI and virtual camera)
            # Edge detection is now done inside Multiverse rendering (based on SD processed frame)
            display_frame = self._draw_visualization(frame)

            # Callback for GUI frame update (send visualization, not raw frame)
            if self.frame_callback:
                self.frame_callback(display_frame)

            # Output to virtual camera if enabled
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

            # Maintain frame rate
            elapsed = time.time() - start_time
            sleep_time = frame_time - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _draw_visualization(self, frame):
        """Draw visualization using ContourCVGenerator overlay"""
        if self.use_multiverse_rendering:
            return self._render_multiverse(frame)
        else:
            return self._render_simple(frame)

    def _render_simple(self, frame):
        """Simple visualization: use ContourCVGenerator overlay"""
        # Use ContourCVGenerator's draw_overlay method
        display_frame = self.contour_cv_generator.draw_overlay(
            frame, self.edges if self.edges is not None else np.zeros_like(frame[:,:,0]),
            envelopes=self.envelopes
        )
        return display_frame

    def _render_multiverse(self, frame):
        """Multiverse rendering: frequency-based color mapping with blend modes (Qt OpenGL on macOS, ModernGL on others)"""
        if self.renderer is None:
            return self._render_simple(frame)

        # Process SD img2img first (if enabled) - SD processes camera frame, not rendered output
        input_frame = frame  # Default: use camera frame
        if self.sd_enabled and self.sd_img2img:
            # Feed camera frame to SD process
            self.sd_img2img.feed_frame(frame)

            # Get SD processed result
            sd_output = self.sd_img2img.get_current_output()

            # If SD has output, use it as input_frame
            if sd_output is not None:
                # Ensure size matches
                if sd_output.shape[:2] != frame.shape[:2]:
                    sd_output = cv2.resize(sd_output, (frame.shape[1], frame.shape[0]))
                input_frame = sd_output

        # Detect edges from input_frame (SD or camera) for CV generation
        # This ensures CV generation is based on the processed/styled image
        gray_input = cv2.cvtColor(input_frame, cv2.COLOR_BGR2GRAY)
        _, edges_new = self.contour_cv_generator.detect_contours(gray_input)
        self.edges = edges_new  # Update edges to reflect SD processed content

        # Prepare channel data for Multiverse renderer
        channels_data = []

        # Use real audio buffers (thread-safe access)
        with self.audio_buffer_lock:
            audio_buffers_copy = [buf.copy() for buf in self.audio_buffers]
            frequencies_copy = self.audio_frequencies.copy()

        # Enable all 4 channels based on user intensity
        for ch_idx in range(4):
            # Check if user intensity is near zero (disable channel)
            user_intensity = self.renderer_params['channel_intensities'][ch_idx]
            if user_intensity < 0.01:
                channels_data.append({'enabled': False})
            else:
                # Get envelope value for intensity modulation
                env_idx = ch_idx % 3
                base_intensity = 0.8  # Base intensity
                env_value = self.cv_values[env_idx] if env_idx < 3 else 0.5
                intensity = base_intensity + (env_value * 0.7)  # 0.8 to 1.5 range
                intensity = float(np.clip(intensity * user_intensity, 0.0, 2.0))

                channels_data.append({
                    'enabled': True,
                    'audio': audio_buffers_copy[ch_idx],  # Real audio from ES-8!
                    'frequency': float(frequencies_copy[ch_idx]),  # Detected frequency
                    'intensity': intensity,
                    'curve': self.renderer_params['channel_curves'][ch_idx],
                    'angle': self.renderer_params['channel_angles'][ch_idx],
                })

        # Generate region map using input_frame (SD or camera) if region rendering is enabled
        region_map = None
        if self.use_region_rendering and self.region_mapper:
            if self.region_mode == 'brightness':
                region_map = self.region_mapper.create_brightness_based_regions(input_frame)
            elif self.region_mode == 'color':
                region_map = self.region_mapper.create_color_based_regions(input_frame)
            elif self.region_mode == 'quadrant':
                region_map = self.region_mapper.create_quadrant_regions(input_frame)
            elif self.region_mode == 'edge':
                region_map = self.region_mapper.create_edge_based_regions(input_frame)

        # Update envelope offsets for GPU renderer (env1-3 control tracks 1-3 hue angles)
        if self.using_gpu and hasattr(self.renderer, 'set_envelope_offsets'):
            self.renderer.set_envelope_offsets(
                self.cv_values[0],  # env1 for channel 1
                self.cv_values[1],  # env2 for channel 2
                self.cv_values[2]   # env3 for channel 3
            )

        # Render using Multiverse engine (4 audio channels)
        # Both Numba and Qt OpenGL renderers support region_map parameter
        if region_map is not None:
            rendered_rgb = self.renderer.render(channels_data, region_map=region_map)
        else:
            rendered_rgb = self.renderer.render(channels_data)

        # Convert RGB to BGR for OpenCV
        rendered_bgr = cv2.cvtColor(rendered_rgb, cv2.COLOR_RGB2BGR)

        # Blend 5th layer (SD or camera) with Multiverse rendering if camera_mix > 0
        # input_frame is either SD output or original camera frame
        camera_mix = self.renderer_params['camera_mix']
        if camera_mix > 0.0:
            # Resize input_frame to match renderer output if needed
            if input_frame.shape[:2] != rendered_bgr.shape[:2]:
                blend_frame = cv2.resize(input_frame, (rendered_bgr.shape[1], rendered_bgr.shape[0]))
            else:
                blend_frame = input_frame

            # Apply blend mode (same as Multiverse channels)
            blend_mode = self.renderer_params['blend_mode']

            # Convert to float for blending (0-1 range)
            base_float = rendered_bgr.astype(np.float32) / 255.0
            blend_float = blend_frame.astype(np.float32) / 255.0

            # Apply camera_mix as alpha
            blend_float = blend_float * camera_mix

            # Blend based on mode
            if blend_mode == 0:  # Add
                result = np.clip(base_float + blend_float, 0.0, 1.0)
            elif blend_mode == 1:  # Screen
                result = 1.0 - (1.0 - base_float) * (1.0 - blend_float)
            elif blend_mode == 2:  # Difference
                result = np.abs(base_float - blend_float)
            elif blend_mode == 3:  # Color Dodge
                result = np.where(blend_float < 0.999,
                                 np.clip(base_float / np.maximum(0.001, 1.0 - blend_float), 0.0, 1.0),
                                 1.0)
            else:
                result = base_float

            # Convert back to uint8
            rendered_bgr = (result * 255.0).astype(np.uint8)

        # Draw CV overlays (dashboard, SEQ lines, ENV rings) - must be on top
        rendered_bgr = self.contour_cv_generator.draw_overlay(
            rendered_bgr,
            self.edges if self.edges is not None else np.zeros_like(rendered_bgr[:,:,0]),
            envelopes=self.envelopes
        )

        # Add info text
        height, width = rendered_bgr.shape[:2]
        mode_names = ["Add", "Screen", "Diff", "Dodge"]
        mode_name = mode_names[self.renderer_params['blend_mode']]
        if NUMBA_AVAILABLE and isinstance(self.renderer, NumbaMultiverseRenderer):
            renderer_type = "Numba JIT"
        elif self.using_gpu and isinstance(self.renderer, QtMultiverseRenderer):
            renderer_type = "Qt OpenGL"
        elif self.using_gpu:
            renderer_type = "GPU"
        else:
            renderer_type = "CPU"
        # Text overlay removed for clean output

        return rendered_bgr

    def _update_cv_values(self):
        """Update CV generator values and handle sequential switch"""
        # Sequential switch logic: check if ContourCV seq1/seq2 stepped
        if self.contour_cv_generator:
            # SEQ1 -> Curve (輪流控制 channel 0-3 的 curve, 擴大範圍 0-5)
            if self.contour_cv_generator.seq1_step_changed:
                seq1_value = self.contour_cv_generator.seq1_value
                curve_value = seq1_value * 5.0
                self.renderer_params['channel_curves'][self.seq1_current_channel] = curve_value
                if self.param_callback:
                    self.param_callback("curve", self.seq1_current_channel, curve_value)
                self.seq1_current_channel = (self.seq1_current_channel + 1) % 4

            # SEQ2 -> Angle (輪流控制 channel 0-3 的 angle, 擴大範圍多圈)
            if self.contour_cv_generator.seq2_step_changed:
                seq2_value = self.contour_cv_generator.seq2_value
                angle_value = seq2_value * 720.0
                self.renderer_params['channel_angles'][self.seq2_current_channel] = angle_value
                if self.param_callback:
                    self.param_callback("angle", self.seq2_current_channel, angle_value)
                self.seq2_current_channel = (self.seq2_current_channel + 1) % 4

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
            self.contour_cv_generator.set_edge_threshold(threshold)

    def set_cv_smoothing(self, smoothing: int):
        """Set temporal smoothing (0-100)"""
        if self.contour_cv_generator:
            self.contour_cv_generator.set_smoothing(smoothing)

    def set_cv_clock_rate(self, bpm: float):
        """Set unified clock rate for SEQ1 and SEQ2 (1-999 BPM)"""
        if self.contour_cv_generator:
            self.contour_cv_generator.set_clock_rate(bpm)

    def _update_audio_buffers(self, indata: np.ndarray):
        """Update audio buffers for Multiverse rendering with frequency detection"""
        if indata.shape[1] < 2:
            return

        # Update circular buffers for first 4 input channels
        with self.audio_buffer_lock:
            for ch_idx in range(min(4, indata.shape[1])):
                audio_data = indata[:, ch_idx]

                # Shift buffer and append new data (no pitch shifting, ratio=1.0)
                shift_amount = len(audio_data)
                self.audio_buffers[ch_idx] = np.roll(self.audio_buffers[ch_idx], -shift_amount)
                self.audio_buffers[ch_idx][-shift_amount:] = audio_data * 10.0  # Scale to ±10V range

                # Detect dominant frequency using FFT
                # Use last 2048 samples for frequency detection
                fft_size = 2048
                if len(self.audio_buffers[ch_idx]) >= fft_size:
                    signal = self.audio_buffers[ch_idx][-fft_size:]

                    # Apply window to reduce spectral leakage
                    window = np.hanning(fft_size)
                    windowed_signal = signal * window

                    # Compute FFT
                    fft = np.fft.rfft(windowed_signal)
                    magnitude = np.abs(fft)

                    # Find peak frequency (ignore DC and very low frequencies)
                    min_freq_bin = int(20.0 * fft_size / self.sample_rate)  # 20 Hz
                    max_freq_bin = int(20000.0 * fft_size / self.sample_rate)  # 20 kHz

                    if max_freq_bin > min_freq_bin:
                        peak_bin = np.argmax(magnitude[min_freq_bin:max_freq_bin]) + min_freq_bin
                        detected_freq = peak_bin * self.sample_rate / fft_size

                        # Smooth frequency changes (low-pass filter)
                        alpha = 0.1  # Smoothing factor
                        self.audio_frequencies[ch_idx] = (alpha * detected_freq +
                                                         (1 - alpha) * self.audio_frequencies[ch_idx])

    def _audio_callback(self, indata: np.ndarray, frames: int) -> np.ndarray:
        """Audio processing callback (runs in audio thread)"""
        # Update audio buffers for Multiverse rendering
        self._update_audio_buffers(indata)

        # Process CV generators (sample-accurate)
        for i in range(frames):
            # Update envelopes
            for j, env in enumerate(self.envelopes):
                self.cv_values[j] = env.process()

            # Update SEQ1/SEQ2 from ContourCV generator (直接使用 ContourCV 的值)
            if self.contour_cv_generator:
                self.cv_values[3] = self.contour_cv_generator.seq1_value  # SEQ1
                self.cv_values[4] = self.contour_cv_generator.seq2_value  # SEQ2
            else:
                # Fallback: use internal sequencers if ContourCV not available
                for j, seq in enumerate(self.sequencers):
                    self.cv_values[3 + j] = seq.process()

        # CV callback for GUI scope update
        if self.cv_callback:
            self.cv_callback(self.cv_values.copy())

        # Mix 4 input channels with individual levels into mono
        # Each channel is treated as mono, mixed together
        mixed_mono = np.zeros(frames, dtype=np.float32)

        for i in range(4):
            if indata.shape[1] > i:
                # Apply channel level and accumulate
                mixed_mono += indata[:, i] * self.channel_levels[i]

        # Convert mono to stereo for Ellen Ripley (duplicate to L/R)
        mixed_left = mixed_mono
        mixed_right = mixed_mono

        # Process mixed tracks through mixer (for compatibility)
        track_inputs = [(mixed_left, mixed_right)]
        for i in range(3):
            track_inputs.append((np.zeros(frames, dtype=np.float32), np.zeros(frames, dtype=np.float32)))

        left_out, right_out = self.mixer.process(track_inputs)

        # Ellen Ripley master effect chain (if enabled)
        if self.ellen_ripley_enabled and self.ellen_ripley:
            left_out, right_out, chaos_cv = self.ellen_ripley.process(left_out, right_out)
            # TODO: Output chaos_cv if needed

        # Audio analysis for visual feedback
        features = self.audio_analyzer.analyze(left_out)
        self.visual_params = self.audio_analyzer.get_visual_parameters(features)

        # Visual callback
        if self.visual_callback:
            self.visual_callback(self.visual_params.copy())

        # Build output based on available channels
        if self.audio_io.output_channels >= 7:
            # Device supports CV output: [L, R, CV1, CV2, CV3, CV4, CV5]
            # Convert CV values (0-1) to audio range (-1 to 1) for Eurorack compatibility
            cv_out = np.zeros((frames, 5), dtype=np.float32)
            for i in range(5):
                # Eurorack CV: 0-10V normalized to -1 to +1 range
                # CV value 0.0 -> -1.0, CV value 1.0 -> +1.0
                cv_out[:, i] = self.cv_values[i] * 2.0 - 1.0

            output = np.column_stack((left_out, right_out, cv_out))
        else:
            # Device only supports stereo: [L, R]
            output = np.column_stack((left_out, right_out))

        return output


    def set_envelope_decay(self, env_idx: int, decay_time: float):
        """Set envelope decay time"""
        if 0 <= env_idx < len(self.envelopes):
            self.envelopes[env_idx].set_decay_time(decay_time)

    def set_global_env_decay(self, decay_time: float):
        """Set decay time for all envelopes"""
        for env in self.envelopes:
            env.set_decay_time(decay_time)

    def set_sequencer_params(self, seq_idx: int, num_steps: int = None,
                            clock_rate: float = None):
        """Set sequencer parameters"""
        if 0 <= seq_idx < len(self.sequencers):
            seq = self.sequencers[seq_idx]
            if num_steps is not None:
                seq.set_num_steps(num_steps)
            if clock_rate is not None:
                seq.set_clock_rate(clock_rate)

    def set_mixer_params(self, track_idx: int, volume: float = None,
                        pan: float = None, solo: bool = None, mute: bool = None):
        """Set mixer track parameters"""
        if 0 <= track_idx < self.mixer.num_channels:
            if volume is not None:
                self.mixer.set_channel_volume(track_idx, volume)
            if pan is not None:
                self.mixer.set_channel_pan(track_idx, pan)
            if solo is not None:
                self.mixer.set_channel_solo(track_idx, solo)
            if mute is not None:
                self.mixer.set_channel_mute(track_idx, mute)


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

    def set_renderer_blend_mode(self, mode: int):
        """Set Multiverse blend mode (0-3)"""
        mode = int(np.clip(mode, 0, 3))
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

    def set_renderer_channel_curve(self, channel: int, curve: float):
        """Set curve for a specific channel (0-1)"""
        if 0 <= channel < 4:
            curve = np.clip(curve, 0.0, 1.0)
            self.renderer_params['channel_curves'][channel] = curve

    def set_renderer_channel_angle(self, channel: int, angle: float):
        """Set rotation angle for a specific channel (-180 to 180)"""
        if 0 <= channel < 4:
            angle = np.clip(angle, -180.0, 180.0)
            self.renderer_params['channel_angles'][channel] = angle

    def set_renderer_channel_intensity(self, channel: int, intensity: float):
        """Set intensity for a specific channel (0-1.5)"""
        if 0 <= channel < 4:
            intensity = np.clip(intensity, 0.0, 1.5)
            self.renderer_params['channel_intensities'][channel] = intensity

    def set_renderer_camera_mix(self, camera_mix: float):
        """Set camera mix amount (0.0=pure multiverse, 1.0=pure camera)"""
        camera_mix = np.clip(camera_mix, 0.0, 1.0)
        self.renderer_params['camera_mix'] = camera_mix

    # Channel level controls (for audio mixing before Ellen Ripley)
    def set_channel_level(self, channel: int, level: float):
        """Set level for a specific channel (0.0-1.0)"""
        if 0 <= channel < 4:
            level = np.clip(level, 0.0, 1.0)
            self.channel_levels[channel] = level

    # Ellen Ripley effect chain controls
    def enable_ellen_ripley(self, enabled: bool):
        """Enable/disable Ellen Ripley effect chain"""
        self.ellen_ripley_enabled = enabled

    def set_ellen_ripley_delay_params(self, time_l: float = None, time_r: float = None,
                                     feedback: float = None, chaos_enabled: bool = None,
                                     wet_dry: float = None):
        """Set Ellen Ripley delay parameters"""
        if self.ellen_ripley:
            self.ellen_ripley.set_delay_params(time_l, time_r, feedback, chaos_enabled, wet_dry)

    def set_ellen_ripley_grain_params(self, size: float = None, density: float = None,
                                     position: float = None, chaos_enabled: bool = None,
                                     wet_dry: float = None):
        """Set Ellen Ripley grain parameters"""
        if self.ellen_ripley:
            self.ellen_ripley.set_grain_params(size, density, position, chaos_enabled, wet_dry)

    def set_ellen_ripley_reverb_params(self, room_size: float = None, damping: float = None,
                                      decay: float = None, chaos_enabled: bool = None,
                                      wet_dry: float = None):
        """Set Ellen Ripley reverb parameters"""
        if self.ellen_ripley:
            self.ellen_ripley.set_reverb_params(room_size, damping, decay, chaos_enabled, wet_dry)

    def set_ellen_ripley_chaos_params(self, rate: float = None, amount: float = None,
                                     shape: bool = None):
        """Set Ellen Ripley chaos parameters"""
        if self.ellen_ripley:
            self.ellen_ripley.set_chaos_params(rate, amount, shape)

    # Region-based rendering controls
    def enable_region_rendering(self, enabled: bool):
        """Enable/disable region-based rendering"""
        self.use_region_rendering = enabled
        status = "enabled" if enabled else "disabled"
        print(f"Region-based rendering {status}")

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
