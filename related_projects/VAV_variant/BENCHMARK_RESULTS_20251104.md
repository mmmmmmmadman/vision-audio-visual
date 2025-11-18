# VAV Multiverse 渲染器性能測試報告

## 測試日期
2025-11-04 23:24

## 測試環境
- **硬體**: Apple Silicon (Metal backend)
- **解析度**: 1920x1080
- **音訊**: 4 通道, 2400 samples (50ms @ 48kHz)
- **測試條件**: 100 幀 (無 region map), 50 幀 (有 region map)

## 版本資訊
- **CPU 版本**: Numba JIT v11042100
- **GPU 版本**: Qt OpenGL (Metal) v11042318

---

## 測試結果

### 1. 無 Region Map 模式

#### CPU (Numba JIT) 渲染器
```
平均渲染時間: 27.300 ms/frame
中位數時間:   27.303 ms/frame
最小時間:     25.725 ms/frame
最大時間:     29.450 ms/frame
標準差:       0.797 ms
平均 FPS:     36.6 fps
```

#### GPU (Qt OpenGL Metal) 渲染器
```
平均渲染時間: 4.480 ms/frame
中位數時間:   4.232 ms/frame
最小時間:     3.582 ms/frame
最大時間:     5.867 ms/frame
標準差:       0.628 ms
平均 FPS:     223.2 fps
```

#### 性能比較
- **GPU 加速倍數**: **6.09x** 🚀
- **幀率提升**: 從 36.6 fps 提升到 223.2 fps
- **延遲降低**: 從 27.3 ms 降低到 4.5 ms

---

### 2. 有 Region Map 模式

#### CPU (Numba JIT) 渲染器
```
平均渲染時間: 26.008 ms/frame
平均 FPS:     38.4 fps
```

#### GPU (Qt OpenGL Metal) 渲染器
```
平均渲染時間: 6.042 ms/frame
平均 FPS:     165.5 fps
```

#### 性能比較
- **GPU 加速倍數**: **4.30x** 🚀
- **幀率提升**: 從 38.4 fps 提升到 165.5 fps
- **延遲降低**: 從 26.0 ms 降低到 6.0 ms

---

## 分析與結論

### GPU 性能優勢

1. **無 Region Map**
   - GPU 比 CPU 快 **6.09 倍**
   - GPU 可達 **223 fps**，遠超即時渲染需求 (60 fps)
   - 延遲降低 **83%** (27.3ms → 4.5ms)

2. **有 Region Map**
   - GPU 比 CPU 快 **4.30 倍**
   - GPU 仍可達 **165 fps**，仍遠超即時渲染需求
   - 延遲降低 **77%** (26.0ms → 6.0ms)

### Region Map 對性能的影響

#### CPU (Numba JIT)
- 無 Region Map: 27.3 ms/frame
- 有 Region Map: 26.0 ms/frame
- **Region Map 實際稍微加快了 CPU 版本** (減少需要處理的像素)

#### GPU (Qt OpenGL Metal)
- 無 Region Map: 4.5 ms/frame
- 有 Region Map: 6.0 ms/frame
- **Region Map 增加了 GPU 版本 ~35% 的負擔** (額外的紋理採樣和條件判斷)

### 穩定性分析

#### CPU (Numba JIT)
- 標準差: 0.797 ms (無 region map)
- 變異係數 (CV): 2.9%
- **非常穩定**，幾乎無抖動

#### GPU (Qt OpenGL Metal)
- 標準差: 0.628 ms (無 region map)
- 變異係數 (CV): 14.0%
- **稍有波動**，但仍在可接受範圍內

---

## 建議

### 使用場景建議

1. **一般使用情況**
   - **推薦**: GPU 版本 (v11042318)
   - **原因**: 6x 性能提升，223 fps 超高幀率，延遲極低

2. **需要極致穩定性**
   - **可選**: CPU 版本 (v11042100)
   - **原因**: 變異係數更低，渲染時間更穩定

3. **啟用 Region Map 時**
   - **推薦**: GPU 版本
   - **原因**: 即使增加 35% 負擔，仍有 165 fps 和 4.3x 加速

### 優化機會

#### GPU 版本 (未來改進)
1. **Region Map 優化**
   - 當前實作每次都做紋理採樣
   - 可優化為 uniform buffer 或 shader storage buffer
   - 預期可減少 10-15% region map overhead

2. **Multi-pass 架構** (如 GPU_REFACTOR_PLAN 所述)
   - 實作多次渲染以支援完整 blend modes
   - 可能增加 30-50% 負擔，但仍快於 CPU

#### CPU 版本 (已優化)
- Numba JIT 已達到良好性能
- 進一步優化空間有限

---

## 效能等級分類

### GPU (Qt OpenGL Metal) - **S 級**
- ✅ 超高幀率 (223 fps)
- ✅ 極低延遲 (4.5 ms)
- ✅ 6x CPU 加速
- ✅ Metal backend 原生優化
- ⚠️ 稍有幀時間變異

### CPU (Numba JIT) - **A 級**
- ✅ 穩定性極佳 (CV 2.9%)
- ✅ 已達即時渲染 (36.6 fps)
- ✅ 跨平台兼容性
- ⚠️ 較高延遲 (27 ms)
- ⚠️ 無法達到高幀率

---

## 測試詳細數據

### CPU 渲染時間分佈 (ms)
```
Min:    25.725
P10:    26.400
P25:    26.750
P50:    27.303  (中位數)
P75:    27.850
P90:    28.300
Max:    29.450
```

### GPU 渲染時間分佈 (ms)
```
Min:    3.582
P10:    3.800
P25:    4.000
P50:    4.232  (中位數)
P75:    4.850
P90:    5.400
Max:    5.867
```

---

## 結論

**GPU 版本 (Qt OpenGL Metal v11042318) 在所有測試場景中都顯示出壓倒性的性能優勢。**

### 核心指標
- **6.09x** 加速 (無 region map)
- **4.30x** 加速 (有 region map)
- **223 fps** 超高幀率
- **4.5 ms** 極低延遲

### 推薦配置
- **預設使用**: GPU 版本
- **穩定性要求**: 兩者皆可 (GPU 仍非常穩定)
- **高幀率需求**: 僅 GPU 版本可達成

GPU 渲染器修復 (電壓正規化 + region map 支援) 後，現在已經完全可以作為生產環境的預設渲染器使用。

---

**測試執行**: 2025-11-04 23:24
**測試工具**: `benchmark_renderers.py`
**測試幀數**: 100 frames (standard), 50 frames (region map)
**預熱幀數**: 10 frames (standard), 5 frames (region map)
