"""Qt application bootstrap and run entry point."""

import logging
import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.ui.numeric_input import install_decimal_separator_filter

LOGGER = logging.getLogger(__name__)
STARTUP_LATHE_FIT_DELAY_MS = 100


def _fit_visible_lathe_stock(window) -> None:
    """Fit the settled startup viewport to visible turning stock, if any."""
    if not window.latheMode:
        return
    if window.stockOutlineBounds() is None:
        return
    window.fitToView()


def run() -> int:
    """Create the Qt application, show the main window, and run the event loop."""
    app = QApplication(sys.argv)
    _decimal_separator_filter = install_decimal_separator_filter(app)
    window = MainWindow()
    LOGGER.info("application_started")
    window.show()
    if window.latheMode:
        # A zero-timeout fires too early when the saved window state is maximized:
        # the GL viewport can still have its pre-maximize size, so the subsequent
        # resize stretches the already-fitted turning stock.  Fit once the native
        # window/layout has settled, matching a manual Fit Screen press.
        QTimer.singleShot(STARTUP_LATHE_FIT_DELAY_MS, lambda: _fit_visible_lathe_stock(window))
    return app.exec()
