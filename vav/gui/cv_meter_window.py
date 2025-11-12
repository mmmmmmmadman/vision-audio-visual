"""
獨立的 CV Meters 視窗
"""

import numpy as np
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QMenu
from PyQt6.QtCore import Qt
from .meter_widget import MeterWidget
from .anchor_xy_pad import AnchorXYPad


class CVMeterWindow(QMainWindow):
    """獨立可調整大小的 CV Meters 視窗"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CV Meters")
        self.resize(600, 370)  # 增加高度以容納 XY Pad (210 + 160)

        # 中央 widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Meter widget (6 channels: ENV1-4, SEQ1-2)
        self.meter_widget = MeterWidget(num_channels=6)
        layout.addWidget(self.meter_widget)

        # Anchor XY Pad
        self.anchor_xy_pad = AnchorXYPad()
        layout.addWidget(self.anchor_xy_pad)

        # MIDI Learn reference (will be set by main window)
        self.midi_learn = None

    def setup_midi_learn(self, midi_learn):
        """設定 MIDI Learn 並註冊 Anchor XY 參數"""
        self.midi_learn = midi_learn

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

    def update_values(self, samples: np.ndarray):
        """更新 CV 值"""
        self.meter_widget.update_values(samples)

    def clear(self):
        """清除所有 meters"""
        self.meter_widget.clear()
