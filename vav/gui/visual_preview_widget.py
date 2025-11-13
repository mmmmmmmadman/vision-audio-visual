"""
Visual preview widget - displays main visual output in small preview
"""

import numpy as np
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QImage, QPixmap


class VisualPreviewWidget(QWidget):
    """Preview widget showing main visual output (273x153 to match Anchor XY Pad)"""

    def __init__(self):
        super().__init__()
        self.setFixedSize(273, 153)
        self.setStyleSheet("background-color: #000000; border: 1px solid #404040;")

        # Current frame (RGB numpy array or None)
        self.frame = None

    def update_frame(self, frame: np.ndarray):
        """
        Update preview with new frame

        Args:
            frame: RGB image as numpy array (H, W, 3) uint8
        """
        self.frame = frame
        self.update()

    def paintEvent(self, event):
        """Paint the preview frame"""
        painter = QPainter(self)

        if self.frame is None:
            # No frame yet, draw black background
            painter.fillRect(self.rect(), Qt.GlobalColor.black)
            return

        # Convert numpy array to QImage
        height, width, channels = self.frame.shape
        bytes_per_line = channels * width

        qimage = QImage(
            self.frame.data,
            width,
            height,
            bytes_per_line,
            QImage.Format.Format_RGB888
        ).rgbSwapped()  # Swap RGB to BGR for Qt

        # Scale to fit widget size (273x153) while maintaining aspect ratio
        pixmap = QPixmap.fromImage(qimage)
        scaled_pixmap = pixmap.scaled(
            self.width(),
            self.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        # Center the scaled pixmap
        x = (self.width() - scaled_pixmap.width()) // 2
        y = (self.height() - scaled_pixmap.height()) // 2
        painter.drawPixmap(x, y, scaled_pixmap)

    def clear(self):
        """Clear the preview"""
        self.frame = None
        self.update()
