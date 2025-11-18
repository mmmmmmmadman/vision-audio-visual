#!/bin/bash
# Vision Narrator 快速啟動腳本

# 啟動虛擬環境
source venv/bin/activate

# 運行主程式
python narrator.py "$@"
