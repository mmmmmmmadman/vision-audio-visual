"""
Contour-based CV generator
從輪廓檢測生成 3 個 Envelope CV
"""

import cv2
import numpy as np
from typing import List, Tuple
from ..utils.cv_colors import CV_COLORS_BGR


class ContourCVGenerator:
    """
    使用邊緣檢測從畫面生成 CV

    SEQ1/SEQ2: 基於 Sobel 邊緣檢測的序列 CV (0-10V)
    ENV1: SEQ1 > 5V 時觸發（粉色）
    ENV2: SEQ2 > 5V 時觸發（白色）
    ENV3: SEQ1 ≤ 5V 且 SEQ2 ≤ 5V 時觸發（紅色）
    """

    def __init__(self):
        """初始化輪廓 CV 生成器"""
        # Canny edge detection 參數（保留用於視覺化 Contour 邊緣）
        self.threshold = 100  # 統一閾值 (0-255)
        self.temporal_alpha = 50  # 時間平滑係數 (0-100)
        self.previous_edges = None  # 時間平滑緩衝

        # 新 SEQ CV 參數（基於邊緣檢測）
        self.anchor_x_pct = 50  # 錨點 X 位置 (0-100%)
        self.anchor_y_pct = 50  # 錨點 Y 位置 (0-100%)
        self.range_pct = 50  # 雙向延伸範圍 (0-50%)
        self.num_steps_x = 8  # SEQ1 採樣點數量
        self.num_steps_y = 8  # SEQ2 採樣點數量
        self.edge_threshold = 50  # Sobel 邊緣強度閾值 (0-255)

        # SEQ CV 輸出值
        self.seq1_value = 0.0  # SEQ1 當前值 (0-1)
        self.seq2_value = 0.0  # SEQ2 當前值 (0-1)

        # SEQ sequencer 狀態
        self.current_step_x = 0  # SEQ1 當前步數
        self.current_step_y = 0  # SEQ2 當前步數
        self.seq1_values = np.zeros(32, dtype=np.float32)  # SEQ1 序列值（最多32步）
        self.seq2_values = np.zeros(32, dtype=np.float32)  # SEQ2 序列值（最多32步）

        # 步進變化標記（供 sequential switch 使用）
        self.seq1_step_changed = False
        self.seq2_step_changed = False

        # SEQ 統一時鐘參數
        self.clock_rate = 120  # 統一 BPM (SEQ1 和 SEQ2 共用)
        self.step_timer = 0.0  # 統一步進計時器

        # 邊緣檢測結果（用於視覺化）
        self.sample_points_horizontal = []  # SEQ1 採樣點 [(x, y), ...]
        self.sample_points_vertical = []  # SEQ2 採樣點 [(x, y), ...]
        self.sobel_gradient = None  # Sobel 梯度圖（用於視覺化）

        # 觸發光圈列表（用於 ENV）
        self.trigger_rings = []

        # 觸發位置記錄（用於視覺化）
        self.last_trigger_positions = {
            'env1': None,  # (x, y, color)
            'env2': None,
            'env3': None
        }

    def update_sequencer_and_triggers(self, dt: float, width: int, height: int, envelopes):
        """更新 SEQ 步進並檢查 ENV 觸發

        Args:
            dt: 時間間隔（秒）
            width: 畫面寬度
            height: 畫面高度
            envelopes: envelope 列表 [env1, env2, env3]
        """

        # 統一時鐘步進邏輯（SEQ1 和 SEQ2 同步）
        self.step_timer += dt
        step_interval = 60.0 / self.clock_rate if self.clock_rate > 0 else 0.5

        # 重置步進標記
        self.seq1_step_changed = False
        self.seq2_step_changed = False

        if self.step_timer >= step_interval:
            self.step_timer = 0.0
            # 同步步進
            self.current_step_x = (self.current_step_x + 1) % self.num_steps_x
            self.current_step_y = (self.current_step_y + 1) % self.num_steps_y

            # 讀取當前步的值（0-1）
            self.seq1_value = self.seq1_values[self.current_step_x]
            self.seq2_value = self.seq2_values[self.current_step_y]

            # 設置步進變化標記
            self.seq1_step_changed = True
            self.seq2_step_changed = True

            # 轉換為電壓（0-10V）
            seq1_voltage = self.seq1_value * 10.0
            seq2_voltage = self.seq2_value * 10.0

            # 新的觸發邏輯：ENV1/2 競爭 + ENV3 獨立條件
            # ENV1 vs ENV2: 比較兩個 sequencer 的電壓，較高者觸發
            if seq1_voltage > seq2_voltage:
                # ENV1 觸發：SEQ1 電壓較高，在 SEQ1 當前步位置
                if self.current_step_x < len(self.sample_points_horizontal):
                    trigger_pos = self.sample_points_horizontal[self.current_step_x]
                    envelopes[0].trigger()
                    self.trigger_rings.append({
                        'pos': trigger_pos,
                        'radius': 30,
                        'alpha': 1.0,
                        'color': CV_COLORS_BGR['ENV1'],  # Light Vermillion (淡朱)
                        'decay_time': envelopes[0].decay_time  # 儲存 ENV1 decay 時間
                    })
                    self.last_trigger_positions['env1'] = (trigger_pos[0], trigger_pos[1], CV_COLORS_BGR['ENV1'])
            else:
                # ENV2 觸發：SEQ2 電壓較高（或相等），在 SEQ2 當前步位置
                if self.current_step_y < len(self.sample_points_vertical):
                    trigger_pos = self.sample_points_vertical[self.current_step_y]
                    envelopes[1].trigger()
                    self.trigger_rings.append({
                        'pos': trigger_pos,
                        'radius': 30,
                        'alpha': 1.0,
                        'color': CV_COLORS_BGR['ENV2'],  # Silver White (銀白)
                        'decay_time': envelopes[1].decay_time  # 儲存 ENV2 decay 時間
                    })
                    self.last_trigger_positions['env2'] = (trigger_pos[0], trigger_pos[1], CV_COLORS_BGR['ENV2'])

            # ENV3: 獨立條件 - 兩者電壓都低於 5V 時觸發
            if seq1_voltage < 5.0 and seq2_voltage < 5.0:
                # ENV3 觸發：在錨點位置
                anchor_x = int(self.anchor_x_pct * width / 100.0)
                anchor_y = int(self.anchor_y_pct * height / 100.0)
                envelopes[2].trigger()
                self.trigger_rings.append({
                    'pos': (anchor_x, anchor_y),
                    'radius': 30,
                    'alpha': 1.0,
                    'color': CV_COLORS_BGR['ENV3'],  # Deep Crimson (深紅)
                    'decay_time': envelopes[2].decay_time  # 儲存 ENV3 decay 時間
                })
                self.last_trigger_positions['env3'] = (anchor_x, anchor_y, CV_COLORS_BGR['ENV3'])

    def detect_contours(self, gray: np.ndarray) -> Tuple[List, np.ndarray]:
        """檢測輪廓並返回輪廓列表和邊緣圖

        Args:
            gray: 灰階畫面

        Returns:
            (contours, edges): 輪廓列表和邊緣圖
        """
        # 高斯模糊（固定強度，減少雜訊）
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Canny 邊緣檢測（使用統一閾值）
        low_threshold = int(self.threshold * 0.5)
        high_threshold = self.threshold
        edges = cv2.Canny(blurred, low_threshold, high_threshold)

        # 時間平滑（移動平均）
        if self.previous_edges is not None and self.temporal_alpha < 100:
            alpha = self.temporal_alpha / 100.0
            edges = cv2.addWeighted(edges, alpha, self.previous_edges, 1 - alpha, 0)
            edges = edges.astype(np.uint8)

        # 儲存當前邊緣供下一幀使用
        self.previous_edges = edges.copy()

        # 尋找輪廓
        contours, hierarchy = cv2.findContours(
            edges,
            cv2.RETR_EXTERNAL,  # 只檢測外部輪廓
            cv2.CHAIN_APPROX_SIMPLE  # 壓縮輪廓
        )

        return contours, edges

    def detect_edges_sobel(self, gray: np.ndarray) -> np.ndarray:
        """使用 Sobel 算子檢測邊緣（用於 SEQ CV 生成）

        Args:
            gray: 灰階畫面

        Returns:
            gradient: 邊緣強度圖（0-255）
        """
        # Sobel X 和 Y 方向梯度
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)

        # 計算梯度強度
        gradient = np.sqrt(sobelx**2 + sobely**2)
        gradient = np.clip(gradient, 0, 255).astype(np.uint8)

        # 儲存用於視覺化
        self.sobel_gradient = gradient

        return gradient

    def sample_edge_sequences(self, gray: np.ndarray):
        """從邊緣檢測採樣生成 SEQ1/SEQ2 序列值

        Args:
            gray: 灰階畫面
        """
        height, width = gray.shape

        # Sobel 邊緣檢測
        gradient = self.detect_edges_sobel(gray)

        # 計算錨點位置
        anchor_x = int(self.anchor_x_pct * width / 100.0)
        anchor_y = int(self.anchor_y_pct * height / 100.0)

        # 計算延伸範圍
        range_x = int(self.range_pct * width / 100.0)
        range_y = int(self.range_pct * height / 100.0)

        # SEQ1: 水平線採樣，垂直方向搜尋邊緣
        x_start = max(0, anchor_x - range_x)
        x_end = min(width, anchor_x + range_x)
        x_range = x_end - x_start

        self.sample_points_horizontal = []
        for i in range(self.num_steps_x):
            # 計算採樣點的 X 座標
            sample_x = x_start + int((i + 0.5) * x_range / self.num_steps_x)
            sample_x = np.clip(sample_x, 0, width - 1)

            # 在垂直方向搜尋最強邊緣
            vertical_line = gradient[:, sample_x]
            vertical_line = np.where(vertical_line >= self.edge_threshold, vertical_line, 0)

            if vertical_line.max() > 0:
                edge_y = np.argmax(vertical_line)
            else:
                edge_y = anchor_y

            edge_y = np.clip(edge_y, 0, height - 1)
            self.sample_points_horizontal.append((sample_x, edge_y))
            self.seq1_values[i] = edge_y / height

        # SEQ2: 垂直線採樣，水平方向搜尋邊緣
        y_start = max(0, anchor_y - range_y)
        y_end = min(height, anchor_y + range_y)
        y_range = y_end - y_start

        self.sample_points_vertical = []
        for i in range(self.num_steps_y):
            # 計算採樣點的 Y 座標
            sample_y = y_start + int((i + 0.5) * y_range / self.num_steps_y)
            sample_y = np.clip(sample_y, 0, height - 1)

            # 在水平方向搜尋最強邊緣
            horizontal_line = gradient[sample_y, :]
            horizontal_line = np.where(horizontal_line >= self.edge_threshold, horizontal_line, 0)

            if horizontal_line.max() > 0:
                edge_x = np.argmax(horizontal_line)
            else:
                edge_x = anchor_x

            edge_x = np.clip(edge_x, 0, width - 1)
            self.sample_points_vertical.append((edge_x, sample_y))
            self.seq2_values[i] = edge_x / width

    def update_trigger_rings(self):
        """更新觸發光圈動畫（同步於 ENV decay 時間）"""
        new_rings = []
        for ring in self.trigger_rings:
            # 擴展半徑（三倍速度：6 像素/幀 @ 60 FPS）
            ring['radius'] += 6

            # 淡出：根據 ENV decay 時間計算 alpha 遞減速率
            # 假設視訊線程運行於 60 FPS
            # alpha_decrement = 1.0 / (decay_time * 60 FPS)
            fps = 60.0
            decay_time = ring.get('decay_time', 1.0)  # 默認 1 秒
            alpha_decrement = 1.0 / (decay_time * fps)
            ring['alpha'] -= alpha_decrement

            # 保留尚未完全消失的光圈（三倍最大半徑：180 像素）
            if ring['alpha'] > 0 and ring['radius'] < 180:
                new_rings.append(ring)

        self.trigger_rings = new_rings

    def set_threshold(self, threshold: int):
        """設定 Canny 閾值"""
        self.threshold = np.clip(threshold, 0, 255)

    def set_smoothing(self, smoothing: int):
        """設定時間平滑係數 (0-100)"""
        self.temporal_alpha = np.clip(smoothing, 0, 100)

    def set_anchor_position(self, x_pct: float, y_pct: float):
        """設定錨點位置

        Args:
            x_pct: X 位置百分比 (0-100)
            y_pct: Y 位置百分比 (0-100)
        """
        self.anchor_x_pct = np.clip(x_pct, 0, 100)
        self.anchor_y_pct = np.clip(y_pct, 0, 100)

    def set_range(self, range_pct: float):
        """設定延伸範圍

        Args:
            range_pct: 範圍百分比 (0-50)
        """
        self.range_pct = np.clip(range_pct, 0, 50)

    def set_num_steps_x(self, steps: int):
        """設定 SEQ1 採樣點數量 (1-32)"""
        self.num_steps_x = np.clip(steps, 1, 32)
        # 重置步進計數器如果超出範圍
        if self.current_step_x >= self.num_steps_x:
            self.current_step_x = 0

    def set_num_steps_y(self, steps: int):
        """設定 SEQ2 採樣點數量 (1-32)"""
        self.num_steps_y = np.clip(steps, 1, 32)
        # 重置步進計數器如果超出範圍
        if self.current_step_y >= self.num_steps_y:
            self.current_step_y = 0

    def set_clock_rate(self, bpm: float):
        """設定統一時鐘速度 (BPM, 1-999) - SEQ1 和 SEQ2 同步"""
        self.clock_rate = np.clip(bpm, 1.0, 999.0)

    def set_edge_threshold(self, threshold: int):
        """設定 Sobel 邊緣強度閾值 (0-255)"""
        self.edge_threshold = np.clip(threshold, 0, 255)


    def draw_overlay(self, frame: np.ndarray, edges: np.ndarray, envelopes=None) -> np.ndarray:
        """繪製掃描線、邊緣、觸發光圈和數據儀表板到畫面上

        Args:
            frame: 原始畫面（BGR）
            edges: 邊緣檢測結果（灰階）
            envelopes: envelope 列表 [env1, env2, env3]（可選，用於數據面板）

        Returns:
            疊加後的畫面（BGR）
        """
        height, width = frame.shape[:2]
        output = frame.copy()

        # 邊緣檢測視覺化已停用（保留功能性邊緣檢測用於 SEQ1/2）
        # # 疊加邊緣檢測結果（白色半透明，3倍粗）
        # # 使用 dilate 將邊緣加粗3倍
        # kernel = np.ones((3, 3), np.uint8)
        # edges_thick = cv2.dilate(edges, kernel, iterations=2)  # 2次迭代約3倍粗
        #
        # edges_bgr = cv2.cvtColor(edges_thick, cv2.COLOR_GRAY2BGR)
        # mask = edges_thick > 0
        #
        # # 只在有邊緣時才疊加（避免空陣列導致崩潰）
        # if np.any(mask):
        #     output[mask] = cv2.addWeighted(output[mask], 0.7, edges_bgr[mask], 0.3, 0)

        # 繪製 SEQ 邊緣曲線（與 ENV 配色一致）
        color_seq1 = CV_COLORS_BGR['SEQ1']  # Flame Vermillion (炎朱) - MOST VIVID
        color_seq2 = CV_COLORS_BGR['SEQ2']  # Snow White (雪白) - PURE white

        # SEQ1 邊緣曲線（水平採樣，垂直搜尋）- Sample/Hold 階梯式線條
        if len(self.sample_points_horizontal) > 1:
            points = self.sample_points_horizontal
            # 繪製階梯式線條（水平 → 垂直）
            for i in range(len(points) - 1):
                x1, y1 = points[i]
                x2, y2 = points[i + 1]
                # 先畫水平線（保持前一點的 Y 值）
                cv2.line(output, (x1, y1), (x2, y1), color_seq1, 1)
                # 再畫垂直線（到達下一點的 Y 值）
                cv2.line(output, (x2, y1), (x2, y2), color_seq1, 1)

            # 繪製當前步的空心正方形（放大三倍：8 → 24，邊長 = 半徑 * 2）
            if self.current_step_x < len(self.sample_points_horizontal):
                current_point = self.sample_points_horizontal[self.current_step_x]
                half_size = 24
                cv2.rectangle(output,
                            (current_point[0] - half_size, current_point[1] - half_size),
                            (current_point[0] + half_size, current_point[1] + half_size),
                            color_seq1, 1)

        # SEQ2 邊緣曲線（垂直採樣，水平搜尋）- Sample/Hold 階梯式線條
        if len(self.sample_points_vertical) > 1:
            points = self.sample_points_vertical
            # 繪製階梯式線條（垂直 → 水平）
            for i in range(len(points) - 1):
                x1, y1 = points[i]
                x2, y2 = points[i + 1]
                # 先畫垂直線（保持前一點的 X 值）
                cv2.line(output, (x1, y1), (x1, y2), color_seq2, 1)
                # 再畫水平線（到達下一點的 X 值）
                cv2.line(output, (x1, y2), (x2, y2), color_seq2, 1)

            # 繪製當前步的空心正方形（放大三倍：8 → 24，邊長 = 半徑 * 2）
            if self.current_step_y < len(self.sample_points_vertical):
                current_point = self.sample_points_vertical[self.current_step_y]
                half_size = 24
                cv2.rectangle(output,
                            (current_point[0] - half_size, current_point[1] - half_size),
                            (current_point[0] + half_size, current_point[1] + half_size),
                            color_seq2, 1)

        # 繪製觸發光圈（ENV）
        for ring in self.trigger_rings:
            pos = ring['pos']
            radius = int(ring['radius'])
            alpha = ring['alpha']
            color = ring['color']

            if alpha > 0:
                # 繪製光圈（使用 alpha 混合）
                overlay = output.copy()
                cv2.circle(overlay, pos, radius, color, 1)
                cv2.addWeighted(overlay, alpha, output, 1 - alpha, 0, output)

        # 繪製 Anchor 粉白圓圈（與 2D 操作畫面相同設計）
        height, width = output.shape[:2]
        anchor_x = int(self.anchor_x_pct * width / 100.0)
        # Y 軸反轉：2D 控制上方=主視覺上方
        anchor_y = int((100.0 - self.anchor_y_pct) * height / 100.0)

        # 外圈白色
        cv2.circle(output, (anchor_x, anchor_y), 6, (255, 255, 255), 2)
        # 內圈粉色填充（與 2D 操作畫面相同的粉白色）
        overlay = output.copy()
        cv2.circle(overlay, (anchor_x, anchor_y), 6, (255, 133, 133, 200), -1)
        cv2.addWeighted(overlay, 0.8, output, 0.2, 0, output)
        # 內圈白色邊框
        cv2.circle(output, (anchor_x, anchor_y), 3, (255, 255, 255), 1)

        # 繪製 CV 數據儀表板（左上角）
        self._draw_data_dashboard(output, envelopes)

        return output

    def _draw_data_dashboard(self, frame: np.ndarray, envelopes=None):
        """繪製即時數據儀表板（左上角）

        Args:
            frame: 輸出畫面（BGR）
            envelopes: envelope 列表（可選）
        """
        # 面板參數
        panel_x = 10
        panel_y = 10
        panel_width = 280
        line_height = 28
        padding = 12

        # 半透明背景
        overlay = frame.copy()
        bg_color = (40, 40, 40)  # 深灰色

        # 計算面板高度（動態根據內容）
        num_lines = 7  # SEQ1 + SEQ2 + X/Y nodes + 3 ENV（移除標題）
        panel_height = padding * 2 + line_height * num_lines

        cv2.rectangle(overlay, (panel_x, panel_y),
                     (panel_x + panel_width, panel_y + panel_height),
                     bg_color, -1)
        cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

        # 面板邊框
        border_color = (100, 100, 100)
        cv2.rectangle(frame, (panel_x, panel_y),
                     (panel_x + panel_width, panel_y + panel_height),
                     border_color, 1)

        # 文字參數
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        font_thickness = 1
        text_color = (140, 140, 140)  # 統一灰色
        seq_value_color = (255, 255, 255)  # SEQ 數值用白色

        y_offset = panel_y + padding + 15

        # 統一 BPM 顯示（居中）
        bpm_text = f"Clock: {self.clock_rate:.0f} BPM"
        cv2.putText(frame, bpm_text,
                   (panel_x + padding, y_offset),
                   font, font_scale, seq_value_color, font_thickness)
        y_offset += line_height

        # SEQ1 長條（Flame Vermillion 炎朱 - MOST VIVID）
        seq1_ratio = self.seq1_value
        cv2.putText(frame, f"SEQ1:",
                   (panel_x + padding, y_offset),
                   font, font_scale, CV_COLORS_BGR['SEQ1'], font_thickness)
        # 電壓顯示
        voltage_text = f"{seq1_ratio * 10.0:.1f}V"
        cv2.putText(frame, voltage_text, (panel_x + 220, y_offset),
                   font, font_scale - 0.05, CV_COLORS_BGR['SEQ1'], font_thickness)

        # SEQ1 條狀圖（Flame Vermillion）
        bar_x = panel_x + 80
        bar_y = y_offset - 12
        bar_width = 130
        bar_height = 12
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height),
                     (80, 80, 80), 1)
        filled_width = int(bar_width * seq1_ratio)
        if filled_width > 0:
            cv2.rectangle(frame, (bar_x + 1, bar_y + 1),
                         (bar_x + filled_width, bar_y + bar_height - 1),
                         CV_COLORS_BGR['SEQ1'], -1)
        y_offset += line_height

        # SEQ2 長條（Snow White 雪白 - PURE white）
        seq2_ratio = self.seq2_value
        cv2.putText(frame, f"SEQ2:",
                   (panel_x + padding, y_offset),
                   font, font_scale, CV_COLORS_BGR['SEQ2'], font_thickness)
        voltage_text = f"{seq2_ratio * 10.0:.1f}V"
        cv2.putText(frame, voltage_text, (panel_x + 220, y_offset),
                   font, font_scale - 0.05, CV_COLORS_BGR['SEQ2'], font_thickness)

        # SEQ2 條狀圖（Snow White）
        bar_y = y_offset - 12
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height),
                     (80, 80, 80), 1)
        filled_width = int(bar_width * seq2_ratio)
        if filled_width > 0:
            cv2.rectangle(frame, (bar_x + 1, bar_y + 1),
                         (bar_x + filled_width, bar_y + bar_height - 1),
                         CV_COLORS_BGR['SEQ2'], -1)
        y_offset += line_height + 5

        # Envelope 數據（如果提供）
        if envelopes and len(envelopes) >= 3:
            env_colors = [CV_COLORS_BGR['ENV1'], CV_COLORS_BGR['ENV2'], CV_COLORS_BGR['ENV3']]
            env_names = ["ENV1", "ENV2", "ENV3"]

            for i, (env, name, color) in enumerate(zip(envelopes, env_names, env_colors)):
                env_value = env.value if hasattr(env, 'value') else 0.0

                # Envelope 名稱和數值
                cv2.putText(frame, f"{name}:", (panel_x + padding, y_offset),
                           font, font_scale, text_color, font_thickness)

                # 繪製 Envelope 條狀圖
                env_bar_x = panel_x + 80
                env_bar_y = y_offset - 12
                env_bar_width = 130
                env_bar_height = 12

                cv2.rectangle(frame, (env_bar_x, env_bar_y),
                             (env_bar_x + env_bar_width, env_bar_y + env_bar_height),
                             (80, 80, 80), 1)

                filled_width = int(env_bar_width * env_value)
                if filled_width > 0:
                    cv2.rectangle(frame, (env_bar_x + 1, env_bar_y + 1),
                                 (env_bar_x + filled_width, env_bar_y + env_bar_height - 1),
                                 color, -1)

                # 數值顯示（灰色）
                value_text = f"{env_value:.2f}"
                cv2.putText(frame, value_text, (panel_x + 220, y_offset),
                           font, font_scale - 0.05, text_color, font_thickness)

                y_offset += line_height
