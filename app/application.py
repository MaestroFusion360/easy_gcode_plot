"""Qt application bootstrap and run entry point."""

import logging
import sys
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from app import i18n, theme
from app.main_window import MainWindow
from app.native import require_packaged_native
from app.settings import ui_language, ui_theme
from app.tools.definitions import DEFAULT_MILLING_TOOL
from app.ui.support.numeric_input import install_decimal_separator_filter

LOGGER = logging.getLogger(__name__)
STARTUP_LATHE_FIT_DELAY_MS = 100


def _fit_visible_lathe_stock(window) -> None:
    """Fit the settled startup viewport to visible turning stock, if any."""
    if not window.latheMode:
        return
    if window.stockOutlineBounds() is None:
        return
    window.fitToView()


def _start_cli_simulation(window: MainWindow, file: Path, language: str, bundle=None) -> None:
    """Open one program and start the existing Stock Removal playback."""
    if window.loadFile(str(file)) is not True:
        return
    window.autoUpdateTimer.stop()
    if bundle is not None:
        stock = bundle.bounds
        ox, oy, oz = bundle.origin
        window.millingStockManual = True
        for attr, value in zip(
            ("XMinus", "XPlus", "YMinus", "YPlus", "ZMinus", "ZPlus"),
            (stock[0] - ox, stock[1] - ox, stock[2] - oy, stock[3] - oy, stock[4] - oz, stock[5] - oz),
        ):
            setattr(window, "millingStock" + attr, value)
        window.millingTools[bundle.tool_number] = {
            **DEFAULT_MILLING_TOOL,
            "diameter": bundle.tool_diameter,
            "type": bundle.tool_type,
        }
        window.importStl(str(bundle.stl))
    turning = language == "fanuc_turn"
    if window.latheMode != turning:
        window.ui.actionLatheMode.setChecked(turning)
    window.ensure_simulation_ready(turning)


def run(*, startup_file: Path | None = None, simulate: bool = False, language: str | None = None, bundle=None) -> int:
    """Create the Qt application, optionally opening an NC file for simulation."""
    require_packaged_native()
    app = QApplication([sys.argv[0]] if simulate else sys.argv)
    theme.apply_application_theme(app, ui_theme())
    i18n.install_translator(app, ui_language())
    _decimal_separator_filter = install_decimal_separator_filter(app)
    window = MainWindow()
    LOGGER.info("application_started")
    window.show()
    if simulate and startup_file is not None and language is not None:
        QTimer.singleShot(
            STARTUP_LATHE_FIT_DELAY_MS,
            lambda: _start_cli_simulation(window, startup_file, language, bundle),
        )
    if window.latheMode:
        # A zero-timeout fires too early when the saved window state is maximized:
        # the GL viewport can still have its pre-maximize size, so the subsequent
        # resize stretches the already-fitted turning stock.  Fit once the native
        # window/layout has settled, matching a manual Fit Screen press.
        QTimer.singleShot(STARTUP_LATHE_FIT_DELAY_MS, lambda: _fit_visible_lathe_stock(window))
    return app.exec()
