"""
Region Mapper - 分散式區域分配系統
將畫面分割成多個區塊，分散地分配給不同通道
"""

import numpy as np
from typing import List, Tuple
from numba import njit


class RegionMapper:
    """管理畫面區域分配給各通道"""

    def __init__(self, width: int = 1920, height: int = 1080):
        self.width = width
        self.height = height
        self.region_map = None  # (height, width) 陣列，每個像素標記屬於哪個通道

    def create_grid_regions(self,
                           grid_cols: int = 5,
                           grid_rows: int = 4,
                           channel_blocks: List[int] = [3, 6, 5, 6],
                           method: str = 'random') -> np.ndarray:
        """
        創建網格分區

        Args:
            grid_cols: 網格列數（橫向）
            grid_rows: 網格行數（縱向）
            channel_blocks: 每個通道分配的區塊數 [CH1, CH2, CH3, CH4]
            method: 分配方法 ('random', 'sequential', 'checkerboard')

        Returns:
            region_map: (height, width) 陣列，值為通道編號 (0-3) 或 -1 (未分配)
        """
        total_blocks = grid_cols * grid_rows
        total_assigned = sum(channel_blocks)

        if total_assigned > total_blocks:
            raise ValueError(f"區塊總數 {total_blocks} 小於分配總數 {total_assigned}")

        # 創建區塊分配陣列
        block_assignment = np.full(total_blocks, -1, dtype=np.int32)

        # 分配區塊給通道
        if method == 'random':
            # 隨機分配
            available_blocks = list(range(total_blocks))
            np.random.shuffle(available_blocks)

            idx = 0
            for channel, num_blocks in enumerate(channel_blocks):
                for _ in range(num_blocks):
                    block_assignment[available_blocks[idx]] = channel
                    idx += 1

        elif method == 'sequential':
            # 順序分配
            idx = 0
            for channel, num_blocks in enumerate(channel_blocks):
                for _ in range(num_blocks):
                    block_assignment[idx] = channel
                    idx += 1

        elif method == 'checkerboard':
            # 棋盤式分配（盡量分散）
            channel_indices = []
            for channel, num_blocks in enumerate(channel_blocks):
                channel_indices.extend([channel] * num_blocks)

            # 按棋盤順序填充
            positions = []
            for offset in range(2):  # 先偶數位置，再奇數位置
                for i in range(total_blocks):
                    if i % 2 == offset:
                        positions.append(i)

            for i, pos in enumerate(positions[:total_assigned]):
                block_assignment[pos] = channel_indices[i]

        # 將區塊分配轉換為像素級 region_map
        block_width = self.width // grid_cols
        block_height = self.height // grid_rows

        self.region_map = np.full((self.height, self.width), -1, dtype=np.int32)

        for block_idx in range(total_blocks):
            channel = block_assignment[block_idx]
            if channel == -1:
                continue

            # 計算區塊位置
            block_row = block_idx // grid_cols
            block_col = block_idx % grid_cols

            y_start = block_row * block_height
            y_end = min((block_row + 1) * block_height, self.height)
            x_start = block_col * block_width
            x_end = min((block_col + 1) * block_width, self.width)

            # 填充區塊
            self.region_map[y_start:y_end, x_start:x_end] = channel

        return self.region_map

    def create_voronoi_regions(self,
                               channel_seeds: List[int] = [3, 6, 5, 6]) -> np.ndarray:
        """
        創建 Voronoi 分區（有機分散）

        Args:
            channel_seeds: 每個通道的種子點數量

        Returns:
            region_map: (height, width) 陣列
        """
        # 生成隨機種子點
        seed_points = []
        seed_channels = []

        for channel, num_seeds in enumerate(channel_seeds):
            for _ in range(num_seeds):
                x = np.random.randint(0, self.width)
                y = np.random.randint(0, self.height)
                seed_points.append((x, y))
                seed_channels.append(channel)

        seed_points = np.array(seed_points)
        seed_channels = np.array(seed_channels)

        # 為每個像素找到最近的種子點（Voronoi）
        self.region_map = np.zeros((self.height, self.width), dtype=np.int32)

        # 使用下採樣加速計算
        downsample = 4
        h_small = self.height // downsample
        w_small = self.width // downsample

        for y in range(h_small):
            for x in range(w_small):
                # 計算到所有種子點的距離
                distances = np.sqrt(
                    (seed_points[:, 0] - x * downsample) ** 2 +
                    (seed_points[:, 1] - y * downsample) ** 2
                )
                nearest_seed = np.argmin(distances)
                channel = seed_channels[nearest_seed]

                # 填充對應的上採樣區域
                y_start = y * downsample
                y_end = min((y + 1) * downsample, self.height)
                x_start = x * downsample
                x_end = min((x + 1) * downsample, self.width)
                self.region_map[y_start:y_end, x_start:x_end] = channel

        return self.region_map

    def create_stripe_regions(self,
                             channel_widths: List[int] = [3, 6, 5, 6],
                             orientation: str = 'vertical',
                             wave: bool = False) -> np.ndarray:
        """
        創建條紋分區

        Args:
            channel_widths: 每個通道的條紋數量
            orientation: 'vertical', 'horizontal', 'diagonal'
            wave: 是否添加波浪效果

        Returns:
            region_map: (height, width) 陣列
        """
        total_stripes = sum(channel_widths)
        self.region_map = np.zeros((self.height, self.width), dtype=np.int32)

        if orientation == 'vertical':
            stripe_width = self.width // total_stripes
            stripe_idx = 0

            for channel, num_stripes in enumerate(channel_widths):
                for _ in range(num_stripes):
                    x_start = stripe_idx * stripe_width
                    x_end = min((stripe_idx + 1) * stripe_width, self.width)

                    if wave:
                        # 添加波浪效果
                        for x in range(x_start, x_end):
                            offset = int(20 * np.sin(x / 100.0))
                            y_start = max(0, offset)
                            y_end = min(self.height, self.height + offset)
                            self.region_map[y_start:y_end, x] = channel
                    else:
                        self.region_map[:, x_start:x_end] = channel

                    stripe_idx += 1

        elif orientation == 'horizontal':
            stripe_height = self.height // total_stripes
            stripe_idx = 0

            for channel, num_stripes in enumerate(channel_widths):
                for _ in range(num_stripes):
                    y_start = stripe_idx * stripe_height
                    y_end = min((stripe_idx + 1) * stripe_height, self.height)
                    self.region_map[y_start:y_end, :] = channel
                    stripe_idx += 1

        return self.region_map

    def get_region_map(self) -> np.ndarray:
        """取得當前 region_map"""
        return self.region_map

    def visualize_regions(self) -> np.ndarray:
        """
        將 region_map 轉換為彩色視覺化圖像

        Returns:
            RGB 圖像 (height, width, 3), uint8
        """
        if self.region_map is None:
            return np.zeros((self.height, self.width, 3), dtype=np.uint8)

        # 每個通道用不同顏色
        colors = [
            [255, 0, 0],    # CH1: 紅
            [0, 255, 0],    # CH2: 綠
            [0, 0, 255],    # CH3: 藍
            [255, 255, 0],  # CH4: 黃
        ]

        vis = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        for channel in range(4):
            mask = self.region_map == channel
            vis[mask] = colors[channel]

        return vis
