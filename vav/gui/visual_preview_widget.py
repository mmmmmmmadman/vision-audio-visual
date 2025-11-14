"""
Visual preview widget - displays main visual output in small preview with anchor overlay
"""

import numpy as np
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QImage, QPixmap, QPen, QColor, QBrush


class VisualPreviewWidget(QWidget):
    """Preview widget showing main visual output with anchor overlay"""

    # Signal emitted when anchor position changes
    position_changed = pyqtSignal(float, float)  # x_pct, y_pct

    def __init__(self):
        super().__init__()
        self.setFixedSize(546, 230)  # Reduced height for better layout balance
        self.setStyleSheet("background-color: #000000; border: 1px solid #404040;")

        # Current frame (RGB numpy array or None)
        self.frame = None

        # Anchor position and range
        self.x_pct = 50.0  # 0-100
        self.y_pct = 50.0  # 0-100
        self.range_pct = 50.0  # 1-120
        self.dragging = False

        # Enable mouse tracking and context menu
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def update_frame(self, frame: np.ndarray):
        """
        Update preview with new frame

        Args:
            frame: RGB image as numpy array (H, W, 3) uint8
        """
        self.frame = frame
        self.update()

    def set_position(self, x_pct: float, y_pct: float, emit_signal: bool = False):
        """Set anchor position (0-100%)"""
        self.x_pct = max(0.0, min(100.0, x_pct))
        self.y_pct = max(0.0, min(100.0, y_pct))
        if emit_signal:
            self.position_changed.emit(self.x_pct, self.y_pct)
        self.update()

    def set_range(self, range_pct: float):
        """Set ROI range (1-120%)"""
        self.range_pct = max(1.0, min(120.0, range_pct))
        self.update()

    def mousePressEvent(self, event):
        """Handle mouse press to start dragging"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self._update_position_from_mouse(event.pos())

    def mouseMoveEvent(self, event):
        """Handle mouse drag to update position"""
        if self.dragging:
            self._update_position_from_mouse(event.pos())

    def mouseReleaseEvent(self, event):
        """Handle mouse release to stop dragging"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False

    def _update_position_from_mouse(self, pos):
        """Convert mouse position to percentage and emit signal"""
        x_pct = (pos.x() / self.width()) * 100.0
        y_pct = (pos.y() / self.height()) * 100.0
        self.set_position(x_pct, y_pct, emit_signal=True)

    def paintEvent(self, event):
        """Paint the preview frame with anchor overlay"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw frame if available
        if self.frame is not None:
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

            # Scale to fit widget size while maintaining aspect ratio
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
        else:
            # No frame yet, draw black background
            painter.fillRect(self.rect(), Qt.GlobalColor.black)

        # Draw anchor overlay
        width = self.width()
        height = self.height()

        # Calculate anchor position in pixels
        anchor_x = (self.x_pct / 100.0) * width
        anchor_y = (self.y_pct / 100.0) * height

        # Calculate ROI circle radius
        range_radius = (self.range_pct / 100.0) * min(width, height) / 2

        # Draw ROI circle
        painter.setPen(QPen(QColor(255, 107, 157, 180), 2))  # Pink semi-transparent
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(int(anchor_x - range_radius), int(anchor_y - range_radius),
                           int(range_radius * 2), int(range_radius * 2))

        # Draw anchor crosshair
        painter.setPen(QPen(QColor(255, 107, 157), 2))  # Bright pink
        cross_size = 10
        painter.drawLine(int(anchor_x - cross_size), int(anchor_y),
                        int(anchor_x + cross_size), int(anchor_y))
        painter.drawLine(int(anchor_x), int(anchor_y - cross_size),
                        int(anchor_x), int(anchor_y + cross_size))

        # Draw center dot
        painter.setBrush(QBrush(QColor(255, 107, 157)))
        painter.drawEllipse(int(anchor_x - 3), int(anchor_y - 3), 6, 6)

    def clear(self):
        """Clear the preview"""
        self.frame = None
        self.update()
