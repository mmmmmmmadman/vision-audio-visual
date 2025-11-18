"""
音訊裝置列舉模組
Audio Device Enumeration Module

用於列舉系統音訊輸出裝置，包括多通道裝置的單獨通道
"""

import subprocess
import re
from typing import List, Dict, Optional


class AudioDeviceManager:
    """音訊裝置管理器"""

    def __init__(self):
        self.devices = []
        self.refresh_devices()

    def refresh_devices(self):
        """重新掃描音訊裝置"""
        self.devices = []
        self._enumerate_coreaudio_devices()

    def _enumerate_coreaudio_devices(self):
        """使用 SoX 列舉 CoreAudio 裝置"""
        try:
            # 使用 SoX 的 play 命令列出裝置
            result = subprocess.run(
                ["play", "-n", "trim", "0", "0"],
                capture_output=True,
                text=True,
                timeout=5
            )

            # 解析輸出
            output = result.stderr  # SoX 將裝置資訊輸出到 stderr

            # 尋找裝置列表部分
            if "coreaudio" in output.lower():
                self._parse_sox_output(output)

        except FileNotFoundError:
            print("警告: SoX 未安裝，使用 Python sounddevice 替代")
            self._enumerate_with_sounddevice()
        except Exception as e:
            print(f"列舉裝置時發生錯誤: {e}")
            self._enumerate_with_sounddevice()

    def _parse_sox_output(self, output: str):
        """解析 SoX 輸出"""
        # 這個方法可能需要根據實際輸出調整
        # 暫時使用 sounddevice 作為主要方法
        self._enumerate_with_sounddevice()

    def _enumerate_with_sounddevice(self):
        """使用 sounddevice 列舉裝置"""
        try:
            import sounddevice as sd

            devices = sd.query_devices()

            for idx, device in enumerate(devices):
                # 只列出輸出裝置
                if device['max_output_channels'] > 0:
                    device_info = {
                        'id': idx,
                        'name': device['name'],
                        'channels': device['max_output_channels'],
                        'sample_rate': device['default_samplerate'],
                        'hostapi': sd.query_hostapis(device['hostapi'])['name']
                    }

                    # 如果是多聲道裝置，為每個通道建立獨立選項
                    if device['max_output_channels'] > 1:
                        # 先加入完整裝置
                        self.devices.append({
                            **device_info,
                            'channel': None,
                            'display_name': f"{device['name']} (Stereo/Multi)",
                            'is_mono': False
                        })

                        # 再加入單聲道選項
                        for ch in range(device['max_output_channels']):
                            self.devices.append({
                                **device_info,
                                'channel': ch,
                                'display_name': f"{device['name']} - Channel {ch + 1}",
                                'is_mono': True
                            })
                    else:
                        # 單聲道裝置
                        self.devices.append({
                            **device_info,
                            'channel': 0,
                            'display_name': f"{device['name']} (Mono)",
                            'is_mono': True
                        })

        except ImportError:
            print("錯誤: 未安裝 sounddevice")
            print("請執行: pip install sounddevice")
        except Exception as e:
            print(f"使用 sounddevice 列舉裝置時發生錯誤: {e}")

    def get_devices(self) -> List[Dict]:
        """
        取得所有可用的音訊裝置

        Returns:
            裝置資訊列表，每個元素包含:
            - id: 裝置 ID
            - name: 裝置名稱
            - channels: 總通道數
            - channel: 指定通道 (None 表示使用所有通道)
            - display_name: 顯示名稱
            - is_mono: 是否為單聲道輸出
        """
        return self.devices

    def get_device_by_name(self, name: str, channel: Optional[int] = None) -> Optional[Dict]:
        """
        根據名稱和通道尋找裝置

        Args:
            name: 裝置名稱 (支援部分匹配)
            channel: 指定通道 (None 表示使用所有通道)

        Returns:
            裝置資訊，如果找不到則返回 None
        """
        for device in self.devices:
            if name.lower() in device['name'].lower():
                if channel is None or device['channel'] == channel:
                    return device
        return None

    def get_es8_output(self, output_num: int = 8) -> Optional[Dict]:
        """
        快速取得 ES-8 的特定輸出

        Args:
            output_num: 輸出編號 (1-8)

        Returns:
            裝置資訊，如果找不到則返回 None
        """
        # ES-8 通常顯示為 "ES-8" 或 "Expert Sleepers ES-8"
        channel = output_num - 1  # 轉換為 0-based index

        for device in self.devices:
            if 'es-8' in device['name'].lower() or 'es8' in device['name'].lower():
                if device['channel'] == channel:
                    return device

        return None

    def print_devices(self):
        """列印所有裝置資訊 (用於除錯)"""
        print("\n=== 可用的音訊輸出裝置 ===\n")

        for i, device in enumerate(self.devices):
            mono_indicator = "[MONO]" if device['is_mono'] else "[MULTI]"
            print(f"{i + 1}. {mono_indicator} {device['display_name']}")
            print(f"   裝置ID: {device['id']}, 通道: {device.get('channel', 'All')}")
            print(f"   總通道數: {device['channels']}, 取樣率: {device['sample_rate']}")
            print()


# 測試程式碼
if __name__ == "__main__":
    print("=== 音訊裝置列舉測試 ===\n")

    manager = AudioDeviceManager()
    manager.print_devices()

    # 測試尋找 ES-8
    print("\n=== 尋找 ES-8 Output 8 ===\n")
    es8_out8 = manager.get_es8_output(8)

    if es8_out8:
        print("✓ 找到 ES-8 Output 8:")
        print(f"  裝置: {es8_out8['display_name']}")
        print(f"  ID: {es8_out8['id']}, 通道: {es8_out8['channel']}")
    else:
        print("✗ 未找到 ES-8")
