#!/usr/bin/env python3
"""
MIDI Monitor - 監控所有 MIDI 訊號
用來診斷 MIDI controller 的行為
"""

import mido
import time
from datetime import datetime

def main():
    # 列出所有可用的 MIDI 輸入端口
    ports = mido.get_input_names()
    print("=== MIDI Monitor ===")
    print(f"Available MIDI input ports:")
    for i, port in enumerate(ports):
        print(f"  [{i}] {port}")

    if not ports:
        print("No MIDI input ports found!")
        return

    # 使用第一個端口
    port_name = ports[0]
    print(f"\nListening on: {port_name}")
    print("Press Ctrl+C to exit\n")
    print("=" * 60)

    try:
        with mido.open_input(port_name) as inport:
            for msg in inport:
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

                if msg.type == 'control_change':
                    print(f"[{timestamp}] CC  → Ch:{msg.channel+1:2d}  CC#{msg.control:3d}  Value:{msg.value:3d}")
                elif msg.type == 'note_on':
                    print(f"[{timestamp}] NOTE ON  → Ch:{msg.channel+1:2d}  Note:{msg.note:3d}  Velocity:{msg.velocity:3d}")
                elif msg.type == 'note_off':
                    print(f"[{timestamp}] NOTE OFF → Ch:{msg.channel+1:2d}  Note:{msg.note:3d}  Velocity:{msg.velocity:3d}")
                else:
                    print(f"[{timestamp}] {msg.type} → {msg}")

    except KeyboardInterrupt:
        print("\n\nMIDI Monitor stopped")

if __name__ == "__main__":
    main()
