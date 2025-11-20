"""
Webcam capture module
"""

import cv2
import numpy as np
from typing import Optional, Tuple, List, Dict
import subprocess
import json
import threading


class AsyncCamera:
    """Asynchronous webcam capture handler with background thread"""

    def __init__(self, device_id: int = 0, width: int = 1920, height: int = 1080, fps: int = 30):
        self.device_id = device_id
        self.width = width
        self.height = height
        self.fps = fps
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_opened = False

        # Async reading
        self.frame = None
        self.frame_lock = threading.Lock()
        self.running = False
        self.read_thread = None

    def open(self) -> bool:
        """Open camera device and start background reading thread"""
        self.cap = cv2.VideoCapture(self.device_id)
        if not self.cap.isOpened():
            return False

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)

        self.is_opened = True

        # Start background thread
        self.running = True
        self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.read_thread.start()

        return True

    def _read_loop(self):
        """Background thread continuously reads frames"""
        while self.running:
            if self.cap is not None and self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret:
                    with self.frame_lock:
                        self.frame = frame

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Read latest frame (non-blocking)"""
        if not self.is_opened:
            return False, None

        with self.frame_lock:
            if self.frame is not None:
                return True, self.frame.copy()
            return False, None

    def close(self):
        """Close camera device and stop background thread"""
        self.running = False
        if self.read_thread is not None:
            self.read_thread.join(timeout=1.0)

        if self.cap is not None:
            self.cap.release()
            self.is_opened = False

    def get_resolution(self) -> Tuple[int, int]:
        """Get actual camera resolution"""
        if self.cap is None:
            return (0, 0)
        w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return (w, h)

    def __del__(self):
        self.close()


class VideoFileSource:
    """Video file playback handler compatible with AsyncCamera interface"""

    def __init__(self, video_path: str, loop: bool = True):
        self.video_path = video_path
        self.loop = loop
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_opened = False

        # Compatibility with AsyncCamera interface
        self.device_id = -1  # -1 indicates video file source

        # Get video properties
        self.width = 1920
        self.height = 1080
        self.fps = 30

        # Async reading
        self.frame = None
        self.frame_lock = threading.Lock()
        self.running = False
        self.read_thread = None

    def open(self) -> bool:
        """Open video file and start background reading thread"""
        self.cap = cv2.VideoCapture(self.video_path)
        if not self.cap.isOpened():
            print(f"Failed to open video file: {self.video_path}")
            return False

        # Get actual video properties
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = int(self.cap.get(cv2.CAP_PROP_FPS))
        if self.fps == 0:
            self.fps = 30

        print(f"Video opened: {self.width}x{self.height} @ {self.fps}fps")

        self.is_opened = True

        # Start background thread
        self.running = True
        self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.read_thread.start()

        return True

    def _read_loop(self):
        """Background thread continuously reads frames"""
        while self.running:
            if self.cap is not None and self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret:
                    with self.frame_lock:
                        self.frame = frame
                else:
                    # End of video
                    if self.loop:
                        # Reset to beginning
                        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        # Small delay to avoid tight loop
                        import time
                        time.sleep(0.01)
                    else:
                        # Stop playback
                        self.running = False
            else:
                # Camera not ready, wait a bit
                import time
                time.sleep(0.05)

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Read latest frame (non-blocking)"""
        if not self.is_opened:
            return False, None

        with self.frame_lock:
            if self.frame is not None:
                return True, self.frame.copy()
            return False, None

    def close(self):
        """Close video file and stop background thread"""
        self.running = False
        if self.read_thread is not None:
            self.read_thread.join(timeout=1.0)

        if self.cap is not None:
            self.cap.release()
            self.is_opened = False

    def get_resolution(self) -> Tuple[int, int]:
        """Get video resolution"""
        return (self.width, self.height)

    def __del__(self):
        self.close()


class Camera:
    """Webcam capture handler (legacy synchronous version)"""

    def __init__(self, device_id: int = 0, width: int = 1920, height: int = 1080, fps: int = 30):
        self.device_id = device_id
        self.width = width
        self.height = height
        self.fps = fps
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_opened = False

    def open(self) -> bool:
        """Open camera device"""
        self.cap = cv2.VideoCapture(self.device_id)
        if not self.cap.isOpened():
            return False

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)

        self.is_opened = True
        return True

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Read frame from camera"""
        if not self.is_opened or self.cap is None:
            return False, None

        ret, frame = self.cap.read()
        return ret, frame

    def close(self):
        """Close camera device"""
        if self.cap is not None:
            self.cap.release()
            self.is_opened = False

    def get_resolution(self) -> Tuple[int, int]:
        """Get actual camera resolution"""
        if self.cap is None:
            return (0, 0)
        w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return (w, h)

    def __del__(self):
        self.close()


def get_camera_list() -> List[Dict]:
    """
    Get list of available cameras with their names
    Returns list of dicts with 'index' and 'name' keys
    """
    cameras = []

    # Try to get camera names using system_profiler on macOS
    try:
        import platform
        if platform.system() == 'Darwin':
            # Use system_profiler to get camera info on macOS
            result = subprocess.run(
                ['system_profiler', 'SPCameraDataType', '-json'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                if 'SPCameraDataType' in data and len(data['SPCameraDataType']) > 0:
                    for idx, cam_info in enumerate(data['SPCameraDataType']):
                        name = cam_info.get('_name', f'Camera {idx}')
                        cameras.append({'index': idx, 'name': name})
    except Exception as e:
        print(f"Failed to get camera names: {e}")

    # Fallback: probe cameras using OpenCV
    if not cameras:
        for i in range(10):  # Check first 10 indices
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                cameras.append({'index': i, 'name': f'Camera {i}'})
                cap.release()
            else:
                break

    return cameras


def get_camera_name(device_id: int) -> str:
    """Get camera name for a given device ID"""
    cameras = get_camera_list()
    for cam in cameras:
        if cam['index'] == device_id:
            return cam['name']
    return f'Camera {device_id}'
