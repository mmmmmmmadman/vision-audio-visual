# BPM 平滑過渡解決方案

## 問題診斷

原始的 `set_bpm()` 方法存在嚴重問題：
1. 立即更新 `samples_per_step` 和 `pattern_length_samples`
2. 當前的 pattern 是用舊的 timing 參數生成的
3. `get_audio_chunk()` 使用新的 timing 讀取舊的 pattern
4. 造成音訊中斷、glitch、甚至 IndexError

## 解決方案：Pattern Boundary Transition（Pattern 邊界過渡）

### 核心概念

**不在 pattern 播放中途改變 timing 參數，而是在 pattern 邊界處應用新的 BPM。**

### 實作細節

#### 1. 新增狀態變數

```python
# BPM transition handling
self.pending_bpm = None  # 等待應用的新 BPM
self.pending_timing = None  # 新的 timing 參數
```

#### 2. 重寫 `set_bpm()` - 調度 BPM 變更

```python
def set_bpm(self, bpm: int):
    """
    調度 BPM 變更，在下一個 pattern 邊界應用
    防止在 pattern 播放中途改變 timing 造成音訊 glitch
    """
    if bpm == self.bpm:
        return  # 無需改變

    # 計算新的 timing 參數
    beat_duration = 60.0 / bpm
    step_duration = beat_duration / 4
    new_samples_per_step = int(step_duration * self.sample_rate)
    new_pattern_length = new_samples_per_step * 16

    # 調度變更 - 將在 pattern 邊界應用
    self.pending_bpm = bpm
    self.pending_timing = {
        'beat_duration': beat_duration,
        'step_duration': step_duration,
        'samples_per_step': new_samples_per_step,
        'pattern_length_samples': new_pattern_length
    }
```

**關鍵點：**
- 不立即修改 `self.bpm` 和 timing 參數
- 計算新參數並存入 `pending_timing`
- 當前 pattern 繼續用舊參數播放

#### 3. 新增 `_apply_pending_bpm()` - 應用 BPM 變更

```python
def _apply_pending_bpm(self):
    """
    應用等待中的 BPM 變更
    在 pattern 邊界調用，確保平滑過渡
    """
    if self.pending_bpm is None or self.pending_timing is None:
        return

    # 應用新 BPM 和 timing
    self.bpm = self.pending_bpm
    self.beat_duration = self.pending_timing['beat_duration']
    self.step_duration = self.pending_timing['step_duration']
    self.samples_per_step = self.pending_timing['samples_per_step']
    self.pattern_length_samples = self.pending_timing['pattern_length_samples']

    # 清除等待狀態
    self.pending_bpm = None
    self.pending_timing = None
```

#### 4. 修改 `get_audio_chunk()` - 在 pattern 邊界應用變更

```python
def get_audio_chunk(self, num_frames: int) -> np.ndarray:
    # 在需要生成新 pattern 時（起始或 pattern 結束）
    if self.current_pattern is None or self.pattern_position >= len(self.current_pattern):
        # 在 pattern 邊界應用等待中的 BPM 變更
        if self.pending_bpm is not None and self.pending_timing is not None:
            self._apply_pending_bpm()

        # 用新的 timing 參數生成新 pattern
        self.current_pattern = self.generate_pattern(self.pattern_type)
        self.pattern_position = 0
        self.bar_count += 1

    # ... 其餘程式碼
```

## 工作流程

### 場景：從 140 BPM 切換到 180 BPM

```
時間軸：
|-------- Pattern A (140 BPM) --------|-------- Pattern B (180 BPM) --------|
                                       ↑
                                    應用 BPM 變更

步驟：
1. [0.0s] 用戶調用 engine.set_bpm(180)
   - engine.bpm = 140 (未變)
   - engine.pending_bpm = 180
   - Pattern A 繼續用 140 BPM 的 timing 播放

2. [0.5s] Pattern A 持續播放
   - 使用舊的 samples_per_step (4725)
   - 無音訊中斷

3. [1.0s] Pattern A 結束（pattern_position >= pattern_length）
   - 檢測到 pending_bpm != None
   - 調用 _apply_pending_bpm()
   - engine.bpm = 180
   - engine.samples_per_step = 3675
   - pending 狀態清除

4. [1.0s] 生成 Pattern B
   - 使用新的 180 BPM timing
   - 新 pattern 長度適合新 BPM

5. [1.5s] Pattern B 播放
   - 以 180 BPM 播放
   - 平滑過渡完成
```

