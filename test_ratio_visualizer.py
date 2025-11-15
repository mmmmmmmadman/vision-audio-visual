"""
Ratio Visualizer Test Tool
獨立測試系統用於測試 ratio 功能和波形映射
"""

import sys
import numpy as np
import sounddevice as sd
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QSlider, QComboBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QImage
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure


class WaveformCanvas(FigureCanvasQTAgg):
    """波形顯示畫布"""

    def __init__(self, parent=None, width=8, height=3, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        super(WaveformCanvas, self).__init__(fig)

        self.waveform_data = np.zeros(1000)
        self.time_data = np.linspace(0, 1, 1000)

        self.axes.set_ylim(-1.2, 1.2)
        self.axes.set_xlim(0, 1)
        self.axes.grid(True, alpha=0.3)
        self.axes.set_xlabel('Time')
        self.axes.set_ylabel('Amplitude')

        self.line, = self.axes.plot(self.time_data, self.waveform_data, 'b-', linewidth=1.5)

    def update_waveform(self, waveform_data):
        """更新波形顯示"""
        self.waveform_data = waveform_data
        self.line.set_ydata(waveform_data)
        self.draw()


class StripeCanvas(QWidget):
    """色塊條紋顯示畫布"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(100)
        self.waveform_data = np.zeros(1000)
        self.ratio = 1.0
        self.compress = 2.0

    def update_stripe(self, waveform_data, ratio, compress):
        """更新條紋顯示"""
        self.waveform_data = waveform_data
        self.ratio = ratio
        self.compress = compress
        self.update()

    def paintEvent(self, event):
        """繪製條紋"""
        painter = QPainter(self)
        width = self.width()
        height = self.height()

        # 建立圖像緩衝
        image = QImage(width, height, QImage.Format.Format_RGB32)

        for x in range(width):
            # 計算採樣位置（使用 ratio 控制條紋密度）
            # 頻率壓縮：compress 參數控制壓縮比例
            # pitch_rate / compress = 讓條紋密度變成原本的 1/compress
            compressed_ratio = self.ratio / self.compress
            x_sample = (x / width) * compressed_ratio

            # 取樣波形（使用小數部分循環採樣）
            sample_idx = int((x_sample % 1.0) * len(self.waveform_data))
            sample_idx = np.clip(sample_idx, 0, len(self.waveform_data) - 1)

            # 波形值 [-1, 1] 映射到顏色
            value = self.waveform_data[sample_idx]

            # 映射到灰階 (可以改成彩色映射)
            gray = int((value + 1.0) * 127.5)  # -1~1 -> 0~255
            gray = np.clip(gray, 0, 255)

            color = QColor(gray, gray, gray)

            # 繪製垂直線
            for y in range(height):
                image.setPixelColor(x, y, color)

        painter.drawImage(0, 0, image)


class RatioVisualizerWindow(QMainWindow):
    """Ratio 視覺化測試視窗"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ratio Visualizer Test - ES-8 Input-1")
        self.setGeometry(100, 100, 1000, 700)

        # 音訊緩衝
        self.audio_buffer = np.zeros(1000)
        self.sample_rate = 48000
        self.buffer_size = 1024

        # 主要 widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # === 控制區 ===
        control_layout = QHBoxLayout()

        # Ratio 滑桿
        control_layout.addWidget(QLabel("Ratio:"))
        self.ratio_slider = QSlider(Qt.Orientation.Horizontal)
        self.ratio_slider.setMinimum(0)
        self.ratio_slider.setMaximum(100)  # 0.0001 ~ 10.0
        self.ratio_slider.setValue(10)  # 預設 1.0
        self.ratio_slider.valueChanged.connect(self.update_stripe_only)
        control_layout.addWidget(self.ratio_slider)
        self.ratio_label = QLabel("1.00")
        control_layout.addWidget(self.ratio_label)

        # Compression 滑桿
        control_layout.addWidget(QLabel("Compress:"))
        self.compress_slider = QSlider(Qt.Orientation.Horizontal)
        self.compress_slider.setMinimum(1)
        self.compress_slider.setMaximum(100)  # 0.1 ~ 10.0
        self.compress_slider.setValue(20)  # 預設 2.0
        self.compress_slider.valueChanged.connect(self.update_stripe_only)
        control_layout.addWidget(self.compress_slider)
        self.compress_label = QLabel("2.0")
        control_layout.addWidget(self.compress_label)

        layout.addLayout(control_layout)

        # === 波形顯示 ===
        layout.addWidget(QLabel("ES-8 Input-1 波形:"))
        self.waveform_canvas = WaveformCanvas(self, width=10, height=3, dpi=100)
        layout.addWidget(self.waveform_canvas)

        # === 條紋顯示 ===
        layout.addWidget(QLabel("條紋映射:"))
        self.stripe_canvas = StripeCanvas(self)
        layout.addWidget(self.stripe_canvas)

        # 啟動音訊輸入
        self.start_audio_input()

        # 定時更新顯示 (30 FPS)
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_visualization)
        self.update_timer.start(33)

    def audio_callback(self, indata, frames, time_info, status):
        """音訊輸入回調"""
        if status:
            print(f"Audio status: {status}")

        # 只取第一個聲道 (ES-8 Input-1)
        audio_data = indata[:, 0].copy()

        # 更新緩衝區
        self.audio_buffer = audio_data

    def start_audio_input(self):
        """啟動音訊輸入串流"""
        try:
            # 開啟音訊輸入 (使用預設裝置)
            self.audio_stream = sd.InputStream(
                samplerate=self.sample_rate,
                blocksize=self.buffer_size,
                channels=1,  # 只需要單聲道
                callback=self.audio_callback
            )
            self.audio_stream.start()
            print("✓ Audio input started")
        except Exception as e:
            print(f"⚠ Failed to start audio input: {e}")
            # 如果失敗，使用靜音緩衝
            self.audio_buffer = np.zeros(1000)

    def update_visualization(self):
        """更新所有視覺化"""
        # Logarithmic mapping: 0-100 → 0.0001-10.0
        slider_val = self.ratio_slider.value() / 100.0
        log_min = -4  # log10(0.0001)
        log_max = 1   # log10(10.0)
        log_value = log_min + slider_val * (log_max - log_min)
        ratio_value = 10 ** log_value

        if ratio_value < 0.01:
            self.ratio_label.setText(f"{ratio_value:.4f}")
        else:
            self.ratio_label.setText(f"{ratio_value:.2f}")

        # Compress 參數：0.1 ~ 10.0
        compress_value = self.compress_slider.value() / 10.0
        self.compress_label.setText(f"{compress_value:.1f}")

        # 取得音訊數據（重採樣到 1000 點）
        if len(self.audio_buffer) > 0:
            indices = np.linspace(0, len(self.audio_buffer) - 1, 1000).astype(int)
            waveform = self.audio_buffer[indices]
        else:
            waveform = np.zeros(1000)

        # 更新顯示
        self.waveform_canvas.update_waveform(waveform)
        self.stripe_canvas.update_stripe(waveform, ratio_value, compress_value)

    def update_stripe_only(self):
        """只更新條紋 (ratio/compress 改變時)"""
        # Logarithmic mapping: 0-100 → 0.0001-10.0
        slider_val = self.ratio_slider.value() / 100.0
        log_min = -4
        log_max = 1
        log_value = log_min + slider_val * (log_max - log_min)
        ratio_value = 10 ** log_value

        if ratio_value < 0.01:
            self.ratio_label.setText(f"{ratio_value:.4f}")
        else:
            self.ratio_label.setText(f"{ratio_value:.2f}")

        # Compress 參數
        compress_value = self.compress_slider.value() / 10.0
        self.compress_label.setText(f"{compress_value:.1f}")

        # 重採樣音訊數據
        if len(self.audio_buffer) > 0:
            indices = np.linspace(0, len(self.audio_buffer) - 1, 1000).astype(int)
            waveform = self.audio_buffer[indices]
        else:
            waveform = np.zeros(1000)

        self.stripe_canvas.update_stripe(waveform, ratio_value, compress_value)

    def closeEvent(self, event):
        """視窗關閉時清理資源"""
        if hasattr(self, 'audio_stream'):
            self.audio_stream.stop()
            self.audio_stream.close()
        if hasattr(self, 'update_timer'):
            self.update_timer.stop()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = RatioVisualizerWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
