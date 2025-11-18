"""
Cable property extraction and analysis
"""

from typing import List
from .cable_detector import Cable


class CableAnalyzer:
    """Analyze cable properties for CV generation"""

    def __init__(self):
        self.last_count = 0
        self.count_changed = False

    def analyze(self, cables: List[Cable]) -> dict:
        """Extract features from detected cables"""
        count = len(cables)

        # Detect count changes (for triggering envelopes)
        self.count_changed = count != self.last_count
        self.last_count = count

        if count == 0:
            return {
                "count": 0,
                "count_changed": self.count_changed,
                "positions": [],
                "lengths": [],
                "angles": [],
                "avg_length": 0,
                "length_variance": 0,
            }

        positions = [c.position for c in cables]
        lengths = [c.length for c in cables]
        angles = [c.angle for c in cables]

        # Calculate statistics
        import numpy as np

        avg_length = np.mean(lengths)
        length_variance = np.var(lengths)

        return {
            "count": count,
            "count_changed": self.count_changed,
            "positions": positions,
            "lengths": lengths,
            "angles": angles,
            "avg_length": avg_length,
            "length_variance": length_variance,
        }

    def get_envelope_triggers(self, cables: List[Cable], num_envelopes: int = 3) -> List[bool]:
        """Generate trigger signals for decay envelopes"""
        triggers = [False] * num_envelopes

        if self.count_changed and len(cables) > 0:
            # Trigger envelopes based on cable count changes
            for i in range(min(num_envelopes, len(cables))):
                triggers[i] = True

        return triggers

    def get_sequence_values(self, cables: List[Cable], num_steps: int = 16, use_lengths: bool = False) -> List[float]:
        """Generate sequence values from cable positions or lengths

        Args:
            cables: List of detected cables
            num_steps: Number of sequence steps
            use_lengths: If True, use cable lengths instead of positions
        """
        if not cables:
            return [0.0] * num_steps

        # Use cable positions or lengths as sequence values
        if use_lengths:
            # Normalize lengths to 0-1 range
            import numpy as np
            lengths = [c.length for c in cables[:num_steps]]
            if lengths:
                max_length = max(lengths)
                min_length = min(lengths)
                if max_length > min_length:
                    # Normalize to 0-1
                    values = [(l - min_length) / (max_length - min_length) for l in lengths]
                else:
                    # All cables same length
                    values = [0.5] * len(lengths)
            else:
                values = []
        else:
            # Use positions (already 0-1 range)
            values = [c.position for c in cables[:num_steps]]

        # Pad if needed
        if len(values) < num_steps:
            if values:
                values.extend([values[-1]] * (num_steps - len(values)))
            else:
                values = [0.0] * num_steps

        return values
