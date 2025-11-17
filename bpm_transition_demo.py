#!/usr/bin/env python3
"""
BPM Transition Demonstration
Visual demonstration of how BPM transitions work
"""

import time


def print_timeline(current_time, pattern_progress, bpm, pending_bpm, event=""):
    """Print a visual timeline of the BPM transition"""
    bar_length = 40
    filled = int(pattern_progress * bar_length)
    bar = "█" * filled + "░" * (bar_length - filled)

    bpm_display = f"{bpm} BPM"
    if pending_bpm:
        bpm_display += f" → {pending_bpm} BPM"

    print(f"[{current_time:4.1f}s] |{bar}| {bpm_display:20s} {event}")


def simulate_bpm_transition():
    """Simulate BPM transition in slow motion"""
    print("\n" + "=" * 70)
    print("BPM Transition Simulation: 140 BPM → 180 BPM")
    print("=" * 70)
    print("\nLegend:")
    print("  █ = Pattern playback progress")
    print("  → = Pending BPM change")
    print("\n")

    # Simulation parameters
    current_bpm = 140
    pending_bpm = None
    pattern_duration = 60.0 / 140 * 4  # 4 beats at 140 BPM ≈ 1.71s
    chunk_duration = 0.1  # 100ms chunks
    total_time = 4.0

    current_time = 0.0
    pattern_start_time = 0.0
    pattern_number = 1

    print(f"Starting playback at {current_bpm} BPM")
    print(f"Pattern duration: {pattern_duration:.2f}s (4 beats)\n")

    while current_time < total_time:
        # Calculate pattern progress
        time_in_pattern = current_time - pattern_start_time
        pattern_progress = min(time_in_pattern / pattern_duration, 1.0)

        event = ""

        # At 0.5s, user requests BPM change
        if abs(current_time - 0.5) < chunk_duration / 2 and pending_bpm is None:
            pending_bpm = 180
            event = "⚡ set_bpm(180) called - SCHEDULED"

        # Check if pattern ended
        if time_in_pattern >= pattern_duration:
            # Apply pending BPM if any
            if pending_bpm is not None:
                current_bpm = pending_bpm
                pattern_duration = 60.0 / current_bpm * 4  # New pattern duration
                event = f"🔄 Pattern boundary - BPM APPLIED to {current_bpm}"
                pending_bpm = None
            else:
                event = "🔁 Pattern boundary - new pattern started"

            pattern_start_time = current_time
            pattern_number += 1
            pattern_progress = 0.0

        # Print timeline
        print_timeline(current_time, pattern_progress, current_bpm, pending_bpm, event)

        # Advance time
        time.sleep(0.05)  # Visual delay for demonstration
        current_time += chunk_duration

    print("\n" + "=" * 70)
    print("Simulation complete")
    print("=" * 70)
    print("\nKey Observations:")
    print("1. BPM change is scheduled immediately when set_bpm() is called")
    print("2. Current pattern continues playing with old BPM")
    print("3. BPM change is applied at the pattern boundary")
    print("4. New pattern starts with new BPM immediately")
    print("5. No audio interruption or glitch occurs")


def compare_approaches():
    """Compare immediate vs scheduled BPM change"""
    print("\n" + "=" * 70)
    print("Comparison: Immediate vs Scheduled BPM Change")
    print("=" * 70)

    print("\n❌ IMMEDIATE CHANGE (Original Implementation):")
    print("   [0.0s] Playing pattern A at 140 BPM (samples_per_step = 4725)")
    print("   [0.5s] set_bpm(180) called")
    print("   [0.5s] ⚠ samples_per_step changed to 3675 IMMEDIATELY")
    print("   [0.5s] ⚠ pattern_length changed to 58800 IMMEDIATELY")
    print("   [0.6s] ❌ get_audio_chunk() reads past pattern end")
    print("   [0.6s] ❌ IndexError or audio glitch")
    print("   [0.6s] ❌ Audio interruption")

    print("\n✅ SCHEDULED CHANGE (New Implementation):")
    print("   [0.0s] Playing pattern A at 140 BPM (samples_per_step = 4725)")
    print("   [0.5s] set_bpm(180) called")
    print("   [0.5s] ✓ pending_bpm set to 180")
    print("   [0.5s] ✓ samples_per_step STAYS at 4725")
    print("   [0.6s] ✓ Pattern A continues normally")
    print("   [1.0s] ✓ Pattern A completes")
    print("   [1.0s] ✓ _apply_pending_bpm() called")
    print("   [1.0s] ✓ samples_per_step updated to 3675")
    print("   [1.0s] ✓ Pattern B generated with new timing")
    print("   [1.0s] ✓ Smooth transition - no audio issues")


def show_code_flow():
    """Show the code flow during BPM transition"""
    print("\n" + "=" * 70)
    print("Code Flow During BPM Transition")
    print("=" * 70)

    print("""
STEP 1: User calls set_bpm(180)
────────────────────────────────────────────────────────────────
def set_bpm(self, bpm: int):
    # Calculate new timing
    new_samples_per_step = int((60.0 / bpm / 4) * self.sample_rate)

    # Schedule (not apply immediately)
    self.pending_bpm = bpm
    self.pending_timing = {
        'samples_per_step': new_samples_per_step,
        ...
    }
    # self.bpm and self.samples_per_step UNCHANGED

STEP 2: Audio callback continues
────────────────────────────────────────────────────────────────
def get_audio_chunk(self, num_frames: int):
    # Pattern still playing...
    chunk = self.current_pattern[start:end]
    # Uses OLD samples_per_step (4725)
    # No issues, pattern was generated with matching timing

STEP 3: Pattern ends, new pattern needed
────────────────────────────────────────────────────────────────
def get_audio_chunk(self, num_frames: int):
    if self.pattern_position >= len(self.current_pattern):

        # Apply pending BPM at pattern boundary
        if self.pending_bpm is not None:
            self._apply_pending_bpm()  # ← BPM APPLIED HERE

        # Generate new pattern with NEW timing
        self.current_pattern = self.generate_pattern(...)
        # Uses NEW samples_per_step (3675)

STEP 4: Continue playback with new BPM
────────────────────────────────────────────────────────────────
def get_audio_chunk(self, num_frames: int):
    # New pattern plays with new BPM
    chunk = self.current_pattern[start:end]
    # Perfect timing match, no issues
""")


def main():
    """Run all demonstrations"""
    print("\n")
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║         BPM Smooth Transition - Visual Demonstration            ║")
    print("╚══════════════════════════════════════════════════════════════════╝")

    show_code_flow()

    print("\n" + "="*70)
    print("Running live simulation...")
    print("="*70)

    simulate_bpm_transition()

    compare_approaches()

    print("\n" + "="*70)
    print("Summary")
    print("="*70)
    print("""
The solution uses a SCHEDULED TRANSITION approach:

1. set_bpm() SCHEDULES the change (doesn't apply immediately)
2. Current pattern continues playing with old timing
3. At pattern boundary, pending BPM is APPLIED
4. New pattern is generated with new timing
5. Smooth, glitch-free transition

Benefits:
✓ No audio interruption
✓ No glitches or clicks
✓ Timing always matches pattern
✓ Musical transition (at bar boundary)
✓ Simple implementation
✓ Predictable behavior

Maximum delay: One pattern duration (~1-2 seconds)
This is acceptable and musically natural.
""")


if __name__ == '__main__':
    main()
