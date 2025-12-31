"""
Vertical meter widget for CV signals (極簡風格)
"""

import numpy as np
from PyQt6.QtWidgets import QWidget, QSizePolicy
from PyQt6.QtCore import Qt, QRectF, QRect, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen
from ..utils.cv_colors import SCOPE_COLORS


class MeterWidget(QWidget):
    """Minimalist vertical meter for CV visualization"""

    # Signal emitted when mute state changes (channel_index, is_muted)
    mute_changed = pyqtSignal(int, bool)

    def __init__(self, num_channels: int = 6):
        """
        Initialize meter widget (horizontal layout)

        Args:
            num_channels: Number of channels to display (6 = 4 ENV + 2 SEQ)
        """
        super().__init__()
        self.num_channels = num_channels
        self.setMinimumHeight(100)  # 增加高度以容納 6 個 channels
        self.setMinimumWidth(240)  # 最小寬度

        # 設置 size policy 讓 widget 可以水平擴展
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # Current values for each channel (0.0 - 1.0)
        self.values = np.zeros(num_channels, dtype=np.float32)

        # Peak hold for each channel
        self.peaks = np.zeros(num_channels, dtype=np.float32)
        self.peak_hold_frames = np.zeros(num_channels, dtype=np.int32)
        self.peak_hold_duration = 10  # frames

        # Colors from unified color scheme (ENV1-4, SEQ1-2)
        self.colors = [QColor(*rgb) for rgb in SCOPE_COLORS]

        # Channel labels
        self.labels = ["ENV1", "ENV2", "ENV3", "ENV4", "SEQ1", "SEQ2"]

        # Mute state for each channel
        self.muted = np.zeros(num_channels, dtype=bool)

        # Mute button rectangles for click detection
        self.mute_button_rects = []

        # Styling
        self.setStyleSheet("background-color: #000000;")

    def update_values(self, samples: np.ndarray):
        """
        Update meter values

        Args:
            samples: Array of values (0.0-1.0) for each channel
        """
        if len(samples) != self.num_channels:
            print(f"METER DEBUG: Wrong length {len(samples)} != {self.num_channels}")
            return

        self.values = np.clip(samples, 0.0, 1.0)

        # Update peak hold
        for i in range(self.num_channels):
            if self.values[i] > self.peaks[i]:
                self.peaks[i] = self.values[i]
                self.peak_hold_frames[i] = self.peak_hold_duration
            else:
                # Decay peak hold
                if self.peak_hold_frames[i] > 0:
                    self.peak_hold_frames[i] -= 1
                else:
                    # Slow decay
                    self.peaks[i] = max(0.0, self.peaks[i] - 0.02)

        self.update()

    def mousePressEvent(self, event):
        """Handle mouse clicks for mute buttons"""
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()
            for i, rect in enumerate(self.mute_button_rects):
                if rect.contains(pos):
                    # Toggle mute state
                    self.muted[i] = not self.muted[i]
                    self.mute_changed.emit(i, bool(self.muted[i]))
                    self.update()
                    break

    def set_mute(self, channel: int, muted: bool):
        """Set mute state for a channel"""
        if 0 <= channel < self.num_channels:
            self.muted[channel] = muted
            self.update()

    def paintEvent(self, event):
        """Paint the meters (horizontal layout)"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()

        # Calculate meter dimensions (horizontal)
        mute_button_size = 16
        mute_button_margin = 5
        label_width = 40
        value_text_width = 50  # 右側數值顯示區域
        margin = 10
        meter_spacing = 20
        # meter 寬度填滿可用空間
        available_width = width - mute_button_size - mute_button_margin - label_width - value_text_width - margin
        meter_width = max(100, available_width)
        meter_height = 15  # 固定高度

        start_y = (height - meter_height * self.num_channels - meter_spacing * (self.num_channels - 1)) // 2

        # Clear button rects
        self.mute_button_rects = []

        for i in range(self.num_channels):
            y = start_y + i * (meter_height + meter_spacing)

            # Draw mute button (left side)
            button_x = 2
            button_y = y + (meter_height - mute_button_size) // 2
            button_rect = QRect(button_x, button_y, mute_button_size, mute_button_size)
            self.mute_button_rects.append(button_rect)

            # Button background
            if self.muted[i]:
                painter.setBrush(QColor(180, 60, 60))  # Red when muted
                painter.setPen(QPen(QColor(200, 80, 80), 1))
            else:
                painter.setBrush(QColor(60, 60, 60))  # Gray when active
                painter.setPen(QPen(QColor(100, 100, 100), 1))

            painter.drawRect(button_x, button_y, mute_button_size, mute_button_size)

            # Draw M text
            painter.setPen(QPen(QColor(220, 220, 220), 1))
            painter.drawText(
                button_x, button_y,
                mute_button_size, mute_button_size,
                Qt.AlignmentFlag.AlignCenter,
                "M"
            )

            # Draw label (after mute button)
            label_x = button_x + mute_button_size + mute_button_margin
            painter.setPen(QPen(QColor(200, 200, 200), 1))
            painter.drawText(
                label_x, y,
                label_width - 5, meter_height,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                self.labels[i]
            )

            # Meter starts after label
            meter_x = label_x + label_width

            # Draw background (dark gray)
            painter.setPen(QPen(QColor(60, 60, 60), 1))
            painter.setBrush(QColor(20, 20, 20))
            painter.drawRect(meter_x, y, meter_width, meter_height)

            # Draw meter bar (horizontal fill from left)
            bar_width = int(self.values[i] * meter_width)
            if bar_width > 0:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(self.colors[i])
                painter.drawRect(
                    meter_x + 1,
                    y + 1,
                    bar_width - 2,
                    meter_height - 2
                )

            # Draw peak hold line (vertical)
            if self.peaks[i] > 0.01:
                peak_x = meter_x + int(self.peaks[i] * meter_width)
                painter.setPen(QPen(self.colors[i], 2))
                painter.drawLine(peak_x, y, peak_x, y + meter_height)

            # Draw value text (right side of meter) - display as voltage (0-10V)
            if self.values[i] > 0.01:
                voltage = self.values[i] * 10.0  # Convert 0-1 to 0-10V
                value_text = f"{voltage:.1f}V"
                painter.setPen(QPen(self.colors[i], 1))
                painter.drawText(
                    meter_x + meter_width + 5, y,
                    40, meter_height,
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    value_text
                )

    def clear(self):
        """Clear all meters"""
        self.values.fill(0.0)
        self.peaks.fill(0.0)
        self.peak_hold_frames.fill(0)
        self.update()
