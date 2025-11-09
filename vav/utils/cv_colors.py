"""
CV Color Configuration - Unified color scheme for all CV channels
Ensures consistent colors across main visual, CV meters, and GUI displays.
"""

# BGR format for OpenCV (used in ContourCV main visual)
# Scheme A+: Classic Torii Colors (SEQ Enhanced) - Japanese Shrine Red & White
CV_COLORS_BGR = {
    'ENV1': (100, 120, 227),  # Light Vermillion (淡朱) - softer paired with SEQ1
    'ENV2': (220, 220, 220),  # Silver White (銀白) - softer paired with SEQ2
    'ENV3': (30, 0, 180),     # Deep Crimson (深紅) - stable deep red
    'SEQ1': (0, 69, 255),     # Flame Vermillion (炎朱) - MOST VIVID orange-red
    'SEQ2': (255, 255, 255),  # Snow White (雪白) - PURE white, highest contrast
}

# RGB format for PyQt/pyqtgraph (used in CV meters and GUI)
CV_COLORS_RGB = {
    'ENV1': (227, 120, 100),  # Light Vermillion (淡朱) - softer paired with SEQ1
    'ENV2': (220, 220, 220),  # Silver White (銀白) - softer paired with SEQ2
    'ENV3': (180, 0, 30),     # Deep Crimson (深紅) - stable deep red
    'SEQ1': (255, 69, 0),     # Flame Vermillion (炎朱) - MOST VIVID orange-red
    'SEQ2': (255, 255, 255),  # Snow White (雪白) - PURE white, highest contrast
}

# Helper function to convert BGR to RGB
def bgr_to_rgb(bgr):
    """Convert BGR tuple to RGB tuple"""
    return (bgr[2], bgr[1], bgr[0])

# Helper function to get color by channel name
def get_cv_color(channel_name, format='BGR'):
    """
    Get color for a CV channel

    Args:
        channel_name: Name of the channel ('ENV1', 'ENV2', 'ENV3', 'SEQ1', 'SEQ2')
        format: 'BGR' for OpenCV, 'RGB' for Qt/pyqtgraph

    Returns:
        Tuple of (R, G, B) or (B, G, R) depending on format
    """
    if format.upper() == 'BGR':
        return CV_COLORS_BGR.get(channel_name, (255, 255, 255))
    else:
        return CV_COLORS_RGB.get(channel_name, (255, 255, 255))

# List format for scope widget (ENV1, ENV2, ENV3, SEQ1, SEQ2)
SCOPE_COLORS = [
    CV_COLORS_RGB['ENV1'],
    CV_COLORS_RGB['ENV2'],
    CV_COLORS_RGB['ENV3'],
    CV_COLORS_RGB['SEQ1'],
    CV_COLORS_RGB['SEQ2'],
]
