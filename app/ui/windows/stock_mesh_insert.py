"""Insert a detached, calculated GPU stock mesh into the ordinary STL scene."""

# pylint: disable=protected-access  # Shares the main window's existing stock capture lifecycle.

import logging
from contextlib import contextmanager
from threading import Event

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QMessageBox

from app.gcode.stock.milling_stock_export import milling_stock_mesh_triangles
from app.ui.plot.stl import MAX_STL_TRIANGLES, mesh_from_triangles
from app.ui.windows.execution_worker import run_execution

LOGGER = logging.getLogger(__name__)


@contextmanager
def _capture_guard(window):
    cancel = Event()
    window._stock_export_active = True
    window._stock_export_cancel = cancel
    controls = (
        window.ui.horizontalSlider,
        window.ui.actionStockPlayback,
        window.ui.actionSaveStockStl,
        window.ui.actionInsertStockMesh,
    )
    enabled = [control.isEnabled() for control in controls]
    for control in controls:
        control.setEnabled(False)
    try:
        yield cancel
    finally:
        window._stock_export_active = False
        window._stock_export_cancel = None
        for control, state in zip(controls, enabled):
            control.setEnabled(state)


def _prepare_mesh(snapshot, *, cancelled):
    report = {}
    triangles = milling_stock_mesh_triangles(
        snapshot, cancelled=cancelled, max_triangles=MAX_STL_TRIANGLES, simplify=True, report=report
    )
    return mesh_from_triangles(triangles), report["simplified"]


def _confirm_simplification(window, title, mesh):
    message = QCoreApplication.translate(
        "StockMeshInsert",
        "The stock mesh exceeds the Plot View triangle limit. "
        "Quality has been reduced to {0} triangles for insertion. "
        "Simulation accuracy is unchanged.\n\nInsert the simplified mesh?",
    ).format(mesh.triangle_count)
    return (
        QMessageBox.warning(
            window,
            title,
            message,
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        == QMessageBox.StandardButton.Ok
    )


def insert_stock_mesh(window):
    timeline = getattr(window, "_stock_timeline", None)
    if (
        window.latheMode
        or not getattr(window, "_stock_animation_active", False)
        or timeline is None
        or getattr(window, "_stock_export_active", False)
    ):
        return False
    window._pause_playback()
    count = window.ui.horizontalSlider.value()
    target = window._playback_movements[count - 1].motion_end if count else 0
    if not window._cancel_milling_seek() or timeline.motion_count != target:
        window.ui.statusbar.showMessage(
            QCoreApplication.translate("StockMeshInsert", "Wait for the selected stock frame to finish displaying."),
            5000,
        )
        return False
    title = QCoreApplication.translate("StockMeshInsert", "Insert Mesh into Plot View")
    try:
        with _capture_guard(window) as cancel:
            snapshot = run_execution(
                window,
                window._milling_stock_item.calculated_snapshot,
                timeline,
                {"cancelled": cancel.is_set},
                cancel.set,
                title=title,
                status_text=QCoreApplication.translate("StockMeshInsert", "Reading calculated stock"),
                cancelling_text=QCoreApplication.translate("StockMeshInsert", "Cancelling mesh insertion"),
                show_dialog=True,
            )
            mesh, simplified = run_execution(
                window,
                _prepare_mesh,
                snapshot,
                {"cancelled": cancel.is_set},
                cancel.set,
                title=title,
                status_text=QCoreApplication.translate("StockMeshInsert", "Building stock mesh"),
                cancelling_text=QCoreApplication.translate("StockMeshInsert", "Cancelling mesh insertion"),
                show_dialog=True,
            )
            if cancel.is_set():
                raise InterruptedError(QCoreApplication.translate("StockMeshInsert", "Stock mesh insertion cancelled"))
            if simplified and not _confirm_simplification(window, title, mesh):
                raise InterruptedError(QCoreApplication.translate("StockMeshInsert", "Stock mesh insertion cancelled"))
            if cancel.is_set():
                raise InterruptedError(QCoreApplication.translate("StockMeshInsert", "Stock mesh insertion cancelled"))
            window._add_stl_mesh(
                mesh, QCoreApplication.translate("StockMeshInsert", "Stock snapshot {0}").format(count)
            )
    except InterruptedError:
        window.ui.statusbar.showMessage(
            QCoreApplication.translate("StockMeshInsert", "Stock mesh insertion cancelled"), 5000
        )
        return False
    except Exception as exc:  # A Qt action must report worker/driver errors without terminating the GUI.
        LOGGER.exception("stock_mesh_insert_failed motion_count=%d", target)
        window.ui.statusbar.showMessage(str(exc), 10000)
        return False
    LOGGER.info("stock_mesh_inserted motion_count=%d triangles=%d", target, mesh.triangle_count)
    window.ui.statusbar.showMessage(
        QCoreApplication.translate("StockMeshInsert", "Stock mesh inserted: {0} triangles").format(mesh.triangle_count),
        5000,
    )
    return True
