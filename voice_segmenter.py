#!/usr/bin/env python3
"""
Voice Segmenter - 語音切割與節奏對齊模組
用於將 TTS 生成的語音切割成音節並對齊到節拍網格
"""

import os
import tempfile
import asyncio
import numpy as np
import librosa
import edge_tts
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class VoiceSegment:
    """語音片段資料結構"""
    audio: np.ndarray  # 音訊資料
    duration: float    # 持續時間(秒)
    text: str         # 對應文字
    onset: float      # 起始時間(秒)


class VoiceSegmenter:
    """語音切割器"""

    def __init__(self, sample_rate: int = 44100):
        """
        初始化語音切割器

        Args:
            sample_rate: 目標取樣率
        """
        self.sample_rate = sample_rate
        self.temp_dir = tempfile.gettempdir()

    async def generate_voice_async(
        self,
        text: str,
        voice: str = "zh-TW-HsiaoChenNeural"
    ) -> np.ndarray:
        """
        使用 edge-tts 生成語音

        Args:
            text: 要合成的文字
            voice: TTS 語音選項

        Returns:
            音訊陣列
        """
        # 生成暫存檔案路徑
        temp_path = os.path.join(self.temp_dir, f"tts_{hash(text)}.wav")

        # 使用 edge-tts 生成語音
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(temp_path)

        # 載入音訊
        audio, sr = librosa.load(temp_path, sr=self.sample_rate, mono=True)

        # 清理暫存檔案
        if os.path.exists(temp_path):
            os.remove(temp_path)

        return audio

    def generate_voice(
        self,
        text: str,
        voice: str = "zh-TW-HsiaoChenNeural"
    ) -> np.ndarray:
        """
        同步版本的語音生成

        Args:
            text: 要合成的文字
            voice: TTS 語音選項

        Returns:
            音訊陣列
        """
        return asyncio.run(self.generate_voice_async(text, voice))

    def detect_onsets(
        self,
        audio: np.ndarray,
        hop_length: int = 512
    ) -> np.ndarray:
        """
        偵測音訊的起始點(onset)

        Args:
            audio: 音訊陣列
            hop_length: 分析視窗跳躍長度

        Returns:
            起始點時間陣列(秒)
        """
        # 使用 librosa 偵測 onset
        onset_frames = librosa.onset.onset_detect(
            y=audio,
            sr=self.sample_rate,
            hop_length=hop_length,
            backtrack=True,
            units='frames'
        )

        # 轉換為時間(秒)
        onset_times = librosa.frames_to_time(
            onset_frames,
            sr=self.sample_rate,
            hop_length=hop_length
        )

        return onset_times

    def segment_by_syllables(
        self,
        audio: np.ndarray,
        text: str,
        target_segments: int = None
    ) -> List[VoiceSegment]:
        """
        將音訊切割成音節

        Args:
            audio: 音訊陣列
            text: 原始文字
            target_segments: 目標片段數量(None=自動偵測)

        Returns:
            語音片段列表
        """
        # 偵測 onset
        onset_times = self.detect_onsets(audio)

        # 如果沒有偵測到 onset 或只有一個，使用整段音訊
        if len(onset_times) < 2:
            return [VoiceSegment(
                audio=audio,
                duration=len(audio) / self.sample_rate,
                text=text,
                onset=0.0
            )]

        # 添加結束時間
        onset_times = np.append(onset_times, len(audio) / self.sample_rate)

        # 創建片段
        segments = []

        # 估算每個字符對應的 onset
        char_count = len(text)
        chars_per_segment = max(1, char_count // len(onset_times))

        for i in range(len(onset_times) - 1):
            start_sample = int(onset_times[i] * self.sample_rate)
            end_sample = int(onset_times[i + 1] * self.sample_rate)

            # 提取音訊片段
            segment_audio = audio[start_sample:end_sample]

            # 估算對應的文字
            text_start = i * chars_per_segment
            text_end = min((i + 1) * chars_per_segment, char_count)
            segment_text = text[text_start:text_end]

            segments.append(VoiceSegment(
                audio=segment_audio,
                duration=len(segment_audio) / self.sample_rate,
                text=segment_text,
                onset=onset_times[i]
            ))

        return segments

    def time_stretch_segment(
        self,
        segment: VoiceSegment,
        target_duration: float
    ) -> np.ndarray:
        """
        時間伸縮語音片段以符合目標長度

        Args:
            segment: 語音片段
            target_duration: 目標持續時間(秒)

        Returns:
            伸縮後的音訊陣列
        """
        # 計算伸縮比例
        stretch_ratio = segment.duration / target_duration

        # 使用 librosa 進行時間伸縮
        stretched = librosa.effects.time_stretch(
            segment.audio,
            rate=stretch_ratio
        )

        # 確保長度精確
        target_samples = int(target_duration * self.sample_rate)

        if len(stretched) > target_samples:
            # 裁剪
            stretched = stretched[:target_samples]
        elif len(stretched) < target_samples:
            # 補零
            stretched = np.pad(
                stretched,
                (0, target_samples - len(stretched)),
                mode='constant'
            )

        return stretched

    def align_to_grid(
        self,
        segments: List[VoiceSegment],
        step_duration: float,
        total_steps: int = 16
    ) -> List[Tuple[int, np.ndarray]]:
        """
        將語音片段對齊到節拍網格

        Args:
            segments: 語音片段列表
            step_duration: 每步的持續時間(秒)
            total_steps: 總步數(預設16步 = 1小節)

        Returns:
            (步數位置, 音訊陣列) 的列表
        """
        aligned = []

        # 計算每個片段應該放置的步數位置
        steps_per_segment = total_steps / len(segments)

        for i, segment in enumerate(segments):
            # 計算步數位置(整數)
            step = int(i * steps_per_segment)

            # 時間伸縮以符合網格
            stretched_audio = self.time_stretch_segment(
                segment,
                step_duration
            )

            aligned.append((step, stretched_audio))

        return aligned

    def generate_voice_pattern(
        self,
        text: str,
        step_duration: float,
        total_steps: int = 16,
        voice: str = "zh-TW-HsiaoChenNeural"
    ) -> List[Tuple[int, np.ndarray]]:
        """
        完整流程：生成語音 -> 切割 -> 對齊到網格

        Args:
            text: 要合成的文字
            step_duration: 每步的持續時間(秒)
            total_steps: 總步數
            voice: TTS 語音選項

        Returns:
            對齊到網格的語音片段列表
        """
        print(f"生成語音: {text}")

        # 1. 生成語音
        audio = self.generate_voice(text, voice)

        # 2. 切割成音節
        segments = self.segment_by_syllables(audio, text)
        print(f"偵測到 {len(segments)} 個音節")

        # 3. 對齊到網格
        aligned = self.align_to_grid(segments, step_duration, total_steps)
        print(f"對齊到 {len(aligned)} 個步數位置")

        return aligned


def main():
    """測試函數"""
    print("Voice Segmenter 測試")
    print("=" * 50)

    # 創建切割器
    segmenter = VoiceSegmenter(sample_rate=44100)

    # 測試文字
    test_text = "今天天氣很好"

    # 假設 BPM 140，每步持續時間
    bpm = 140
    beat_duration = 60.0 / bpm
    step_duration = beat_duration / 4  # 16分音符

    print(f"\n測試文字: {test_text}")
    print(f"BPM: {bpm}")
    print(f"每步時長: {step_duration:.4f} 秒\n")

    # 生成對齊的語音片段
    aligned_segments = segmenter.generate_voice_pattern(
        text=test_text,
        step_duration=step_duration,
        total_steps=16
    )

    print("\n對齊結果:")
    for step, audio in aligned_segments:
        duration = len(audio) / 44100
        print(f"  步數 {step:2d}: 長度 {len(audio)} 樣本 ({duration:.4f} 秒)")

    print("\n測試完成")


if __name__ == '__main__':
    main()
