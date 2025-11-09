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

        # CV 輸出值 0-10V
        self.seq1_value = 0.0  # X 座標 0-10V
        self.seq2_value = 0.0  # Y 座標 0-10V
        self.env1_value = 0.0  # ENV1觸發式 0-10V
        self.env2_value = 0.0  # ENV2觸發式 0-10V
        self.env3_value = 0.0  # ENV3觸發式 0-10V

        # Envelope觸發狀態追蹤
        self.prev_x_greater = False  # 上一幀 X > Y 的狀態
        self.prev_y_greater = False  # 上一幀 Y > X 的狀態
        self.curvature_threshold = 0.3  # 曲率觸發閾值
        self.prev_high_curvature = False  # 上一幀高曲率狀態

        # 視覺化
        self.current_scan_pos = None  # 當前掃描位置 (x, y)
        self.trigger_rings = []
        self.last_trigger_positions = {'env1': None, 'env2': None, 'env3': None}

        # 輪廓穩定性追蹤
        self.prev_anchor_x_pct = self.anchor_x_pct
        self.prev_anchor_y_pct = self.anchor_y_pct
        self.prev_range_pct = self.range_pct
        self.prev_gray = None
        self.scene_change_threshold = 5.0  # 場景變化閾值 百分比

        # 檢測時的畫面尺寸 用於繪製時縮放
        self.detection_width = 1920
        self.detection_height = 1080

        # Sobel 梯度（用於邊緣強度計算）
        self.sobel_gradient = None

    def detect_and_extract_contour(self, gray: np.ndarray):
        """偵測邊緣並提取最主要的輪廓線

        只在以下情況更新輪廓:
        1. 錨點位置改變
        2. Range改變
        3. 畫面內容明顯變化
        4. 首次執行

        Args:
            gray: 灰階畫面
        """
        height, width = gray.shape

        # 檢查是否需要更新輪廓
        anchor_moved = (abs(self.anchor_x_pct - self.prev_anchor_x_pct) > 0.0001 or
                       abs(self.anchor_y_pct - self.prev_anchor_y_pct) > 0.0001)
        range_changed = abs(self.range_pct - self.prev_range_pct) > 0.0001

        scene_changed = False
        if self.prev_gray is not None:
            diff = cv2.absdiff(gray, self.prev_gray)
            mean_diff = np.mean(diff)
            diff_percentage = (mean_diff / 255.0) * 100.0
            scene_changed = diff_percentage > self.scene_change_threshold

        # 只在錨點range移動或場景變化或首次執行時更新
        if not (anchor_moved or range_changed or scene_changed or self.prev_gray is None):
            return self.previous_edges if self.previous_edges is not None else np.zeros_like(gray)

        # 更新追蹤狀態
        self.prev_anchor_x_pct = self.anchor_x_pct
        self.prev_anchor_y_pct = self.anchor_y_pct
        self.prev_range_pct = self.range_pct
        self.prev_gray = gray.copy()

        # 儲存檢測時的畫面尺寸
        self.detection_width = width
        self.detection_height = height

        # 計算錨點位置和ROI範圍
        anchor_x = int(self.anchor_x_pct * width / 100.0)
        anchor_y = int(self.anchor_y_pct * height / 100.0)
        # range_pct是ROI半徑的百分比 所以除以2
        range_x = int(self.range_pct * width / 100.0 / 2.0)
        range_y = int(self.range_pct * height / 100.0 / 2.0)

        # 高斯模糊
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Canny 邊緣檢測
        low_threshold = int(self.threshold * 0.5)
        high_threshold = self.threshold
        edges = cv2.Canny(blurred, low_threshold, high_threshold)

        # 建立ROI mask 只保留ROI內的邊緣
        mask = np.zeros_like(edges)
        roi_x1 = max(0, anchor_x - range_x)
        roi_y1 = max(0, anchor_y - range_y)
        roi_x2 = min(width, anchor_x + range_x)
        roi_y2 = min(height, anchor_y + range_y)
        mask[roi_y1:roi_y2, roi_x1:roi_x2] = 255
        edges = cv2.bitwise_and(edges, edges, mask=mask)

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

        # 找輪廓 現在只會找到ROI內的輪廓
        contours, hierarchy = cv2.findContours(
            edges,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_NONE
        )

        if not contours:
            self.contour_points = []
            return edges

        # 過濾太短的輪廓
        valid_contours = [c for c in contours if len(c) > 10]

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

    def update_scan(self, dt: float, width: int, height: int, envelopes: list = None):
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

        # 計算 SEQ1/SEQ2 輸出0-10V
        seq1_normalized = scan_x / width
        seq2_normalized = scan_y / height
        self.seq1_value = seq1_normalized * 10.0
        self.seq2_value = seq2_normalized * 10.0

        # ENV1觸發檢測: X > Y邊緣觸發
        x_greater = seq1_normalized > seq2_normalized
        if x_greater and not self.prev_x_greater:
            # 從X≤Y變成X>Y 觸發ENV1
            if envelopes and len(envelopes) > 0:
                envelopes[0].trigger()
                self.trigger_rings.append({
                    'pos': (scan_x, scan_y),
                    'radius': 15,
                    'alpha': 1.0,
                    'color': CV_COLORS_BGR['ENV1'],
                    'decay_time': envelopes[0].decay_time
                })
                self.last_trigger_positions['env1'] = (scan_x, scan_y, CV_COLORS_BGR['ENV1'])
        self.prev_x_greater = x_greater

        # ENV2觸發檢測: Y > X邊緣觸發
        y_greater = seq2_normalized > seq1_normalized
        if y_greater and not self.prev_y_greater:
            # 從Y≤X變成Y>X 觸發ENV2
            if envelopes and len(envelopes) > 1:
                envelopes[1].trigger()
                self.trigger_rings.append({
                    'pos': (scan_x, scan_y),
                    'radius': 15,
                    'alpha': 1.0,
                    'color': CV_COLORS_BGR['ENV2'],
                    'decay_time': envelopes[1].decay_time
                })
                self.last_trigger_positions['env2'] = (scan_x, scan_y, CV_COLORS_BGR['ENV2'])
        self.prev_y_greater = y_greater

        # ENV3觸發檢測: 高曲率轉彎
        curvature = self._calculate_curvature(self.current_scan_index)
        high_curvature = curvature > self.curvature_threshold
        if high_curvature and not self.prev_high_curvature:
            # 從低曲率變成高曲率 觸發ENV3
            if envelopes and len(envelopes) > 2:
                envelopes[2].trigger()
                self.trigger_rings.append({
                    'pos': (scan_x, scan_y),
                    'radius': 15,
                    'alpha': 1.0,
                    'color': CV_COLORS_BGR['ENV3'],
                    'decay_time': envelopes[2].decay_time
                })
                self.last_trigger_positions['env3'] = (scan_x, scan_y, CV_COLORS_BGR['ENV3'])
        self.prev_high_curvature = high_curvature

        # 更新envelope輸出值 0-10V
        if envelopes:
            if len(envelopes) > 0:
                self.env1_value = envelopes[0].value * 10.0
            if len(envelopes) > 1:
                self.env2_value = envelopes[1].value * 10.0
            if len(envelopes) > 2:
                self.env3_value = envelopes[2].value * 10.0

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

    def update_trigger_rings(self, dt: float = 1.0/60.0):
        """更新觸發光圈動畫

        Args:
            dt: 時間間隔 秒
        """
        new_rings = []
        for ring in self.trigger_rings:
            # 根據decay_time計算擴張和淡出速度
            decay_time = ring.get('decay_time', 1.0)

            # 半徑在decay_time內從15擴張到150
            radius_speed = (150 - 15) / decay_time
            ring['radius'] += radius_speed * dt

            # alpha在decay_time內從1.0淡到0
            alpha_speed = 1.0 / decay_time
            ring['alpha'] -= alpha_speed * dt

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
        frame_height, frame_width = output.shape[:2]

        # 計算座標縮放比例 從檢測畫面到繪製畫面
        scale_x = frame_width / self.detection_width if self.detection_width > 0 else 1.0
        scale_y = frame_height / self.detection_height if self.detection_height > 0 else 1.0

        # 繪製輪廓線 黑線與白線並存 加粗兩倍
        if len(self.contour_points) > 1:
            scaled_points = [(int(x * scale_x), int(y * scale_y)) for x, y in self.contour_points]
            points = np.array(scaled_points, dtype=np.int32)
            # 先畫黑色粗線
            cv2.polylines(output, [points], False, (0, 0, 0), 8)
            # 再畫白色細線
            cv2.polylines(output, [points], False, (255, 255, 255), 4)

        # 繪製當前掃描點 黑色與白色十字並存 加粗兩倍
        if self.current_scan_pos is not None:
            scan_x_scaled = int(self.current_scan_pos[0] * scale_x)
            scan_y_scaled = int(self.current_scan_pos[1] * scale_y)
            cross_size = 20
            # 黑色十字
            cv2.line(output,
                    (scan_x_scaled - cross_size, scan_y_scaled),
                    (scan_x_scaled + cross_size, scan_y_scaled),
                    (0, 0, 0), 8)
            cv2.line(output,
                    (scan_x_scaled, scan_y_scaled - cross_size),
                    (scan_x_scaled, scan_y_scaled + cross_size),
                    (0, 0, 0), 8)
            # 白色十字
            cv2.line(output,
                    (scan_x_scaled - cross_size, scan_y_scaled),
                    (scan_x_scaled + cross_size, scan_y_scaled),
                    (255, 255, 255), 4)
            cv2.line(output,
                    (scan_x_scaled, scan_y_scaled - cross_size),
                    (scan_x_scaled, scan_y_scaled + cross_size),
                    (255, 255, 255), 4)

        # 繪製觸發光圈
        for ring in self.trigger_rings:
            pos_x, pos_y = ring['pos']
            pos_x_scaled = int(pos_x * scale_x)
            pos_y_scaled = int(pos_y * scale_y)
            radius_scaled = int(ring['radius'] * scale_x)
            color = ring['color']
            alpha = ring['alpha']

            # 建立半透明圖層
            overlay = output.copy()
            cv2.circle(overlay, (pos_x_scaled, pos_y_scaled), radius_scaled, color, 3)
            cv2.addWeighted(overlay, alpha, output, 1 - alpha, 0, output)

        # 繪製錨點（粉白圓圈）
        anchor_x = int(self.anchor_x_pct * frame_width / 100.0)
        anchor_y = int(self.anchor_y_pct * frame_height / 100.0)
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
        """繪製單個 CV 條狀圖

        Args:
            value: 0-10V 的電壓值
        """
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        font_thickness = 1
        padding = 12

        # 標籤
        cv2.putText(frame, f"{label}:", (panel_x + padding, y_offset),
                   font, font_scale, color, font_thickness)

        # 電壓值 value已經是0-10V
        voltage_text = f"{value:.1f}V"
        cv2.putText(frame, voltage_text, (panel_x + 220, y_offset),
                   font, font_scale - 0.05, color, font_thickness)

        # 條狀圖 需要正規化為0-1
        bar_x = panel_x + 80
        bar_y = y_offset - 12
        bar_width = 130
        bar_height = 12

        cv2.rectangle(frame, (bar_x, bar_y),
                     (bar_x + bar_width, bar_y + bar_height),
                     (80, 80, 80), 1)

        normalized_value = value / 10.0  # 0-10V轉為0-1
        filled_width = int(bar_width * normalized_value)
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
        self.range_pct = np.clip(range_pct, 0, 100)

    def set_scan_time(self, scan_time: float):
        """設定掃描時間（秒）"""
        self.scan_time = np.clip(scan_time, 0.1, 60.0)
