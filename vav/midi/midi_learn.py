"""
MIDI Learn system for VAV
Handles MIDI CC mapping and learning
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, Callable, Optional
import threading

try:
    import mido
    MIDI_AVAILABLE = True
except ImportError:
    MIDI_AVAILABLE = False
    print("⚠ mido not available, MIDI Learn disabled")


class MIDILearnManager:
    """Manages MIDI CC learning and mapping"""

    def __init__(self, config_path: str = None):
        """Initialize MIDI Learn manager

        Args:
            config_path: Path to JSON config file for storing mappings
        """
        self.midi_available = MIDI_AVAILABLE

        # Config file path
        if config_path is None:
            config_dir = Path.home() / ".vav"
            config_dir.mkdir(exist_ok=True)
            config_path = str(config_dir / "midi_mappings.json")
        self.config_path = config_path

        # MIDI CC mappings: {(channel, cc): parameter_id}
        self.mappings: Dict[tuple, str] = {}

        # MIDI Note mappings: {(channel, note): parameter_id}
        self.note_mappings: Dict[tuple, str] = {}

        # Parameter callbacks: {parameter_id: callback_function}
        self.callbacks: Dict[str, Callable] = {}

        # Parameter ranges: {parameter_id: (min, max)}
        self.ranges: Dict[str, tuple] = {}

        # Button toggle states: {parameter_id: bool}
        self.button_states: Dict[str, bool] = {}

        # Last note trigger time to prevent double-triggering: {(channel, note): timestamp}
        self.last_note_time: Dict[tuple, float] = {}

        # Last CC trigger time for buttons: {param_id: timestamp}
        self.last_button_cc_time: Dict[str, float] = {}

        # Learn mode state
        self.learn_mode = False
        self.learn_parameter = None

        # MIDI input
        self.midi_in = None
        self.midi_thread = None
        self.running = False

        # Load existing mappings
        self.load_mappings()

        # Start MIDI if available
        if self.midi_available:
            self._start_midi()

    def load_mappings(self):
        """Load MIDI mappings from JSON file"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                    # Load CC mappings
                    self.mappings = {
                        tuple(map(int, k.split(','))): v
                        for k, v in data.get('cc_mappings', data).items()
                    }
                    # Load Note mappings
                    self.note_mappings = {
                        tuple(map(int, k.split(','))): v
                        for k, v in data.get('note_mappings', {}).items()
                    }
                print(f"✓ Loaded {len(self.mappings)} CC mappings, {len(self.note_mappings)} Note mappings")
            except Exception as e:
                print(f"⚠ Failed to load MIDI mappings: {e}")
                self.mappings = {}
                self.note_mappings = {}
        else:
            self.mappings = {}
            self.note_mappings = {}

    def save_mappings(self):
        """Save MIDI mappings to JSON file"""
        try:
            # Convert tuple keys to strings for JSON
            data = {
                'cc_mappings': {f"{k[0]},{k[1]}": v for k, v in self.mappings.items()},
                'note_mappings': {f"{k[0]},{k[1]}": v for k, v in self.note_mappings.items()}
            }
            with open(self.config_path, 'w') as f:
                json.dump(data, f, indent=2)
            print(f"✓ Saved {len(self.mappings)} CC mappings, {len(self.note_mappings)} Note mappings")
        except Exception as e:
            print(f"⚠ Failed to save MIDI mappings: {e}")

    def register_parameter(self, param_id: str, callback: Callable,
                          min_val: float = 0.0, max_val: float = 1.0):
        """Register a parameter for MIDI control

        Args:
            param_id: Unique parameter identifier
            callback: Function to call when parameter changes (receives normalized 0-1 value)
            min_val: Minimum parameter value
            max_val: Maximum parameter value
        """
        self.callbacks[param_id] = callback
        self.ranges[param_id] = (min_val, max_val)

    def register_button(self, param_id: str, callback: Callable):
        """Register a button for MIDI CC/Note toggle control

        Args:
            param_id: Unique parameter identifier
            callback: Function to call when button toggles (receives bool)
        """
        # Wrap callback to convert CC value (0-127) or bool to bool
        def button_wrapper(value):
            if isinstance(value, bool):
                callback(value)
            else:
                # CC value: debounce to prevent rapid toggles from MIDI button
                current_time = time.time()
                if param_id in self.last_button_cc_time:
                    if current_time - self.last_button_cc_time[param_id] < 0.2:
                        return
                self.last_button_cc_time[param_id] = current_time

                # Toggle on any CC message (regardless of value)
                self.button_states[param_id] = not self.button_states.get(param_id, False)
                callback(self.button_states[param_id])

        self.callbacks[param_id] = button_wrapper
        self.button_states[param_id] = False

    def enter_learn_mode(self, param_id: str):
        """Enter MIDI learn mode for a parameter

        Args:
            param_id: Parameter to learn
        """
        if not self.midi_available:
            print("⚠ MIDI not available")
            return False

        self.learn_mode = True
        self.learn_parameter = param_id
        print(f"⏺ MIDI Learn: Waiting for CC message for '{param_id}'...")
        return True

    def exit_learn_mode(self):
        """Exit MIDI learn mode"""
        self.learn_mode = False
        self.learn_parameter = None
        print("✓ MIDI Learn mode exited")

    def clear_mapping(self, param_id: str):
        """Clear MIDI mapping for a parameter

        Args:
            param_id: Parameter to clear mapping for
        """
        # Find and remove CC mapping
        keys_to_remove = [k for k, v in self.mappings.items() if v == param_id]
        for key in keys_to_remove:
            del self.mappings[key]
            print(f"✓ Cleared MIDI CC mapping for '{param_id}'")

        # Find and remove Note mapping
        note_keys_to_remove = [k for k, v in self.note_mappings.items() if v == param_id]
        for key in note_keys_to_remove:
            del self.note_mappings[key]
            print(f"✓ Cleared MIDI Note mapping for '{param_id}'")

        self.save_mappings()

    def clear_all_mappings(self):
        """Clear all MIDI mappings"""
        self.mappings.clear()
        self.note_mappings.clear()
        self.save_mappings()
        print("✓ Cleared all MIDI mappings")

    def _start_midi(self):
        """Start MIDI input thread"""
        try:
            # Get available MIDI input ports
            ports = mido.get_input_names()
            if not ports:
                print("⚠ No MIDI input ports available")
                self.midi_available = False
                return

            # Use first available port
            port_name = ports[0]
            self.midi_in = mido.open_input(port_name)
            print(f"✓ MIDI input opened: {port_name}")

            # Start MIDI listening thread only if midi_in was successfully opened
            if self.midi_in:
                self.running = True
                self.midi_thread = threading.Thread(target=self._midi_loop, daemon=True)
                self.midi_thread.start()

        except Exception as e:
            print(f"⚠ Failed to start MIDI: {e}")
            self.midi_available = False

    def _midi_loop(self):
        """MIDI message processing loop (runs in separate thread)"""
        while self.running and self.midi_in:
            try:
                # Use iter_pending() which is non-blocking
                for msg in self.midi_in.iter_pending():
                    if msg.type == 'control_change':
                        self._handle_cc(msg.channel, msg.control, msg.value)
                    # Only handle note_on with velocity > 0 (ignore note_off)
                    elif msg.type == 'note_on' and msg.velocity > 0:
                        self._handle_note(msg.channel, msg.note)

                # Sleep to avoid busy-waiting and reduce CPU usage
                time.sleep(0.01)  # 10ms sleep = max 100Hz MIDI polling

            except Exception as e:
                print(f"⚠ MIDI error: {e}")
                break

    def _handle_cc(self, channel: int, cc: int, value: int):
        """Handle MIDI CC message

        Args:
            channel: MIDI channel (0-15)
            cc: CC number (0-127)
            value: CC value (0-127)
        """
        # Learn mode: assign this CC to the parameter
        if self.learn_mode and self.learn_parameter:
            # First, remove any existing mapping for this parameter (one-to-one mapping)
            old_mappings = [k for k, v in self.mappings.items() if v == self.learn_parameter]
            for old_key in old_mappings:
                del self.mappings[old_key]
                print(f"✓ Cleared old mapping: Ch{old_key[0]+1} CC{old_key[1]} → '{self.learn_parameter}'")

            # Now assign the new mapping
            self.mappings[(channel, cc)] = self.learn_parameter
            print(f"✓ Learned: Ch{channel+1} CC{cc} → '{self.learn_parameter}'")
            self.save_mappings()
            self.exit_learn_mode()
            return

        # Normal mode: execute mapped parameter
        key = (channel, cc)
        if key in self.mappings:
            param_id = self.mappings[key]
            if param_id in self.callbacks:
                # Normalize CC value (0-127) to parameter range
                normalized = value / 127.0
                min_val, max_val = self.ranges.get(param_id, (0.0, 1.0))
                actual_value = min_val + (normalized * (max_val - min_val))

                # Call parameter callback
                try:
                    self.callbacks[param_id](actual_value)
                except Exception as e:
                    print(f"⚠ Error calling callback for '{param_id}': {e}")

    def _handle_note(self, channel: int, note: int):
        """Handle MIDI Note On message for button toggle

        Args:
            channel: MIDI channel (0-15)
            note: Note number (0-127)
        """
        # Learn mode: assign this note to the parameter
        if self.learn_mode and self.learn_parameter:
            # First, remove any existing note mapping for this parameter
            old_mappings = [k for k, v in self.note_mappings.items() if v == self.learn_parameter]
            for old_key in old_mappings:
                del self.note_mappings[old_key]
                print(f"✓ Cleared old note mapping: Ch{old_key[0]+1} Note{old_key[1]} → '{self.learn_parameter}'")

            # Now assign the new mapping
            self.note_mappings[(channel, note)] = self.learn_parameter
            print(f"✓ Learned Note: Ch{channel+1} Note{note} → '{self.learn_parameter}'")
            self.save_mappings()
            self.exit_learn_mode()
            return

        # Normal mode: toggle button state
        key = (channel, note)
        if key in self.note_mappings:
            param_id = self.note_mappings[key]
            if param_id in self.callbacks:
                # Toggle button state (no debounce - MIDI controller handles toggle)
                self.button_states[param_id] = not self.button_states.get(param_id, False)

                # Call button callback with toggle state
                try:
                    self.callbacks[param_id](self.button_states[param_id])
                except Exception as e:
                    print(f"⚠ Error calling button callback for '{param_id}': {e}")

    def shutdown(self):
        """Shutdown MIDI system"""
        self.running = False
        if self.midi_in:
            self.midi_in.close()
            print("✓ MIDI input closed")
        if self.midi_thread:
            self.midi_thread.join(timeout=1.0)
