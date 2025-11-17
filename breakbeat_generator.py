#!/usr/bin/env python3
"""
Break Beat Generator
Generates continuous break beat rhythms using drum samples
"""

import os
import numpy as np
import soundfile as sf
import random
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple
import sounddevice as sd
import threading


@dataclass
class DrumSample:
    """Drum sample data"""
    name: str
    audio: np.ndarray
    sample_rate: int
    category: str  # kick, snare, hihat, crash, etc.


class BreakBeatGenerator:
    """Generate break beat rhythms from drum samples"""

    def __init__(self, sample_dir: str, bpm: int = 140, sample_rate: int = 44100):
        """
        Initialize break beat generator

        Args:
            sample_dir: Directory containing drum samples
            bpm: Beats per minute
            sample_rate: Audio sample rate
        """
        self.sample_dir = sample_dir
        self.bpm = bpm
        self.sample_rate = sample_rate
        self.samples: Dict[str, List[DrumSample]] = {}
        self.playing = False
        self.play_thread = None

        # Calculate timing
        self.beat_duration = 60.0 / bpm  # seconds per beat
        self.step_duration = self.beat_duration / 4  # 16th note duration
        self.samples_per_step = int(self.step_duration * sample_rate)

        self._load_samples()

    def _load_samples(self):
        """Load all drum samples from directory"""
        print(f"Loading drum samples from {self.sample_dir}...")

        # Category mapping based on filename patterns
        category_map = {
            'kick': ['1_Kick', '0_Trummer'],
            'snare': ['2_SN'],
            'roll': ['3_Roll'],
            'hihat': ['6_HH'],
            'ride': ['4_Ride'],
            'crash': ['5_Crash'],
            'tom': ['6_TM']
        }

        for filename in os.listdir(self.sample_dir):
            if not filename.endswith('.wav'):
                continue

            filepath = os.path.join(self.sample_dir, filename)

            try:
                audio, sr = sf.read(filepath)

                # Convert to mono if stereo
                if len(audio.shape) > 1:
                    audio = np.mean(audio, axis=1)

                # Resample if needed
                if sr != self.sample_rate:
                    from scipy.signal import resample
                    audio = resample(audio, int(len(audio) * self.sample_rate / sr))

                # Determine category
                category = 'other'
                for cat, patterns in category_map.items():
                    if any(pattern in filename for pattern in patterns):
                        category = cat
                        break

                sample = DrumSample(
                    name=filename.replace('.wav', ''),
                    audio=audio,
                    sample_rate=self.sample_rate,
                    category=category
                )

                if category not in self.samples:
                    self.samples[category] = []
                self.samples[category].append(sample)

                print(f"  Loaded: {filename} ({category})")

            except Exception as e:
                print(f"  Error loading {filename}: {e}")

        print(f"\nLoaded {sum(len(v) for v in self.samples.values())} samples")
        print(f"Categories: {list(self.samples.keys())}")

    def _get_random_sample(self, category: str, variation: str = None) -> DrumSample:
        """Get random sample from category"""
        if category not in self.samples:
            return None

        candidates = self.samples[category]

        # Filter by variation if specified (H/L)
        if variation:
            candidates = [s for s in candidates if variation in s.name]
            if not candidates:
                candidates = self.samples[category]

        return random.choice(candidates)

    def create_amen_break_pattern(self) -> np.ndarray:
        """
        Create Amen Break inspired pattern (classic break beat)
        16 steps (4 beats)
        """
        # Create empty pattern (16 steps)
        pattern_length = self.samples_per_step * 16
        pattern = np.zeros(pattern_length, dtype=np.float32)

        # Classic Amen Break structure:
        # Beat 1: Kick + HH
        # Beat 2: Snare + HH
        # Beat 3: Kick + HH (with ghost notes)
        # Beat 4: Snare + Roll + HH

        def add_sample(step: int, sample: DrumSample, gain: float = 1.0):
            if sample is None:
                return
            start = step * self.samples_per_step
            audio = sample.audio * gain
            length = min(len(audio), pattern_length - start)
            pattern[start:start+length] += audio[:length]

        # Beat 1
        add_sample(0, self._get_random_sample('kick'))  # Kick
        add_sample(0, self._get_random_sample('hihat', 'C'), 0.6)  # HH
        add_sample(2, self._get_random_sample('hihat', 'A'), 0.4)  # HH ghost

        # Beat 2
        add_sample(4, self._get_random_sample('snare'))  # Snare
        add_sample(4, self._get_random_sample('hihat', 'C'), 0.6)  # HH
        add_sample(6, self._get_random_sample('hihat', 'A'), 0.3)  # HH ghost

        # Beat 3 (syncopated)
        add_sample(8, self._get_random_sample('kick'), 0.9)  # Kick
        add_sample(8, self._get_random_sample('hihat', 'C'), 0.6)  # HH
        add_sample(10, self._get_random_sample('kick'), 0.7)  # Kick ghost
        add_sample(10, self._get_random_sample('hihat', 'A'), 0.4)  # HH

        # Beat 4 (fill)
        add_sample(12, self._get_random_sample('snare'))  # Snare
        add_sample(13, self._get_random_sample('roll', 'H'), 0.8)  # Roll
        add_sample(14, self._get_random_sample('snare', 'Stick'), 0.7)  # Stick
        add_sample(12, self._get_random_sample('hihat', 'O'), 0.5)  # HH open

        # Random variations every 8 bars
        if random.random() < 0.125:  # 1/8 chance
            # Add crash on downbeat
            add_sample(0, self._get_random_sample('crash'), 0.4)

        # Normalize
        max_val = np.max(np.abs(pattern))
        if max_val > 0:
            pattern = pattern / max_val * 0.8

        return pattern

    def create_jungle_pattern(self) -> np.ndarray:
        """
        Create jungle/drum & bass pattern
        Fast, complex, syncopated
        """
        pattern_length = self.samples_per_step * 16
        pattern = np.zeros(pattern_length, dtype=np.float32)

        def add_sample(step: int, sample: DrumSample, gain: float = 1.0):
            if sample is None:
                return
            start = step * self.samples_per_step
            audio = sample.audio * gain
            length = min(len(audio), pattern_length - start)
            pattern[start:start+length] += audio[:length]

        # Kick pattern (varied placement)
        kick_steps = [0, 6, 10, 13]
        for step in kick_steps:
            add_sample(step, self._get_random_sample('kick'), random.uniform(0.8, 1.0))

        # Snare on 2 and 4
        add_sample(4, self._get_random_sample('snare'))
        add_sample(12, self._get_random_sample('snare'))

        # Fast hi-hat pattern
        for step in range(0, 16, 2):
            variation = 'C' if step % 4 == 0 else 'A'
            gain = 0.6 if step % 4 == 0 else 0.3
            add_sample(step, self._get_random_sample('hihat', variation), gain)

        # Random fills
        if random.random() < 0.3:
            add_sample(14, self._get_random_sample('roll'), 0.6)

        # Normalize
        max_val = np.max(np.abs(pattern))
        if max_val > 0:
            pattern = pattern / max_val * 0.8

        return pattern

    def create_boom_bap_pattern(self) -> np.ndarray:
        """
        Create boom bap hip-hop pattern
        Simple, hard-hitting
        """
        pattern_length = self.samples_per_step * 16
        pattern = np.zeros(pattern_length, dtype=np.float32)

        def add_sample(step: int, sample: DrumSample, gain: float = 1.0):
            if sample is None:
                return
            start = step * self.samples_per_step
            audio = sample.audio * gain
            length = min(len(audio), pattern_length - start)
            pattern[start:start+length] += audio[:length]

        # Kick on 1 and 3
        add_sample(0, self._get_random_sample('kick', 'H'))
        add_sample(8, self._get_random_sample('kick', 'H'))

        # Snare on 2 and 4
        add_sample(4, self._get_random_sample('snare', 'H'))
        add_sample(12, self._get_random_sample('snare', 'H'))

        # Hi-hat pattern
        for step in [0, 2, 4, 6, 8, 10, 12, 14]:
            add_sample(step, self._get_random_sample('hihat', 'C'), 0.5)

        # Ghost kicks
        if random.random() < 0.5:
            add_sample(6, self._get_random_sample('kick', 'L'), 0.4)
        if random.random() < 0.5:
            add_sample(14, self._get_random_sample('kick', 'L'), 0.5)

        # Normalize
        max_val = np.max(np.abs(pattern))
        if max_val > 0:
            pattern = pattern / max_val * 0.8

        return pattern

    def play_loop(self, pattern_type: str = 'amen', duration: float = None):
        """
        Play break beat loop continuously

        Args:
            pattern_type: 'amen', 'jungle', or 'boom_bap'
            duration: Play duration in seconds (None = infinite)
        """
        pattern_generators = {
            'amen': self.create_amen_break_pattern,
            'jungle': self.create_jungle_pattern,
            'boom_bap': self.create_boom_bap_pattern
        }

        if pattern_type not in pattern_generators:
            print(f"Unknown pattern type: {pattern_type}")
            return

        generator = pattern_generators[pattern_type]

        print(f"\nPlaying {pattern_type} break beat @ {self.bpm} BPM")
        print("Press Ctrl+C to stop\n")

        self.playing = True
        start_time = time.time()
        bar_count = 0

        try:
            while self.playing:
                # Generate pattern
                pattern = generator()

                # Play pattern
                sd.play(pattern, self.sample_rate)
                sd.wait()

                bar_count += 1

                # Print progress
                elapsed = time.time() - start_time
                print(f"Bar {bar_count} | {elapsed:.1f}s", end='\r')

                # Check duration
                if duration and elapsed >= duration:
                    break

        except KeyboardInterrupt:
            print("\n\nStopped")
        finally:
            self.playing = False
            sd.stop()

    def start_background_loop(self, pattern_type: str = 'amen'):
        """Start playing in background thread"""
        if self.playing:
            print("Already playing")
            return

        self.play_thread = threading.Thread(
            target=self.play_loop,
            args=(pattern_type,),
            daemon=True
        )
        self.play_thread.start()

    def stop(self):
        """Stop background playback"""
        self.playing = False
        sd.stop()


def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description="Break Beat Generator")
    parser.add_argument('--bpm', type=int, default=140, help='Beats per minute')
    parser.add_argument('--pattern', default='amen',
                       choices=['amen', 'jungle', 'boom_bap'],
                       help='Beat pattern type')
    parser.add_argument('--duration', type=float, help='Play duration in seconds')
    parser.add_argument('--sample-dir', default='Audio Sample',
                       help='Directory containing drum samples')

    args = parser.parse_args()

    # Create generator
    generator = BreakBeatGenerator(
        sample_dir=args.sample_dir,
        bpm=args.bpm
    )

    # Play loop
    generator.play_loop(
        pattern_type=args.pattern,
        duration=args.duration
    )


if __name__ == '__main__':
    main()
