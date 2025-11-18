"""
視覺理解模組
Vision Language Model Module

支援的後端:
- mlx-vlm: 使用 MLX 框架運行 LLaVA 等模型 (Apple Silicon 優化)
- transformers: 使用 HuggingFace Transformers (通用方案)
"""

import numpy as np
from PIL import Image
from typing import Optional, Dict, Any
import time


class VisionDescriptor:
    """視覺描述基礎類別"""

    def __init__(self, backend: str = "mlx-vlm", model_name: Optional[str] = None, **kwargs):
        """
        初始化視覺描述器

        Args:
            backend: 後端類型 ("mlx-vlm" 或 "transformers")
            model_name: 模型名稱
            **kwargs: 其他參數
        """
        self.backend = backend
        self.model_name = model_name
        self.model = None
        self.processor = None

        print(f"初始化視覺描述器 (後端: {backend})")

        if backend == "mlx-vlm":
            self._init_mlx_vlm(**kwargs)
        elif backend == "transformers":
            self._init_transformers(**kwargs)
        else:
            raise ValueError(f"不支援的後端: {backend}")

    def _init_mlx_vlm(self, **kwargs):
        """初始化 MLX-VLM 後端"""
        try:
            from mlx_vlm import load, generate
            from mlx_vlm.utils import load_image
            import os

            self.generate_func = generate
            self.load_image_func = load_image

            # 預設模型
            if self.model_name is None:
                # 優先使用本地 SmolVLM，若不存在則使用 HuggingFace
                local_smolvlm = "models/smolvlm"
                if os.path.exists(local_smolvlm):
                    self.model_name = local_smolvlm
                    print(f"使用本地模型: {self.model_name}")
                else:
                    self.model_name = "mlx-community/SmolVLM-Instruct-4bit"
                    print(f"本地模型不存在，將從 HuggingFace 下載: {self.model_name}")
                    print("首次運行會下載模型，請耐心等待...")

            print(f"載入模型: {self.model_name}")

            start_time = time.time()
            self.model, self.processor = load(self.model_name)
            load_time = time.time() - start_time

            print(f"✓ 模型載入完成 (耗時: {load_time:.1f} 秒)")

        except ImportError:
            print("錯誤: 未安裝 mlx-vlm")
            print("請執行: pip install mlx-vlm")
            raise

    def _init_transformers(self, **kwargs):
        """初始化 Transformers 後端"""
        try:
            from transformers import LlavaNextProcessor, LlavaNextForConditionalGeneration
            import torch

            # 預設模型
            if self.model_name is None:
                self.model_name = "llava-hf/llava-v1.6-vicuna-7b-hf"

            print(f"載入模型: {self.model_name}")
            print("首次運行會下載模型，請耐心等待...")

            start_time = time.time()

            self.processor = LlavaNextProcessor.from_pretrained(self.model_name)
            self.model = LlavaNextForConditionalGeneration.from_pretrained(
                self.model_name,
                torch_dtype=torch.float16,
                device_map="mps" if torch.backends.mps.is_available() else "cpu"
            )

            load_time = time.time() - start_time
            print(f"✓ 模型載入完成 (耗時: {load_time:.1f} 秒)")

        except ImportError:
            print("錯誤: 未安裝 transformers 或 torch")
            print("請執行: pip install transformers torch torchvision")
            raise

    def describe(self, image: np.ndarray, prompt: Optional[str] = None, **kwargs) -> str:
        """
        描述圖片內容

        Args:
            image: RGB 格式的圖片 (numpy array)
            prompt: 自定義提示詞
            **kwargs: 其他生成參數

        Returns:
            str: 圖片描述
        """
        # 預設中文提示詞
        if prompt is None:
            prompt = "請用繁體中文詳細描述這張圖片的內容。"

        # 轉換為 PIL Image
        pil_image = Image.fromarray(image)

        if self.backend == "mlx-vlm":
            return self._describe_mlx_vlm(pil_image, prompt, **kwargs)
        elif self.backend == "transformers":
            return self._describe_transformers(pil_image, prompt, **kwargs)

    def describe_multilang(self, image: np.ndarray, **kwargs) -> Dict[str, str]:
        """
        生成多語言描述

        Args:
            image: RGB 格式的圖片 (numpy array)
            **kwargs: 其他生成參數

        Returns:
            Dict[str, str]: {"zh-TW": "中文描述", "en-GB": "English", "ja-JP": "日本語"}
        """
        pil_image = Image.fromarray(image)

        prompts = {
            "zh-TW": "請用繁體中文詳細描述這張圖片。",
            "en-GB": "Describe this image in English.",
            "ja-JP": "この画像を日本語で詳しく説明してください。"
        }

        descriptions = {}

        for lang, prompt in prompts.items():
            print(f"生成 {lang} 描述...")
            if self.backend == "mlx-vlm":
                descriptions[lang] = self._describe_mlx_vlm(pil_image, prompt, **kwargs)
            elif self.backend == "transformers":
                descriptions[lang] = self._describe_transformers(pil_image, prompt, **kwargs)

        return descriptions

    def _describe_mlx_vlm(self, image: Image.Image, prompt: str, **kwargs) -> str:
        """使用 MLX-VLM 生成描述"""
        import tempfile
        import os

        # MLX-VLM 的 prompt 格式
        full_prompt = f"USER: <image>\n{prompt}\nASSISTANT:"

        # 生成參數
        max_tokens = kwargs.get("max_tokens", 256)
        temperature = kwargs.get("temperature", 0.7)

        try:
            # MLX-VLM 需要檔案路徑，先將PIL Image存為臨時檔
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                tmp_path = tmp.name
                image.save(tmp_path)

            try:
                output = self.generate_func(
                    self.model,
                    self.processor,
                    full_prompt,
                    image=tmp_path,
                    max_tokens=max_tokens,
                    temp=temperature,
                    verbose=False
                )

                # MLX-VLM返回GenerationResult對象，需要取text屬性
                result_text = output.text if hasattr(output, 'text') else str(output)
                return result_text.strip()

            finally:
                # 清理臨時檔
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

        except Exception as e:
            print(f"生成描述時發生錯誤: {e}")
            return f"[無法生成描述: {str(e)}]"

    def _describe_transformers(self, image: Image.Image, prompt: str, **kwargs) -> str:
        """使用 Transformers 生成描述"""
        import torch

        # LLaVA 的 prompt 格式
        full_prompt = f"USER: <image>\n{prompt}\nASSISTANT:"

        # 處理輸入
        inputs = self.processor(full_prompt, image, return_tensors="pt")

        # 移動到設備
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        inputs = {k: v.to(device) for k, v in inputs.items()}

        # 生成參數
        max_tokens = kwargs.get("max_tokens", 256)
        temperature = kwargs.get("temperature", 0.7)

        try:
            # 生成
            with torch.no_grad():
                output_ids = self.model.generate(
                    **inputs,
                    max_new_tokens=max_tokens,
                    temperature=temperature,
                    do_sample=True
                )

            # 解碼
            output = self.processor.decode(output_ids[0], skip_special_tokens=True)

            # 提取 ASSISTANT 之後的內容
            if "ASSISTANT:" in output:
                output = output.split("ASSISTANT:")[-1].strip()

            return output

        except Exception as e:
            print(f"生成描述時發生錯誤: {e}")
            return f"[無法生成描述: {str(e)}]"

    def get_info(self) -> Dict[str, Any]:
        """取得模型資訊"""
        return {
            "backend": self.backend,
            "model_name": self.model_name,
            "loaded": self.model is not None
        }


