"""Qt application bootstrap and run entry point."""

import logging
import sys

from PyQt6.QtWidgets import QApplication

from app.main_window import MainWindow

LOGGER = logging.getLogger(__name__)


def run() -> int:
    """Create the Qt application, show the main window, and run the event loop."""
    app = QApplication(sys.argv)
    window = MainWindow()
    LOGGER.info("application_started")
    window.show()
    return app.exec()
