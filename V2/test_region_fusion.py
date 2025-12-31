#!/usr/bin/env python3
"""
VAV V2 雙相機區域融合測試程式

目標效果：
「第二相機是彩色紙，把這彩色紙按亮度剪成四塊碎片，填入第一相機的四個亮度區域中」

測試不同的演算法來達成「剪碎」的視覺效果。
"""

import cv2
import numpy as np
from pathlib import Path
import argparse

# 預設閾值
DEFAULT_THRESHOLDS = [0.25, 0.5, 0.75]


def load_image(path: str) -> np.ndarray:
    """載入圖片，確保是 BGR 格式"""
    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError(f"無法載入圖片: {path}")
    return img


def get_brightness(img: np.ndarray) -> np.ndarray:
    """計算圖片亮度 (0-1)"""
    # 使用 BT.601 標準
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return gray.astype(np.float32) / 255.0


def get_region_map(brightness: np.ndarray, thresholds: list) -> np.ndarray:
    """根據亮度和閾值計算區域圖 (0-3)"""
    region_map = np.zeros_like(brightness, dtype=np.uint8)
    region_map[brightness >= thresholds[2]] = 3
    region_map[(brightness >= thresholds[1]) & (brightness < thresholds[2])] = 2
    region_map[(brightness >= thresholds[0]) & (brightness < thresholds[1])] = 1
    # region 0 已經是預設值
    return region_map


def visualize_regions(img: np.ndarray, region_map: np.ndarray) -> np.ndarray:
    """將區域圖可視化，疊加在原圖上"""
    # 區域顏色 (BGR)
    colors = [
        (255, 0, 0),    # 區域 0: 藍色
        (0, 255, 0),    # 區域 1: 綠色
        (0, 255, 255),  # 區域 2: 黃色
        (0, 0, 255),    # 區域 3: 紅色
    ]

    overlay = img.copy()
    for i, color in enumerate(colors):
        mask = region_map == i
        overlay[mask] = cv2.addWeighted(
            img[mask].reshape(-1, 3), 0.5,
            np.array([color] * mask.sum(), dtype=np.uint8), 0.5,
            0
        ).reshape(-1, 3)

    return overlay


# ============================================================================
# 不同的融合演算法
# ============================================================================

def method_0_baseline(primary: np.ndarray, secondary: np.ndarray,
                       thresholds: list) -> np.ndarray:
    """
    方法 0: 基準 - 同位置取樣 + 區域匹配檢查

    如果副相機像素的區域與主相機匹配，顯示副相機；否則顯示純色。
    這是目前 shader 的實作方式。

    問題：匹配處還是連續的原圖，沒有破碎感。
    """
    primary_brightness = get_brightness(primary)
    secondary_brightness = get_brightness(secondary)

    primary_regions = get_region_map(primary_brightness, thresholds)
    secondary_regions = get_region_map(secondary_brightness, thresholds)

    # 區域顏色
    region_hues = [
        np.array([180, 50, 50], dtype=np.uint8),   # 區域 0: 深藍
        np.array([50, 180, 50], dtype=np.uint8),   # 區域 1: 綠
        np.array([50, 180, 180], dtype=np.uint8),  # 區域 2: 黃
        np.array([50, 50, 180], dtype=np.uint8),   # 區域 3: 紅
    ]

    result = np.zeros_like(primary)

    for region_id in range(4):
        # 主相機中屬於這個區域的像素
        primary_mask = primary_regions == region_id
        # 副相機中屬於這個區域的像素
        secondary_mask = secondary_regions == region_id

        # 匹配的像素位置
        match_mask = primary_mask & secondary_mask
        # 不匹配的位置
        no_match_mask = primary_mask & ~secondary_mask

        # 匹配處顯示副相機內容
        result[match_mask] = secondary[match_mask]
        # 不匹配處顯示純色
        result[no_match_mask] = region_hues[region_id]

    return result


