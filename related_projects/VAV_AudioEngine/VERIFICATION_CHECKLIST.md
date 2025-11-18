# Alien4 功能驗證檢查清單

**快速參考**: 使用本清單逐項驗證功能實作

---

## ✅ 核心功能檢查

### 1. Slice 系統

#### 1.1 Slice 結構體
- [ ] `int startSample`
- [ ] `int endSample`
- [ ] `float peakAmplitude`
- [ ] `bool active`

#### 1.2 rescanSlices() 方法
- [ ] 接受參數: `threshold`, `minSliceTime`, `sampleRate`
- [ ] 清空現有 slices: `slices.clear()`
- [ ] Onset detection: `lastAmp < threshold && currentAmp >= threshold`
- [ ] MIN_SLICE_TIME 過濾: 移除過短的 slice
- [ ] Peak amplitude 追蹤
- [ ] 正確 finalize 最後一個 slice

#### 1.3 即時 Slice 偵測
- [ ] 錄音時偵測 threshold crossing
- [ ] 即時創建 Slice 物件
- [ ] 即時更新 peakAmplitude
- [ ] 停止錄音時 finalize

#### 1.4 MIN_SLICE_TIME 功能
- [ ] 指數曲線（0.0-0.5）: `0.001 * pow(1000, t)`
- [ ] 線性曲線（0.5-1.0）: `1.0 + t * 4.0`
- [ ] 範圍: 0.001 - 5.0 秒
- [ ] 變化時自動 rescan
- [ ] 變化時自動 redistribute voices

#### 1.5 測試驗證
- [ ] 錄音後 slice 數量 > 0
- [ ] MIN_SLICE_TIME = 0.0 → 更多 slices
- [ ] MIN_SLICE_TIME = 1.0 → 更少 slices
- [ ] Slice startSample < endSample
- [ ] 所有 active slices 有效

---

### 2. Polyphonic Voice 系統

#### 2.1 Voice 結構體
- [ ] `int sliceIndex`
- [ ] `int playbackPosition`
- [ ] `float playbackPhase`
- [ ] `float speedMultiplier`

#### 2.2 redistributeVoices() 方法
- [ ] 只在 `numVoices > 1` 時執行
- [ ] 只在 `slices.size() > 0` 時執行
- [ ] 隨機選擇 slice: `uniform_int_distribution`
- [ ] 隨機 speed: `uniform_real_distribution(-2.0, 2.0)`
- [ ] 確保選擇 active slice
- [ ] 安全性檢查（最多 20 次嘗試）

#### 2.3 Voice 動態管理
- [ ] `numVoices` 範圍: 1-8
- [ ] Voice 0 使用當前 slice
- [ ] Voice 1-7 隨機分配 slice
- [ ] Voice 1-7 隨機 speed multiplier
- [ ] `voices.resize(numVoices)` 正確

#### 2.4 Polyphonic 播放邏輯
- [ ] 每個 voice 獨立播放
- [ ] 每個 voice 獨立速度: `voiceSpeed * speedMultiplier`
- [ ] 每個 voice 獨立 phase 追蹤
- [ ] 每個 voice 在自己的 slice 內 loop
- [ ] 支援反向播放（負速度）
- [ ] L/R 交替: 偶數 → L, 奇數 → R
- [ ] 正規化: `sqrt(leftVoices)`, `sqrt(rightVoices)`
- [ ] 更新 layer position 為 voice 0

#### 2.5 測試驗證
- [ ] POLY = 1: mono 輸出
- [ ] POLY = 2: stereo 輸出，L/R 不同
- [ ] POLY = 4: 豐富的 polyphonic 音色
- [ ] POLY = 8: 最大 polyphony
- [ ] 聽到隨機 speed 變化
- [ ] 聽到立體聲場分布

---

### 3. SCAN 參數

#### 3.1 功能實作
- [ ] 參數型別: `float` (0.0-1.0)
- [ ] 映射到 slice index: `round(scan * (slices.size()-1))`
- [ ] 更新 `currentSliceIndex`
- [ ] 更新 `playbackPosition` 到 slice start
- [ ] 重置 `playbackPhase = 0.0`
- [ ] 更新 voice 0 的 slice
- [ ] SCAN 變化時觸發 `redistributeVoices()`

