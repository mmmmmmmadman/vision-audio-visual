"""
Cable detection using MediaPipe and OpenCV
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class Cable:
    """Detected cable information"""
    start: Tuple[int, int]
    end: Tuple[int, int]
    length: float
    angle: float
    position: float  # Normalized position 0-1


class CableDetector:
    """Detect and track patch cables in webcam feed"""

    def __init__(
        self,
        min_length: int = 50,
        max_cables: int = 32,
        confidence_threshold: float = 0.7,
    ):
        self.min_length = min_length
        self.max_cables = max_cables
        self.confidence_threshold = confidence_threshold
        self.cables: List[Cable] = []

    def detect(self, frame: np.ndarray) -> List[Cable]:
        """Detect cables in frame using line detection"""
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Apply Gaussian blur
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Edge detection
        edges = cv2.Canny(blurred, 50, 150, apertureSize=3)

        # Hough Line Transform
        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=50,
            minLineLength=self.min_length,
            maxLineGap=10,
        )

        cables = []
        if lines is not None:
            for line in lines[: self.max_cables]:
                x1, y1, x2, y2 = line[0]

                # Calculate cable properties
                length = np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
                angle = np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi

                # Normalized position (0-1) based on x coordinate
                position = (x1 + x2) / (2 * frame.shape[1])

                cable = Cable(
                    start=(x1, y1),
                    end=(x2, y2),
                    length=length,
                    angle=angle,
                    position=position,
                )
                cables.append(cable)

        # Sort by position for consistent sequence
        cables.sort(key=lambda c: c.position)
        self.cables = cables
        return cables

    def draw_cables(self, frame: np.ndarray, cables: List[Cable]) -> np.ndarray:
        """Draw detected cables on frame"""
        output = frame.copy()
        for i, cable in enumerate(cables):
            # Color based on position
            hue = int(cable.position * 179)
            color = cv2.cvtColor(
                np.uint8([[[hue, 255, 255]]]), cv2.COLOR_HSV2BGR
            )[0][0]
            color = tuple(map(int, color))

            cv2.line(output, cable.start, cable.end, color, 3)

            # Draw cable number
            mid_x = (cable.start[0] + cable.end[0]) // 2
            mid_y = (cable.start[1] + cable.end[1]) // 2
            cv2.putText(
                output,
                str(i + 1),
                (mid_x, mid_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                2,
            )

        return output

    def get_cable_count(self) -> int:
        """Get current number of detected cables"""
        return len(self.cables)

    def get_cable_stats(self) -> dict:
        """Get statistical info about detected cables"""
        if not self.cables:
            return {
                "count": 0,
                "avg_length": 0,
                "max_length": 0,
                "min_length": 0,
            }

        lengths = [c.length for c in self.cables]
        return {
            "count": len(self.cables),
            "avg_length": np.mean(lengths),
            "max_length": np.max(lengths),
            "min_length": np.min(lengths),
        }
