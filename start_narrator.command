#!/bin/bash

# 取得腳本所在目錄
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# 切換到 vision_narrator 目錄
cd "$DIR/vision_narrator"

# 啟動 venv 並執行 narrator GUI 將輸出重定向
nohup ./venv/bin/python3 narrator_gui.py > /dev/null 2>&1 &

# 顯示啟動訊息
echo "Vision Narrator 已在背景啟動"
echo "按任意鍵關閉此視窗..."
read -n 1

# 關閉 Terminal 視窗
osascript -e 'tell application "Terminal" to close first window' & exit
