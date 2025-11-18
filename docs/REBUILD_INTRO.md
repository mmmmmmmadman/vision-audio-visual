# Breakbeat Engine - 重做音訊效果功能

## 專案路徑

- C++ 引擎: `/Users/madzine/Documents/VAV/breakbeat_cpp/src/breakbeat_engine.cpp`
- Pattern 生成: `/Users/madzine/Documents/VAV/breakbeat_cpp/src/breakbeat_pattern.cpp`
- 標頭檔: `/Users/madzine/Documents/VAV/breakbeat_cpp/include/breakbeat_engine.h`
- GUI: `/Users/madzine/Documents/VAV/breakbeat_gui_test.py`
- 編譯: `cd /Users/madzine/Documents/VAV/breakbeat_cpp/build && make`

## 問題描述

有兩個音訊效果完全無效，需要重做：

### 1. Random Pitch (主節奏隨機音高)
- 目標：隨機改變每個鼓聲音高 ±24 semitones
- 參數：`random_amount` (0.0-1.0)
- GUI slider: "Random"
- 問題：完全沒有效果

### 2. Latin Stutter (Latin 層切片重複)
- 目標：將樣本切片並重複，製造機械效果
- 參數：`latin_stutter_amount` (0.0-1.0)
- GUI slider: "Latin Stutter"
- 問題：完全沒有效果

## 核心問題

效果在 pattern 生成時套用，但 pattern 會被緩存。移動 slider 改變參數後，緩存的 pattern 不會重新生成，所以聽不到效果變化。

## 當前實作位置

- `apply_random_effects()` - breakbeat_engine.cpp 約 269 行
- `apply_stutter_effect()` - breakbeat_engine.cpp 約 256 行
- 在 `generate_pattern()` 和 `generate_latin_pattern()` 中被呼叫

**注意：程式碼包含大量除錯訊息需要一併清理**

## 需求

重新設計這兩個效果，確保：
1. GUI slider 移動時效果能即時反應
2. 不需要停止/重新播放
3. 效果明顯可聽

## 其他資訊

- macOS, Python 3.11, pybind11
- 虛擬環境: `/Users/madzine/Documents/VAV/venv`
- 其他功能 (BPM, Swing, Fill, Pattern 類型) 都正常運作
