"""
獨立的 CV Meters 視窗
"""

import numpy as np
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QMenu, QSlider, QLabel
from PyQt6.QtCore import Qt, pyqtSignal
from .meter_widget import MeterWidget
from .visual_preview_widget import VisualPreviewWidget


class CVMeterWindow(QMainWindow):
    """獨立可調整大小的 CV Meters 視窗"""

    # Signal for thread-safe MIDI anchor updates
    midi_anchor_updated = pyqtSignal(str, float)  # axis ('x' or 'y'), value

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CV Meters")
        # Visual Preview with anchor overlay (546x230 + meters)
        self.resize(560, 480)

        # 中央 widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)

        # Meter widget (6 channels: ENV1-4, SEQ1-2)
        self.meter_widget = MeterWidget(num_channels=6)
        self.meter_widget.setMinimumHeight(180)
        self.meter_widget.mute_changed.connect(self._on_mute_changed)
        layout.addWidget(self.meter_widget, stretch=1)

        # Bottom row: Range slider + Visual Preview
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(10)

        # Range slider (vertical, left side)
        range_container = QVBoxLayout()
        range_container.setSpacing(5)

        range_label = QLabel("Range")
        range_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        range_container.addWidget(range_label)

        self.range_slider = QSlider(Qt.Orientation.Vertical)
        self.range_slider.setMinimum(1)
        self.range_slider.setMaximum(120)
        self.range_slider.setValue(50)
        self.range_slider.setFixedHeight(200)
        self.range_slider.valueChanged.connect(self._on_range_changed)
        range_container.addWidget(self.range_slider)

        self.range_value_label = QLabel("50%")
        self.range_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        range_container.addWidget(self.range_value_label)

        bottom_layout.addLayout(range_container)

        # Visual Preview with anchor overlay (546x306)
        self.visual_preview = VisualPreviewWidget()
        bottom_layout.addWidget(self.visual_preview)

        layout.addLayout(bottom_layout)

        # MIDI Learn reference (will be set by main window)
        self.midi_learn = None

        # Controller reference (will be set by main window)
        self.controller = None

        # Connect MIDI anchor signal for thread-safe updates
        self.midi_anchor_updated.connect(self._on_midi_anchor_update)

    def set_controller(self, controller):
        """設定 controller 並連接 anchor position signal"""
        self.controller = controller

        # Connect visual preview position changes to controller
        def on_position_changed(x_pct, y_pct):
            if self.controller and self.controller.contour_cv_generator:
                self.controller.contour_cv_generator.set_anchor_position(x_pct, y_pct)

        self.visual_preview.position_changed.connect(on_position_changed)

    def _on_range_changed(self, value: int):
        """Range slider changed"""
        self.range_value_label.setText(f"{value}%")
        self.visual_preview.set_range(float(value))

        # Update controller
        if self.controller and self.controller.contour_cv_generator:
            self.controller.contour_cv_generator.set_range(float(value))

    def setup_midi_learn(self, midi_learn):
        """設定 MIDI Learn 並註冊 Anchor XY 參數"""
        self.midi_learn = midi_learn

        # Register Anchor X/Y for MIDI Learn (thread-safe via signal)
        def anchor_x_midi_callback(value):
            # Emit signal to update GUI in main thread (thread-safe)
            self.midi_anchor_updated.emit('x', value)

        def anchor_y_midi_callback(value):
            # Emit signal to update GUI in main thread (thread-safe)
            self.midi_anchor_updated.emit('y', value)

        self.midi_learn.register_parameter("anchor_x", anchor_x_midi_callback, 0.0, 100.0)
        self.midi_learn.register_parameter("anchor_y", anchor_y_midi_callback, 0.0, 100.0)

        # Setup context menu for MIDI Learn
        self._setup_midi_context_menu()

    def _on_midi_anchor_update(self, axis: str, value: float):
        """Handle MIDI anchor update in main thread (thread-safe)"""
        if axis == 'x':
            self.visual_preview.set_position(value, self.visual_preview.y_pct, emit_signal=True)
        elif axis == 'y':
            # Invert Y: MIDI 0-100 → GUI 100-0
            inverted_y = 100.0 - value
            self.visual_preview.set_position(self.visual_preview.x_pct, inverted_y, emit_signal=True)

    def _setup_midi_context_menu(self):
        """Add context menu for Visual Preview MIDI Learn"""
        def show_xy_context_menu(pos):
            menu = QMenu()
            learn_x_action = menu.addAction("MIDI Learn X")
            learn_y_action = menu.addAction("MIDI Learn Y")
            menu.addSeparator()
            clear_x_action = menu.addAction("Clear X Mapping")
            clear_y_action = menu.addAction("Clear Y Mapping")
            menu.addSeparator()
            clear_all_action = menu.addAction("Clear All MIDI Mappings")

            action = menu.exec(self.visual_preview.mapToGlobal(pos))

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

        self.visual_preview.customContextMenuRequested.connect(show_xy_context_menu)

    def update_values(self, samples: np.ndarray):
        """更新 CV 值"""
        self.meter_widget.update_values(samples)

    def update_visual_preview(self, frame: np.ndarray):
        """更新 visual preview"""
        self.visual_preview.update_frame(frame)

    def _on_mute_changed(self, channel: int, muted: bool):
        """處理 mute 狀態改變"""
        if self.controller:
            # Channel mapping: 0-3=ENV1-4, 4-5=SEQ1-2
            self.controller.set_cv_channel_mute(channel, muted)
            print(f"CV Channel {channel} muted: {muted}")

    def clear(self):
        """清除所有 meters 和 preview"""
        self.meter_widget.clear()
        self.visual_preview.clear()
