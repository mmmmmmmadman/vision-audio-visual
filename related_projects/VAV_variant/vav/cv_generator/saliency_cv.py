"""
Saliency CV Generator (未使用)

狀態: 實驗性功能，未整合到主程式
保留原因: 未來可能開發

Spectral Residual Saliency Point Detector
從畫面顯著性分析提取顯著點（用於 Sequencer）
"""

import cv2
import numpy as np
from typing import List, Tuple


class SaliencyCVGenerator:
    """
    使用 Spectral Residual Saliency 從畫面提取顯著點

    用途：
    - 提取 N 個最顯著的點（替代 Corner Detection）
    - 計算顯著性能量（用於 Envelope 觸發判斷）
    """

    def __init__(self):
        """初始化 Saliency 點偵測器"""
        # 創建 OpenCV Spectral Residual Saliency 檢測器
        self.saliency_detector = cv2.saliency.StaticSaliencySpectralResidual_create()

        # 顯著性能量歷史（用於觸發判斷）
        self.saliency_energy = 0.0

        # 參數
        self.binary_threshold = 30  # 二值化閾值（0-255）

    def extract_salient_points(self, gray: np.ndarray, num_points: int) -> List[Tuple[int, int]]:
        """
        從畫面提取 N 個最顯著的點

        Args:
            gray: 灰階畫面
            num_points: 要提取的點數量

        Returns:
            List[(x, y)]: 顯著點座標列表
        """
        height, width = gray.shape

        # 計算 saliency map
        success, saliency_map = self.saliency_detector.computeSaliency(gray)

        if not success:
            # 失敗時返回均勻網格
            return self._create_grid_points(width, height, num_points)

        # 轉換為 uint8
        if saliency_map.max() <= 1.0:
            saliency_map_uint8 = (saliency_map * 255).astype(np.uint8)
        else:
            saliency_map_uint8 = saliency_map.astype(np.uint8)

        # 更新能量
        self.saliency_energy = np.mean(saliency_map_uint8) / 255.0

        # 使用 goodFeaturesToTrack 在 saliency map 上找最亮的點
        # （這比簡單找最大值更好，因為會考慮區域分布）
        points = cv2.goodFeaturesToTrack(
            saliency_map_uint8,
            maxCorners=num_points * 2,  # 找多一些
            qualityLevel=0.01,  # 低閾值，接受更多點
            minDistance=max(min(width, height) // (num_points + 2), 5)  # 確保分散
        )

        if points is None or len(points) == 0:
            # 沒找到點，返回均勻網格
            return self._create_grid_points(width, height, num_points)

        # 轉換格式
        points = points.reshape(-1, 2)  # (N, 2)

        # 按 saliency 值排序（從最顯著開始）
        point_saliency = []
        for pt in points:
            x, y = int(pt[0]), int(pt[1])
            if 0 <= x < width and 0 <= y < height:
                sal_val = saliency_map_uint8[y, x]
                point_saliency.append((x, y, sal_val))

        # 按顯著性排序（降序）
        point_saliency.sort(key=lambda p: p[2], reverse=True)

        # 取前 num_points 個
        result = [(p[0], p[1]) for p in point_saliency[:num_points]]

        # 如果點數不足，用網格補齊
        if len(result) < num_points:
            grid_points = self._create_grid_points(width, height, num_points)
            result.extend(grid_points[len(result):])

        return result[:num_points]

    def get_saliency_energy(self) -> float:
        """
        取得當前顯著性能量

        Returns:
            float: 能量值 (0.0-1.0)
        """
        return self.saliency_energy

    def _create_grid_points(self, width: int, height: int, num_points: int) -> List[Tuple[int, int]]:
        """
        創建均勻網格點（fallback）

        Args:
            width: 畫面寬度
            height: 畫面高度
            num_points: 點數量

        Returns:
            List[(x, y)]: 網格點座標
        """
        grid_points = []
        grid_size = int(np.sqrt(num_points))

        for i in range(num_points):
            row = i // grid_size
            col = i % grid_size
            x = int((col + 0.5) / grid_size * width)
            y = int((row + 0.5) / grid_size * height)
            grid_points.append((x, y))

        return grid_points

    def set_binary_threshold(self, threshold: int):
        """設定二值化閾值 (0-255)"""
        self.binary_threshold = np.clip(threshold, 1, 255)
