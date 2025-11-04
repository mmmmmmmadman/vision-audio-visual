"""
Compact Main GUI window for VAV system - optimized layout
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QGroupBox, QGridLayout,
    QComboBox, QCheckBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
import numpy as np
import cv2

from .scope_widget import ScopeWidget
from .device_dialog import DeviceSelectionDialog
from .anchor_xy_pad import AnchorXYPad
from ..core.controller import VAVController


class CompactMainWindow(QMainWindow):
    """Compact main application window with efficient layout"""

    # Signals
    frame_updated = pyqtSignal(np.ndarray, list)
    cv_updated = pyqtSignal(np.ndarray)
    visual_updated = pyqtSignal(dict)

    def __init__(self, controller: VAVController):
        super().__init__()
        self.controller = controller
        self.setWindowTitle("VAV Control")
        self.setGeometry(100, 100, 1400, 800)

        # Connect controller callbacks
        self.controller.set_frame_callback(self._on_frame)
        self.controller.set_cv_callback(self._on_cv)
        self.controller.set_visual_callback(self._on_visual)

        # Connect signals to slots (thread-safe)
        self.frame_updated.connect(self._update_frame_display)
        self.cv_updated.connect(self._update_cv_display)
        self.visual_updated.connect(self._update_visual_display)

        # Build UI
        self._build_ui()

        # Status bar
        self.status_label = QLabel("Ready")
        self.statusBar().addWidget(self.status_label)

        # Device status on right side of status bar
        self.device_status_label = QLabel("No devices")
        self.device_status_label.setWordWrap(False)
        self.statusBar().addPermanentWidget(self.device_status_label)

        # Update initial device status
        self._update_device_status()

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

        # Use splitter to make scope resizable
        from PyQt6.QtWidgets import QSplitter
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Scope (resizable)
        scope_group = QGroupBox("Scope")
        scope_layout = QVBoxLayout(scope_group)
        scope_layout.setContentsMargins(2, 2, 2, 2)
        self.scope_widget = ScopeWidget(num_channels=5)
        scope_layout.addWidget(self.scope_widget)
        splitter.addWidget(scope_group)

        # Controls in compact widget
        controls_widget = QWidget()
        controls_grid = QGridLayout(controls_widget)
        controls_grid.setVerticalSpacing(18)    # 9x vertical spacing (3x3)
        controls_grid.setHorizontalSpacing(10)  # 2x horizontal spacing
        controls_grid.setContentsMargins(5, 5, 5, 5)
        # 6 visual columns x 3 grid columns each = 18 columns + 1 stretch
        for i in range(18):
            controls_grid.setColumnStretch(i, 0)  # No stretch for control columns
        controls_grid.setColumnStretch(18, 1)  # Stretch remainder
        self._build_all_controls_inline(controls_grid)
        splitter.addWidget(controls_widget)

        # Set initial sizes: scope gets 40%, controls get 60%
        splitter.setSizes([200, 200])
        splitter.setStretchFactor(0, 2)  # Scope stretches more
        splitter.setStretchFactor(1, 1)  # Controls stay compact

        main_layout.addWidget(splitter)

        # Video window (separate)
        self.video_window = QWidget()
        self.video_window.setWindowTitle("VAV - Video")
        video_layout = QVBoxLayout(self.video_window)
        self.video_label = QLabel()
        self.video_label.setMinimumSize(960, 540)
        self.video_label.setStyleSheet("background-color: black;")
        self.video_label.setScaledContents(True)
        video_layout.addWidget(self.video_label)

    def _build_all_controls_inline(self, grid: QGridLayout):
        """Build all controls in 6-column layout"""

        # Column positions (each visual column uses 3 grid columns)
        COL1 = 0   # CV Source
        COL2 = 3   # Mixer
        COL3 = 6   # Multiverse Main
        COL4 = 9   # Multiverse Channels
        COL5 = 12  # Ellen Ripley Delay+Grain
        COL6 = 15  # Ellen Ripley Reverb+Chaos

        # ===== COLUMN 1: CV Source =====
        row1 = 0

        # ENV Global Decay (exponential: 0.1~1s, 1~5s)
        grid.addWidget(QLabel("ENV Global Decay"), row1, COL1)
        self.env_global_slider = QSlider(Qt.Orientation.Horizontal)
        self.env_global_slider.setFixedHeight(16)
        self.env_global_slider.setFixedWidth(140)
        self.env_global_slider.setMinimum(0)
        self.env_global_slider.setMaximum(100)
        self.env_global_slider.setValue(50)
        self.env_global_slider.valueChanged.connect(self._on_env_global_decay_changed)
        grid.addWidget(self.env_global_slider, row1, COL1 + 1)
        self.env_global_label = QLabel("1.0s")
        self.env_global_label.setFixedWidth(35)
        grid.addWidget(self.env_global_label, row1, COL1 + 2)
        row1 += 1

        # SEQ 1-2 Steps
        self.seq_steps_spinners = []
        for i in range(2):
            grid.addWidget(QLabel(f"SEQ {i+1} Steps"), row1, COL1)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setFixedHeight(16)
            slider.setFixedWidth(140)
            slider.setMinimum(4)
            slider.setMaximum(32)
            slider.setValue(8)
            slider.valueChanged.connect(lambda val, idx=i: self._on_seq_steps_changed(idx, val))
            grid.addWidget(slider, row1, COL1 + 1)
            value = QLabel("8")
            value.setFixedWidth(25)
            grid.addWidget(value, row1, COL1 + 2)
            self.seq_steps_spinners.append((slider, value))
            row1 += 1

        # Unified Clock BPM (統一時鐘)
        grid.addWidget(QLabel("Clock BPM"), row1, COL1)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setFixedHeight(16)
        slider.setFixedWidth(140)
        slider.setMinimum(1)
        slider.setMaximum(999)
        slider.setValue(120)
        slider.valueChanged.connect(self._on_clock_rate_changed)
        grid.addWidget(slider, row1, COL1 + 1)
        value = QLabel("120")
        value.setFixedWidth(35)
        grid.addWidget(value, row1, COL1 + 2)
        self.clock_slider = (slider, value)
        row1 += 1

        # Range
        grid.addWidget(QLabel("Range"), row1, COL1)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setFixedHeight(16)
        slider.setFixedWidth(140)
        slider.setMinimum(0)
        slider.setMaximum(50)
        slider.setValue(50)
        slider.valueChanged.connect(self._on_range_changed)
        grid.addWidget(slider, row1, COL1 + 1)
        value = QLabel("50%")
        value.setFixedWidth(35)
        grid.addWidget(value, row1, COL1 + 2)
        self.range_slider = (slider, value)
        row1 += 1

        # Edge Threshold
        grid.addWidget(QLabel("Threshold"), row1, COL1)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setFixedHeight(16)
        slider.setFixedWidth(140)
        slider.setMinimum(0)
        slider.setMaximum(255)
        slider.setValue(50)
        slider.valueChanged.connect(self._on_threshold_changed)
        grid.addWidget(slider, row1, COL1 + 1)
        value = QLabel("50")
        value.setFixedWidth(35)
        grid.addWidget(value, row1, COL1 + 2)
        self.threshold_slider = (slider, value)
        row1 += 1

        # Smoothing
        grid.addWidget(QLabel("Smoothing"), row1, COL1)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setFixedHeight(16)
        slider.setFixedWidth(140)
        slider.setMinimum(0)
        slider.setMaximum(100)
        slider.setValue(50)
        slider.valueChanged.connect(self._on_smoothing_changed)
        grid.addWidget(slider, row1, COL1 + 1)
        value = QLabel("50")
        value.setFixedWidth(35)
        grid.addWidget(value, row1, COL1 + 2)
        self.smoothing_slider = (slider, value)
        row1 += 1

        # Min Length
        grid.addWidget(QLabel("Min Length"), row1, COL1)
        self.min_length_slider = QSlider(Qt.Orientation.Horizontal)
        self.min_length_slider.setFixedHeight(16)
        self.min_length_slider.setFixedWidth(140)
        self.min_length_slider.setMinimum(10)
        self.min_length_slider.setMaximum(200)
        self.min_length_slider.setValue(50)
        self.min_length_slider.valueChanged.connect(self._on_min_length_changed)
        grid.addWidget(self.min_length_slider, row1, COL1 + 1)
        self.min_length_label = QLabel("50")
        self.min_length_label.setFixedWidth(30)
        grid.addWidget(self.min_length_label, row1, COL1 + 2)
        row1 += 1

        # ===== COLUMN 2: Mixer =====
        row2 = 0
        self.mixer_sliders = []
        for i in range(4):
            grid.addWidget(QLabel(f"Track {i+1} Vol"), row2, COL2)
            mix_slider = QSlider(Qt.Orientation.Horizontal)
            mix_slider.setFixedHeight(16)
            mix_slider.setFixedWidth(120)
            mix_slider.setMinimum(0)
            mix_slider.setMaximum(100)
            mix_slider.setValue(80)
            mix_slider.valueChanged.connect(lambda val, idx=i: self._on_mixer_volume(idx, val / 100.0))
            grid.addWidget(mix_slider, row2, COL2 + 1)
            mix_label = QLabel("0.8")
            mix_label.setFixedWidth(25)
            grid.addWidget(mix_label, row2, COL2 + 2)
            self.mixer_sliders.append((mix_slider, mix_label))
            row2 += 1

        # ===== COLUMN 3: Multiverse Main =====
        row3 = 0

        # Enable
        self.multiverse_checkbox = QCheckBox("Multiverse")
        self.multiverse_checkbox.setChecked(False)
        self.multiverse_checkbox.stateChanged.connect(self._on_multiverse_toggle)
        grid.addWidget(self.multiverse_checkbox, row3, COL3, 1, 2)
        row3 += 1

        # Blend mode
        grid.addWidget(QLabel("Blend"), row3, COL3)
        self.blend_mode_combo = QComboBox()
        self.blend_mode_combo.addItems(["Add", "Scrn", "Diff", "Dodg"])
        self.blend_mode_combo.setFixedHeight(20)
        self.blend_mode_combo.setFixedWidth(120)
        self.blend_mode_combo.currentIndexChanged.connect(self._on_blend_mode_changed)
        grid.addWidget(self.blend_mode_combo, row3, COL3 + 1, 1, 2)
        row3 += 1

        # Brightness
        grid.addWidget(QLabel("Brightness"), row3, COL3)
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setFixedHeight(16)
        self.brightness_slider.setFixedWidth(120)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(400)
        self.brightness_slider.setValue(250)
        self.brightness_slider.valueChanged.connect(self._on_brightness_changed)
        grid.addWidget(self.brightness_slider, row3, COL3 + 1)
        self.brightness_label = QLabel("2.5")
        self.brightness_label.setFixedWidth(25)
        grid.addWidget(self.brightness_label, row3, COL3 + 2)
        row3 += 1

        # Camera Mix
        grid.addWidget(QLabel("Camera Mix"), row3, COL3)
        self.camera_mix_slider = QSlider(Qt.Orientation.Horizontal)
        self.camera_mix_slider.setFixedHeight(16)
        self.camera_mix_slider.setFixedWidth(120)
        self.camera_mix_slider.setMinimum(0)
        self.camera_mix_slider.setMaximum(100)
        self.camera_mix_slider.setValue(0)  # Default: pure multiverse
        self.camera_mix_slider.valueChanged.connect(self._on_camera_mix_changed)
        grid.addWidget(self.camera_mix_slider, row3, COL3 + 1)
        self.camera_mix_label = QLabel("0.0")
        self.camera_mix_label.setFixedWidth(25)
        grid.addWidget(self.camera_mix_label, row3, COL3 + 2)
        row3 += 1

        # Region Rendering
        self.region_rendering_checkbox = QCheckBox("Region Map")
        self.region_rendering_checkbox.setChecked(False)
        self.region_rendering_checkbox.stateChanged.connect(self._on_region_rendering_toggle)
        grid.addWidget(self.region_rendering_checkbox, row3, COL3, 1, 2)
        row3 += 1

        # Region Mode
        grid.addWidget(QLabel("Region Mode"), row3, COL3)
        self.region_mode_combo = QComboBox()
        self.region_mode_combo.addItems(["Bright", "Color", "Quad", "Edge"])
        self.region_mode_combo.setFixedHeight(20)
        self.region_mode_combo.setFixedWidth(120)
        self.region_mode_combo.currentIndexChanged.connect(self._on_region_mode_changed)
        grid.addWidget(self.region_mode_combo, row3, COL3 + 1, 1, 2)
        row3 += 1

        # Ch1-2 controls
        self.channel_curve_sliders = []
        self.channel_angle_sliders = []
        self.channel_intensity_sliders = []
        # GUI slider: 0-360, mapped to -180 to +180
        # So 180 = 0°, 225 = 45°, 270 = 90°, 315 = 135°
        default_angles = [180, 225, 270, 315]

        for i in range(2):
            # Curve
            grid.addWidget(QLabel(f"Ch{i+1} Curve"), row3, COL3)
            curve_slider = QSlider(Qt.Orientation.Horizontal)
            curve_slider.setFixedHeight(16)
            curve_slider.setFixedWidth(120)
            curve_slider.setMinimum(0)
            curve_slider.setMaximum(100)
            curve_slider.setValue(0)
            curve_slider.valueChanged.connect(lambda val, idx=i: self._on_channel_curve_changed(idx, val))
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
            angle_slider.setMinimum(0)
            angle_slider.setMaximum(360)
            angle_slider.setValue(default_angles[i])
            angle_slider.valueChanged.connect(lambda val, idx=i: self._on_channel_angle_changed(idx, val))
            grid.addWidget(angle_slider, row3, COL3 + 1)
            angle_label = QLabel(f"{default_angles[i]}°")
            angle_label.setFixedWidth(30)
            grid.addWidget(angle_label, row3, COL3 + 2)
            self.channel_angle_sliders.append((angle_slider, angle_label))
            row3 += 1

            # Intensity
            grid.addWidget(QLabel(f"Ch{i+1} Intensity"), row3, COL3)
            intensity_slider = QSlider(Qt.Orientation.Horizontal)
            intensity_slider.setFixedHeight(16)
            intensity_slider.setFixedWidth(120)
            intensity_slider.setMinimum(0)
            intensity_slider.setMaximum(150)
            intensity_slider.setValue(100)
            intensity_slider.valueChanged.connect(lambda val, idx=i: self._on_channel_intensity_changed(idx, val))
            grid.addWidget(intensity_slider, row3, COL3 + 1)
            intensity_label = QLabel("1.0")
            intensity_label.setFixedWidth(25)
            grid.addWidget(intensity_label, row3, COL3 + 2)
            self.channel_intensity_sliders.append((intensity_slider, intensity_label))
            row3 += 1

        # ===== COLUMN 4: Multiverse Channels =====
        row4 = 0

        # Ch3-4 controls
        for i in range(2, 4):
            # Curve
            grid.addWidget(QLabel(f"Ch{i+1} Curve"), row4, COL4)
            curve_slider = QSlider(Qt.Orientation.Horizontal)
            curve_slider.setFixedHeight(16)
            curve_slider.setFixedWidth(120)
            curve_slider.setMinimum(0)
            curve_slider.setMaximum(100)
            curve_slider.setValue(0)
            curve_slider.valueChanged.connect(lambda val, idx=i: self._on_channel_curve_changed(idx, val))
            grid.addWidget(curve_slider, row4, COL4 + 1)
            curve_label = QLabel("0.0")
            curve_label.setFixedWidth(25)
            grid.addWidget(curve_label, row4, COL4 + 2)
            self.channel_curve_sliders.append((curve_slider, curve_label))
            row4 += 1

            # Angle
            grid.addWidget(QLabel(f"Ch{i+1} Angle"), row4, COL4)
            angle_slider = QSlider(Qt.Orientation.Horizontal)
            angle_slider.setFixedHeight(16)
            angle_slider.setFixedWidth(120)
            angle_slider.setMinimum(0)
            angle_slider.setMaximum(360)
            angle_slider.setValue(default_angles[i])
            angle_slider.valueChanged.connect(lambda val, idx=i: self._on_channel_angle_changed(idx, val))
            grid.addWidget(angle_slider, row4, COL4 + 1)
            angle_label = QLabel(f"{default_angles[i]}°")
            angle_label.setFixedWidth(30)
            grid.addWidget(angle_label, row4, COL4 + 2)
            self.channel_angle_sliders.append((angle_slider, angle_label))
            row4 += 1

            # Intensity
            grid.addWidget(QLabel(f"Ch{i+1} Intensity"), row4, COL4)
            intensity_slider = QSlider(Qt.Orientation.Horizontal)
            intensity_slider.setFixedHeight(16)
            intensity_slider.setFixedWidth(120)
            intensity_slider.setMinimum(0)
            intensity_slider.setMaximum(150)
            intensity_slider.setValue(100)
            intensity_slider.valueChanged.connect(lambda val, idx=i: self._on_channel_intensity_changed(idx, val))
            grid.addWidget(intensity_slider, row4, COL4 + 1)
            intensity_label = QLabel("1.0")
            intensity_label.setFixedWidth(25)
            grid.addWidget(intensity_label, row4, COL4 + 2)
            self.channel_intensity_sliders.append((intensity_slider, intensity_label))
            row4 += 1

        # ===== COLUMN 5: Ellen Ripley Delay+Grain =====
        row5 = 0

        # Enable
        self.ellen_ripley_checkbox = QCheckBox("Ellen Ripley")
        self.ellen_ripley_checkbox.setChecked(False)
        self.ellen_ripley_checkbox.stateChanged.connect(self._on_ellen_ripley_toggle)
        grid.addWidget(self.ellen_ripley_checkbox, row5, COL5, 1, 3)
        row5 += 1

        # Delay Time L
        grid.addWidget(QLabel("Delay Time L"), row5, COL5)
        self.er_delay_time_l_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_delay_time_l_slider.setFixedHeight(16)
        self.er_delay_time_l_slider.setFixedWidth(120)
        self.er_delay_time_l_slider.setMinimum(1)
        self.er_delay_time_l_slider.setMaximum(2000)
        self.er_delay_time_l_slider.setValue(250)
        self.er_delay_time_l_slider.valueChanged.connect(self._on_er_delay_time_l_changed)
        grid.addWidget(self.er_delay_time_l_slider, row5, COL5 + 1)
        self.er_delay_time_l_label = QLabel("0.25s")
        self.er_delay_time_l_label.setFixedWidth(35)
        grid.addWidget(self.er_delay_time_l_label, row5, COL5 + 2)
        row5 += 1

        # Delay Time R
        grid.addWidget(QLabel("Delay Time R"), row5, COL5)
        self.er_delay_time_r_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_delay_time_r_slider.setFixedHeight(16)
        self.er_delay_time_r_slider.setFixedWidth(120)
        self.er_delay_time_r_slider.setMinimum(1)
        self.er_delay_time_r_slider.setMaximum(2000)
        self.er_delay_time_r_slider.setValue(250)
        self.er_delay_time_r_slider.valueChanged.connect(self._on_er_delay_time_r_changed)
        grid.addWidget(self.er_delay_time_r_slider, row5, COL5 + 1)
        self.er_delay_time_r_label = QLabel("0.25s")
        self.er_delay_time_r_label.setFixedWidth(35)
        grid.addWidget(self.er_delay_time_r_label, row5, COL5 + 2)
        row5 += 1

        # Delay FB
        grid.addWidget(QLabel("Delay FB"), row5, COL5)
        self.er_delay_fb_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_delay_fb_slider.setFixedHeight(16)
        self.er_delay_fb_slider.setFixedWidth(120)
        self.er_delay_fb_slider.setMinimum(0)
        self.er_delay_fb_slider.setMaximum(95)
        self.er_delay_fb_slider.setValue(30)
        self.er_delay_fb_slider.valueChanged.connect(self._on_er_delay_fb_changed)
        grid.addWidget(self.er_delay_fb_slider, row5, COL5 + 1)
        self.er_delay_fb_label = QLabel("0.30")
        self.er_delay_fb_label.setFixedWidth(30)
        grid.addWidget(self.er_delay_fb_label, row5, COL5 + 2)
        row5 += 1

        # Delay Chaos + Mix on same row
        self.er_delay_chaos_checkbox = QCheckBox("Dly Chaos")
        self.er_delay_chaos_checkbox.stateChanged.connect(self._on_er_delay_chaos_changed)
        grid.addWidget(self.er_delay_chaos_checkbox, row5, COL5)

        self.er_delay_mix_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_delay_mix_slider.setFixedHeight(16)
        self.er_delay_mix_slider.setFixedWidth(120)
        self.er_delay_mix_slider.setMinimum(0)
        self.er_delay_mix_slider.setMaximum(100)
        self.er_delay_mix_slider.setValue(0)
        self.er_delay_mix_slider.valueChanged.connect(self._on_er_delay_mix_changed)
        grid.addWidget(self.er_delay_mix_slider, row5, COL5 + 1, 1, 2)
        row5 += 1

        # Grain Size
        grid.addWidget(QLabel("Grain Size"), row5, COL5)
        self.er_grain_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_grain_size_slider.setFixedHeight(16)
        self.er_grain_size_slider.setFixedWidth(120)
        self.er_grain_size_slider.setMinimum(0)
        self.er_grain_size_slider.setMaximum(100)
        self.er_grain_size_slider.setValue(30)
        self.er_grain_size_slider.valueChanged.connect(self._on_er_grain_size_changed)
        grid.addWidget(self.er_grain_size_slider, row5, COL5 + 1)
        self.er_grain_size_label = QLabel("0.30")
        self.er_grain_size_label.setFixedWidth(30)
        grid.addWidget(self.er_grain_size_label, row5, COL5 + 2)
        row5 += 1

        # Grain Density
        grid.addWidget(QLabel("Grain Density"), row5, COL5)
        self.er_grain_density_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_grain_density_slider.setFixedHeight(16)
        self.er_grain_density_slider.setFixedWidth(120)
        self.er_grain_density_slider.setMinimum(0)
        self.er_grain_density_slider.setMaximum(100)
        self.er_grain_density_slider.setValue(40)
        self.er_grain_density_slider.valueChanged.connect(self._on_er_grain_density_changed)
        grid.addWidget(self.er_grain_density_slider, row5, COL5 + 1)
        self.er_grain_density_label = QLabel("0.40")
        self.er_grain_density_label.setFixedWidth(30)
        grid.addWidget(self.er_grain_density_label, row5, COL5 + 2)
        row5 += 1

        # Grain Position
        grid.addWidget(QLabel("Grain Position"), row5, COL5)
        self.er_grain_pos_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_grain_pos_slider.setFixedHeight(16)
        self.er_grain_pos_slider.setFixedWidth(120)
        self.er_grain_pos_slider.setMinimum(0)
        self.er_grain_pos_slider.setMaximum(100)
        self.er_grain_pos_slider.setValue(50)
        self.er_grain_pos_slider.valueChanged.connect(self._on_er_grain_pos_changed)
        grid.addWidget(self.er_grain_pos_slider, row5, COL5 + 1)
        self.er_grain_pos_label = QLabel("0.50")
        self.er_grain_pos_label.setFixedWidth(30)
        grid.addWidget(self.er_grain_pos_label, row5, COL5 + 2)
        row5 += 1

        # Grain Chaos + Mix on same row
        self.er_grain_chaos_checkbox = QCheckBox("Grn Chaos")
        self.er_grain_chaos_checkbox.stateChanged.connect(self._on_er_grain_chaos_changed)
        grid.addWidget(self.er_grain_chaos_checkbox, row5, COL5)

        self.er_grain_mix_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_grain_mix_slider.setFixedHeight(16)
        self.er_grain_mix_slider.setFixedWidth(120)
        self.er_grain_mix_slider.setMinimum(0)
        self.er_grain_mix_slider.setMaximum(100)
        self.er_grain_mix_slider.setValue(0)
        self.er_grain_mix_slider.valueChanged.connect(self._on_er_grain_mix_changed)
        grid.addWidget(self.er_grain_mix_slider, row5, COL5 + 1, 1, 2)
        row5 += 1

        # ===== COLUMN 6: Ellen Ripley Reverb+Chaos =====
        row6 = 0

        # Reverb Room
        grid.addWidget(QLabel("Reverb Room"), row6, COL6)
        self.er_reverb_room_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_reverb_room_slider.setFixedHeight(16)
        self.er_reverb_room_slider.setFixedWidth(120)
        self.er_reverb_room_slider.setMinimum(0)
        self.er_reverb_room_slider.setMaximum(100)
        self.er_reverb_room_slider.setValue(50)
        self.er_reverb_room_slider.valueChanged.connect(self._on_er_reverb_room_changed)
        grid.addWidget(self.er_reverb_room_slider, row6, COL6 + 1)
        self.er_reverb_room_label = QLabel("0.50")
        self.er_reverb_room_label.setFixedWidth(30)
        grid.addWidget(self.er_reverb_room_label, row6, COL6 + 2)
        row6 += 1

        # Reverb Damping
        grid.addWidget(QLabel("Reverb Damp"), row6, COL6)
        self.er_reverb_damp_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_reverb_damp_slider.setFixedHeight(16)
        self.er_reverb_damp_slider.setFixedWidth(120)
        self.er_reverb_damp_slider.setMinimum(0)
        self.er_reverb_damp_slider.setMaximum(100)
        self.er_reverb_damp_slider.setValue(40)
        self.er_reverb_damp_slider.valueChanged.connect(self._on_er_reverb_damp_changed)
        grid.addWidget(self.er_reverb_damp_slider, row6, COL6 + 1)
        self.er_reverb_damp_label = QLabel("0.40")
        self.er_reverb_damp_label.setFixedWidth(30)
        grid.addWidget(self.er_reverb_damp_label, row6, COL6 + 2)
        row6 += 1

        # Reverb Decay
        grid.addWidget(QLabel("Reverb Decay"), row6, COL6)
        self.er_reverb_decay_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_reverb_decay_slider.setFixedHeight(16)
        self.er_reverb_decay_slider.setFixedWidth(120)
        self.er_reverb_decay_slider.setMinimum(0)
        self.er_reverb_decay_slider.setMaximum(100)
        self.er_reverb_decay_slider.setValue(60)
        self.er_reverb_decay_slider.valueChanged.connect(self._on_er_reverb_decay_changed)
        grid.addWidget(self.er_reverb_decay_slider, row6, COL6 + 1)
        self.er_reverb_decay_label = QLabel("0.60")
        self.er_reverb_decay_label.setFixedWidth(30)
        grid.addWidget(self.er_reverb_decay_label, row6, COL6 + 2)
        row6 += 1

        # Reverb Chaos + Mix on same row
        self.er_reverb_chaos_checkbox = QCheckBox("Rev Chaos")
        self.er_reverb_chaos_checkbox.stateChanged.connect(self._on_er_reverb_chaos_changed)
        grid.addWidget(self.er_reverb_chaos_checkbox, row6, COL6)

        self.er_reverb_mix_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_reverb_mix_slider.setFixedHeight(16)
        self.er_reverb_mix_slider.setFixedWidth(120)
        self.er_reverb_mix_slider.setMinimum(0)
        self.er_reverb_mix_slider.setMaximum(100)
        self.er_reverb_mix_slider.setValue(0)
        self.er_reverb_mix_slider.valueChanged.connect(self._on_er_reverb_mix_changed)
        grid.addWidget(self.er_reverb_mix_slider, row6, COL6 + 1, 1, 2)
        row6 += 1

        # Chaos Rate
        grid.addWidget(QLabel("Chaos Rate"), row6, COL6)
        self.er_chaos_rate_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_chaos_rate_slider.setFixedHeight(16)
        self.er_chaos_rate_slider.setFixedWidth(120)
        self.er_chaos_rate_slider.setMinimum(0)
        self.er_chaos_rate_slider.setMaximum(100)
        self.er_chaos_rate_slider.setValue(1)
        self.er_chaos_rate_slider.valueChanged.connect(self._on_er_chaos_rate_changed)
        grid.addWidget(self.er_chaos_rate_slider, row6, COL6 + 1)
        self.er_chaos_rate_label = QLabel("0.01")
        self.er_chaos_rate_label.setFixedWidth(30)
        grid.addWidget(self.er_chaos_rate_label, row6, COL6 + 2)
        row6 += 1

        # Chaos Amount
        grid.addWidget(QLabel("Chaos Amount"), row6, COL6)
        self.er_chaos_amount_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_chaos_amount_slider.setFixedHeight(16)
        self.er_chaos_amount_slider.setFixedWidth(120)
        self.er_chaos_amount_slider.setMinimum(0)
        self.er_chaos_amount_slider.setMaximum(100)
        self.er_chaos_amount_slider.setValue(100)
        self.er_chaos_amount_slider.valueChanged.connect(self._on_er_chaos_amount_changed)
        grid.addWidget(self.er_chaos_amount_slider, row6, COL6 + 1)
        self.er_chaos_amount_label = QLabel("1.00")
        self.er_chaos_amount_label.setFixedWidth(30)
        grid.addWidget(self.er_chaos_amount_label, row6, COL6 + 2)
        row6 += 1

        # Chaos Shape
        self.er_chaos_shape_checkbox = QCheckBox("Chaos Shape")
        self.er_chaos_shape_checkbox.stateChanged.connect(self._on_er_chaos_shape_changed)
        grid.addWidget(self.er_chaos_shape_checkbox, row6, COL6, 1, 3)
        row6 += 1

        # Anchor XY Pad (below column 6)
        grid.addWidget(QLabel("Anchor XY"), row6, COL6)
        row6 += 1

        self.anchor_xy_pad = AnchorXYPad()
        self.anchor_xy_pad.position_changed.connect(self._on_anchor_xy_changed)
        grid.addWidget(self.anchor_xy_pad, row6, COL6, 3, 3)  # Span 3 rows, 3 columns

        # Position labels below pad
        row6 += 3
        self.anchor_xy_label = QLabel("X: 50%  Y: 50%")
        grid.addWidget(self.anchor_xy_label, row6, COL6, 1, 3)

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
        slider.setMinimum(0)
        slider.setMaximum(50)
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

        # Cable detection
        cable_layout = QGridLayout()
        cable_layout.setSpacing(2)
        min_label = QLabel("MinL")
        min_label.setFixedWidth(30)
        cable_layout.addWidget(min_label, 0, 0)
        self.min_length_slider = QSlider(Qt.Orientation.Horizontal)
        self.min_length_slider.setFixedHeight(18)
        self.min_length_slider.setMinimum(10)
        self.min_length_slider.setMaximum(200)
        self.min_length_slider.setValue(50)
        self.min_length_slider.valueChanged.connect(self._on_min_length_changed)
        cable_layout.addWidget(self.min_length_slider, 0, 1)
        self.min_length_label = QLabel("50")
        self.min_length_label.setFixedWidth(25)
        cable_layout.addWidget(self.min_length_label, 0, 2)
        layout.addLayout(cable_layout)

        return widget

    # Event handlers
    def _on_start(self):
        self.controller.start()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText("Running")
        self._update_device_status()  # Update device status when starting

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

    def _on_seq_steps_changed(self, seq_idx: int, value: int):
        # Note: Num steps is now controlled by ContourCVGenerator parameters
        # This is kept for backward compatibility but may not be used
        _, label = self.seq_steps_spinners[seq_idx]
        label.setText(str(value))

    def _on_clock_rate_changed(self, value: int):
        """Unified clock rate for both SEQ1 and SEQ2"""
        self.controller.set_cv_clock_rate(float(value))
        _, label = self.clock_slider
        label.setText(str(value))

    def _on_anchor_xy_changed(self, x_pct: float, y_pct: float):
        """Anchor XY position changed from 2D pad"""
        self.controller.set_anchor_position(x_pct, y_pct)
        self.anchor_xy_label.setText(f"X: {x_pct:.0f}%  Y: {y_pct:.0f}%")

    def _on_range_changed(self, value: int):
        """Sampling range from anchor (0-50%)"""
        self.controller.set_cv_range(float(value))
        _, label = self.range_slider
        label.setText(f"{value}%")

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
        self.controller.set_mixer_params(track, volume=value)
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

    def _on_min_length_changed(self, value: int):
        self.min_length_label.setText(str(value))
        if self.controller.cable_detector:
            self.controller.cable_detector.min_length = value

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

    def _on_blend_mode_changed(self, index: int):
        self.controller.set_renderer_blend_mode(index)
        mode_names = ["Add", "Screen", "Diff", "Dodge"]
        self.status_label.setText(f"Blend: {mode_names[index]}")

    def _on_brightness_changed(self, value: int):
        brightness = value / 100.0
        self.brightness_label.setText(f"{brightness:.1f}")
        self.controller.set_renderer_brightness(brightness)

    def _on_region_rendering_toggle(self, state: int):
        """Toggle region-based rendering"""
        enabled = state == Qt.CheckState.Checked.value
        self.controller.enable_region_rendering(enabled)
        status = "Region ON" if enabled else "Region OFF"
        self.status_label.setText(status)

    def _on_region_mode_changed(self, index: int):
        """Change region rendering mode"""
        modes = ['brightness', 'color', 'quadrant', 'edge']
        mode = modes[index]
        self.controller.set_region_mode(mode)
        mode_names = ['Brightness', 'Color', 'Quadrant', 'Edge']
        self.status_label.setText(f"Region: {mode_names[index]}")

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

    def _on_channel_intensity_changed(self, channel: int, value: int):
        """Channel intensity changed"""
        intensity = value / 100.0
        _, label = self.channel_intensity_sliders[channel]
        label.setText(f"{intensity:.1f}")
        self.controller.set_renderer_channel_intensity(channel, intensity)

    def _on_camera_mix_changed(self, value: int):
        """Camera mix changed"""
        camera_mix = value / 100.0
        self.camera_mix_label.setText(f"{camera_mix:.1f}")
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

    # Controller callbacks
    def _on_frame(self, frame: np.ndarray, cables: list):
        self.frame_updated.emit(frame, cables)

    def _on_cv(self, cv_values: np.ndarray):
        self.cv_updated.emit(cv_values)

    def _on_visual(self, visual_params: dict):
        self.visual_updated.emit(visual_params)

    # Qt slots
    def _update_frame_display(self, frame: np.ndarray, cables: list):
        # Frame is already rendered (Simple or Multiverse mode) by controller
        # Just display it directly
        height, width = frame.shape[:2]
        bytes_per_line = 3 * width
        q_image = QImage(frame.data, width, height, bytes_per_line,
                        QImage.Format.Format_RGB888).rgbSwapped()
        self.video_label.setPixmap(QPixmap.fromImage(q_image))

    def _update_cv_display(self, cv_values: np.ndarray):
        self.scope_widget.add_samples(cv_values)
        # CV Meter Window removed - use Scope Widget instead

    def _update_visual_display(self, visual_params: dict):
        pass

    def closeEvent(self, event):
        self.controller.stop()
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
