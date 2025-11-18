# VAV Multiverse 渲染器 + Stable Diffusion 性能測試報告

## 測試日期
2025-11-04 23:32

## 測試目的
測試開啟 Stable Diffusion img2img 時，CPU (Numba v11042100) vs GPU (Qt OpenGL Metal v11042318) 的性能差異。

## 測試環境
- **硬體**: Apple Silicon (Metal backend)
- **解析度**: 1920x1080
- **音訊**: 4 通道, 2400 samples (50ms @ 48kHz)
- **SD 模型**: Stable Diffusion 1.5 + LCM LoRA + TAESD
- **SD 參數**:
  - Steps: 2
  - Strength: 0.5
  - Guidance Scale: 1.0
  - Send Interval: 1.5 秒
- **測試幀數**: 100 frames per test (4 tests total)

---

## 測試結果摘要

### CPU (Numba JIT) 性能

| 測試條件 | 渲染時間 | FPS | SD Overhead |
|---------|---------|-----|-------------|
| Without SD | 27.104 ms | 36.9 fps | - |
| With SD (render only) | 29.066 ms | 34.4 fps | +1.962 ms |
| With SD (total) | 29.134 ms | 34.3 fps | +2.030 ms |

**SD 對 CPU 渲染的影響**: +7.2%

### GPU (Qt OpenGL Metal) 性能

| 測試條件 | 渲染時間 | FPS | SD Overhead |
|---------|---------|-----|-------------|
| Without SD | 4.825 ms | 207.3 fps | - |
| With SD (render only) | 5.862 ms | 170.6 fps | +1.037 ms |
| With SD (total) | 5.900 ms | 169.5 fps | +1.076 ms |

**SD 對 GPU 渲染的影響**: +21.5%

### GPU vs CPU (WITH SD enabled)

- **GPU 渲染加速**: **4.96x**
- **GPU 絕對優勢**: 23.204 ms faster per frame
- **GPU 即使開啟 SD 仍可達**: 169.5 fps

---

## 詳細測試數據

### Test 1: CPU WITHOUT SD (Baseline)

```
Frames rendered: 100
Average render time: 27.104 ms/frame
Median render time: 27.003 ms/frame
Min render time: 25.617 ms/frame
Max render time: 30.020 ms/frame
Std deviation: 0.796 ms
Average FPS: 36.9 fps
```

### Test 2: CPU WITH SD

```
Frames rendered: 100

=== Rendering Performance ===
Average render time: 29.066 ms/frame
Median render time: 28.465 ms/frame
Min render time: 26.352 ms/frame
Max render time: 44.292 ms/frame
Std deviation: 2.250 ms
Average FPS: 34.4 fps

=== SD Processing Performance ===
Average SD feed time: 0.018 ms
Average SD get time: 0.048 ms
SD overhead: 0.066 ms

=== Total Performance (Render + SD) ===
Average total time: 29.134 ms/frame
Average total FPS: 34.3 fps
Total overhead: 0.068 ms
```

**分析**:
- SD feed/get 本身只增加 0.068 ms (非常少)
- 但渲染時間增加了 1.962 ms (7.2%)
- 原因：SD 在獨立進程中運行，但共用 GPU 資源 (MPS backend)
- 標準差從 0.796 ms 增加到 2.250 ms (變異性增加)

### Test 3: GPU WITHOUT SD (Baseline)

```
Frames rendered: 100
Average render time: 4.825 ms/frame
Median render time: 4.849 ms/frame
Min render time: 3.630 ms/frame
Max render time: 6.265 ms/frame
Std deviation: 0.701 ms
Average FPS: 207.3 fps
```

### Test 4: GPU WITH SD

```
Frames rendered: 100

=== Rendering Performance ===
Average render time: 5.862 ms/frame
Median render time: 5.358 ms/frame
Min render time: 3.846 ms/frame
Max render time: 27.173 ms/frame
Std deviation: 2.536 ms
Average FPS: 170.6 fps

=== SD Processing Performance ===
Average SD feed time: 0.014 ms
Average SD get time: 0.023 ms
SD overhead: 0.037 ms

=== Total Performance (Render + SD) ===
Average total time: 5.900 ms/frame
Average total FPS: 169.5 fps
Total overhead: 0.039 ms
```

**分析**:
- SD feed/get 只增加 0.039 ms (比 CPU 還少)
- 但渲染時間增加了 1.037 ms (21.5%)
- GPU 版本受 SD 影響較大 (21.5% vs 7.2%)
- 原因：Metal GPU 資源在 Multiverse 和 SD 之間競爭
- 最大渲染時間從 6.265 ms 暴增到 27.173 ms (4.3x spike)
- 標準差從 0.701 ms 增加到 2.536 ms (變異性大幅增加)

---

## 核心發現

### 1. SD 對渲染性能的影響

#### CPU (Numba JIT)
- **渲染時間增加**: +1.962 ms (+7.2%)
- **變異性增加**: 0.796 ms → 2.250 ms (2.8x)
- **影響較小**: CPU 渲染和 SD 推理在不同資源上

#### GPU (Qt OpenGL Metal)
- **渲染時間增加**: +1.037 ms (+21.5%)
- **變異性增加**: 0.701 ms → 2.536 ms (3.6x)
- **影響較大**: GPU 渲染和 SD 推理競爭 Metal 資源

### 2. GPU 性能優勢

#### 無 SD 環境
- **加速倍數**: 5.62x (27.104 ms / 4.825 ms)
- **FPS 提升**: 36.9 fps → 207.3 fps