def method_1_scatter_fill(primary: np.ndarray, secondary: np.ndarray,
                          thresholds: list) -> np.ndarray:
    """
    方法 1: 散射填充

    真正的「剪碎」：
    1. 收集副相機中每個區域的所有像素
    2. 將這些像素「填入」主相機對應區域的位置

    實現方式：對於主相機區域 N 的每個位置，從副相機區域 N 的像素池中取樣。
    """
    primary_brightness = get_brightness(primary)
    secondary_brightness = get_brightness(secondary)

    primary_regions = get_region_map(primary_brightness, thresholds)
    secondary_regions = get_region_map(secondary_brightness, thresholds)

    result = np.zeros_like(primary)

    for region_id in range(4):
        # 主相機中這個區域的所有位置
        primary_positions = np.where(primary_regions == region_id)
        primary_count = len(primary_positions[0])

        if primary_count == 0:
            continue

        # 副相機中這個區域的所有像素值
        secondary_mask = secondary_regions == region_id
        secondary_pixels = secondary[secondary_mask]
        secondary_count = len(secondary_pixels)

        if secondary_count == 0:
            # 如果副相機沒有這個區域，用灰色填充
            result[primary_positions] = [128, 128, 128]
            continue

        # 循環使用副相機的像素來填充主相機的位置
        # 這會產生重複但打亂的效果
        indices = np.arange(primary_count) % secondary_count
        # 加入隨機打亂
        np.random.seed(region_id * 1000)  # 固定種子確保一致性
        np.random.shuffle(indices)

        result[primary_positions] = secondary_pixels[indices]

    return result


def method_2_uv_remap(primary: np.ndarray, secondary: np.ndarray,
                      thresholds: list) -> np.ndarray:
    """
    方法 2: 邊界框拉伸填滿

    1. 提取副相機區域 N 的邊界框內容
    2. 拉伸到主相機區域 N 的邊界框大小
    3. 用主相機區域 N 的遮罩貼上

    這樣副相機的碎片會被「整塊拉伸」填入主相機對應區域。
    """
    h, w = primary.shape[:2]
    primary_brightness = get_brightness(primary)
    secondary_brightness = get_brightness(secondary)

    primary_regions = get_region_map(primary_brightness, thresholds)
    secondary_regions = get_region_map(secondary_brightness, thresholds)

    result = np.zeros_like(primary)

    for region_id in range(4):
        # 主相機區域的邊界框
        primary_mask = primary_regions == region_id
        primary_ys, primary_xs = np.where(primary_mask)

        if len(primary_ys) == 0:
            continue

        p_y_min, p_y_max = primary_ys.min(), primary_ys.max() + 1
        p_x_min, p_x_max = primary_xs.min(), primary_xs.max() + 1
        p_h = p_y_max - p_y_min
        p_w = p_x_max - p_x_min

        # 副相機區域的邊界框
        secondary_mask = secondary_regions == region_id
        secondary_ys, secondary_xs = np.where(secondary_mask)

        if len(secondary_ys) == 0:
            result[primary_mask] = [128, 128, 128]
            continue

        s_y_min, s_y_max = secondary_ys.min(), secondary_ys.max() + 1
        s_x_min, s_x_max = secondary_xs.min(), secondary_xs.max() + 1

        # 提取副相機區域的邊界框內容
        secondary_crop = secondary[s_y_min:s_y_max, s_x_min:s_x_max].copy()

        # 拉伸到主相機區域的邊界框大小
        secondary_resized = cv2.resize(secondary_crop, (p_w, p_h), interpolation=cv2.INTER_LINEAR)

        # 建立主相機區域在邊界框內的局部遮罩
        local_mask = primary_mask[p_y_min:p_y_max, p_x_min:p_x_max]

        # 用遮罩貼上
        result[p_y_min:p_y_max, p_x_min:p_x_max][local_mask] = secondary_resized[local_mask]

    return result


