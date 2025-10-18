"""
Device selection dialogs
"""

import sounddevice as sd
import cv2
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QGroupBox, QFormLayout,
)
from PyQt6.QtCore import Qt


class DeviceSelectionDialog(QDialog):
    """Dialog for selecting audio and video devices"""

    def __init__(self, parent=None, current_devices=None):
        super().__init__(parent)
        self.setWindowTitle("Device Selection")
        self.setModal(True)
        self.setMinimumWidth(500)

        # Current device configuration (to pre-select in dialog)
        self.current_devices = current_devices or {}

        # Selected devices
        self.selected_audio_input = None
        self.selected_audio_output = None
        self.selected_camera_input = None
        self.selected_camera_output = None

        self._build_ui()
        self._populate_devices()

    def _build_ui(self):
        """Build dialog UI"""
        layout = QVBoxLayout(self)

        # Audio devices
        audio_group = QGroupBox("Audio Devices")
        audio_layout = QFormLayout(audio_group)

        self.audio_input_combo = QComboBox()
        audio_layout.addRow("Input:", self.audio_input_combo)

        self.audio_output_combo = QComboBox()
        audio_layout.addRow("Output:", self.audio_output_combo)

        layout.addWidget(audio_group)

        # Video devices
        video_group = QGroupBox("Video Devices")
        video_layout = QFormLayout(video_group)

        self.camera_input_combo = QComboBox()
        video_layout.addRow("Camera Input:", self.camera_input_combo)

        self.camera_output_combo = QComboBox()
        video_layout.addRow("Camera Output (Virtual):", self.camera_output_combo)

        layout.addWidget(video_group)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

    def _populate_devices(self):
        """Populate device lists"""
        # Audio devices
        try:
            devices = sd.query_devices()

            # Input devices
            for i, dev in enumerate(devices):
                if dev['max_input_channels'] > 0:
                    name = f"{i}: {dev['name']} ({dev['max_input_channels']} in)"
                    self.audio_input_combo.addItem(name, i)

            # Output devices
            for i, dev in enumerate(devices):
                if dev['max_output_channels'] > 0:
                    name = f"{i}: {dev['name']} ({dev['max_output_channels']} out)"
                    self.audio_output_combo.addItem(name, i)

            # Set current or default devices
            # Priority: current_devices > system defaults
            current_input = self.current_devices.get('audio_input')
            current_output = self.current_devices.get('audio_output')

            if current_input is not None:
                # Use currently configured input device
                idx = self.audio_input_combo.findData(current_input)
                if idx >= 0:
                    self.audio_input_combo.setCurrentIndex(idx)
                    print(f"[DeviceDialog] Pre-selected input device: {current_input}")
            else:
                # Fall back to system default
                default_input = sd.query_devices(kind='input')
                if default_input:
                    idx = self.audio_input_combo.findData(default_input['index'])
                    if idx >= 0:
                        self.audio_input_combo.setCurrentIndex(idx)

            if current_output is not None:
                # Use currently configured output device
                idx = self.audio_output_combo.findData(current_output)
                if idx >= 0:
                    self.audio_output_combo.setCurrentIndex(idx)
                    print(f"[DeviceDialog] Pre-selected output device: {current_output}")
            else:
                # Fall back to system default
                default_output = sd.query_devices(kind='output')
                if default_output:
                    idx = self.audio_output_combo.findData(default_output['index'])
                    if idx >= 0:
                        self.audio_output_combo.setCurrentIndex(idx)

        except Exception as e:
            print(f"Error listing audio devices: {e}")

        # Camera input devices
        try:
            # Get camera names from macOS system
            import platform
            import subprocess

            camera_names = {}
            if platform.system() == 'Darwin':  # macOS
                try:
                    result = subprocess.run(
                        ['system_profiler', 'SPCameraDataType'],
                        capture_output=True, text=True, timeout=3
                    )
                    # Parse camera names
                    current_camera = None
                    for line in result.stdout.split('\n'):
                        line = line.strip()
                        if line.endswith(':') and not line.startswith('Camera'):
                            current_camera = line.rstrip(':')
                        elif 'Unique ID' in line and current_camera:
                            # Map to camera index (rough approximation)
                            idx = len(camera_names)
                            camera_names[idx] = current_camera
                except:
                    pass

            # Scan only first 3 cameras to avoid errors
            test_indices = range(3)
            found_cameras = []

            print("Scanning for cameras...")
            for i in test_indices:
                try:
                    cap = cv2.VideoCapture(i)
                    if cap.isOpened():
                        # Read a test frame to verify it's actually working
                        ret, frame = cap.read()
                        if ret and frame is not None:
                            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

                            # Use camera name from system_profiler if available
                            if i in camera_names:
                                name = f"{camera_names[i]} (ID {i}): {width}x{height}"
                            else:
                                name = f"Camera {i}: {width}x{height}"

                            found_cameras.append((i, name))
                            print(f"  Found: {name}")
                        cap.release()
                except Exception as e:
                    # Skip cameras that fail to open
                    continue

            # Populate camera input combo
            if found_cameras:
                for idx, name in found_cameras:
                    self.camera_input_combo.addItem(name, idx)

                # Pre-select current camera if specified
                current_camera = self.current_devices.get('camera_input')
                if current_camera is not None:
                    idx = self.camera_input_combo.findData(current_camera)
                    if idx >= 0:
                        self.camera_input_combo.setCurrentIndex(idx)
                        print(f"[DeviceDialog] Pre-selected camera: {current_camera}")
                    else:
                        self.camera_input_combo.setCurrentIndex(0)
                else:
                    self.camera_input_combo.setCurrentIndex(0)
            else:
                self.camera_input_combo.addItem("No cameras found", None)
                self.camera_input_combo.setEnabled(False)

            # Camera output is for display only (not used)
            self.camera_output_combo.addItem("(Virtual cam output - see Virtual Cam button)", None)
            self.camera_output_combo.setEnabled(False)

        except Exception as e:
            print(f"Error listing cameras: {e}")
            import traceback
            traceback.print_exc()
            self.camera_input_combo.addItem("Error listing cameras", None)
            self.camera_input_combo.setEnabled(False)
            self.camera_output_combo.addItem("Error", None)
            self.camera_output_combo.setEnabled(False)

    def get_selected_devices(self):
        """Get selected device indices"""
        devices = {
            'audio_input': self.audio_input_combo.currentData(),
            'audio_output': self.audio_output_combo.currentData(),
            'camera_input': self.camera_input_combo.currentData(),
            'camera_output': self.camera_output_combo.currentData(),
        }
        print(f"[DeviceDialog] Selected devices: {devices}")
        return devices

    @staticmethod
    def select_devices(parent=None, current_devices=None):
        """Show device selection dialog and return selected devices"""
        dialog = DeviceSelectionDialog(parent, current_devices=current_devices)
        result = dialog.exec()

        if result == QDialog.DialogCode.Accepted:
            return dialog.get_selected_devices()
        return None
