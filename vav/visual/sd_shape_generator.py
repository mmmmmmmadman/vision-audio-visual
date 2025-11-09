"""
SD Shape Generator for CV Overlay
使用 LCM + TAESD 快速生成幾何形狀
"""

import torch
from diffusers import StableDiffusionPipeline, LCMScheduler, AutoencoderTiny
from PIL import Image
import numpy as np
import threading
import random
import time
import queue
from typing import Optional


class SDShapeGenerator:
    """背景生成 AI 圖形池"""

    def __init__(self,
                 pool_size: int = 50,
                 min_pool_size: int = 10,
                 image_size: int = 128):
        """
        Args:
            pool_size: 池子最大容量
            min_pool_size: 啟動時快速生成數量
            image_size: 生成圖片尺寸 (正方形)
        """
        self.pool_size = pool_size
        self.min_pool_size = min_pool_size
        self.image_size = image_size

        # 圖形池
        self.shape_pool = queue.Queue(maxsize=pool_size)

        # 顏色列表
        self.colors = [
            "red", "blue", "green", "yellow", "purple",
            "orange", "cyan", "magenta", "pink", "lime"
        ]

        # Prompt 模板
        self.prompt_template = """minimalist {animal} silhouette,
white outline stroke, solid {color} fill,
pure black background, flat design,
simple animal icon, clean edges"""

        # 動物類型列表
        self.animals = [
            "cat", "dog", "bird", "fish", "rabbit",
            "deer", "fox", "bear", "owl", "butterfly",
            "elephant", "whale", "dragon", "horse", "wolf"
        ]

        # Pipeline
        self.pipe = None
        self.device = "mps"
        self.loaded = False

        # 背景執行緒
        self.running = False
        self.generator_thread = None

    def load_model(self):
        """載入 LCM pipeline"""
        print("[SD Shape Generator] 載入模型...")

        model_id = "runwayml/stable-diffusion-v1-5"
        lcm_lora_path = "/Users/madzine/Documents/AI_V/02_Visual_Generation/lcm-lora-sdv1-5"

        # 載入基礎模型
        self.pipe = StableDiffusionPipeline.from_pretrained(
            model_id,
            torch_dtype=torch.float16,
            use_safetensors=True
        )

        # 載入 LCM LoRA
        print("[SD Shape Generator] 載入 LCM LoRA...")
        self.pipe.load_lora_weights(lcm_lora_path)

        # 設定 LCM Scheduler
        self.pipe.scheduler = LCMScheduler.from_config(self.pipe.scheduler.config)

        # 載入 TAESD
        print("[SD Shape Generator] 載入 TAESD...")
        tiny_vae = AutoencoderTiny.from_pretrained(
            "madebyollin/taesd",
            torch_dtype=torch.float16
        )
        self.pipe.vae = tiny_vae

        # 移到 GPU
        self.pipe = self.pipe.to(self.device)

        # 關閉安全檢查
        self.pipe.safety_checker = None
        self.pipe.requires_safety_checker = False

        self.loaded = True
        print("[SD Shape Generator] 模型載入完成")

    def generate_single_shape(self) -> Optional[np.ndarray]:
        """生成單一圖形"""
        if not self.loaded:
            return None

        try:
            # 隨機顏色和動物
            color = random.choice(self.colors)
            animal = random.choice(self.animals)

            # 生成 prompt
            prompt = self.prompt_template.format(color=color, animal=animal)

            # 隨機種子
            seed = random.randint(0, 999999)
            generator = torch.Generator(device=self.device).manual_seed(seed)

            # 生成圖片
            result = self.pipe(
                prompt=prompt,
                width=self.image_size,
                height=self.image_size,
                num_inference_steps=2,
                guidance_scale=1.5,
                generator=generator
            ).images[0]

            # 轉成 numpy array (BGR for OpenCV)
            img_array = np.array(result)
            img_bgr = img_array[:, :, ::-1].copy()  # RGB to BGR

            return img_bgr

        except Exception as e:
            print(f"[SD Shape Generator] 生成錯誤: {e}")
            return None

    def _background_generator(self):
        """背景執行緒：持續生成圖形"""
        print("[SD Shape Generator] 背景生成執行緒啟動")

        while self.running:
            try:
                # 檢查池子是否已滿
                if self.shape_pool.qsize() < self.pool_size:
                    shape = self.generate_single_shape()

                    if shape is not None:
                        self.shape_pool.put(shape, block=False)
                        current = self.shape_pool.qsize()
                        print(f"[SD Shape Generator] 生成池: {current}/{self.pool_size}")
                else:
                    # 池子滿了，休息
                    time.sleep(0.5)

                # 生成間隔
                time.sleep(0.2)

            except queue.Full:
                time.sleep(0.5)
            except Exception as e:
                print(f"[SD Shape Generator] 背景生成錯誤: {e}")
                time.sleep(1.0)

        print("[SD Shape Generator] 背景生成執行緒結束")

    def start(self):
        """啟動生成器"""
        if not self.loaded:
            self.load_model()

        # 快速生成初始圖形
        print(f"[SD Shape Generator] 快速生成 {self.min_pool_size} 張初始圖形...")
        for i in range(self.min_pool_size):
            shape = self.generate_single_shape()
            if shape is not None:
                self.shape_pool.put(shape)
                print(f"  {i+1}/{self.min_pool_size}")

        # 啟動背景執行緒
        self.running = True
        self.generator_thread = threading.Thread(target=self._background_generator, daemon=True)
        self.generator_thread.start()

        print(f"[SD Shape Generator] 啟動完成，背景補充至 {self.pool_size} 張")

    def stop(self):
        """停止生成器"""
        print("[SD Shape Generator] 停止生成器...")
        self.running = False
        if self.generator_thread:
            self.generator_thread.join(timeout=2.0)

    def get_shape(self) -> Optional[np.ndarray]:
        """取得一個隨機圖形"""
        try:
            shape = self.shape_pool.get(block=False)
            return shape
        except queue.Empty:
            print("[SD Shape Generator] 警告：池子空了，返回 None")
            return None

    def pool_status(self) -> dict:
        """查詢池子狀態"""
        return {
            'current': self.shape_pool.qsize(),
            'max': self.pool_size,
            'loaded': self.loaded,
            'running': self.running
        }


# 全域單例（避免重複載入模型）
_global_generator = None


def get_global_generator() -> SDShapeGenerator:
    """取得全域生成器實例"""
    global _global_generator
    if _global_generator is None:
        _global_generator = SDShapeGenerator()
    return _global_generator


if __name__ == "__main__":
    # 測試代碼
    print("測試 SD Shape Generator")

    gen = SDShapeGenerator(pool_size=5, min_pool_size=2, image_size=128)
    gen.start()

    # 等待生成
    time.sleep(10)

    # 取得幾個圖形
    for i in range(3):
        shape = gen.get_shape()
        if shape is not None:
            print(f"取得圖形 {i+1}: {shape.shape}")

    # 查看狀態
    print("池子狀態:", gen.pool_status())

    gen.stop()
