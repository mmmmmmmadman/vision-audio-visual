"""
獨立的 Audio Process - 用 multiprocessing 實作
完全獨立於 main process，避免 GIL 影響
"""

import numpy as np
import multiprocessing as mp
from typing import Optional
import time
import sys

# 設定 multiprocessing 為 spawn 模式避免 macOS fork 問題
if sys.platform == 'darwin':
    try:
        mp.set_start_method('spawn')
    except RuntimeError:
        pass  # 已經設定過了

from .io import AudioIO
from .mixer import StereoMixer
from .effects.ellen_ripley import EllenRipleyEffectChain
from ..cv_generator.envelope import DecayEnvelope


def audio_process_worker(
    cv_queue: mp.Queue,
    cv_output_queue: mp.Queue,
    control_queue: mp.Queue,
    config: dict,
    stop_event: mp.Event
):
    """
    獨立 process 的 worker function

    Args:
        cv_queue: 從 main process 接收 CV 值 (SEQ1, SEQ2)
        cv_output_queue: 回傳 CV 值給 GUI (5 channels)
        control_queue: 接收控制訊息 (envelope decay 等)
        config: 音訊設定
        stop_event: 停止信號
    """

    # 初始化音訊系統
    audio_config = config.get("audio", {})
    sample_rate = audio_config.get("sample_rate", 48000)
    buffer_size = audio_config.get("buffer_size", 256)

    # 從 config 取得正確的 channel 數量和裝置 ID
    input_channels = audio_config.get("input_channels", 4)
    output_channels = audio_config.get("output_channels", 7)
    input_device = audio_config.get("input_device")
    output_device = audio_config.get("output_device")

    # DEBUG
    print(f"[Audio Process] Config received:")
    print(f"  input_channels: {input_channels}")
    print(f"  output_channels: {output_channels}")
    print(f"  input_device: {input_device}")
    print(f"  output_device: {output_device}")

    # 創建 AudioIO（使用 config 中已調整好的 channel 數量）
    audio_io = AudioIO(
        sample_rate=sample_rate,
        buffer_size=buffer_size,
        input_channels=input_channels,
        output_channels=output_channels,
    )

    # 直接設定裝置 ID（不透過 set_devices 避免重新 query）
    audio_io.input_device = input_device
    audio_io.output_device = output_device

    # 初始化其他組件
    mixer = StereoMixer(num_channels=4)
    ellen_ripley = EllenRipleyEffectChain(sample_rate=sample_rate)

    # Pre-warm Numba JIT
    dummy_audio = np.zeros((256, 2), dtype=np.float32)
    _ = ellen_ripley.process(dummy_audio[:, 0], dummy_audio[:, 1])

    # CV generators (3 envelopes)
    envelopes = []
    cv_config = config.get("cv", {})
    for i in range(3):
        env = DecayEnvelope(
            sample_rate=sample_rate,
            decay_time=cv_config.get(f"decay_{i}_time", 1.0),
        )
        envelopes.append(env)

    # CV values (5 channels: ENV1-3, SEQ1-2)
    cv_values = np.zeros(5, dtype=np.float32)

    # SEQ1/SEQ2 從 queue 接收
    seq1_value = 0.0
    seq2_value = 0.0

    # Previous SEQ values for edge detection
    prev_seq1 = 0.0
    prev_seq2 = 0.0
    prev_x_greater = False
    prev_y_greater = False

    # Channel levels
    channel_levels = [1.0, 1.0, 1.0, 1.0]

    def audio_callback(indata: np.ndarray, frames: int) -> np.ndarray:
        """Audio callback - 在獨立 process 中執行"""
        nonlocal cv_values, seq1_value, seq2_value, prev_x_greater, prev_y_greater

        # 處理控制訊息 (non-blocking)
        try:
            while not control_queue.empty():
                msg = control_queue.get_nowait()
                msg_type = msg.get('type')

                if msg_type == 'set_envelope_decay':
                    env_idx = msg['env_idx']
                    decay_time = msg['decay_time']
                    if 0 <= env_idx < len(envelopes):
                        envelopes[env_idx].set_decay_time(decay_time)

                elif msg_type == 'set_channel_level':
                    channel = msg['channel']
                    level = msg['level']
                    if 0 <= channel < len(channel_levels):
                        channel_levels[channel] = level

                elif msg_type == 'set_ellen_ripley_delay':
                    ellen_ripley.set_delay_params(
                        time_l=msg.get('time_l'),
                        time_r=msg.get('time_r'),
                        feedback=msg.get('feedback'),
                        chaos_enabled=msg.get('chaos_enabled'),
                        wet_dry=msg.get('wet_dry')
                    )

                elif msg_type == 'set_ellen_ripley_grain':
                    ellen_ripley.set_grain_params(
                        size=msg.get('size'),
                        density=msg.get('density'),
                        position=msg.get('position'),
                        chaos_enabled=msg.get('chaos_enabled'),
                        wet_dry=msg.get('wet_dry')
                    )

                elif msg_type == 'set_ellen_ripley_reverb':
                    ellen_ripley.set_reverb_params(
                        room_size=msg.get('room_size'),
                        damping=msg.get('damping'),
                        decay=msg.get('decay'),
                        chaos_enabled=msg.get('chaos_enabled'),
                        wet_dry=msg.get('wet_dry')
                    )

                elif msg_type == 'set_ellen_ripley_chaos':
                    ellen_ripley.set_chaos_params(
                        rate=msg.get('rate'),
                        amount=msg.get('amount'),
                        shape=msg.get('shape')
                    )
        except:
            pass

        # 嘗試從 queue 讀取最新的 SEQ 值 (non-blocking)
        try:
            while not cv_queue.empty():
                seq1_value, seq2_value = cv_queue.get_nowait()
        except:
            pass

        # Envelope 觸發檢測 (基於 SEQ1 和 SEQ2 的邊緣檢測)
        # ENV1: X > Y 邊緣觸發
        x_greater = seq1_value > seq2_value
        if x_greater and not prev_x_greater:
            envelopes[0].trigger()
        prev_x_greater = x_greater

        # ENV2: Y > X 邊緣觸發
        y_greater = seq2_value > seq1_value
        if y_greater and not prev_y_greater:
            envelopes[1].trigger()
        prev_y_greater = y_greater

        # ENV3: 當 SEQ1 或 SEQ2 任一超過 0.5 時觸發
        if seq1_value > 0.5 or seq2_value > 0.5:
            if not envelopes[2].is_active:
                envelopes[2].trigger()

        # Process CV generators (sample-accurate)
        for i in range(frames):
            # Update envelopes
            for j, env in enumerate(envelopes):
                cv_values[j] = env.process()

            # SEQ1/SEQ2 from queue (不會阻塞)
            cv_values[3] = seq1_value
            cv_values[4] = seq2_value

        # 回傳 CV 值給 GUI (non-blocking)
        try:
            cv_output_queue.put_nowait(cv_values.copy())
        except:
            pass

        # Mix 4 input channels
        mixed_mono = np.zeros(frames, dtype=np.float32)
        for i in range(4):
            if indata.shape[1] > i:
                mixed_mono += indata[:, i] * channel_levels[i]

        # Convert mono to stereo
        mixed_left = mixed_mono
        mixed_right = mixed_mono

        # Process through mixer
        track_inputs = [(mixed_left, mixed_right)]
        for i in range(3):
            track_inputs.append((np.zeros_like(mixed_left), np.zeros_like(mixed_right)))

        master_left, master_right = mixer.process(track_inputs)

        # Process through Ellen Ripley (returns 3 values: left, right, chaos_cv)
        processed_left, processed_right, _ = ellen_ripley.process(master_left, master_right)

        # Build output array
        outdata = np.zeros((frames, audio_io.output_channels), dtype=np.float32)
        outdata[:, 0] = processed_left
        outdata[:, 1] = processed_right

        # CV outputs (channels 2-6)
        # ES-8 使用 -1 到 +1 的音訊範圍對應 -10V 到 +10V
        # 所以 0-10V 需要映射到 0 到 +1
        if audio_io.output_channels >= 7:
            for i in range(5):
                outdata[:, 2 + i] = cv_values[i]  # 0-1 範圍對應 0-10V

        return outdata

    # 啟動 audio stream
    print("[Audio Process] Starting audio stream...")
    audio_io.start(audio_callback)
    print("[Audio Process] Audio stream started")

    # 等待停止信號
    while not stop_event.is_set():
        time.sleep(0.1)

    # 停止 audio stream
    print("[Audio Process] Stopping audio stream...")
    audio_io.stop()
    print("[Audio Process] Audio process terminated")


