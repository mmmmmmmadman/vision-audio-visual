#!/usr/bin/env python3
"""
快速測試腳本：驗證 Region Map 是否正確運作

測試方法：
1. 只啟用 CH1 和 CH4 (極端對比)
2. CH1: 0° (垂直), CH4: 90° (水平)
3. 用手遮蔽鏡頭一半來製造明暗對比

預期結果：
- Region Map ON: 暗區顯示垂直波形, 亮區顯示水平波形
- Region Map OFF: 全畫面都是垂直+水平的混合
"""

import sys
import os
sys.path.insert(0, '/Users/madzine/Documents/VAV')

from vav.core.controller import VAVController
from vav.gui.compact_main_window import MainWindow
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

def setup_test_config(controller):
    """設置測試配置：只啟用 CH1 (0°) 和 CH4 (135°)"""
    print("\n" + "="*60)
    print("設置測試配置...")
    print("="*60)

    # 停用 CH2 和 CH3
    controller.toggle_channel(1, False)  # CH2 OFF
    controller.toggle_channel(2, False)  # CH3 OFF

    # 確保 CH1 和 CH4 啟用
    controller.toggle_channel(0, True)   # CH1 ON (0°)
    controller.toggle_channel(3, True)   # CH4 ON (135°)

    # 設置不同角度以便區分
    controller.set_channel_angle(0, 0.0)    # CH1: 垂直
    controller.set_channel_angle(3, 90.0)   # CH4: 水平

    # 設置相同的 ratio 和 intensity
    for ch in [0, 3]:
        controller.set_channel_ratio(ch, 1.0)
        controller.set_channel_intensity(ch, 1.0)
        controller.set_channel_curve(ch, 0.0)

    # 啟用 Region Map (brightness mode)
    controller.enable_region_rendering(True)
    controller.set_region_mode('brightness')

    print("\n測試配置完成！")
    print("-" * 60)
    print("Channel 狀態:")
    print("  CH1 (0°):    啟用 - 垂直波形")
    print("  CH2 (45°):   停用")
    print("  CH3 (90°):   停用")
    print("  CH4 (135°):  啟用 - 水平波形")
    print("-" * 60)
    print("\n現在請測試：")
    print("1. 用手遮蔽鏡頭的左半邊（製造暗區）")
    print("2. 觀察波形方向：")
    print("   - Region ON: 暗區=垂直, 亮區=水平")
    print("   - Region OFF: 全畫面都是垂直+水平混合")
    print("3. 切換 Region Map checkbox 來比較差異")
    print("="*60 + "\n")

if __name__ == '__main__':
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    # 延遲 3 秒後設置測試配置（等待系統初始化）
    QTimer.singleShot(3000, lambda: setup_test_config(window.controller))

    sys.exit(app.exec())