# 測試程式碼
if __name__ == "__main__":
    import cv2
    import sys

    print("=== 視覺描述模組測試 ===\n")

    # 選擇後端
    print("選擇後端:")
    print("1. mlx-vlm (推薦，Apple Silicon 優化)")
    print("2. transformers (通用方案)")

    choice = input("\n請輸入 1 或 2: ").strip()

    if choice == "1":
        backend = "mlx-vlm"
    elif choice == "2":
        backend = "transformers"
    else:
        print("無效選擇")
        sys.exit(1)

    # 創建描述器
    try:
        descriptor = VisionDescriptor(backend=backend)
    except Exception as e:
        print(f"\n初始化失敗: {e}")
        sys.exit(1)

    print("\n選擇測試模式:")
    print("1. 測試圖片檔案")
    print("2. 測試攝影機即時畫面")

    mode = input("\n請輸入 1 或 2: ").strip()

    if mode == "1":
        # 測試圖片檔案
        image_path = input("請輸入圖片路徑: ").strip()

        try:
            image = cv2.imread(image_path)
            if image is None:
                print(f"無法讀取圖片: {image_path}")
                sys.exit(1)

            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            print("\n開始生成描述...")
            start_time = time.time()

            description = descriptor.describe(image_rgb)

            inference_time = time.time() - start_time

            print(f"\n【描述結果】")
            print(f"{description}")
            print(f"\n(推理時間: {inference_time:.2f} 秒)")

        except Exception as e:
            print(f"處理圖片時發生錯誤: {e}")

    elif mode == "2":
        # 測試攝影機
        print("\n啟動攝影機...")

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("無法開啟攝影機")
            sys.exit(1)

        print("按空白鍵生成描述，按 'q' 退出")

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            cv2.putText(
                frame,
                "Press SPACE to describe, 'q' to quit",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )

            cv2.imshow("Camera", frame)

            key = cv2.waitKey(1) & 0xFF

            if key == ord(' '):
                print("\n生成描述中...")
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                start_time = time.time()
                description = descriptor.describe(frame_rgb)
                inference_time = time.time() - start_time

                print(f"\n【描述】{description}")
                print(f"(推理時間: {inference_time:.2f} 秒)\n")

            elif key == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()

    else:
        print("無效選擇")

    print("\n測試完成")
