#!/usr/bin/env python3
"""
測試 Spectral Residual Saliency for CV Generation
驗證顯著性檢測對 SD 畫面的適用性
"""

import cv2
import numpy as np
import time


def analyze_saliency_map(saliency_map, width, height):
    """
    從顯著性圖提取 CV 值

    Returns:
        dict: {
            'seq1': 顯著區域重心 X (0.0-1.0),
            'seq2': 顯著區域重心 Y (0.0-1.0),
            'env1': 顯著性總能量 (0.0-1.0),
            'env2': 顯著區域數量 (0.0-1.0),
            'env3': 顯著性分散程度 (0.0-1.0)
        }
    """
    # 確保 saliency_map 是 0-255 範圍
    if saliency_map.max() <= 1.0:
        saliency_map = (saliency_map * 255).astype(np.uint8)

    # 二值化以找到顯著區域（使用 Otsu 自動閾值）
    _, binary = cv2.threshold(saliency_map, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # ENV1: 顯著性總能量（平均顯著性值）
    total_energy = np.mean(saliency_map) / 255.0

    # 找到連通區域
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary, connectivity=8)

    # 過濾掉背景（label 0）和太小的區域
    min_area = (width * height) * 0.001  # 至少佔畫面 0.1%
    significant_regions = []

    for i in range(1, num_labels):  # 跳過背景
        area = stats[i, cv2.CC_STAT_AREA]
        if area >= min_area:
            significant_regions.append({
                'centroid': centroids[i],
                'area': area
            })

    # ENV2: 顯著區域數量（正規化到 0-1，假設最多 10 個區域）
    num_regions = len(significant_regions)
    env2 = min(num_regions / 10.0, 1.0)

    if len(significant_regions) == 0:
        # 沒有顯著區域，返回畫面中心
        return {
            'seq1': 0.5,
            'seq2': 0.5,
            'env1': total_energy,
            'env2': 0.0,
            'env3': 0.0
        }

    # SEQ1, SEQ2: 加權重心（依區域面積加權）
    total_area = sum(r['area'] for r in significant_regions)
    weighted_x = sum(r['centroid'][0] * r['area'] for r in significant_regions) / total_area
    weighted_y = sum(r['centroid'][1] * r['area'] for r in significant_regions) / total_area

    seq1 = weighted_x / width
    seq2 = weighted_y / height

    # ENV3: 顯著性分散程度（標準差）
    # 計算各區域到加權重心的距離
    if len(significant_regions) > 1:
        distances = []
        for r in significant_regions:
            cx, cy = r['centroid']
            dist = np.sqrt((cx - weighted_x)**2 + (cy - weighted_y)**2)
            distances.append(dist)

        # 標準差，正規化到畫面對角線長度
        diagonal = np.sqrt(width**2 + height**2)
        spread = np.std(distances) / diagonal
    else:
        spread = 0.0

    return {
        'seq1': float(np.clip(seq1, 0.0, 1.0)),
        'seq2': float(np.clip(seq2, 0.0, 1.0)),
        'env1': float(np.clip(total_energy, 0.0, 1.0)),
        'env2': float(np.clip(env2, 0.0, 1.0)),
        'env3': float(np.clip(spread, 0.0, 1.0))
    }


