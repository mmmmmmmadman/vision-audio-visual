#!/usr/bin/env python3
"""
VAV - Visual Audio Visual System
Compact GUI entry point
"""

import sys
from PyQt6.QtWidgets import QApplication
from vav.core.controller import VAVController
from vav.gui.compact_main_window import CompactMainWindow
from vav.utils.config import Config


def main():
    """Main application entry point with compact GUI"""
    # Load configuration
    config = Config()
    config.load()

    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("VAV Control")
    app.setOrganizationName("MADZINE")

    # Create controller
    controller = VAVController(config=config.get_all())

    # Initialize system
    if not controller.initialize():
        print("Failed to initialize VAV system")
        sys.exit(1)

    # Create compact main window
    window = CompactMainWindow(controller)
    window.show()

    # Run
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
