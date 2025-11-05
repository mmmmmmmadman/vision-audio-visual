"""
Oscilloscope widget for CV signals
"""

import numpy as np
from PyQt6.QtWidgets import QWidget
import pyqtgraph as pg


class ScopeWidget(QWidget):
    """Multi-channel oscilloscope for CV visualization"""

    def __init__(self, num_channels: int = 5, buffer_size: int = 1000):
        super().__init__()
        self.num_channels = num_channels
        self.buffer_size = buffer_size

        # Data buffers for each channel
        self.buffers = [np.zeros(buffer_size, dtype=np.float32) for _ in range(num_channels)]
        self.write_index = 0

        # Colors for channels (unified with main visual and GUI)
        from ..utils.cv_colors import SCOPE_COLORS
        self.colors = SCOPE_COLORS

        # Build UI
        self._build_ui()

    def _build_ui(self):
        """Build scope display with separate plots for each channel"""
        from PyQt6.QtWidgets import QVBoxLayout

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create GraphicsLayoutWidget for multiple plots
        self.graphics_widget = pg.GraphicsLayoutWidget()
        self.graphics_widget.setBackground('k')

        # Channel labels
        channel_names = [
            "ENV 1",
            "ENV 2",
            "ENV 3",
            "SEQ 1",
            "SEQ 2"
        ]

        # Create separate plot for each channel
        self.plot_items = []
        self.curves = []

        for i in range(self.num_channels):
            # Create plot item
            plot_item = self.graphics_widget.addPlot(row=i, col=0)
            plot_item.setYRange(0, 1.0)
            plot_item.setXRange(0, self.buffer_size)
            plot_item.showGrid(x=True, y=True, alpha=0.3)
            plot_item.setLabel('left', channel_names[i])

            # Only show X axis label on bottom plot
            if i == self.num_channels - 1:
                plot_item.setLabel('bottom', 'Samples')
            else:
                # Hide X axis labels for upper plots
                plot_item.getAxis('bottom').setStyle(showValues=False)

            # Create curve
            curve = plot_item.plot(
                pen=pg.mkPen(color=self.colors[i], width=3)
            )

            self.plot_items.append(plot_item)
            self.curves.append(curve)

        layout.addWidget(self.graphics_widget)

    def add_samples(self, samples: np.ndarray):
        """Add new samples (one sample per channel)"""
        if len(samples) != self.num_channels:
            return

        # Write samples to buffers
        for i, value in enumerate(samples):
            self.buffers[i][self.write_index] = value

        self.write_index = (self.write_index + 1) % self.buffer_size

        # Update display every N samples for performance
        if self.write_index % 10 == 0:
            self._update_display()

    def _update_display(self):
        """Update plot curves"""
        for i in range(self.num_channels):
            # Reorder buffer to show continuous waveform
            data = np.roll(self.buffers[i], -self.write_index)
            self.curves[i].setData(data)

    def clear(self):
        """Clear all buffers"""
        for buf in self.buffers:
            buf.fill(0.0)
        self.write_index = 0
        self._update_display()
