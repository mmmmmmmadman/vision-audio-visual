"""
邊緣強度 CV 生成測試程式
使用 Sobel 邊緣強度檢測，從基準點水平/垂直掃描找最強邊緣
"""

import cv2
import numpy as np


class EdgeCVTest:
    def __init__(self, camera_id=0):
        # 初始化相機
        self.cap = cv2.VideoCapture(camera_id)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

        # 獲取實際解析度
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # 基準點（百分比 0-100）
        self.anchor_x_pct = 50      # X 軸基準點位置 (%)
        self.anchor_y_pct = 50      # Y 軸基準點位置 (%)

        # Sobel 參數
        self.blur_size = 5          # 高斯模糊核心大小 (1-15, 奇數)
        self.threshold = 50         # 邊緣強度閾值 (0-255)
        self.temporal_alpha = 50    # 時間平滑係數 (0-100)

        # 時間平滑緩衝
        self.previous_gradient = None

        # Sequencer 參數
        self.num_steps_x = 8        # SEQ1 採樣點數 (4-32)
        self.num_steps_y = 8        # SEQ2 採樣點數 (4-32)
        self.clock_rate = 120       # 時鐘速率 BPM (30-240)
        self.current_step_x = 0     # SEQ1 當前步進位置
        self.current_step_y = 0     # SEQ2 當前步進位置
        self.phase = 0.0            # 時鐘相位
        self.samples_per_step = 0   # 每步所需的幀數
        self.update_clock()

        # 採樣範圍參數（從基準點雙向延伸，百分比 0-50）
        self.range = 50             # 範圍（從基準點向四方延伸）

        # Sequence 數值儲存
        self.seq1_values = [0.5] * self.num_steps_x  # SEQ1 (水平掃描)
        self.seq2_values = [0.5] * self.num_steps_y  # SEQ2 (垂直掃描)

        # CV 輸出值（當前步的值）
        self.cv1_value = 0.5        # CV1 (0-1, 對應 0-10V)
        self.cv2_value = 0.5        # CV2 (0-1, 對應 0-10V)

        # 採樣點座標列表（用於視覺化）
        self.sample_points_horizontal = []  # [(x, y), ...]
        self.sample_points_vertical = []    # [(x, y), ...]

        # 控制方框設定
        self.control_box_size = 200
        self.control_box_margin = 20
        self.control_box_x = 0  # 將在 run() 中設定
        self.control_box_y = 0
        self.is_dragging = False  # 是否正在拖曳

        # 建立視窗
        self.window_name = "Edge CV Test"
        cv2.namedWindow(self.window_name)
        cv2.setMouseCallback(self.window_name, self.on_mouse_event)

        # 建立滑桿
        cv2.createTrackbar("Range", self.window_name,
                          self.range, 50, self.on_range_change)
        cv2.createTrackbar("Steps X", self.window_name,
                          self.num_steps_x, 32, self.on_steps_x_change)
        cv2.createTrackbar("Steps Y", self.window_name,
                          self.num_steps_y, 32, self.on_steps_y_change)
        cv2.createTrackbar("BPM", self.window_name,
                          self.clock_rate, 240, self.on_bpm_change)
        cv2.createTrackbar("Blur Size", self.window_name,
                          self.blur_size, 15, self.on_blur_change)
        cv2.createTrackbar("Threshold", self.window_name,
                          self.threshold, 255, self.on_threshold_change)
        cv2.createTrackbar("Smoothing", self.window_name,
                          self.temporal_alpha, 100, self.on_smoothing_change)

    def update_clock(self):
        """更新時鐘計算"""
        # 每步的時間（秒）
        beats_per_second = self.clock_rate / 60.0
        self.step_duration = 1.0 / beats_per_second

    def on_mouse_event(self, event, x, y, flags, param):
        """滑鼠事件處理：在控制方框內拖曳設定基準點"""
        # 檢查是否在控制方框內
        in_control_box = (self.control_box_x <= x <= self.control_box_x + self.control_box_size and
                         self.control_box_y <= y <= self.control_box_y + self.control_box_size)

        if event == cv2.EVENT_LBUTTONDOWN and in_control_box:
            # 開始拖曳
            self.is_dragging = True

        elif event == cv2.EVENT_MOUSEMOVE and self.is_dragging and in_control_box:
            # 拖曳中，持續更新位置
            rel_x = x - self.control_box_x
            rel_y = y - self.control_box_y
            self.anchor_x_pct = int(np.clip(rel_x * 100 / self.control_box_size, 0, 100))
            self.anchor_y_pct = int(np.clip(rel_y * 100 / self.control_box_size, 0, 100))

            # 不需要更新滑桿，因為已移除 Anchor X/Y 滑桿

        elif event == cv2.EVENT_LBUTTONUP:
            # 結束拖曳
            self.is_dragging = False

    def on_anchor_x_change(self, value):
        self.anchor_x_pct = value

    def on_anchor_y_change(self, value):
        self.anchor_y_pct = value

    def on_range_change(self, value):
        self.range = value

    def on_blur_change(self, value):
        # 確保為奇數
        self.blur_size = value if value % 2 == 1 else value + 1
        self.blur_size = max(1, self.blur_size)

    def on_threshold_change(self, value):
        self.threshold = value

    def on_smoothing_change(self, value):
        self.temporal_alpha = value

    def on_steps_x_change(self, value):
        self.num_steps_x = max(4, value)  # 至少 4 步
        self.seq1_values = [0.5] * self.num_steps_x

    def on_steps_y_change(self, value):
        self.num_steps_y = max(4, value)  # 至少 4 步
        self.seq2_values = [0.5] * self.num_steps_y

    def on_bpm_change(self, value):
        self.clock_rate = max(30, value)  # 至少 30 BPM
        self.update_clock()

    def compute_edge_strength(self, gray):
        """使用 Sobel 計算邊緣強度

        Args:
            gray: 灰階影像

        Returns:
            gradient_magnitude: 邊緣強度圖 (0-255)
        """
        # 高斯模糊（降噪）
        if self.blur_size > 1:
            blurred = cv2.GaussianBlur(gray, (self.blur_size, self.blur_size), 0)
        else:
            blurred = gray

        # Sobel 梯度計算（X 和 Y 方向）
        grad_x = cv2.Sobel(blurred, cv2.CV_64F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(blurred, cv2.CV_64F, 0, 1, ksize=3)

        # 計算梯度強度（magnitude）
        gradient_magnitude = np.sqrt(grad_x**2 + grad_y**2)

        # 歸一化到 0-255
        gradient_magnitude = np.uint8(gradient_magnitude / gradient_magnitude.max() * 255)

        # 時間平滑
        if self.previous_gradient is not None and self.temporal_alpha < 100:
            alpha = self.temporal_alpha / 100.0
            gradient_magnitude = cv2.addWeighted(
                gradient_magnitude, alpha,
                self.previous_gradient, 1 - alpha, 0
            )
            gradient_magnitude = gradient_magnitude.astype(np.uint8)

        # 儲存當前梯度供下一幀使用
        self.previous_gradient = gradient_magnitude.copy()

        return gradient_magnitude

    def sample_all_steps(self, gradient):
        """在所有採樣點上進行邊緣檢測，更新 sequence 數值

        Args:
            gradient: 邊緣強度圖
        """
        height, width = gradient.shape

        # 清空採樣點列表
        self.sample_points_horizontal = []
        self.sample_points_vertical = []

        # 計算基準點像素座標
        anchor_x = int(width * self.anchor_x_pct / 100.0)
        anchor_y = int(height * self.anchor_y_pct / 100.0)

        # 計算採樣範圍（從基準點雙向延伸，X和Y使用相同範圍）
        x_range_half = int(width * self.range / 100.0)
        x_start = max(0, anchor_x - x_range_half)
        x_end = min(width, anchor_x + x_range_half)
        x_range = max(1, x_end - x_start)

        y_range_half = int(height * self.range / 100.0)
        y_start = max(0, anchor_y - y_range_half)
        y_end = min(height, anchor_y + y_range_half)
        y_range = max(1, y_end - y_start)

        # SEQ1：在基準點的 Y 座標（水平線）上，X 方向採樣
        for i in range(self.num_steps_x):
            # 計算採樣點的 X 座標（在範圍內）
            sample_x = x_start + int((i + 0.5) * x_range / self.num_steps_x)
            sample_x = min(sample_x, width - 1)

            # 在該 X 座標上，垂直方向（Y軸）搜尋最強邊緣
            vertical_line = gradient[:, sample_x]
            vertical_line = np.where(vertical_line >= self.threshold, vertical_line, 0)

            if vertical_line.max() > 0:
                # 找到最強邊緣的 Y 座標
                edge_y = np.argmax(vertical_line)
            else:
                # 沒有邊緣時使用基準點的 Y 座標
                edge_y = anchor_y

            # 儲存採樣點座標（X在水平線上分布，Y是找到的邊緣位置）
            self.sample_points_horizontal.append((sample_x, edge_y))

            # 更新 sequence 值（邊緣的 Y 座標歸一化到 0-1）
            self.seq1_values[i] = edge_y / height

        # SEQ2：在基準點的 X 座標（垂直線）上，Y 方向採樣
        for i in range(self.num_steps_y):
            # 計算採樣點的 Y 座標（在範圍內）
            sample_y = y_start + int((i + 0.5) * y_range / self.num_steps_y)
            sample_y = min(sample_y, height - 1)

            # 在該 Y 座標上，水平方向（X軸）搜尋最強邊緣
            horizontal_line = gradient[sample_y, :]
            horizontal_line = np.where(horizontal_line >= self.threshold, horizontal_line, 0)

            if horizontal_line.max() > 0:
                # 找到最強邊緣的 X 座標
                edge_x = np.argmax(horizontal_line)
            else:
                # 沒有邊緣時使用基準點的 X 座標
                edge_x = anchor_x

            # 儲存採樣點座標（Y在垂直線上分布，X是找到的邊緣位置）
            self.sample_points_vertical.append((edge_x, sample_y))

            # 更新 sequence 值（邊緣的 X 座標歸一化到 0-1）
            self.seq2_values[i] = edge_x / width

    def update_sequencer(self, dt):
        """更新 sequencer 步進，輸出當前步的 CV 值

        Args:
            dt: 時間間隔（秒）
        """
        # 更新時鐘相位（累積時間）
        self.phase += dt

        # 檢查是否該切換到下一步
        if self.phase >= self.step_duration:
            self.phase -= self.step_duration  # 保留餘數
            # 各自獨立步進
            self.current_step_x = (self.current_step_x + 1) % self.num_steps_x
            self.current_step_y = (self.current_step_y + 1) % self.num_steps_y

        # 輸出當前步的 CV 值
        self.cv1_value = self.seq1_values[self.current_step_x]
        self.cv2_value = self.seq2_values[self.current_step_y]

    def draw_visualization(self, frame, gradient):
        """繪製視覺化結果

        Args:
            frame: 原始畫面（BGR）
            gradient: 邊緣強度圖（灰階）

        Returns:
            display: 視覺化畫面（BGR）
        """
        # 顯示原始相機畫面
        display = frame.copy()

        # 計算基準點
        height, width = display.shape[:2]
        anchor_x = int(width * self.anchor_x_pct / 100.0)
        anchor_y = int(height * self.anchor_y_pct / 100.0)

        # 繪製基準點（白色十字）
        cross_size = 20
        cv2.line(display, (anchor_x - cross_size, anchor_y),
                (anchor_x + cross_size, anchor_y), (255, 255, 255), 2)
        cv2.line(display, (anchor_x, anchor_y - cross_size),
                (anchor_x, anchor_y + cross_size), (255, 255, 255), 2)

        # MUJI 風格配色（BGR 格式）
        color_cv1 = (170, 190, 210)  # 溫暖米褐色
        color_cv2 = (180, 200, 180)  # 自然灰綠色

        # 繪製 SEQ1 描邊曲線（連接所有找到的邊緣點，米褐色，3px）
        if len(self.sample_points_horizontal) > 1:
            points = np.array(self.sample_points_horizontal, dtype=np.int32)
            cv2.polylines(display, [points], False, color_cv1, 3)

            # 標記當前步（空心圈）
            if self.current_step_x < len(self.sample_points_horizontal):
                current_point = self.sample_points_horizontal[self.current_step_x]
                cv2.circle(display, current_point, 8, color_cv1, 2)

        # 繪製 SEQ2 描邊曲線（連接所有找到的邊緣點，灰綠色，3px）
        if len(self.sample_points_vertical) > 1:
            points = np.array(self.sample_points_vertical, dtype=np.int32)
            cv2.polylines(display, [points], False, color_cv2, 3)

            # 標記當前步（空心圈）
            if self.current_step_y < len(self.sample_points_vertical):
                current_point = self.sample_points_vertical[self.current_step_y]
                cv2.circle(display, current_point, 8, color_cv2, 2)

        # 顯示參數資訊（左上角）
        info_y = 30
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.7
        font_thickness = 2
        text_color = (255, 255, 255)

        cv2.putText(display,
                   f"Steps X:{self.num_steps_x} Y:{self.num_steps_y}  BPM:{self.clock_rate}  Current X:{self.current_step_x + 1} Y:{self.current_step_y + 1}",
                   (10, info_y), font, font_scale, text_color, font_thickness)
        cv2.putText(display,
                   f"Anchor: ({self.anchor_x_pct}%, {self.anchor_y_pct}%)  Range: {self.range}%",
                   (10, info_y + 30), font, font_scale, text_color, font_thickness)
        cv2.putText(display,
                   f"Blur: {self.blur_size}  Threshold: {self.threshold}  Smoothing: {self.temporal_alpha}%",
                   (10, info_y + 60), font, font_scale, text_color, font_thickness)

        # 顯示 CV 數值（右上角）
        cv_info_x = self.width - 300
        cv2.putText(display,
                   f"CV1: {self.cv1_value:.3f} ({self.cv1_value * 10:.2f}V)",
                   (cv_info_x, 40), font, font_scale, (255, 255, 255), font_thickness)
        cv2.putText(display,
                   f"CV2: {self.cv2_value:.3f} ({self.cv2_value * 10:.2f}V)",
                   (cv_info_x, 80), font, font_scale, (255, 255, 255), font_thickness)

        # 繪製 CV 條狀圖（右上角）
        bar_x = cv_info_x
        bar_y = 100
        bar_width = 200
        bar_height = 20
        bar_spacing = 30

        # CV1 條狀圖（白色）
        cv2.rectangle(display, (bar_x, bar_y),
                     (bar_x + bar_width, bar_y + bar_height),
                     (100, 100, 100), 1)
        filled_width_1 = int(bar_width * self.cv1_value)
        if filled_width_1 > 0:
            cv2.rectangle(display, (bar_x + 1, bar_y + 1),
                         (bar_x + filled_width_1, bar_y + bar_height - 1),
                         (255, 255, 255), -1)

        # CV2 條狀圖（白色）
        bar_y += bar_spacing
        cv2.rectangle(display, (bar_x, bar_y),
                     (bar_x + bar_width, bar_y + bar_height),
                     (100, 100, 100), 1)
        filled_width_2 = int(bar_width * self.cv2_value)
        if filled_width_2 > 0:
            cv2.rectangle(display, (bar_x + 1, bar_y + 1),
                         (bar_x + filled_width_2, bar_y + bar_height - 1),
                         (255, 255, 255), -1)

        # 繪製控制方框（右下角）
        box_x = width - self.control_box_size - self.control_box_margin
        box_y = height - self.control_box_size - self.control_box_margin
        self.control_box_x = box_x
        self.control_box_y = box_y

        # 方框背景（半透明深灰色）
        overlay = display.copy()
        cv2.rectangle(overlay, (box_x, box_y),
                     (box_x + self.control_box_size, box_y + self.control_box_size),
                     (40, 40, 40), -1)
        cv2.addWeighted(overlay, 0.7, display, 0.3, 0, display)

        # 方框邊框（白色）
        cv2.rectangle(display, (box_x, box_y),
                     (box_x + self.control_box_size, box_y + self.control_box_size),
                     (255, 255, 255), 2)

        # 在方框內顯示當前基準點位置（白色圓點）
        anchor_in_box_x = box_x + int(self.anchor_x_pct * self.control_box_size / 100)
        anchor_in_box_y = box_y + int(self.anchor_y_pct * self.control_box_size / 100)
        cv2.circle(display, (anchor_in_box_x, anchor_in_box_y), 6, (255, 255, 255), -1)

        # 方框標籤
        cv2.putText(display, "Anchor Control",
                   (box_x + 5, box_y + 20), font, 0.5, (255, 255, 255), 1)

        # 顯示使用說明（左下角）
        help_y = self.height - 80
        help_font_scale = 0.6
        cv2.putText(display, "White curves: Edge detection  |  Hollow circle: Current step  |  Drag control box to set anchor",
                   (10, help_y), font, help_font_scale, (255, 255, 0), 1)
        cv2.putText(display, "'q' or ESC: Exit  |  's': Save Frame",
                   (10, help_y + 25), font, help_font_scale, (255, 255, 0), 1)

        return display

    def run(self):
        """運行主循環"""
        print("=== Edge CV Sequencer Test ===")
        print("功能說明：")
        print("  - SEQ1（綠色）：水平方向採樣，在每個垂直線上找最強邊緣")
        print("  - SEQ2（藍色）：垂直方向採樣，在每個水平線上找最強邊緣")
        print("  - 按照 BPM 時鐘自動步進")
        print()
        print("參數調整：")
        print("  - Steps: 採樣點數（4-32 步）")
        print("  - BPM: 時鐘速率（30-240 BPM）")
        print("  - Blur Size: 高斯模糊核心大小（降噪）")
        print("  - Threshold: 邊緣強度閾值（過濾弱邊緣）")
        print("  - Smoothing: 時間平滑（0=最平滑, 100=無平滑）")
        print()
        print("控制：")
        print("  - 按 'q' 或 ESC 退出")
        print("  - 按 's' 儲存當前畫面")
        print()

        frame_count = 0
        import time
        last_time = time.time()

        while True:
            ret, frame = self.cap.read()
            if not ret:
                print("無法讀取畫面")
                break

            frame_count += 1

            # 計算時間間隔
            current_time = time.time()
            dt = current_time - last_time
            last_time = current_time

            # 轉換為灰階
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # 計算邊緣強度
            gradient = self.compute_edge_strength(gray)

            # 在所有採樣點上進行邊緣檢測，更新 sequence
            self.sample_all_steps(gradient)

            # 更新 sequencer 步進，輸出當前步的 CV 值
            self.update_sequencer(dt)

            # 繪製視覺化
            display = self.draw_visualization(frame, gradient)

            # 顯示結果
            cv2.imshow(self.window_name, display)

            # 處理按鍵
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:  # 'q' 或 ESC
                break
            elif key == ord('s'):  # 儲存畫面
                filename = f"edge_cv_test_{frame_count:04d}.png"
                cv2.imwrite(filename, display)
                print(f"已儲存: {filename}")

        # 清理
        self.cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    # 執行測試
    # camera_id: 0=內建攝影機, 1=外接攝影機
    test = EdgeCVTest(camera_id=0)
    test.run()
