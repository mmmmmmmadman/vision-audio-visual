#!/usr/bin/env python3
"""
即時監控 Alien4 狀態
會持續更新顯示當前狀態
"""
import time
import os

# 因為主程式已經在運行，我們需要用 IPC 或直接讀取共享狀態
# 這裡我們用一個簡單的方式: 定期執行狀態檢查

print("開始監控 Alien4 狀態...")
print("按 Ctrl+C 停止監控")
print("=" * 70)

last_status = {}

while True:
    try:
        # 清除畫面
        os.system('clear' if os.name != 'nt' else 'cls')

        print("=" * 70)
        print("Alien4 即時狀態監控")
        print("=" * 70)
        print(f"時間: {time.strftime('%H:%M:%S')}")
        print()

        # 這裡我們無法直接存取正在運行的 instance
        # 所以顯示操作說明
        print("操作說明:")
        print("  1. 按下 REC 按鈕開始錄音")
        print("  2. 播放聲音 (確保振幅 > 0.05)")
        print("  3. 再次按下 REC 停止錄音")
        print("  4. 調整 MIN slider 來改變 slice 數量")
        print("  5. 調整 POLY slider 來啟用多聲道 (1-8)")
        print()
        print("檢查要點:")
        print("  - MIN 在最左邊 (0) 時應該檢測到很多 slice")
        print("  - MIN 在最右邊 (100) 時應該只有少數或沒有 slice")
        print("  - POLY > 1 時應該聽到更豐富的聲音和 stereo 效果")
        print()
        print("如果 POLY 沒有效果:")
        print("  - 確認已經錄音")
        print("  - 確認 MIN slider 不要太右邊 (建議 < 30)")
        print("  - 確認 MIX slider 不是 0 (建議 > 50)")
        print()
        print("=" * 70)

        time.sleep(2)

    except KeyboardInterrupt:
        print("\n\n監控結束")
        break
