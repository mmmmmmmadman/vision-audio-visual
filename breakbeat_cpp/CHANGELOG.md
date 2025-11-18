# Breakbeat Engine 開發進度

## 2025-11-18

### 修正與優化

#### 1. 移除失敗的 Random 功能
- 移除 random_amount 參數及相關程式碼
- 移除 set_random_amount 函式
- 移除 Python 綁定
- 移除 GUI 中的 Random 滑桿
- 回復到穩定的工作版本

#### 2. Fill 功能優化
調整 Fill 參數映射使效果更明顯

**Fill 長度**
- 0-25%: 3-7 steps
- 25-60%: 7-14 steps
- 60-100%: 14-16 steps

**Fill 密度**
- 0-25%: 1 種鼓 60% 密度
- 25-60%: 2 種鼓 75% 密度
- 60-100%: 3 種鼓 90% 密度

**Fill 頻率**
- 0-25%: 每 8 bar
- 25-60%: 每 4 bar
- 60-100%: 每 2 bar

**Crash 觸發**
- 50% 以上 fill_amount 時 70% 機率在結尾加 crash

### 已知問題

#### 主節奏音色缺乏隨機性
- 目前主節奏 (generate_pattern) 使用固定 variation 選擇樣本
- Latin pattern 和 Fill 有隨機選擇機制
- 需要為主節奏增加音色隨機選擇功能

### 待處理項目

1. 實作主節奏音色隨機選擇
2. 測試參數變化時的點擊聲問題
3. 優化 BPM 變化響應速度

### 程式架構分析

#### 隨機要素分布
1. Gain 隨機化 - 所有鼓點都有音量範圍變化
2. 條件觸發 - Pattern 中可選元素的機率控制
3. 樣本選擇 - get_sample 函式的隨機機制
4. Rest pattern - shuffle 打亂位置
5. Fill - 密度 鼓類型 gain 都有隨機

#### 隨機數生成器
- 使用 std::mt19937
- std::random_device 初始化種子
- 所有隨機操作共用同一個 rng_
