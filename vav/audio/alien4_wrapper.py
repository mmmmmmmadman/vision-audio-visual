"""
Alien4 Wrapper - 相容 VAV 現有介面
"""

import numpy as np

# Import Alien4 C++ module
try:
    from . import alien4
    ALIEN4_AVAILABLE = True
except ImportError:
    print("[WARNING] Alien4 module not found, using placeholder")
    ALIEN4_AVAILABLE = False


class Alien4EffectChain:
    """
    Alien4 效果鏈包裝類別
    提供與 EllenRipley 相容的介面
    """

    def __init__(self, sample_rate=48000):
        self.sample_rate = sample_rate

        if ALIEN4_AVAILABLE:
            self.engine = alien4.AudioEngine(float(sample_rate))
        else:
            self.engine = None

        # 預設參數
        self.recording = True
        self.looping = True

    def set_delay_params(self, time_l=None, time_r=None, feedback=None,
                        chaos_enabled=None, wet_dry=None):
        """設定 Delay 參數 (相容 EllenRipley 介面)"""
        if not ALIEN4_AVAILABLE or self.engine is None:
            return

        # Store current delay times if we need to preserve one
        if time_l is not None or time_r is not None:
            # Get current values if not provided
            if not hasattr(self, '_delay_time_l'):
                self._delay_time_l = 0.25
            if not hasattr(self, '_delay_time_r'):
                self._delay_time_r = 0.25

            if time_l is not None:
                self._delay_time_l = float(time_l)
            if time_r is not None:
                self._delay_time_r = float(time_r)

            self.engine.set_delay_time(self._delay_time_l, self._delay_time_r)

        if feedback is not None:
            self.engine.set_delay_feedback(float(feedback))

        # wet_dry 映射到 delay_wet
        if wet_dry is not None:
            self.engine.set_delay_wet(float(wet_dry))

    def set_grain_params(self, size=None, density=None, position=None,
                        chaos_enabled=None, wet_dry=None):
        """設定 Grain 參數 (Alien4 無 Grain, 映射到其他參數)"""
        # Alien4 沒有 Grain, 可以忽略或映射到其他參數
        pass

    def set_reverb_params(self, room_size=None, damping=None, decay=None,
                         chaos_enabled=None, wet_dry=None):
        """設定 Reverb 參數"""
        if not ALIEN4_AVAILABLE or self.engine is None:
            return

        if room_size is not None:
            self.engine.set_reverb_room(float(room_size))

        if damping is not None:
            self.engine.set_reverb_damping(float(damping))

        if decay is not None:
            self.engine.set_reverb_decay(float(decay))

        # wet_dry 映射到 reverb_wet
        if wet_dry is not None:
            self.engine.set_reverb_wet(float(wet_dry))

    def set_chaos_params(self, rate=None, amount=None, shape=None):
        """設定 Chaos 參數 (Alien4 無 Chaos, 可忽略)"""
        # Alien4 沒有 Chaos, 可以忽略
        pass

    def set_documenta_params(self, mix=None, feedback=None, speed=None,
                            eq_low=None, eq_mid=None, eq_high=None, poly=None):
        """設定 Documenta 參數 (新增)"""
        if not ALIEN4_AVAILABLE or self.engine is None:
            return

        if mix is not None:
            self.engine.set_mix(float(mix))

        if feedback is not None:
            self.engine.set_feedback(float(feedback))

        if speed is not None:
            self.engine.set_speed(float(speed))

        if eq_low is not None:
            self.engine.set_eq_low(float(eq_low))

        if eq_mid is not None:
            self.engine.set_eq_mid(float(eq_mid))

        if eq_high is not None:
            self.engine.set_eq_high(float(eq_high))

        if poly is not None:
            self.engine.set_poly(int(poly))

    def set_recording(self, enabled):
        """設定錄音"""
        if not ALIEN4_AVAILABLE or self.engine is None:
            return
        self.recording = enabled
        self.engine.set_recording(bool(enabled))

    def set_looping(self, enabled):
        """設定循環播放"""
        if not ALIEN4_AVAILABLE or self.engine is None:
            return
        self.looping = enabled
        self.engine.set_looping(bool(enabled))

    def get_status(self):
        """取得當前狀態 (debug 用)"""
        if not ALIEN4_AVAILABLE or self.engine is None:
            return {"available": False}
        return {
            "available": True,
            "num_slices": self.engine.get_num_slices(),
            "num_voices": self.engine.get_num_voices(),
            "recorded_length": self.engine.get_recorded_length(),
        }

    def set_scan(self, value):
        """設定 Slice Scan (0.0-1.0)"""
        if not ALIEN4_AVAILABLE or self.engine is None:
            return
        self.engine.set_scan(float(value))

    def set_gate_threshold(self, value):
        """設定 Gate Threshold (0.0-1.0, lower=more sensitive)"""
        if not ALIEN4_AVAILABLE or self.engine is None:
            return
        self.engine.set_gate_threshold(float(value))

    def set_poly(self, voices):
        """設定 Polyphonic Voices (1-8)"""
        if not ALIEN4_AVAILABLE or self.engine is None:
            return
        self.engine.set_poly(int(voices))

    def process(self, left_in, right_in):
        """
        處理音訊
        Returns: (left_out, right_out, chaos_cv_dummy)
        """
        if not ALIEN4_AVAILABLE or self.engine is None:
            # Fallback: passthrough
            return left_in, right_in, np.zeros_like(left_in)

        # 確保輸入是 float32
        left_in = left_in.astype(np.float32)
        right_in = right_in.astype(np.float32)

        # 處理
        left_out, right_out = self.engine.process(left_in, right_in)

        # 返回相容格式 (加入 dummy chaos_cv)
        chaos_cv = np.zeros_like(left_out)
        return left_out, right_out, chaos_cv

    def clear(self):
        """清除 buffer"""
        if not ALIEN4_AVAILABLE or self.engine is None:
            return
        self.engine.clear()