## 優點

### 1. 無音訊中斷
- 當前 pattern 完整播放到結束
- 無需清除或截斷 pattern

### 2. 無 glitch/噪音
- timing 參數和 pattern 始終匹配
- 無 buffer overflow 或 underflow

### 3. 可預測的過渡時間
- 最大延遲：一個 pattern 的長度（4 拍）
- 在 140 BPM：~1.7 秒
- 在 180 BPM：~1.3 秒

### 4. 正確的音樂時間點
- 變更總是發生在小節邊界
- 符合音樂直覺

### 5. 處理多次變更
- 多次 `set_bpm()` 調用會覆蓋 pending 變更
- 只有最後一次調用生效

## 測試結果

所有單元測試通過：

```
✓ PASS: BPM Scheduling - BPM 變更被正確調度
✓ PASS: BPM Application - BPM 在 pattern 邊界正確應用
✓ PASS: No Change Same BPM - 相同 BPM 不產生變更
✓ PASS: Multiple BPM Changes - 多次變更正確覆蓋
✓ PASS: Timing Calculations - timing 計算準確

Total: 5/5 tests passed
```

### 測試的 BPM 範圍

| BPM | Sample Rate | Samples/Step | Pattern Length |
|-----|-------------|--------------|----------------|
| 90  | 48000Hz     | 8000         | 128000         |
| 120 | 44100Hz     | 5512         | 88192          |
| 140 | 44100Hz     | 4725         | 75600          |
| 160 | 44100Hz     | 4134         | 66144          |
| 180 | 44100Hz     | 3675         | 58800          |
| 200 | 48000Hz     | 3600         | 57600          |

所有計算精確度在 ±1 sample 範圍內（因整數捨入）。

## 使用方式

```python
# 創建 engine
engine = BreakBeatEngine(
    sample_dir="Audio Sample",
    bpm=140,
    sample_rate=44100
)

# 改變 BPM（調度變更）
engine.set_bpm(180)
# -> engine.bpm 仍然是 140
# -> engine.pending_bpm = 180

# 繼續獲取音訊
chunk = engine.get_audio_chunk(1024)
# -> 當前 pattern 用 140 BPM 播放

# ... 幾個 chunk 後，pattern 結束 ...
chunk = engine.get_audio_chunk(1024)
# -> 自動應用 180 BPM
# -> 新 pattern 用 180 BPM 生成
```

## 與其他方案的比較

### 方案 1：立即應用（原始方案）❌
- 優：BPM 立即生效
- 劣：造成音訊中斷、glitch
- 劣：可能產生 IndexError

### 方案 2：Pattern Boundary Transition（已實作）✅
- 優：無音訊中斷
- 優：無 glitch
- 優：符合音樂節奏
- 劣：最多延遲一個 pattern（~1-2 秒）

### 方案 3：Gradual Resampling（漸進式重採樣）
- 優：可以在幾個小節內平滑改變速度
- 劣：實作複雜
- 劣：需要動態 resampling
- 劣：可能影響音質

### 方案 4：Crossfade（交叉淡入淡出）
- 優：過渡更平滑
- 劣：需要同時生成兩個 pattern
- 劣：記憶體使用量加倍
- 劣：實作複雜

## 結論

Pattern Boundary Transition 是最簡單且有效的解決方案：
- ✅ 無音訊中斷
- ✅ 無 glitch/噪音
- ✅ 符合音樂直覺
- ✅ 實作簡單
- ✅ 效能優秀
- ✅ 可預測的行為

對於節奏引擎來說，在小節邊界改變 BPM 是最自然的方式，符合 DJ 和音樂製作人的期望。
