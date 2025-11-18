#!/usr/bin/env python3
"""
Vision Narrator - 即時視覺描述與語音播報系統
Real-time Vision Description and Speech Narrator

完全離線、開源的視覺理解與中文語音播報應用程式
"""

import argparse
import time
import threading
from modules import CameraCapture, VisionDescriptor, TTSEngine


class VisionNarrator:
    """視覺描述播報系統主類別"""

    def __init__(self, config: dict):
        """
        初始化系統

        Args:
            config: 配置字典
        """
        self.config = config
        self.running = False
        self.paused = False

        # 初始化各模組
        print("\n=== 初始化視覺描述播報系統 ===\n")

        # 1. 攝影機
        print("[ 1/3 ] 初始化攝影機...")
        self.camera = CameraCapture(
            camera_id=config["camera"]["id"],
            resolution=tuple(config["camera"]["resolution"])
        )

        if not self.camera.start():
            raise RuntimeError("攝影機啟動失敗")

        # 2. 視覺描述模型
        print("\n[ 2/3 ] 載入視覺理解模型...")
        self.vision = VisionDescriptor(
            backend=config["vision"]["backend"],
            model_name=config["vision"].get("model_name")
        )

        # 3. TTS 引擎
        print("\n[ 3/3 ] 初始化語音合成引擎...")
        self.tts = TTSEngine(
            backend=config["tts"]["backend"],
            language=config["tts"]["language"],
            voice=config["tts"].get("voice"),
            multilang=config["tts"].get("multilang", False)
        )

        print("\n系統初始化完成\n")

    def describe_and_speak(self):
        """捕捉畫面、生成描述並朗讀"""
        # 捕捉畫面
        frame = self.camera.get_frame_rgb()
        if frame is None:
            print("無法捕捉畫面")
            return

        # 生成描述
        print("\n分析畫面中...")
        start_time = time.time()

        # 檢查是否多語言模式
        if self.config["tts"].get("multilang", False):
            # 多語言模式：生成三種語言描述
            descriptions = self.vision.describe_multilang(
                frame,
                max_tokens=self.config["vision"]["max_tokens"],
                temperature=self.config["vision"]["temperature"]
            )

            inference_time = time.time() - start_time

            # 顯示所有描述
            print(f"\n多語言描述:")
            for lang, desc in descriptions.items():
                print(f"   {lang}: {desc}")
            print(f"   推理時間: {inference_time:.2f} 秒\n")

            # 多語言混合朗讀
            print("開始多語言混合朗讀...")
            self.tts.speak_multilang_mix(descriptions, blocking=False)

        else:
            # 單一語言模式
            description = self.vision.describe(
                frame,
                prompt=self.config["vision"]["prompt"],
                max_tokens=self.config["vision"]["max_tokens"],
                temperature=self.config["vision"]["temperature"]
            )

            inference_time = time.time() - start_time

            # 顯示描述
            print(f"\n描述: {description}")
            print(f"   推理時間: {inference_time:.2f} 秒\n")

            # 朗讀 (非阻塞)
            print("開始朗讀...")
            self.tts.speak(description, blocking=False)

    def run_auto_mode(self):
        """自動模式：定時描述"""
        interval = self.config["capture"]["interval"]

        print(f"自動描述模式 間隔 {interval} 秒")
        print("按 Ctrl+C 停止\n")
        print("-" * 50)

        try:
            while self.running:
                if not self.paused:
                    self.describe_and_speak()
                    print("-" * 50)

                # 等待間隔時間
                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n\n停止自動描述")

    def run_interactive_mode(self):
        """互動模式：手動觸發描述"""
        print("互動模式")
        print("\n控制指令:")
        print("  空白鍵 - 立即描述")
        print("  p      - 暫停/繼續自動描述")
        print("  +      - 增加間隔")
        print("  -      - 減少間隔")
        print("  i      - 顯示系統資訊")
        print("  q      - 退出")
        print("\n按空白鍵開始...")
        print("-" * 50 + "\n")

        # 啟動背景自動描述執行緒 (如果啟用)
        auto_thread = None
        if self.config.get("auto_mode", False):
            auto_thread = threading.Thread(target=self._auto_describe_loop, daemon=True)
            auto_thread.start()

        # 主迴圈等待使用者輸入
        import sys
        import select

        try:
            while self.running:
                # 檢查是否有輸入 (非阻塞)
                if sys.stdin in select.select([sys.stdin], [], [], 0.1)[0]:
                    key = sys.stdin.read(1).lower()

                    if key == ' ':
                        # 空白鍵 - 立即描述
                        self.describe_and_speak()
                        print("-" * 50 + "\n")

                    elif key == 'p':
                        # p - 暫停/繼續
                        self.paused = not self.paused
                        status = "暫停" if self.paused else "繼續"
                        print(f"\n{status}\n")

                    elif key == '+':
                        # + - 增加間隔
                        self.config["capture"]["interval"] += 1
                        print(f"\n間隔: {self.config['capture']['interval']} 秒\n")

                    elif key == '-':
                        # - - 減少間隔
                        self.config["capture"]["interval"] = max(1, self.config["capture"]["interval"] - 1)
                        print(f"\n間隔: {self.config['capture']['interval']} 秒\n")

                    elif key == 'i':
                        # i - 顯示資訊
                        self._print_info()

                    elif key == 'q':
                        # q - 退出
                        print("\n退出程式")
                        break

        except KeyboardInterrupt:
            print("\n\n停止程式")

    def _auto_describe_loop(self):
        """背景自動描述迴圈"""
        while self.running:
            if not self.paused:
                time.sleep(self.config["capture"]["interval"])
                if self.running and not self.paused:
                    print("\n[自動] ")
                    self.describe_and_speak()
                    print("-" * 50 + "\n")

    def _print_info(self):
        """顯示系統資訊"""
        print("\n" + "=" * 50)
        print("系統資訊")
        print("=" * 50)
        print(f"視覺模型: {self.vision.model_name} ({self.vision.backend})")
        print(f"TTS 引擎: {self.tts.backend} ({self.tts.language})")
        print(f"攝影機: ID {self.camera.camera_id}, {self.camera.resolution}")
        print(f"更新間隔: {self.config['capture']['interval']} 秒")
        print(f"狀態: {'暫停' if self.paused else '運行中'}")
        print("=" * 50 + "\n")

    def start(self, mode: str = "auto"):
        """
        啟動系統

        Args:
            mode: 運行模式 ("auto" 或 "interactive")
        """
        self.running = True

        if mode == "auto":
            self.run_auto_mode()
        elif mode == "interactive":
            self.run_interactive_mode()
        else:
            raise ValueError(f"未知模式: {mode}")

    def stop(self):
        """停止系統"""
        self.running = False
        self.camera.stop()
        self.tts.cleanup()
        print("\n✓ 系統已停止")


