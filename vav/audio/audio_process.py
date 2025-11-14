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
# from .effects.ellen_ripley import EllenRipleyEffectChain
from .alien4_wrapper import Alien4EffectChain
from ..cv_generator.envelope import DecayEnvelope


def audio_process_worker(
    cv_queue: mp.Queue,
    cv_output_queue: mp.Queue,
    control_queue: mp.Queue,
    config: dict,
    stop_event: mp.Event,
    shared_audio_buffers: list
):
    """
    獨立 process 的 worker function

    Args:
        cv_queue: 從 main process 接收 CV 值 (SEQ1, SEQ2, scan_loop_completed)
        cv_output_queue: 回傳 CV 值給 GUI (6 channels: ENV1-4, SEQ1-2)
        control_queue: 接收控制訊息 (envelope decay 等)
        config: 音訊設定
        stop_event: 停止信號
        shared_audio_buffers: shared memory buffers for display (4 channels)
    """

    # 初始化音訊系統
    audio_config = config.get("audio", {})
    sample_rate = audio_config.get("sample_rate", 48000)
    buffer_size = audio_config.get("buffer_size", 256)

    # Display buffer parameters (matching Multiverse.cpp)
    # Show 50ms of data for smooth visualization
    MS_PER_SCREEN = 50.0
    DISPLAY_WIDTH = len(shared_audio_buffers[0]) if shared_audio_buffers else 1920
    samples_per_screen = sample_rate * MS_PER_SCREEN / 1000.0
    samples_per_pixel = samples_per_screen / DISPLAY_WIDTH

    # Per-channel display state
    display_buffer_indices = [0] * 4  # Current write position in circular buffer
    frame_counters = [0.0] * 4  # Frame accumulator for downsampling

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
    # ellen_ripley = EllenRipleyEffectChain(sample_rate=sample_rate)
    alien4 = Alien4EffectChain(sample_rate=sample_rate)

    # Pre-warm
    dummy_audio = np.zeros((256, 2), dtype=np.float32)
    _ = alien4.process(dummy_audio[:, 0], dummy_audio[:, 1])

    # CV generators (4 envelopes: ENV1-4)
    envelopes = []
    cv_config = config.get("cv", {})
    for i in range(4):
        env = DecayEnvelope(
            sample_rate=sample_rate,
            decay_time=cv_config.get(f"decay_{i}_time", 1.0),
        )
        envelopes.append(env)

    # CV values (6 channels: ENV1-4, SEQ1-2)
    cv_values = np.zeros(6, dtype=np.float32)

    # SEQ1/SEQ2 從 queue 接收
    seq1_value = 0.0
    seq2_value = 0.0
    scan_loop_completed = False  # 掃描循環完成標記

    # Channel levels
    channel_levels = [1.0, 1.0, 1.0, 1.0]

    def audio_callback(indata: np.ndarray, frames: int) -> np.ndarray:
        """Audio callback - 在獨立 process 中執行"""
        nonlocal cv_values, seq1_value, seq2_value, scan_loop_completed

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
                    alien4.set_delay_params(
                        time_l=msg.get('time_l'),
                        time_r=msg.get('time_r'),
                        feedback=msg.get('feedback'),
                        chaos_enabled=msg.get('chaos_enabled'),
                        wet_dry=msg.get('wet_dry')
                    )

                elif msg_type == 'set_ellen_ripley_grain':
                    alien4.set_grain_params(
                        size=msg.get('size'),
                        density=msg.get('density'),
                        position=msg.get('position'),
                        chaos_enabled=msg.get('chaos_enabled'),
                        wet_dry=msg.get('wet_dry')
                    )

                elif msg_type == 'set_ellen_ripley_reverb':
                    alien4.set_reverb_params(
                        room_size=msg.get('room_size'),
                        damping=msg.get('damping'),
                        decay=msg.get('decay'),
                        chaos_enabled=msg.get('chaos_enabled'),
                        wet_dry=msg.get('wet_dry')
                    )

                elif msg_type == 'set_ellen_ripley_chaos':
                    alien4.set_chaos_params(
                        rate=msg.get('rate'),
                        amount=msg.get('amount'),
                        shape=msg.get('shape')
                    )

                # Alien4 控制訊息
                elif msg_type == 'set_alien4_documenta':
                    alien4.set_documenta_params(
                        mix=msg.get('mix'),
                        feedback=msg.get('feedback'),
                        speed=msg.get('speed'),
                        eq_low=msg.get('eq_low'),
                        eq_mid=msg.get('eq_mid'),
                        eq_high=msg.get('eq_high'),
                        poly=msg.get('poly')
                    )

                elif msg_type == 'set_alien4_recording':
                    alien4.set_recording(msg.get('enabled'))

                elif msg_type == 'set_alien4_delay':
                    alien4.set_delay_params(
                        time_l=msg.get('time_l'),
                        time_r=msg.get('time_r'),
                        feedback=msg.get('feedback'),
                        wet_dry=msg.get('wet_dry')
                    )

                elif msg_type == 'set_alien4_reverb':
                    alien4.set_reverb_params(
                        decay=msg.get('decay'),
                        wet_dry=msg.get('wet_dry')
                    )

                elif msg_type == 'set_alien4_scan':
                    alien4.set_scan(msg.get('value'))

                elif msg_type == 'set_alien4_gate_threshold':
                    alien4.set_gate_threshold(msg.get('value'))

        except:
            pass

        # 嘗試從 queue 讀取最新的 SEQ 值和觸發事件 (non-blocking)
        # 接收 7 個值: seq1, seq2, scan_loop_completed, env1_trigger, env2_trigger, env3_trigger, env4_trigger
        env1_trigger = False
        env2_trigger = False
        env3_trigger = False
        env4_trigger = False
        try:
            while not cv_queue.empty():
                data = cv_queue.get_nowait()
                if len(data) == 7:
                    seq1_value, seq2_value, scan_loop_completed, env1_trigger, env2_trigger, env3_trigger, env4_trigger = data
                elif len(data) == 3:
                    # 相容舊版 (只有 3 個值)
                    seq1_value, seq2_value, scan_loop_completed = data
                else:
                    # 相容更舊版 (只有 2 個值)
                    seq1_value, seq2_value = data[:2]
                    scan_loop_completed = False
        except:
            pass

        # Envelope 觸發處理 (完全信任 contour_scanner 的 retrigger 判斷)
        # contour_scanner 已經處理了 retrigger 保護，這裡直接執行觸發
        # ENV1: 觸發事件
        if env1_trigger:
            envelopes[0].trigger()
            # 立即更新 cv_values 讓 GUI 看到觸發
            cv_values[0] = envelopes[0].process()

        # ENV2: 觸發事件
        if env2_trigger:
            envelopes[1].trigger()
            # 立即更新 cv_values 讓 GUI 看到觸發
            cv_values[1] = envelopes[1].process()

        # ENV3: 觸發事件
        if env3_trigger:
            envelopes[2].trigger()
            # 立即更新 cv_values 讓 GUI 看到觸發
            cv_values[2] = envelopes[2].process()

        # ENV4: 觸發事件
        if env4_trigger:
            envelopes[3].trigger()
            # 立即更新 cv_values 讓 GUI 看到觸發
            cv_values[3] = envelopes[3].process()

        # Build output array first
        outdata = np.zeros((frames, audio_io.output_channels), dtype=np.float32)

        # Process CV generators (sample-accurate)
        for i in range(frames):
            # Update envelopes (ENV1-4)
            for j, env in enumerate(envelopes):
                cv_values[j] = env.process()

            # SEQ1/SEQ2 from queue (不會阻塞)
            cv_values[4] = seq1_value
            cv_values[5] = seq2_value

            # Write CV outputs sample-accurately (channels 2-7: ENV1-4, SEQ1-2)
            # ES-8 使用 -1 到 +1 的音訊範圍對應 -10V 到 +10V
            # 所以 0-10V 需要映射到 0 到 +1
            if audio_io.output_channels >= 8:
                for ch in range(6):
                    outdata[i, 2 + ch] = cv_values[ch]  # 0-1 範圍對應 0-10V

        # 回傳最後的 CV 值給 GUI (non-blocking)
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

        # Seq1 controls Alien4 Scan position (0.0-1.0 voltage directly maps to scan)
        alien4.set_scan(seq1_value)

        # Process through Alien4 (returns 3 values: left, right, chaos_cv)
        processed_left, processed_right, _ = alien4.process(master_left, master_right)

        # Fill audio outputs (L/R) in outdata (CV已經在上面的loop中填充)
        outdata[:, 0] = processed_left  # Audio L
        outdata[:, 1] = processed_right  # Audio R

        # Update display buffer (circular buffer with downsampling, matching Multiverse.cpp)
        # This prevents visual flickering by downsampling audio to display resolution
        for ch in range(4):
            if indata.shape[1] > ch:
                # Process each sample in the audio buffer
                for sample_idx in range(frames):
                    voltage = indata[sample_idx, ch]

                    # Increment frame counter
                    frame_counters[ch] += 1.0

                    # Write to display buffer when accumulated enough samples
                    if frame_counters[ch] >= samples_per_pixel:
                        # Write to circular buffer
                        buffer_idx = display_buffer_indices[ch]

                        # Get shared memory view and write sample
                        shared_np = np.frombuffer(shared_audio_buffers[ch], dtype=np.float32)
                        shared_np[buffer_idx] = voltage

                        # Advance circular buffer index
                        display_buffer_indices[ch] = (buffer_idx + 1) % DISPLAY_WIDTH
                        frame_counters[ch] = 0.0

        return outdata

    # 啟動 audio stream
    print("[Audio Process] Starting audio stream...")
    try:
        audio_io.start(audio_callback)
        print("[Audio Process] Audio stream started")

        # 等待停止信號
        while not stop_event.is_set():
            time.sleep(0.1)

        # 停止 audio stream
        print("[Audio Process] Stopping audio stream...")
        audio_io.stop()
        print("[Audio Process] Audio process terminated")
    except Exception as e:
        print(f"[Audio Process] ERROR: Failed to start audio stream: {e}")
        print("[Audio Process] Audio process will terminate")
        # Don't raise - let the process exit gracefully
        return


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

        # Shared memory for audio buffers (for Multiverse)
        # Use display width from camera config, default to 1920
        camera_config = config.get("camera", {})
        display_width = camera_config.get("width", 1920)
        self.shared_audio_buffers = [
            mp.RawArray('f', display_width) for _ in range(4)
        ]
        print(f"[AudioProcess] Created shared display buffers: {display_width} samples per channel")

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
            args=(self.cv_queue, self.cv_output_queue, self.control_queue, self.config, self.stop_event, self.shared_audio_buffers),
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

    def send_cv_values(self, seq1: float, seq2: float, scan_loop_completed: bool = False,
                      env1_trigger: bool = False, env2_trigger: bool = False,
                      env3_trigger: bool = False, env4_trigger: bool = False):
        """
        發送 SEQ1/SEQ2 值和 envelope 觸發事件到 audio process

        Args:
            seq1: SEQ1 value (0-1)
            seq2: SEQ2 value (0-1)
            scan_loop_completed: 掃描循環完成標記 (用於 ENV4 觸發)
            env1_trigger: ENV1 觸發事件
            env2_trigger: ENV2 觸發事件
            env3_trigger: ENV3 觸發事件
            env4_trigger: ENV4 觸發事件
        """
        if not self.running:
            return

        try:
            # Non-blocking put，避免阻塞 vision thread
            self.cv_queue.put_nowait((seq1, seq2, scan_loop_completed,
                                     env1_trigger, env2_trigger, env3_trigger, env4_trigger))
        except:
            # Queue full，忽略
            pass

    def get_cv_values(self) -> Optional[np.ndarray]:
        """
        從 audio process 獲取 CV 值 (for GUI display)

        Returns:
            6-element array: ENV1, ENV2, ENV3, ENV4, SEQ1, SEQ2
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

    # Alien4 控制方法
    def set_alien4_documenta_params(self, mix=None, feedback=None, speed=None,
                                   eq_low=None, eq_mid=None, eq_high=None, poly=None):
        """設定 Alien4 Documenta (Loop+EQ) 參數"""
        if not self.running:
            return
        try:
            msg = {
                'type': 'set_alien4_documenta',
                'mix': mix,
                'feedback': feedback,
                'speed': speed,
                'eq_low': eq_low,
                'eq_mid': eq_mid,
                'eq_high': eq_high,
                'poly': poly
            }
            self.control_queue.put_nowait(msg)
        except:
            pass

    def set_alien4_recording(self, enabled):
        """設定 Alien4 錄音狀態"""
        if not self.running:
            return
        try:
            msg = {
                'type': 'set_alien4_recording',
                'enabled': enabled
            }
            self.control_queue.put_nowait(msg)
        except:
            pass

    def set_alien4_delay_params(self, time_l=None, time_r=None, feedback=None, wet_dry=None):
        """設定 Alien4 delay 參數"""
        if not self.running:
            return
        try:
            msg = {
                'type': 'set_alien4_delay',
                'time_l': time_l,
                'time_r': time_r,
                'feedback': feedback,
                'wet_dry': wet_dry
            }
            self.control_queue.put_nowait(msg)
        except:
            pass

    def set_alien4_reverb_params(self, decay=None, wet_dry=None):
        """設定 Alien4 reverb 參數"""
        if not self.running:
            return
        try:
            msg = {
                'type': 'set_alien4_reverb',
                'decay': decay,
                'wet_dry': wet_dry
            }
            self.control_queue.put_nowait(msg)
        except:
            pass

    def set_alien4_scan(self, value):
        """設定 Alien4 scan position"""
        if not self.running:
            return
        try:
            msg = {
                'type': 'set_alien4_scan',
                'value': value
            }
            self.control_queue.put_nowait(msg)
        except:
            pass

    def set_alien4_gate_threshold(self, value):
        """設定 Alien4 gate threshold"""
        if not self.running:
            return
        try:
            msg = {
                'type': 'set_alien4_gate_threshold',
                'value': value
            }
            self.control_queue.put_nowait(msg)
        except:
            pass
