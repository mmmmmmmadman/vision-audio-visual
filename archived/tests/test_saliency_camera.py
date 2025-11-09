#!/usr/bin/env python3
"""
即時相機測試 Spectral Residual Saliency for CV Generation
使用相機輸入測試顯著性檢測的實際效果
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


def visualize_saliency(image, saliency_map, cv_values, fps=0):
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

    # 顯示 CV 值和 FPS
    y_offset = 30
    texts = [
        f"FPS: {fps:.1f}",
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


def main():
    """主測試流程"""
    print("=" * 60)
    print("Spectral Residual Saliency 即時相機測試")
    print("=" * 60)
    print()

    # 開啟相機
    print("開啟相機...")
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("錯誤：無法開啟相機")
        return

    # 設定解析度
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

    actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"相機解析度: {actual_width}x{actual_height}")

    # 創建 Spectral Residual Saliency 檢測器
    print("建立 Spectral Residual Saliency 檢測器...")
    saliency = cv2.saliency.StaticSaliencySpectralResidual_create()

    print("\n開始即時檢測...")
    print("按 'q' 退出")
    print("-" * 60)

    frame_count = 0
    start_time = time.time()
    fps = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            print("錯誤：無法讀取畫面")
            break

        # 計算 FPS
        frame_count += 1
        if frame_count % 10 == 0:
            elapsed = time.time() - start_time
            fps = frame_count / elapsed

        # 縮小到 512x512 以加速處理
        height, width = frame.shape[:2]
        scale = 512 / max(width, height)
        new_width = int(width * scale)
        new_height = int(height * scale)
        small_frame = cv2.resize(frame, (new_width, new_height))

        # 轉灰階
        gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)

        # 計算顯著性
        saliency_start = time.time()
        success, saliency_map = saliency.computeSaliency(gray)
        saliency_time = (time.time() - saliency_start) * 1000

        if not success:
            print("警告：顯著性計算失敗")
            continue

        # 提取 CV 值
        cv_values = analyze_saliency_map(saliency_map, new_width, new_height)

        # 視覺化
        visualization = visualize_saliency(small_frame, saliency_map, cv_values, fps)

        # 顯示處理時間
        cv2.putText(visualization, f"Saliency: {saliency_time:.1f}ms",
                    (10, new_height - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

        # 顯示結果
        cv2.imshow("Saliency CV Test", visualization)

        # 按 'q' 退出
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # 清理
    cap.release()
    cv2.destroyAllWindows()

    print("\n" + "=" * 60)
    print("測試完成")
    print(f"平均 FPS: {fps:.1f}")
    print("=" * 60)


if __name__ == "__main__":
    main()
