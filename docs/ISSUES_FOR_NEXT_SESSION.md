# Vision Rhythm Complete GUI 待修復問題

程式路徑 /Users/madzine/Documents/VAV/vision_rhythm_complete_gui.py

## 核心問題

### 1. Random Mix 非整合模式語音持續循環播放無法停止
- 啟動 Vision 後在非整合模式下 Random Mix 會不斷循環播放
- 即使勾選 Integration 也無法停止 TTS 循環
- 導致同時有多個聲音播放 混亂不堪

### 2. 音訊長度不一致導致節奏引擎崩潰
錯誤訊息
```
ValueError: operands could not be broadcast together with shapes (24178,) (25938,) (24178,)
```
位置 breakbeat_engine.py line 257
```python
pattern[start:start+length] += audio[:length]
```

原因 BPM 改變後 samples_per_step 變化 但現有音訊片段長度未更新

### 3. Random effects 導致音訊長度改變
breakbeat_engine.py line 203-225 的 _apply_random_effects 會做
- Speed variation 改變音訊長度
- Pitch shift 改變音訊長度
- 導致音訊片段長度與預期的 step_duration 不符

### 4. 中文在 Random Mix 中出現但不完整
從 log 可見
- 中文有生成 但被切片成很小的片段
- 0.6s 1.1s 等短片段
- 英文日文佔據較長時間

### 5. Fill Swing Random 參數改變後仍有爆音或停止
雖然已經立即重新生成 pattern 但
- 立即重新生成會在播放中途切換 導致爆音
- BPM 快速移動時 pattern 不斷重新生成 導致音訊停止

## 建議修復方向

### 問題 1 TTS 循環播放
需要在 vision_rhythm_complete_gui.py 的 _on_integration_toggle 中
- 確實停止 TTS 的 loop_play thread
- 檢查 tts.should_stop_loop 是否真的有效

### 問題 2 和 3 音訊長度問題
方案 A 限制音訊長度
- 在 generate_pattern 的 add 函數中 確保音訊長度不超過 samples_per_step
- 裁剪或補零到固定長度

方案 B 移除 random effects 的長度改變
- Speed variation 和 pitch shift 後需要 resample 回原長度
- 或完全移除這些效果

### 問題 4 中文片段太短
在 tts_engine.py 的 speak_multilang_mix 中
- 增加最小片段長度限制 如 duration = random.uniform(1.0, 2.0)
- 或確保每種語言至少佔據一定比例

### 問題 5 即時參數改變的爆音
方案 不要立即重新生成 而是等到小節結束
- 恢復 pattern_position == 0 的條件
- 或改為 pattern_position % samples_per_beat == 0 在拍子邊界切換

或 使用 crossfade 淡入淡出避免爆音

## 測試步驟

1. 啟動程式
2. 選 Random Mix
3. 不勾選 Integration
4. 啟動 Vision
5. 確認可以聽到完整的中英日三種語言
6. 勾選 Integration
7. 啟動 Rhythm
8. 確認 TTS 停止 只有 rhythm 引擎的聲音
9. 調整 BPM Fill Swing Random 確認無爆音且參數有效
