"""
Parameter smoother - prevents zipper noise from parameter changes
"""

import numpy as np


class ParamSmoother:
    """
    Exponential parameter smoother
    Smooths parameter changes to prevent audio artifacts (zipper noise)
    """

    def __init__(self, initial_value: float = 0.0, lambda_factor: float = 0.005):
        """
        Args:
            initial_value: Starting value
            lambda_factor: Smoothing coefficient (0.001-0.01)
                          Lower = smoother but slower response
                          Higher = faster response but less smooth
        """
        self.current = initial_value
        self.lambda_factor = lambda_factor

    def process(self, target: float) -> float:
        """
        Process one step of smoothing

        Args:
            target: Target value to smooth towards

        Returns:
            Smoothed value
        """
        # Exponential smoothing: current += (target - current) * lambda
        self.current += (target - self.current) * self.lambda_factor
        return self.current

    def reset(self, value: float):
        """Reset to a specific value immediately"""
        self.current = value

    def set_lambda(self, lambda_factor: float):
        """Update smoothing coefficient"""
        self.lambda_factor = np.clip(lambda_factor, 0.0001, 0.1)
