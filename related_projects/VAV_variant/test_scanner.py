#!/usr/bin/env python3
"""
測試輪廓掃描器
"""

import sys
import cv2
import numpy as np
from vav.vision.camera import Camera
from vav.cv_generator.contour_scanner import ContourScanner


def main():
    """測試輪廓掃描"""
    # 開啟攝像頭
    camera = Camera(device_id=0, width=1920, height=1080, fps=30)
    if not camera.open():
        print("無法開啟攝像頭")
        return 1

    # 建立掃描器
    scanner = ContourScanner()
    scanner.set_scan_time(3.0)  # 3 秒掃過完整輪廓

    print("輪廓掃描測試")
    print("參數:")
    print(f"  掃描時間: {scanner.scan_time}s")
    print(f"  錨點: ({scanner.anchor_x_pct}%, {scanner.anchor_y_pct}%)")
    print(f"  範圍: {scanner.range_pct}%")
    print("\n按 'q' 退出")
    print("按 's' 增加掃描時間")
    print("按 'f' 減少掃描時間")

    last_time = cv2.getTickCount()

    while True:
        # 讀取畫面
        success, frame = camera.cap.read()
        if not success or frame is None:
            continue

        # 計算 dt
        current_time = cv2.getTickCount()
        dt = (current_time - last_time) / cv2.getTickFrequency()
        last_time = current_time

        # 灰階轉換
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 偵測輪廓
        edges = scanner.detect_and_extract_contour(gray)

        # 更新掃描
        scanner.update_scan(dt, frame.shape[1], frame.shape[0])

        # 更新動畫
        scanner.update_trigger_rings()

        # 繪製疊加
        display_frame = scanner.draw_overlay(frame, edges)

        # 顯示 CV 值（終端輸出）
        if scanner.current_scan_pos is not None:
            print(f"\rSEQ1: {scanner.seq1_value*10:.2f}V  "
                  f"SEQ2: {scanner.seq2_value*10:.2f}V  "
                  f"ENV1: {scanner.env1_value*10:.2f}V  "
                  f"ENV2: {scanner.env2_value*10:.2f}V  "
                  f"ENV3: {scanner.env3_value*10:.2f}V  "
                  f"Points: {len(scanner.contour_points)}  ",
                  end='', flush=True)

        # 顯示畫面
        cv2.imshow("Contour Scanner Test", display_frame)

        # 按鍵處理
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('s'):
            scanner.set_scan_time(scanner.scan_time + 0.5)
            print(f"\n掃描時間: {scanner.scan_time}s")
        elif key == ord('f'):
            scanner.set_scan_time(scanner.scan_time - 0.5)
            print(f"\n掃描時間: {scanner.scan_time}s")

    # 清理
    camera.close()
    cv2.destroyAllWindows()
    print("\n測試結束")
    return 0


if __name__ == "__main__":
    sys.exit(main())
