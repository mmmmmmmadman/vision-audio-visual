"""
獨立的 CV Meters 視窗
"""

import numpy as np
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt
from .meter_widget import MeterWidget


class CVMeterWindow(QMainWindow):
    """獨立可調整大小的 CV Meters 視窗"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CV Meters")
        self.resize(600, 210)  # 調整大小以容納 6 個 channels

        # 中央 widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        # Meter widget (6 channels: ENV1-4, SEQ1-2)
        self.meter_widget = MeterWidget(num_channels=6)
        layout.addWidget(self.meter_widget)

    def update_values(self, samples: np.ndarray):
        """更新 CV 值"""
        self.meter_widget.update_values(samples)

    def clear(self):
        """清除所有 meters"""
        self.meter_widget.clear()
