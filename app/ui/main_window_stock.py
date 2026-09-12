"""Main-window integration for turning Stock Removal playback."""

from __future__ import annotations

import logging
from time import perf_counter

import numpy as np
from PyQt6.QtGui import QColor
from pyqtgraph.opengl import GLLinePlotItem

from app.gcode.stock import TurningStockSpec, TurningStockTimeline
from app.gcode.turning_stock_bounds import auto_turning_stock_suggestion, stock_outline_bounds
from app.ui.stock_overlay import TurningStockOverlayItem

STOCK_OUTLINE_COLOR = "#4fa7a0"
LOGGER = logging.getLogger(__name__)
_SLOW_STOCK_FRAME_MS = 100.0
_SLOW_LOG_INTERVAL_SECONDS = 1.0
STOCK_RENDER_INTERVAL_SECONDS = 1.0 / 30.0


class MainWindowStockMixin:
    """Own the stock timeline and its isolated playback scene."""

    def _current_stock_spec(self):
        spec = TurningStockSpec(
            outer_diameter=self.turnStockDiameter,
            inner_diameter=self.turnStockInnerDiameter,
            length=self.turnStockLength,
            resolution=self.turnStockResolution,
            front_z=self.turnStockFrontAllowance,
        )
        spec.validate()
        return spec

    def applyStockSettings(self, values):
        spec = TurningStockSpec(
            outer_diameter=float(values["outer_diameter"]),
            inner_diameter=float(values.get("inner_diameter", 0.0)),
            length=float(values["length"]),
            resolution=float(values["resolution"]),
            front_z=float(values.get("front_allowance", getattr(self, "turnStockFrontAllowance", 2.0))),
        )
        spec.validate()
        self.turnStockDiameter = spec.outer_diameter
        self.turnStockInnerDiameter = spec.inner_diameter
        self.turnStockLength = spec.length
        self.turnStockResolution = spec.resolution
        self.turnStockFrontAllowance = spec.front_z
        self.stockEnabled = bool(values.get("enabled", True))
        self.stockConfigured = True
        self._stock_outline_use_configured = True
        if getattr(self, "_stock_animation_active", False):
            self.ui.actionPlay.setChecked(False)
            self.timer.stop()
            self._leave_stock_animation()
        self.saveSettings()
        self._update_stock_outline()
        LOGGER.info(
            "stock_settings_applied enabled=%s outer_diameter=%.3f inner_diameter=%.3f length=%.3f "
            "front_z=%.3f resolution=%.3f",
            self.stockEnabled,
            spec.outer_diameter,
            spec.inner_diameter,
            spec.length,
            spec.front_z,
            spec.resolution,
        )
        self.ui.statusbar.showMessage("Turning stock configured", 5000)

    def _refresh_auto_stock_suggestion(self) -> None:
        result = getattr(self, "execution_result", None)
        motions = () if result is None else result.motions
        self._stock_auto_suggestion = auto_turning_stock_suggestion(motions) if self.latheMode and motions else None
        if self._stock_auto_suggestion is not None:
            self._stock_outline_use_configured = False
            LOGGER.debug(
                "stock_auto_bounds outer_diameter=%.3f inner_diameter=%.3f length=%.3f motions=%d",
                self._stock_auto_suggestion.outer_diameter,
                self._stock_auto_suggestion.inner_diameter,
                self._stock_auto_suggestion.length,
                len(motions),
            )
        else:
            LOGGER.debug("stock_auto_bounds unavailable lathe=%s motions=%d", self.latheMode, len(motions))

    def _effective_stock_spec(self):
        """Return the stock dimensions shared by the outline and playback."""
        configured = getattr(self, "stockConfigured", False)
        if configured and getattr(self, "_stock_outline_use_configured", True):
            return self._current_stock_spec()
        suggestion = getattr(self, "_stock_auto_suggestion", None)
        if suggestion is None:
            return self._current_stock_spec() if configured else None
        front_allowance = max(0.0, float(getattr(self, "turnStockFrontAllowance", 2.0)))
        return TurningStockSpec(
            outer_diameter=float(suggestion.outer_diameter),
            inner_diameter=float(suggestion.inner_diameter),
            length=float(suggestion.length) + front_allowance,
            resolution=float(getattr(self, "turnStockResolution", 0.5)),
            front_z=front_allowance,
        )

    def _stock_outline_spec(self):
        if (
            not self.latheMode
            or not getattr(self, "showStock", True)
            or getattr(self, "_stock_animation_active", False)
        ):
            return None
        return self._effective_stock_spec()

    def _stock_outline_segments(self, spec: TurningStockSpec):
        outer = float(spec.outer_diameter) * 0.5
        inner = float(spec.inner_diameter) * 0.5
        front = float(spec.front_z)
        back = front - float(spec.length)
        segments = [
            ((-outer, 0.0, front), (-outer, 0.0, back), (outer, 0.0, back), (outer, 0.0, front)),
        ]
        if inner > 0.0:
            segments.append(((-inner, 0.0, front), (-inner, 0.0, back), (inner, 0.0, back), (inner, 0.0, front)))
        return segments

    def _ensure_stock_outline_items(self, count: int) -> None:
        items = getattr(self, "_stock_outline_items", None)
        if items is None:
            items = []
            self._stock_outline_items = items
        while len(items) < count:
            item = GLLinePlotItem(
                pos=np.empty((0, 3), dtype=np.float32),
                color=QColor(STOCK_OUTLINE_COLOR),
                width=1.25,
                antialias=True,
                mode="line_strip",
            )
            item.setGLOptions("translucent")
            items.append(item)

    def _update_stock_outline(self) -> None:
        spec = self._stock_outline_spec()
        if spec is None:
            self._clear_stock_outline()
            return
        segments = self._stock_outline_segments(spec)
        self._ensure_stock_outline_items(len(segments))
        for item, segment in zip(self._stock_outline_items, segments, strict=False):
            points = (*segment, segment[0])
            item.setData(pos=np.asarray(points, dtype=np.float32), color=QColor(STOCK_OUTLINE_COLOR), width=1.25)
            if item not in self.ui.graphicsView.items:
                self.ui.graphicsView.addItem(item)
            item.setVisible(True)
        for item in self._stock_outline_items[len(segments) :]:
            item.setVisible(False)

    def _clear_stock_outline(self) -> None:
        for item in getattr(self, "_stock_outline_items", ()) or ():
            if item in self.ui.graphicsView.items:
                self.ui.graphicsView.removeItem(item)
            item.setVisible(False)

    def stockOutlineBounds(self):
        spec = self._stock_outline_spec()
        return None if spec is None else stock_outline_bounds(spec)

    def stockFitBounds(self):
        """Return effective stock bounds for Lathe Fit View, independent of outline visibility."""
        if not self.latheMode:
            return None
        if getattr(self, "_stock_animation_active", False):
            return self.stockAnimationBounds()
        spec = self._effective_stock_spec()
        return None if spec is None else stock_outline_bounds(spec)

    def _rebuild_stock_timeline(self) -> bool:
        started = perf_counter()
        result = getattr(self, "execution_result", None)
        LOGGER.debug(
            "stock_timeline_build_requested lathe=%s enabled=%s configured=%s complete=%s motions=%d",
            self.latheMode,
            getattr(self, "stockEnabled", False),
            getattr(self, "stockConfigured", False),
            None if result is None else result.complete,
            0 if result is None else len(result.motions),
        )
        if not self.latheMode or not getattr(self, "stockEnabled", False):
            self._stock_timeline = None
            return False
        if not getattr(self, "stockConfigured", False):
            self._stock_timeline = None
            self.ui.statusbar.showMessage("Configure turning stock in Settings > Stock first.", 10000)
            return False
        if result is None or not result.motions:
            self._stock_timeline = None
            self.ui.statusbar.showMessage("Stock Removal needs a calculated turning toolpath.", 10000)
            return False
        if not result.complete:
            self._stock_timeline = None
            self.ui.statusbar.showMessage("Stock Removal needs a complete turning program.", 10000)
            return False
        spec = self._effective_stock_spec()
        try:
            self._stock_timeline = TurningStockTimeline(result.motions, spec, self.tools)
        except ValueError as exc:
            self._stock_timeline = None
            self.ui.statusbar.showMessage(f"Stock Removal is unavailable: {exc}", 10000)
            LOGGER.warning("stock_timeline_build_failed error=%s", exc)
            return False
        if getattr(self, "_stock_item", None) is None:
            self._stock_item = TurningStockOverlayItem()
        LOGGER.info(
            "stock_timeline_built duration_ms=%.3f motions=%d profile_points=%d resolution=%.3f "
            "outer_diameter=%.3f inner_diameter=%.3f length=%.3f front_z=%.3f tools=%d",
            (perf_counter() - started) * 1000.0,
            len(result.motions),
            len(self._stock_timeline.z),
            spec.resolution,
            spec.outer_diameter,
            spec.inner_diameter,
            spec.length,
            spec.front_z,
            len(self.tools),
        )
        return True

    def _start_stock_animation(self) -> bool:
        started = perf_counter()
        if not self.latheMode or not getattr(self, "stockEnabled", False):
            return False
        if getattr(self, "_stock_animation_active", False):
            if self.ui.horizontalSlider.value() >= self.ui.horizontalSlider.maximum():
                self.ui.horizontalSlider.setValue(0)
            return True
        if not self._rebuild_stock_timeline():
            return False
        self._stock_animation_active = True
        self.ui.horizontalSlider.blockSignals(True)
        self.ui.horizontalSlider.setValue(0)
        self.ui.horizontalSlider.blockSignals(False)
        self._load_stock_animation_plot()
        self.valueHandler(0, sync_editor=False)
        self.fitToView()
        LOGGER.info(
            "stock_playback_started duration_ms=%.3f slider_max=%d",
            (perf_counter() - started) * 1000.0,
            self.ui.horizontalSlider.maximum(),
        )
        return True

    def _leave_stock_animation(self, *, restore_plot: bool = True) -> None:
        if not getattr(self, "_stock_animation_active", False):
            return
        self._stock_animation_active = False
        self._stock_timeline = None
        item = getattr(self, "_stock_item", None)
        if item is not None:
            item.clear()
        if restore_plot:
            self.loadPlot()
            self._create_trace_items()
            if hasattr(self, "_update_stock_outline"):
                self._update_stock_outline()
        LOGGER.info("stock_playback_left restore_plot=%s", restore_plot)

    def _clear_stock_animation(self) -> None:
        self._stock_animation_active = False
        self._stock_timeline = None
        item = getattr(self, "_stock_item", None)
        if item is not None:
            item.clear()
        self._update_stock_outline()

    def _load_stock_animation_plot(self) -> None:
        self.ui.graphicsView.clear()
        self.ui.graphicsView.setBackgroundGradient(
            getattr(self, "plotBackgroundGradient", False),
            self.plotBackground,
        )
        item = getattr(self, "_stock_item", None)
        if item is not None and item not in self.ui.graphicsView.items:
            self.ui.graphicsView.addItem(item)

    def _update_stock_animation_frame(self, playback_count: int) -> None:
        timeline = getattr(self, "_stock_timeline", None)
        result = getattr(self, "execution_result", None)
        if timeline is None or result is None or not result.motions:
            return
        started = perf_counter()
        previous_count = timeline.motion_count
        logical_count = max(0, min(int(playback_count), len(self._playback_movements)))
        count = 0 if logical_count == 0 else self._playback_movements[logical_count - 1].motion_end
        update_started = perf_counter()
        timeline.set_motion_count(count)
        timeline_ms = (perf_counter() - update_started) * 1000.0
        motion = result.motions[0] if count <= 0 else result.motions[count - 1]
        position = (
            motion.start_x * 0.5 if count <= 0 else motion.end_x * 0.5,
            motion.start_z if count <= 0 else motion.end_z,
        )
        tool_spec = self.tools.get(motion.tool or "", {})
        mesh_started = perf_counter()
        render_now = perf_counter()
        last_render = getattr(self, "_stock_last_render_at", 0.0)
        playback_active = bool(self.ui.actionPlay.isChecked())
        update_stock = (
            not playback_active
            or count in (0, len(result.motions))
            or render_now - last_render >= STOCK_RENDER_INTERVAL_SECONDS
        )
        self._stock_item.set_frame(timeline, position, tool_spec, update_stock=update_stock)
        if update_stock:
            self._stock_last_render_at = render_now
        mesh_ms = (perf_counter() - mesh_started) * 1000.0
        if self._stock_item not in self.ui.graphicsView.items:
            self.ui.graphicsView.addItem(self._stock_item)
        total_ms = (perf_counter() - started) * 1000.0
        sample_interval = max(100, len(result.motions) // 20)
        sampled = count in (0, len(result.motions)) or count % sample_interval == 0
        now = perf_counter()
        last_slow_log = getattr(self, "_stock_last_slow_log_at", 0.0)
        slow_log_due = total_ms >= _SLOW_STOCK_FRAME_MS and now - last_slow_log >= _SLOW_LOG_INTERVAL_SECONDS
        if slow_log_due:
            self._stock_last_slow_log_at = now
        log = LOGGER.warning if slow_log_due else LOGGER.debug
        if sampled or slow_log_due:
            log(
                "stock_frame count=%d/%d delta=%d total_ms=%.3f timeline_ms=%.3f mesh_ms=%.3f "
                "revision=%d profile_points=%d vertices=%d faces=%d tool=%s",
                count,
                len(result.motions),
                abs(count - previous_count),
                total_ms,
                timeline_ms,
                mesh_ms,
                timeline.revision,
                len(timeline.z),
                self._stock_item.last_stock_vertex_count,
                self._stock_item.last_stock_face_count,
                motion.tool or "unknown",
            )

    def stockAnimationBounds(self):
        timeline = getattr(self, "_stock_timeline", None)
        if not getattr(self, "_stock_animation_active", False) or timeline is None:
            return None
        bounds = timeline.bounds
        margin = max(2.0, timeline.spec.outer_diameter * 0.09)
        return (
            (bounds[0][0] - margin, bounds[0][1] + margin),
            (-margin * 0.15, margin * 0.15),
            (bounds[2][0] - margin * 0.25, bounds[2][1] + margin * 0.25),
        )