#### 3.2 測試驗證
- [ ] SCAN = 0.0 → 播放第一個 slice
- [ ] SCAN = 1.0 → 播放最後一個 slice
- [ ] SCAN = 0.5 → 播放中間 slice
- [ ] 旋轉 SCAN 時聽到不同 slice
- [ ] SCAN 變化時 voice 1-7 重新分配

---

### 4. POLY 參數

#### 4.1 功能實作
- [ ] 參數型別: `int` (1-8)
- [ ] 整數捕捉（snap）
- [ ] 設定時 resize voices
- [ ] 設定時初始化所有 voices
- [ ] Python binding: `set_poly(int)`
- [ ] Python binding: `get_num_voices()`

#### 4.2 測試驗證
- [ ] POLY = 1: 單一 voice
- [ ] POLY = 4: 4 個 voices
- [ ] POLY = 8: 8 個 voices
- [ ] 動態改變 POLY 時平滑轉換

---

### 5. SPEED 參數

#### 5.1 範圍檢查
- [ ] 最小值: -8.0
- [ ] 最大值: +8.0
- [ ] 預設值: 1.0
- [ ] 負值支援（反向播放）

#### 5.2 測試驗證
- [ ] SPEED = 1.0: 正常速度
- [ ] SPEED = 2.0: 2倍速
- [ ] SPEED = -1.0: 反向播放
- [ ] SPEED = -8.0: 8倍反向
- [ ] 在 polyphonic 模式下，每個 voice 速度不同

---

## ✅ 音訊處理流程

### 6. 錄音 → Slice 偵測

- [ ] 按下 REC 按鈕開始錄音
- [ ] 即時偵測 threshold crossing (0.5)
- [ ] 即時創建 slices
- [ ] 按下 REC 停止錄音
- [ ] Finalize 最後一個 slice
- [ ] 複製 temp buffer 到 main buffer

---

### 7. Polyphonic 播放

#### 單 Voice 模式
- [ ] 播放當前 slice
- [ ] Loop 在 slice 範圍內
- [ ] 支援正向/反向
- [ ] 線性插值

#### 多 Voice 模式
- [ ] 所有 voices 同時播放
- [ ] 每個 voice 不同 slice
- [ ] 每個 voice 不同速度
- [ ] L/R 交替輸出
- [ ] 正規化輸出

---

### 8. MIX 控制

- [ ] MIX = 0.0: 100% input
- [ ] MIX = 0.5: 50% input + 50% loop
- [ ] MIX = 1.0: 100% loop
- [ ] Input 是 mono，分配到 L/R

---

### 9. FDBK 控制

- [ ] Feedback 來自效果鏈末端
- [ ] 使用 tanh 軟限制: `tanh(x * 0.3) / 0.3`
- [ ] FDBK = 0.0: 無 feedback
- [ ] FDBK = 1.0: 最大 feedback
- [ ] 避免爆音

---

### 10. 3-Band EQ

#### 頻率檢查
- [ ] Low shelf: 80 Hz (不是 250 Hz)
- [ ] Mid peak: 2500 Hz (不是 1000 Hz)
- [ ] High shelf: 12000 Hz (不是 4000 Hz)

#### 增益範圍
- [ ] -20 dB 到 +20 dB
- [ ] 0 dB = bypass

#### 測試驗證
- [ ] Low +10dB: 低音增強
- [ ] Mid -10dB: 中音衰減
- [ ] High +10dB: 高音增強

---

### 11. Delay

- [ ] 獨立 L/R delay time
- [ ] Time L: 0.001 - 2.0 秒
- [ ] Time R: 0.001 - 2.0 秒
- [ ] Feedback: 0.0 - 0.95
- [ ] Wet/Dry mix: 0.0 - 1.0
- [ ] Buffer size: 96000 samples (2秒 @ 48kHz)

---

### 12. Reverb

#### 架構檢查
- [ ] Freeverb style
- [ ] 4 comb filters (VCV) 或 8 (重建版)
- [ ] 2 allpass filters (VCV) 或 4 (重建版)
- [ ] Highpass filter (100 Hz)

#### 參數檢查
- [ ] Room size: 0.0 - 1.0
- [ ] Damping: 0.0 - 1.0
- [ ] Decay: 0.0 - 1.0
- [ ] Wet/Dry: 0.0 - 1.0

---

## ✅ Python Binding

