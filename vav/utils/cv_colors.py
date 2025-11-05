"""
CV Color Configuration - Unified color scheme for all CV channels
Ensures consistent colors across main visual, CV meters, and GUI displays.
"""

# BGR format for OpenCV (used in ContourCV main visual)
CV_COLORS_BGR = {
    'ENV1': (133, 133, 255),  # Light blue-purple
    'ENV2': (255, 255, 255),  # White
    'ENV3': (45, 0, 188),     # Japanese flag red
    'SEQ1': (133, 133, 255),  # Light blue-purple (same as ENV1)
    'SEQ2': (255, 255, 255),  # White (same as ENV2)
}

# RGB format for PyQt/pyqtgraph (used in CV meters and GUI)
CV_COLORS_RGB = {
    'ENV1': (255, 133, 133),  # Light purple-blue (reversed from BGR)
    'ENV2': (255, 255, 255),  # White
    'ENV3': (188, 0, 45),     # Japanese flag red (reversed from BGR)
    'SEQ1': (255, 133, 133),  # Light purple-blue (same as ENV1)
    'SEQ2': (255, 255, 255),  # White (same as ENV2)
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
