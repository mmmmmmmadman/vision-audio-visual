#!/usr/bin/env python3
"""生成16個組合：4張主圖 × 4個影片，每個影片拉伸填充主圖的4個亮度區域"""

import cv2
import numpy as np
import sys

def create_video_stretched(primary_idx, video_idx):
    """將單一影片拉伸填充到主圖的4個亮度區域"""

    # 載入主圖
    primary = cv2.imread(f'/Users/madzine/Desktop/{primary_idx}.jpeg')
    if primary is None:
        print(f"  錯誤: 無法載入 {primary_idx}.jpeg")
        return False

    # 載入影片
    cap = cv2.VideoCapture(f'/Users/madzine/Desktop/{video_idx}.MOV')
    if not cap.isOpened():
        print(f"  錯誤: 無法載入 {video_idx}.MOV")
        return False

    # 取得影片資訊
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # 輸出解析度使用主圖大小
    out_h, out_w = primary.shape[:2]
    print(f"  解析度: {out_w}x{out_h}, 幀數: {frame_count}")

    # 計算主圖的亮度區域
    pri_gray = cv2.cvtColor(primary, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    thresholds = [0.25, 0.5, 0.75]
    pri_regions = np.zeros((out_h, out_w), dtype=np.uint8)
    for i, thresh in enumerate(thresholds):
        pri_regions[pri_gray >= thresh] = i + 1

    # 計算每個區域的bounding box
    bboxes = []
    for region_id in range(4):
        mask = pri_regions == region_id
        ys, xs = np.where(mask)
        if len(ys) > 0:
            bboxes.append((ys.min(), ys.max()+1, xs.min(), xs.max()+1))
        else:
            bboxes.append((0, out_h, 0, out_w))

    # 建立輸出影片
    output_path = f'/Users/madzine/Documents/VAV/V2/p{primary_idx}_v{video_idx}.mp4'
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (out_w, out_h))

    # 處理每一幀
    for frame_idx in range(frame_count):
        ret, frame = cap.read()
        if not ret:
            break

        result = np.zeros((out_h, out_w, 3), dtype=np.uint8)

        # 將影片拉伸填充到每個區域
        for region_id in range(4):
            y_min, y_max, x_min, x_max = bboxes[region_id]
            bbox_h = y_max - y_min
            bbox_w = x_max - x_min

            if bbox_h > 0 and bbox_w > 0:
                stretched = cv2.resize(frame, (bbox_w, bbox_h))
                mask = pri_regions == region_id

                for y in range(y_min, y_max):
                    for x in range(x_min, x_max):
                        if mask[y, x]:
                            result[y, x] = stretched[y - y_min, x - x_min]

        out.write(result)

        if frame_idx % 100 == 0:
            print(f"  {frame_idx}/{frame_count}...")

    cap.release()
    out.release()
    print(f"  完成: p{primary_idx}_v{video_idx}.mp4")
    return True

# 生成16個組合
print("開始生成16個組合...")
for p in range(1, 5):
    for v in range(1, 5):
        print(f"\n=== 主圖 {p}.jpeg ← 影片 {v}.MOV ===")
        create_video_stretched(p, v)

print("\n全部完成！")