#### 有 SD 環境
- **加速倍數**: 4.96x (29.066 ms / 5.862 ms)
- **FPS 提升**: 34.4 fps → 170.6 fps
- **仍遠超即時需求**: 169.5 fps >> 60 fps

### 3. SD 進程隔離的效果

SD img2img 使用 `multiprocessing` 在獨立進程中運行：

**優點**:
- feed/get 操作本身幾乎無開銷 (0.037-0.068 ms)
- 不阻塞主進程渲染循環
- SD 模型載入不影響主程式

**缺點**:
- GPU 資源仍然共用 (Metal backend)
- 渲染時間因 GPU 競爭增加 7-21%
- 變異性增加 (2.8-3.6x)

---

## 效能等級分類

### GPU (Qt OpenGL Metal) + SD - **S 級**
- ✅ 超高幀率 (169.5 fps) 即使開啟 SD
- ✅ 4.96x CPU 加速
- ✅ Metal backend GPU 加速
- ✅ 即時渲染 (5.9 ms/frame)
- ⚠️ SD 競爭導致 21.5% 性能下降
- ⚠️ 變異性增加 (max spike to 27 ms)

### CPU (Numba JIT) + SD - **A 級**
- ✅ SD 影響較小 (7.2%)
- ✅ 變異性增加較少
- ✅ 穩定的即時渲染 (34.3 fps)
- ⚠️ 無法達到高幀率
- ⚠️ 較高延遲 (29 ms)

---

## SD img2img 性能指標

### 生成時間
- **首次生成**: 0.68-0.81 秒 (包含 warm-up)
- **後續生成**: 0.45-0.47 秒
- **初始化等待**: 10.7-11.4 秒 (模型載入)

### 生成頻率
- **Send Interval**: 1.5 秒
- **實際影響**: 僅在 send 時刻有輕微影響
- **顯示更新**: 30 FPS (獨立線程)

---

## 資源競爭分析

### Metal GPU 使用

**Multiverse 渲染器** (主進程):
- Fragment shader 處理
- 4 通道音訊紋理上傳
- Region map 紋理上傳
- Blend 操作
- Read back to CPU

**SD img2img** (獨立進程):
- Diffusion model 推理 (float16)
- VAE encoding/decoding
- LCM scheduler 步驟
- TAESD 快速 VAE

**競爭結果**:
- GPU 版本受影響更大 (21.5% vs 7.2%)
- Max render time 出現 spike (27 ms)
- 但平均仍遠快於 CPU (5.9 ms vs 29.1 ms)

---

## 建議

### 使用場景建議

1. **需要最高幀率 + SD**
   - **推薦**: GPU 版本 (169.5 fps)
   - **原因**: 即使開啟 SD，仍遠超 60 fps 需求

2. **需要穩定性 + SD**
   - **可選**: CPU 版本
   - **原因**: SD 影響較小 (7.2%)，變異性較低

3. **不使用 SD**
   - **強烈推薦**: GPU 版本 (207.3 fps)
   - **原因**: 5.62x 加速，無競爭問題

### 優化建議

#### 短期優化
1. **SD Send Interval 調整**
   - 當前: 1.5 秒
   - 可增加到 2-3 秒減少競爭
   - 視覺變化已足夠緩慢

2. **SD Steps 減少**
   - 當前: 2 steps
   - 可測試 1 step (LCM 支援)
   - 進一步減少 GPU 負擔

#### 長期優化
1. **雙 GPU 架構** (如果硬體支援)
   - Multiverse 在 GPU 0
   - SD 在 GPU 1
   - 完全消除資源競爭

2. **SD 批次處理**
   - 累積多個 frames
   - 一次性處理
   - 減少 GPU 切換開銷

---

## 與無 SD 測試比較

| 指標 | CPU 無 SD | CPU 有 SD | GPU 無 SD | GPU 有 SD |
|------|----------|-----------|-----------|-----------|
| 平均渲染時間 | 27.104 ms | 29.066 ms | 4.825 ms | 5.862 ms |
| 平均 FPS | 36.9 | 34.4 | 207.3 | 170.6 |
| 標準差 | 0.796 ms | 2.250 ms | 0.701 ms | 2.536 ms |
| 最大時間 | 30.020 ms | 44.292 ms | 6.265 ms | 27.173 ms |
| SD 影響 | - | +7.2% | - | +21.5% |
| GPU 加速 | - | - | 5.62x | 4.96x |

---

## 結論

**開啟 Stable Diffusion 後，GPU 版本仍然展現壓倒性的性能優勢。**

### 核心指標 (WITH SD)
- **4.96x** 加速 (CPU: 29.1 ms vs GPU: 5.9 ms)
- **169.5 fps** 超高幀率 (遠超 60 fps 需求)
- **23.2 ms** 絕對優勢 per frame

### SD 影響分析
- **CPU 受影響較小**: +7.2% (資源分離)
- **GPU 受影響較大**: +21.5% (GPU 競爭)
- **變異性增加**: 兩者都約 3x (GPU 略高)

### 推薦配置
- **預設使用**: GPU 版本 + SD
- **理由**: 即使有 21.5% 性能下降，仍有 169.5 fps
- **SD 參數**: 當前配置 (2 steps, 1.5s interval) 已優化

**GPU 渲染器在所有測試場景中都是最佳選擇，包括開啟 SD 的情況。**

---

**測試執行**: 2025-11-04 23:32
**測試工具**: `benchmark_with_sd.py`
**測試幀數**: 400 frames total (4 tests × 100 frames)
**SD 初始化**: 2 次 (CPU test + GPU test)
**總測試時間**: 約 6 分鐘

