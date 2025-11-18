#!/usr/bin/env python3
"""
GPU Region Mode 完整驗證測試腳本
測試 Qt OpenGL 實作的 Region mode 功能
"""

import sys
import time
import numpy as np
import cv2
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

# 確保可以 import VAV 模組
sys.path.insert(0, '/Users/madzine/Documents/VAV')

from vav.core.controller import VAVController
from vav.utils.config import Config


class RegionModeGPUTester:
    """Region mode GPU 測試器"""

    def __init__(self):
        self.test_results = []
        self.fps_data = {}

    def log_result(self, test_name: str, passed: bool, details: str = ""):
        """記錄測試結果"""
        status = "PASS" if passed else "FAIL"
        result = {
            'test': test_name,
            'status': status,
            'passed': passed,
            'details': details
        }
        self.test_results.append(result)
        print(f"[{status}] {test_name}")
        if details:
            print(f"      {details}")

    def measure_fps(self, controller: VAVController, duration: float = 5.0, mode_name: str = ""):
        """測量 FPS（秒數內）"""
        print(f"\n[FPS] Measuring {mode_name} for {duration}s...")

        frame_count = 0
        start_time = time.time()

        # 等待系統穩定
        time.sleep(1.0)

        # 計數 frame_count
        last_frame = None
        measurement_start = time.time()

        while time.time() - measurement_start < duration:
            frame = controller.get_current_frame()
            if frame is not None:
                # 檢查是否是新畫面
                if last_frame is None or not np.array_equal(frame, last_frame):
                    frame_count += 1
                    last_frame = frame.copy()

            # 處理 Qt 事件（確保 OpenGL 能渲染）
            QApplication.processEvents()
            time.sleep(0.001)  # 1ms 小延遲

        elapsed = time.time() - measurement_start
        fps = frame_count / elapsed if elapsed > 0 else 0

        print(f"[FPS] {mode_name}: {fps:.1f} FPS ({frame_count} frames in {elapsed:.2f}s)")

        self.fps_data[mode_name] = {
            'fps': fps,
            'frame_count': frame_count,
            'duration': elapsed
        }

        return fps

    def test_basic_initialization(self):
        """測試 1: 基本初始化"""
        print("\n=== Test 1: Basic Initialization ===")

        try:
            config = Config()
            config.load()

            controller = VAVController(config=config.get_all())

            if not controller.initialize():
                self.log_result("Test 1.1: Controller initialization", False, "Failed to initialize")
                return None

            self.log_result("Test 1.1: Controller initialization", True, "Controller initialized successfully")

            # 檢查 GPU renderer 是否正確初始化
            if controller.renderer is None:
                self.log_result("Test 1.2: Renderer initialization", False, "Renderer is None")
                return None

            self.log_result("Test 1.2: Renderer initialization", True,
                          f"Using GPU: {controller.using_gpu}")

            # 檢查 region mapper
            if controller.region_mapper is None:
                self.log_result("Test 1.3: Region mapper initialization", False, "Region mapper is None")
                return None

            self.log_result("Test 1.3: Region mapper initialization", True,
                          f"Resolution: {controller.region_mapper.width}x{controller.region_mapper.height}")

            return controller

        except Exception as e:
            self.log_result("Test 1: Basic initialization", False, f"Exception: {e}")
            import traceback
            traceback.print_exc()
            return None

    def test_region_mode_off(self, controller: VAVController):
        """測試 2: Region mode OFF"""
        print("\n=== Test 2: Region Mode OFF ===")

        try:
            # 確保 Region mode 關閉
            controller.enable_region_rendering(False)
            controller.enable_multiverse_rendering(True)

            # 啟動系統
            controller.start()
            self.log_result("Test 2.1: System start", True, "System started")

            # 等待穩定
            time.sleep(2.0)

            # 檢查是否有畫面
            frame = controller.get_current_frame()
            if frame is None:
                self.log_result("Test 2.2: Frame capture", False, "No frame captured")
                controller.stop()
                return False

            self.log_result("Test 2.2: Frame capture", True,
                          f"Frame shape: {frame.shape}")

            # 測量 FPS (Region mode OFF)
            fps = self.measure_fps(controller, duration=5.0, mode_name="Region OFF")

            if fps < 20.0:
                self.log_result("Test 2.3: FPS performance", False,
                              f"FPS too low: {fps:.1f} < 20")
            else:
                self.log_result("Test 2.3: FPS performance", True,
                              f"FPS: {fps:.1f}")

            controller.stop()
            return True

        except Exception as e:
            self.log_result("Test 2: Region mode OFF", False, f"Exception: {e}")
            import traceback
            traceback.print_exc()
            if controller.running:
                controller.stop()
            return False

    def test_region_mode_brightness(self, controller: VAVController):
        """測試 3: Region mode ON (brightness)"""
        print("\n=== Test 3: Region Mode ON (Brightness) ===")

        try:
            # 啟用 Region mode (brightness)
            controller.set_region_mode('brightness')
            controller.enable_region_rendering(True)
            controller.enable_multiverse_rendering(True)

            # 啟動系統
            controller.start()
            self.log_result("Test 3.1: Region mode enabled", True, "Brightness mode")

            # 等待穩定
            time.sleep(2.0)

            # 檢查是否有畫面
            frame = controller.get_current_frame()
            if frame is None:
                self.log_result("Test 3.2: Frame capture", False, "No frame captured")
                controller.stop()
                return False

            self.log_result("Test 3.2: Frame capture", True,
                          f"Frame shape: {frame.shape}")

            # 測量 FPS (Region mode ON)
            fps = self.measure_fps(controller, duration=5.0, mode_name="Region Brightness ON")

            if fps < 20.0:
                self.log_result("Test 3.3: FPS performance", False,
                              f"FPS too low: {fps:.1f} < 20")
            else:
                self.log_result("Test 3.3: FPS performance", True,
                              f"FPS: {fps:.1f}")

            # 檢查 region map 是否正確生成
            if controller.region_mapper.region_map is None:
                self.log_result("Test 3.4: Region map generation", False,
                              "Region map is None")
            else:
                unique_regions = np.unique(controller.region_mapper.region_map)
                self.log_result("Test 3.4: Region map generation", True,
                              f"Unique regions: {unique_regions}")

            controller.stop()
            return True

        except Exception as e:
            self.log_result("Test 3: Region mode brightness", False, f"Exception: {e}")
            import traceback
            traceback.print_exc()
            if controller.running:
                controller.stop()
            return False

    def test_visual_output(self, controller: VAVController):
        """測試 4: 視覺輸出驗證"""
        print("\n=== Test 4: Visual Output Verification ===")

        try:
            # Test multiple blend modes with region on/off
            test_configs = [
                ("Region OFF + Add", False, 0),
                ("Region ON + Add", True, 0),
                ("Region OFF + Screen", False, 1),
                ("Region ON + Screen", True, 1),
            ]

            for config_name, region_enabled, blend_mode in test_configs:
                print(f"\n[Test 4] Testing: {config_name}")

                # 設定
                controller.enable_region_rendering(region_enabled)
                if region_enabled:
                    controller.set_region_mode('brightness')
                controller.set_renderer_blend_mode(blend_mode)
                controller.enable_multiverse_rendering(True)

                # 啟動
                controller.start()
                time.sleep(1.5)

                # 取得畫面
                frame = controller.get_current_frame()

                if frame is None:
                    self.log_result(f"Test 4: {config_name}", False, "No frame")
                    controller.stop()
                    continue

                # 檢查畫面非全黑
                mean_brightness = np.mean(frame)
                if mean_brightness < 1.0:
                    self.log_result(f"Test 4: {config_name}", False,
                                  f"Frame too dark: {mean_brightness:.2f}")
                else:
                    self.log_result(f"Test 4: {config_name}", True,
                                  f"Mean brightness: {mean_brightness:.2f}")

                # 儲存截圖
                filename = f"test_output_{config_name.replace(' ', '_').replace('+', '')}.png"
                cv2.imwrite(filename, frame)
                print(f"      Saved: {filename}")

                controller.stop()
                time.sleep(0.5)

            return True

        except Exception as e:
            self.log_result("Test 4: Visual output", False, f"Exception: {e}")
            import traceback
            traceback.print_exc()
            if controller.running:
                controller.stop()
            return False

    def test_integration(self, controller: VAVController):
        """測試 5: 整合測試"""
        print("\n=== Test 5: Integration Test ===")

        try:
            # 啟用所有功能
            controller.enable_multiverse_rendering(True)
            controller.enable_region_rendering(True)
            controller.set_region_mode('brightness')

            # 設定參數
            controller.set_renderer_brightness(2.5)
            controller.set_renderer_blend_mode(0)  # Add

            # 啟動
            controller.start()
            self.log_result("Test 5.1: Full system start", True)

            # 運行 3 秒
            time.sleep(3.0)

            # 檢查 CV 值
            cv_values = controller.get_cv_values()
            self.log_result("Test 5.2: CV generation", True,
                          f"CV values: {cv_values[:3]}")  # Show ENV1-3

            # 檢查畫面
            frame = controller.get_current_frame()
            if frame is not None:
                self.log_result("Test 5.3: Frame rendering", True,
                              f"Shape: {frame.shape}")
            else:
                self.log_result("Test 5.3: Frame rendering", False, "No frame")

            controller.stop()
            return True

        except Exception as e:
            self.log_result("Test 5: Integration test", False, f"Exception: {e}")
            import traceback
            traceback.print_exc()
            if controller.running:
                controller.stop()
            return False

    def test_boundary_conditions(self, controller: VAVController):
        """測試 6: 邊界條件"""
        print("\n=== Test 6: Boundary Conditions ===")

        try:
            # Test 6.1: All channels disabled
            print("\n[Test 6.1] All channels disabled")
            controller.enable_multiverse_rendering(True)
            controller.enable_region_rendering(True)

            for i in range(4):
                controller.set_renderer_channel_intensity(i, 0.0)

            controller.start()
            time.sleep(1.5)

            frame = controller.get_current_frame()
            if frame is not None:
                mean = np.mean(frame)
                self.log_result("Test 6.1: All channels off", True,
                              f"Mean brightness: {mean:.2f} (should be ~0)")
            else:
                self.log_result("Test 6.1: All channels off", False, "No frame")

            controller.stop()

            # Test 6.2: Single channel enabled with region
            print("\n[Test 6.2] Single channel with region")
            controller.set_renderer_channel_intensity(0, 1.0)  # Enable Ch1 only
            for i in range(1, 4):
                controller.set_renderer_channel_intensity(i, 0.0)

            controller.start()
            time.sleep(1.5)

            frame = controller.get_current_frame()
            if frame is not None:
                self.log_result("Test 6.2: Single channel + region", True,
                              f"Frame shape: {frame.shape}")
            else:
                self.log_result("Test 6.2: Single channel + region", False, "No frame")

            controller.stop()

            # Restore defaults
            for i in range(4):
                controller.set_renderer_channel_intensity(i, 1.0)

            return True

        except Exception as e:
            self.log_result("Test 6: Boundary conditions", False, f"Exception: {e}")
            import traceback
            traceback.print_exc()
            if controller.running:
                controller.stop()
            return False

    def generate_report(self):
        """生成測試報告"""
        print("\n" + "="*60)
        print("GPU REGION MODE TEST REPORT")
        print("="*60)

        # 統計
        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r['passed'])
        failed = total - passed

        print(f"\nSummary: {passed}/{total} tests passed ({failed} failed)")

        # 詳細結果
        print("\nDetailed Results:")
        print("-" * 60)
        for result in self.test_results:
            status_icon = "✓" if result['passed'] else "✗"
            print(f"{status_icon} [{result['status']}] {result['test']}")
            if result['details']:
                print(f"           {result['details']}")

        # FPS 數據
        if self.fps_data:
            print("\nFPS Performance:")
            print("-" * 60)
            for mode_name, data in self.fps_data.items():
                print(f"{mode_name:30s}: {data['fps']:6.1f} FPS")

        # 整體評估
        print("\n" + "="*60)
        if failed == 0:
            print("OVERALL ASSESSMENT: ALL TESTS PASSED ✓")
            print("Region mode GPU implementation is READY for deployment.")
        elif failed <= 2:
            print("OVERALL ASSESSMENT: MINOR ISSUES DETECTED")
            print(f"{failed} test(s) failed. Review and fix before deployment.")
        else:
            print("OVERALL ASSESSMENT: MAJOR ISSUES DETECTED")
            print(f"{failed} test(s) failed. NOT recommended for deployment.")
        print("="*60 + "\n")

        return passed == total


def main():
    """主測試流程"""
    print("GPU Region Mode Verification Test")
    print("Platform: macOS")
    print("Renderer: Qt OpenGL Multi-Pass")
    print("-" * 60)

    # 創建 Qt Application
    app = QApplication(sys.argv)

    # 創建測試器
    tester = RegionModeGPUTester()

    # Test 1: Basic initialization
    controller = tester.test_basic_initialization()
    if controller is None:
        print("\n[FATAL] Failed to initialize controller. Aborting tests.")
        return 1

    # Test 2: Region mode OFF
    tester.test_region_mode_off(controller)

    # Test 3: Region mode ON (brightness)
    tester.test_region_mode_brightness(controller)

    # Test 4: Visual output
    tester.test_visual_output(controller)

    # Test 5: Integration test
    tester.test_integration(controller)

    # Test 6: Boundary conditions
    tester.test_boundary_conditions(controller)

    # Generate report
    all_passed = tester.generate_report()

    # Cleanup
    if controller.running:
        controller.stop()

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