def visualize_saliency(image, saliency_map, cv_values):
    """視覺化顯著性圖和 CV 值"""
    height, width = image.shape[:2]

    # 確保 saliency_map 是 0-255 範圍
    if saliency_map.max() <= 1.0:
        saliency_map = (saliency_map * 255).astype(np.uint8)

    # 轉換灰階圖為 BGR
    if len(image.shape) == 2:
        image_bgr = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    else:
        image_bgr = image.copy()

    # 顯著性圖轉熱圖
    saliency_colored = cv2.applyColorMap(saliency_map, cv2.COLORMAP_JET)

    # 疊加顯著性圖到原圖
    overlay = cv2.addWeighted(image_bgr, 0.6, saliency_colored, 0.4, 0)

    # 繪製重心位置
    centroid_x = int(cv_values['seq1'] * width)
    centroid_y = int(cv_values['seq2'] * height)
    cv2.circle(overlay, (centroid_x, centroid_y), 20, (0, 255, 0), 2)
    cv2.circle(overlay, (centroid_x, centroid_y), 3, (0, 255, 0), -1)

    # 繪製十字線
    cv2.line(overlay, (centroid_x, 0), (centroid_x, height), (0, 255, 0), 1)
    cv2.line(overlay, (0, centroid_y), (width, centroid_y), (0, 255, 0), 1)

    # 顯示 CV 值
    y_offset = 30
    texts = [
        f"SEQ1 (X): {cv_values['seq1']:.3f}",
        f"SEQ2 (Y): {cv_values['seq2']:.3f}",
        f"ENV1 (Energy): {cv_values['env1']:.3f}",
        f"ENV2 (Regions): {cv_values['env2']:.3f}",
        f"ENV3 (Spread): {cv_values['env3']:.3f}"
    ]

    for i, text in enumerate(texts):
        cv2.putText(overlay, text, (10, y_offset + i * 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    return overlay


def test_with_synthetic_image():
    """使用合成圖片測試"""
    print("生成合成測試圖片...")

    # 創建 512x512 測試圖片
    width, height = 512, 512
    image = np.zeros((height, width, 3), dtype=np.uint8)

    # 添加一些幾何形狀
    # 左上：大圓
    cv2.circle(image, (150, 150), 80, (200, 100, 50), -1)

    # 右上：矩形
    cv2.rectangle(image, (350, 80), (480, 220), (50, 150, 200), -1)

    # 左下：三角形
    pts = np.array([[100, 400], [200, 500], [50, 480]], np.int32)
    cv2.fillPoly(image, [pts], (100, 200, 100))

    # 中心：小圓
    cv2.circle(image, (256, 300), 30, (255, 255, 255), -1)

    # 添加噪點
    noise = np.random.randint(0, 30, (height, width, 3), dtype=np.uint8)
    image = cv2.add(image, noise)

    return image


def test_saliency(image):
    """測試顯著性檢測"""
    height, width = image.shape[:2]

    # 轉灰階
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    # 創建 Spectral Residual Saliency 檢測器
    print("建立 Spectral Residual Saliency 檢測器...")
    saliency = cv2.saliency.StaticSaliencySpectralResidual_create()

    # 計算顯著性
    print("計算顯著性圖...")
    start_time = time.time()
    success, saliency_map = saliency.computeSaliency(gray)
    elapsed_ms = (time.time() - start_time) * 1000

    if not success:
        print("錯誤：顯著性計算失敗")
        return None

    print(f"計算時間：{elapsed_ms:.2f} ms")

    # 提取 CV 值
    print("提取 CV 值...")
    cv_values = analyze_saliency_map(saliency_map, width, height)

    print("\nCV 值：")
    print(f"  SEQ1 (重心 X):       {cv_values['seq1']:.3f}")
    print(f"  SEQ2 (重心 Y):       {cv_values['seq2']:.3f}")
    print(f"  ENV1 (總能量):       {cv_values['env1']:.3f}")
    print(f"  ENV2 (區域數):       {cv_values['env2']:.3f}")
    print(f"  ENV3 (分散度):       {cv_values['env3']:.3f}")

    # 視覺化
    print("\n視覺化結果...")
    visualization = visualize_saliency(image, saliency_map, cv_values)

    return visualization, saliency_map, cv_values


def main():
    """主測試流程"""
    print("=" * 60)
    print("Spectral Residual Saliency CV Generation 測試")
    print("=" * 60)
    print()

    # 測試 1: 合成圖片
    print("測試 1: 合成幾何圖片")
    print("-" * 60)
    test_image = test_with_synthetic_image()
    result1, saliency1, cv1 = test_saliency(test_image)

    # 顯示結果
    cv2.imshow("Original", test_image)
    cv2.imshow("Saliency + CV", result1)

    print("\n按任意鍵測試下一張圖片...")
    cv2.waitKey(0)

    # 測試 2: 隨機噪點（最壞情況）
    print("\n測試 2: 隨機噪點（最壞情況）")
    print("-" * 60)
    noise_image = np.random.randint(0, 256, (512, 512, 3), dtype=np.uint8)
    result2, saliency2, cv2_vals = test_saliency(noise_image)

    cv2.imshow("Original", noise_image)
    cv2.imshow("Saliency + CV", result2)

    print("\n按任意鍵測試下一張圖片...")
    cv2.waitKey(0)

    # 測試 3: 漸層（平滑情況）
    print("\n測試 3: 平滑漸層")
    print("-" * 60)
    gradient = np.zeros((512, 512, 3), dtype=np.uint8)
    for i in range(512):
        gradient[:, i] = [i // 2, 255 - i // 2, 128]

    result3, saliency3, cv3 = test_saliency(gradient)

    cv2.imshow("Original", gradient)
    cv2.imshow("Saliency + CV", result3)

    print("\n按任意鍵關閉視窗...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    print("\n" + "=" * 60)
    print("測試完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
