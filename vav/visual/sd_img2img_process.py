"""
SD Real-time Img2Img - Process 版本
使用 multiprocessing 將 SD 推理隔離到獨立進程
解決 GPU 資源競爭問題
"""

import torch
from diffusers import StableDiffusionImg2ImgPipeline, LCMScheduler, AutoencoderTiny
from PIL import Image
import numpy as np
import cv2
import multiprocessing as mp
import time
from typing import Optional
import queue


def _sd_worker_process(
    input_queue: mp.Queue,
    output_queue: mp.Queue,
    control_queue: mp.Queue,
    params: dict
):
    """
    SD 工作進程

    Args:
        input_queue: 接收輸入 frame
        output_queue: 發送生成結果
        control_queue: 控制指令
        params: SD 參數
    """
    print("[SD Process] 啟動 SD 工作進程...")

    # 載入模型
    model_id = "runwayml/stable-diffusion-v1-5"
    lcm_lora_path = "/Users/madzine/Documents/AI_V/02_Visual_Generation/lcm-lora-sdv1-5"
    device = params.get('device', 'mps')

    print("[SD Process] 載入 SD 1.5...")
    pipe = StableDiffusionImg2ImgPipeline.from_pretrained(
        model_id,
        torch_dtype=torch.float16,
        use_safetensors=True
    )

    print("[SD Process] 載入 LCM LoRA...")
    pipe.load_lora_weights(lcm_lora_path)

    print("[SD Process] 設定 LCM Scheduler...")
    pipe.scheduler = LCMScheduler.from_config(pipe.scheduler.config)

    print("[SD Process] 載入 TAESD...")
    tiny_vae = AutoencoderTiny.from_pretrained(
        "madebyollin/taesd",
        torch_dtype=torch.float16
    )
    pipe.vae = tiny_vae

    print("[SD Process] 移到裝置...")
    pipe = pipe.to(device)

    pipe.safety_checker = None
    pipe.requires_safety_checker = False

    print("[SD Process] 模型載入完成，開始處理循環")

    # 生成參數（可即時更新）
    # LCM 優化：提高步數和強度以改善 prompt 控制力
    prompt = params.get('prompt', 'artistic style, abstract, monochrome ink painting, high quality')
    strength = params.get('strength', 0.5)
    guidance_scale = params.get('guidance_scale', 1.0)
    num_steps = params.get('num_steps', 2)
    output_width = params.get('output_width', 1280)
    output_height = params.get('output_height', 720)

    running = True

    while running:
        try:
            # 檢查控制指令（支援即時更新）
            try:
                cmd = control_queue.get_nowait()
                if cmd == 'stop':
                    print("[SD Process] 收到停止指令")
                    running = False
                    break
                elif isinstance(cmd, dict):
                    # 更新參數
                    if 'prompt' in cmd:
                        prompt = cmd['prompt']
                        print(f"[SD Process] 更新 Prompt: {prompt}")
                    if 'strength' in cmd:
                        strength = cmd['strength']
                        print(f"[SD Process] 更新 Strength: {strength}")
                    if 'guidance_scale' in cmd:
                        guidance_scale = cmd['guidance_scale']
                        print(f"[SD Process] 更新 Guidance Scale: {guidance_scale}")
                    if 'num_steps' in cmd:
                        num_steps = cmd['num_steps']
                        print(f"[SD Process] 更新 Steps: {num_steps}")
            except queue.Empty:
                pass

            # 從 input_queue 取得 frame（非阻塞）
            try:
                input_frame = input_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if input_frame is None:
                continue

            # 執行推理
            start_time = time.time()

            # 轉換成 PIL Image (use BILINEAR for speed)
            pil_image = Image.fromarray(input_frame[:, :, ::-1])  # BGR to RGB
            pil_image = pil_image.resize((512, 512), Image.Resampling.BILINEAR)

            # 生成
            result = pipe(
                prompt=prompt,
                image=pil_image,
                strength=strength,
                guidance_scale=guidance_scale,
                num_inference_steps=num_steps
            ).images[0]

            # 轉回 numpy BGR
            result_array = np.array(result)
            result_bgr = result_array[:, :, ::-1].copy()

            # 放大到目標解析度 (use BILINEAR for speed)
            result_resized = np.array(Image.fromarray(result_bgr).resize(
                (output_width, output_height),
                Image.Resampling.BILINEAR
            ))

            gen_time = time.time() - start_time
            print(f"[SD Process] 生成完成: {gen_time:.2f}s")

            # 發送結果（非阻塞，如果滿了就丟棄舊的）
            try:
                output_queue.put_nowait(result_resized)
            except queue.Full:
                # 清空舊的結果
                try:
                    output_queue.get_nowait()
                    output_queue.put_nowait(result_resized)
                except:
                    pass

        except Exception as e:
            import traceback
            print(f"[SD Process] 錯誤: {e}")
            print(f"[SD Process] 詳細:\n{traceback.format_exc()}")
            time.sleep(0.1)

    print("[SD Process] 工作進程結束")


