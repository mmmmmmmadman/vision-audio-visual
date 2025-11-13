"""
Compact Main GUI window for VAV system - optimized layout
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QGroupBox, QGridLayout,
    QComboBox, QCheckBox, QTextEdit, QLineEdit, QMenu,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QImage, QPixmap
import numpy as np
import cv2

from .device_dialog import DeviceSelectionDialog
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
        self.setGeometry(100, 100, 1300, 420)

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

        # Setup MIDI Learn for Anchor XY Pad in CV Meter Window
        self.cv_meter_window.setup_midi_learn(self.midi_learn)

        # Connect Anchor XY Pad position changes to controller
        self.cv_meter_window.anchor_xy_pad.position_changed.connect(self._on_anchor_xy_changed)

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

        # Controls in compact widget (use HBox with independent columns to avoid row alignment)
        controls_widget = QWidget()
        controls_layout = QHBoxLayout(controls_widget)
        controls_layout.setSpacing(10)  # Horizontal spacing between columns
        controls_layout.setContentsMargins(5, 5, 5, 5)
        controls_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._build_all_controls_inline(controls_layout)

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

    def _fixed_height_label(self, text: str, width: int = None, align_left: bool = False) -> QLabel:
        """Create a QLabel with fixed height for consistent spacing"""
        label = QLabel(text)
        label.setFixedHeight(16)
        if width:
            label.setFixedWidth(width)
        if align_left:
            label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        return label

    def _create_control_row(self, label_text: str, control_widget, value_label=None, label_width: int = 80):
        """Create a horizontal row with label + control + optional value label"""
        row = QHBoxLayout()
        row.setSpacing(5)
        row.setContentsMargins(0, 0, 0, 0)

        # Label (fixed width, left aligned)
        label = self._fixed_height_label(label_text, label_width, align_left=True)
        row.addWidget(label)

        # Control widget
        row.addWidget(control_widget)

        # Optional value label
        if value_label:
            row.addWidget(value_label)

        row.addStretch()
        return row

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

    def _build_all_controls_inline(self, hbox: QHBoxLayout):
        """Build all controls in 5-column layout using VBoxLayout with _create_control_row helper"""
        from PyQt6.QtWidgets import QVBoxLayout

        # Enhanced pink color scheme for better contrast
        COLOR_COL1 = "#FF6B9D"  # Vibrant pink (Audio basics)
        COLOR_COL2 = "#FF9A76"  # Coral orange (Multiverse global)
        COLOR_COL3 = "#C77DFF"  # Purple (Multiverse channels)
        COLOR_COL4 = "#FF8FA3"  # Rose pink (Ellen Ripley)

        # Create 5 independent VBox layouts with fixed label widths
        col1_layout = QVBoxLayout()
        col1_layout.setSpacing(8)

        col2_layout = QVBoxLayout()
        col2_layout.setSpacing(8)

        col3_layout = QVBoxLayout()
        col3_layout.setSpacing(8)

        col4_layout = QVBoxLayout()
        col4_layout.setSpacing(8)

        col5_layout = QVBoxLayout()
        col5_layout.setSpacing(8)

        # Fixed label width for consistent alignment
        LABEL_WIDTH = 80

        # ===== COLUMN 1: CV Source =====

        # ENV Decay (exponential: 0.1~1s, 1~5s)
        self.env_global_slider = QSlider(Qt.Orientation.Horizontal)
        self.env_global_slider.setFixedHeight(16)
        self.env_global_slider.setFixedWidth(140)
        self._apply_slider_style(self.env_global_slider, COLOR_COL1)
        self.env_global_slider.setMinimum(0)
        self.env_global_slider.setMaximum(100)
        self.env_global_slider.setValue(50)
        self.env_global_slider.valueChanged.connect(self._on_env_global_decay_changed)
        self._make_slider_learnable(self.env_global_slider, "env_global_decay", self._on_env_global_decay_changed)
        self.env_global_label = self._fixed_height_label("1.0s", 35)
        row = self._create_control_row("ENV Decay", self.env_global_slider, self.env_global_label, LABEL_WIDTH)
        col1_layout.addLayout(row)

        # Scan Time (掃描時間，秒)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setFixedHeight(16)
        slider.setFixedWidth(140)
        self._apply_slider_style(slider, COLOR_COL1)
        slider.setMinimum(2)  # 0.1s
        slider.setMaximum(600)  # 30s
        slider.setValue(200)  # 10.0s
        slider.valueChanged.connect(self._on_clock_rate_changed)
        self._make_slider_learnable(slider, "scan_time", self._on_clock_rate_changed)
        value = self._fixed_height_label("10.0s", 35)
        self.clock_slider = (slider, value)
        row = self._create_control_row("Scan Time", slider, value, LABEL_WIDTH)
        col1_layout.addLayout(row)

        # Range
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setFixedHeight(16)
        slider.setFixedWidth(140)
        self._apply_slider_style(slider, COLOR_COL1)
        slider.setMinimum(1)
        slider.setMaximum(120)
        slider.setValue(50)
        slider.valueChanged.connect(self._on_range_changed)
        self._make_slider_learnable(slider, "range", self._on_range_changed)
        value = self._fixed_height_label("50%", 35)
        self.range_slider = (slider, value)
        row = self._create_control_row("Range", slider, value, LABEL_WIDTH)
        col1_layout.addLayout(row)

        # Mixer (moved from COL2)
        self.mixer_sliders = []
        # Track 1-4
        for i in range(4):
            mix_slider = QSlider(Qt.Orientation.Horizontal)
            mix_slider.setFixedHeight(16)
            mix_slider.setFixedWidth(140)
            self._apply_slider_style(mix_slider, COLOR_COL1)
            mix_slider.setMinimum(0)
            mix_slider.setMaximum(100)
            mix_slider.setValue(80)
            mix_slider.valueChanged.connect(lambda val, idx=i: self._on_mixer_volume(idx, val / 100.0))
            self._make_slider_learnable(mix_slider, f"track{i+1}_vol", lambda val, idx=i: self._on_mixer_volume(idx, val / 100.0))
            mix_label = self._fixed_height_label("0.8", 25)
            self.mixer_sliders.append((mix_slider, mix_label))
            row = self._create_control_row(f"Track {i+1} Vol", mix_slider, mix_label, LABEL_WIDTH)
            col1_layout.addLayout(row)

        # CV Overlay checkbox
        self.cv_overlay_checkbox = QCheckBox("CV Overlay")
        self.cv_overlay_checkbox.setFixedHeight(16)
        self.cv_overlay_checkbox.setChecked(True)  # Default enabled
        self.cv_overlay_checkbox.stateChanged.connect(self._on_cv_overlay_toggle)
        col1_layout.addWidget(self.cv_overlay_checkbox)

        # Countdown Timer (倒數計時器)
        timer_layout = QHBoxLayout()
        timer_layout.setSpacing(5)
        timer_layout.setContentsMargins(0, 0, 0, 0)

        # Timer display (倒數顯示)
        self.timer_display = QLabel("00:00")
        self.timer_display.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.timer_display.setFixedWidth(45)
        self.timer_display.setFixedHeight(16)  # Match other controls
        self.timer_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        timer_layout.addWidget(self.timer_display)

        # Time input (分:秒)
        self.timer_minutes = QLineEdit("05")
        self.timer_minutes.setFixedWidth(30)
        self.timer_minutes.setFixedHeight(16)  # Match other controls
        self.timer_minutes.setMaxLength(2)
        self.timer_minutes.setAlignment(Qt.AlignmentFlag.AlignCenter)
        timer_layout.addWidget(self.timer_minutes)
        colon_label = QLabel(":")
        colon_label.setFixedHeight(16)
        timer_layout.addWidget(colon_label)
        self.timer_seconds = QLineEdit("00")
        self.timer_seconds.setFixedWidth(30)
        self.timer_seconds.setFixedHeight(16)  # Match other controls
        self.timer_seconds.setMaxLength(2)
        self.timer_seconds.setAlignment(Qt.AlignmentFlag.AlignCenter)
        timer_layout.addWidget(self.timer_seconds)

        # Start/Stop button
        self.timer_button = QPushButton("Start")
        self.timer_button.setFixedWidth(50)
        self.timer_button.setFixedHeight(24)  # Taller for better appearance
        self.timer_button.clicked.connect(self._on_timer_toggle)
        timer_layout.addWidget(self.timer_button)

        timer_layout.addStretch()

        # Timer row with label (manually create row since timer has complex layout)
        timer_row = QHBoxLayout()
        timer_row.setSpacing(5)
        timer_row.setContentsMargins(0, 0, 0, 0)
        timer_label = self._fixed_height_label("Timer", LABEL_WIDTH, align_left=True)
        timer_row.addWidget(timer_label)
        timer_row.addLayout(timer_layout)
        col1_layout.addLayout(timer_row)

        # Timer state
        self.timer_running = False
        self.timer_remaining = 0  # seconds
        self.timer_total = 0  # seconds
        self.timer_start_time = 0  # timestamp

        # Timer animation - store initial values
        self.timer_initial_color_scheme = 0
        self.timer_initial_blend_mode = 0
        self.timer_initial_base_hue = 0
        self.timer_target_color_scheme = 100
        self.timer_target_blend_mode = 100
        self.timer_target_base_hue = 333

        # Timer update (using QTimer)
        self.timer_updater = QTimer()
        self.timer_updater.timeout.connect(self._update_timer)
        self.timer_updater.setInterval(100)  # Update every 100ms

        # ===== COLUMN 2: Multiverse Main =====

        # Enable (Multiverse checkbox with color scheme slider on same row)
        self.multiverse_checkbox = QCheckBox("Multiverse")
        self.multiverse_checkbox.setFixedHeight(16)  # Match slider height for consistent spacing
        self.multiverse_checkbox.setChecked(True)  # Default enabled
        self.multiverse_checkbox.stateChanged.connect(self._on_multiverse_toggle)

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

        # Multiverse row - put checkbox in place of label, slider aligned
        multiverse_row_layout = QHBoxLayout()
        multiverse_row_layout.setSpacing(5)
        multiverse_row_layout.setContentsMargins(0, 0, 0, 0)

        # Checkbox acts as the label (fixed width to match label width)
        self.multiverse_checkbox.setFixedWidth(LABEL_WIDTH)
        multiverse_row_layout.addWidget(self.multiverse_checkbox)

        # Add 9px spacing to push slider right
        multiverse_row_layout.addSpacing(9)

        # Slider (same position as other sliders)
        multiverse_row_layout.addWidget(self.color_scheme_slider)
        multiverse_row_layout.addStretch()

        col2_layout.addLayout(multiverse_row_layout)

        # Blend mode fader
        self.blend_mode_slider = QSlider(Qt.Orientation.Horizontal)
        self.blend_mode_slider.setFixedHeight(16)
        self.blend_mode_slider.setFixedWidth(120)
        self._apply_slider_style(self.blend_mode_slider, COLOR_COL2)
        self.blend_mode_slider.setMinimum(0)
        self.blend_mode_slider.setMaximum(100)
        self.blend_mode_slider.setValue(0)  # Default to Add
        self.blend_mode_slider.valueChanged.connect(self._on_blend_mode_changed)
        self._make_slider_learnable(self.blend_mode_slider, "blend_mode", self._on_blend_mode_changed)
        row = self._create_control_row("Blend", self.blend_mode_slider, None, LABEL_WIDTH)
        col2_layout.addLayout(row)

        # Brightness
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setFixedHeight(16)
        self.brightness_slider.setFixedWidth(120)
        self._apply_slider_style(self.brightness_slider, COLOR_COL2)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(400)
        self.brightness_slider.setValue(150)  # Default 1.5
        self.brightness_slider.valueChanged.connect(self._on_brightness_changed)
        self._make_slider_learnable(self.brightness_slider, "brightness", self._on_brightness_changed)
        self.brightness_label = QLabel("1.5")
        self.brightness_label.setFixedWidth(25)
        row = self._create_control_row("Brightness", self.brightness_slider, self.brightness_label, LABEL_WIDTH)
        col2_layout.addLayout(row)

        # Base Hue
        self.base_hue_slider = QSlider(Qt.Orientation.Horizontal)
        self.base_hue_slider.setFixedHeight(16)
        self.base_hue_slider.setFixedWidth(120)
        self._apply_slider_style(self.base_hue_slider, COLOR_COL2)
        self.base_hue_slider.setMinimum(0)
        self.base_hue_slider.setMaximum(333)
        self.base_hue_slider.setValue(0)  # Default red
        self.base_hue_slider.valueChanged.connect(self._on_base_hue_changed)
        self._make_slider_learnable(self.base_hue_slider, "base_hue", self._on_base_hue_changed)
        self.base_hue_label = QLabel("0")
        self.base_hue_label.setFixedWidth(25)
        row = self._create_control_row("Base Hue", self.base_hue_slider, self.base_hue_label, LABEL_WIDTH)
        col2_layout.addLayout(row)

        # Camera Mix
        self.camera_mix_slider = QSlider(Qt.Orientation.Horizontal)
        self.camera_mix_slider.setFixedHeight(16)
        self.camera_mix_slider.setFixedWidth(120)
        self._apply_slider_style(self.camera_mix_slider, COLOR_COL2)
        self.camera_mix_slider.setMinimum(0)
        self.camera_mix_slider.setMaximum(30)  # Max 0.3
        self.camera_mix_slider.setValue(0)  # Default: pure multiverse
        self.camera_mix_slider.valueChanged.connect(self._on_camera_mix_changed)
        self._make_slider_learnable(self.camera_mix_slider, "camera_mix", self._on_camera_mix_changed)
        self.camera_mix_label = QLabel("0.0")
        self.camera_mix_label.setFixedWidth(25)
        row = self._create_control_row("Camera Mix", self.camera_mix_slider, self.camera_mix_label, LABEL_WIDTH)
        col2_layout.addLayout(row)

        # Global Ratio (控制全部 4 個通道) - 與 Multiverse.cpp 相同範圍
        self.global_ratio_slider = QSlider(Qt.Orientation.Horizontal)
        self.global_ratio_slider.setFixedHeight(16)
        self.global_ratio_slider.setFixedWidth(120)
        self._apply_slider_style(self.global_ratio_slider, COLOR_COL2)
        self.global_ratio_slider.setMinimum(0)  # 0.0
        self.global_ratio_slider.setMaximum(100)  # 1.0
        self.global_ratio_slider.setValue(100)  # 1.0 default (no pitch shift)
        self.global_ratio_slider.valueChanged.connect(self._on_global_ratio_changed)
        self._make_slider_learnable(self.global_ratio_slider, "global_ratio", self._on_global_ratio_changed)
        self.global_ratio_label = QLabel("1.00")
        self.global_ratio_label.setFixedWidth(30)
        row = self._create_control_row("Ratio", self.global_ratio_slider, self.global_ratio_label, LABEL_WIDTH)
        col2_layout.addLayout(row)

        # Region Rendering + SD img2img (same row)
        region_sd_layout = QHBoxLayout()
        region_sd_layout.setSpacing(10)
        region_sd_layout.setContentsMargins(0, 0, 0, 0)

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

        col2_layout.addLayout(region_sd_layout)

        # SD Prompt (multiline text area, no label)
        self.sd_prompt_edit = QTextEdit()
        self.sd_prompt_edit.setFixedHeight(40)
        self.sd_prompt_edit.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.sd_prompt_edit.setPlainText("artistic style, abstract, monochrome ink painting, high quality")
        self.sd_prompt_edit.textChanged.connect(self._on_sd_prompt_changed)
        col2_layout.addWidget(self.sd_prompt_edit)

        # SD Steps
        self.sd_steps_slider = QSlider(Qt.Orientation.Horizontal)
        self.sd_steps_slider.setFixedHeight(16)
        self.sd_steps_slider.setFixedWidth(120)
        self._apply_slider_style(self.sd_steps_slider, COLOR_COL2)
        self.sd_steps_slider.setMinimum(1)
        self.sd_steps_slider.setMaximum(4)  # 最高到 4
        self.sd_steps_slider.setValue(2)
        self.sd_steps_slider.valueChanged.connect(self._on_sd_steps_changed)
        self._make_slider_learnable(self.sd_steps_slider, "sd_steps", self._on_sd_steps_changed)
        self.sd_steps_label = QLabel("2")
        self.sd_steps_label.setFixedWidth(25)
        row = self._create_control_row("Steps", self.sd_steps_slider, self.sd_steps_label, LABEL_WIDTH)
        col2_layout.addLayout(row)

        # SD Strength
        self.sd_strength_slider = QSlider(Qt.Orientation.Horizontal)
        self.sd_strength_slider.setFixedHeight(16)
        self.sd_strength_slider.setFixedWidth(120)
        self._apply_slider_style(self.sd_strength_slider, COLOR_COL2)
        self.sd_strength_slider.setMinimum(50)
        self.sd_strength_slider.setMaximum(100)
        self.sd_strength_slider.setValue(50)
        self.sd_strength_slider.valueChanged.connect(self._on_sd_strength_changed)
        self._make_slider_learnable(self.sd_strength_slider, "sd_strength", self._on_sd_strength_changed)
        self.sd_strength_label = QLabel("0.50")
        self.sd_strength_label.setFixedWidth(30)
        row = self._create_control_row("Strength", self.sd_strength_slider, self.sd_strength_label, LABEL_WIDTH)
        col2_layout.addLayout(row)

        # SD Guidance
        self.sd_guidance_slider = QSlider(Qt.Orientation.Horizontal)
        self.sd_guidance_slider.setFixedHeight(16)
        self.sd_guidance_slider.setFixedWidth(120)
        self._apply_slider_style(self.sd_guidance_slider, COLOR_COL2)
        self.sd_guidance_slider.setMinimum(10)
        self.sd_guidance_slider.setMaximum(50)  # 最高到 5.0
        self.sd_guidance_slider.setValue(10)
        self.sd_guidance_slider.valueChanged.connect(self._on_sd_guidance_changed)
        self._make_slider_learnable(self.sd_guidance_slider, "sd_guidance", self._on_sd_guidance_changed)
        self.sd_guidance_label = QLabel("1.0")
        self.sd_guidance_label.setFixedWidth(30)
        row = self._create_control_row("Guidance", self.sd_guidance_slider, self.sd_guidance_label, LABEL_WIDTH)
        col2_layout.addLayout(row)

        # SD Gen Interval
        self.sd_interval_edit = QLineEdit("0.5")
        self.sd_interval_edit.setFixedWidth(120)
        self.sd_interval_edit.setFixedHeight(16)  # Match slider height for consistent spacing
        self.sd_interval_edit.textChanged.connect(self._on_sd_interval_changed)
        interval_suffix = QLabel("s")
        row = self._create_control_row("Gen Interval", self.sd_interval_edit, interval_suffix, LABEL_WIDTH)
        col2_layout.addLayout(row)

        # ===== COLUMN 3: Multiverse Channels (Ch1-4, vertical layout) =====
        self.channel_curve_sliders = []
        self.channel_angle_sliders = []
        default_angles = [180, 225, 270, 315]

        # Create all 4 channels with vertical layout (Curve, Angle in separate rows)
        for i in range(4):
            # Curve (現在是 modulation amount 0-100%)
            curve_slider = QSlider(Qt.Orientation.Horizontal)
            curve_slider.setFixedHeight(16)
            curve_slider.setFixedWidth(120)
            self._apply_slider_style(curve_slider, COLOR_COL3)
            curve_slider.setMinimum(0)
            curve_slider.setMaximum(100)
            curve_slider.setValue(100)  # 預設 100% modulation
            curve_slider.valueChanged.connect(lambda val, idx=i: self._on_channel_curve_changed(idx, val))
            self._make_slider_learnable(curve_slider, f"ch{i+1}_curve", lambda val, idx=i: self._on_channel_curve_changed(idx, val))
            curve_label = QLabel("0.0")
            curve_label.setFixedWidth(25)
            self.channel_curve_sliders.append((curve_slider, curve_label))
            row = self._create_control_row(f"Ch{i+1} Curve", curve_slider, curve_label, LABEL_WIDTH)
            col3_layout.addLayout(row)

            # Angle (現在是 modulation amount 0-360 映射到 0-100%)
            angle_slider = QSlider(Qt.Orientation.Horizontal)
            angle_slider.setFixedHeight(16)
            angle_slider.setFixedWidth(120)
            self._apply_slider_style(angle_slider, COLOR_COL3)
            angle_slider.setMinimum(0)
            angle_slider.setMaximum(360)
            angle_slider.setValue(360)  # 預設 360 = 100% modulation
            angle_slider.valueChanged.connect(lambda val, idx=i: self._on_channel_angle_changed(idx, val))
            self._make_slider_learnable(angle_slider, f"ch{i+1}_angle", lambda val, idx=i: self._on_channel_angle_changed(idx, val))
            angle_label = QLabel(f"{default_angles[i]}°")
            angle_label.setFixedWidth(30)
            self.channel_angle_sliders.append((angle_slider, angle_label))
            row = self._create_control_row(f"Ch{i+1} Angle", angle_slider, angle_label, LABEL_WIDTH)
            col3_layout.addLayout(row)

        # ===== COLUMN 4: Ellen Ripley Delay+Grain =====

        # Ellen Ripley is always enabled (no checkbox)
        # Enable Ellen Ripley immediately during initialization

        # Delay Time L
        self.er_delay_time_l_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_delay_time_l_slider.setFixedHeight(16)
        self.er_delay_time_l_slider.setFixedWidth(120)
        self._apply_slider_style(self.er_delay_time_l_slider, COLOR_COL4)
        self.er_delay_time_l_slider.setMinimum(1)
        self.er_delay_time_l_slider.setMaximum(2000)
        self.er_delay_time_l_slider.setValue(250)
        self.er_delay_time_l_slider.valueChanged.connect(self._on_er_delay_time_l_changed)
        self._make_slider_learnable(self.er_delay_time_l_slider, "er_delay_time_l", self._on_er_delay_time_l_changed)
        self.er_delay_time_l_label = QLabel("0.25s")
        self.er_delay_time_l_label.setFixedWidth(35)
        row = self._create_control_row("Delay Time L", self.er_delay_time_l_slider, self.er_delay_time_l_label, LABEL_WIDTH)
        col4_layout.addLayout(row)

        # Delay Time R
        self.er_delay_time_r_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_delay_time_r_slider.setFixedHeight(16)
        self.er_delay_time_r_slider.setFixedWidth(120)
        self._apply_slider_style(self.er_delay_time_r_slider, COLOR_COL4)
        self.er_delay_time_r_slider.setMinimum(1)
        self.er_delay_time_r_slider.setMaximum(2000)
        self.er_delay_time_r_slider.setValue(300)  # Slightly slower
        self.er_delay_time_r_slider.valueChanged.connect(self._on_er_delay_time_r_changed)
        self._make_slider_learnable(self.er_delay_time_r_slider, "er_delay_time_r", self._on_er_delay_time_r_changed)
        self.er_delay_time_r_label = QLabel("0.30s")
        self.er_delay_time_r_label.setFixedWidth(35)
        row = self._create_control_row("Delay Time R", self.er_delay_time_r_slider, self.er_delay_time_r_label, LABEL_WIDTH)
        col4_layout.addLayout(row)

        # Delay FB
        self.er_delay_fb_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_delay_fb_slider.setFixedHeight(16)
        self.er_delay_fb_slider.setFixedWidth(120)
        self._apply_slider_style(self.er_delay_fb_slider, COLOR_COL4)
        self.er_delay_fb_slider.setMinimum(0)
        self.er_delay_fb_slider.setMaximum(95)
        self.er_delay_fb_slider.setValue(30)
        self.er_delay_fb_slider.valueChanged.connect(self._on_er_delay_fb_changed)
        self._make_slider_learnable(self.er_delay_fb_slider, "er_delay_fb", self._on_er_delay_fb_changed)
        self.er_delay_fb_label = QLabel("0.30")
        self.er_delay_fb_label.setFixedWidth(30)
        row = self._create_control_row("Delay FB", self.er_delay_fb_slider, self.er_delay_fb_label, LABEL_WIDTH)
        col4_layout.addLayout(row)

        # Delay Mix
        self.er_delay_mix_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_delay_mix_slider.setFixedHeight(16)
        self.er_delay_mix_slider.setFixedWidth(120)
        self._apply_slider_style(self.er_delay_mix_slider, COLOR_COL4)
        self.er_delay_mix_slider.setMinimum(0)
        self.er_delay_mix_slider.setMaximum(100)
        self.er_delay_mix_slider.setValue(0)
        self.er_delay_mix_slider.valueChanged.connect(self._on_er_delay_mix_changed)
        self._make_slider_learnable(self.er_delay_mix_slider, "er_delay_mix", self._on_er_delay_mix_changed)
        self.er_delay_mix_label = QLabel("0.00")
        self.er_delay_mix_label.setFixedWidth(30)
        row = self._create_control_row("Dly Mix", self.er_delay_mix_slider, self.er_delay_mix_label, LABEL_WIDTH)
        col4_layout.addLayout(row)

        # Grain Size
        self.er_grain_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_grain_size_slider.setFixedHeight(16)
        self.er_grain_size_slider.setFixedWidth(120)
        self._apply_slider_style(self.er_grain_size_slider, COLOR_COL4)
        self.er_grain_size_slider.setMinimum(0)
        self.er_grain_size_slider.setMaximum(100)
        self.er_grain_size_slider.setValue(50)  # Default to 50%
        self.er_grain_size_slider.valueChanged.connect(self._on_er_grain_size_changed)
        self._make_slider_learnable(self.er_grain_size_slider, "er_grain_size", self._on_er_grain_size_changed)
        self.er_grain_size_label = QLabel("0.50")
        self.er_grain_size_label.setFixedWidth(30)
        row = self._create_control_row("Grain Size", self.er_grain_size_slider, self.er_grain_size_label, LABEL_WIDTH)
        col4_layout.addLayout(row)

        # Grain Density
        self.er_grain_density_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_grain_density_slider.setFixedHeight(16)
        self.er_grain_density_slider.setFixedWidth(120)
        self._apply_slider_style(self.er_grain_density_slider, COLOR_COL4)
        self.er_grain_density_slider.setMinimum(0)
        self.er_grain_density_slider.setMaximum(100)
        self.er_grain_density_slider.setValue(40)
        self.er_grain_density_slider.valueChanged.connect(self._on_er_grain_density_changed)
        self._make_slider_learnable(self.er_grain_density_slider, "er_grain_density", self._on_er_grain_density_changed)
        self.er_grain_density_label = QLabel("0.40")
        self.er_grain_density_label.setFixedWidth(30)
        row = self._create_control_row("Grain Density", self.er_grain_density_slider, self.er_grain_density_label, LABEL_WIDTH)
        col4_layout.addLayout(row)

        # Grain Position
        self.er_grain_pos_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_grain_pos_slider.setFixedHeight(16)
        self.er_grain_pos_slider.setFixedWidth(120)
        self._apply_slider_style(self.er_grain_pos_slider, COLOR_COL4)
        self.er_grain_pos_slider.setMinimum(0)
        self.er_grain_pos_slider.setMaximum(100)
        self.er_grain_pos_slider.setValue(50)
        self.er_grain_pos_slider.valueChanged.connect(self._on_er_grain_pos_changed)
        self._make_slider_learnable(self.er_grain_pos_slider, "er_grain_pos", self._on_er_grain_pos_changed)
        self.er_grain_pos_label = QLabel("0.50")
        self.er_grain_pos_label.setFixedWidth(30)
        row = self._create_control_row("Grain Position", self.er_grain_pos_slider, self.er_grain_pos_label, LABEL_WIDTH)
        col4_layout.addLayout(row)

        # Grain Mix
        self.er_grain_mix_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_grain_mix_slider.setFixedHeight(16)
        self.er_grain_mix_slider.setFixedWidth(120)
        self._apply_slider_style(self.er_grain_mix_slider, COLOR_COL4)
        self.er_grain_mix_slider.setMinimum(0)
        self.er_grain_mix_slider.setMaximum(100)
        self.er_grain_mix_slider.setValue(0)
        self.er_grain_mix_slider.valueChanged.connect(self._on_er_grain_mix_changed)
        self._make_slider_learnable(self.er_grain_mix_slider, "er_grain_mix", self._on_er_grain_mix_changed)
        self.er_grain_mix_label = QLabel("0.00")
        self.er_grain_mix_label.setFixedWidth(30)
        row = self._create_control_row("Grn Mix", self.er_grain_mix_slider, self.er_grain_mix_label, LABEL_WIDTH)
        col4_layout.addLayout(row)

        # ===== COLUMN 5: Ellen Ripley Reverb+Chaos =====

        # Reverb Room
        self.er_reverb_room_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_reverb_room_slider.setFixedHeight(16)
        self.er_reverb_room_slider.setFixedWidth(120)
        self._apply_slider_style(self.er_reverb_room_slider, COLOR_COL4)
        self.er_reverb_room_slider.setMinimum(0)
        self.er_reverb_room_slider.setMaximum(100)
        self.er_reverb_room_slider.setValue(100)  # Default to maximum
        self.er_reverb_room_slider.valueChanged.connect(self._on_er_reverb_room_changed)
        self._make_slider_learnable(self.er_reverb_room_slider, "er_reverb_room", self._on_er_reverb_room_changed)
        self.er_reverb_room_label = QLabel("1.00")
        self.er_reverb_room_label.setFixedWidth(30)
        row = self._create_control_row("Reverb Room", self.er_reverb_room_slider, self.er_reverb_room_label, LABEL_WIDTH)
        col5_layout.addLayout(row)

        # Reverb Damping
        self.er_reverb_damp_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_reverb_damp_slider.setFixedHeight(16)
        self.er_reverb_damp_slider.setFixedWidth(120)
        self._apply_slider_style(self.er_reverb_damp_slider, COLOR_COL4)
        self.er_reverb_damp_slider.setMinimum(0)
        self.er_reverb_damp_slider.setMaximum(100)
        self.er_reverb_damp_slider.setValue(100)  # Default to maximum
        self.er_reverb_damp_slider.valueChanged.connect(self._on_er_reverb_damp_changed)
        self._make_slider_learnable(self.er_reverb_damp_slider, "er_reverb_damp", self._on_er_reverb_damp_changed)
        self.er_reverb_damp_label = QLabel("1.00")
        self.er_reverb_damp_label.setFixedWidth(30)
        row = self._create_control_row("Reverb Damp", self.er_reverb_damp_slider, self.er_reverb_damp_label, LABEL_WIDTH)
        col5_layout.addLayout(row)

        # Reverb Decay
        self.er_reverb_decay_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_reverb_decay_slider.setFixedHeight(16)
        self.er_reverb_decay_slider.setFixedWidth(120)
        self._apply_slider_style(self.er_reverb_decay_slider, COLOR_COL4)
        self.er_reverb_decay_slider.setMinimum(0)
        self.er_reverb_decay_slider.setMaximum(100)
        self.er_reverb_decay_slider.setValue(80)  # Default to 80%
        self.er_reverb_decay_slider.valueChanged.connect(self._on_er_reverb_decay_changed)
        self._make_slider_learnable(self.er_reverb_decay_slider, "er_reverb_decay", self._on_er_reverb_decay_changed)
        self.er_reverb_decay_label = QLabel("0.80")
        self.er_reverb_decay_label.setFixedWidth(30)
        row = self._create_control_row("Reverb Decay", self.er_reverb_decay_slider, self.er_reverb_decay_label, LABEL_WIDTH)
        col5_layout.addLayout(row)

        # Reverb Mix
        self.er_reverb_mix_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_reverb_mix_slider.setFixedHeight(16)
        self.er_reverb_mix_slider.setFixedWidth(120)
        self._apply_slider_style(self.er_reverb_mix_slider, COLOR_COL4)
        self.er_reverb_mix_slider.setMinimum(0)
        self.er_reverb_mix_slider.setMaximum(100)
        self.er_reverb_mix_slider.setValue(0)
        self.er_reverb_mix_slider.valueChanged.connect(self._on_er_reverb_mix_changed)
        self._make_slider_learnable(self.er_reverb_mix_slider, "er_reverb_mix", self._on_er_reverb_mix_changed)
        self.er_reverb_mix_label = QLabel("0.00")
        self.er_reverb_mix_label.setFixedWidth(30)
        row = self._create_control_row("Rev Mix", self.er_reverb_mix_slider, self.er_reverb_mix_label, LABEL_WIDTH)
        col5_layout.addLayout(row)

        # Chaos Rate
        self.er_chaos_rate_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_chaos_rate_slider.setFixedHeight(16)
        self.er_chaos_rate_slider.setFixedWidth(120)
        self._apply_slider_style(self.er_chaos_rate_slider, COLOR_COL4)
        self.er_chaos_rate_slider.setMinimum(0)
        self.er_chaos_rate_slider.setMaximum(100)
        self.er_chaos_rate_slider.setValue(1)
        self.er_chaos_rate_slider.valueChanged.connect(self._on_er_chaos_rate_changed)
        self._make_slider_learnable(self.er_chaos_rate_slider, "er_chaos_rate", self._on_er_chaos_rate_changed)
        self.er_chaos_rate_label = QLabel("0.01")
        self.er_chaos_rate_label.setFixedWidth(30)
        row = self._create_control_row("Chaos Rate", self.er_chaos_rate_slider, self.er_chaos_rate_label, LABEL_WIDTH)
        col5_layout.addLayout(row)

        # Chaos Amount
        self.er_chaos_amount_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_chaos_amount_slider.setFixedHeight(16)
        self.er_chaos_amount_slider.setFixedWidth(120)
        self._apply_slider_style(self.er_chaos_amount_slider, COLOR_COL4)
        self.er_chaos_amount_slider.setMinimum(0)
        self.er_chaos_amount_slider.setMaximum(100)
        self.er_chaos_amount_slider.setValue(100)
        self.er_chaos_amount_slider.valueChanged.connect(self._on_er_chaos_amount_changed)
        self._make_slider_learnable(self.er_chaos_amount_slider, "er_chaos_amount", self._on_er_chaos_amount_changed)
        self.er_chaos_amount_label = QLabel("1.00")
        self.er_chaos_amount_label.setFixedWidth(30)
        row = self._create_control_row("Chaos Amount", self.er_chaos_amount_slider, self.er_chaos_amount_label, LABEL_WIDTH)
        col5_layout.addLayout(row)

        # Chaos toggles in two rows
        # First row: Delay Chaos, Grain Chaos
        chaos_row1_layout = QHBoxLayout()
        chaos_row1_layout.setSpacing(5)
        chaos_row1_layout.setContentsMargins(0, 0, 0, 0)

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

        col5_layout.addLayout(chaos_row1_layout)

        # Second row: Reverb Chaos, Chaos Shape
        chaos_row2_layout = QHBoxLayout()
        chaos_row2_layout.setSpacing(5)
        chaos_row2_layout.setContentsMargins(0, 0, 0, 0)

        self.er_reverb_chaos_checkbox = QCheckBox("Rev Chaos")
        self.er_reverb_chaos_checkbox.setFixedHeight(16)
        self.er_reverb_chaos_checkbox.stateChanged.connect(self._on_er_reverb_chaos_changed)
        chaos_row2_layout.addWidget(self.er_reverb_chaos_checkbox)

        self.er_chaos_shape_checkbox = QCheckBox("Chaos Shape")
        self.er_chaos_shape_checkbox.setFixedHeight(16)
        self.er_chaos_shape_checkbox.stateChanged.connect(self._on_er_chaos_shape_changed)
        chaos_row2_layout.addWidget(self.er_chaos_shape_checkbox)

        chaos_row2_layout.addStretch()

        col5_layout.addLayout(chaos_row2_layout)

        # Add all column layouts to the horizontal box
        hbox.addLayout(col1_layout)
        hbox.addLayout(col2_layout)
        hbox.addLayout(col3_layout)
        hbox.addLayout(col4_layout)
        hbox.addLayout(col5_layout)
        hbox.addStretch()

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
        self.cv_meter_window.anchor_xy_pad.set_range(float(value))

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

    def _on_global_ratio_changed(self, value: int):
        """Global ratio changed - update all 4 channels

        擴展 Multiverse.cpp 邏輯：
        - GUI ratio: 0-100 (0.0-1.0)
        - octaveDown = (1 - ratio) * 13.3 (擴展到 13.3 octaves，比原本再小 1/10)
        - pitchRate = 0.5^octaveDown
        """
        # Convert slider to ratio (0-1)
        ratio = value / 100.0
        self.global_ratio_label.setText(f"{ratio:.2f}")

        # Calculate pitch rate (extended range for sparser stripes)
        octave_down = (1.0 - ratio) * 13.3
        pitch_rate = 0.5 ** octave_down

        # Update all 4 channels with pitch rate
        for i in range(4):
            self.controller.set_renderer_channel_ratio(i, pitch_rate)

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

    # Timer event handlers
    def _on_timer_toggle(self):
        """Toggle timer start/stop"""
        if not self.timer_running:
            # Start timer
            try:
                minutes = int(self.timer_minutes.text())
                seconds = int(self.timer_seconds.text())
                total_seconds = minutes * 60 + seconds

                if total_seconds <= 0:
                    return

                self.timer_total = total_seconds
                self.timer_remaining = total_seconds
                self.timer_running = True
                self.timer_button.setText("Stop")

                # Disable input
                self.timer_minutes.setEnabled(False)
                self.timer_seconds.setEnabled(False)

                # Store initial values and set to 0
                self.timer_initial_color_scheme = self.color_scheme_slider.value()
                self.timer_initial_blend_mode = self.blend_mode_slider.value()
                self.timer_initial_base_hue = self.base_hue_slider.value()

                # Reset to 0
                self.color_scheme_slider.setValue(0)
                self.blend_mode_slider.setValue(0)
                self.base_hue_slider.setValue(0)

                # Start QTimer
                import time
                self.timer_start_time = time.time()
                self.timer_updater.start()

            except ValueError:
                pass
        else:
            # Stop timer
            self._stop_timer()

    def _stop_timer(self):
        """Stop and reset timer"""
        self.timer_running = False
        self.timer_updater.stop()
        self.timer_button.setText("Start")

        # Enable input
        self.timer_minutes.setEnabled(True)
        self.timer_seconds.setEnabled(True)

        # Reset display
        self.timer_display.setText("00:00")

    def _update_timer(self):
        """Update timer display (called every 100ms)"""
        if not self.timer_running:
            return

        import time
        elapsed = time.time() - self.timer_start_time
        remaining = max(0, self.timer_total - elapsed)

        if remaining <= 0:
            # Timer finished - set to max values
            self.color_scheme_slider.setValue(self.timer_target_color_scheme)
            self.blend_mode_slider.setValue(self.timer_target_blend_mode)
            self.base_hue_slider.setValue(self.timer_target_base_hue)

            self._stop_timer()
            self.timer_display.setText("00:00")
            self.timer_display.setStyleSheet("font-size: 16px; font-weight: bold; color: red;")
            return

        # Calculate progress (0 to 1)
        progress = (self.timer_total - remaining) / self.timer_total

        # Update parameters linearly from 0 to max
        color_scheme_value = int(progress * self.timer_target_color_scheme)
        blend_mode_value = int(progress * self.timer_target_blend_mode)
        base_hue_value = int(progress * self.timer_target_base_hue)

        # Update sliders (block signals to avoid feedback)
        self.color_scheme_slider.blockSignals(True)
        self.blend_mode_slider.blockSignals(True)
        self.base_hue_slider.blockSignals(True)

        self.color_scheme_slider.setValue(color_scheme_value)
        self.blend_mode_slider.setValue(blend_mode_value)
        self.base_hue_slider.setValue(base_hue_value)

        self.color_scheme_slider.blockSignals(False)
        self.blend_mode_slider.blockSignals(False)
        self.base_hue_slider.blockSignals(False)

        # Manually trigger updates to controller
        self.controller.set_color_scheme(color_scheme_value / 100.0)
        self.controller.set_renderer_blend_mode(blend_mode_value / 100.0)
        self.controller.set_renderer_base_hue(base_hue_value / 333.0)

        # Update display
        minutes = int(remaining // 60)
        seconds = int(remaining % 60)
        self.timer_display.setText(f"{minutes:02d}:{seconds:02d}")

        # Change color when less than 1 minute
        if remaining < 60:
            self.timer_display.setStyleSheet("font-size: 16px; font-weight: bold; color: orange;")
        else:
            self.timer_display.setStyleSheet("font-size: 16px; font-weight: bold;")

    # Qt slots
    def _update_frame_display(self, frame: np.ndarray):
        # Frame is already rendered (Simple or Multiverse mode) by controller
        # Just display it directly
        height, width = frame.shape[:2]
        bytes_per_line = 3 * width
        q_image = QImage(frame.data, width, height, bytes_per_line,
                        QImage.Format.Format_RGB888).rgbSwapped()
        self.video_label.setPixmap(QPixmap.fromImage(q_image))

        # Update visual preview in CV meter window
        if self.cv_meter_window:
            self.cv_meter_window.update_visual_preview(frame)

    def _update_cv_display(self, cv_values: np.ndarray):
        """Update CV Meter Window with new CV values"""
        if self.cv_meter_window:
            self.cv_meter_window.update_values(cv_values)

    def _update_visual_display(self, visual_params: dict):
        pass

    def _update_param_display(self, param_name: str, channel: int, value: float):
        """Update GUI label to show current actual value (LFO modulated)

        Slider 不更新因為它現在控制 modulation amount
        只更新 label 顯示當前實際 angle/curve 值
        """
        if param_name == "curve":
            # 顯示當前實際 curve 值 (0-1)
            _, label = self.channel_curve_sliders[channel]
            label.setText(f"{value:.2f}")
        elif param_name == "angle":
            # 顯示當前實際 angle 值 (-180 到 +180)
            _, label = self.channel_angle_sliders[channel]
            label.setText(f"{int(value)}°")

    def _on_cv_overlay_toggle(self, state: int):
        """Toggle CV overlay display on main visual"""
        enabled = (state == Qt.CheckState.Checked.value)
        self.controller.enable_cv_overlay(enabled)

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
