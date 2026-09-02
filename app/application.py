"""Qt application bootstrap and run entry point."""

import sys

from PyQt6.QtWidgets import QApplication

from app.main_window import MainWindow


def run() -> int:
    """Create the Qt application, show the main window, and run the event loop."""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()
