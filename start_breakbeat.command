#!/bin/bash

# 切換到正確目錄
cd /Users/madzine/Documents/VAV

# 啟動虛擬環境並執行程式
source venv/bin/activate
export PYTHONPATH=/Users/madzine/Documents/VAV/breakbeat_cpp/build:$PYTHONPATH
python3 breakbeat_gui_test.py
