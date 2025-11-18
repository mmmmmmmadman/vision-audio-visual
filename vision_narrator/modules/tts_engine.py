"""
語音合成模組
Text-to-Speech Engine Module

支援的後端:
- edge-tts: Microsoft Edge TTS (輕量、品質好)
- coqui: Coqui XTTSv2 (高品質、支援多語言)
- macos: macOS 內建 say 指令 (最簡單)
"""

import os
import subprocess
import tempfile
from typing import Optional
import asyncio


class TTSEngine:
    """語音合成基礎類別"""

    def __init__(self, backend: str = "edge-tts", language: str = "zh-TW", voice: Optional[str] = None, multilang: bool = False, audio_device: Optional[dict] = None):
        """
        初始化 TTS 引擎

        Args:
            backend: 後端類型 ("edge-tts", "coqui", 或 "macos")
            language: 語言代碼 (zh-TW, zh-CN)
            voice: 指定聲音 (可選)
            multilang: 是否啟用多語言混合模式
            audio_device: 音訊輸出裝置資訊 (來自 AudioDeviceManager)
        """
        self.backend = backend
        self.language = language
        self.voice = voice
        self.multilang = multilang
        self.audio_device = audio_device
        self.temp_dir = tempfile.mkdtemp()

        # 循環播放控制
        self.current_audio_process = None
        self.should_stop_loop = False

        # 多語言聲音配置
        self.voices = {
            "zh-TW": "zh-TW-HsiaoChenNeural",
            "en-GB": "en-GB-SoniaNeural",
            "ja-JP": "ja-JP-NanamiNeural"
        }

        # 音訊快取 格式: {cache_key: audio_file_path}
        self.audio_cache = {}
        self.max_cache_size = 50

        # 簡單翻譯對照表（常用詞彙）
        self.translations = {
            "這": {"en-GB": "This", "ja-JP": "これ"},
            "是": {"en-GB": "is", "ja-JP": "は"},
            "一個": {"en-GB": "a", "ja-JP": "一つの"},
            "測試": {"en-GB": "test", "ja-JP": "テスト"},
            "現在": {"en-GB": "now", "ja-JP": "今"},
            "天氣": {"en-GB": "weather", "ja-JP": "天気"},
            "很好": {"en-GB": "very good", "ja-JP": "とても良い"},
            "我們": {"en-GB": "we", "ja-JP": "私たち"},
            "來": {"en-GB": "let's", "ja-JP": "来"},
            "看看": {"en-GB": "look at", "ja-JP": "見て"},
            "這個": {"en-GB": "this", "ja-JP": "この"},
            "系統": {"en-GB": "system", "ja-JP": "システム"},
            "真的": {"en-GB": "really", "ja-JP": "本当に"},
            "有趣": {"en-GB": "interesting", "ja-JP": "面白い"},
        }

        print(f"初始化 TTS 引擎 (後端: {backend}, 語言: {language}, 多語言: {multilang})")

        if backend == "edge-tts":
            self._init_edge_tts()
        elif backend == "coqui":
            self._init_coqui()
        elif backend == "macos":
            self._init_macos()
        else:
            raise ValueError(f"不支援的後端: {backend}")

    def _init_edge_tts(self):
        """初始化 Edge TTS"""
        try:
            import edge_tts
            self.edge_tts = edge_tts

            # 預設聲音
            if self.voice is None:
                if self.language == "zh-TW":
                    self.voice = "zh-TW-HsiaoChenNeural"  # 女聲
                elif self.language == "zh-CN":
                    self.voice = "zh-CN-XiaoxiaoNeural"  # 女聲
                elif self.language == "ja-JP":
                    self.voice = "ja-JP-NanamiNeural"  # 七海 女聲
                elif self.language == "en-GB":
                    self.voice = "en-GB-SoniaNeural"  # Sonia 女聲
                elif self.language == "en-US":
                    self.voice = "en-US-AriaNeural"  # Aria 女聲
                elif self.language.startswith("en"):
                    self.voice = "en-GB-SoniaNeural"  # 預設英文用 Sonia
                elif self.language.startswith("ja"):
                    self.voice = "ja-JP-NanamiNeural"  # 預設日文用七海
                else:
                    self.voice = "zh-TW-HsiaoChenNeural"

            print(f"✓ Edge TTS 初始化完成 (聲音: {self.voice})")

        except ImportError:
            print("錯誤: 未安裝 edge-tts")
            print("請執行: pip install edge-tts")
            raise

    def _init_coqui(self):
        """初始化 Coqui TTS"""
        try:
            from TTS.api import TTS
            import torch

            print("載入 Coqui TTS 模型...")

            # 使用 XTTS v2 (支援多語言)
            model_name = "tts_models/multilingual/multi-dataset/xtts_v2"

            self.tts = TTS(model_name)

            # 設定為 CPU (MPS 不支援)
            device = "cpu"
            self.tts.to(device)

            # 語言代碼轉換
            if self.language in ["zh-TW", "zh-CN"]:
                self.tts_language = "zh-cn"  # XTTS 使用 zh-cn
            else:
                self.tts_language = "zh-cn"

            print(f"✓ Coqui TTS 初始化完成 (語言: {self.tts_language})")

        except ImportError:
            print("錯誤: 未安裝 coqui-tts")
            print("請執行: pip install coqui-tts")
            raise

    def _init_macos(self):
        """初始化 macOS say 指令"""
        # 測試 say 指令是否可用
        try:
            result = subprocess.run(
                ["say", "-v", "?"],
                capture_output=True,
                text=True
            )

            # 尋找中文聲音
            voices = result.stdout.split("\n")
            zh_voices = [v for v in voices if "zh_" in v.lower()]

            if zh_voices:
                # 取得第一個中文聲音名稱
                first_voice = zh_voices[0].split()[0]
                self.voice = first_voice if self.voice is None else self.voice
                print(f"✓ macOS TTS 初始化完成 (聲音: {self.voice})")
            else:
                print("⚠ 未找到中文聲音，使用預設聲音")
                self.voice = None

        except Exception as e:
            print(f"初始化 macOS TTS 時發生錯誤: {e}")
            raise

    def _get_cache_key(self, text: str, voice: str) -> str:
        """生成快取鍵"""
        import hashlib
        content = f"{text}|{voice}"
        return hashlib.md5(content.encode()).hexdigest()

    def _manage_cache_size(self):
        """管理快取大小 避免佔用過多空間"""
        if len(self.audio_cache) > self.max_cache_size:
            # 刪除最舊的20%快取
            remove_count = int(self.max_cache_size * 0.2)
            keys_to_remove = list(self.audio_cache.keys())[:remove_count]

            for key in keys_to_remove:
                file_path = self.audio_cache[key]
                if os.path.exists(file_path):
                    os.remove(file_path)
                del self.audio_cache[key]

    def speak(self, text: str, blocking: bool = True, language: Optional[str] = None, loop: bool = False) -> bool:
        """
        朗讀文字

        Args:
            text: 要朗讀的文字
            blocking: 是否等待朗讀完成
            language: 指定語言 (zh-TW, en-GB, ja-JP)，若無則使用預設語言
            loop: 是否循環播放

        Returns:
            bool: 是否成功
        """
        if not text or text.strip() == "":
            print("警告: 文字為空，跳過朗讀")
            return False

        print(f"[TTS] {text}")

        try:
            # 多語言混合模式
            if self.multilang and self.backend == "edge-tts" and language is None:
                return self._speak_multilang(text, blocking)

            # 單一語言模式
            if self.backend == "edge-tts":
                return self._speak_edge_tts(text, blocking, language, loop)
            elif self.backend == "coqui":
                return self._speak_coqui(text, blocking)
            elif self.backend == "macos":
                return self._speak_macos(text, blocking)
        except Exception as e:
            print(f"朗讀時發生錯誤: {e}")
            return False

    def speak_multilang_mix(self, descriptions: dict, blocking: bool = True) -> bool:
        """
        多語言混合播報：三種語言用ffmpeg混合（支援快取和並行生成）

        Args:
            descriptions: {"zh-TW": "中文", "en-GB": "English", "ja-JP": "日本語"}
            blocking: 是否等待播放完成
        """
        import random
        import subprocess

        print("生成三種語言的完整音訊...")

        # 生成每種語言的完整音訊
        audio_files = {}

        async def generate_all_audio():
            # 並行生成所有語言的音訊
            tasks = []

            for lang, text in descriptions.items():
                voice = self.voices[lang]
                cache_key = self._get_cache_key(text, voice)

                # 檢查快取
                if cache_key in self.audio_cache:
                    cached_file = self.audio_cache[cache_key]
                    if os.path.exists(cached_file):
                        print(f"  使用快取 {lang}: {text}")
                        audio_files[lang] = cached_file
                        continue

                # 需要生成新音訊
                audio_file = os.path.join(self.temp_dir, f"cache_{cache_key}.mp3")

                async def generate_single(language, txt, vc, af):
                    print(f"  生成 {language}: {txt}")
                    communicate = self.edge_tts.Communicate(txt, vc)
                    await communicate.save(af)
                    return language, af

                tasks.append(generate_single(lang, text, voice, audio_file))

            # 並行執行所有生成任務
            if tasks:
                results = await asyncio.gather(*tasks)
                for lang, audio_file in results:
                    audio_files[lang] = audio_file
                    # 加入快取
                    cache_key = self._get_cache_key(descriptions[lang], self.voices[lang])
                    self.audio_cache[cache_key] = audio_file
                    self._manage_cache_size()

        # 執行async生成 使用新的event loop避免衝突
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            new_loop.run_until_complete(generate_all_audio())
        finally:
            new_loop.close()

        # 使用ffmpeg切片並混合
        print("\n規劃語言切換...")

        # 先取得最短的音訊長度（避免超出範圍）
        import json
        durations = {}
        for lang, file in audio_files.items():
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", file],
                capture_output=True, text=True
            )
            info = json.loads(result.stdout)
            durations[lang] = float(info["format"]["duration"])

        # 使用最短的音訊長度
        target_duration = min(durations.values())

        # 規劃切換時間點（減少片段數量加快處理）
        segments = []
        current_time = 0.0
        languages = list(audio_files.keys())

        # 追蹤每種語言已使用的時間
        lang_offsets = {lang: 0.0 for lang in languages}

        while current_time < target_duration:
            lang = random.choice(languages)
            duration = random.uniform(0.5, 1.5)  # 增加片段長度

            if current_time + duration > target_duration:
                duration = target_duration - current_time

            # 檢查該語言是否還有足夠的音訊
            if lang_offsets[lang] + duration > durations[lang]:
                # 如果超出，重新從頭開始
                lang_offsets[lang] = 0.0

            segments.append({
                "lang": lang,
                "start": lang_offsets[lang],  # 從該語言的當前位置切片
                "duration": duration
            })

            print(f"  {current_time:.1f}s - {current_time+duration:.1f}s: {lang} (from {lang_offsets[lang]:.1f}s)")

            lang_offsets[lang] += duration  # 更新該語言的位置
            current_time += duration

        # 切片並合併
        print("\n生成混合音訊...")
        segment_files = []

        for i, seg in enumerate(segments):
            output_file = os.path.join(self.temp_dir, f"seg_{i}.mp3")
            subprocess.run([
                "ffmpeg", "-y", "-i", audio_files[seg["lang"]],
                "-ss", str(seg["start"]),
                "-t", str(seg["duration"]),
                "-c", "copy",
                output_file
            ], capture_output=True)
            segment_files.append(output_file)

        # 合併所有片段
        concat_file = os.path.join(self.temp_dir, "concat_list.txt")
        with open(concat_file, "w") as f:
            for seg_file in segment_files:
                f.write(f"file '{seg_file}'\n")

        final_output = os.path.join(self.temp_dir, "mixed.mp3")
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            final_output
        ], capture_output=True)

        # 播放混合音訊（使用循環填補空白）
        print("播放混合音訊...")
        self._play_audio(final_output, blocking=blocking, loop=True)

        # 注意：不再清理臨時檔案，因為音訊可能還在播放中
        # 檔案會在temp_dir中累積，但會在cleanup()時一次清理

        return True

    def _speak_multilang(self, text: str, blocking: bool) -> bool:
        """多語言混合朗讀 - 舊版本保留"""
        import random

        chars = list(text)
        parts = []
        current_part = []
        group_size = random.randint(1, 3)

        for char in chars:
            if char.strip() == '':
                continue
            current_part.append(char)
            if len(current_part) >= group_size:
                parts.append(''.join(current_part))
                current_part = []
                group_size = random.randint(1, 3)

        if current_part:
            parts.append(''.join(current_part))

        audio_files = []
        languages = list(self.voices.keys())

        for part in parts:
            if not part.strip():
                continue
            lang = random.choice(languages)
            voice = self.voices[lang]
            print(f"  {lang}: {part}")
            audio_file = os.path.join(self.temp_dir, f"speech_{len(audio_files)}.mp3")

            async def generate():
                communicate = self.edge_tts.Communicate(part, voice)
                await communicate.save(audio_file)

            try:
                asyncio.run(generate())
                audio_files.append(audio_file)
            except RuntimeError:
                loop = asyncio.get_event_loop()
                loop.run_until_complete(generate())
                audio_files.append(audio_file)
            except Exception as e:
                print(f"  跳過: {e}")
                continue

        for audio_file in audio_files:
            if os.path.exists(audio_file):
                self._play_audio(audio_file, blocking=True)

        for audio_file in audio_files:
            if os.path.exists(audio_file):
                os.remove(audio_file)

        return True

    def _speak_edge_tts(self, text: str, blocking: bool, language: Optional[str] = None, loop: bool = False) -> bool:
        """使用 Edge TTS 朗讀（支援快取）"""
        # 如果指定語言，使用該語言的聲音
        voice = self.voices[language] if language and language in self.voices else self.voice

        # 檢查快取
        cache_key = self._get_cache_key(text, voice)

        if cache_key in self.audio_cache:
            cached_file = self.audio_cache[cache_key]
            if os.path.exists(cached_file):
                # 使用快取的音訊
                return self._play_audio(cached_file, blocking, loop)

        # 生成新音訊
        audio_file = os.path.join(self.temp_dir, f"cache_{cache_key}.mp3")

        async def generate():
            communicate = self.edge_tts.Communicate(text, voice)
            await communicate.save(audio_file)

        # 執行異步任務
        try:
            asyncio.run(generate())
        except RuntimeError:
            # 如果已經在 event loop 中
            loop = asyncio.get_event_loop()
            loop.run_until_complete(generate())

        # 加入快取
        self.audio_cache[cache_key] = audio_file
        self._manage_cache_size()

        # 播放音訊
        return self._play_audio(audio_file, blocking, loop)

    def _speak_coqui(self, text: str, blocking: bool) -> bool:
        """使用 Coqui TTS 朗讀"""
        audio_file = os.path.join(self.temp_dir, "speech.wav")

        # 生成語音
        self.tts.tts_to_file(
            text=text,
            language=self.tts_language,
            file_path=audio_file
        )

        # 播放音訊
        return self._play_audio(audio_file, blocking)

    def _speak_macos(self, text: str, blocking: bool) -> bool:
        """使用 macOS say 指令朗讀"""
        cmd = ["say"]

        if self.voice:
            cmd.extend(["-v", self.voice])

        cmd.append(text)

        try:
            if blocking:
                subprocess.run(cmd, check=True)
            else:
                subprocess.Popen(cmd)
            return True
        except Exception as e:
            print(f"macOS say 執行失敗: {e}")
            return False

    def _play_audio(self, audio_file: str, blocking: bool, loop: bool = False) -> bool:
        """
        播放音訊檔案

        Args:
            audio_file: 音訊檔案路徑
            blocking: 是否等待播放完成
            loop: 是否循環播放

        Returns:
            bool: 是否成功
        """
        try:
            # 如果指定了音訊裝置，使用 sounddevice 播放
            if self.audio_device is not None:
                return self._play_audio_with_sounddevice(audio_file, blocking, loop)
            else:
                # 使用系統預設播放器 (afplay)
                return self._play_audio_with_afplay(audio_file, blocking, loop)

        except Exception as e:
            print(f"播放音訊失敗: {e}")
            return False

    def _play_audio_with_afplay(self, audio_file: str, blocking: bool, loop: bool = False) -> bool:
        """使用 afplay 播放音訊（系統預設）"""
        # 停止之前的循環播放
        if self.current_audio_process and self.current_audio_process.poll() is None:
            self.should_stop_loop = True
            self.current_audio_process.terminate()
            import time
            time.sleep(0.1)

        self.should_stop_loop = False

        if loop:
            # 循環播放：在背景執行緒持續播放
            import threading
            def loop_play():
                while not self.should_stop_loop:
                    try:
                        process = subprocess.Popen(["afplay", audio_file])
                        self.current_audio_process = process
                        process.wait()
                        if self.should_stop_loop:
                            break
                    except Exception as e:
                        print(f"循環播放錯誤: {e}")
                        break

            threading.Thread(target=loop_play, daemon=True).start()
        else:
            # 一次性播放
            if blocking:
                subprocess.run(["afplay", audio_file], check=True)
            else:
                subprocess.Popen(["afplay", audio_file])

        return True

    def _play_audio_with_sounddevice(self, audio_file: str, blocking: bool, loop: bool = False) -> bool:
        """使用 sounddevice 播放音訊到指定裝置"""
        import sounddevice as sd
        import soundfile as sf
        import numpy as np

        # 停止之前的播放
        try:
            sd.stop()
        except:
            pass

        # 停止之前的循環播放
        if self.current_audio_process:
            self.should_stop_loop = True
            import time
            time.sleep(0.2)

        self.should_stop_loop = False

        # 讀取音訊檔案
        data, samplerate = sf.read(audio_file, dtype='float32')

        # 處理單聲道輸出
        if self.audio_device.get('is_mono', False) and self.audio_device.get('channel') is not None:
            # 需要輸出到特定通道
            device_id = self.audio_device['id']
            channel = self.audio_device['channel']
            total_channels = self.audio_device['channels']

            # 如果音訊是立體聲，轉換為單聲道
            if len(data.shape) > 1:
                data = np.mean(data, axis=1)

            # 建立多聲道陣列，只在指定通道填入數據
            multichannel_data = np.zeros((len(data), total_channels), dtype='float32')
            multichannel_data[:, channel] = data

            output_data = multichannel_data
        else:
            # 使用完整裝置（立體聲或多聲道）
            device_id = self.audio_device['id']
            output_data = data

        def play_once():
            try:
                sd.play(output_data, samplerate=samplerate, device=device_id)
                if blocking:
                    sd.wait()
            except Exception as e:
                print(f"播放錯誤: {e}")

        if loop:
            # 循環播放
            import threading
            def loop_play():
                while not self.should_stop_loop:
                    try:
                        sd.play(output_data, samplerate=samplerate, device=device_id)
                        sd.wait()
                        if self.should_stop_loop:
                            break
                    except Exception as e:
                        print(f"循環播放錯誤: {e}")
                        break

            self.current_audio_process = True  # 標記為正在播放
            threading.Thread(target=loop_play, daemon=True).start()
        else:
            play_once()

        return True

    def cleanup(self):
        """清理暫存檔案"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            print("暫存檔案已清理")

    def __del__(self):
        """清理資源"""
        self.cleanup()


# 測試程式碼
if __name__ == "__main__":
    import sys
    import time

    print("=== TTS 引擎測試 ===\n")

    # 選擇後端
    print("選擇 TTS 後端:")
    print("1. edge-tts (推薦，輕量快速)")
    print("2. coqui (高品質，較慢)")
    print("3. macos (內建，最簡單)")

    choice = input("\n請輸入 1, 2 或 3: ").strip()

    if choice == "1":
        backend = "edge-tts"
    elif choice == "2":
        backend = "coqui"
    elif choice == "3":
        backend = "macos"
    else:
        print("無效選擇")
        sys.exit(1)

    # 選擇語言
    print("\n選擇語言:")
    print("1. 繁體中文 (zh-TW)")
    print("2. 簡體中文 (zh-CN)")

    lang_choice = input("\n請輸入 1 或 2: ").strip()

    if lang_choice == "1":
        language = "zh-TW"
    elif lang_choice == "2":
        language = "zh-CN"
    else:
        print("無效選擇")
        sys.exit(1)

    # 創建 TTS 引擎
    try:
        tts = TTSEngine(backend=backend, language=language)
    except Exception as e:
        print(f"\n初始化失敗: {e}")
        sys.exit(1)

    # 測試文字
    test_texts = [
        "你好，這是語音合成測試。",
        "畫面中有一個人正在使用電腦。",
        "天氣很好，陽光明媚。"
    ]

    print("\n開始測試...\n")

    for i, text in enumerate(test_texts, 1):
        print(f"\n[{i}/{len(test_texts)}] 朗讀: {text}")

        start_time = time.time()
        success = tts.speak(text, blocking=True)
        duration = time.time() - start_time

        if success:
            print(f"✓ 完成 (耗時: {duration:.2f} 秒)")
        else:
            print("✗ 失敗")

        if i < len(test_texts):
            time.sleep(0.5)

    # 互動測試
    print("\n\n=== 互動模式 ===")
    print("輸入文字進行朗讀，輸入 'q' 退出\n")

    while True:
        text = input("請輸入文字: ").strip()

        if text.lower() == 'q':
            break

        if text:
            tts.speak(text, blocking=True)

    print("\n測試完成")
    tts.cleanup()
