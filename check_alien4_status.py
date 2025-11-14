#!/usr/bin/env python3
"""
快速檢查 Alien4 狀態的腳本
使用方法: 在程式執行時，在另一個終端執行這個腳本
"""
import sys
sys.path.insert(0, '/Users/madzine/Documents/VAV')

from vav.audio.alien4_wrapper import Alien4EffectChain

# 創建一個 dummy instance 來檢查
alien4 = Alien4EffectChain(48000)
status = alien4.get_status()

print("=" * 60)
print("Alien4 當前狀態")
print("=" * 60)

if not status["available"]:
    print("Alien4 engine 不可用")
    sys.exit(1)

print(f"已錄音長度: {status['recorded_length']} samples ({status['recorded_length']/48000:.2f} 秒)")
print(f"檢測到的 slices: {status['num_slices']}")
print(f"當前 voices 數量: {status['num_voices']}")

print("\n" + "=" * 60)

if status['recorded_length'] == 0:
    print("狀態: 尚未錄音")
elif status['num_slices'] == 0:
    print("狀態: 已錄音但沒有 slices (MIN 參數可能太大)")
    print("建議: 調小 MIN slider")
elif status['num_voices'] == 1:
    print("狀態: 單聲道模式")
    print("建議: 調整 POLY slider")
else:
    print(f"狀態: 複音模式 ({status['num_voices']} voices, {status['num_slices']} slices)")
    print("POLY 功能應該正常")

print("=" * 60)
