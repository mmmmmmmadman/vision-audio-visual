"""
Audio I/O management using sounddevice
"""

import sounddevice as sd
import numpy as np
from typing import Optional, Callable, List, Tuple


class AudioIO:
    """Audio interface manager"""

    def __init__(
        self,
        sample_rate: int = 48000,
        buffer_size: int = 256,
        input_channels: int = 8,
        output_channels: int = 2,
    ):
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.input_channels = input_channels
        self.output_channels = output_channels

        self.input_device: Optional[int] = None
        self.output_device: Optional[int] = None
        self.stream: Optional[sd.Stream] = None
        self.callback: Optional[Callable] = None

    def list_devices(self) -> List[dict]:
        """List available audio devices"""
        devices = sd.query_devices()
        return [
            {
                "index": i,
                "name": dev["name"],
                "inputs": dev["max_input_channels"],
                "outputs": dev["max_output_channels"],
                "default_sr": dev["default_samplerate"],
            }
            for i, dev in enumerate(devices)
        ]

    def set_devices(self, input_device: int = None, output_device: int = None):
        """Set input/output devices and restart stream if running"""
        devices = sd.query_devices()

        # Check if stream needs to be restarted
        was_active = self.is_active()
        callback_backup = self.callback if was_active else None

        # Stop stream if active (must stop before changing devices)
        if was_active:
            print("  Stopping audio stream to change devices...")
            self.stop()

        # Update input device
        if input_device is not None:
            self.input_device = input_device
            # Adjust input channels to device maximum
            if input_device < len(devices):
                max_in = devices[input_device]['max_input_channels']
                self.input_channels = min(self.input_channels, max_in)
                print(f"Input device {input_device}: {devices[input_device]['name']}")
                print(f"  Channels: {self.input_channels}/{max_in}")

        # Update output device
        if output_device is not None:
            self.output_device = output_device
            # Adjust output channels to device maximum
            if output_device < len(devices):
                max_out = devices[output_device]['max_output_channels']
                # Prefer 8 channels (stereo + 6 CV for ES-8), fall back to stereo if not supported
                if max_out >= 8:
                    self.output_channels = 8
                else:
                    self.output_channels = min(2, max_out)
                print(f"Output device {output_device}: {devices[output_device]['name']}")
                print(f"  Channels: {self.output_channels}/{max_out}")
                if self.output_channels < 8:
                    print(f"  Warning: Device only supports {max_out} channels, CV output disabled")

        # Restart stream if it was active
        if was_active and callback_backup:
            print("  Restarting audio stream with new devices...")
            try:
                self.start(callback_backup)
                print("  Audio stream restarted successfully")
            except Exception as e:
                print(f"  Error restarting audio stream: {e}")
                # Re-raise to let caller handle
                raise

    def start(self, callback: Callable):
        """Start audio stream"""
        self.callback = callback

        def audio_callback(indata, outdata, frames, time, status):
            if status:
                print(f"Audio status: {status}")

            # Call user callback
            output = self.callback(indata, frames)

            # Copy to output
            if output is not None:
                outdata[:] = output
            else:
                outdata.fill(0)

        # Debug: verify device capabilities before opening stream
        try:
            devices = sd.query_devices()
            if self.input_device is not None and self.input_device < len(devices):
                in_dev = devices[self.input_device]
                print(f"[AudioIO Debug] Input device {self.input_device}: {in_dev['name']}")
                print(f"  max_input_channels: {in_dev['max_input_channels']}, requesting: {self.input_channels}")
            if self.output_device is not None and self.output_device < len(devices):
                out_dev = devices[self.output_device]
                print(f"[AudioIO Debug] Output device {self.output_device}: {out_dev['name']}")
                print(f"  max_output_channels: {out_dev['max_output_channels']}, requesting: {self.output_channels}")
        except Exception as e:
            print(f"[AudioIO Debug] Failed to query devices: {e}")

        self.stream = sd.Stream(
            samplerate=self.sample_rate,
            blocksize=self.buffer_size,
            device=(self.input_device, self.output_device),
            channels=(self.input_channels, self.output_channels),
            dtype=np.float32,
            callback=audio_callback,
        )

        self.stream.start()

    def stop(self):
        """Stop audio stream"""
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    def is_active(self) -> bool:
        """Check if stream is active"""
        return self.stream is not None and self.stream.active

    def get_input_latency(self) -> float:
        """Get input latency in ms"""
        if self.stream:
            return self.stream.latency[0] * 1000
        return 0.0

    def get_output_latency(self) -> float:
        """Get output latency in ms"""
        if self.stream:
            return self.stream.latency[1] * 1000
        return 0.0
