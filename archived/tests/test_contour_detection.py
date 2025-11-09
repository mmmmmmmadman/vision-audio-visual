"""
輪廓檢測測試程式
使用門檻參數調整輪廓點的數量和顯著性
"""

import cv2
import numpy as np


class DecayEnvelope:
    """Exponential decay envelope generator"""

    def __init__(self, decay_time: float = 1.0, sample_rate: int = 30):
        self.decay_time = decay_time  # seconds
        self.sample_rate = sample_rate  # fps
        self.decay_coeff = 0.0
        self.value = 0.0
        self.is_active = False
        self.update_decay_coeff()

    def update_decay_coeff(self):
        """Calculate decay coefficient from decay time"""
        # Exponential decay: v(t) = e^(-t/tau)
        self.decay_coeff = np.exp(-1.0 / (self.decay_time * self.sample_rate))

    def trigger(self):
        """Trigger envelope"""
        self.value = 1.0
        self.is_active = True

    def process(self) -> float:
        """Generate next sample"""
        if self.is_active:
            self.value *= self.decay_coeff

            # Stop when value is very small
            if self.value < 0.001:
                self.value = 0.0
                self.is_active = False

        return self.value

    def set_decay_time(self, time: float):
        """Set decay time in seconds"""
        self.decay_time = np.clip(time, 0.01, 10.0)
        self.update_decay_coeff()


