"""
Media Cache module for loading and caching images/videos from a folder
"""

import cv2
import numpy as np
from typing import Optional, List, Dict, Tuple
import os
import threading
import random


class MediaItem:
    """Represents a single cached media item (image or video)"""

    def __init__(self, path: str):
        self.path = path
        self.filename = os.path.basename(path)
        self.is_video = self._is_video_file(path)

        # For images: store the numpy array directly
        self.image_data: Optional[np.ndarray] = None

        # For videos: store VideoCapture and maintain frame index
        self.video_cap: Optional[cv2.VideoCapture] = None
        self.video_frame_count: int = 0
        self.video_fps: float = 30.0
        self.current_frame_idx: int = 0
        self.current_frame: Optional[np.ndarray] = None

        # Video playback thread
        self.running = False
        self.read_thread = None
        self.frame_lock = threading.Lock()

    def _is_video_file(self, path: str) -> bool:
        """Check if file is a video based on extension"""
        video_exts = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v'}
        ext = os.path.splitext(path)[1].lower()
        return ext in video_exts

    def load(self) -> bool:
        """Load the media item into memory"""
        try:
            if self.is_video:
                return self._load_video()
            else:
                return self._load_image()
        except Exception as e:
            print(f"Error loading {self.path}: {e}")
            return False

    def _load_image(self) -> bool:
        """Load image into memory"""
        self.image_data = cv2.imread(self.path)
        if self.image_data is None:
            print(f"Failed to load image: {self.path}")
            return False
        print(f"Loaded image: {self.filename} ({self.image_data.shape[1]}x{self.image_data.shape[0]})")
        return True

    def _load_video(self) -> bool:
        """Load video and start playback thread"""
        self.video_cap = cv2.VideoCapture(self.path)
        if not self.video_cap.isOpened():
            print(f"Failed to open video: {self.path}")
            return False

        self.video_frame_count = int(self.video_cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.video_fps = self.video_cap.get(cv2.CAP_PROP_FPS)
        if self.video_fps <= 0:
            self.video_fps = 30.0

        width = int(self.video_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.video_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        print(f"Loaded video: {self.filename} ({width}x{height}, {self.video_frame_count} frames @ {self.video_fps:.1f}fps)")

        # Read first frame
        ret, frame = self.video_cap.read()
        if ret:
            with self.frame_lock:
                self.current_frame = frame
                self.current_frame_idx = 0

        # Start playback thread
        self.running = True
        self.read_thread = threading.Thread(target=self._video_read_loop, daemon=True)
        self.read_thread.start()

        return True

    def _video_read_loop(self):
        """Background thread for video playback"""
        import time
        frame_interval = 1.0 / self.video_fps
        last_frame_time = time.time()

        while self.running:
            if self.video_cap is None or not self.video_cap.isOpened():
                break

            # Wait for next frame time
            current_time = time.time()
            elapsed = current_time - last_frame_time
            if elapsed < frame_interval:
                time.sleep(frame_interval - elapsed)

            ret, frame = self.video_cap.read()
            last_frame_time = time.time()

            if ret:
                with self.frame_lock:
                    self.current_frame = frame
                    self.current_frame_idx += 1
            else:
                # End of video - loop back
                self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                self.current_frame_idx = 0
                time.sleep(0.01)

    def get_frame(self, target_size: Optional[Tuple[int, int]] = None) -> Optional[np.ndarray]:
        """
        Get current frame (resized to target_size if specified)

        Args:
            target_size: (width, height) to resize to, or None for original size

        Returns:
            Current frame as BGR numpy array
        """
        frame = None

        if self.is_video:
            with self.frame_lock:
                if self.current_frame is not None:
                    frame = self.current_frame.copy()
        else:
            if self.image_data is not None:
                frame = self.image_data.copy()

        if frame is None:
            return None

        if target_size is not None:
            frame = cv2.resize(frame, target_size)

        return frame

    def close(self):
        """Release resources"""
        self.running = False
        if self.read_thread is not None:
            self.read_thread.join(timeout=1.0)

        if self.video_cap is not None:
            self.video_cap.release()
            self.video_cap = None

        self.image_data = None
        self.current_frame = None

    def __del__(self):
        self.close()


class MediaCache:
    """
    Cache for loading and managing media files from a folder.
    Supports random selection of 4 items for region-based rendering.
    """

    SUPPORTED_IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
    SUPPORTED_VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v'}

    def __init__(self):
        self.folder_path: Optional[str] = None
        self.media_items: List[MediaItem] = []
        self.selected_items: List[MediaItem] = [None, None, None, None]  # 4 selected items for 4 regions
        self.loading = False
        self.loaded = False

    def load_folder(self, folder_path: str) -> bool:
        """
        Load all media files from a folder into cache.

        Args:
            folder_path: Path to folder containing media files

        Returns:
            True if at least one file was loaded successfully
        """
        if not os.path.isdir(folder_path):
            print(f"Invalid folder path: {folder_path}")
            return False

        # Close existing items
        self.close()

        self.folder_path = folder_path
        self.loading = True

        # Find all supported media files
        all_exts = self.SUPPORTED_IMAGE_EXTS | self.SUPPORTED_VIDEO_EXTS
        media_files = []

        for filename in os.listdir(folder_path):
            ext = os.path.splitext(filename)[1].lower()
            if ext in all_exts:
                full_path = os.path.join(folder_path, filename)
                if os.path.isfile(full_path):
                    media_files.append(full_path)

        if not media_files:
            print(f"No media files found in: {folder_path}")
            self.loading = False
            return False

        print(f"Found {len(media_files)} media files in {folder_path}")

        # Load each file
        for path in sorted(media_files):
            item = MediaItem(path)
            if item.load():
                self.media_items.append(item)

        self.loading = False
        self.loaded = len(self.media_items) > 0

        if self.loaded:
            print(f"Successfully loaded {len(self.media_items)} media items")
            # Auto-shuffle on first load
            self.shuffle()

        return self.loaded

    def shuffle(self):
        """Randomly select 4 items for the 4 regions"""
        if not self.media_items:
            print("No media items to shuffle")
            return

        # Randomly select 4 items (with replacement if less than 4 items)
        if len(self.media_items) >= 4:
            self.selected_items = random.sample(self.media_items, 4)
        else:
            # Less than 4 items: select with replacement
            self.selected_items = [random.choice(self.media_items) for _ in range(4)]

        print(f"Shuffled: Region 0={self.selected_items[0].filename}, "
              f"Region 1={self.selected_items[1].filename}, "
              f"Region 2={self.selected_items[2].filename}, "
              f"Region 3={self.selected_items[3].filename}")

    def get_region_frames(self, target_size: Optional[Tuple[int, int]] = None) -> List[Optional[np.ndarray]]:
        """
        Get current frames for all 4 regions.

        Args:
            target_size: (width, height) to resize each frame, or None for original

        Returns:
            List of 4 frames (BGR numpy arrays), None for empty slots
        """
        frames = []
        for item in self.selected_items:
            if item is not None:
                frames.append(item.get_frame(target_size))
            else:
                frames.append(None)
        return frames

    def get_region_frame(self, region_id: int, target_size: Optional[Tuple[int, int]] = None) -> Optional[np.ndarray]:
        """
        Get current frame for a specific region.

        Args:
            region_id: 0-3 for the 4 regions
            target_size: (width, height) to resize, or None for original

        Returns:
            Frame as BGR numpy array, or None if not available
        """
        if region_id < 0 or region_id >= 4:
            return None

        item = self.selected_items[region_id]
        if item is None:
            return None

        return item.get_frame(target_size)

    def get_item_count(self) -> int:
        """Get total number of loaded media items"""
        return len(self.media_items)

    def is_loaded(self) -> bool:
        """Check if media cache has loaded items"""
        return self.loaded and len(self.media_items) > 0

    def close(self):
        """Release all resources"""
        for item in self.media_items:
            item.close()
        self.media_items.clear()
        self.selected_items = [None, None, None, None]
        self.loaded = False
        self.folder_path = None

    def __del__(self):
        self.close()
