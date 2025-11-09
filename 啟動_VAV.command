#!/bin/bash

# VAV 系統啟動腳本
# 自動切換到 VAV 目錄並啟動主程式

# 切換到腳本所在目錄
cd "$(dirname "$0")"

# 顯示啟動訊息
echo "========================================="
echo "啟動 VAV 系統..."
echo "========================================="

# 檢查虛擬環境是否存在
if [ ! -d "venv" ]; then
    echo "錯誤：找不到虛擬環境 venv"
    echo "請先執行：python3 -m venv venv"
    echo "然後安裝依賴：venv/bin/pip install -r requirements.txt"
    read -p "按 Enter 鍵關閉視窗..."
    exit 1
fi

# 啟動 VAV
venv/bin/python3 main_compact.py

# 如果程式異常退出，顯示錯誤訊息
if [ $? -ne 0 ]; then
    echo ""
    echo "========================================="
    echo "VAV 系統異常退出"
    echo "========================================="
    read -p "按 Enter 鍵關閉視窗..."
fi