class AudioProcess:
    """
    Audio Process 管理類別
    在獨立 process 中執行 audio callback，避免 GIL 影響
    """

    def __init__(self, config: dict):
        self.config = config
        self.process: Optional[mp.Process] = None
        self.cv_queue: Optional[mp.Queue] = None
        self.cv_output_queue: Optional[mp.Queue] = None
        self.control_queue: Optional[mp.Queue] = None
        self.stop_event: Optional[mp.Event] = None
        self.running = False

    def start(self):
        """啟動 audio process"""
        if self.running:
            return

        # 創建通訊管道
        self.cv_queue = mp.Queue(maxsize=10)  # SEQ1/SEQ2 input
        self.cv_output_queue = mp.Queue(maxsize=10)  # CV output to GUI
        self.control_queue = mp.Queue(maxsize=20)  # Control messages
        self.stop_event = mp.Event()

        # 啟動 process
        self.process = mp.Process(
            target=audio_process_worker,
            args=(self.cv_queue, self.cv_output_queue, self.control_queue, self.config, self.stop_event),
            daemon=False  # 不是 daemon，確保正常關閉
        )
        self.process.start()
        self.running = True
        print("[AudioProcess] Started")

    def stop(self):
        """停止 audio process"""
        if not self.running:
            return

        self.stop_event.set()
        self.process.join(timeout=3.0)
        if self.process.is_alive():
            print("[AudioProcess] Force terminating...")
            self.process.terminate()
            self.process.join(timeout=2.0)
            if self.process.is_alive():
                print("[AudioProcess] Force killing...")
                self.process.kill()
                self.process.join()

        self.running = False
        print("[AudioProcess] Stopped")

    def send_cv_values(self, seq1: float, seq2: float):
        """
        發送 SEQ1/SEQ2 值到 audio process

        Args:
            seq1: SEQ1 value (0-1)
            seq2: SEQ2 value (0-1)
        """
        if not self.running:
            return

        try:
            # Non-blocking put，避免阻塞 vision thread
            self.cv_queue.put_nowait((seq1, seq2))
        except:
            # Queue full，忽略
            pass

    def get_cv_values(self) -> Optional[np.ndarray]:
        """
        從 audio process 獲取 CV 值 (for GUI display)

        Returns:
            5-element array: ENV1, ENV2, ENV3, SEQ1, SEQ2
        """
        if not self.running:
            return None

        try:
            # Non-blocking get
            return self.cv_output_queue.get_nowait()
        except:
            return None

    def set_envelope_decay(self, env_idx: int, decay_time: float):
        """設定特定 envelope 的 decay time"""
        if not self.running:
            return
        try:
            msg = {
                'type': 'set_envelope_decay',
                'env_idx': env_idx,
                'decay_time': decay_time
            }
            self.control_queue.put_nowait(msg)
        except:
            pass

    def set_channel_level(self, channel: int, level: float):
        """設定特定 channel 的 input level"""
        if not self.running:
            return
        try:
            msg = {
                'type': 'set_channel_level',
                'channel': channel,
                'level': level
            }
            self.control_queue.put_nowait(msg)
        except:
            pass

    def set_ellen_ripley_delay_params(self, time_l=None, time_r=None, feedback=None,
                                     chaos_enabled=None, wet_dry=None):
        """設定 Ellen Ripley delay 參數"""
        if not self.running:
            return
        try:
            msg = {
                'type': 'set_ellen_ripley_delay',
                'time_l': time_l,
                'time_r': time_r,
                'feedback': feedback,
                'chaos_enabled': chaos_enabled,
                'wet_dry': wet_dry
            }
            self.control_queue.put_nowait(msg)
        except:
            pass

    def set_ellen_ripley_grain_params(self, size=None, density=None, position=None,
                                     chaos_enabled=None, wet_dry=None):
        """設定 Ellen Ripley grain 參數"""
        if not self.running:
            return
        try:
            msg = {
                'type': 'set_ellen_ripley_grain',
                'size': size,
                'density': density,
                'position': position,
                'chaos_enabled': chaos_enabled,
                'wet_dry': wet_dry
            }
            self.control_queue.put_nowait(msg)
        except:
            pass

    def set_ellen_ripley_reverb_params(self, room_size=None, damping=None, decay=None,
                                      chaos_enabled=None, wet_dry=None):
        """設定 Ellen Ripley reverb 參數"""
        if not self.running:
            return
        try:
            msg = {
                'type': 'set_ellen_ripley_reverb',
                'room_size': room_size,
                'damping': damping,
                'decay': decay,
                'chaos_enabled': chaos_enabled,
                'wet_dry': wet_dry
            }
            self.control_queue.put_nowait(msg)
        except:
            pass

    def set_ellen_ripley_chaos_params(self, rate=None, amount=None, shape=None):
        """設定 Ellen Ripley chaos 參數"""
        if not self.running:
            return
        try:
            msg = {
                'type': 'set_ellen_ripley_chaos',
                'rate': rate,
                'amount': amount,
                'shape': shape
            }
            self.control_queue.put_nowait(msg)
        except:
            pass