def main():
    """主函數"""
    parser = argparse.ArgumentParser(
        description="Vision Narrator - 即時視覺描述與語音播報系統",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  %(prog)s                           # 使用預設設定
  %(prog)s --interval 5             # 每 5 秒描述一次
  %(prog)s --backend mlx-vlm        # 使用 mlx-vlm 後端
  %(prog)s --tts edge-tts           # 使用 edge-tts 語音
  %(prog)s --mode interactive       # 互動模式
        """
    )

    # 視覺模型參數
    parser.add_argument(
        "--backend",
        default="mlx-vlm",
        choices=["mlx-vlm", "transformers"],
        help="視覺模型後端 (預設: mlx-vlm)"
    )
    parser.add_argument(
        "--model",
        help="模型名稱 (預設: llava-hf/llava-1.5-7b-hf)"
    )
    parser.add_argument(
        "--prompt",
        default="請用繁體中文詳細描述這張圖片的內容。",
        help="視覺描述提示詞"
    )

    # TTS 參數
    parser.add_argument(
        "--tts",
        default="edge-tts",
        choices=["edge-tts", "coqui", "macos"],
        help="TTS 引擎 (預設: edge-tts)"
    )
    parser.add_argument(
        "--language",
        default="zh-TW",
        choices=["zh-TW", "zh-CN", "ja-JP", "en-GB", "en-US"],
        help="語言 (預設: zh-TW)"
    )
    parser.add_argument(
        "--multilang",
        action="store_true",
        help="啟用多語言混合模式 (中英日隨機切換)"
    )

    # 捕捉參數
    parser.add_argument(
        "--interval",
        type=int,
        default=3,
        help="描述間隔秒數 (預設: 3)"
    )
    parser.add_argument(
        "--camera",
        type=int,
        default=0,
        help="攝影機 ID (預設: 0)"
    )

    # 運行模式
    parser.add_argument(
        "--mode",
        default="auto",
        choices=["auto", "interactive"],
        help="運行模式 (預設: auto)"
    )

    args = parser.parse_args()

    # 建立配置
    config = {
        "vision": {
            "backend": args.backend,
            "model_name": args.model,
            "prompt": args.prompt,
            "max_tokens": 256,
            "temperature": 0.7
        },
        "tts": {
            "backend": args.tts,
            "language": args.language,
            "voice": None,
            "multilang": args.multilang
        },
        "camera": {
            "id": args.camera,
            "resolution": [640, 480]
        },
        "capture": {
            "interval": args.interval
        }
    }

    # 創建並啟動系統
    try:
        narrator = VisionNarrator(config)
        narrator.start(mode=args.mode)
    except KeyboardInterrupt:
        print("\n\n⏹ 使用者中斷")
    except Exception as e:
        print(f"\n❌ 錯誤: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n再見！")


if __name__ == "__main__":
    main()