class ContourDetectionTest:
    def __init__(self, camera_id=0):
        # 初始化相機
        self.cap = cv2.VideoCapture(camera_id)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

        # 輪廓檢測參數
        self.threshold = 100         # 統一閾值 (0-255)
        self.temporal_alpha = 50     # 時間平滑係數 (0-100, 100=無平滑)
        self.scan_speed_x = 50       # X軸掃描速度 (1-100, 越大越快)
        self.scan_speed_y = 50       # Y軸掃描速度 (1-100, 越大越快)
        self.decay_time = 100        # Envelope decay time (10-1000, 映射到 0.1-10.0秒)

        # 時間平滑緩衝
        self.previous_edges = None

        # 掃描線狀態
        self.scan_x = 0              # X軸掃描線位置 (0-1)
        self.scan_y = 0              # Y軸掃描線位置 (0-1)

        # Envelope 生成器（30fps）
        self.envelopes = [
            DecayEnvelope(decay_time=1.0, sample_rate=30),
            DecayEnvelope(decay_time=1.0, sample_rate=30),
            DecayEnvelope(decay_time=1.0, sample_rate=30),
        ]

        # 節點數追蹤（用於 edge trigger）
        self.prev_x_nodes = 0
        self.prev_y_nodes = 0

        # 觸發光圈列表 (position, radius, alpha)
        self.trigger_rings = []

        # 建立視窗
        self.window_name = "Contour Detection Test"
        cv2.namedWindow(self.window_name)

        # 建立滑桿
        cv2.createTrackbar("Threshold", self.window_name,
                          self.threshold, 255, self.on_threshold_change)
        cv2.createTrackbar("Smoothing", self.window_name,
                          self.temporal_alpha, 100, self.on_smoothing_change)
        cv2.createTrackbar("X Speed", self.window_name,
                          self.scan_speed_x, 100, self.on_x_speed_change)
        cv2.createTrackbar("Y Speed", self.window_name,
                          self.scan_speed_y, 100, self.on_y_speed_change)
        cv2.createTrackbar("Decay", self.window_name,
                          self.decay_time, 1000, self.on_decay_change)

    def on_threshold_change(self, value):
        self.threshold = value

    def on_smoothing_change(self, value):
        self.temporal_alpha = value

    def on_x_speed_change(self, value):
        self.scan_speed_x = max(1, value)  # 至少為1

    def on_y_speed_change(self, value):
        self.scan_speed_y = max(1, value)  # 至少為1

    def on_decay_change(self, value):
        self.decay_time = max(10, value)  # 至少為10
        # 更新所有 envelope 的 decay time
        decay_seconds = self.decay_time / 100.0  # 10-1000 → 0.1-10.0秒
        for env in self.envelopes:
            env.set_decay_time(decay_seconds)

    def detect_contours(self, frame):
        """檢測輪廓並返回輪廓點"""
        # 轉換為灰階
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 高斯模糊（固定強度，減少雜訊）
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Canny 邊緣檢測（使用統一閾值）
        # threshold 作為高閾值，低閾值為 threshold * 0.5
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

    def count_scan_intersections(self, contours, scan_pos, axis, width, height, tolerance=5):
        """計算掃描線經過的節點數量

        Args:
            contours: 輪廓列表
            scan_pos: 掃描位置 (0-1)
            axis: 'x' 或 'y'
            width: 畫面寬度
            height: 畫面高度
            tolerance: 容差範圍（像素）
        """
        count = 0

        if axis == 'x':
            # 垂直掃描線（X軸）
            scan_pixel = int(scan_pos * width)
            for contour in contours:
                epsilon = 0.01 * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)
                for point in approx:
                    x, y = point[0]
                    if abs(x - scan_pixel) <= tolerance:
                        count += 1
        else:
            # 水平掃描線（Y軸）
            scan_pixel = int(scan_pos * height)
            for contour in contours:
                epsilon = 0.01 * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)
                for point in approx:
                    x, y = point[0]
                    if abs(y - scan_pixel) <= tolerance:
                        count += 1

        return count

    def find_densest_region(self, coordinates, axis_size, bin_size=50):
        """找出座標最密集的區域

        Args:
            coordinates: 座標列表
            axis_size: 軸的總長度（寬或高）
            bin_size: 分段大小（像素）

        Returns:
            最密集區域的中心座標
        """
        if len(coordinates) == 0:
            return axis_size // 2  # 無節點時返回中心

        # 建立直方圖
        num_bins = max(1, axis_size // bin_size)
        hist = [0] * num_bins

        for coord in coordinates:
            bin_idx = min(int(coord / bin_size), num_bins - 1)
            hist[bin_idx] += 1

        # 找出最密集的 bin
        max_count = max(hist)
        densest_bin = hist.index(max_count)

        # 返回該 bin 的中心座標
        center = int((densest_bin + 0.5) * bin_size)
        return min(center, axis_size - 1)

    def check_triggers(self, edges, contours, x_nodes, y_nodes, scan_x_pixel, scan_y_pixel, width, height):
        """檢查並觸發 envelope（不做 retrigger）"""

        # ENV1: XY 交叉點碰到白線（粉色光圈 #FF8585）
        if not self.envelopes[0].is_active:
            # 檢查交叉點位置的邊緣值
            if 0 <= scan_x_pixel < width and 0 <= scan_y_pixel < height:
                if edges[scan_y_pixel, scan_x_pixel] > 0:
                    print(f"ENV1 TRIGGER! 交叉點碰到輪廓")
                    self.envelopes[0].trigger()
                    self.trigger_rings.append({
                        'pos': (scan_x_pixel, scan_y_pixel),
                        'radius': 10,
                        'alpha': 1.0,
                        'color': (133, 133, 255)  # 粉色 #FF8585 (BGR)
                    })

        # ENV2: X軸節點數 > Y軸節點數（白色光圈，在 X 軸掃描線的最密集處）
        if not self.envelopes[1].is_active:
            if x_nodes > y_nodes and x_nodes > 0:
                # 收集 X 軸掃描線上所有節點的 Y 座標
                y_coords = []
                tolerance = 5
                for contour in contours:
                    epsilon = 0.01 * cv2.arcLength(contour, True)
                    approx = cv2.approxPolyDP(contour, epsilon, True)
                    for point in approx:
                        x, y = point[0]
                        if abs(x - scan_x_pixel) <= tolerance:
                            y_coords.append(y)

                # 找出最密集的 Y 位置
                densest_y = self.find_densest_region(y_coords, height)

                print(f"ENV2 TRIGGER! X節點({x_nodes}) > Y節點({y_nodes}), 密集處 Y={densest_y}")
                self.envelopes[1].trigger()
                self.trigger_rings.append({
                    'pos': (scan_x_pixel, densest_y),
                    'radius': 10,
                    'alpha': 1.0,
                    'color': (255, 255, 255)  # 白色 (BGR)
                })

        # ENV3: Y軸節點數 > X軸節點數（日本國旗紅色光圈 #BC002D，在 Y 軸掃描線的最密集處）
        if not self.envelopes[2].is_active:
            if y_nodes > x_nodes and y_nodes > 0:
                # 收集 Y 軸掃描線上所有節點的 X 座標
                x_coords = []
                tolerance = 5
                for contour in contours:
                    epsilon = 0.01 * cv2.arcLength(contour, True)
                    approx = cv2.approxPolyDP(contour, epsilon, True)
                    for point in approx:
                        x, y = point[0]
                        if abs(y - scan_y_pixel) <= tolerance:
                            x_coords.append(x)

                # 找出最密集的 X 位置
                densest_x = self.find_densest_region(x_coords, width)

                print(f"ENV3 TRIGGER! Y節點({y_nodes}) > X節點({x_nodes}), 密集處 X={densest_x}")
                self.envelopes[2].trigger()
                self.trigger_rings.append({
                    'pos': (densest_x, scan_y_pixel),
                    'radius': 10,
                    'alpha': 1.0,
                    'color': (45, 0, 188)  # 日本國旗紅色 #BC002D (BGR)
                })

    def update_trigger_rings(self):
        """更新觸發光圈動畫"""
        new_rings = []
        for ring in self.trigger_rings:
            # 擴展半徑
            ring['radius'] += 2
            # 淡出
            ring['alpha'] -= 0.05

            # 保留尚未完全消失的光圈
            if ring['alpha'] > 0 and ring['radius'] < 60:
                new_rings.append(ring)

        self.trigger_rings = new_rings

    def draw_visualization(self, frame, contours, edges):
        """繪製視覺化結果"""
        # 轉換邊緣檢測結果為 BGR（用於顯示）
        display = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)

        height, width = display.shape[:2]

        # 計算掃描線位置
        scan_x_pixel = int(self.scan_x * width)
        scan_y_pixel = int(self.scan_y * height)

        # 計算掃描線經過的節點數量
        x_nodes = self.count_scan_intersections(contours, self.scan_x, 'x', width, height)
        y_nodes = self.count_scan_intersections(contours, self.scan_y, 'y', width, height)

        # 檢查並觸發 envelope（傳入 edges, contours, width, height）
        self.check_triggers(edges, contours, x_nodes, y_nodes, scan_x_pixel, scan_y_pixel, width, height)

        # 更新 envelope 值
        for env in self.envelopes:
            env.process()

        # 更新觸發光圈
        self.update_trigger_rings()

        # 繪製垂直掃描線（X軸）- 淺灰色
        cv2.line(display, (scan_x_pixel, 0), (scan_x_pixel, height), (180, 180, 180), 2)

        # 繪製水平掃描線（Y軸）- 淺灰色
        cv2.line(display, (0, scan_y_pixel), (width, scan_y_pixel), (180, 180, 180), 2)

        # 繪製觸發光圈（使用各自的顏色）
        for ring in self.trigger_rings:
            color = ring['color']  # 從 ring 取得顏色
            thickness = 3
            alpha = ring['alpha']
            radius = int(ring['radius'])

            # 創建透明疊加層
            overlay = display.copy()
            cv2.circle(overlay, ring['pos'], radius, color, thickness)
            cv2.addWeighted(overlay, alpha, display, 1 - alpha, 0, display)

        # 計算總點數（用於顯示）
        total_points = 0
        for contour in contours:
            epsilon = 0.01 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)
            total_points += len(approx)

        # 顯示統計資訊
        info_y = 30
        cv2.putText(display, f"Contours: {len(contours)}  Points: {total_points}",
                   (10, info_y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(display, f"Threshold: {self.threshold}  Smoothing: {self.temporal_alpha}%",
                   (10, info_y + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(display, f"X Speed: {self.scan_speed_x}  Y Speed: {self.scan_speed_y}  Decay: {self.decay_time/100.0:.2f}s",
                   (10, info_y + 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        # 顯示掃描線節點數量（右上角）
        cv2.putText(display, f"X: {x_nodes}",
                   (width - 150, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
        cv2.putText(display, f"Y: {y_nodes}",
                   (width - 150, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 0, 0), 3)

        # 顯示 Envelope 數值（左下角）
        env_y = height - 100
        bar_width = 200
        bar_height = 20

        for i, env in enumerate(self.envelopes):
            # 繪製背景條
            cv2.rectangle(display, (10, env_y + i * 30), (10 + bar_width, env_y + i * 30 + bar_height),
                         (50, 50, 50), -1)

            # 繪製數值條
            filled_width = int(bar_width * env.value)
            if filled_width > 0:
                color = [(100, 200, 255), (255, 200, 100), (200, 100, 255)][i]
                cv2.rectangle(display, (10, env_y + i * 30), (10 + filled_width, env_y + i * 30 + bar_height),
                             color, -1)

            # 顯示文字
            cv2.putText(display, f"ENV{i+1}: {env.value:.2f}",
                       (220, env_y + i * 30 + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        return display

    def run(self):
        """運行主循環"""
        print("=== Contour Detection Test ===")
        print("Controls:")
        print("  - Threshold: 邊緣檢測敏感度（越高越少邊緣）")
        print("  - Smoothing: 時間平滑（0=最平滑, 100=無平滑）")
        print("  - X Speed: X軸掃描線速度（1-100）")
        print("  - Y Speed: Y軸掃描線速度（1-100）")
        print("  - Decay: Envelope decay time（10-1000 → 0.1-10.0秒）")
        print()
        print("Envelope Triggers:")
        print("  - ENV1: XY交叉點碰到輪廓")
        print("  - ENV2: X軸節點數 > Y軸節點數")
        print("  - ENV3: Y軸節點數 > X軸節點數")
        print("  - 不做 retrigger（等 decay 結束才能再觸發）")
        print()
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

            # 更新掃描線位置（各自獨立速度）
            speed_factor_x = self.scan_speed_x / 100.0  # 0.01 到 1.0
            speed_factor_y = self.scan_speed_y / 100.0  # 0.01 到 1.0
            increment_x = speed_factor_x * dt * 0.5  # 每秒最多移動0.5（2秒一個週期）
            increment_y = speed_factor_y * dt * 0.5

            self.scan_x += increment_x
            self.scan_y += increment_y

            # 循環掃描
            if self.scan_x >= 1.0:
                self.scan_x = 0.0
            if self.scan_y >= 1.0:
                self.scan_y = 0.0

            # 檢測輪廓
            contours, edges = self.detect_contours(frame)

            # 繪製視覺化
            display = self.draw_visualization(frame, contours, edges)

            # 顯示結果
            cv2.imshow(self.window_name, display)

            # 處理按鍵
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:  # 'q' 或 ESC
                break
            elif key == ord('s'):  # 儲存畫面
                filename = f"contour_test_{frame_count:04d}.png"
                cv2.imwrite(filename, display)
                print(f"已儲存: {filename}")

        # 清理
        self.cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    # 執行測試
    test = ContourDetectionTest(camera_id=0)
    test.run()