def method_3_tile_shuffle(primary: np.ndarray, secondary: np.ndarray,
                          thresholds: list, tile_size: int = 16) -> np.ndarray:
    """
    方法 3: 瓷磚打亂

    1. 把副相機分成小方塊 (tiles)
    2. 根據每個方塊的平均亮度分類到區域
    3. 把這些方塊填入主相機對應區域的位置

    這會產生真正的「碎片」視覺效果。
    """
    h, w = primary.shape[:2]
    primary_brightness = get_brightness(primary)
    primary_regions = get_region_map(primary_brightness, thresholds)

    # 計算副相機每個 tile 的區域
    secondary_brightness = get_brightness(secondary)

    # 收集每個區域的 tiles
    region_tiles = {0: [], 1: [], 2: [], 3: []}

    for ty in range(0, h - tile_size + 1, tile_size):
        for tx in range(0, w - tile_size + 1, tile_size):
            tile = secondary[ty:ty+tile_size, tx:tx+tile_size]
            tile_brightness = secondary_brightness[ty:ty+tile_size, tx:tx+tile_size]
            avg_brightness = np.mean(tile_brightness)

            # 決定這個 tile 屬於哪個區域
            if avg_brightness >= thresholds[2]:
                region = 3
            elif avg_brightness >= thresholds[1]:
                region = 2
            elif avg_brightness >= thresholds[0]:
                region = 1
            else:
                region = 0

            region_tiles[region].append(tile)

    result = np.zeros_like(primary)
    tile_indices = {0: 0, 1: 0, 2: 0, 3: 0}

    # 打亂每個區域的 tiles
    for region_id in range(4):
        if region_tiles[region_id]:
            np.random.seed(region_id * 1000)
            np.random.shuffle(region_tiles[region_id])

    # 填充
    for ty in range(0, h - tile_size + 1, tile_size):
        for tx in range(0, w - tile_size + 1, tile_size):
            # 這個位置在主相機中屬於哪個區域？（取中心點）
            center_y = ty + tile_size // 2
            center_x = tx + tile_size // 2
            region = primary_regions[center_y, center_x]

            # 從對應區域的 tile 池中取一個
            tiles = region_tiles[region]
            if tiles:
                idx = tile_indices[region] % len(tiles)
                result[ty:ty+tile_size, tx:tx+tile_size] = tiles[idx]
                tile_indices[region] += 1
            else:
                # 沒有對應區域的 tile，用灰色
                result[ty:ty+tile_size, tx:tx+tile_size] = 128

    return result


def method_4_brightness_swap(primary: np.ndarray, secondary: np.ndarray,
                              thresholds: list) -> np.ndarray:
    """
    方法 4: 亮度交換

    主相機決定「形狀」，副相機決定「顏色」。
    對於主相機區域 N 的每個像素：
    - 找一個副相機中亮度相似的像素（也在區域 N）
    - 用那個像素的顏色

    這樣會把副相機的顏色「撒」到主相機的形狀上。
    """
    h, w = primary.shape[:2]
    primary_brightness = get_brightness(primary)
    secondary_brightness = get_brightness(secondary)

    primary_regions = get_region_map(primary_brightness, thresholds)
    secondary_regions = get_region_map(secondary_brightness, thresholds)

    result = np.zeros_like(primary)

    for region_id in range(4):
        # 收集副相機這個區域的像素及其亮度
        secondary_mask = secondary_regions == region_id
        secondary_positions = np.where(secondary_mask)

        if len(secondary_positions[0]) == 0:
            # 沒有副相機像素，用灰色
            primary_mask = primary_regions == region_id
            result[primary_mask] = [128, 128, 128]
            continue

        secondary_brightnesses = secondary_brightness[secondary_mask]
        secondary_colors = secondary[secondary_mask]

        # 按亮度排序
        sorted_indices = np.argsort(secondary_brightnesses)
        sorted_brightnesses = secondary_brightnesses[sorted_indices]
        sorted_colors = secondary_colors[sorted_indices]

        # 對主相機這個區域的每個像素
        primary_mask = primary_regions == region_id
        primary_ys, primary_xs = np.where(primary_mask)

        for py, px in zip(primary_ys, primary_xs):
            pb = primary_brightness[py, px]

            # 在副相機中找亮度最接近的像素
            idx = np.searchsorted(sorted_brightnesses, pb)
            idx = np.clip(idx, 0, len(sorted_brightnesses) - 1)

            result[py, px] = sorted_colors[idx]

    return result


