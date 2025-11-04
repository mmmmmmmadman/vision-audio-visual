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
        self.resize(500, 180)

        # 中央 widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        # Meter widget
        self.meter_widget = MeterWidget(num_channels=5)
        layout.addWidget(self.meter_widget)

    def update_values(self, samples: np.ndarray):
        """更新 CV 值"""
        self.meter_widget.update_values(samples)

    def clear(self):
        """清除所有 meters"""
        self.meter_widget.clear()
