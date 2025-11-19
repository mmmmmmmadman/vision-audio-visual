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
        self.range_pct = 25  # 預設 25%

        # 掃描參數
        self.scan_time = 10.0  # 掃過完整輪廓的時間（秒）預設 10 秒
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
        self.env4_value = 0.0  # ENV4觸發式 0-10V

        # 正規化的 X Y 座標 (0-1)
        self.x_normalized = 0.0
        self.y_normalized = 0.0

        # Envelope 觸發事件 (當幀有觸發時設為 True)
        self.env1_triggered = False
        self.env2_triggered = False
        self.env3_triggered = False
        self.env4_triggered = False

        # Envelope decay 狀態追蹤 (用於 retrigger 保護)
        self.env1_decay_active = False
        self.env2_decay_active = False
        self.env3_decay_active = False
        self.env4_decay_active = False
        self.env_decay_counters = [0.0, 0.0, 0.0, 0.0]  # 剩餘 decay 時間 (秒)

        # Envelope觸發狀態追蹤
        self.prev_x_greater = False  # 上一幀 X > Y 的狀態
        self.prev_y_greater = False  # 上一幀 Y > X 的狀態
        self.curvature_threshold = 0.3  # 曲率觸發閾值
        self.prev_high_curvature = False  # 上一幀高曲率狀態
        self.prev_speed_weight = 1.0  # 上一幀的速度權重 (用於偵測加減速)

        # 視覺化
        self.current_scan_pos = None  # 當前掃描位置 (x, y)
        self.trigger_rings = []
        self.last_trigger_positions = {'env1': None, 'env2': None, 'env3': None}
        self.contour_brightness = []  # 輪廓點的亮度值 0-1

        # 輪廓穩定性追蹤
        self.prev_anchor_x_pct = self.anchor_x_pct
        self.prev_anchor_y_pct = self.anchor_y_pct
        self.prev_range_pct = self.range_pct
        self.prev_gray = None
        self.scene_change_threshold = 1.0  # 場景變化閾值 百分比 (可從 GUI 調整 1-10%)

        # Chaos LFO speed ratio
        self.chaos_ratio = 0.1  # 0.1-1.0, LFO speed relative to scan time (預設 1/10)

        # 檢測時的畫面尺寸 用於繪製時縮放
        self.detection_width = 1920
        self.detection_height = 1080

        # 快取上次找到的所有輪廓，用於快速重新過濾
        self.cached_contours = []

        # 輪廓長度
        self.contour_length = 0.0

        # ENV4: 掃描循環完成觸發
        self.scan_loop_completed = False

        # 變速掃描系統
        self.curvature_values = []  # 每個點的曲率值
        self.speed_weights = []  # 每個點的速度權重 (0.5x-2x)
        self.time_allocations = []  # 每個點分配的時間比例
        self.cumulative_time = []  # 累積時間比例 (用於查找當前點)

        # LFO Pattern 系統
        self.lfo_phase = 0.0  # 當前 LFO 相位 (0 到 1)
        self.lfo_variants = np.zeros(8, dtype=np.float32)  # 8 個變種訊號輸出
        self.modulation_amounts = np.ones(8, dtype=np.float32)  # 8 個 modulation amount (0-1) 預設全滿

        # 8 個 pattern 預計算的波形 (每個 pattern 100 個點)
        self.lfo_patterns = []  # List of 8 arrays, each with 100 samples
        self.pattern_resolution = 100  # Pattern 解析度
        self._generate_lfo_patterns()


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

        # 降低偵測解析度至 25%
        detection_scale = 0.25
        detect_width = int(width * detection_scale)
        detect_height = int(height * detection_scale)
        gray_small = cv2.resize(gray, (detect_width, detect_height))

        # 檢查是否需要更新輪廓
        anchor_moved = (abs(self.anchor_x_pct - self.prev_anchor_x_pct) > 0.0001 or
                       abs(self.anchor_y_pct - self.prev_anchor_y_pct) > 0.0001)
        range_changed = abs(self.range_pct - self.prev_range_pct) > 0.0001

        scene_changed = False
        if self.prev_gray is not None:
            diff = cv2.absdiff(gray_small, self.prev_gray)
            mean_diff = np.mean(diff)
            diff_percentage = (mean_diff / 255.0) * 100.0
            scene_changed = diff_percentage > self.scene_change_threshold

        # 正常執行邊緣檢測（anchor/range改變也會觸發）
        params_changed = anchor_moved or range_changed

        # 如果參數沒變且場景也沒變 直接返回使用舊輪廓
        if not params_changed and not scene_changed and len(self.contour_points) > 0:
            return

        # 更新追蹤狀態
        self.prev_anchor_x_pct = self.anchor_x_pct
        self.prev_anchor_y_pct = self.anchor_y_pct
        self.prev_range_pct = self.range_pct
        self.prev_gray = gray_small.copy()

        # 儲存原始畫面尺寸
        self.detection_width = width
        self.detection_height = height

        # 計算錨點位置和ROI範圍 使用縮小後的座標
        anchor_x = int(self.anchor_x_pct * detect_width / 100.0)
        anchor_y = int(self.anchor_y_pct * detect_height / 100.0)
        range_x = int(self.range_pct * detect_width / 100.0 / 2.0)
        range_y = int(self.range_pct * detect_height / 100.0 / 2.0)

        # DEBUG: Monitor sync status
        if anchor_moved or range_changed:
            print(f"🔄 ROI UPDATE: Anchor({self.anchor_x_pct:.1f}%, {self.anchor_y_pct:.1f}%) → Pixel({anchor_x}, {anchor_y}), Range={self.range_pct:.0f}% → Radius({range_x}, {range_y})")

        # 計算ROI邊界
        roi_x1 = max(0, anchor_x - range_x)
        roi_y1 = max(0, anchor_y - range_y)
        roi_x2 = min(detect_width, anchor_x + range_x)
        roi_y2 = min(detect_height, anchor_y + range_y)

        # 只對ROI區域執行高斯模糊和Canny
        roi_gray = gray_small[roi_y1:roi_y2, roi_x1:roi_x2]
        roi_blurred = cv2.GaussianBlur(roi_gray, (5, 5), 0)

        # Canny 邊緣檢測
        low_threshold = int(self.threshold * 0.5)
        high_threshold = self.threshold
        roi_edges = cv2.Canny(roi_blurred, low_threshold, high_threshold)

        # 形態學閉合操作
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        roi_edges = cv2.morphologyEx(roi_edges, cv2.MORPH_CLOSE, kernel)

        # 建立縮小尺寸的edges圖像
        edges = np.zeros_like(gray_small)
        edges[roi_y1:roi_y2, roi_x1:roi_x2] = roi_edges

        # 時間平滑
        if self.previous_edges is not None and self.temporal_alpha < 100:
            if anchor_moved or range_changed:
                alpha = min(0.9, self.temporal_alpha / 100.0 + 0.3)
            else:
                alpha = self.temporal_alpha / 100.0
            edges = cv2.addWeighted(edges, alpha, self.previous_edges, 1 - alpha, 0)
            edges = edges.astype(np.uint8)

        self.previous_edges = edges.copy()

        # 找輪廓
        contours, hierarchy = cv2.findContours(
            edges,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_NONE
        )

        if not contours:
            self.contour_points = []
            return edges

        # 過濾太短的輪廓
        valid_contours = [c for c in contours if len(c) > 1]

        if not valid_contours:
            self.contour_points = []
            self.cached_contours = []
            return edges

        self.cached_contours = valid_contours

        # 過濾輪廓並放大座標回原始解析度
        range_radius = ((range_x ** 2 + range_y ** 2) ** 0.5)
        range_radius_sq = range_radius ** 2
        best_filtered_contour = []
        best_brightness = []

        for contour in valid_contours:
            filtered_points = []
            filtered_brightness = []
            for point in contour:
                x, y = point[0]
                dist_sq = (x - anchor_x) ** 2 + (y - anchor_y) ** 2
                if dist_sq <= range_radius_sq:
                    # 放大座標回原始解析度
                    x_scaled = int(x / detection_scale)
                    y_scaled = int(y / detection_scale)
                    filtered_points.append((x_scaled, y_scaled))

                    # 從原始灰階圖取樣該點的亮度
                    # 確保座標在範圍內
                    if 0 <= y_scaled < height and 0 <= x_scaled < width:
                        brightness = float(gray[y_scaled, x_scaled]) / 255.0
                        filtered_brightness.append(brightness)
                    else:
                        filtered_brightness.append(0.5)  # 預設中等亮度

            if len(filtered_points) > len(best_filtered_contour):
                best_filtered_contour = filtered_points
                best_brightness = filtered_brightness

        self.contour_points = best_filtered_contour
        self.contour_brightness = best_brightness

        # 計算輪廓長度 (用於 ENV4 觸發)
        self.contour_length = float(len(self.contour_points))

        # 計算變速掃描參數
        self._calculate_variable_speed_params()

        return edges

    def update_scan(self, dt: float, width: int, height: int, envelopes: list = None,
                   env_decay_times: list = None):
        """更新掃描進度並計算 CV 值

        Args:
            dt: 時間間隔（秒）
            width: 畫面寬度
            height: 畫面高度
            envelopes: envelope 物件列表（可選，用於相容性）
            env_decay_times: envelope decay 時間列表 [env1_decay, env2_decay, env3_decay]
        """
        if not self.contour_points or self.scan_time <= 0:
            return

        # 預設 decay time
        if env_decay_times is None:
            env_decay_times = [1.0, 1.0, 1.0]

        # 更新掃描進度
        progress_increment = dt / self.scan_time
        self.scan_progress += progress_increment

        # 循環掃描
        self.scan_loop_completed = False
        if self.scan_progress >= 1.0:
            self.scan_progress = 0.0
            self.scan_loop_completed = True  # 標記循環完成

        # 計算當前掃描點索引
        num_points = len(self.contour_points)

        # 使用變速掃描：根據累積時間查找當前點
        if len(self.cumulative_time) > 0:
            # 二分搜尋找到對應的點索引
            self.current_scan_index = 0
            for i in range(len(self.cumulative_time) - 1):
                if self.cumulative_time[i] <= self.scan_progress < self.cumulative_time[i + 1]:
                    self.current_scan_index = i
                    break
            else:
                # 如果沒找到 使用最後一個點
                self.current_scan_index = num_points - 1
        else:
            # 降級到等速掃描
            self.current_scan_index = int(self.scan_progress * num_points)
            self.current_scan_index = min(self.current_scan_index, num_points - 1)

        # 取得當前掃描點
        scan_x, scan_y = self.contour_points[self.current_scan_index]
        self.current_scan_pos = (scan_x, scan_y)

        # 計算 SEQ1/SEQ2 輸出0-10V
        # SEQ1: X 座標到 Anchor 的距離
        # SEQ2: Y 座標到 Anchor 的距離
        x_normalized = scan_x / width
        y_normalized = scan_y / height

        # 計算 Anchor 正規化座標
        anchor_x_normalized = self.anchor_x_pct / 100.0
        anchor_y_normalized = self.anchor_y_pct / 100.0

        # 計算距離 (絕對值)
        seq1_normalized = abs(x_normalized - anchor_x_normalized)
        seq2_normalized = abs(y_normalized - anchor_y_normalized)

        # Range 控制輸出放大倍數 (指數映射)
        # Range 1% -> 8x, Range 120% -> 2x
        # 使用指數映射讓放大倍數快速降低
        # 正規化 range_pct 到 0-1
        range_normalized = (self.range_pct - 1.0) / 119.0
        # 反向指數曲線: 2 + 6 * (1 - t)^2
        gain = 2.0 + (6.0 * ((1.0 - range_normalized) ** 2))

        # 應用放大並限制在 0-10V
        self.seq1_value = min(seq1_normalized * gain * 10.0, 10.0)
        self.seq2_value = min(seq2_normalized * gain * 10.0, 10.0)

        # 保存正規化的 X Y 座標 (用於 envelope 觸發)
        self.x_normalized = x_normalized
        self.y_normalized = y_normalized

        # 更新 envelope decay 計數器
        for i in range(4):
            if self.env_decay_counters[i] > 0:
                self.env_decay_counters[i] -= dt
                if self.env_decay_counters[i] <= 0:
                    self.env_decay_counters[i] = 0
                    # Decay 完成 更新狀態
                    if i == 0:
                        self.env1_decay_active = False
                    elif i == 1:
                        self.env2_decay_active = False
                    elif i == 2:
                        self.env3_decay_active = False
                    elif i == 3:
                        self.env4_decay_active = False

        # 清除上一幀的觸發標記
        self.env1_triggered = False
        self.env2_triggered = False
        self.env3_triggered = False
        self.env4_triggered = False

        # ENV1觸發檢測: X 距離 Anchor > Y 距離 Anchor (邊緣觸發)
        x_dist_greater = seq1_normalized > seq2_normalized
        if x_dist_greater and not self.prev_x_greater:
            # 從 X距離≤Y距離 變成 X距離>Y距離 觸發ENV1 (檢查 retrigger 保護)
            if not self.env1_decay_active:
                self.env1_triggered = True
                self.env1_decay_active = True
                decay_time = env_decay_times[0] if len(env_decay_times) > 0 else 1.0
                self.env_decay_counters[0] = decay_time
                # 創建視覺觸發光圈
                self.trigger_rings.append({
                    'pos': (scan_x, scan_y),
                    'radius': 15,
                    'alpha': 1.0,
                    'color': CV_COLORS_BGR['ENV1'],
                    'decay_time': decay_time,
                    'arc_segments': self._generate_arc_segments(16)
                })
                self.last_trigger_positions['env1'] = (scan_x, scan_y, CV_COLORS_BGR['ENV1'])
        self.prev_x_greater = x_dist_greater

        # ENV2觸發檢測: Y 距離 Anchor > X 距離 Anchor (邊緣觸發)
        y_dist_greater = seq2_normalized > seq1_normalized
        if y_dist_greater and not self.prev_y_greater:
            # 從 Y距離≤X距離 變成 Y距離>X距離 觸發ENV2 (檢查 retrigger 保護)
            if not self.env2_decay_active:
                self.env2_triggered = True
                self.env2_decay_active = True
                decay_time = env_decay_times[1] if len(env_decay_times) > 1 else 1.0
                self.env_decay_counters[1] = decay_time
                # 創建視覺觸發光圈
                self.trigger_rings.append({
                    'pos': (scan_x, scan_y),
                    'radius': 15,
                    'alpha': 1.0,
                    'color': CV_COLORS_BGR['ENV2'],
                    'decay_time': decay_time,
                    'arc_segments': self._generate_arc_segments(16)
                })
                self.last_trigger_positions['env2'] = (scan_x, scan_y, CV_COLORS_BGR['ENV2'])
        self.prev_y_greater = y_dist_greater

        # ENV3觸發檢測: 加速瞬間觸發
        # 取得當前點的速度權重
        current_speed_weight = 1.0
        if len(self.speed_weights) > 0 and self.current_scan_index < len(self.speed_weights):
            current_speed_weight = self.speed_weights[self.current_scan_index]

        # 偵測加速: 速度權重降低 (權重低 = 速度快)
        # 設定閾值避免微小變化觸發
        speed_threshold = 0.3
        is_accelerating = (self.prev_speed_weight - current_speed_weight) > speed_threshold

        if is_accelerating and not self.env3_decay_active:
            self.env3_triggered = True
            self.env3_decay_active = True
            decay_time = env_decay_times[2] if len(env_decay_times) > 2 else 1.0
            self.env_decay_counters[2] = decay_time
            self.trigger_rings.append({
                'pos': (scan_x, scan_y),
                'radius': 15,
                'alpha': 1.0,
                'color': CV_COLORS_BGR['ENV3'],
                'decay_time': decay_time,
                'arc_segments': self._generate_arc_segments(16)
            })
            self.last_trigger_positions['env3'] = (scan_x, scan_y, CV_COLORS_BGR['ENV3'])

        # ENV4觸發檢測: 減速瞬間觸發
        # 偵測減速: 速度權重增加 (權重高 = 速度慢)
        is_decelerating = (current_speed_weight - self.prev_speed_weight) > speed_threshold

        if is_decelerating and not self.env4_decay_active:
            self.env4_triggered = True
            self.env4_decay_active = True
            decay_time = env_decay_times[3] if len(env_decay_times) > 3 else 1.0
            self.env_decay_counters[3] = decay_time
            self.trigger_rings.append({
                'pos': (scan_x, scan_y),
                'radius': 15,
                'alpha': 1.0,
                'color': CV_COLORS_BGR['ENV4'],
                'decay_time': decay_time,
                'arc_segments': self._generate_arc_segments(16)
            })
            self.last_trigger_positions['env4'] = (scan_x, scan_y, CV_COLORS_BGR['ENV4'])

        # 更新上一幀的速度權重
        self.prev_speed_weight = current_speed_weight

        # 更新 Sine LFO 與變種訊號
        self._update_lfo()

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

    def _calculate_variable_speed_params(self):
        """計算變速掃描參數

        1. 計算每個點的曲率
        2. 根據曲率分配速度權重 (彎道 0.5x, 直線 2x) 瞬間切換
        3. 重新分配時間確保總時間符合 scan_time
        """
        if len(self.contour_points) < 5:
            self.curvature_values = []
            self.speed_weights = []
            self.time_allocations = []
            self.cumulative_time = []
            return

        num_points = len(self.contour_points)

        # 1. 計算每個點的曲率
        self.curvature_values = []
        for i in range(num_points):
            curvature = self._calculate_curvature(i)
            self.curvature_values.append(curvature)

        # 2. 根據曲率分配速度權重 (瞬間加速減速)
        # 曲率高 (彎道) -> 速度慢 0.5x -> 權重高 2.0
        # 曲率低 (直線) -> 速度快 2x -> 權重低 0.5
        # 速度 = 1 / 權重
        self.speed_weights = []
        for curvature in self.curvature_values:
            # 增加曲率敏感度：使用指數放大
            enhanced_curvature = curvature ** 0.5  # 平方根讓小曲率也能偵測到
            # 映射到更大的權重範圍 0.25-3.0 (速度 4x - 0.33x)
            # 直線更快 彎道更慢
            weight = 0.25 + (2.75 * enhanced_curvature)
            self.speed_weights.append(weight)

        # 3. 重新分配時間確保總時間符合 scan_time
        total_weight = sum(self.speed_weights)
        self.time_allocations = [w / total_weight for w in self.speed_weights]

        # 4. 計算累積時間 (用於根據 scan_progress 查找當前點)
        self.cumulative_time = [0.0]
        for time_alloc in self.time_allocations:
            self.cumulative_time.append(self.cumulative_time[-1] + time_alloc)

        # 確保最後一個值是 1.0
        if self.cumulative_time:
            self.cumulative_time[-1] = 1.0

    def _generate_arc_segments(self, num_segments: int = 16):
        """生成破碎波紋的弧段配置 基於真實水波物理

        Args:
            num_segments: 弧段數量

        Returns:
            弧段配置列表 每個弧段包含角度調變參數
        """
        segments = []
        segment_angle = 360.0 / num_segments

        # 生成隨機相位用於正弦波調變 模擬表面張力干涉
        phase_offsets = [np.random.random() * 2 * np.pi for _ in range(3)]

        # 每個角度的調變由多個正弦波疊加
        # 模擬重力波和毛細波的組合效果
        for i in range(num_segments):
            base_angle = i * segment_angle
            angle_rad = np.deg2rad(base_angle)

            # 多頻率正弦波疊加 產生自然的破碎模式
            # 使用較少波峰 讓段落更長更連續
            # 低頻: 2-3 個大段落
            # 中頻: 輕微調變
            modulation = (
                0.7 * np.sin(2.3 * angle_rad + phase_offsets[0]) +
                0.2 * np.sin(4.7 * angle_rad + phase_offsets[1]) +
                0.1 * np.sin(9.1 * angle_rad + phase_offsets[2])
            )

            # 歸一化到 0-1 範圍
            visibility = (modulation + 1.0) / 2.0  # -1~1 -> 0~1

            # 輕微的非線性變換 保持較高的整體可見度
            # 使用 1.2 次方 稍微拉開差距但不要太極端
            visibility = visibility ** 1.2

            segments.append({
                'base_angle': base_angle,
                'visibility': visibility,  # 0=完全消失 1=完全可見
                'phase_offsets': phase_offsets  # 保留相位供繪製時使用
            })

        return segments

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

    def draw_overlay(self, frame: np.ndarray, cv_values: np.ndarray = None) -> np.ndarray:
        """繪製輪廓掃描視覺化

        Args:
            frame: 原始畫面（BGR）
            cv_values: CV 值陣列 [ENV1, ENV2, ENV3, SEQ1, SEQ2] (0-1 range)

        Returns:
            疊加後的畫面
        """
        output = frame.copy()
        frame_height, frame_width = output.shape[:2]

        # 計算座標縮放比例 從檢測畫面到繪製畫面
        scale_x = frame_width / self.detection_width if self.detection_width > 0 else 1.0
        scale_y = frame_height / self.detection_height if self.detection_height > 0 else 1.0

        # 輪廓線繪製已移至 GPU overlay (qt_opengl_renderer.py)
        # CPU 版本已停用以避免重複繪製

        # 掃描點十字繪製已移至 GPU overlay (qt_opengl_renderer.py)
        # CPU 版本已停用以避免重複繪製

        # PERFORMANCE: ROI 圓圈和 CV meter 已停用以提升效能
        # 保留錨點計算供內部使用
        anchor_x = int(self.anchor_x_pct * frame_width / 100.0)
        anchor_y = int(self.anchor_y_pct * frame_height / 100.0)
        range_radius_x = int(self.range_pct * frame_width / 100.0 / 2.0)
        range_radius_y = int(self.range_pct * frame_height / 100.0 / 2.0)
        range_radius = int((range_radius_x + range_radius_y) / 2)

        # 觸發光圈繪製已移至 GPU overlay (qt_opengl_renderer.py)
        # CPU 版本已停用以避免重複繪製

        # 掃描進度條已停用
        # self._draw_scan_progress(output)

        # CV 數據面板 (已移到 GPU renderer CPU端繪製)
        # self._draw_data_dashboard(output, cv_values)

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

    def _draw_data_dashboard(self, frame: np.ndarray, cv_values: np.ndarray = None):
        """繪製 CV 數據面板

        Args:
            frame: 畫面
            cv_values: CV 值陣列 [ENV1, ENV2, ENV3, SEQ1, SEQ2] (0-1 range)
        """
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

        # 使用從 audio process 傳來的 CV 值 如果沒有則用本地值
        if cv_values is not None and len(cv_values) >= 6:
            env1_val = cv_values[0] * 10.0  # 轉換為 0-10V
            env2_val = cv_values[1] * 10.0
            env3_val = cv_values[2] * 10.0
            env4_val = cv_values[3] * 10.0
            seq1_val = cv_values[4] * 10.0
            seq2_val = cv_values[5] * 10.0
        else:
            env1_val = self.env1_value
            env2_val = self.env2_value
            env3_val = self.env3_value
            env4_val = self.env4_value
            seq1_val = self.seq1_value
            seq2_val = self.seq2_value

        # ENV1 (X > Y)
        self._draw_cv_bar(frame, panel_x, y_offset, "ENV1 (X>Y)",
                         env1_val, CV_COLORS_BGR['ENV1'])
        y_offset += line_height

        # ENV2 (Y > X)
        self._draw_cv_bar(frame, panel_x, y_offset, "ENV2 (Y>X)",
                         env2_val, CV_COLORS_BGR['ENV2'])
        y_offset += line_height

        # ENV3 (閾值)
        self._draw_cv_bar(frame, panel_x, y_offset, "ENV3 (Thr)",
                         env3_val, CV_COLORS_BGR['ENV3'])
        y_offset += line_height

        # ENV4 (循環)
        self._draw_cv_bar(frame, panel_x, y_offset, "ENV4 (Loop)",
                         env4_val, CV_COLORS_BGR['ENV4'])
        y_offset += line_height

        # SEQ1 (X座標)
        self._draw_cv_bar(frame, panel_x, y_offset, "SEQ1",
                         seq1_val, CV_COLORS_BGR['SEQ1'])
        y_offset += line_height

        # SEQ2 (Y座標)
        self._draw_cv_bar(frame, panel_x, y_offset, "SEQ2",
                         seq2_val, CV_COLORS_BGR['SEQ2'])

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
        # 重新生成 chaos offsets 並重置 LFO 相位
        self._regenerate_lfo()

    def set_range(self, range_pct: float):
        self.range_pct = np.clip(range_pct, 1, 120)
        # 重新生成 chaos offsets 並重置 LFO 相位
        self._regenerate_lfo()

    def set_chaos_ratio(self, ratio: float):
        """Set chaos LFO speed ratio (0.1-1.0)"""
        self.chaos_ratio = np.clip(ratio, 0.1, 1.0)

    def set_scan_time(self, scan_time: float):
        """設定掃描時間（秒）0.1-300s (5 minutes max)"""
        self.scan_time = np.clip(scan_time, 0.1, 300.0)
        # 重新生成 chaos offsets 並重置 LFO 相位
        self._regenerate_lfo()

    def get_contour_length(self) -> float:
        """取得當前輪廓長度（正規化為 0-1）"""
        # 假設最大輪廓長度為畫面寬+高的 2 倍（對角線來回）
        max_length = (self.detection_width + self.detection_height) * 2.0
        if max_length > 0:
            return min(self.contour_length / max_length, 1.0)
        return 0.0

    def get_scan_loop_completed(self) -> bool:
        """取得掃描循環是否完成"""
        return self.scan_loop_completed

    def _generate_modulation_amounts(self) -> np.ndarray:
        """生成 8 個隨機 modulation amount 範圍 0.5 到 1.0"""
        return np.random.uniform(0.5, 1.0, 8).astype(np.float32)

    def _generate_lfo_patterns(self):
        """生成 8 個隨機 LFO pattern

        每個 pattern 可以是:
        - 圓滑 (smooth): sine, triangle, smooth random
        - 跳躍 (stepped): square, random steps, multi-step
        """
        self.lfo_patterns = []

        for i in range(8):
            # 隨機選擇 pattern 類型
            pattern_type = np.random.choice(['sine', 'triangle', 'smooth_random',
                                            'square', 'random_steps', 'multi_step'])

            if pattern_type == 'sine':
                # 圓滑 sine wave
                phase = np.linspace(0, 2 * np.pi, self.pattern_resolution)
                pattern = np.sin(phase)

            elif pattern_type == 'triangle':
                # 圓滑三角波
                phase = np.linspace(0, 1, self.pattern_resolution)
                pattern = 2 * np.abs(2 * (phase - np.floor(phase + 0.5))) - 1

            elif pattern_type == 'smooth_random':
                # 圓滑隨機波形 (使用低通濾波)
                random_points = np.random.uniform(-1, 1, 20)
                # 插值到 100 個點
                x = np.linspace(0, 19, 20)
                x_new = np.linspace(0, 19, self.pattern_resolution)
                pattern = np.interp(x_new, x, random_points)

            elif pattern_type == 'square':
                # 跳躍方波
                phase = np.linspace(0, 1, self.pattern_resolution)
                pattern = np.where(phase < 0.5, 1.0, -1.0)

            elif pattern_type == 'random_steps':
                # 隨機階梯 (2-4 個階梯)
                num_steps = np.random.randint(2, 5)
                step_values = np.random.uniform(-1, 1, num_steps)
                pattern = np.repeat(step_values, self.pattern_resolution // num_steps + 1)[:self.pattern_resolution]

            elif pattern_type == 'multi_step':
                # 多階梯 (8 個階梯)
                step_values = np.random.uniform(-1, 1, 8)
                pattern = np.repeat(step_values, self.pattern_resolution // 8 + 1)[:self.pattern_resolution]

            # 添加些微隨機偏移 (±10%)
            offset = np.random.uniform(-0.1, 0.1)
            pattern = pattern * (1.0 + offset)

            self.lfo_patterns.append(pattern.astype(np.float32))

    def _regenerate_lfo(self):
        """重新生成 LFO patterns, modulation amounts 並重置 LFO 相位"""
        self._generate_lfo_patterns()
        self.modulation_amounts = self._generate_modulation_amounts()
        self.lfo_phase = 0.0

    def _update_lfo(self):
        """更新 LFO Pattern 與 8 個變種訊號

        基於當前掃描進度計算 LFO 相位並從預計算的 pattern 取值
        - LFO 週期 = scan_time / chaos_ratio
        - chaos_ratio: 0.1 (預設) = 1/10 速度, 1.0 = 同速
        - scan_progress (0-1) 對應 LFO 的 chaos_ratio 週期
        - 從預計算的 pattern array 中取值
        """
        # 防禦性檢查：確保 patterns 已經生成
        if len(self.lfo_patterns) != 8:
            self._generate_lfo_patterns()
            return

        # 計算 LFO 相位 (0 到 1，週期由 chaos_ratio 控制)
        self.lfo_phase = (self.scan_progress * self.chaos_ratio) % 1.0

        # 從預計算的 pattern 中取值
        pattern_index = int(self.lfo_phase * (self.pattern_resolution - 1))

        for i in range(8):
            self.lfo_variants[i] = self.lfo_patterns[i][pattern_index]

    def get_lfo_variants(self) -> np.ndarray:
        """取得 8 個 LFO 變種訊號

        Returns:
            8-element array: 變種訊號 0-3 用於 angle, 4-7 用於 curve
            範圍約 -1.1 到 +1.1
        """
        return self.lfo_variants.copy()

    def get_modulation_amounts(self) -> np.ndarray:
        """取得 8 個 modulation amount

        Returns:
            8-element array: modulation amount 0-3 用於 angle, 4-7 用於 curve
            範圍 0.5 到 1.0
        """
        return self.modulation_amounts.copy()
