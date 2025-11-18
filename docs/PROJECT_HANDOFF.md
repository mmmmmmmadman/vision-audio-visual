# Breakbeat Engine 專案狀況說明

## 專案概述
C++ Breakbeat 節奏引擎，使用 pybind11 綁定到 Python，Tkinter GUI 測試介面

## 主要檔案路徑

### C++ 引擎
- 主程式: `/Users/madzine/Documents/VAV/breakbeat_cpp/src/breakbeat_engine.cpp`
- Pattern 生成: `/Users/madzine/Documents/VAV/breakbeat_cpp/src/breakbeat_pattern.cpp`
- 標頭檔: `/Users/madzine/Documents/VAV/breakbeat_cpp/include/breakbeat_engine.h`
- Python 綁定: `/Users/madzine/Documents/VAV/breakbeat_cpp/python/bindings.cpp`

### Python 介面
- GUI 測試程式: `/Users/madzine/Documents/VAV/breakbeat_gui_test.py`

### 編譯環境
- 編譯目錄: `/Users/madzine/Documents/VAV/breakbeat_cpp/build`
- Python 虛擬環境: `/Users/madzine/Documents/VAV/venv`
- Sample 目錄: `/Users/madzine/Documents/VAV/Audio Sample`

## 編譯指令
```bash
cd /Users/madzine/Documents/VAV/breakbeat_cpp/build
make
```

## 執行 GUI
```bash
cd /Users/madzine/Documents/VAV
source venv/bin/activate
PYTHONPATH=/Users/madzine/Documents/VAV/breakbeat_cpp/build:$PYTHONPATH python3 breakbeat_gui_test.py
```

## 當前問題描述

### 問題：音訊效果參數無法即時生效

有兩個音訊效果在 GUI 中移動 slider 時完全沒有效果：

1. **Random Pitch 效果** (已移除)
   - 目標：隨機改變音高
   - 位置：breakbeat_engine.cpp `apply_random_effects` 函數
   - 呼叫：breakbeat_pattern.cpp 第 56 行在 `add_sample` lambda 中呼叫
   - 問題：即使參數設為 100% 也完全聽不到效果

2. **Latin Stutter 效果** (仍存在)
   - 目標：將樣本切片並重複填滿
   - 位置：breakbeat_engine.cpp `apply_stutter_effect` 函數
   - 呼叫：breakbeat_pattern.cpp 第 276 行在 Latin pattern 生成時呼叫
   - 問題：即使參數設為 100% 也幾乎聽不到效果

### 診斷結果

經過大量除錯發現：

1. **效果函數本身正常運作** - 在獨立測試腳本中效果確實有執行
2. **參數有正確傳遞** - `set_random_amount()` 和 `set_latin_stutter_amount()` 正確更新參數
3. **核心問題：Pattern 緩存機制**
   - 第一次按 Play 時以預設參數 (random_amount=0, latin_stutter_amount=0) 生成 pattern
   - Pattern 被緩存在 `current_pattern_` 和 `current_latin_pattern_`
   - 之後移動 slider 改變參數但 pattern 不會立即重新生成
   - 參數變化檢查邏輯在 `get_audio_chunk` 中但條件可能不滿足

### 相關程式碼位置

**Pattern 生成時機** (breakbeat_pattern.cpp)
- 第 375-500 行：`get_audio_chunk` 函數
- 第 383-418 行：參數變化檢查邏輯 (最近修改)
- 第 428-446 行：原本的參數檢查邏輯 (在 for loop 內每 1/32 音符檢查)

**問題分析**
- Pattern 只在特定條件下重新生成：
  1. Pattern 為空
  2. BPM 改變
  3. 參數改變且到達檢查點位置
- 最近嘗試修改為每次 `get_audio_chunk` 開頭就檢查參數變化
- 但仍無法解決問題

## 建議的解決方向

1. **簡化 pattern 更新機制** - 移除複雜的檢查點邏輯，每次參數變化都立即重新生成
2. **或實作真正的即時效果** - 不在 pattern 生成時套用效果，而是在音訊輸出時套用
3. **檢查 sounddevice callback** - 可能 callback 執行環境導致參數更新延遲

## 目前程式碼狀態

包含大量除錯訊息 (std::cerr) 需要清理：
- breakbeat_engine.cpp `apply_random_effects` 和 `apply_stutter_effect`
- breakbeat_pattern.cpp `generate_pattern` 和 `get_audio_chunk`

## 其他功能狀態

正常運作的功能：
- Pattern 類型切換 (AMEN, JUNGLE, BOOM_BAP, TECHNO)
- BPM 調整
- Swing 效果
- Fill 效果
- Rest 機率
- Latin 節奏層
- LA-2A Compressor

## 下一步建議

重新設計音訊效果的架構：
1. 將效果從 pattern 生成階段移到音訊輸出階段
2. 或確保參數變化時立即且可靠地重新生成 pattern
3. 簡化參數檢查邏輯避免複雜的條件判斷
