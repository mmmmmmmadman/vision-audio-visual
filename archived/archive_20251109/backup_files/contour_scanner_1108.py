"""
Contour-based CV generator with continuous scanning
沿著輪廓線連續掃描，直接輸出座標變化作為 CV
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional
from ..utils.cv_colors import CV_COLORS_BGR


class ContourScanner:
    """
    輪廓掃描 CV 生成器

    不使用 Sample & Hold，改用連續掃描輪廓線
    SEQ1/SEQ2: 掃描點的 X/Y 座標（連續變化）
    ENV1-3: 輪廓特徵（強度、曲率等）
    """

    def __init__(self):
        """初始化輪廓掃描器"""
        # Canny edge detection 參數
        self.threshold = 100
        self.temporal_alpha = 50
        self.previous_edges = None

        # 錨點與範圍
        self.anchor_x_pct = 50
        self.anchor_y_pct = 50
        self.range_pct = 50

        # 掃描參數
        self.scan_time = 2.0  # 掃過完整輪廓的時間（秒）
        self.scan_progress = 0.0  # 當前掃描進度 (0-1)

        # 輪廓數據
        self.contour_points = []  # 當前追蹤的輪廓點列表 [(x, y), ...]
        self.current_scan_index = 0  # 當前掃描點索引

        # CV 輸出值（連續）
        self.seq1_value = 0.0  # X 座標 (0-1)
        self.seq2_value = 0.0  # Y 座標 (0-1)
        self.env1_value = 0.0  # 輪廓強度
        self.env2_value = 0.0  # 輪廓曲率
        self.env3_value = 0.0  # 輪廓距離

        # 視覺化
        self.current_scan_pos = None  # 當前掃描位置 (x, y)
        self.trigger_rings = []

        # Sobel 梯度（用於邊緣強度計算）
        self.sobel_gradient = None

    def detect_and_extract_contour(self, gray: np.ndarray):
        """偵測邊緣並提取最主要的輪廓線

        Args:
            gray: 灰階畫面
        """
        height, width = gray.shape

        # 高斯模糊
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Canny 邊緣檢測
        low_threshold = int(self.threshold * 0.5)
        high_threshold = self.threshold
        edges = cv2.Canny(blurred, low_threshold, high_threshold)

        # 時間平滑
        if self.previous_edges is not None and self.temporal_alpha < 100:
            alpha = self.temporal_alpha / 100.0
            edges = cv2.addWeighted(edges, alpha, self.previous_edges, 1 - alpha, 0)
            edges = edges.astype(np.uint8)

        self.previous_edges = edges.copy()

        # 計算 Sobel 梯度（用於強度計算）
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        self.sobel_gradient = np.sqrt(sobelx**2 + sobely**2)
        self.sobel_gradient = np.clip(self.sobel_gradient, 0, 255).astype(np.uint8)

        # 找輪廓
        contours, hierarchy = cv2.findContours(
            edges,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_NONE  # 不壓縮，保留所有點
        )

        if not contours:
            self.contour_points = []
            return edges

        # 計算錨點位置
        anchor_x = int(self.anchor_x_pct * width / 100.0)
        anchor_y = int(self.anchor_y_pct * height / 100.0)

        # 計算範圍
        range_x = int(self.range_pct * width / 100.0)
        range_y = int(self.range_pct * height / 100.0)

        # 過濾範圍內的輪廓
        valid_contours = []
        for contour in contours:
            # 檢查輪廓是否在範圍內
            x, y, w, h = cv2.boundingRect(contour)
            cx = x + w // 2
            cy = y + h // 2

            if (abs(cx - anchor_x) <= range_x and
                abs(cy - anchor_y) <= range_y and
                len(contour) > 10):  # 至少要有 10 個點
                valid_contours.append(contour)

        if not valid_contours:
            self.contour_points = []
            return edges

        # 選擇最長的輪廓
        longest_contour = max(valid_contours, key=len)

        # 轉換為點列表
        self.contour_points = []
        for point in longest_contour:
            x, y = point[0]
            self.contour_points.append((int(x), int(y)))

        return edges

    def update_scan(self, dt: float, width: int, height: int):
        """更新掃描進度並計算 CV 值

        Args:
            dt: 時間間隔（秒）
            width: 畫面寬度
            height: 畫面高度
        """
        if not self.contour_points or self.scan_time <= 0:
            return

        # 更新掃描進度
        progress_increment = dt / self.scan_time
        self.scan_progress += progress_increment

        # 循環掃描
        if self.scan_progress >= 1.0:
            self.scan_progress = 0.0

        # 計算當前掃描點索引
        num_points = len(self.contour_points)
        self.current_scan_index = int(self.scan_progress * num_points)
        self.current_scan_index = min(self.current_scan_index, num_points - 1)

        # 取得當前掃描點
        scan_x, scan_y = self.contour_points[self.current_scan_index]
        self.current_scan_pos = (scan_x, scan_y)

        # 計算 SEQ1/SEQ2（正規化座標）
        self.seq1_value = scan_x / width
        self.seq2_value = scan_y / height

        # 計算 ENV1: X > Y 時輸出差值，否則 0
        if self.seq1_value > self.seq2_value:
            self.env1_value = self.seq1_value - self.seq2_value
        else:
            self.env1_value = 0.0

        # 計算 ENV2: Y > X 時輸出差值，否則 0
        if self.seq2_value > self.seq1_value:
            self.env2_value = self.seq2_value - self.seq1_value
        else:
            self.env2_value = 0.0

        # 計算 ENV3: X 和 Y 接近時輸出（對角線檢測）
        # 當 |X - Y| 越小，輸出越大
        diff = abs(self.seq1_value - self.seq2_value)
        self.env3_value = 1.0 - diff  # 完全相等時 = 1.0，差異大時 = 0.0

    def _calculate_curvature(self, index: int) -> float:
        """計算當前點的輪廓曲率

        Args:
            index: 當前點索引

        Returns:
            曲率值 (0-1)
        """
        if len(self.contour_points) < 5:
            return 0.0

        # 取前後各兩個點
        window = 2
        idx_prev = max(0, index - window)
        idx_next = min(len(self.contour_points) - 1, index + window)

        if idx_prev == idx_next:
            return 0.0

        # 計算向量
        p_prev = np.array(self.contour_points[idx_prev])
        p_curr = np.array(self.contour_points[index])
        p_next = np.array(self.contour_points[idx_next])

        v1 = p_curr - p_prev
        v2 = p_next - p_curr

        # 避免零向量
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 < 1e-6 or norm2 < 1e-6:
            return 0.0

        # 計算夾角
        v1_norm = v1 / norm1
        v2_norm = v2 / norm2

        cos_angle = np.clip(np.dot(v1_norm, v2_norm), -1.0, 1.0)
        angle = np.arccos(cos_angle)

        # 正規化到 0-1（180度 = 1.0）
        curvature = angle / np.pi

        return curvature

    def update_trigger_rings(self):
        """更新觸發光圈動畫"""
        new_rings = []
        for ring in self.trigger_rings:
            ring['radius'] += 6
            ring['alpha'] -= 0.016  # 約 1 秒淡出

            if ring['alpha'] > 0 and ring['radius'] < 180:
                new_rings.append(ring)

        self.trigger_rings = new_rings

    def draw_overlay(self, frame: np.ndarray, edges: np.ndarray) -> np.ndarray:
        """繪製輪廓掃描視覺化

        Args:
            frame: 原始畫面（BGR）
            edges: 邊緣檢測結果

        Returns:
            疊加後的畫面
        """
        output = frame.copy()
        height, width = output.shape[:2]

        # 繪製輪廓線（白色）
        if len(self.contour_points) > 1:
            points = np.array(self.contour_points, dtype=np.int32)
            cv2.polylines(output, [points], False, (255, 255, 255), 2)

        # 繪製當前掃描點（大紅色圓圈）
        if self.current_scan_pos is not None:
            cv2.circle(output, self.current_scan_pos, 12, (0, 0, 255), 2)
            cv2.circle(output, self.current_scan_pos, 8, (0, 0, 255), -1)

        # 繪製錨點（粉白圓圈）
        anchor_x = int(self.anchor_x_pct * width / 100.0)
        anchor_y = int(self.anchor_y_pct * height / 100.0)
        cv2.circle(output, (anchor_x, anchor_y), 6, (255, 255, 255), 2)
        overlay = output.copy()
        cv2.circle(overlay, (anchor_x, anchor_y), 6, (255, 133, 133), -1)
        cv2.addWeighted(overlay, 0.8, output, 0.2, 0, output)
        cv2.circle(output, (anchor_x, anchor_y), 3, (255, 255, 255), 1)

        # 繪製掃描進度條
        self._draw_scan_progress(output)

        # 繪製 CV 數據面板
        self._draw_data_dashboard(output)

        return output

    def _draw_scan_progress(self, frame: np.ndarray):
        """繪製掃描進度條"""
        bar_x = 10
        bar_y = frame.shape[0] - 30
        bar_width = 300
        bar_height = 15

        # 背景
        cv2.rectangle(frame, (bar_x, bar_y),
                     (bar_x + bar_width, bar_y + bar_height),
                     (60, 60, 60), -1)

        # 進度
        filled_width = int(bar_width * self.scan_progress)
        if filled_width > 0:
            cv2.rectangle(frame, (bar_x, bar_y),
                         (bar_x + filled_width, bar_y + bar_height),
                         (0, 255, 0), -1)

        # 邊框
        cv2.rectangle(frame, (bar_x, bar_y),
                     (bar_x + bar_width, bar_y + bar_height),
                     (100, 100, 100), 1)

        # 文字
        text = f"Scan: {self.scan_progress*100:.1f}%"
        cv2.putText(frame, text, (bar_x + bar_width + 10, bar_y + 12),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

    def _draw_data_dashboard(self, frame: np.ndarray):
        """繪製 CV 數據面板"""
        panel_x = 10
        panel_y = 10
        panel_width = 280
        line_height = 28
        padding = 12

        # 背景
        overlay = frame.copy()
        num_lines = 6  # Scan Time + SEQ1 + SEQ2 + ENV1 + ENV2 + ENV3
        panel_height = padding * 2 + line_height * num_lines

        cv2.rectangle(overlay, (panel_x, panel_y),
                     (panel_x + panel_width, panel_y + panel_height),
                     (40, 40, 40), -1)
        cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

        # 邊框
        cv2.rectangle(frame, (panel_x, panel_y),
                     (panel_x + panel_width, panel_y + panel_height),
                     (100, 100, 100), 1)

        # 文字參數
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        font_thickness = 1
        text_color = (140, 140, 140)
        value_color = (255, 255, 255)

        y_offset = panel_y + padding + 15

        # Scan Time
        scan_text = f"Scan Time: {self.scan_time:.1f}s"
        cv2.putText(frame, scan_text, (panel_x + padding, y_offset),
                   font, font_scale, value_color, font_thickness)
        y_offset += line_height

        # SEQ1 (X座標)
        self._draw_cv_bar(frame, panel_x, y_offset, "SEQ1",
                         self.seq1_value, CV_COLORS_BGR['SEQ1'])
        y_offset += line_height

        # SEQ2 (Y座標)
        self._draw_cv_bar(frame, panel_x, y_offset, "SEQ2",
                         self.seq2_value, CV_COLORS_BGR['SEQ2'])
        y_offset += line_height

        # ENV1 (X > Y)
        self._draw_cv_bar(frame, panel_x, y_offset, "ENV1 (X>Y)",
                         self.env1_value, CV_COLORS_BGR['ENV1'])
        y_offset += line_height

        # ENV2 (Y > X)
        self._draw_cv_bar(frame, panel_x, y_offset, "ENV2 (Y>X)",
                         self.env2_value, CV_COLORS_BGR['ENV2'])
        y_offset += line_height

        # ENV3 (對角線)
        self._draw_cv_bar(frame, panel_x, y_offset, "ENV3 (X=Y)",
                         self.env3_value, CV_COLORS_BGR['ENV3'])

    def _draw_cv_bar(self, frame: np.ndarray, panel_x: int, y_offset: int,
                     label: str, value: float, color: Tuple[int, int, int]):
        """繪製單個 CV 條狀圖"""
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        font_thickness = 1
        padding = 12

        # 標籤
        cv2.putText(frame, f"{label}:", (panel_x + padding, y_offset),
                   font, font_scale, color, font_thickness)

        # 電壓值
        voltage = value * 10.0
        voltage_text = f"{voltage:.1f}V"
        cv2.putText(frame, voltage_text, (panel_x + 220, y_offset),
                   font, font_scale - 0.05, color, font_thickness)

        # 條狀圖
        bar_x = panel_x + 80
        bar_y = y_offset - 12
        bar_width = 130
        bar_height = 12

        cv2.rectangle(frame, (bar_x, bar_y),
                     (bar_x + bar_width, bar_y + bar_height),
                     (80, 80, 80), 1)

        filled_width = int(bar_width * value)
        if filled_width > 0:
            cv2.rectangle(frame, (bar_x + 1, bar_y + 1),
                         (bar_x + filled_width, bar_y + bar_height - 1),
                         color, -1)

    # 參數設定方法
    def set_threshold(self, threshold: int):
        self.threshold = np.clip(threshold, 0, 255)

    def set_smoothing(self, smoothing: int):
        self.temporal_alpha = np.clip(smoothing, 0, 100)

    def set_anchor_position(self, x_pct: float, y_pct: float):
        self.anchor_x_pct = np.clip(x_pct, 0, 100)
        self.anchor_y_pct = np.clip(y_pct, 0, 100)

    def set_range(self, range_pct: float):
        self.range_pct = np.clip(range_pct, 0, 50)

    def set_scan_time(self, scan_time: float):
        """設定掃描時間（秒）"""
        self.scan_time = np.clip(scan_time, 0.1, 60.0)