class SDImg2ImgProcess:
    """SD img2img 進程版本"""

    def __init__(self,
                 output_width: int = 1280,
                 output_height: int = 720,
                 fps_target: int = 30):
        """
        Args:
            output_width: 輸出寬度
            output_height: 輸出高度
            fps_target: 目標 FPS
        """
        self.output_width = output_width
        self.output_height = output_height
        self.fps_target = fps_target

        # SD 參數（LCM 優化配置）
        self.prompt = "artistic style, abstract, monochrome ink painting, high quality"
        self.strength = 0.5
        self.guidance_scale = 1.0
        self.num_steps = 2
        self.device = "mps"

        # 進程和通訊
        self.process = None
        self.input_queue = None
        self.output_queue = None
        self.control_queue = None

        # 顯示狀態
        self.current_image = None
        self.previous_image = None
        self.display_image = None
        self.is_transitioning = False
        self.transition_start_time = 0
        self.transition_duration = 1.0
        self.first_generation = True

        # 定時發送
        self.last_send_time = 0
        self.send_interval = 1.5  # 每 1.5 秒發送一次 frame

        # 顯示更新線程
        self.running = False
        self.display_update_thread = None

    def start(self):
        """啟動 SD 進程"""
        print("[SD img2img] 啟動進程版本...")

        # 創建通訊 Queue
        self.input_queue = mp.Queue(maxsize=2)
        self.output_queue = mp.Queue(maxsize=2)
        self.control_queue = mp.Queue()

        # SD 參數
        params = {
            'device': self.device,
            'prompt': self.prompt,
            'strength': self.strength,
            'guidance_scale': self.guidance_scale,
            'num_steps': self.num_steps,
            'output_width': self.output_width,
            'output_height': self.output_height,
        }

        # 啟動 SD 工作進程
        self.process = mp.Process(
            target=_sd_worker_process,
            args=(self.input_queue, self.output_queue, self.control_queue, params),
            daemon=True
        )
        self.process.start()

        # 啟動顯示更新線程
        self.running = True
        import threading
        self.display_update_thread = threading.Thread(
            target=self._display_update_loop,
            daemon=True
        )
        self.display_update_thread.start()

        print("[SD img2img] 進程啟動完成")

    def stop(self):
        """停止 SD 進程（異步）"""
        if not self.process:
            return

        print("[SD img2img] 停止進程...")

        # 立即標記停止
        self.running = False

        # 發送停止指令
        if self.control_queue:
            self.control_queue.put('stop')

        # 在背景線程中等待清理
        import threading
        def _cleanup():
            # 等待線程結束
            if self.display_update_thread:
                self.display_update_thread.join(timeout=2.0)

            # 等待進程結束
            if self.process and self.process.is_alive():
                self.process.join(timeout=3.0)
                if self.process.is_alive():
                    self.process.terminate()

            print("[SD img2img] 進程已停止")

        cleanup_thread = threading.Thread(target=_cleanup, daemon=True)
        cleanup_thread.start()
        print("[SD img2img] 停止中（背景清理）...")

    def feed_frame(self, input_frame: np.ndarray):
        """
        餵入新的 frame（主進程只在時間間隔到達時發送）

        Args:
            input_frame: 輸入圖像 (BGR format)
        """
        if not self.process or not self.process.is_alive():
            return

        current_time = time.time()

        # 檢查是否需要發送
        if current_time - self.last_send_time < self.send_interval:
            return

        # 非阻塞發送（如果 Queue 滿了就跳過）
        try:
            self.input_queue.put_nowait(input_frame.copy())
            self.last_send_time = current_time
        except queue.Full:
            pass

    def _display_update_loop(self):
        """顯示更新循環（在主進程的線程中運行）"""
        print("[SD img2img] 顯示更新線程啟動")

        while self.running:
            try:
                # 嘗試從 output_queue 取得新的生成結果
                try:
                    new_image = self.output_queue.get_nowait()

                    # 更新圖像和過渡狀態
                    if self.first_generation:
                        self.first_generation = False
                        self.previous_image = np.zeros_like(new_image)
                    else:
                        self.previous_image = self.current_image

                    self.current_image = new_image
                    self.is_transitioning = True
                    self.transition_start_time = time.time()

                except queue.Empty:
                    pass

                # 計算顯示圖像（過渡效果）
                current_time = time.time()

                if self.is_transitioning and self.previous_image is not None and self.current_image is not None:
                    elapsed = current_time - self.transition_start_time
                    progress = min(elapsed / self.transition_duration, 1.0)

                    if progress >= 1.0:
                        self.is_transitioning = False
                        self.display_image = self.current_image
                    else:
                        # 混合
                        self.display_image = cv2.addWeighted(
                            self.previous_image, 1 - progress,
                            self.current_image, progress,
                            0
                        )
                elif self.current_image is not None:
                    self.display_image = self.current_image

                # 30 FPS 更新
                time.sleep(1.0 / 30)

            except Exception as e:
                print(f"[SD img2img] 顯示更新錯誤: {e}")
                time.sleep(0.1)

        print("[SD img2img] 顯示更新線程結束")

    def get_current_output(self) -> Optional[np.ndarray]:
        """取得當前輸出"""
        return self.display_image

    def set_prompt(self, prompt: str):
        """設定 prompt（即時生效）"""
        self.prompt = prompt

        # 即時發送給工作進程
        if self.control_queue and self.process and self.process.is_alive():
            try:
                # 清空 input_queue 中的舊 frame（避免積壓）
                while not self.input_queue.empty():
                    try:
                        self.input_queue.get_nowait()
                    except:
                        break

                self.control_queue.put_nowait({'prompt': prompt})
                # 強制觸發立即生成（重置 send 計時器）
                self.last_send_time = 0
                print(f"[SD img2img] Prompt 已即時更新: {prompt}")
            except queue.Full:
                print(f"[SD img2img] Prompt 更新失敗（Queue 已滿）")
        else:
            print(f"[SD img2img] Prompt 已儲存: {prompt}（將在啟動時生效）")

    def set_parameters(self, strength: float = None, guidance_scale: float = None,
                      num_steps: int = None):
        """設定生成參數（即時生效）"""
        update_dict = {}

        if strength is not None:
            self.strength = strength
            update_dict['strength'] = strength
        if guidance_scale is not None:
            self.guidance_scale = guidance_scale
            update_dict['guidance_scale'] = guidance_scale
        if num_steps is not None:
            self.num_steps = num_steps
            update_dict['num_steps'] = num_steps

        # 即時發送給工作進程
        if update_dict and self.control_queue and self.process and self.process.is_alive():
            try:
                # 清空 input_queue 中的舊 frame（避免積壓）
                while not self.input_queue.empty():
                    try:
                        self.input_queue.get_nowait()
                    except:
                        break

                self.control_queue.put_nowait(update_dict)
                # 強制觸發立即生成（重置 send 計時器）
                self.last_send_time = 0
                print(f"[SD img2img] 參數已即時更新 - Strength: {self.strength}, "
                      f"Guidance: {self.guidance_scale}, Steps: {self.num_steps}")
            except queue.Full:
                print(f"[SD img2img] 參數更新失敗（Queue 已滿）")
        else:
            print(f"[SD img2img] 參數已儲存（將在啟動時生效）")
