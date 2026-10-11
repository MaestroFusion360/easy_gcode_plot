"""Milling stock configuration, cooperative replay and bounded STL export."""

from __future__ import annotations

import logging
from bisect import bisect_right
from threading import Event
from time import perf_counter

from PyQt6.QtCore import QCoreApplication, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QFileDialog
from pyqtgraph.opengl import GLLinePlotItem

from app.gcode.stock import MillingStockSpec, MillingStockTimeline, auto_milling_stock, write_milling_stock_stl
from app.gcode.stock.milling_stock_quality import MILLING_ACCURACY_PRESETS
from app.gcode.stock.replay import finish_milling_seek
from app.tools.definitions import DEFAULT_MILLING_TOOL
from app.ui.dialogs.stock_stl_export_dialog import StockStlExportDialog
from app.ui.plot.milling_stock_overlay import MillingStockOverlayItem
from app.ui.windows.execution_worker import run_execution
from app.ui.windows.milling_stock_worker import MillingStockFrameWorker

LOGGER = logging.getLogger(__name__)


class MainWindowMillingStockMixin:
    """Keep milling simulation independent of turning profile rendering."""

    def _selected_milling_stock_accuracy(self):
        return max(0, min(4, int(self.millingStockAccuracy)))

    def _set_milling_stock_quality(self, accuracy):
        self._milling_display_accuracy = accuracy
        self._milling_stock_item.set_quality(*MILLING_ACCURACY_PRESETS[accuracy])

    def _request_milling_stock_quality(self):
        accuracy = self._selected_milling_stock_accuracy()
        current = getattr(self, "_milling_pending_quality", None)
        if current is None:
            current = getattr(self, "_milling_display_accuracy", None)
        if accuracy == current:
            return
        count = self.ui.horizontalSlider.value()
        worker = getattr(self, "_milling_frame_worker", None)
        if worker is not None:
            self._milling_pending_quality = accuracy
            self._milling_pending_count = count
            worker.requestInterruption()
        else:
            self._set_milling_stock_quality(accuracy)
            self._apply_milling_stock_frame(count)

    def _milling_stock_bounds_changed(self, values):
        manual = bool(values.get("manual", True))
        if manual != self.millingStockManual:
            return True
        pairs = [("allowance", "millingStockAllowance"), ("resolution", "millingStockResolution")]
        if manual:
            pairs.extend(
                (axis, "millingStock" + axis.title().replace("_", ""))
                for axis in ("x_minus", "x_plus", "y_minus", "y_plus", "z_minus", "z_plus")
            )
        return any(float(values[key]) != float(getattr(self, attribute)) for key, attribute in pairs)

    def _advance_milling_stock_playback(self, maximum, value):
        if self.playbackSpeed == 5:
            self._apply_milling_stock_frame(
                maximum,
                replay_budget=max(0.05, getattr(self, "_milling_mesh_seconds", 0.05) * 3),
            )
            return
        clock = getattr(self, "_milling_play_clock", None)
        if clock is None:
            clock = (perf_counter(), value)
            self._milling_play_clock = clock
        target = min(maximum, max(value + 1, clock[1] + int((perf_counter() - clock[0]) * 1000 / self.speedTimer)))
        self.ui.horizontalSlider.setValue(target)

    def millingStockOrigin(self):
        result = getattr(self, "execution_result", None)
        if result is None:
            return (0.0, 0.0, 0.0)
        cutting = next((m for m in result.motions if m.move != 0), None)
        code = next(
            (
                step.active_wcs
                for step in result.execution_steps
                if cutting is not None and step.source_block == cutting.source_block
            ),
            54,
        )
        return dict(result.wcs_offsets).get(code, (0.0, 0.0, 0.0))

    def millingStockDialogSpec(self, *, force_auto=False):
        """Return saved WCS box or the current trajectory-derived suggestion."""
        if getattr(self, "millingStockManual", False) and not force_auto:
            ox, oy, oz = self.millingStockOrigin()
            return MillingStockSpec(
                self.millingStockXMinus + ox,
                self.millingStockXPlus + ox,
                self.millingStockYMinus + oy,
                self.millingStockYPlus + oy,
                self.millingStockZMinus + oz,
                self.millingStockZPlus + oz,
                self.millingStockResolution,
            )
        result = getattr(self, "execution_result", None)
        motions = () if result is None else result.motions
        return auto_milling_stock(
            motions,
            self.millingStockAllowance,
            self.millingStockResolution,
            tools=self.millingTools,
            wcs_origin=self.millingStockOrigin(),
        )

    def applyMillingStockSettings(self, values):
        """Apply the six WCS offsets and bounded dexel resolution."""
        bounds_changed = self._milling_stock_bounds_changed(values)
        spec = MillingStockSpec(
            float(values["x_minus"]),
            float(values["x_plus"]),
            float(values["y_minus"]),
            float(values["y_plus"]),
            float(values["z_minus"]),
            float(values["z_plus"]),
            float(values["resolution"]),
        )
        if bool(values.get("manual", True)):
            spec.validate()
        else:
            result = getattr(self, "execution_result", None)
            motions = () if result is None else result.motions
            suggestion = auto_milling_stock(
                motions,
                float(values["allowance"]),
                float(values["resolution"]),
                tools=self.millingTools,
                wcs_origin=self.millingStockOrigin(),
            )
            if suggestion is not None:
                suggestion.validate()
        for axis in ("x_minus", "x_plus", "y_minus", "y_plus", "z_minus", "z_plus"):
            setattr(self, "millingStock" + "".join(part.title() for part in axis.split("_")), float(values[axis]))
        self.millingStockAllowance = float(values["allowance"])
        self.millingStockResolution = spec.resolution
        self.millingStockManual = bool(values.get("manual", True))
        self.millingStockAccuracy = max(0, min(4, int(values.get("accuracy", self.millingStockAccuracy))))
        if getattr(self, "_stock_animation_active", False):
            self._apply_active_milling_stock_settings(bounds_changed)
        self.saveSettings()
        self.ui.statusbar.showMessage(QCoreApplication.translate("MainWindow", "Milling stock configured"), 5000)

    def _apply_active_milling_stock_settings(self, bounds_changed):
        self._pause_playback()
        if bounds_changed:
            self._leave_stock_animation()
        else:
            self._request_milling_stock_quality()

    def resetMillingStockToAuto(self):
        self.millingStockManual = False
        if getattr(self, "_stock_animation_active", False) and not self.latheMode:
            self.ui.actionPlay.setChecked(False)
            self.timer.stop()
            self._leave_stock_animation()
        self.saveSettings()

    def _start_milling_stock_animation(self):
        self._cancel_milling_seek()
        result = getattr(self, "execution_result", None)
        if result is None or not result.complete or not result.motions:
            self.ui.statusbar.showMessage(
                QCoreApplication.translate("MainWindow", "Stock Removal needs a complete milling toolpath."), 10000
            )
            return False
        if result.language != "fanuc_mill" or result.source_dialect not in ("fanuc", "sinumerik"):
            self.ui.statusbar.showMessage(
                QCoreApplication.translate("MainWindow", "3-axis milling stock requires FANUC or native SINUMERIK."),
                10000,
            )
            return False
        try:
            if any(abs(angle) > 1e-10 for _, angle in result.rotary_angles):
                raise ValueError("3-axis stock only: rotary axes are not supported")
            for step in getattr(result, "execution_steps", ()):
                if step.tool_axis_control or step.twp_orientation is not None or step.rotary_angles:
                    raise ValueError("3-axis stock only: rotary/TCP commands are not supported")
            spec = self.millingStockDialogSpec()
            if spec is None:
                raise ValueError("No toolpath bounds")
            self._stock_timeline = MillingStockTimeline(result.motions, spec, self.millingTools)
        except ValueError as exc:
            self.ui.statusbar.showMessage(
                QCoreApplication.translate("MainWindow", "Stock Removal is unavailable: {0}").format(exc), 10000
            )
            LOGGER.warning("milling_stock_unavailable reason=%s", exc)
            self._stock_timeline = None
            return False
        if getattr(self, "_milling_stock_item", None) is None:
            self._milling_stock_item = MillingStockOverlayItem()
            self.ui.actionPlay.toggled.connect(self._milling_stock_item.set_playing)
        self._milling_stock_item.set_playing(self.ui.actionPlay.isChecked())
        self._set_milling_stock_quality(self._selected_milling_stock_accuracy())
        self._milling_mesh_seconds = 0.05
        self._milling_stock_item.set_colors(
            getattr(self, "plotStockColor", "#4fa7a0"), getattr(self, "plotCutColor", "#b8a879")
        )
        # The initial full box must render before the first playback movement.
        self._milling_stock_item.set_frame(self._stock_timeline)
        self._stock_animation_active = True
        getattr(self.ui, "actionSaveStockStl").setEnabled(True)
        self.ui.horizontalSlider.blockSignals(True)
        self.ui.horizontalSlider.setValue(0)
        self.ui.horizontalSlider.blockSignals(False)
        self._load_stock_animation_plot()
        self.valueHandler(0, sync_editor=False)
        self.fitToView()
        if self._stock_timeline.missing_tools:
            names = ", ".join(str(tool) if tool is not None else "?" for tool in self._stock_timeline.missing_tools)
            self.ui.statusbar.showMessage(
                QCoreApplication.translate(
                    "MainWindow",
                    "Stock Removal: missing tool(s) {0}; default cutter used. Removal geometry may be inaccurate.",
                ).format(names),
                15000,
            )
        return True

    def _update_milling_stock_animation_frame(self, playback_count):
        if getattr(self, "_milling_publishing_frame", False):
            return
        self._ensure_milling_seek_timer()
        if self.ui.horizontalSlider.isSliderDown():
            self._milling_pending_count = playback_count
            self._milling_seek_timer.start(30)
            return
        if getattr(self, "_milling_seek_timer", None) is not None:
            self._milling_seek_timer.stop()
        self._milling_pending_count = None
        self._apply_milling_stock_frame(playback_count)

    def _ensure_milling_seek_timer(self):
        if getattr(self, "_milling_seek_timer", None) is None:
            self._milling_seek_timer = QTimer(self)
            self._milling_seek_timer.setSingleShot(True)
            self._milling_seek_timer.timeout.connect(self._flush_milling_seek)
            self.ui.horizontalSlider.sliderReleased.connect(self._flush_milling_seek)

    def _cancel_milling_seek(self):
        timer = getattr(self, "_milling_seek_timer", None)
        if timer is not None:
            timer.stop()
        self._milling_pending_count = None
        self._milling_pending_quality = None
        worker = getattr(self, "_milling_frame_worker", None)
        if worker is not None:
            worker.requestInterruption()
            worker.wait()
            self._milling_frame_worker = None
            worker.deleteLater()

    def _flush_milling_seek(self):
        self._milling_seek_timer.stop()
        count = getattr(self, "_milling_pending_count", None)
        self._milling_pending_count = None
        if count is not None and self._stock_animation_active and not self.latheMode:
            self._apply_milling_stock_frame(count)

    def _apply_milling_stock_frame(self, playback_count, *, replay_budget=None):
        timeline = getattr(self, "_stock_timeline", None)
        result = getattr(self, "execution_result", None)
        if timeline is None or result is None:
            return
        logical_count = max(0, min(int(playback_count), len(self._playback_movements)))
        count = 0 if logical_count == 0 else self._playback_movements[logical_count - 1].motion_end
        worker = getattr(self, "_milling_frame_worker", None)
        if worker is not None:
            self._milling_pending_count = playback_count
            if worker.count != count:
                worker.requestInterruption()
            return
        self._milling_stock_item.set_colors(self.plotStockColor, self.plotCutColor)
        worker = MillingStockFrameWorker(timeline, self._milling_stock_item, count, replay_budget)
        self._milling_frame_worker = worker
        worker.finished.connect(self._finish_milling_stock_frame)
        worker.start()

    def _finish_milling_stock_frame(self):
        worker = self.sender()
        if worker is not getattr(self, "_milling_frame_worker", None):
            return
        self._milling_frame_worker = None
        pending = self._milling_pending_count
        self._milling_pending_count = None
        quality = getattr(self, "_milling_pending_quality", None)
        self._milling_pending_quality = None
        if quality is not None:
            self._set_milling_stock_quality(quality)
        timeline = worker.timeline
        if worker.error is not None and not isinstance(worker.error, InterruptedError):
            self.ui.statusbar.showMessage(str(worker.error), 10000)
            self.ui.actionPlay.setChecked(False)
            self.timer.stop()
            self._leave_stock_animation()
        elif pending is not None:
            self._apply_milling_stock_frame(pending)
        elif worker.tiles is not None and timeline is getattr(self, "_stock_timeline", None):
            self._milling_stock_item.apply_frame(timeline, worker.tiles, worker.revision)
            self._milling_mesh_seconds = worker.mesh_seconds
            if worker.replay_budget is not None:
                logical_count = bisect_right(
                    self._playback_movements, timeline.motion_count, key=lambda m: m.motion_end
                )
                self.ui.horizontalSlider.blockSignals(True)
                self.ui.horizontalSlider.setValue(logical_count)
                self.ui.horizontalSlider.blockSignals(False)
                self._milling_publishing_frame = True
                try:
                    self.valueHandler(logical_count)
                finally:
                    self._milling_publishing_frame = False
                self._macro_playback_position_changed(logical_count)
            self._show_milling_stock_position()
        worker.deleteLater()

    def _show_milling_stock_position(self):
        timeline = self._stock_timeline
        result = self.execution_result
        count = timeline.motion_count
        logical_count = bisect_right(self._playback_movements, count, key=lambda move: move.motion_end)
        motion = result.motions[0] if count == 0 else result.motions[count - 1]
        xyz = (
            (motion.start_x, motion.start_y, motion.start_z)
            if count == 0
            else (motion.end_x, motion.end_y, motion.end_z)
        )
        tool = getattr(self, "_milling_tool_item", None)
        if tool is not None:
            tool.show_tool(self.millingTools.get(motion.tool, DEFAULT_MILLING_TOOL), xyz)
        tail = getattr(self, "_stock_tail_item", None)
        toolpath = getattr(self, "_toolpath_item", None)
        if tail is None:
            tail = GLLinePlotItem(mode="lines", width=2, antialias=True)
            self._stock_tail_item = tail
        if logical_count > 0 and toolpath is not None:
            begin, end = toolpath.segment_range_for_logical(logical_count - 1)
            tail.setData(pos=toolpath.packed_vertices[begin * 2 : end * 2], color=QColor(self.plotCurrentColor))
            if tail not in self.ui.graphicsView.items:
                self.ui.graphicsView.addItem(tail)
        elif tail in self.ui.graphicsView.items:
            self.ui.graphicsView.removeItem(tail)

    def saveMillingStockStl(self):
        timeline = getattr(self, "_stock_timeline", None)
        if not getattr(self, "_stock_animation_active", False) or self.latheMode or timeline is None:
            return
        self._pause_playback()
        options = StockStlExportDialog.get_options(self)
        if options is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, QCoreApplication.translate("MainWindow", "Save stock as STL"), "stock.stl", "STL (*.stl)"
        )
        if not path:
            return
        if not path.lower().endswith(".stl"):
            path += ".stl"
        self._pause_playback()
        timeline = self._stock_timeline
        if timeline is None or getattr(self, "_stock_export_active", False):
            return
        self._cancel_milling_seek()
        cancel = Event()
        self._stock_export_active = True
        self._stock_export_cancel = cancel
        self.ui.actionSaveStockStl.setEnabled(False)
        try:
            logical_count = self.ui.horizontalSlider.value()
            count = 0 if logical_count == 0 else self._playback_movements[logical_count - 1].motion_end
            snapshot = run_execution(
                self,
                finish_milling_seek,
                timeline,
                {"count": count, "cancelled": cancel.is_set},
                cancel.set,
                title=QCoreApplication.translate("MainWindow", "Save stock as STL"),
                show_dialog=True,
            )
            tiles = run_execution(
                self,
                self._milling_stock_item.build_frame,
                timeline,
                {"cancelled": cancel.is_set},
                cancel.set,
                show_dialog=False,
            )
            self._milling_stock_item.apply_frame(timeline, tiles, timeline.revision)
            triangles = run_execution(
                self,
                write_milling_stock_stl,
                path,
                {"timeline": snapshot, "cancelled": cancel.is_set, "precise": True, "options": options},
                cancel.set,
                title=QCoreApplication.translate("MainWindow", "Save stock as STL"),
                status_text=QCoreApplication.translate("MainWindow", "Writing stock STL..."),
                cancelling_text=QCoreApplication.translate("MainWindow", "Cancelling stock STL export..."),
            )
        except (OSError, ValueError, InterruptedError) as exc:
            self.ui.statusbar.showMessage(str(exc), 10000)
        else:
            self.ui.statusbar.showMessage(
                QCoreApplication.translate("MainWindow", "STL: {0} triangles").format(f"{triangles:,}"), 7000
            )
        finally:
            self._stock_export_active = False
            self._stock_export_cancel = None
            self.ui.actionSaveStockStl.setEnabled(self._stock_animation_active and not self.latheMode)
