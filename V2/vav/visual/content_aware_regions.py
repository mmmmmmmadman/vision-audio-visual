"""
Content-Aware Region Mapper
根據畫面內容動態分配區域
"""

import cv2
import numpy as np
from typing import Tuple, List


class ContentAwareRegionMapper:
    """基於畫面內容的動態區域分配"""

    def __init__(self, width: int = 1920, height: int = 1080):
        self.width = width
        self.height = height
        self.region_map = None

    def create_color_based_regions(self, frame: np.ndarray) -> np.ndarray:
        """
        基於顏色分區

        Args:
            frame: 輸入畫面 (BGR)

        Returns:
            region_map: (height, width) 陣列，值為通道編號 (0-3)
        """
        # 轉換為 HSV
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        self.region_map = np.zeros((self.height, self.width), dtype=np.int32)

        # 定義顏色範圍（HSV）
        color_ranges = [
            # CH1: 紅色 (0-30, 150-180)
            ([0, 100, 100], [30, 255, 255]),
            # CH2: 綠色 (40-80)
            ([40, 100, 100], [80, 255, 255]),
            # CH3: 藍色 (90-130)
            ([90, 100, 100], [130, 255, 255]),
            # CH4: 黃色 (20-40)
            ([20, 100, 100], [40, 255, 255]),
        ]

        # 為每個顏色創建遮罩
        for channel, (lower, upper) in enumerate(color_ranges):
            lower = np.array(lower)
            upper = np.array(upper)
            mask = cv2.inRange(hsv, lower, upper)
            self.region_map[mask > 0] = channel

        # 處理紅色的特殊情況（跨越 0/180）
        lower_red2 = np.array([150, 100, 100])
        upper_red2 = np.array([180, 255, 255])
        mask_red2 = cv2.inRange(hsv, lower_red2, upper_red2)
        self.region_map[mask_red2 > 0] = 0  # CH1

        return self.region_map

    def create_brightness_based_regions(self, frame: np.ndarray) -> np.ndarray:
        """
        基於亮度分區（4 個亮度級別）

        Args:
            frame: 輸入畫面 (BGR)

        Returns:
            region_map: (height, width) 陣列
        """
        # 轉換為灰階
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        self.region_map = np.zeros((self.height, self.width), dtype=np.int32)

        # 根據亮度分成 4 個級別
        self.region_map[gray < 64] = 0    # CH1: 很暗
        self.region_map[(gray >= 64) & (gray < 128)] = 1   # CH2: 中暗
        self.region_map[(gray >= 128) & (gray < 192)] = 2  # CH3: 中亮
        self.region_map[gray >= 192] = 3  # CH4: 很亮

        return self.region_map

    def create_quadrant_regions(self, frame: np.ndarray) -> np.ndarray:
        """
        基於畫面四象限（簡單但實用）

        Returns:
            region_map: (height, width) 陣列
        """
        self.region_map = np.zeros((self.height, self.width), dtype=np.int32)

        mid_h = self.height // 2
        mid_w = self.width // 2

        self.region_map[0:mid_h, 0:mid_w] = 0           # CH1: 左上
        self.region_map[0:mid_h, mid_w:] = 1            # CH2: 右上
        self.region_map[mid_h:, 0:mid_w] = 2            # CH3: 左下
        self.region_map[mid_h:, mid_w:] = 3             # CH4: 右下

        return self.region_map

    def create_edge_based_regions(self, frame: np.ndarray, blur_size: int = 21) -> np.ndarray:
        """
        基於邊緣檢測分區

        Args:
            frame: 輸入畫面 (BGR)
            blur_size: 模糊核大小（越大區域越平滑）

        Returns:
            region_map: (height, width) 陣列
        """
        # 轉換為灰階
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 邊緣檢測
        edges = cv2.Canny(gray, 50, 150)

        # 膨脹邊緣
        kernel = np.ones((5, 5), np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=2)

        # 使用距離變換
        dist_transform = cv2.distanceTransform(255 - edges, cv2.DIST_L2, 5)

        # 找到局部最大值作為標記
        ret, sure_fg = cv2.threshold(dist_transform, 0.3 * dist_transform.max(), 255, 0)
        sure_fg = np.uint8(sure_fg)

        # 找輪廓
        contours, _ = cv2.findContours(sure_fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # 創建標記
        markers = np.zeros_like(gray, dtype=np.int32)
        for i, contour in enumerate(contours[:4]):  # 最多 4 個區域
            cv2.drawContours(markers, [contour], -1, i + 1, -1)

        # Watershed 分割
        if len(contours) > 0:
            markers = cv2.watershed(frame, markers)

            # 轉換為通道映射
            self.region_map = np.zeros((self.height, self.width), dtype=np.int32)
            for channel in range(4):
                self.region_map[markers == (channel + 1)] = channel
        else:
            # 如果沒有檢測到區域，使用四象限
            self.region_map = self.create_quadrant_regions(frame)

        return self.region_map

    def create_cable_based_regions(self, cables: List, frame_shape: Tuple[int, int]) -> np.ndarray:
        """
        基於檢測到的電纜分區

        Args:
            cables: 電纜列表（來自 CableDetector）
            frame_shape: (height, width)

        Returns:
            region_map: (height, width) 陣列
        """
        height, width = frame_shape
        self.region_map = np.zeros((height, width), dtype=np.int32)

        if len(cables) == 0:
            # 沒有電纜，使用四象限
            return self.create_quadrant_regions(np.zeros((height, width, 3), dtype=np.uint8))

        # 根據電纜位置分割畫面
        # 簡單策略：根據電纜的 X 位置分割垂直區域
        cable_x_positions = sorted([cable.position for cable in cables])

        # 添加邊界
        boundaries = [0.0] + cable_x_positions + [1.0]

        # 分配通道（循環使用 4 個通道）
        for i in range(len(boundaries) - 1):
            x_start = int(boundaries[i] * width)
            x_end = int(boundaries[i + 1] * width)
            channel = i % 4
            self.region_map[:, x_start:x_end] = channel

        return self.region_map

    def get_region_map(self) -> np.ndarray:
        """取得當前 region_map"""
        return self.region_map

    def visualize_regions(self, overlay_frame: np.ndarray = None, alpha: float = 0.5) -> np.ndarray:
        """
        視覺化區域分配，可選疊加原始畫面

        Args:
            overlay_frame: 原始畫面 (BGR)，如果提供則疊加
            alpha: 疊加透明度 (0-1)

        Returns:
            RGB 圖像 (height, width, 3), uint8
        """
        if self.region_map is None:
            return np.zeros((self.height, self.width, 3), dtype=np.uint8)

        # 每個通道用不同顏色
        colors = [
            [255, 0, 0],    # CH1: 紅
            [0, 255, 0],    # CH2: 綠
            [0, 0, 255],    # CH3: 藍
            [255, 255, 0],  # CH4: 黃
        ]

        vis = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        for channel in range(4):
            mask = self.region_map == channel
            vis[mask] = colors[channel]

        # 疊加原始畫面
        if overlay_frame is not None:
            overlay_frame = cv2.resize(overlay_frame, (self.width, self.height))
            vis = cv2.addWeighted(overlay_frame, alpha, vis, 1 - alpha, 0)

        return vis