### 13. 基本參數

- [ ] `set_recording(bool)`
- [ ] `set_looping(bool)`
- [ ] `set_min_slice_time(float)` - 0.0-1.0 knob value
- [ ] `set_scan(float)` - 0.0-1.0 (不是 int)
- [ ] `set_feedback(float)` - 0.0-1.0
- [ ] `set_mix(float)` - 0.0-1.0
- [ ] `set_speed(float)` - -8.0 到 +8.0
- [ ] `set_poly(int)` - 1 到 8

---

### 14. EQ 參數

- [ ] `set_eq_low(float)` - -20.0 到 +20.0 dB
- [ ] `set_eq_mid(float)` - -20.0 到 +20.0 dB
- [ ] `set_eq_high(float)` - -20.0 到 +20.0 dB

---

### 15. Delay 參數

- [ ] `set_delay_time(float, float)` - L/R time
- [ ] `set_delay_feedback(float)` - 0.0-0.95
- [ ] `set_delay_wet(float)` - 0.0-1.0

---

### 16. Reverb 參數

- [ ] `set_reverb_room(float)` - 0.0-1.0
- [ ] `set_reverb_damping(float)` - 0.0-1.0
- [ ] `set_reverb_decay(float)` - 0.0-1.0
- [ ] `set_reverb_wet(float)` - 0.0-1.0

---

### 17. 查詢方法

- [ ] `get_num_slices()` → int
- [ ] `get_slice_info(int)` → dict
- [ ] `get_num_voices()` → int
- [ ] `get_current_slice()` → int

---

### 18. 音訊處理

- [ ] `process(array_l, array_r)` → (array_l, array_r)
- [ ] 接受 NumPy arrays
- [ ] 返回 NumPy arrays
- [ ] 支援任意 buffer size

---

### 19. 其他

- [ ] `clear()` - 清空所有 buffers

---

## ✅ 測試驗證

### 20. 單元測試

#### Slice 系統
- [ ] test_slice_structure
- [ ] test_rescan_slices
- [ ] test_min_slice_time_exponential
- [ ] test_realtime_slice_detection
- [ ] test_slice_finalization

#### Polyphonic 系統
- [ ] test_voice_structure
- [ ] test_redistribute_voices
- [ ] test_voice_management
- [ ] test_polyphonic_playback
- [ ] test_lr_alternation
- [ ] test_normalization

#### SCAN 功能
- [ ] test_scan_parameter
- [ ] test_scan_slice_selection
- [ ] test_scan_redistribute

---

### 21. 整合測試

- [ ] test_complete_workflow
- [ ] test_parameter_ranges
- [ ] test_effects_chain
- [ ] test_python_binding

---

### 22. 性能測試

- [ ] Realtime ratio > 10x (POLY=1)
- [ ] Realtime ratio > 5x (POLY=8)
- [ ] 記憶體使用 < 100 MB
- [ ] 無記憶體洩漏

---

### 23. 音色驗證

- [ ] 與 VCV Rack 輸出相似度 > 95%
- [ ] 聽感測試通過
- [ ] A/B 對比測試

---

## 📊 完成度追蹤

### 核心系統
- [ ] Slice 系統: 0% → 100%
- [ ] Polyphonic Voice: 0% → 100%
- [ ] SCAN 功能: 0% → 100%
- [ ] POLY 參數: 0% → 100%

### 參數修正
- [ ] SPEED 範圍: 50% → 100%
- [ ] MIN_SLICE_TIME: 30% → 100%
- [ ] EQ 頻率: 80% → 100%
- [ ] Feedback: 70% → 100%

### 總體完成度
- [ ] 當前: ~40%
- [ ] 目標: 100%

---

## 🎯 里程碑檢查

- [ ] **M1**: Slice 系統可用
- [ ] **M2**: Polyphonic 可用
- [ ] **M3**: SCAN 可用
- [ ] **M4**: 100% 功能對等

---

**使用說明**:
1. 在實作過程中逐項勾選
2. 每完成一個小節，執行相應測試
3. 所有項目勾選完成後，達成 100% 功能對等

**相關文件**:
- [VERIFICATION_REPORT.md](./VERIFICATION_REPORT.md) - 詳細分析
- [IMPLEMENTATION_ROADMAP.md](./IMPLEMENTATION_ROADMAP.md) - 實作指南