def method_5_histogram_match(primary: np.ndarray, secondary: np.ndarray,
                              thresholds: list) -> np.ndarray:
    """
    方法 5: 直方圖匹配式填充

    對每個區域，將副相機的像素按照主相機區域的亮度分布重新排列。
    這樣可以保持副相機的顏色，但空間關係完全打亂。
    """
    h, w = primary.shape[:2]
    primary_brightness = get_brightness(primary)
    secondary_brightness = get_brightness(secondary)

    primary_regions = get_region_map(primary_brightness, thresholds)
    secondary_regions = get_region_map(secondary_brightness, thresholds)

    result = np.zeros_like(primary)

    for region_id in range(4):
        # 主相機區域
        primary_mask = primary_regions == region_id
        primary_ys, primary_xs = np.where(primary_mask)
        primary_count = len(primary_ys)

        if primary_count == 0:
            continue

        # 主相機這些位置的亮度，取得排序索引
        primary_b = primary_brightness[primary_mask]
        primary_order = np.argsort(primary_b)

        # 副相機區域
        secondary_mask = secondary_regions == region_id
        secondary_pixels = secondary[secondary_mask]
        secondary_b = secondary_brightness[secondary_mask]
        secondary_count = len(secondary_pixels)

        if secondary_count == 0:
            result[primary_mask] = [128, 128, 128]
            continue

        # 副相機像素按亮度排序
        secondary_order = np.argsort(secondary_b)
        sorted_secondary = secondary_pixels[secondary_order]

        # 建立結果陣列
        region_result = np.zeros((primary_count, 3), dtype=np.uint8)

        # 根據主相機的亮度排序，分配副相機的像素
        for i, rank in enumerate(primary_order):
            # 對應的副相機索引（線性映射）
            sec_idx = int(rank / primary_count * secondary_count)
            sec_idx = min(sec_idx, secondary_count - 1)
            region_result[i] = sorted_secondary[sec_idx]

        # 但我們要的是按原始順序，所以需要反排序
        final_result = np.zeros_like(region_result)
        for i, rank in enumerate(primary_order):
            final_result[rank] = region_result[i]

        # 填回結果
        result[primary_ys, primary_xs] = final_result

    return result


def create_test_images(size: tuple = (480, 640)) -> tuple:
    """創建測試用的合成圖片"""
    h, w = size

    # 主相機：有明確區域的圖案（例如漸層）
    primary = np.zeros((h, w, 3), dtype=np.uint8)
    for y in range(h):
        brightness = int(255 * y / h)
        primary[y, :] = brightness

    # 副相機：有顏色但亮度分布不同（例如彩色方塊）
    secondary = np.zeros((h, w, 3), dtype=np.uint8)
    block_size = 64
    colors = [
        (255, 0, 0),    # 藍（亮度低）
        (0, 255, 0),    # 綠（亮度中）
        (0, 0, 255),    # 紅（亮度中）
        (255, 255, 0),  # 青（亮度高）
        (255, 0, 255),  # 洋紅（亮度中）
        (0, 255, 255),  # 黃（亮度高）
        (255, 255, 255),# 白（亮度最高）
        (0, 0, 0),      # 黑（亮度最低）
    ]

    color_idx = 0
    for y in range(0, h, block_size):
        for x in range(0, w, block_size):
            secondary[y:y+block_size, x:x+block_size] = colors[color_idx % len(colors)]
            color_idx += 1

    return primary, secondary


