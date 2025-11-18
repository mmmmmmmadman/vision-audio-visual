"""
Anchor XY Pad - 2D draggable control widget
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, pyqtSignal, QPointF
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush


class AnchorXYPad(QWidget):
    """2D draggable pad for anchor position control"""

    # Signal emitted when position changes
    position_changed = pyqtSignal(float, float)  # x_pct, y_pct

    def __init__(self, parent=None):
        super().__init__(parent)
        self.x_pct = 50.0  # 0-100
        self.y_pct = 50.0  # 0-100
        self.dragging = False

        # Fixed size: 1.5x larger, 16:9 aspect ratio (matching main visual)
        # Original: 182x102, scaled 1.5x = 273x153
        self.setMinimumSize(273, 153)
        self.setMaximumSize(273, 153)
        self.setFixedSize(273, 153)

        # Enable mouse tracking
        self.setMouseTracking(True)

    def set_position(self, x_pct: float, y_pct: float):
        """Set anchor position (0-100%)"""
        self.x_pct = max(0.0, min(100.0, x_pct))
        self.y_pct = max(0.0, min(100.0, y_pct))
        self.update()

    def paintEvent(self, event):
        """Draw pad with grid and anchor point"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()
        margin = 5

        # Draw background
        painter.fillRect(margin, margin, width - margin * 2, height - margin * 2,
                        QColor(40, 40, 40))

        # Draw border
        painter.setPen(QPen(QColor(100, 100, 100), 1))
        painter.drawRect(margin, margin, width - margin * 2 - 1, height - margin * 2 - 1)

        # Draw grid (4x4)
        painter.setPen(QPen(QColor(60, 60, 60), 1, Qt.PenStyle.DashLine))
        for i in range(1, 4):
            # Vertical lines
            x = margin + (width - margin * 2) * i / 4
            painter.drawLine(int(x), margin, int(x), height - margin)
            # Horizontal lines
            y = margin + (height - margin * 2) * i / 4
            painter.drawLine(margin, int(y), width - margin, int(y))

        # Draw center cross
        painter.setPen(QPen(QColor(80, 80, 80), 1))
        center_x = width / 2
        center_y = height / 2
        painter.drawLine(int(center_x - 5), int(center_y), int(center_x + 5), int(center_y))
        painter.drawLine(int(center_x), int(center_y - 5), int(center_x), int(center_y + 5))

        # Calculate anchor pixel position
        anchor_x = margin + (width - margin * 2) * self.x_pct / 100.0
        anchor_y = margin + (height - margin * 2) * (100.0 - self.y_pct) / 100.0  # Invert Y

        # Draw anchor point (circle)
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.setBrush(QBrush(QColor(255, 133, 133, 200)))  # Pink with alpha
        painter.drawEllipse(QPointF(anchor_x, anchor_y), 6, 6)

        # Draw inner circle
        painter.setPen(QPen(QColor(255, 255, 255), 1))
        painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        painter.drawEllipse(QPointF(anchor_x, anchor_y), 3, 3)

    def mousePressEvent(self, event):
        """Handle mouse press"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self._update_position(event.pos())

    def mouseMoveEvent(self, event):
        """Handle mouse move (drag)"""
        if self.dragging:
            self._update_position(event.pos())

    def mouseReleaseEvent(self, event):
        """Handle mouse release"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False

    def _update_position(self, pos):
        """Update anchor position from mouse position"""
        width = self.width()
        height = self.height()
        margin = 5

        # Calculate percentage
        x_pct = (pos.x() - margin) / (width - margin * 2) * 100.0
        y_pct = (1.0 - (pos.y() - margin) / (height - margin * 2)) * 100.0  # Invert Y

        # Clamp to 0-100
        x_pct = max(0.0, min(100.0, x_pct))
        y_pct = max(0.0, min(100.0, y_pct))

        # Update internal state
        self.x_pct = x_pct
        self.y_pct = y_pct

        # Emit signal
        self.position_changed.emit(x_pct, y_pct)

        # Redraw
        self.update()
