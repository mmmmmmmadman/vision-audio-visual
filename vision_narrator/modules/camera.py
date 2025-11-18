"""
視訊鏡頭捕捉模組
Camera Capture Module
"""

import cv2
import numpy as np
from typing import Optional, Tuple
import threading
import time


class CameraCapture:
    """視訊鏡頭捕捉類別"""

    def __init__(self, camera_id: int = 0, resolution: Tuple[int, int] = (640, 480)):
        """
        初始化攝影機

        Args:
            camera_id: 攝影機 ID (預設 0)
            resolution: 解析度 (width, height)
        """
        self.camera_id = camera_id
        self.resolution = resolution
        self.cap = None
        self.latest_frame = None
        self.running = False
        self.lock = threading.Lock()

    def start(self) -> bool:
        """
        啟動攝影機

        Returns:
            bool: 是否成功啟動
        """
        self.cap = cv2.VideoCapture(self.camera_id)

        if not self.cap.isOpened():
            print(f"無法開啟攝影機 {self.camera_id}")
            print("請檢查:")
            print("1. 攝影機是否已連接")
            print("2. 系統偏好設定 > 隱私權與安全性 > 相機 > 是否已授權")
            print("3. 其他應用程式是否正在使用攝影機")
            return False

        # 設定解析度
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])

        # 讀取一幀確認可用
        ret, frame = self.cap.read()
        if not ret:
            print("攝影機已開啟但無法讀取畫面")
            return False

        self.running = True
        print(f"攝影機已啟動 (ID: {self.camera_id}, 解析度: {self.resolution})")

        # 啟動背景擷取執行緒
        self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.capture_thread.start()

        return True

    def _capture_loop(self):
        """背景執行緒持續捕捉畫面"""
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                with self.lock:
                    self.latest_frame = frame.copy()
            time.sleep(0.03)  # ~30fps

    def get_frame(self) -> Optional[np.ndarray]:
        """
        取得最新一幀畫面

        Returns:
            np.ndarray: BGR 格式的畫面，失敗回傳 None
        """
        with self.lock:
            if self.latest_frame is not None:
                return self.latest_frame.copy()
        return None

    def get_frame_rgb(self) -> Optional[np.ndarray]:
        """
        取得最新一幀畫面 (RGB 格式)

        Returns:
            np.ndarray: RGB 格式的畫面
        """
        frame = self.get_frame()
        if frame is not None:
            return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return None

    def save_frame(self, filename: str) -> bool:
        """
        儲存當前畫面

        Args:
            filename: 檔案名稱

        Returns:
            bool: 是否成功儲存
        """
        frame = self.get_frame()
        if frame is not None:
            cv2.imwrite(filename, frame)
            print(f"畫面已儲存: {filename}")
            return True
        return False

    def stop(self):
        """停止攝影機"""
        self.running = False
        if self.capture_thread is not None:
            self.capture_thread.join(timeout=1.0)

        if self.cap is not None:
            self.cap.release()
            print("攝影機已關閉")

    def __del__(self):
        """清理資源"""
        self.stop()


class CameraPreview:
    """攝影機預覽視窗 (可選功能)"""

    def __init__(self, camera: CameraCapture, window_name: str = "Camera Preview"):
        """
        初始化預覽視窗

        Args:
            camera: CameraCapture 實例
            window_name: 視窗名稱
        """
        self.camera = camera
        self.window_name = window_name
        self.showing = False

    def show(self):
        """顯示預覽視窗"""
        self.showing = True
        cv2.namedWindow(self.window_name)

        while self.showing:
            frame = self.camera.get_frame()
            if frame is not None:
                # 顯示提示文字
                cv2.putText(
                    frame,
                    "Press 'q' to quit, SPACE to capture",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2
                )

                cv2.imshow(self.window_name, frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                self.showing = False
                break
            elif key == ord(' '):
                # 空白鍵截圖
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                self.camera.save_frame(f"capture_{timestamp}.jpg")

        cv2.destroyWindow(self.window_name)

    def stop(self):
        """停止預覽"""
        self.showing = False


# 測試程式碼
if __name__ == "__main__":
    print("=== 攝影機捕捉模組測試 ===\n")

    # 創建攝影機實例
    camera = CameraCapture(camera_id=0, resolution=(640, 480))

    # 啟動攝影機
    if not camera.start():
        print("攝影機啟動失敗，退出測試")
        exit(1)

    print("\n選擇測試模式:")
    print("1. 預覽視窗模式 (顯示即時畫面)")
    print("2. 定時截圖模式 (每 3 秒擷取一次)")

    choice = input("\n請輸入 1 或 2: ").strip()

    if choice == "1":
        # 預覽模式
        print("\n啟動預覽視窗...")
        print("按 'q' 退出，空白鍵截圖")
        preview = CameraPreview(camera)
        preview.show()

    elif choice == "2":
        # 定時截圖模式
        print("\n定時截圖模式啟動 (每 3 秒)")
        print("按 Ctrl+C 停止\n")

        try:
            count = 0
            while True:
                frame = camera.get_frame_rgb()
                if frame is not None:
                    count += 1
                    print(f"[{count}] 擷取畫面 - 形狀: {frame.shape}, 型態: {frame.dtype}")
                time.sleep(3)
        except KeyboardInterrupt:
            print("\n\n停止截圖")

    else:
        print("無效選擇")

    # 清理
    camera.stop()
    print("\n測試完成")
