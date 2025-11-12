"""
Compact Main GUI window for VAV system - optimized layout
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QGroupBox, QGridLayout,
    QComboBox, QCheckBox, QTextEdit, QLineEdit, QMenu,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
import numpy as np
import cv2

from .device_dialog import DeviceSelectionDialog
from .anchor_xy_pad import AnchorXYPad
from .cv_meter_window import CVMeterWindow
from ..core.controller import VAVController


class CompactMainWindow(QMainWindow):
    """Compact main application window with efficient layout"""

    # Signals
    frame_updated = pyqtSignal(np.ndarray)
    cv_updated = pyqtSignal(np.ndarray)
    visual_updated = pyqtSignal(dict)
    param_updated = pyqtSignal(str, int, float)  # param_name, channel, value

    def __init__(self, controller: VAVController):
        super().__init__()
        self.controller = controller
        self.setWindowTitle("VAV Control")
        self.setGeometry(100, 100, 1300, 480)

        # Connect controller callbacks
        self.controller.set_frame_callback(self._on_frame)
        self.controller.set_cv_callback(self._on_cv)
        self.controller.set_visual_callback(self._on_visual)
        self.controller.set_param_callback(self._on_param)

        # Connect signals to slots (thread-safe)
        self.frame_updated.connect(self._update_frame_display)
        self.cv_updated.connect(self._update_cv_display)
        self.visual_updated.connect(self._update_visual_display)
        self.param_updated.connect(self._update_param_display)

        # MIDI Learn system (initialize before building UI)
        from ..midi import MIDILearnManager
        self.midi_learn = MIDILearnManager()

        # Build UI
        self._build_ui()

        # Enable Ellen Ripley and Multiverse by default after UI is built
        self.controller.enable_ellen_ripley(True)
        self.controller.enable_multiverse_rendering(True)
        self.controller.enable_region_rendering(True)
        self.controller.set_region_mode('brightness')
        # Set brightness to 1.5
        self.controller.set_renderer_brightness(1.5)

        # Initialize anchor position to center (50%, 50%)
        self.controller.set_anchor_position(50.0, 50.0)

        # CV Meter Window (independent)
        self.cv_meter_window = CVMeterWindow()
        self.cv_meter_window.show()

        # Status bar
        self.status_label = QLabel("Ready")
        self.statusBar().addWidget(self.status_label)

        # Device status on right side of status bar
        self.device_status_label = QLabel("No devices")
        self.device_status_label.setWordWrap(False)
        self.statusBar().addPermanentWidget(self.device_status_label)

        # Update initial device status
        self._update_device_status()

    def _make_slider_learnable(self, slider, param_id: str, callback):
        """Make a slider MIDI-learnable with right-click context menu"""
        from PyQt6.QtWidgets import QMenu

        # Enable context menu
        slider.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        def show_context_menu(pos):
            menu = QMenu()
            learn_action = menu.addAction("MIDI Learn")
            clear_action = menu.addAction("Clear MIDI Mapping")
            menu.addSeparator()
            clear_all_action = menu.addAction("Clear All MIDI Mappings")

            action = menu.exec(slider.mapToGlobal(pos))

            if action == learn_action:
                self.midi_learn.enter_learn_mode(param_id)
            elif action == clear_action:
                self.midi_learn.clear_mapping(param_id)
            elif action == clear_all_action:
                self.midi_learn.clear_all_mappings()

        slider.customContextMenuRequested.connect(show_context_menu)

        # Register with MIDI Learn system
        min_val = slider.minimum()
        max_val = slider.maximum()

        def midi_callback(value):
            # Value already scaled by midi_learn.py to slider range
            slider_value = int(value)

            # Block signals to prevent recursion, then update slider
            slider.blockSignals(True)
            slider.setValue(slider_value)
            slider.blockSignals(False)

            # Call the original callback directly with the slider value
            callback(slider_value)

        self.midi_learn.register_parameter(param_id, midi_callback, min_val, max_val)

    def _build_ui(self):
        """Build compact UI layout"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(5)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # Top: Control buttons
        control_layout = QHBoxLayout()
        control_layout.setSpacing(5)

        self.start_btn = QPushButton("Start")
        self.start_btn.setFixedHeight(30)
        self.start_btn.clicked.connect(self._on_start)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setFixedHeight(30)
        self.stop_btn.clicked.connect(self._on_stop)
        self.stop_btn.setEnabled(False)

        self.show_video_btn = QPushButton("Video")
        self.show_video_btn.setFixedHeight(30)
        self.show_video_btn.clicked.connect(self._on_show_video)

        self.devices_btn = QPushButton("Devices")
        self.devices_btn.setFixedHeight(30)
        self.devices_btn.clicked.connect(self._on_select_devices)

        self.vcam_btn = QPushButton("Virtual Cam")
        self.vcam_btn.setFixedHeight(30)
        self.vcam_btn.setCheckable(True)
        self.vcam_btn.clicked.connect(self._on_toggle_virtual_camera)

        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.stop_btn)
        control_layout.addWidget(self.show_video_btn)
        control_layout.addWidget(self.devices_btn)
        control_layout.addWidget(self.vcam_btn)
        control_layout.addStretch()
        main_layout.addLayout(control_layout)

        # Controls in compact widget
        controls_widget = QWidget()
        controls_grid = QGridLayout(controls_widget)
        controls_grid.setVerticalSpacing(10)    # Consistent vertical spacing for all controls
        controls_grid.setHorizontalSpacing(10)  # Horizontal spacing
        controls_grid.setContentsMargins(5, 5, 5, 5)
        # 5 visual columns x 3 grid columns each = 15 columns + 1 stretch
        for i in range(15):
            controls_grid.setColumnStretch(i, 0)  # No stretch for control columns
        controls_grid.setColumnStretch(15, 1)  # Stretch remainder
        self._build_all_controls_inline(controls_grid)

        main_layout.addWidget(controls_widget)

        # Video window (separate)
        self.video_window = QWidget()
        self.video_window.setWindowTitle("VAV - Video")
        self.video_window.setStyleSheet("background-color: black;")
        video_layout = QVBoxLayout(self.video_window)
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.setSpacing(0)
        self.video_label = QLabel()
        self.video_label.setMinimumSize(960, 540)
        self.video_label.setStyleSheet("background-color: black;")
        self.video_label.setScaledContents(True)
        video_layout.addWidget(self.video_label)

    def _apply_slider_style(self, slider, color):
        """Apply styled slider with MUJI-inspired pink color scheme"""
        slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background: #f0f0f0;
                height: 4px;
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {color};
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {color};
                opacity: 0.8;
            }}
            QSlider::sub-page:horizontal {{
                background: {color};
                border-radius: 2px;
            }}
        """)

    def _build_all_controls_inline(self, grid: QGridLayout):
        """Build all controls in 5-column layout"""

        # Enhanced pink color scheme for better contrast
        COLOR_COL1 = "#FF6B9D"  # Vibrant pink (Audio basics)
        COLOR_COL2 = "#FF9A76"  # Coral orange (Multiverse global)
        COLOR_COL3 = "#C77DFF"  # Purple (Multiverse channels)
        COLOR_COL4 = "#FF8FA3"  # Rose pink (Ellen Ripley)

        # Column positions (each visual column uses 3 grid columns)
        COL1 = 0   # CV Source + Mixer
        COL2 = 3   # Multiverse Main
        COL3 = 6   # Multiverse Channels + SD img2img
        COL4 = 9   # Ellen Ripley Delay+Grain
        COL5 = 12  # Ellen Ripley Reverb+Chaos

        # ===== COLUMN 1: CV Source =====
        row1 = 0

        # ENV Global Decay (exponential: 0.1~1s, 1~5s)
        grid.addWidget(QLabel("ENV Global Decay"), row1, COL1)
        self.env_global_slider = QSlider(Qt.Orientation.Horizontal)
        self.env_global_slider.setFixedHeight(16)
        self.env_global_slider.setFixedWidth(140)
        self._apply_slider_style(self.env_global_slider, COLOR_COL1)
        self.env_global_slider.setMinimum(0)
        self.env_global_slider.setMaximum(100)
        self.env_global_slider.setValue(50)
        self.env_global_slider.valueChanged.connect(self._on_env_global_decay_changed)
        self._make_slider_learnable(self.env_global_slider, "env_global_decay", self._on_env_global_decay_changed)
        grid.addWidget(self.env_global_slider, row1, COL1 + 1)
        self.env_global_label = QLabel("1.0s")
        self.env_global_label.setFixedWidth(35)
        grid.addWidget(self.env_global_label, row1, COL1 + 2)
        row1 += 1

        # Scan Time (掃描時間，秒)
        grid.addWidget(QLabel("Scan Time"), row1, COL1)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setFixedHeight(16)
        slider.setFixedWidth(140)
        self._apply_slider_style(slider, COLOR_COL1)
        slider.setMinimum(2)  # 0.1s
        slider.setMaximum(600)  # 30s
        slider.setValue(200)  # 10.0s
        slider.valueChanged.connect(self._on_clock_rate_changed)
        self._make_slider_learnable(slider, "scan_time", self._on_clock_rate_changed)
        grid.addWidget(slider, row1, COL1 + 1)
        value = QLabel("10.0s")
        value.setFixedWidth(35)
        grid.addWidget(value, row1, COL1 + 2)
        self.clock_slider = (slider, value)
        row1 += 1

        # Range
        grid.addWidget(QLabel("Range"), row1, COL1)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setFixedHeight(16)
        slider.setFixedWidth(140)
        self._apply_slider_style(slider, COLOR_COL1)
        slider.setMinimum(1)
        slider.setMaximum(120)
        slider.setValue(50)
        slider.valueChanged.connect(self._on_range_changed)
        self._make_slider_learnable(slider, "range", self._on_range_changed)
        grid.addWidget(slider, row1, COL1 + 1)
        value = QLabel("50%")
        value.setFixedWidth(35)
        grid.addWidget(value, row1, COL1 + 2)
        self.range_slider = (slider, value)
        row1 += 1

        # Mixer (moved from COL2)
        self.mixer_sliders = []
        for i in range(4):
            grid.addWidget(QLabel(f"Track {i+1} Vol"), row1, COL1)
            mix_slider = QSlider(Qt.Orientation.Horizontal)
            mix_slider.setFixedHeight(16)
            mix_slider.setFixedWidth(140)
            self._apply_slider_style(mix_slider, COLOR_COL1)
            mix_slider.setMinimum(0)
            mix_slider.setMaximum(100)
            mix_slider.setValue(80)
            mix_slider.valueChanged.connect(lambda val, idx=i: self._on_mixer_volume(idx, val / 100.0))
            self._make_slider_learnable(mix_slider, f"track{i+1}_vol", lambda val, idx=i: self._on_mixer_volume(idx, val / 100.0))
            grid.addWidget(mix_slider, row1, COL1 + 1)
            mix_label = QLabel("0.8")
            mix_label.setFixedWidth(25)
            grid.addWidget(mix_label, row1, COL1 + 2)
            self.mixer_sliders.append((mix_slider, mix_label))
            row1 += 1

        # ===== COLUMN 2: Multiverse Main =====
        row2 = 0

        # Enable
        self.multiverse_checkbox = QCheckBox("Multiverse")
        self.multiverse_checkbox.setFixedHeight(16)  # Match slider height for consistent spacing
        self.multiverse_checkbox.setChecked(True)  # Default enabled
        self.multiverse_checkbox.stateChanged.connect(self._on_multiverse_toggle)
        grid.addWidget(self.multiverse_checkbox, row2, COL2)

        # Color scheme fader (no label, continuous blend)
        self.color_scheme_slider = QSlider(Qt.Orientation.Horizontal)
        self.color_scheme_slider.setFixedHeight(16)
        self.color_scheme_slider.setFixedWidth(120)
        self._apply_slider_style(self.color_scheme_slider, COLOR_COL2)
        self.color_scheme_slider.setMinimum(0)
        self.color_scheme_slider.setMaximum(100)
        self.color_scheme_slider.setValue(50)  # Default to middle (Tri+Contrast)
        self.color_scheme_slider.valueChanged.connect(self._on_color_scheme_changed)
        self._make_slider_learnable(self.color_scheme_slider, "color_scheme", self._on_color_scheme_changed)
        grid.addWidget(self.color_scheme_slider, row2, COL2 + 1, 1, 2)
        row2 += 1

        # Blend mode fader
        grid.addWidget(QLabel("Blend"), row2, COL2)
        self.blend_mode_slider = QSlider(Qt.Orientation.Horizontal)
        self.blend_mode_slider.setFixedHeight(16)
        self.blend_mode_slider.setFixedWidth(120)
        self._apply_slider_style(self.blend_mode_slider, COLOR_COL2)
        self.blend_mode_slider.setMinimum(0)
        self.blend_mode_slider.setMaximum(100)
        self.blend_mode_slider.setValue(0)  # Default to Add
        self.blend_mode_slider.valueChanged.connect(self._on_blend_mode_changed)
        self._make_slider_learnable(self.blend_mode_slider, "blend_mode", self._on_blend_mode_changed)
        grid.addWidget(self.blend_mode_slider, row2, COL2 + 1, 1, 2)
        row2 += 1

        # Brightness
        grid.addWidget(QLabel("Brightness"), row2, COL2)
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setFixedHeight(16)
        self.brightness_slider.setFixedWidth(120)
        self._apply_slider_style(self.brightness_slider, COLOR_COL2)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(400)
        self.brightness_slider.setValue(150)  # Default 1.5
        self.brightness_slider.valueChanged.connect(self._on_brightness_changed)
        self._make_slider_learnable(self.brightness_slider, "brightness", self._on_brightness_changed)
        grid.addWidget(self.brightness_slider, row2, COL2 + 1)
        self.brightness_label = QLabel("1.5")
        self.brightness_label.setFixedWidth(25)
        grid.addWidget(self.brightness_label, row2, COL2 + 2)
        row2 += 1

        # Base Hue
        grid.addWidget(QLabel("Base Hue"), row2, COL2)
        self.base_hue_slider = QSlider(Qt.Orientation.Horizontal)
        self.base_hue_slider.setFixedHeight(16)
        self.base_hue_slider.setFixedWidth(120)
        self._apply_slider_style(self.base_hue_slider, COLOR_COL2)
        self.base_hue_slider.setMinimum(0)
        self.base_hue_slider.setMaximum(333)
        self.base_hue_slider.setValue(0)  # Default red
        self.base_hue_slider.valueChanged.connect(self._on_base_hue_changed)
        self._make_slider_learnable(self.base_hue_slider, "base_hue", self._on_base_hue_changed)
        grid.addWidget(self.base_hue_slider, row2, COL2 + 1)
        self.base_hue_label = QLabel("0")
        self.base_hue_label.setFixedWidth(25)
        grid.addWidget(self.base_hue_label, row2, COL2 + 2)
        row2 += 1

        # Camera Mix
        grid.addWidget(QLabel("Camera Mix"), row2, COL2)
        self.camera_mix_slider = QSlider(Qt.Orientation.Horizontal)
        self.camera_mix_slider.setFixedHeight(16)
        self.camera_mix_slider.setFixedWidth(120)
        self._apply_slider_style(self.camera_mix_slider, COLOR_COL2)
        self.camera_mix_slider.setMinimum(0)
        self.camera_mix_slider.setMaximum(30)  # Max 0.3
        self.camera_mix_slider.setValue(0)  # Default: pure multiverse
        self.camera_mix_slider.valueChanged.connect(self._on_camera_mix_changed)
        self._make_slider_learnable(self.camera_mix_slider, "camera_mix", self._on_camera_mix_changed)
        grid.addWidget(self.camera_mix_slider, row2, COL2 + 1)
        self.camera_mix_label = QLabel("0.0")
        self.camera_mix_label.setFixedWidth(25)
        grid.addWidget(self.camera_mix_label, row2, COL2 + 2)
        row2 += 1

        # Region Rendering + SD img2img (same row)
        region_sd_layout = QHBoxLayout()
        region_sd_layout.setSpacing(10)

        self.region_rendering_checkbox = QCheckBox("Region Map")
        self.region_rendering_checkbox.setFixedHeight(16)  # Match slider height for consistent spacing
        self.region_rendering_checkbox.setChecked(True)  # Default enabled
        self.region_rendering_checkbox.stateChanged.connect(self._on_region_rendering_toggle)
        region_sd_layout.addWidget(self.region_rendering_checkbox)

        self.sd_checkbox = QCheckBox("SD img2img")
        self.sd_checkbox.setFixedHeight(16)  # Match slider height for consistent spacing
        self.sd_checkbox.setChecked(False)
        self.sd_checkbox.stateChanged.connect(self._on_sd_toggle)
        region_sd_layout.addWidget(self.sd_checkbox)
        region_sd_layout.addStretch()

        region_sd_widget = QWidget()
        region_sd_widget.setLayout(region_sd_layout)
        grid.addWidget(region_sd_widget, row2, COL2, 1, 3)
        row2 += 1

        # SD Prompt (multiline text area, no label)
        self.sd_prompt_edit = QTextEdit()
        # Height = 1 row (16px slider) + 1 spacing (10px) + 1 row (16px) = 42px for clean 2-row span
        self.sd_prompt_edit.setFixedHeight(42)
        self.sd_prompt_edit.setPlainText("artistic style, abstract, monochrome ink painting, high quality")
        self.sd_prompt_edit.textChanged.connect(self._on_sd_prompt_changed)
        grid.addWidget(self.sd_prompt_edit, row2, COL2, 2, 3)  # Span 2 rows, 3 columns
        row2 += 2

        # SD Steps
        grid.addWidget(QLabel("Steps"), row2, COL2)
        self.sd_steps_slider = QSlider(Qt.Orientation.Horizontal)
        self.sd_steps_slider.setFixedHeight(16)
        self.sd_steps_slider.setFixedWidth(120)
        self._apply_slider_style(self.sd_steps_slider, COLOR_COL2)
        self.sd_steps_slider.setMinimum(1)
        self.sd_steps_slider.setMaximum(20)
        self.sd_steps_slider.setValue(2)
        self.sd_steps_slider.valueChanged.connect(self._on_sd_steps_changed)
        self._make_slider_learnable(self.sd_steps_slider, "sd_steps", self._on_sd_steps_changed)
        grid.addWidget(self.sd_steps_slider, row2, COL2 + 1)
        self.sd_steps_label = QLabel("2")
        self.sd_steps_label.setFixedWidth(25)
        grid.addWidget(self.sd_steps_label, row2, COL2 + 2)
        row2 += 1

        # SD Strength
        grid.addWidget(QLabel("Strength"), row2, COL2)
        self.sd_strength_slider = QSlider(Qt.Orientation.Horizontal)
        self.sd_strength_slider.setFixedHeight(16)
        self.sd_strength_slider.setFixedWidth(120)
        self._apply_slider_style(self.sd_strength_slider, COLOR_COL2)
        self.sd_strength_slider.setMinimum(50)
        self.sd_strength_slider.setMaximum(100)
        self.sd_strength_slider.setValue(50)
        self.sd_strength_slider.valueChanged.connect(self._on_sd_strength_changed)
        self._make_slider_learnable(self.sd_strength_slider, "sd_strength", self._on_sd_strength_changed)
        grid.addWidget(self.sd_strength_slider, row2, COL2 + 1)
        self.sd_strength_label = QLabel("0.50")
        self.sd_strength_label.setFixedWidth(30)
        grid.addWidget(self.sd_strength_label, row2, COL2 + 2)
        row2 += 1

        # SD Guidance
        grid.addWidget(QLabel("Guidance"), row2, COL2)
        self.sd_guidance_slider = QSlider(Qt.Orientation.Horizontal)
        self.sd_guidance_slider.setFixedHeight(16)
        self.sd_guidance_slider.setFixedWidth(120)
        self._apply_slider_style(self.sd_guidance_slider, COLOR_COL2)
        self.sd_guidance_slider.setMinimum(10)
        self.sd_guidance_slider.setMaximum(150)
        self.sd_guidance_slider.setValue(10)
        self.sd_guidance_slider.valueChanged.connect(self._on_sd_guidance_changed)
        self._make_slider_learnable(self.sd_guidance_slider, "sd_guidance", self._on_sd_guidance_changed)
        grid.addWidget(self.sd_guidance_slider, row2, COL2 + 1)
        self.sd_guidance_label = QLabel("1.0")
        self.sd_guidance_label.setFixedWidth(30)
        grid.addWidget(self.sd_guidance_label, row2, COL2 + 2)
        row2 += 1

        # SD Gen Interval
        grid.addWidget(QLabel("Gen Interval"), row2, COL2)
        self.sd_interval_edit = QLineEdit("0.5")
        self.sd_interval_edit.setFixedWidth(120)
        self.sd_interval_edit.setFixedHeight(16)  # Match slider height for consistent spacing
        self.sd_interval_edit.textChanged.connect(self._on_sd_interval_changed)
        grid.addWidget(self.sd_interval_edit, row2, COL2 + 1)
        grid.addWidget(QLabel("s"), row2, COL2 + 2)
        row2 += 1

        # ===== COLUMN 3: Multiverse Channels (Ch1-4, vertical layout) =====
        row3 = 0
        self.channel_curve_sliders = []
        self.channel_angle_sliders = []
        self.channel_ratio_sliders = []
        default_angles = [180, 225, 270, 315]

        # Create all 4 channels with vertical layout (Curve, Angle, Ratio in separate rows)
        for i in range(4):
            # Curve
            grid.addWidget(QLabel(f"Ch{i+1} Curve"), row3, COL3)
            curve_slider = QSlider(Qt.Orientation.Horizontal)
            curve_slider.setFixedHeight(16)
            curve_slider.setFixedWidth(120)
            self._apply_slider_style(curve_slider, COLOR_COL3)
            curve_slider.setMinimum(0)
            curve_slider.setMaximum(100)
            curve_slider.setValue(0)
            curve_slider.valueChanged.connect(lambda val, idx=i: self._on_channel_curve_changed(idx, val))
            self._make_slider_learnable(curve_slider, f"ch{i+1}_curve", lambda val, idx=i: self._on_channel_curve_changed(idx, val))
            grid.addWidget(curve_slider, row3, COL3 + 1)
            curve_label = QLabel("0.0")
            curve_label.setFixedWidth(25)
            grid.addWidget(curve_label, row3, COL3 + 2)
            self.channel_curve_sliders.append((curve_slider, curve_label))
            row3 += 1

            # Angle
            grid.addWidget(QLabel(f"Ch{i+1} Angle"), row3, COL3)
            angle_slider = QSlider(Qt.Orientation.Horizontal)
            angle_slider.setFixedHeight(16)
            angle_slider.setFixedWidth(120)
            self._apply_slider_style(angle_slider, COLOR_COL3)
            angle_slider.setMinimum(0)
            angle_slider.setMaximum(360)
            angle_slider.setValue(default_angles[i])
            angle_slider.valueChanged.connect(lambda val, idx=i: self._on_channel_angle_changed(idx, val))
            self._make_slider_learnable(angle_slider, f"ch{i+1}_angle", lambda val, idx=i: self._on_channel_angle_changed(idx, val))
            grid.addWidget(angle_slider, row3, COL3 + 1)
            angle_label = QLabel(f"{default_angles[i]}°")
            angle_label.setFixedWidth(30)
            grid.addWidget(angle_label, row3, COL3 + 2)
            self.channel_angle_sliders.append((angle_slider, angle_label))
            row3 += 1

            # Ratio
            grid.addWidget(QLabel(f"Ch{i+1} Ratio"), row3, COL3)
            ratio_slider = QSlider(Qt.Orientation.Horizontal)
            ratio_slider.setFixedHeight(16)
            ratio_slider.setFixedWidth(120)
            self._apply_slider_style(ratio_slider, COLOR_COL3)
            ratio_slider.setMinimum(5)  # 0.05
            ratio_slider.setMaximum(1000)  # 10.0
            ratio_slider.setValue(5)  # 0.05 default
            ratio_slider.valueChanged.connect(lambda val, idx=i: self._on_channel_ratio_changed(idx, val))
            self._make_slider_learnable(ratio_slider, f"ch{i+1}_ratio", lambda val, idx=i: self._on_channel_ratio_changed(idx, val))
            grid.addWidget(ratio_slider, row3, COL3 + 1)
            ratio_label = QLabel("1.0")
            ratio_label.setFixedWidth(25)
            grid.addWidget(ratio_label, row3, COL3 + 2)
            self.channel_ratio_sliders.append((ratio_slider, ratio_label))
            row3 += 1

        # ===== COLUMN 4: Ellen Ripley Delay+Grain =====
        row4 = 0

        # Ellen Ripley is always enabled (no checkbox)
        # Enable Ellen Ripley immediately during initialization

        # Delay Time L
        grid.addWidget(QLabel("Delay Time L"), row4, COL4)
        self.er_delay_time_l_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_delay_time_l_slider.setFixedHeight(16)
        self.er_delay_time_l_slider.setFixedWidth(120)
        self._apply_slider_style(self.er_delay_time_l_slider, COLOR_COL4)
        self.er_delay_time_l_slider.setMinimum(1)
        self.er_delay_time_l_slider.setMaximum(2000)
        self.er_delay_time_l_slider.setValue(250)
        self.er_delay_time_l_slider.valueChanged.connect(self._on_er_delay_time_l_changed)
        self._make_slider_learnable(self.er_delay_time_l_slider, "er_delay_time_l", self._on_er_delay_time_l_changed)
        grid.addWidget(self.er_delay_time_l_slider, row4, COL4 + 1)
        self.er_delay_time_l_label = QLabel("0.25s")
        self.er_delay_time_l_label.setFixedWidth(35)
        grid.addWidget(self.er_delay_time_l_label, row4, COL4 + 2)
        row4 += 1

        # Delay Time R
        grid.addWidget(QLabel("Delay Time R"), row4, COL4)
        self.er_delay_time_r_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_delay_time_r_slider.setFixedHeight(16)
        self.er_delay_time_r_slider.setFixedWidth(120)
        self._apply_slider_style(self.er_delay_time_r_slider, COLOR_COL4)
        self.er_delay_time_r_slider.setMinimum(1)
        self.er_delay_time_r_slider.setMaximum(2000)
        self.er_delay_time_r_slider.setValue(250)
        self.er_delay_time_r_slider.valueChanged.connect(self._on_er_delay_time_r_changed)
        self._make_slider_learnable(self.er_delay_time_r_slider, "er_delay_time_r", self._on_er_delay_time_r_changed)
        grid.addWidget(self.er_delay_time_r_slider, row4, COL4 + 1)
        self.er_delay_time_r_label = QLabel("0.25s")
        self.er_delay_time_r_label.setFixedWidth(35)
        grid.addWidget(self.er_delay_time_r_label, row4, COL4 + 2)
        row4 += 1

        # Delay FB
        grid.addWidget(QLabel("Delay FB"), row4, COL4)
        self.er_delay_fb_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_delay_fb_slider.setFixedHeight(16)
        self.er_delay_fb_slider.setFixedWidth(120)
        self._apply_slider_style(self.er_delay_fb_slider, COLOR_COL4)
        self.er_delay_fb_slider.setMinimum(0)
        self.er_delay_fb_slider.setMaximum(95)
        self.er_delay_fb_slider.setValue(30)
        self.er_delay_fb_slider.valueChanged.connect(self._on_er_delay_fb_changed)
        self._make_slider_learnable(self.er_delay_fb_slider, "er_delay_fb", self._on_er_delay_fb_changed)
        grid.addWidget(self.er_delay_fb_slider, row4, COL4 + 1)
        self.er_delay_fb_label = QLabel("0.30")
        self.er_delay_fb_label.setFixedWidth(30)
        grid.addWidget(self.er_delay_fb_label, row4, COL4 + 2)
        row4 += 1

        # Delay Mix
        grid.addWidget(QLabel("Dly Mix"), row4, COL4)
        self.er_delay_mix_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_delay_mix_slider.setFixedHeight(16)
        self.er_delay_mix_slider.setFixedWidth(120)
        self._apply_slider_style(self.er_delay_mix_slider, COLOR_COL4)
        self.er_delay_mix_slider.setMinimum(0)
        self.er_delay_mix_slider.setMaximum(100)
        self.er_delay_mix_slider.setValue(0)
        self.er_delay_mix_slider.valueChanged.connect(self._on_er_delay_mix_changed)
        self._make_slider_learnable(self.er_delay_mix_slider, "er_delay_mix", self._on_er_delay_mix_changed)
        grid.addWidget(self.er_delay_mix_slider, row4, COL4 + 1)
        self.er_delay_mix_label = QLabel("0.00")
        self.er_delay_mix_label.setFixedWidth(30)
        grid.addWidget(self.er_delay_mix_label, row4, COL4 + 2)
        row4 += 1


        # Grain Size
        grid.addWidget(QLabel("Grain Size"), row4, COL4)
        self.er_grain_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_grain_size_slider.setFixedHeight(16)
        self.er_grain_size_slider.setFixedWidth(120)
        self._apply_slider_style(self.er_grain_size_slider, COLOR_COL4)
        self.er_grain_size_slider.setMinimum(0)
        self.er_grain_size_slider.setMaximum(100)
        self.er_grain_size_slider.setValue(30)
        self.er_grain_size_slider.valueChanged.connect(self._on_er_grain_size_changed)
        self._make_slider_learnable(self.er_grain_size_slider, "er_grain_size", self._on_er_grain_size_changed)
        grid.addWidget(self.er_grain_size_slider, row4, COL4 + 1)
        self.er_grain_size_label = QLabel("0.30")
        self.er_grain_size_label.setFixedWidth(30)
        grid.addWidget(self.er_grain_size_label, row4, COL4 + 2)
        row4 += 1

        # Grain Density
        grid.addWidget(QLabel("Grain Density"), row4, COL4)
        self.er_grain_density_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_grain_density_slider.setFixedHeight(16)
        self.er_grain_density_slider.setFixedWidth(120)
        self._apply_slider_style(self.er_grain_density_slider, COLOR_COL4)
        self.er_grain_density_slider.setMinimum(0)
        self.er_grain_density_slider.setMaximum(100)
        self.er_grain_density_slider.setValue(40)
        self.er_grain_density_slider.valueChanged.connect(self._on_er_grain_density_changed)
        self._make_slider_learnable(self.er_grain_density_slider, "er_grain_density", self._on_er_grain_density_changed)
        grid.addWidget(self.er_grain_density_slider, row4, COL4 + 1)
        self.er_grain_density_label = QLabel("0.40")
        self.er_grain_density_label.setFixedWidth(30)
        grid.addWidget(self.er_grain_density_label, row4, COL4 + 2)
        row4 += 1

        # Grain Position
        grid.addWidget(QLabel("Grain Position"), row4, COL4)
        self.er_grain_pos_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_grain_pos_slider.setFixedHeight(16)
        self.er_grain_pos_slider.setFixedWidth(120)
        self._apply_slider_style(self.er_grain_pos_slider, COLOR_COL4)
        self.er_grain_pos_slider.setMinimum(0)
        self.er_grain_pos_slider.setMaximum(100)
        self.er_grain_pos_slider.setValue(50)
        self.er_grain_pos_slider.valueChanged.connect(self._on_er_grain_pos_changed)
        self._make_slider_learnable(self.er_grain_pos_slider, "er_grain_pos", self._on_er_grain_pos_changed)
        grid.addWidget(self.er_grain_pos_slider, row4, COL4 + 1)
        self.er_grain_pos_label = QLabel("0.50")
        self.er_grain_pos_label.setFixedWidth(30)
        grid.addWidget(self.er_grain_pos_label, row4, COL4 + 2)
        row4 += 1

        # Grain Mix
        grid.addWidget(QLabel("Grn Mix"), row4, COL4)
        self.er_grain_mix_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_grain_mix_slider.setFixedHeight(16)
        self.er_grain_mix_slider.setFixedWidth(120)
        self._apply_slider_style(self.er_grain_mix_slider, COLOR_COL4)
        self.er_grain_mix_slider.setMinimum(0)
        self.er_grain_mix_slider.setMaximum(100)
        self.er_grain_mix_slider.setValue(0)
        self.er_grain_mix_slider.valueChanged.connect(self._on_er_grain_mix_changed)
        self._make_slider_learnable(self.er_grain_mix_slider, "er_grain_mix", self._on_er_grain_mix_changed)
        grid.addWidget(self.er_grain_mix_slider, row4, COL4 + 1)
        self.er_grain_mix_label = QLabel("0.00")
        self.er_grain_mix_label.setFixedWidth(30)
        grid.addWidget(self.er_grain_mix_label, row4, COL4 + 2)
        row4 += 1


        # ===== COLUMN 6: Ellen Ripley Reverb+Chaos =====
        row5 = 0

        # Reverb Room
        grid.addWidget(QLabel("Reverb Room"), row5, COL5)
        self.er_reverb_room_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_reverb_room_slider.setFixedHeight(16)
        self.er_reverb_room_slider.setFixedWidth(120)
        self._apply_slider_style(self.er_reverb_room_slider, COLOR_COL4)
        self.er_reverb_room_slider.setMinimum(0)
        self.er_reverb_room_slider.setMaximum(100)
        self.er_reverb_room_slider.setValue(50)
        self.er_reverb_room_slider.valueChanged.connect(self._on_er_reverb_room_changed)
        self._make_slider_learnable(self.er_reverb_room_slider, "er_reverb_room", self._on_er_reverb_room_changed)
        grid.addWidget(self.er_reverb_room_slider, row5, COL5 + 1)
        self.er_reverb_room_label = QLabel("0.50")
        self.er_reverb_room_label.setFixedWidth(30)
        grid.addWidget(self.er_reverb_room_label, row5, COL5 + 2)
        row5 += 1

        # Reverb Damping
        grid.addWidget(QLabel("Reverb Damp"), row5, COL5)
        self.er_reverb_damp_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_reverb_damp_slider.setFixedHeight(16)
        self.er_reverb_damp_slider.setFixedWidth(120)
        self._apply_slider_style(self.er_reverb_damp_slider, COLOR_COL4)
        self.er_reverb_damp_slider.setMinimum(0)
        self.er_reverb_damp_slider.setMaximum(100)
        self.er_reverb_damp_slider.setValue(40)
        self.er_reverb_damp_slider.valueChanged.connect(self._on_er_reverb_damp_changed)
        self._make_slider_learnable(self.er_reverb_damp_slider, "er_reverb_damp", self._on_er_reverb_damp_changed)
        grid.addWidget(self.er_reverb_damp_slider, row5, COL5 + 1)
        self.er_reverb_damp_label = QLabel("0.40")
        self.er_reverb_damp_label.setFixedWidth(30)
        grid.addWidget(self.er_reverb_damp_label, row5, COL5 + 2)
        row5 += 1

        # Reverb Decay
        grid.addWidget(QLabel("Reverb Decay"), row5, COL5)
        self.er_reverb_decay_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_reverb_decay_slider.setFixedHeight(16)
        self.er_reverb_decay_slider.setFixedWidth(120)
        self._apply_slider_style(self.er_reverb_decay_slider, COLOR_COL4)
        self.er_reverb_decay_slider.setMinimum(0)
        self.er_reverb_decay_slider.setMaximum(100)
        self.er_reverb_decay_slider.setValue(60)
        self.er_reverb_decay_slider.valueChanged.connect(self._on_er_reverb_decay_changed)
        self._make_slider_learnable(self.er_reverb_decay_slider, "er_reverb_decay", self._on_er_reverb_decay_changed)
        grid.addWidget(self.er_reverb_decay_slider, row5, COL5 + 1)
        self.er_reverb_decay_label = QLabel("0.60")
        self.er_reverb_decay_label.setFixedWidth(30)
        grid.addWidget(self.er_reverb_decay_label, row5, COL5 + 2)
        row5 += 1

        # Reverb Mix
        grid.addWidget(QLabel("Rev Mix"), row5, COL5)
        self.er_reverb_mix_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_reverb_mix_slider.setFixedHeight(16)
        self.er_reverb_mix_slider.setFixedWidth(120)
        self._apply_slider_style(self.er_reverb_mix_slider, COLOR_COL4)
        self.er_reverb_mix_slider.setMinimum(0)
        self.er_reverb_mix_slider.setMaximum(100)
        self.er_reverb_mix_slider.setValue(0)
        self.er_reverb_mix_slider.valueChanged.connect(self._on_er_reverb_mix_changed)
        self._make_slider_learnable(self.er_reverb_mix_slider, "er_reverb_mix", self._on_er_reverb_mix_changed)
        grid.addWidget(self.er_reverb_mix_slider, row5, COL5 + 1)
        self.er_reverb_mix_label = QLabel("0.00")
        self.er_reverb_mix_label.setFixedWidth(30)
        grid.addWidget(self.er_reverb_mix_label, row5, COL5 + 2)
        row5 += 1

        # Chaos Rate
        grid.addWidget(QLabel("Chaos Rate"), row5, COL5)
        self.er_chaos_rate_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_chaos_rate_slider.setFixedHeight(16)
        self.er_chaos_rate_slider.setFixedWidth(120)
        self._apply_slider_style(self.er_chaos_rate_slider, COLOR_COL4)
        self.er_chaos_rate_slider.setMinimum(0)
        self.er_chaos_rate_slider.setMaximum(100)
        self.er_chaos_rate_slider.setValue(1)
        self.er_chaos_rate_slider.valueChanged.connect(self._on_er_chaos_rate_changed)
        self._make_slider_learnable(self.er_chaos_rate_slider, "er_chaos_rate", self._on_er_chaos_rate_changed)
        grid.addWidget(self.er_chaos_rate_slider, row5, COL5 + 1)
        self.er_chaos_rate_label = QLabel("0.01")
        self.er_chaos_rate_label.setFixedWidth(30)
        grid.addWidget(self.er_chaos_rate_label, row5, COL5 + 2)
        row5 += 1

        # Chaos Amount
        grid.addWidget(QLabel("Chaos Amount"), row5, COL5)
        self.er_chaos_amount_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_chaos_amount_slider.setFixedHeight(16)
        self.er_chaos_amount_slider.setFixedWidth(120)
        self._apply_slider_style(self.er_chaos_amount_slider, COLOR_COL4)
        self.er_chaos_amount_slider.setMinimum(0)
        self.er_chaos_amount_slider.setMaximum(100)
        self.er_chaos_amount_slider.setValue(100)
        self.er_chaos_amount_slider.valueChanged.connect(self._on_er_chaos_amount_changed)
        self._make_slider_learnable(self.er_chaos_amount_slider, "er_chaos_amount", self._on_er_chaos_amount_changed)
        grid.addWidget(self.er_chaos_amount_slider, row5, COL5 + 1)
        self.er_chaos_amount_label = QLabel("1.00")
        self.er_chaos_amount_label.setFixedWidth(30)
        grid.addWidget(self.er_chaos_amount_label, row5, COL5 + 2)
        row5 += 1

        # Chaos toggles in two rows
        # First row: Delay Chaos, Grain Chaos
        chaos_row1_layout = QHBoxLayout()
        chaos_row1_layout.setSpacing(5)

        self.er_delay_chaos_checkbox = QCheckBox("Dly Chaos")
        self.er_delay_chaos_checkbox.setFixedHeight(16)
        self.er_delay_chaos_checkbox.stateChanged.connect(self._on_er_delay_chaos_changed)
        chaos_row1_layout.addWidget(self.er_delay_chaos_checkbox)

        self.er_grain_chaos_checkbox = QCheckBox("Grn Chaos")
        self.er_grain_chaos_checkbox.setFixedHeight(16)
        self.er_grain_chaos_checkbox.setChecked(True)  # Default ON
        self.er_grain_chaos_checkbox.stateChanged.connect(self._on_er_grain_chaos_changed)
        chaos_row1_layout.addWidget(self.er_grain_chaos_checkbox)

        chaos_row1_layout.addStretch()

        chaos_row1_widget = QWidget()
        chaos_row1_widget.setLayout(chaos_row1_layout)
        grid.addWidget(chaos_row1_widget, row5, COL5, 1, 3)
        row5 += 1

        # Second row: Reverb Chaos, Chaos Shape
        chaos_row2_layout = QHBoxLayout()
        chaos_row2_layout.setSpacing(5)

        self.er_reverb_chaos_checkbox = QCheckBox("Rev Chaos")
        self.er_reverb_chaos_checkbox.setFixedHeight(16)
        self.er_reverb_chaos_checkbox.stateChanged.connect(self._on_er_reverb_chaos_changed)
        chaos_row2_layout.addWidget(self.er_reverb_chaos_checkbox)

        self.er_chaos_shape_checkbox = QCheckBox("Chaos Shape")
        self.er_chaos_shape_checkbox.setFixedHeight(16)
        self.er_chaos_shape_checkbox.stateChanged.connect(self._on_er_chaos_shape_changed)
        chaos_row2_layout.addWidget(self.er_chaos_shape_checkbox)

        chaos_row2_layout.addStretch()

        chaos_row2_widget = QWidget()
        chaos_row2_widget.setLayout(chaos_row2_layout)
        grid.addWidget(chaos_row2_widget, row5, COL5, 1, 3)
        row5 += 1

        # Anchor XY Pad (no label)
        self.anchor_xy_pad = AnchorXYPad()
        self.anchor_xy_pad.position_changed.connect(self._on_anchor_xy_changed)
        grid.addWidget(self.anchor_xy_pad, row5, COL4, 3, 3)  # Span 3 rows, 3 columns

        # Register Anchor X/Y for MIDI Learn
        def anchor_x_midi_callback(value):
            self.anchor_xy_pad.set_position(value, self.anchor_xy_pad.y_pct, emit_signal=True)

        def anchor_y_midi_callback(value):
            # Invert Y: MIDI 0-100 → GUI 100-0
            inverted_y = 100.0 - value
            self.anchor_xy_pad.set_position(self.anchor_xy_pad.x_pct, inverted_y, emit_signal=True)

        self.midi_learn.register_parameter("anchor_x", anchor_x_midi_callback, 0.0, 100.0)
        self.midi_learn.register_parameter("anchor_y", anchor_y_midi_callback, 0.0, 100.0)

        # Add context menu for XY Pad
        def show_xy_context_menu(pos):
            menu = QMenu()
            learn_x_action = menu.addAction("MIDI Learn X")
            learn_y_action = menu.addAction("MIDI Learn Y")
            menu.addSeparator()
            clear_x_action = menu.addAction("Clear X Mapping")
            clear_y_action = menu.addAction("Clear Y Mapping")
            menu.addSeparator()
            clear_all_action = menu.addAction("Clear All MIDI Mappings")

            action = menu.exec(self.anchor_xy_pad.mapToGlobal(pos))

            if action == learn_x_action:
                self.midi_learn.enter_learn_mode("anchor_x")
            elif action == learn_y_action:
                self.midi_learn.enter_learn_mode("anchor_y")
            elif action == clear_x_action:
                self.midi_learn.clear_mapping("anchor_x")
            elif action == clear_y_action:
                self.midi_learn.clear_mapping("anchor_y")
            elif action == clear_all_action:
                self.midi_learn.clear_all_mappings()

        self.anchor_xy_pad.customContextMenuRequested.connect(show_xy_context_menu)

        row5 += 3

    def _build_cv_column(self) -> QWidget:
        """Build CV controls column"""
        widget = QGroupBox("CV")
        layout = QGridLayout(widget)
        layout.setSpacing(2)
        layout.setContentsMargins(3, 3, 3, 3)

        # Compact sliders for ENVs
        self.env_sliders = []
        for i in range(3):
            label = QLabel(f"E{i+1}")
            label.setFixedWidth(20)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setFixedHeight(18)
            slider.setMinimum(10)
            slider.setMaximum(10000)
            slider.setValue(1000)
            slider.valueChanged.connect(
                lambda val, idx=i: self._on_env_decay_changed(idx, val)
            )
            value_label = QLabel("1.0s")
            value_label.setFixedWidth(35)
            self.env_sliders.append((slider, value_label))

            layout.addWidget(label, i, 0)
            layout.addWidget(slider, i, 1)
            layout.addWidget(value_label, i, 2)

        # Compact sliders for SEQs
        self.seq_steps_spinners = []

        for i in range(2):
            row = 3 + i

            # Steps
            label = QLabel(f"S{i+1}St")
            label.setFixedWidth(30)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setFixedHeight(18)
            slider.setMinimum(4)
            slider.setMaximum(32)
            slider.setValue(8)
            slider.valueChanged.connect(
                lambda val, idx=i: self._on_seq_steps_changed(idx, val)
            )
            value = QLabel("8")
            value.setFixedWidth(25)
            self.seq_steps_spinners.append((slider, value))

            layout.addWidget(label, row, 0)
            layout.addWidget(slider, row, 1)
            layout.addWidget(value, row, 2)

        # Unified Clock BPM
        label = QLabel("BPM")
        label.setFixedWidth(30)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setFixedHeight(18)
        slider.setMinimum(1)
        slider.setMaximum(999)
        slider.setValue(120)
        slider.valueChanged.connect(self._on_clock_rate_changed)
        value = QLabel("120")
        value.setFixedWidth(25)
        self.clock_slider = (slider, value)
        layout.addWidget(label, 5, 0)
        layout.addWidget(slider, 5, 1)
        layout.addWidget(value, 5, 2)

        # Anchor X
        label = QLabel("AncX")
        label.setFixedWidth(30)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setFixedHeight(18)
        slider.setMinimum(0)
        slider.setMaximum(100)
        slider.setValue(50)
        slider.valueChanged.connect(self._on_anchor_x_changed)
        value = QLabel("50%")
        value.setFixedWidth(25)
        self.anchor_x_slider = (slider, value)
        layout.addWidget(label, 6, 0)
        layout.addWidget(slider, 6, 1)
        layout.addWidget(value, 6, 2)

        # Anchor Y
        label = QLabel("AncY")
        label.setFixedWidth(30)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setFixedHeight(18)
        slider.setMinimum(0)
        slider.setMaximum(100)
        slider.setValue(50)
        slider.valueChanged.connect(self._on_anchor_y_changed)
        value = QLabel("50%")
        value.setFixedWidth(25)
        self.anchor_y_slider = (slider, value)
        layout.addWidget(label, 7, 0)
        layout.addWidget(slider, 7, 1)
        layout.addWidget(value, 7, 2)

        # Range
        label = QLabel("Rng")
        label.setFixedWidth(30)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setFixedHeight(18)
        slider.setMinimum(1)
        slider.setMaximum(120)
        slider.setValue(50)
        slider.valueChanged.connect(self._on_range_changed)
        value = QLabel("50%")
        value.setFixedWidth(25)
        self.range_slider = (slider, value)
        layout.addWidget(label, 8, 0)
        layout.addWidget(slider, 8, 1)
        layout.addWidget(value, 8, 2)

        # Edge Threshold
        label = QLabel("Thrs")
        label.setFixedWidth(30)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setFixedHeight(18)
        slider.setMinimum(0)
        slider.setMaximum(255)
        slider.setValue(50)
        slider.valueChanged.connect(self._on_threshold_changed)
        value = QLabel("50")
        value.setFixedWidth(25)
        self.threshold_slider = (slider, value)
        layout.addWidget(label, 9, 0)
        layout.addWidget(slider, 9, 1)
        layout.addWidget(value, 9, 2)

        # Smoothing
        label = QLabel("Smth")
        label.setFixedWidth(30)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setFixedHeight(18)
        slider.setMinimum(0)
        slider.setMaximum(100)
        slider.setValue(50)
        slider.valueChanged.connect(self._on_smoothing_changed)
        value = QLabel("50")
        value.setFixedWidth(25)
        self.smoothing_slider = (slider, value)
        layout.addWidget(label, 10, 0)
        layout.addWidget(slider, 10, 1)
        layout.addWidget(value, 10, 2)

        return widget

    def _build_mixer_effects_column(self) -> QWidget:
        """Build mixer and effects column"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(3)
        layout.setContentsMargins(0, 0, 0, 0)

        # Compact mixer
        mixer_group = QGroupBox("Mix")
        mixer_layout = QGridLayout(mixer_group)
        mixer_layout.setSpacing(2)
        mixer_layout.setContentsMargins(3, 3, 3, 3)

        self.mixer_sliders = []
        for i in range(4):
            label = QLabel(f"T{i+1}")
            label.setFixedWidth(20)

            vol_slider = QSlider(Qt.Orientation.Horizontal)
            vol_slider.setFixedHeight(18)
            vol_slider.setMinimum(0)
            vol_slider.setMaximum(100)
            vol_slider.setValue(80)
            vol_slider.valueChanged.connect(
                lambda val, idx=i: self._on_mixer_volume(idx, val / 100.0)
            )

            vol_label = QLabel("0.8")
            vol_label.setFixedWidth(28)

            self.mixer_sliders.append((vol_slider, vol_label))

            mixer_layout.addWidget(label, i, 0)
            mixer_layout.addWidget(vol_slider, i, 1)
            mixer_layout.addWidget(vol_label, i, 2)

        layout.addWidget(mixer_group)

        # Compact effects
        fx_group = QGroupBox("FX")
        fx_layout = QGridLayout(fx_group)
        fx_layout.setSpacing(2)
        fx_layout.setContentsMargins(3, 3, 3, 3)

        # Delay
        delay_label = QLabel("Dly")
        delay_label.setFixedWidth(25)
        fx_layout.addWidget(delay_label, 0, 0)
        self.delay_time_slider = QSlider(Qt.Orientation.Horizontal)
        self.delay_time_slider.setFixedHeight(18)
        self.delay_time_slider.setMinimum(10)
        self.delay_time_slider.setMaximum(2000)
        self.delay_time_slider.setValue(250)
        self.delay_time_slider.valueChanged.connect(self._on_delay_time_changed)
        self.delay_time_label = QLabel("0.25s")
        self.delay_time_label.setFixedWidth(35)
        fx_layout.addWidget(self.delay_time_slider, 0, 1)
        fx_layout.addWidget(self.delay_time_label, 0, 2)

        fb_label = QLabel("FB")
        fb_label.setFixedWidth(25)
        fx_layout.addWidget(fb_label, 1, 0)
        self.delay_feedback_slider = QSlider(Qt.Orientation.Horizontal)
        self.delay_feedback_slider.setFixedHeight(18)
        self.delay_feedback_slider.setMinimum(0)
        self.delay_feedback_slider.setMaximum(95)
        self.delay_feedback_slider.setValue(30)
        self.delay_feedback_slider.valueChanged.connect(self._on_delay_feedback_changed)
        self.delay_feedback_label = QLabel("0.30")
        self.delay_feedback_label.setFixedWidth(35)
        fx_layout.addWidget(self.delay_feedback_slider, 1, 1)
        fx_layout.addWidget(self.delay_feedback_label, 1, 2)

        # Grain
        grain_label = QLabel("Grn")
        grain_label.setFixedWidth(25)
        fx_layout.addWidget(grain_label, 2, 0)
        self.grain_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.grain_size_slider.setFixedHeight(18)
        self.grain_size_slider.setMinimum(0)
        self.grain_size_slider.setMaximum(100)
        self.grain_size_slider.setValue(30)
        self.grain_size_slider.valueChanged.connect(self._on_grain_size_changed)
        self.grain_size_label = QLabel("0.30")
        self.grain_size_label.setFixedWidth(35)
        fx_layout.addWidget(self.grain_size_slider, 2, 1)
        fx_layout.addWidget(self.grain_size_label, 2, 2)

        # Reverb
        rev_label = QLabel("Rev")
        rev_label.setFixedWidth(25)
        fx_layout.addWidget(rev_label, 3, 0)
        self.reverb_room_slider = QSlider(Qt.Orientation.Horizontal)
        self.reverb_room_slider.setFixedHeight(18)
        self.reverb_room_slider.setMinimum(0)
        self.reverb_room_slider.setMaximum(100)
        self.reverb_room_slider.setValue(50)
        self.reverb_room_slider.valueChanged.connect(self._on_reverb_room_changed)
        self.reverb_room_label = QLabel("0.50")
        self.reverb_room_label.setFixedWidth(35)
        fx_layout.addWidget(self.reverb_room_slider, 3, 1)
        fx_layout.addWidget(self.reverb_room_label, 3, 2)

        layout.addWidget(fx_group)

        return widget

    def _build_settings_column(self) -> QWidget:
        """Build settings column"""
        widget = QGroupBox("Set")
        layout = QVBoxLayout(widget)
        layout.setSpacing(3)
        layout.setContentsMargins(3, 3, 3, 3)

        self.device_status_label = QLabel("No devices")
        self.device_status_label.setWordWrap(True)
        self.device_status_label.setStyleSheet("font-size: 8pt;")
        layout.addWidget(self.device_status_label)

        return widget

    # Event handlers
    def _on_start(self):
        # Check if devices are configured
        if not self.controller.audio_io or \
           self.controller.audio_io.input_device is None or \
           self.controller.audio_io.output_device is None:
            # Show device selection dialog
            print("[MainWindow] No devices configured, showing device dialog...")
            self._on_select_devices()

            # Check again after device selection
            if not self.controller.audio_io or \
               self.controller.audio_io.input_device is None or \
               self.controller.audio_io.output_device is None:
                print("[MainWindow] Still no devices configured, cannot start")
                self.status_label.setText("No devices selected")
                return

        # Start the system
        try:
            self.controller.start()
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.status_label.setText("Running")
            self._update_device_status()  # Update device status when starting
        except Exception as e:
            print(f"[MainWindow] Failed to start: {e}")
            self.status_label.setText(f"Start failed: {e}")
            import traceback
            traceback.print_exc()

    def _on_stop(self):
        self.controller.stop()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText("Stopped")

    def _on_show_video(self):
        if self.video_window.isVisible():
            self.video_window.hide()
            self.show_video_btn.setText("Video")
        else:
            self.video_window.show()
            self.show_video_btn.setText("Hide Video")

    def _on_env_global_decay_changed(self, value: int):
        """Global ENV decay with exponential mapping
        0-50: 0.1s ~ 1s
        50-100: 1s ~ 5s
        """
        import numpy as np
        if value <= 50:
            # First half: exponential 0.1 ~ 1.0
            t = value / 50.0
            decay_time = 0.1 * (10.0 ** t)
        else:
            # Second half: exponential 1.0 ~ 5.0
            t = (value - 50) / 50.0
            decay_time = 1.0 * (5.0 ** t)

        # Set all envelopes
        self.controller.set_global_env_decay(decay_time)
        self.env_global_label.setText(f"{decay_time:.2f}s")

    def _on_clock_rate_changed(self, value: int):
        """Scan time in seconds"""
        scan_time = value / 20.0  # 2-600 -> 0.1-30s
        self.controller.set_scan_time(scan_time)
        _, label = self.clock_slider
        label.setText(f"{scan_time:.1f}s")

    def _on_anchor_xy_changed(self, x_pct: float, y_pct: float):
        """Anchor XY position changed from 2D pad"""
        print(f"🎮 2D PAD: Anchor position changed to ({x_pct:.1f}%, {y_pct:.1f}%)")
        self.controller.set_anchor_position(x_pct, y_pct)

    def _on_range_changed(self, value: int):
        """Sampling range from anchor (1-120%)"""
        self.controller.set_cv_range(float(value))
        _, label = self.range_slider
        label.setText(f"{value}%")
        # Update XY Pad to show ROI circle
        self.anchor_xy_pad.set_range(float(value))

    def _on_threshold_changed(self, value: int):
        """Edge detection threshold (0-255)"""
        self.controller.set_edge_threshold(value)
        _, label = self.threshold_slider
        label.setText(str(value))

    def _on_smoothing_changed(self, value: int):
        """Temporal smoothing (0-100)"""
        self.controller.set_cv_smoothing(value)
        _, label = self.smoothing_slider
        label.setText(str(value))

    def _on_mixer_volume(self, track: int, value: float):
        """Track volume changed - affects BOTH Multiverse intensity and Ellen Ripley mix level"""
        # Set Multiverse visual intensity
        if self.controller:
            self.controller.set_renderer_channel_intensity(track, value)
            # Set Ellen Ripley mix level
            self.controller.set_channel_level(track, value)
        # Update label
        _, label = self.mixer_sliders[track]
        label.setText(f"{value:.1f}")

    def _on_select_devices(self):
        import sounddevice as sd

        # Get current device configuration
        current_devices = {
            'audio_input': self.controller.audio_io.input_device,
            'audio_output': self.controller.audio_io.output_device,
            'camera_input': self.controller.camera.device_id,
            'camera_output': None,
        }
        print(f"[MainWindow] Current devices: {current_devices}")

        # Open dialog with current devices pre-selected
        devices = DeviceSelectionDialog.select_devices(self, current_devices=current_devices)
        print(f"[MainWindow] Received devices from dialog: {devices}")
        if devices:
            # If system is running, stop it first
            was_running = self.controller.running
            if was_running:
                print("Stopping system to change devices...")
                self.controller.stop()
                self.start_btn.setEnabled(True)
                self.stop_btn.setEnabled(False)

            # Apply device changes
            try:
                # Set audio devices (will auto-restart stream if running)
                if devices['audio_input'] is not None or devices['audio_output'] is not None:
                    print(f"Setting audio devices: in={devices['audio_input']}, out={devices['audio_output']}")
                    self.controller.audio_io.set_devices(
                        input_device=devices['audio_input'],
                        output_device=devices['audio_output'],
                    )

                # Set camera device (just update device_id, don't open yet)
                # controller.start() will handle opening the camera
                if devices['camera_input'] is not None and devices['camera_input'] != self.controller.camera.device_id:
                    print(f"Setting camera device: {devices['camera_input']}")
                    self.controller.camera.device_id = devices['camera_input']
                    print(f"  Camera device_id updated to {devices['camera_input']}")

                # Update device status display
                self._update_device_status()

                # Show confirmation message and restart if needed
                if was_running:
                    print("Restarting system with new devices...")
                    self._on_start()
                    self.status_label.setText("Devices updated and restarted")
                else:
                    self.status_label.setText("Devices updated - ready to start")

            except Exception as e:
                print(f"Error setting devices: {e}")
                import traceback
                traceback.print_exc()
                self.status_label.setText(f"Error setting devices: {e}")
                # If restart failed, ensure UI state is correct
                if was_running:
                    self.start_btn.setEnabled(True)
                    self.stop_btn.setEnabled(False)

    def _update_device_status(self):
        """Update device status display with current devices"""
        import sounddevice as sd
        from ..vision.camera import get_camera_name

        status_lines = []
        try:
            all_devices = sd.query_devices()

            # Audio input
            if self.controller.audio_io and self.controller.audio_io.input_device is not None:
                dev = all_devices[self.controller.audio_io.input_device]
                status_lines.append(f"In: {dev['name']}")

            # Audio output
            if self.controller.audio_io and self.controller.audio_io.output_device is not None:
                dev = all_devices[self.controller.audio_io.output_device]
                status_lines.append(f"Out: {dev['name']}")
        except Exception as e:
            # Fallback to device ID if name lookup fails
            if self.controller.audio_io and self.controller.audio_io.input_device is not None:
                status_lines.append(f"In: Device {self.controller.audio_io.input_device}")
            if self.controller.audio_io and self.controller.audio_io.output_device is not None:
                status_lines.append(f"Out: Device {self.controller.audio_io.output_device}")

        # Camera input
        if self.controller.camera and self.controller.camera.device_id is not None:
            try:
                # Get camera name
                cam_name = get_camera_name(self.controller.camera.device_id)

                # Get resolution
                import cv2
                cap = cv2.VideoCapture(self.controller.camera.device_id)
                if cap.isOpened():
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    status_lines.append(f"{cam_name}: {width}x{height}")
                    cap.release()
                else:
                    status_lines.append(f"{cam_name}")
            except Exception as e:
                # Fallback
                status_lines.append(f"Camera {self.controller.camera.device_id}")

        if status_lines:
            self.device_status_label.setText(" | ".join(status_lines))
        else:
            self.device_status_label.setText("No devices")

    def _on_toggle_virtual_camera(self, checked: bool):
        if checked:
            success = self.controller.enable_virtual_camera()
            if not success:
                self.vcam_btn.setChecked(False)
                self.status_label.setText("Failed to enable virtual camera")
            else:
                self.status_label.setText("Virtual camera enabled")
        else:
            self.controller.disable_virtual_camera()
            self.status_label.setText("Virtual camera disabled")

    def _on_multiverse_toggle(self, state: int):
        enabled = (state == Qt.CheckState.Checked.value)
        self.controller.enable_multiverse_rendering(enabled)
        mode = "Multiverse" if enabled else "Simple"
        self.status_label.setText(f"Rendering: {mode}")

    def _on_blend_mode_changed(self, value: int):
        # Convert 0-100 to 0.0-1.0 for continuous blend
        blend_value = value / 100.0
        self.controller.set_renderer_blend_mode(blend_value)

    def _on_color_scheme_changed(self, value: int):
        # Convert 0-100 to 0.0-1.0 for continuous color scheme blend
        scheme_value = value / 100.0
        self.controller.set_color_scheme(scheme_value)

    def _on_brightness_changed(self, value: int):
        brightness = value / 100.0
        self.brightness_label.setText(f"{brightness:.1f}")
        self.controller.set_renderer_brightness(brightness)

    def _on_base_hue_changed(self, value: int):
        hue = value / 333.0  # Convert 0-333 to 0.0-1.0
        self.base_hue_label.setText(f"{value}")
        self.controller.set_renderer_base_hue(hue)

    def _on_region_rendering_toggle(self, state: int):
        """Toggle region-based rendering - fixed to brightness mode"""
        enabled = state == Qt.CheckState.Checked.value
        self.controller.enable_region_rendering(enabled)
        # Always set mode to brightness
        if enabled:
            self.controller.set_region_mode('brightness')
        status = "Region ON" if enabled else "Region OFF"
        self.status_label.setText(status)

    def _on_region_mode_changed(self, index: int):
        """Change region rendering mode - FIXED to brightness only"""
        # Region mode is now fixed to 'brightness'
        # This method is kept for compatibility but does nothing
        pass

    def _on_channel_curve_changed(self, channel: int, value: int):
        """Channel curve changed"""
        curve = value / 100.0
        _, label = self.channel_curve_sliders[channel]
        label.setText(f"{curve:.1f}")
        self.controller.set_renderer_channel_curve(channel, curve)

    def _on_channel_angle_changed(self, channel: int, value: int):
        """Channel angle changed"""
        _, label = self.channel_angle_sliders[channel]
        label.setText(f"{value}°")
        # Map 0-360 to -180 to +180 (like original Multiverse)
        mapped_angle = float(value) - 180.0
        self.controller.set_renderer_channel_angle(channel, mapped_angle)

    def _on_channel_ratio_changed(self, channel: int, value: int):
        """Channel ratio changed"""
        ratio = value / 100.0
        _, label = self.channel_ratio_sliders[channel]
        label.setText(f"{ratio:.1f}")
        self.controller.set_renderer_channel_ratio(channel, ratio)

    def _on_camera_mix_changed(self, value: int):
        """Camera mix changed"""
        camera_mix = value / 100.0  # 0-30 slider -> 0.0-0.3
        self.camera_mix_label.setText(f"{camera_mix:.2f}")
        self.controller.set_renderer_camera_mix(camera_mix)

    # Ellen Ripley event handlers
    def _on_ellen_ripley_toggle(self, state: int):
        enabled = state == 2
        self.controller.enable_ellen_ripley(enabled)
        self.status_label.setText(f"Ellen Ripley: {'ON' if enabled else 'OFF'}")

    def _on_er_delay_time_l_changed(self, value: int):
        time_s = value / 1000.0
        self.er_delay_time_l_label.setText(f"{time_s:.2f}s")
        self.controller.set_ellen_ripley_delay_params(time_l=time_s)

    def _on_er_delay_time_r_changed(self, value: int):
        time_s = value / 1000.0
        self.er_delay_time_r_label.setText(f"{time_s:.2f}s")
        self.controller.set_ellen_ripley_delay_params(time_r=time_s)

    def _on_er_delay_fb_changed(self, value: int):
        fb = value / 100.0
        self.er_delay_fb_label.setText(f"{fb:.2f}")
        self.controller.set_ellen_ripley_delay_params(feedback=fb)

    def _on_er_delay_chaos_changed(self, state: int):
        enabled = state == 2
        self.controller.set_ellen_ripley_delay_params(chaos_enabled=enabled)

    def _on_er_delay_mix_changed(self, value: int):
        mix = value / 100.0
        self.er_delay_mix_label.setText(f"{mix:.2f}")
        self.controller.set_ellen_ripley_delay_params(wet_dry=mix)

    def _on_er_grain_size_changed(self, value: int):
        size = value / 100.0
        self.er_grain_size_label.setText(f"{size:.2f}")
        self.controller.set_ellen_ripley_grain_params(size=size)

    def _on_er_grain_density_changed(self, value: int):
        density = value / 100.0
        self.er_grain_density_label.setText(f"{density:.2f}")
        self.controller.set_ellen_ripley_grain_params(density=density)

    def _on_er_grain_pos_changed(self, value: int):
        pos = value / 100.0
        self.er_grain_pos_label.setText(f"{pos:.2f}")
        self.controller.set_ellen_ripley_grain_params(position=pos)

    def _on_er_grain_chaos_changed(self, state: int):
        enabled = state == 2
        self.controller.set_ellen_ripley_grain_params(chaos_enabled=enabled)

    def _on_er_grain_mix_changed(self, value: int):
        mix = value / 100.0
        self.er_grain_mix_label.setText(f"{mix:.2f}")
        self.controller.set_ellen_ripley_grain_params(wet_dry=mix)

    def _on_er_reverb_room_changed(self, value: int):
        room = value / 100.0
        self.er_reverb_room_label.setText(f"{room:.2f}")
        self.controller.set_ellen_ripley_reverb_params(room_size=room)

    def _on_er_reverb_damp_changed(self, value: int):
        damp = value / 100.0
        self.er_reverb_damp_label.setText(f"{damp:.2f}")
        self.controller.set_ellen_ripley_reverb_params(damping=damp)

    def _on_er_reverb_decay_changed(self, value: int):
        decay = value / 100.0
        self.er_reverb_decay_label.setText(f"{decay:.2f}")
        self.controller.set_ellen_ripley_reverb_params(decay=decay)

    def _on_er_reverb_chaos_changed(self, state: int):
        enabled = state == 2
        self.controller.set_ellen_ripley_reverb_params(chaos_enabled=enabled)

    def _on_er_reverb_mix_changed(self, value: int):
        mix = value / 100.0
        self.er_reverb_mix_label.setText(f"{mix:.2f}")
        self.controller.set_ellen_ripley_reverb_params(wet_dry=mix)

    def _on_er_chaos_rate_changed(self, value: int):
        rate = value / 100.0
        self.er_chaos_rate_label.setText(f"{rate:.2f}")
        self.controller.set_ellen_ripley_chaos_params(rate=rate)

    def _on_er_chaos_amount_changed(self, value: int):
        amount = value / 100.0
        self.er_chaos_amount_label.setText(f"{amount:.2f}")
        self.controller.set_ellen_ripley_chaos_params(amount=amount)

    def _on_er_chaos_shape_changed(self, state: int):
        shape = state == 2
        self.controller.set_ellen_ripley_chaos_params(shape=shape)

    # SD img2img controls
    def _on_sd_toggle(self, state: int):
        """SD img2img enable/disable"""
        enabled = state == 2
        if hasattr(self.controller, "set_sd_enabled"):
            self.controller.set_sd_enabled(enabled)
        else:
            status = "enabled" if enabled else "disabled"
            print(f"SD img2img {status} (not yet implemented in controller)")

    def _on_sd_prompt_changed(self):
        """SD prompt changed"""
        prompt = self.sd_prompt_edit.toPlainText()
        if hasattr(self.controller, "set_sd_prompt"):
            self.controller.set_sd_prompt(prompt)

    def _on_sd_steps_changed(self, value: int):
        """SD steps changed"""
        self.sd_steps_label.setText(str(value))
        if hasattr(self.controller, "set_sd_parameters"):
            self.controller.set_sd_parameters(num_steps=value)

    def _on_sd_strength_changed(self, value: int):
        """SD strength changed"""
        strength = value / 100.0
        self.sd_strength_label.setText(f"{strength:.2f}")
        if hasattr(self.controller, "set_sd_parameters"):
            self.controller.set_sd_parameters(strength=strength)

    def _on_sd_guidance_changed(self, value: int):
        """SD guidance changed"""
        guidance = value / 10.0
        self.sd_guidance_label.setText(f"{guidance:.1f}")
        if hasattr(self.controller, "set_sd_parameters"):
            self.controller.set_sd_parameters(guidance_scale=guidance)

    def _on_sd_interval_changed(self, text: str):
        """SD generation interval changed"""
        try:
            interval = float(text)
            if hasattr(self.controller, "set_sd_interval"):
                self.controller.set_sd_interval(interval)
        except ValueError:
            pass

    # Controller callbacks
    def _on_frame(self, frame: np.ndarray):
        self.frame_updated.emit(frame)

    def _on_cv(self, cv_values: np.ndarray):
        self.cv_updated.emit(cv_values)

    def _on_visual(self, visual_params: dict):
        self.visual_updated.emit(visual_params)

    def _on_param(self, param_name: str, channel: int, value: float):
        self.param_updated.emit(param_name, channel, value)

    # Qt slots
    def _update_frame_display(self, frame: np.ndarray):
        # Frame is already rendered (Simple or Multiverse mode) by controller
        # Just display it directly
        height, width = frame.shape[:2]
        bytes_per_line = 3 * width
        q_image = QImage(frame.data, width, height, bytes_per_line,
                        QImage.Format.Format_RGB888).rgbSwapped()
        self.video_label.setPixmap(QPixmap.fromImage(q_image))

    def _update_cv_display(self, cv_values: np.ndarray):
        """Update CV Meter Window with new CV values"""
        if self.cv_meter_window:
            self.cv_meter_window.update_values(cv_values)

    def _update_visual_display(self, visual_params: dict):
        pass

    def _update_param_display(self, param_name: str, channel: int, value: float):
        """Update GUI slider when parameter is changed by seq"""
        if param_name == "curve":
            # Curve: value 0-5, slider 0-500 (100x)
            slider, label = self.channel_curve_sliders[channel]
            slider.blockSignals(True)  # Avoid feedback loop
            slider.setValue(int(value * 100))
            label.setText(f"{value:.2f}")
            slider.blockSignals(False)
        elif param_name == "angle":
            # Angle: value 0-720, slider 0-360
            slider, label = self.channel_angle_sliders[channel]
            slider.blockSignals(True)
            # Map 0-720 to 0-360 slider
            slider_value = int(value) % 360
            slider.setValue(slider_value)
            label.setText(f"{int(value)}")
            slider.blockSignals(False)

    def closeEvent(self, event):
        """Close all windows and stop controller"""
        self.controller.stop()
        if self.cv_meter_window:
            self.cv_meter_window.close()
        if hasattr(self, 'midi_learn'):
            self.midi_learn.shutdown()
        event.accept()


def main():
    """Main entry point"""
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("VAV")

    controller = VAVController()
    if not controller.initialize():
        print("Failed to initialize VAV system")
        sys.exit(1)

    window = CompactMainWindow(controller)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
