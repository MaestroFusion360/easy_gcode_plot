"""Qt application bootstrap and run entry point."""

import logging
import sys
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from app import i18n, theme
from app.integration.minicad_bundle import apply_bundle
from app.integration.simulation_session import SimulationSession, forward_simulation
from app.main_window import MainWindow
from app.native import require_packaged_native
from app.settings import ui_language, ui_theme
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
    if window._document_reload_busy():
        QTimer.singleShot(100, lambda: _start_cli_simulation(window, file, language, bundle))
        return
    existing = window._document_index_for_path(str(file))
    if existing is not None and existing != window._active_document_index:
        if not window._activate_document(existing):
            return
    if existing is not None and window.ui.editor.isModified() and not window.maybeSave():
        return
    if window.loadFile(str(file), reload=existing is not None) is not True:
        return
    window.autoUpdateTimer.stop()
    if bundle is not None:
        apply_bundle(window, bundle, import_reference=True)
    turning = language == "fanuc_turn"
    if window.latheMode != turning:
        window.ui.actionLatheMode.setChecked(turning)
    window.ensure_simulation_ready(turning)
    if window.isMinimized():
        window.showNormal()
    window.raise_()
    window.activateWindow()


def run(*, startup_file: Path | None = None, simulate: bool = False, language: str | None = None, bundle=None) -> int:
    """Create the Qt application, optionally opening an NC file for simulation."""
    require_packaged_native()
    app = QApplication([sys.argv[0]] if simulate else sys.argv)
    if simulate and startup_file is not None and forward_simulation(startup_file, language, bundle):
        return 0
    theme.apply_application_theme(app, ui_theme())
    i18n.install_translator(app, ui_language())
    _decimal_separator_filter = install_decimal_separator_filter(app)
    window = MainWindow()
    LOGGER.info("application_started")
    window.show()
    session = SimulationSession(lambda file, language, bundle: _start_cli_simulation(window, file, language, bundle))
    session.listen()
    window._simulation_session = session
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