def main():
    parser = argparse.ArgumentParser(description='VAV V2 雙相機區域融合測試')
    parser.add_argument('--primary', type=str, help='主相機圖片路徑')
    parser.add_argument('--secondary', type=str, help='副相機圖片路徑')
    parser.add_argument('--output', type=str, default='fusion_result.png', help='輸出路徑')
    parser.add_argument('--method', type=int, default=-1,
                        help='使用的方法 (0-5)，-1 表示顯示所有方法')
    parser.add_argument('--thresholds', type=float, nargs=3,
                        default=DEFAULT_THRESHOLDS, help='亮度閾值')
    parser.add_argument('--tile-size', type=int, default=16,
                        help='方法 3 的瓷磚大小')
    parser.add_argument('--synthetic', action='store_true',
                        help='使用合成測試圖片')
    args = parser.parse_args()

    # 載入或創建圖片
    if args.synthetic or (args.primary is None and args.secondary is None):
        print("使用合成測試圖片...")
        primary, secondary = create_test_images()
    else:
        if args.primary is None or args.secondary is None:
            print("錯誤：必須同時提供 --primary 和 --secondary，或使用 --synthetic")
            return
        primary = load_image(args.primary)
        secondary = load_image(args.secondary)

        # 確保大小一致
        if primary.shape[:2] != secondary.shape[:2]:
            secondary = cv2.resize(secondary, (primary.shape[1], primary.shape[0]))

    print(f"圖片大小: {primary.shape[1]}x{primary.shape[0]}")
    print(f"閾值: {args.thresholds}")

    # 可視化區域分割
    primary_regions = get_region_map(get_brightness(primary), args.thresholds)
    secondary_regions = get_region_map(get_brightness(secondary), args.thresholds)

    primary_vis = visualize_regions(primary, primary_regions)
    secondary_vis = visualize_regions(secondary, secondary_regions)

    methods = {
        0: ("基準: 同位置取樣 + 區域匹配",
            lambda p, s: method_0_baseline(p, s, args.thresholds)),
        1: ("散射填充: 區域像素重新分配",
            lambda p, s: method_1_scatter_fill(p, s, args.thresholds)),
        2: ("UV 重映射: 邊界框內相對位置",
            lambda p, s: method_2_uv_remap(p, s, args.thresholds)),
        3: (f"瓷磚打亂: {args.tile_size}px 方塊",
            lambda p, s: method_3_tile_shuffle(p, s, args.thresholds, args.tile_size)),
        4: ("亮度交換: 找相似亮度的顏色",
            lambda p, s: method_4_brightness_swap(p, s, args.thresholds)),
        5: ("直方圖匹配: 按亮度分布排列",
            lambda p, s: method_5_histogram_match(p, s, args.thresholds)),
    }

    if args.method >= 0:
        # 只執行一個方法
        if args.method not in methods:
            print(f"錯誤：方法 {args.method} 不存在")
            return

        name, func = methods[args.method]
        print(f"\n執行方法 {args.method}: {name}")
        result = func(primary, secondary)

        # 組合顯示
        top_row = np.hstack([primary, secondary])
        bottom_row = np.hstack([primary_vis, result])
        combined = np.vstack([top_row, bottom_row])

        cv2.imwrite(args.output, combined)
        print(f"結果已存到: {args.output}")

        # 顯示視窗
        cv2.imshow('Primary (左上), Secondary (右上), Primary+Regions (左下), Result (右下)', combined)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    else:
        # 顯示所有方法
        print("\n執行所有方法...")

        results = []
        for method_id, (name, func) in methods.items():
            print(f"  方法 {method_id}: {name}")
            results.append(func(primary, secondary))

        # 創建比較視圖
        # 第一行：原圖和區域視覺化
        row1 = np.hstack([primary, secondary, primary_vis, secondary_vis])

        # 第二行：方法 0-2
        row2 = np.hstack([results[0], results[1], results[2],
                          np.zeros_like(primary)])

        # 第三行：方法 3-5
        row3 = np.hstack([results[3], results[4], results[5],
                          np.zeros_like(primary)])

        # 縮小以適合螢幕
        combined = np.vstack([row1, row2, row3])
        scale = min(1.0, 1920 / combined.shape[1], 1080 / combined.shape[0])
        if scale < 1.0:
            combined = cv2.resize(combined, None, fx=scale, fy=scale)

        cv2.imwrite(args.output, combined)
        print(f"\n結果已存到: {args.output}")

        # 顯示說明
        print("\n視圖說明:")
        print("第一行: 主相機, 副相機, 主相機+區域, 副相機+區域")
        print("第二行: 方法 0 (基準), 方法 1 (散射), 方法 2 (UV重映射), (空白)")
        print("第三行: 方法 3 (瓷磚), 方法 4 (亮度交換), 方法 5 (直方圖), (空白)")

        cv2.imshow('All Methods Comparison', combined)
        cv2.waitKey(0)
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
