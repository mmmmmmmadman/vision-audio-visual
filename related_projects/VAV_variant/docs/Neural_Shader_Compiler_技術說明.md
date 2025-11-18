# Neural Shader Compiler 技術說明

## 概述

Neural Shader Compiler 是一種創新的音頻可視化技術，利用 **大型語言模型 (LLM)** 生成 **GLSL Shader 代碼**，而非直接生成影像。這種方法實現了高效能、低延遲的即時音頻視覺化。

---

## 核心概念

### 什麼是 GLSL Shader？

- **GLSL** (OpenGL Shading Language)：在 GPU 上執行的圖形程式語言
- 直接控制每個像素的渲染方式
- 支援程序化生成，可創造無限變化的視覺效果
- 原生 GPU 執行，效能極高

---

## 技術架構比較

### 傳統 AI 生圖方式

```
音頻參數 → AI模型 → 生成完整影像 → 顯示
```

**限制：**
- 每一幀都需要 AI 重新生成圖片
- 高延遲（通常數秒）
- 大量記憶體佔用
- 難以達到即時效果（通常 < 10 fps）

### Neural Shader Compiler 方式

```
音頻參數 → LLM → 生成 GLSL 代碼 → GPU 編譯執行 → 即時渲染
```

**優勢：**
- LLM 只需生成代碼（一次性或低頻率）
- GPU 執行代碼進行即時渲染
- 可達 60-120 fps 的流暢效果
- 極低記憶體佔用

---

## 核心優勢

### 1. 速度革命性提升

- **GLSL 在 GPU 上原生執行**，無需 AI 推理延遲
- 可達 **60-120 fps** 的即時渲染
- 音頻反應延遲極低（< 16ms）

### 2. 無限創意潛力

- **程序化生成**：每一幀都可以動態變化
- 可創造傳統 AI 生圖無法達成的效果：
  - 粒子系統
  - 流體模擬
  - 複雜幾何變形
  - 即時光照效果

### 3. 記憶體效率

- 只需儲存 **代碼文本**（通常 < 10 KB）
- 不需儲存大量預生成影像
- 一段 shader 代碼可生成無限變化

---

## 實際運作示例

### 輸入場景
**音頻特徵：** 低頻強烈、高頻微弱

### LLM 生成的 GLSL 代碼

```glsl
// 提取低音強度
float bass = audioData[0] * 2.0;

// 根據低音產生扭曲效果
vec2 distortion = sin(uv * bass * 10.0) * 0.1;
vec2 distortedUV = uv + distortion;

// 混合顏色隨低音變化
vec3 color = mix(vec3(1.0, 0.0, 0.0), vec3(0.5, 0.0, 0.5), bass);

// 輸出最終顏色
fragColor = vec4(color, 1.0);
```

### 渲染結果
GPU 即時執行這段代碼，產生**隨低音震動的紫紅色波紋效果**，每幀自動更新。

---

## 技術挑戰

### 1. LLM 需理解 GLSL 語法
- 需要訓練或微調 LLM 以生成有效的 GLSL 代碼
- 代碼必須符合 GLSL 版本規範（如 GLSL 330, 400 等）

### 2. 代碼驗證機制
- 需要即時編譯驗證，防止語法錯誤
- 錯誤處理與降級策略
- 安全性檢查（防止無限迴圈等）

### 3. 音頻參數到視覺效果的映射學習
- 如何將音頻特徵（頻譜、節奏、音調）映射到視覺參數
- 需要建立訓練數據集或提示工程
- 風格控制與一致性保持

---

## 與 VAV 項目的潛在應用

### 當前 VAV 架構
VAV 目前使用預設的 shader 或固定效果進行音頻可視化。

### Neural Shader Compiler 整合方案

#### 方案 1：離線代碼生成
```python
# 音頻分析
audio_features = analyze_audio(audio_data)

# LLM 生成 shader 代碼
shader_code = llm.generate_shader(
    audio_features=audio_features,
    style="psychedelic",
    complexity="high"
)

# 編譯並載入到 GPU
shader = compile_glsl(shader_code)
renderer.load_shader(shader)
```

#### 方案 2：即時動態調整
```python
# 根據音頻動態調整 shader 參數
for frame in audio_stream:
    features = extract_features(frame)

    # 小幅調整現有 shader 或生成新變體
    if should_regenerate(features):
        shader_code = llm.adjust_shader(
            current_shader=current_shader,
            new_features=features
        )
        update_shader(shader_code)
```

#### 方案 3：預設 Shader Pool + AI 混合
```python
# 建立 AI 生成的 shader 池
shader_pool = [
    llm.generate_shader(style="ambient"),
    llm.generate_shader(style="aggressive"),
    llm.generate_shader(style="minimal"),
]

# 根據音頻特徵動態選擇或混合
current_shader = blend_shaders(
    shader_pool,
    weights=calculate_weights(audio_features)
)
```

---

## 實作考量

### 技術棧建議

| 組件 | 技術選擇 |
|------|---------|
| LLM | GPT-4, Claude, CodeLlama |
| Shader 編譯 | PyOpenGL, ModernGL |
| 音頻分析 | Librosa, Essentia |
| 渲染管線 | OpenGL 3.3+, Vulkan |

### 效能目標
- LLM 生成延遲：< 5 秒（離線）或 < 500ms（即時）
- Shader 編譯時間：< 100ms
- 渲染幀率：60 fps（目標）/ 30 fps（最低）

### 安全性
- Shader 代碼沙箱執行
- 編譯超時限制
- GPU 記憶體使用監控

---

## 參考資源

- [GLSL 官方規範](https://www.khronos.org/opengl/wiki/Core_Language_(GLSL))
- [Shadertoy](https://www.shadertoy.com/) - GLSL Shader 範例庫
- [The Book of Shaders](https://thebookofshaders.com/) - GLSL 學習資源

---

## 版本歷史

- **2025-10-19**：初版文件建立，記錄核心概念與 VAV 整合方案

---

## 附註

此技術仍在探索階段，需要進一步實驗驗證其在 VAV 項目中的可行性與效能表現。建議從簡單的 shader 生成開始，逐步擴展到複雜的即時生成系統。
