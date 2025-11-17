#!/usr/bin/env python3
"""
Break Beat Engine for VAV Integration
Real-time break beat generation with audio output callback
"""

import os
import numpy as np
import soundfile as sf
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Callable
from scipy.signal import resample


@dataclass
class DrumSample:
    """Drum sample data"""
    name: str
    audio: np.ndarray
    category: str


class BreakBeatEngine:
    """
    Break beat engine with callback-based audio generation
    Designed for integration with VAV audio pipeline
    """

    def __init__(self, sample_dir: str, bpm: int = 140, sample_rate: int = 44100):
        """
        Initialize break beat engine

        Args:
            sample_dir: Directory containing drum samples
            bpm: Beats per minute
            sample_rate: Audio sample rate
        """
        self.sample_dir = sample_dir
        self.bpm = bpm
        self.sample_rate = sample_rate
        self.samples: Dict[str, List[DrumSample]] = {}

        # Timing
        self.beat_duration = 60.0 / bpm
        self.step_duration = self.beat_duration / 4  # 16th note
        self.samples_per_step = int(self.step_duration * sample_rate)
        self.pattern_length_samples = self.samples_per_step * 16  # 4 beats

        # BPM transition handling
        self.pending_bpm = None  # New BPM waiting to be applied
        self.pending_timing = None  # New timing parameters (samples_per_step, pattern_length)

        # State
        self.current_pattern = None
        self.pattern_position = 0
        self.bar_count = 0
        self.pattern_type = 'amen'
        self.samples_per_beat = self.samples_per_step * 4  # One beat = 4 steps

        # Latin rhythm layer
        self.latin_enabled = False
        self.latin_pattern_type = 'samba'
        self.latin_pattern = None
        self.all_samples = []  # Flat list of all samples for latin rhythm

        # Rest (silence) layer
        self.rest_probability = 0.0  # 0.0 to 1.0
        self.rest_pattern = []  # List of step indices to silence

        # Fill in layer
        self.fill_amount = 0.0  # 0.0 to 1.0 (controls density, complexity, length)
        self.last_fill_bar = -99  # Track when last fill occurred

        # Swing
        self.swing_amount = 0.0  # 0.0 = no swing, 0.33 = triplet feel

        self._load_samples()

    def _load_samples(self):
        """Load all drum samples"""
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

                # Convert to mono
                if len(audio.shape) > 1:
                    audio = np.mean(audio, axis=1)

                # Resample if needed
                if sr != self.sample_rate:
                    audio = resample(audio, int(len(audio) * self.sample_rate / sr))

                # Normalize
                max_val = np.max(np.abs(audio))
                if max_val > 0:
                    audio = audio / max_val

                # Determine category
                category = 'other'
                for cat, patterns in category_map.items():
                    if any(pattern in filename for pattern in patterns):
                        category = cat
                        break

                sample = DrumSample(
                    name=filename.replace('.wav', ''),
                    audio=audio,
                    category=category
                )

                if category not in self.samples:
                    self.samples[category] = []
                self.samples[category].append(sample)

                # Add to flat list for latin rhythm
                self.all_samples.append(sample)

            except Exception as e:
                print(f"Error loading {filename}: {e}")

        print(f"BreakBeat: Loaded {sum(len(v) for v in self.samples.values())} samples")
        print(f"BreakBeat: {len(self.all_samples)} samples available for latin rhythm")

    def _get_sample(self, category: str, variation: str = None) -> Optional[DrumSample]:
        """Get random sample from category"""
        if category not in self.samples:
            return None

        candidates = self.samples[category]

        if variation:
            filtered = [s for s in candidates if variation in s.name]
            if filtered:
                candidates = filtered

        return random.choice(candidates)

    def generate_pattern(self, pattern_type: str = 'amen') -> np.ndarray:
        """
        Generate break beat pattern

        Args:
            pattern_type: 'amen', 'jungle', or 'boom_bap'

        Returns:
            Audio array for one pattern (4 beats, 16 steps)
        """
        pattern = np.zeros(self.pattern_length_samples, dtype=np.float32)

        def add(step: int, sample: DrumSample, gain: float = 1.0):
            if sample is None:
                return

            # Apply swing to off-beat steps (odd-numbered 16th notes)
            start = step * self.samples_per_step
            if step % 2 == 1 and self.swing_amount > 0:
                # Delay off-beat notes by swing amount
                swing_offset = int(self.swing_amount * self.samples_per_step)
                start += swing_offset

            audio = sample.audio * gain
            length = min(len(audio), self.pattern_length_samples - start)
            if start < self.pattern_length_samples:
                pattern[start:start+length] += audio[:length]

        if pattern_type == 'amen':
            # Amen Break
            add(0, self._get_sample('kick'))
            add(0, self._get_sample('hihat', 'C'), 0.6)
            add(2, self._get_sample('hihat', 'A'), 0.4)

            add(4, self._get_sample('snare'))
            add(4, self._get_sample('hihat', 'C'), 0.6)
            add(6, self._get_sample('hihat', 'A'), 0.3)

            add(8, self._get_sample('kick'), 0.9)
            add(8, self._get_sample('hihat', 'C'), 0.6)
            add(10, self._get_sample('kick'), 0.7)
            add(10, self._get_sample('hihat', 'A'), 0.4)

            add(12, self._get_sample('snare'))
            add(13, self._get_sample('roll', 'H'), 0.8)
            add(14, self._get_sample('snare', 'Stick'), 0.7)
            add(12, self._get_sample('hihat', 'O'), 0.5)

            # Occasional crash
            if random.random() < 0.125:
                add(0, self._get_sample('crash'), 0.3)

        elif pattern_type == 'jungle':
            # Jungle/DnB
            for step in [0, 6, 10, 13]:
                add(step, self._get_sample('kick'), random.uniform(0.8, 1.0))

            add(4, self._get_sample('snare'))
            add(12, self._get_sample('snare'))

            for step in range(0, 16, 2):
                var = 'C' if step % 4 == 0 else 'A'
                gain = 0.6 if step % 4 == 0 else 0.3
                add(step, self._get_sample('hihat', var), gain)

            if random.random() < 0.3:
                add(14, self._get_sample('roll'), 0.6)

        elif pattern_type == 'techno':
            # Techno - 4 on the floor with tight hihat
            # Kick on every beat
            for beat in [0, 4, 8, 12]:
                add(beat, self._get_sample('kick', 'H'), 1.0)

            # Snare/clap on 2 and 4
            add(4, self._get_sample('snare'), 0.7)
            add(12, self._get_sample('snare'), 0.7)

            # Tight closed hihat on offbeats
            for step in [2, 6, 10, 14]:
                add(step, self._get_sample('hihat', 'C'), 0.5)

            # 16th note hihat pattern for groove
            for step in [1, 3, 5, 7, 9, 11, 13, 15]:
                if random.random() < 0.6:
                    add(step, self._get_sample('hihat', 'C'), 0.3)

            # Occasional open hihat
            if random.random() < 0.4:
                add(6, self._get_sample('hihat', 'O'), 0.4)

            # Ride for texture
            if random.random() < 0.3:
                for step in [0, 8]:
                    add(step, self._get_sample('ride'), 0.3)

        else:  # boom_bap
            # Boom Bap
            add(0, self._get_sample('kick', 'H'))
            add(8, self._get_sample('kick', 'H'))

            add(4, self._get_sample('snare', 'H'))
            add(12, self._get_sample('snare', 'H'))

            for step in [0, 2, 4, 6, 8, 10, 12, 14]:
                add(step, self._get_sample('hihat', 'C'), 0.5)

            if random.random() < 0.5:
                add(6, self._get_sample('kick', 'L'), 0.4)
            if random.random() < 0.5:
                add(14, self._get_sample('kick', 'L'), 0.5)

        # Apply fill in (before rest)
        if self.fill_amount > 0 and self._should_add_fill():
            pattern = self._add_fill_to_pattern(pattern)

        # Apply rest pattern (silence specific steps)
        if self.rest_pattern:
            for rest_step in self.rest_pattern:
                start = rest_step * self.samples_per_step
                end = start + self.samples_per_step
                pattern[start:end] = 0.0

        # Normalize
        max_val = np.max(np.abs(pattern))
        if max_val > 0:
            pattern = pattern / max_val * 0.7

        return pattern

    def generate_latin_pattern(self, pattern_type: str = 'samba') -> np.ndarray:
        """
        Generate monophonic latin rhythm pattern
        Uses random samples from all available drums

        Args:
            pattern_type: 'samba', 'bossa', or 'salsa'

        Returns:
            Audio array for one pattern (4 beats, 16 steps)
        """
        pattern = np.zeros(self.pattern_length_samples, dtype=np.float32)

        if not self.all_samples:
            return pattern

        def add_mono(step: int, gain: float = 1.0):
            """Add sample at step (monophonic - clears previous audio)"""
            sample = random.choice(self.all_samples)

            # Apply swing to off-beat steps (odd-numbered 16th notes)
            start = step * self.samples_per_step
            if step % 2 == 1 and self.swing_amount > 0:
                # Delay off-beat notes by swing amount
                swing_offset = int(self.swing_amount * self.samples_per_step)
                start += swing_offset

            audio = sample.audio * gain
            length = min(len(audio), self.pattern_length_samples - start)

            # Clear any overlapping audio (monophonic)
            if start < self.pattern_length_samples:
                end = start + length
                pattern[start:end] = audio[:length]

        if pattern_type == 'samba':
            # Samba: 16th note pattern with syncopation
            # x.x.x.xx.x.x.xx
            steps = [0, 2, 4, 6, 7, 9, 11, 13, 14]
            for step in steps:
                gain = 0.9 if step % 4 == 0 else random.uniform(0.5, 0.7)
                add_mono(step, gain)

        elif pattern_type == 'bossa':
            # Bossa Nova: Softer, syncopated
            # x..x..x.x..x.x..
            steps = [0, 3, 6, 8, 11, 13]
            for step in steps:
                gain = 0.7 if step % 4 == 0 else random.uniform(0.4, 0.6)
                add_mono(step, gain)

        else:  # salsa
            # Salsa: Clave-based rhythm
            # x..x...x..x.x...
            steps = [0, 3, 7, 10, 12]
            for step in steps:
                gain = 0.85 if step in [0, 7] else random.uniform(0.5, 0.7)
                add_mono(step, gain)

        # Apply rest pattern (silence specific steps) - same as main pattern
        if self.rest_pattern:
            for rest_step in self.rest_pattern:
                start = rest_step * self.samples_per_step
                end = start + self.samples_per_step
                pattern[start:end] = 0.0

        # Normalize
        max_val = np.max(np.abs(pattern))
        if max_val > 0:
            pattern = pattern / max_val * 0.5  # Lower volume for layering

        return pattern

    def get_audio_chunk(self, num_frames: int) -> np.ndarray:
        """
        Get audio chunk for real-time playback
        Called by audio callback

        Args:
            num_frames: Number of frames to return

        Returns:
            Audio array
        """
        # Check if we're at a beat boundary (every beat = 4 steps)
        if self.pattern_position % self.samples_per_beat == 0 and self.pattern_position > 0:
            # Apply pending BPM change at beat boundary
            if self.pending_bpm is not None and self.pending_timing is not None:
                self._apply_pending_bpm()
                # Regenerate pattern with new timing
                self.current_pattern = self.generate_pattern(self.pattern_type)
                if self.latin_enabled:
                    self.latin_pattern = self.generate_latin_pattern(self.latin_pattern_type)
                self.pattern_position = 0

        # Generate new pattern if needed (at start or end of pattern)
        if self.current_pattern is None or self.pattern_position >= len(self.current_pattern):
            self.current_pattern = self.generate_pattern(self.pattern_type)
            self.pattern_position = 0
            self.bar_count += 1

        # Generate new latin pattern if needed
        if self.latin_enabled:
            if self.latin_pattern is None or self.pattern_position == 0:
                self.latin_pattern = self.generate_latin_pattern(self.latin_pattern_type)

        # Get chunk from current pattern
        start = self.pattern_position
        end = min(start + num_frames, len(self.current_pattern))
        chunk = self.current_pattern[start:end].copy()

        # Mix latin rhythm if enabled
        if self.latin_enabled and self.latin_pattern is not None:
            latin_chunk = self.latin_pattern[start:end]
            if len(latin_chunk) == len(chunk):
                chunk += latin_chunk

        # Pad if needed
        if len(chunk) < num_frames:
            chunk = np.pad(chunk, (0, num_frames - len(chunk)))

        self.pattern_position = end

        return chunk

    def set_pattern_type(self, pattern_type: str):
        """Change pattern type"""
        if pattern_type in ['amen', 'jungle', 'boom_bap', 'techno']:
            self.pattern_type = pattern_type

    def set_bpm(self, bpm: int):
        """
        Schedule BPM change to be applied at next pattern boundary
        This prevents audio glitches by not changing timing mid-pattern
        """
        if bpm == self.bpm:
            return  # No change needed

        # Calculate new timing parameters
        beat_duration = 60.0 / bpm
        step_duration = beat_duration / 4
        new_samples_per_step = int(step_duration * self.sample_rate)
        new_pattern_length = new_samples_per_step * 16

        # Schedule the change - will be applied at pattern boundary
        self.pending_bpm = bpm
        self.pending_timing = {
            'beat_duration': beat_duration,
            'step_duration': step_duration,
            'samples_per_step': new_samples_per_step,
            'pattern_length_samples': new_pattern_length
        }

    def _apply_pending_bpm(self):
        """
        Apply pending BPM change
        Called at beat boundary to ensure smooth transition
        """
        if self.pending_bpm is None or self.pending_timing is None:
            return

        # Apply new BPM and timing
        self.bpm = self.pending_bpm
        self.beat_duration = self.pending_timing['beat_duration']
        self.step_duration = self.pending_timing['step_duration']
        self.samples_per_step = self.pending_timing['samples_per_step']
        self.pattern_length_samples = self.pending_timing['pattern_length_samples']
        self.samples_per_beat = self.samples_per_step * 4  # Update beat size

        # Clear pending change
        self.pending_bpm = None
        self.pending_timing = None

    def set_latin_enabled(self, enabled: bool):
        """Enable/disable latin rhythm layer"""
        self.latin_enabled = enabled
        if not enabled:
            self.latin_pattern = None

    def set_latin_pattern_type(self, pattern_type: str):
        """Change latin pattern type"""
        if pattern_type in ['samba', 'bossa', 'salsa']:
            self.latin_pattern_type = pattern_type
            self.latin_pattern = None  # Force regeneration

    def _generate_rest_pattern(self):
        """Generate rhythmic rest pattern based on probability"""
        if self.rest_probability <= 0:
            self.rest_pattern = []
            return

        # Calculate number of rests based on probability
        num_rests = int(16 * self.rest_probability)
        if num_rests == 0:
            self.rest_pattern = []
            return

        # Generate rhythmic rest pattern
        # Prefer rests on weaker beats (off-beats)
        weak_beats = [1, 3, 5, 7, 9, 11, 13, 15]  # 16th note off-beats
        strong_beats = [0, 2, 4, 6, 8, 10, 12, 14]  # On-beats

        # Weighted selection - prefer weak beats
        available_steps = weak_beats + strong_beats
        weights = [2.0] * len(weak_beats) + [0.5] * len(strong_beats)

        # Normalize weights
        total_weight = sum(weights)
        weights = [w / total_weight for w in weights]

        # Select rest positions
        import numpy as np
        self.rest_pattern = sorted(
            np.random.choice(
                available_steps,
                size=min(num_rests, len(available_steps)),
                replace=False,
                p=weights
            ).tolist()
        )

    def set_rest_probability(self, probability: float):
        """Set rest probability and regenerate pattern"""
        self.rest_probability = max(0.0, min(1.0, probability))
        self._generate_rest_pattern()

    def _should_add_fill(self) -> bool:
        """Determine if fill should be added (based on density/frequency)"""
        # Density: how often fills appear
        # 0.0-0.3: rarely (every 8+ bars)
        # 0.3-0.7: sometimes (every 4 bars)
        # 0.7-1.0: often (every 2 bars)

        if self.fill_amount < 0.1:
            return False

        # Calculate fill interval based on amount
        if self.fill_amount < 0.3:
            interval = 8
        elif self.fill_amount < 0.7:
            interval = 4
        else:
            interval = 2

        # Check if enough bars have passed
        bars_since_fill = self.bar_count - self.last_fill_bar

        # Add fill at end of interval
        if bars_since_fill >= (interval - 1):
            self.last_fill_bar = self.bar_count
            return True

        return False

    def _add_fill_to_pattern(self, pattern: np.ndarray) -> np.ndarray:
        """
        Add fill to pattern (complexity and length based on fill_amount)
        Replaces last part of pattern with fill
        """
        # Length: how many steps the fill occupies
        # 0.0-0.3: short (2 steps = 1/8 beat)
        # 0.3-0.7: medium (4 steps = 1/4 beat)
        # 0.7-1.0: long (6-8 steps = 1/2 beat or more)

        if self.fill_amount < 0.3:
            fill_steps = 2
        elif self.fill_amount < 0.7:
            fill_steps = 4
        else:
            fill_steps = min(8, int(2 + self.fill_amount * 6))

        # Complexity: how many different drum types and density
        # 0.0-0.3: simple (1-2 drum types, sparse)
        # 0.3-0.7: medium (2-3 drum types, moderate)
        # 0.7-1.0: complex (3-4 drum types, dense + crash)

        if self.fill_amount < 0.3:
            num_drum_types = 1
            density = 0.5  # 50% of steps have hits
        elif self.fill_amount < 0.7:
            num_drum_types = 2
            density = 0.7
        else:
            num_drum_types = 3
            density = 1.0

        # Start fill from end
        fill_start_step = 16 - fill_steps

        # Clear fill region
        fill_start_sample = fill_start_step * self.samples_per_step
        pattern[fill_start_sample:] = 0.0

        # Select drum categories for fill
        fill_categories = []
        if num_drum_types >= 1:
            fill_categories.append('snare')
        if num_drum_types >= 2:
            fill_categories.append('tom')
        if num_drum_types >= 3:
            fill_categories.append('kick')

        # Add fill hits
        for i in range(fill_steps):
            if random.random() < density:
                step = fill_start_step + i
                cat = random.choice(fill_categories)
                sample = self._get_sample(cat)

                if sample:
                    # Apply swing to off-beat steps
                    start = step * self.samples_per_step
                    if step % 2 == 1 and self.swing_amount > 0:
                        swing_offset = int(self.swing_amount * self.samples_per_step)
                        start += swing_offset

                    audio = sample.audio * random.uniform(0.7, 1.0)
                    length = min(len(audio), self.pattern_length_samples - start)
                    if start < self.pattern_length_samples:
                        pattern[start:start+length] += audio[:length]

        # Add crash at end for high complexity
        if self.fill_amount > 0.7 and random.random() < 0.7:
            crash = self._get_sample('crash')
            if crash:
                step = 16 - 1
                # Apply swing to off-beat (step 15 is odd)
                start = step * self.samples_per_step
                if step % 2 == 1 and self.swing_amount > 0:
                    swing_offset = int(self.swing_amount * self.samples_per_step)
                    start += swing_offset

                audio = crash.audio * 0.5
                length = min(len(audio), self.pattern_length_samples - start)
                if start < self.pattern_length_samples:
                    pattern[start:start+length] += audio[:length]

        return pattern

    def set_fill_amount(self, amount: float):
        """Set fill amount (0.0 to 1.0)"""
        self.fill_amount = max(0.0, min(1.0, amount))

    def set_swing_amount(self, amount: float):
        """Set swing amount (0.0 to 0.33)"""
        self.swing_amount = max(0.0, min(0.33, amount))


def main():
    """Test the engine"""
    import sounddevice as sd

    print("Break Beat Engine Test")
    print("=" * 50)

    # Initialize
    engine = BreakBeatEngine(
        sample_dir="Audio Sample",
        bpm=140,
        sample_rate=44100
    )

    print(f"\nPlaying @ {engine.bpm} BPM")
    print("Press Ctrl+C to stop\n")

    # Audio callback
    def callback(outdata, frames, time_info, status):
        chunk = engine.get_audio_chunk(frames)
        outdata[:, 0] = chunk

    # Play
    try:
        with sd.OutputStream(
            channels=1,
            callback=callback,
            samplerate=engine.sample_rate,
            blocksize=1024
        ):
            while True:
                sd.sleep(100)
                print(f"Bar {engine.bar_count}", end='\r')

    except KeyboardInterrupt:
        print("\n\nStopped")


if __name__ == '__main__':
    main()
