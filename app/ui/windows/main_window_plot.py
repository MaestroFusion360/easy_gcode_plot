"""OpenGL rendering, view, grid, and trajectory-picking helpers for the main window."""

import logging
import math
from dataclasses import dataclass, replace
from pathlib import Path
from time import perf_counter

import numpy as np
from OpenGL import GL
from PyQt6.QtCore import QCoreApplication, QSignalBlocker, Qt
from PyQt6.QtGui import QColor, QMatrix4x4, QQuaternion, QVector3D, QVector4D
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
)
from pyqtgraph.opengl import GLGridItem, GLLinePlotItem, GLScatterPlotItem

from app.tools.definitions import DEFAULT_MILLING_TOOL
from app.ui.panels.stl_objects_panel import StlObjectsPanel
from app.ui.plot.axis_triad import AxisTriadItem
from app.ui.plot.milling_tool_preview import MillingToolPreviewItem
from app.ui.plot.plot_grid import adaptive_grid_geometry
from app.ui.plot.plot_navigation import point_segment_distance as _point_segment_distance
from app.ui.plot.stl import StlMesh, mesh_from_triangles, read_stl
from app.ui.plot.stl_overlay import StlOverlay
from app.ui.plot.stl_transform import (
    MeshMeasurements,
    StlObject,
    circular_array,
    clip_mesh,
    measure_mesh,
    rectangular_array,
)
from app.ui.plot.toolpath_vbo import ToolpathVboItem, segments_from_render_points

PICK_DISTANCE_PX = 8.0
CURSOR_SIZE_PX = 7.0
RAPID_COLOR = "#d02020"
LOGGER = logging.getLogger(__name__)
GRID_GL_OPTIONS = {
    GL.GL_DEPTH_TEST: True,
    GL.GL_BLEND: True,
    GL.GL_CULL_FACE: False,
    "glDepthMask": (False,),
    "glBlendFuncSeparate": (
        GL.GL_SRC_ALPHA,
        GL.GL_ONE_MINUS_SRC_ALPHA,
        GL.GL_ONE,
        GL.GL_ONE_MINUS_SRC_ALPHA,
    ),
}


def _display_value(value, unit_scale):
    """Format a physical millimetre value in the active program units."""
    rounded = round(float(value) / float(unit_scale), 3)
    return str(0.0 if rounded == 0 else rounded)


def _lathe_arc_offsets(motion):
    """Return relative Fanuc I/K values from resolved physical arc geometry."""
    if motion.arc is None or motion.plane != 18:
        return motion.i, motion.k
    center_x, _, center_z = motion.arc.center
    i_value = (center_x - motion.start_x * motion.x_scale) / motion.x_scale
    return i_value, center_z - motion.start_z


def _render_point_bounds(points):
    if not points:
        return None
    first = points[0]
    lows = [float(first.x), float(first.y), float(first.z)]
    highs = lows.copy()
    for point in points[1:]:
        for axis, value in enumerate((point.x, point.y, point.z)):
            value = float(value)
            lows[axis] = min(lows[axis], value)
            highs[axis] = max(highs[axis], value)
    return tuple((lows[axis], highs[axis]) for axis in range(3))


def _bounds_exceed_milling_camera(view, bounds):
    matrix = view.viewMatrix()
    camera_center = matrix * QVector4D(view.opts["center"], 1.0)
    aspect = max(float(view.width()), 1.0) / max(float(view.height()), 1.0)
    distance = float(view.opts["distance"])
    tangent = math.tan(math.radians(max(float(view.opts.get("fov", 60.0)), 0.01)) / 2.0)
    for x in bounds[0]:
        for y in bounds[1]:
            for z in bounds[2]:
                corner = matrix * QVector4D(x, y, z, 1.0)
                lateral = max(abs(corner.x() - camera_center.x()), abs(corner.y() - camera_center.y()) * aspect)
                if view.isOrthographic():
                    if lateral > view.orthographicWidth() * 0.4:
                        return True
                    continue
                depth = corner.z() - camera_center.z()
                half_width = (distance - depth) * tangent * 0.8
                if half_width <= 0 or lateral > half_width:
                    return True
    return False


@dataclass
class _StlSceneEntry:
    obj: StlObject
    overlay: StlOverlay
    measurements: MeshMeasurements | None = None
    section_overlay: StlOverlay | None = None


@dataclass(frozen=True)
class _StlSceneState:
    objects: tuple[StlObject, ...]
    selected_row: int
    section: tuple[int, str, float, bool] | None


class MainWindowPlotMixin:
    def _configure_stl_panel(self):
        """Create the runtime STL object dock without modifying generated Designer files."""
        self._stl_entries = []
        self._stl_section_item = None
        self._stl_section_spec = None
        self._stl_pivot_item = None
        self._stl_bbox_item = None
        self._stl_bbox_picks_item = None
        self._stl_bbox_entry = None
        self._stl_bbox_picked_index = None
        self._stl_undo = []
        self._stl_redo = []
        self.stlObjectsDock = StlObjectsPanel(self)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.stlObjectsDock)
        self.ui.menuSettings.insertAction(self.ui.actionOptions, self.stlObjectsDock.toggleViewAction())
        self.stlObjectsDock.hide()

        panel = self.stlObjectsDock
        panel.selectionChanged.connect(self._stl_selection_changed)
        panel.deleteRequested.connect(self.removeSelectedStl)
        panel.statisticsRequested.connect(self._show_selected_stl_statistics)
        panel.pivotRequested.connect(self._set_selected_stl_pivot)
        panel.moveRequested.connect(self._move_selected_stl)
        panel.rotateRequested.connect(self._rotate_selected_stl)
        panel.mirrorRequested.connect(self._mirror_selected_stl)
        panel.scaleRequested.connect(self._scale_selected_stl)
        panel.circularArrayRequested.connect(self._circular_array_selected_stl)
        panel.rectangularArrayRequested.connect(self._rectangular_array_selected_stl)
        panel.sectionRequested.connect(self._section_selected_stl)
        panel.clearSectionRequested.connect(self._clear_stl_section_with_history)
        panel.undoRequested.connect(self.undoStl)
        panel.redoRequested.connect(self.redoStl)
        panel.set_history_available(undo=False, redo=False)

    def _capture_stl_scene(self):
        return _StlSceneState(
            tuple(entry.obj for entry in self._stl_entries),
            self.stlObjectsDock.objectList.currentRow(),
            self._stl_section_spec,
        )

    def _record_stl_edit(self):
        self._stl_undo.append(self._capture_stl_scene())
        del self._stl_undo[:-50]
        self._stl_redo.clear()
        self.stlObjectsDock.set_history_available(undo=True, redo=False)

    def _restore_stl_scene(self, state):
        self.clearStlSection()
        for entry in self._stl_entries:
            self._replace_scene_item(entry.overlay.item, None)
        self._stl_entries.clear()
        for obj in state.objects:
            overlay = StlOverlay(obj)
            item = overlay.item_for(getattr(self, "stlColor", "#b0b0b0"), getattr(self, "stlWireframe", False))
            self._stl_entries.append(_StlSceneEntry(obj, overlay))
            self._replace_scene_item(None, item)
        self._sync_stl_panel(state.selected_row)
        self.stlObjectsDock.setVisible(bool(state.objects))
        if state.section is not None:
            row, axis, offset, keep_positive = state.section
            self._show_stl_section(row, axis, offset, keep_positive)
        self._restore_trace_overlay_order()
        if self.render_points or state.objects:
            self.fitToView()

    def undoStl(self):
        if not self._stl_undo:
            return False
        self._stl_redo.append(self._capture_stl_scene())
        self._restore_stl_scene(self._stl_undo.pop())
        self.stlObjectsDock.set_history_available(undo=bool(self._stl_undo), redo=True)
        return True

    def redoStl(self):
        if not self._stl_redo:
            return False
        self._stl_undo.append(self._capture_stl_scene())
        self._restore_stl_scene(self._stl_redo.pop())
        self.stlObjectsDock.set_history_available(undo=True, redo=bool(self._stl_redo))
        return True

    def importStl(self, path=None):
        """Import an STL model as another editable object in the plot scene."""
        if not path:
            path, _selected_filter = QFileDialog.getOpenFileName(
                self,
                "Import STL",
                "",
                "STL files (*.stl);;All files (*)",
            )
        if not path:
            return False
        try:
            mesh = read_stl(path)
            self._add_stl_mesh(mesh, Path(path).name)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "STL Import Error", str(exc))
            return False
        self._add_recent_stl(path)
        self.ui.statusbar.showMessage(
            QCoreApplication.translate("MainWindow", "Imported STL: {0:,} triangles").format(mesh.triangle_count), 5000
        )
        return True

    def _replace_scene_item(self, old_item, new_item):
        """Replace one GL item without clearing unrelated persistent scene geometry."""
        view = self.ui.graphicsView
        if old_item is new_item:
            if new_item is not None and new_item not in view.items:
                view.addItem(new_item)
            return
        if old_item is not None and old_item in view.items:
            view.removeItem(old_item)
        if new_item is not None and new_item not in view.items:
            view.addItem(new_item)

    def _restore_trace_overlay_order(self):
        """Keep the toolpath/cursor above opaque STL objects without rebuilding buffers."""
        view = self.ui.graphicsView
        for item in (
            getattr(self, "_stl_section_item", None),
            getattr(self, "_stl_bbox_item", None),
            getattr(self, "_stl_bbox_picks_item", None),
            getattr(self, "_stl_pivot_item", None),
            getattr(self, "_toolpath_item", None),
            getattr(self, "_cursor_item", None),
            getattr(self, "_milling_tool_item", None),
        ):
            if item is not None and item in view.items:
                view.removeItem(item)
                view.addItem(item)

    def _unique_stl_name(self, requested: str) -> str:
        existing = {entry.obj.name for entry in self._stl_entries}
        if requested not in existing:
            return requested
        stem = Path(requested).stem or requested
        suffix = Path(requested).suffix
        index = 2
        while f"{stem} ({index}){suffix}" in existing:
            index += 1
        return f"{stem} ({index}){suffix}"

    def _add_stl_mesh(self, mesh: StlMesh, name: str = "STL"):
        obj = StlObject(mesh=mesh, name=self._unique_stl_name(name)).set_pivot("center")
        if self._stl_entries:
            self._record_stl_edit()
        else:
            # The first imported model establishes the scene baseline. Undo must
            # never restore the empty scene and make the STL dock disappear.
            self._stl_undo.clear()
            self._stl_redo.clear()
            self.stlObjectsDock.set_history_available(undo=False, redo=False)
        self._append_stl_object(obj, select=True)
        self.stlObjectsDock.show()
        self.fitToView()

    def _append_stl_object(self, obj: StlObject, *, select: bool):
        overlay = StlOverlay(obj)
        item = overlay.item_for(getattr(self, "stlColor", "#b0b0b0"), getattr(self, "stlWireframe", False))
        self._stl_entries.append(_StlSceneEntry(obj=obj, overlay=overlay))
        self._replace_scene_item(None, item)
        row = len(self._stl_entries) - 1 if select else self.stlObjectsDock.objectList.currentRow()
        self._sync_stl_panel(row)
        self._restore_trace_overlay_order()
        self.ui.actionClearSTL.setEnabled(True)

    def _selected_stl_entry(self):
        row = self.stlObjectsDock.objectList.currentRow()
        if 0 <= row < len(self._stl_entries):
            return row, self._stl_entries[row]
        return None, None

    def _pivot_mode(self, obj: StlObject) -> str:
        return obj.pivot_mode

    def _sync_stl_panel(self, current_row=None):
        if current_row is None:
            current_row = self.stlObjectsDock.objectList.currentRow()
        self.stlObjectsDock.set_objects((entry.obj.name for entry in self._stl_entries), current_row)
        self.ui.actionClearSTL.setEnabled(bool(self._stl_entries))
        self._stl_selection_changed(self.stlObjectsDock.objectList.currentRow())

    def _stl_selection_changed(self, row: int):
        if not 0 <= row < len(self._stl_entries):
            self.stlObjectsDock.set_measurements(None)
            self._update_stl_pivot_marker(None)
            return
        obj = self._stl_entries[row].obj
        self.stlObjectsDock.set_object_state(
            pivot_mode=self._pivot_mode(obj),
            pivot=obj.pivot,
            world_pivot=obj.world_pivot(),
        )
        measurements = measure_mesh(obj.world_triangles())
        self._stl_entries[row].measurements = measurements
        self.stlObjectsDock.set_measurements(measurements)
        self._update_stl_pivot_marker(obj.world_pivot())
        self._update_stl_bbox_overlay(row)

    def _update_stl_pivot_marker(self, point):
        old_item = self._stl_pivot_item
        if old_item is not None and old_item in self.ui.graphicsView.items:
            self.ui.graphicsView.removeItem(old_item)
        self._stl_pivot_item = None
        if point is None:
            return
        item = GLScatterPlotItem(
            pos=np.asarray((point,), dtype=np.float32),
            color=(1.0, 0.56, 0.08, 1.0),
            size=12,
            pxMode=True,
        )
        item.setGLOptions({GL.GL_DEPTH_TEST: False, GL.GL_BLEND: True, "glDepthMask": (False,)})
        self._stl_pivot_item = item
        self.ui.graphicsView.addItem(item)
        self._restore_trace_overlay_order()

    def _update_stl_bbox_overlay(self, selected_row):
        view = self.ui.graphicsView
        for attribute in ("_stl_bbox_item", "_stl_bbox_picks_item"):
            item = getattr(self, attribute, None)
            if item is not None and item in view.items:
                view.removeItem(item)
            setattr(self, attribute, None)
        if not 0 <= selected_row < len(self._stl_entries):
            self._stl_bbox_entry = None
            return
        entry = self._stl_entries[selected_row]
        obj = entry.obj
        if obj.pivot_mode == "min":
            if self._stl_bbox_entry is not entry:
                self._stl_bbox_picked_index = None
            self._stl_bbox_entry = entry
        elif obj.pivot_mode != "custom" or self._stl_bbox_entry is not entry:
            self._stl_bbox_entry = None
        if self._stl_bbox_entry is not entry:
            return
        bounds = entry.overlay.bounds
        corners = np.asarray(
            [(x, y, z) for x in bounds[0] for y in bounds[1] for z in bounds[2]],
            dtype=np.float32,
        )
        edges = ((0, 1), (0, 2), (0, 4), (1, 3), (1, 5), (2, 3), (2, 6), (3, 7), (4, 5), (4, 6), (5, 7), (6, 7))
        line_positions = np.asarray([corners[index] for edge in edges for index in edge], dtype=np.float32)
        color = (1.0, 0.56, 0.08, 1.0)
        line = GLLinePlotItem(pos=line_positions, color=color, width=2.0, antialias=True, mode="lines")
        line.setGLOptions({GL.GL_DEPTH_TEST: False, GL.GL_BLEND: True, "glDepthMask": (False,)})
        pick_positions = corners
        pick_colors = np.tile(color, (8, 1))
        pick_sizes = np.full(8, 10.0, dtype=np.float32)
        if self._stl_bbox_picked_index is not None:
            pick_colors[self._stl_bbox_picked_index] = (0.15, 0.9, 1.0, 1.0)
            pick_sizes[self._stl_bbox_picked_index] = 16.0
        picks = GLScatterPlotItem(pos=pick_positions, color=pick_colors, size=pick_sizes, pxMode=True)
        picks.setGLOptions({GL.GL_DEPTH_TEST: False, GL.GL_BLEND: True, "glDepthMask": (False,)})
        self._stl_bbox_item = line
        self._stl_bbox_picks_item = picks
        view.addItem(line)
        view.addItem(picks)
        self._restore_trace_overlay_order()

    def _pick_stl_bbox_point(self, position):
        _row, entry = self._selected_stl_entry()
        if entry is None or entry is not self._stl_bbox_entry or self._stl_bbox_picks_item is None:
            return False
        px, py = float(position.x()), float(position.y())
        best_index, best_distance = None, PICK_DISTANCE_PX
        for index, point in enumerate(self._stl_bbox_picks_item.pos):
            projected = self._project_world_to_screen(*point)
            if projected is None:
                continue
            distance = math.hypot(px - projected[0], py - projected[1])
            if distance <= best_distance:
                best_index, best_distance = index, distance
        if best_index is None:
            return False
        self._stl_bbox_picked_index = best_index
        bounds = entry.overlay.bounds
        corner_index = best_index
        corner = np.asarray(
            [
                bounds[0][(corner_index >> 2) & 1],
                bounds[1][(corner_index >> 1) & 1],
                bounds[2][corner_index & 1],
            ],
            dtype=float,
        )
        source_point = (np.linalg.inv(entry.obj.matrix) @ np.append(corner, 1.0))[:3]
        self._stl_bbox_entry = entry
        self._replace_selected_stl_object(entry.obj.set_pivot("custom", source_point), geometry_changed=False)
        return True

    def _show_selected_stl_statistics(self):
        _row, entry = self._selected_stl_entry()
        if entry is None:
            return
        if entry.measurements is None:
            entry.measurements = measure_mesh(entry.obj.world_triangles())
        self.stlObjectsDock.set_measurements(entry.measurements)
        dialog = QDialog(self)
        dialog.setWindowTitle(QCoreApplication.translate("MainWindow", "STL Statistics"))
        layout = QVBoxLayout(dialog)
        text = QPlainTextEdit(dialog)
        text.setObjectName("stlStatisticsText")
        text.setReadOnly(True)
        text.setMinimumSize(440, 150)
        layout.addWidget(text)
        inches = QCheckBox(QCoreApplication.translate("MainWindow", "Inches"), dialog)
        inches.setObjectName("stlStatisticsInchesCheck")
        inches.toggled.connect(
            lambda checked: text.setPlainText(
                self.stlObjectsDock.format_measurements(entry.measurements, inches=checked)
            )
        )
        text.setPlainText(self.stlObjectsDock.format_measurements(entry.measurements))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=dialog)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        buttons.button(QDialogButtonBox.StandardButton.Close).clicked.connect(dialog.accept)
        controls = QHBoxLayout()
        controls.addWidget(inches)
        controls.addStretch(1)
        controls.addWidget(buttons)
        layout.addLayout(controls)
        dialog.exec()

    def _replace_selected_stl_object(self, obj: StlObject, *, geometry_changed: bool):
        row, entry = self._selected_stl_entry()
        if entry is None:
            return False
        if (
            np.array_equal(entry.obj.matrix, obj.matrix)
            and entry.obj.pivot == obj.pivot
            and entry.obj.pivot_mode == obj.pivot_mode
        ):
            return False
        self._record_stl_edit()
        if geometry_changed:
            self.clearStlSection()
        old_item = entry.overlay.item
        entry.obj = obj
        if geometry_changed:
            entry.overlay.set_object(obj)
            new_item = entry.overlay.item_for(
                getattr(self, "stlColor", "#b0b0b0"), getattr(self, "stlWireframe", False)
            )
            self._replace_scene_item(old_item, new_item)
            self._restore_trace_overlay_order()
        else:
            entry.overlay.object = obj
        self._sync_stl_panel(row)
        if geometry_changed:
            self.fitToView()
        return True

    def _set_selected_stl_pivot(self, mode: str, point):
        _row, entry = self._selected_stl_entry()
        if entry is not None:
            self._replace_selected_stl_object(entry.obj.set_pivot(mode, point), geometry_changed=False)

    def _move_selected_stl(self, target):
        _row, entry = self._selected_stl_entry()
        if entry is not None:
            self._replace_selected_stl_object(entry.obj.move_pivot_to(target), geometry_changed=True)

    def _rotate_selected_stl(self, axis: str, angle: float):
        _row, entry = self._selected_stl_entry()
        if entry is not None:
            self._replace_selected_stl_object(entry.obj.rotate(axis, angle), geometry_changed=True)

    def _mirror_selected_stl(self, plane: str):
        _row, entry = self._selected_stl_entry()
        if entry is not None:
            self._replace_selected_stl_object(entry.obj.mirrored(plane), geometry_changed=True)

    def _scale_selected_stl(self, factor: float):
        _row, entry = self._selected_stl_entry()
        if entry is not None:
            self._replace_selected_stl_object(entry.obj.scaled(factor), geometry_changed=True)

    def _append_array_copies(self, source: StlObject, matrices):
        if len(matrices) <= 1:
            return
        self._record_stl_edit()
        current_row = self.stlObjectsDock.objectList.currentRow()
        for index, matrix in enumerate(matrices[1:], 2):
            name = self._unique_stl_name(f"{source.name} [{index}]")
            copy = replace(source, name=name, matrix=matrix @ source.matrix)
            self._append_stl_object(copy, select=False)
        self._sync_stl_panel(current_row)
        self.fitToView()

    def _circular_array_selected_stl(self, count: int, total_angle: float, axis: str, center, rotate_copies: bool):
        _row, entry = self._selected_stl_entry()
        if entry is None:
            return
        matrices = circular_array(
            count,
            total_angle,
            axis,
            center,
            rotate_copies=rotate_copies,
            pivot=entry.obj.world_pivot(),
        )
        self._append_array_copies(entry.obj, matrices)

    def _rectangular_array_selected_stl(self, nx: int, ny: int, nz: int, dx: float, dy: float, dz: float):
        _row, entry = self._selected_stl_entry()
        if entry is not None:
            self._append_array_copies(entry.obj, rectangular_array(nx, ny, nz, dx, dy, dz))

    def _section_selected_stl(self, axis: str, offset: float, keep_positive: bool = True):
        row, _entry = self._selected_stl_entry()
        if row is None:
            return
        spec = (row, axis, float(offset), bool(keep_positive))
        if self._stl_section_spec == spec:
            return
        self._record_stl_edit()
        self._show_stl_section(*spec)

    def _show_stl_section(self, row: int, axis: str, offset: float, keep_positive: bool = True):
        entry = self._stl_entries[row]
        triangles = clip_mesh(entry.obj.world_triangles(), axis, offset, keep_positive)
        self.clearStlSection()
        if not triangles.size:
            self.ui.statusbar.showMessage(QCoreApplication.translate("MainWindow", "STL section is empty"), 3000)
            return
        cut_mesh = mesh_from_triangles(triangles)
        cut_obj = StlObject(mesh=cut_mesh, name=entry.obj.name)
        overlay = StlOverlay(cut_obj)
        item = overlay.item_for(getattr(self, "stlColor", "#b0b0b0"), getattr(self, "stlWireframe", False))
        self._replace_scene_item(entry.overlay.item, item)
        entry.section_overlay = overlay
        self._stl_section_item = item
        self._stl_section_spec = (row, axis, float(offset), bool(keep_positive))
        self._restore_trace_overlay_order()
        self.ui.statusbar.showMessage(
            QCoreApplication.translate("MainWindow", "STL cut created: {0:,} triangles").format(len(triangles)),
            5000,
        )

    def clearStlSection(self):
        restored = False
        for entry in getattr(self, "_stl_entries", ()):
            overlay = entry.section_overlay
            if overlay is None:
                continue
            self._replace_scene_item(overlay.item, None)
            entry.section_overlay = None
            self._replace_scene_item(None, entry.overlay.item)
            restored = True
        self._stl_section_item = None
        self._stl_section_spec = None
        if restored:
            self._restore_trace_overlay_order()

    def _clear_stl_section_with_history(self):
        if self._stl_section_spec is not None:
            self._record_stl_edit()
            self.clearStlSection()

    def removeSelectedStl(self):
        row, entry = self._selected_stl_entry()
        if entry is None:
            return False
        self._record_stl_edit()
        self.clearStlSection()
        self._replace_scene_item(entry.overlay.item, None)
        del self._stl_entries[row]
        self._sync_stl_panel(min(row, len(self._stl_entries) - 1))
        if not self._stl_entries:
            self.stlObjectsDock.hide()
        self.fitToView()
        return True

    def refreshStlAppearance(self):
        """Rebuild STL GL items only when the shared visual style changed."""
        changed = False
        for entry in self._stl_entries:
            active_overlay = entry.section_overlay or entry.overlay
            old_item = active_overlay.item
            new_item = active_overlay.item_for(
                getattr(self, "stlColor", "#b0b0b0"), getattr(self, "stlWireframe", False)
            )
            if old_item in self.ui.graphicsView.items:
                self._replace_scene_item(old_item, new_item)
            if entry.section_overlay is not None:
                self._stl_section_item = new_item
            if entry.section_overlay is None and old_item not in self.ui.graphicsView.items:
                entry.overlay.item_for(getattr(self, "stlColor", "#b0b0b0"), getattr(self, "stlWireframe", False))
            changed = changed or new_item is not old_item
        if changed:
            self._restore_trace_overlay_order()
        return changed

    def clearStl(self):
        """Remove all imported STL objects, preserving the executed toolpath."""
        if self._stl_entries:
            self._record_stl_edit()
        self.clearStlSection()
        for entry in self._stl_entries:
            self._replace_scene_item(entry.overlay.item, None)
        self._stl_entries.clear()
        self._sync_stl_panel(-1)
        self.stlObjectsDock.hide()
        if self.render_points:
            self.fitToView()

    def zoomIn(self):
        """Zoom in on the plot."""
        self.ui.graphicsView.zoomBy(0.9)
        self._update_adaptive_grid()

    def zoomOut(self):
        """Zoom out on the plot."""
        self.ui.graphicsView.zoomBy(1.1)
        self._update_adaptive_grid()

    def gridChecked(self):
        """Toggle plot grid visibility and refresh the view."""
        self.plotGrid = self.ui.actionGrid.isChecked()
        LOGGER.info("plot_grid_changed enabled=%s lathe=%s", self.plotGrid, getattr(self, "latheMode", False))
        self.loadPlot()
        self._create_trace_items()
        if self.execution_result is not None and self.execution_result.motions:
            self.valueHandler(self.ui.horizontalSlider.value(), sync_editor=False)

    def plotContextMenu(self, point):
        """Show context menu for plot view controls."""
        menu = QMenu()
        menu.addAction(self.ui.actionFitToView)
        menu.addSeparator()
        menu.addAction(self.ui.actionZoom_In)
        menu.addAction(self.ui.actionZoom_Out)
        menu.addSeparator()
        menu.addAction(self.ui.action3D)
        menu.addAction(self.ui.actionTop)
        menu.addAction(self.ui.actionFront)
        menu.addAction(self.ui.actionLeft)
        menu.addSeparator()
        menu.addAction(self.ui.actionGrid)
        menu.exec(self.ui.graphicsView.mapToGlobal(point))

    def _cached_toolpath_bounds(self):
        points = self.render_points
        if not points:
            self._toolpath_bounds_source = points
            self._toolpath_bounds_cache = None
            return None
        if getattr(self, "_toolpath_bounds_source", None) is points:
            return getattr(self, "_toolpath_bounds_cache", None)
        bounds = _render_point_bounds(points)
        self._toolpath_bounds_source = points
        self._toolpath_bounds_cache = bounds
        return bounds

    def _scene_bounds(self):
        if getattr(self, "_stock_animation_active", False) and hasattr(self, "stockFitBounds"):
            return self.stockFitBounds()
        toolpath_bounds = self._cached_toolpath_bounds()
        stock_bounds = self.stockFitBounds() if hasattr(self, "stockFitBounds") else None
        stl_bounds = [entry.overlay.bounds for entry in getattr(self, "_stl_entries", ())]
        bounds = [item for item in (toolpath_bounds, stock_bounds, *stl_bounds) if item is not None]
        if not bounds:
            return None
        return tuple(
            (min(item[axis][0] for item in bounds), max(item[axis][1] for item in bounds)) for axis in range(3)
        )

    def _should_auto_fit_milling(self, previous_bounds, points):
        """Fit only when a newly pasted 3D path has outgrown the current view."""
        if self.latheMode or getattr(self, "_view_mode", "3d") != "3d" or not points:
            return False
        view = self.ui.graphicsView
        bounds = _render_point_bounds(points)
        if bounds is None:
            return False
        spans = [high - low for low, high in bounds]
        if previous_bounds is not None:
            old_spans = [high - low for low, high in previous_bounds]
            old_size = max(*old_spans, 1.0)
            new_size = max(spans)
            center_shift = max(
                abs((low + high - old_low - old_high) / 2.0)
                for (low, high), (old_low, old_high) in zip(bounds, previous_bounds)
            )
            if new_size < old_size * 3.0 and center_shift < old_size * 2.0:
                return False

        return _bounds_exceed_milling_camera(view, bounds)

    def fitToView(self):
        """Center and fit the complete rendered toolpath and STL in the active projection."""
        started = perf_counter()
        bounds = self._scene_bounds()
        if bounds is None:
            # A turning stock fit can leave the camera centered far from the
            # machine origin. When switching to an empty milling scene there
            # are no bounds to replace that center, so restore world zero.
            if not self.latheMode:
                self.ui.graphicsView.opts["center"] = QVector3D(0.0, 0.0, 0.0)
            self._update_adaptive_grid()
            LOGGER.debug("fit_view skipped_no_bounds duration_ms=%.3f", (perf_counter() - started) * 1000.0)
            return

        spans = tuple(high - low for low, high in bounds)
        center = QVector3D(*(low + span / 2.0 for (low, _high), span in zip(bounds, spans)))
        mode = "lathe" if self.latheMode else getattr(self, "_view_mode", "3d")

        view = self.ui.graphicsView
        view.opts["center"] = center
        aspect = max(float(view.width()), 1.0) / max(float(view.height()), 1.0)
        half_fov = math.radians(max(float(view.opts.get("fov", 60.0)), 0.01) / 2.0)

        if mode == "lathe":
            # Keep the established turning fit behavior independent from milling views.
            half_extent = max(spans[2] / 2.0, spans[0] * aspect / 2.0)
            half_extent = max(half_extent, 0.5)
            distance = half_extent * 1.1 / math.tan(half_fov)
        else:
            matrix = view.viewMatrix()
            corners = [matrix * QVector4D(x, y, z, 1.0) for x in bounds[0] for y in bounds[1] for z in bounds[2]]
            view_center = matrix * QVector4D(center, 1.0)

            if view.isOrthographic():
                half_width = (
                    max(
                        max(abs(corner.x() - view_center.x()), abs(corner.y() - view_center.y()) * aspect, 0.5)
                        for corner in corners
                    )
                    / 0.9
                )
                diagonal = max(math.sqrt(sum(span * span for span in spans)), 1.0)
                depths = [corner.z() - view_center.z() for corner in corners]
                origin = matrix * QVector4D(0.0, 0.0, 0.0, 1.0)
                depths.append(origin.z() - view_center.z())
                margin = max(diagonal * 0.05, 1.0)
                max_depth = max(depths)
                min_depth = min(depths)
                distance = max(max_depth + margin, margin)
                near_clip = max(distance - max_depth, 1e-3)
                far_clip = max(distance - min_depth + margin, near_clip + 1.0)
                view.setOrthographicProjection(2.0 * half_width, near_clip, far_clip)
            else:
                # GLViewWidget's fov is horizontal, so vertical view-space extent
                # must be multiplied by width/height when converted to distance.
                tangent = math.tan(half_fov)
                distance = max(
                    max(abs(corner.x() - view_center.x()), abs(corner.y() - view_center.y()) * aspect, 0.5)
                    / (0.9 * tangent)
                    + (corner.z() - view_center.z())
                    for corner in corners
                )

        view.setCameraPosition(distance=distance)
        self.dist = distance
        self._update_adaptive_grid()
        toolpath_item = getattr(self, "_toolpath_item", None)
        if toolpath_item is not None:
            toolpath_item.update_dashes_for_view()
        LOGGER.debug(
            "fit_view duration_ms=%.3f mode=%s distance=%.3f bounds=%s",
            (perf_counter() - started) * 1000.0,
            mode,
            distance,
            bounds,
        )

    def _create_trace_items(self):
        """Attach the persistent VBO toolpath and lightweight cursor overlay."""
        if getattr(self, "_stock_animation_active", False):
            self._load_stock_animation_plot()
            return
        width = getattr(self, "plotLineWidth", 1.5)
        toolpath_item = getattr(self, "_toolpath_item", None)
        execution_result = getattr(self, "execution_result", None)
        if toolpath_item is None and execution_result is not None:
            toolpath_item = ToolpathVboItem()
            toolpath_item.set_segments(
                segments_from_render_points(
                    self.render_points,
                    execution_result.motions,
                    getattr(self, "_motion_to_playback", None),
                    lathe_radius_view=getattr(self, "latheMode", False),
                ),
                len(getattr(self, "_playback_movements", execution_result.motions)),
            )
            self._toolpath_item = toolpath_item
        if toolpath_item is not None:
            toolpath_item.set_style(
                rapid_color=getattr(self, "plotRapidColor", RAPID_COLOR),
                linear_color=self.plotLineColor,
                arc_color=getattr(self, "plotArcColor", "#008000"),
                width=width,
                show_rapid=getattr(self, "plotShowRapid", True),
                dashed_rapid=getattr(self, "plotDashedRapid", True),
                color_by_tool=getattr(self, "plotColorByTool", False),
            )
            if toolpath_item not in self.ui.graphicsView.items:
                self.ui.graphicsView.addItem(toolpath_item)
            toolpath_item.update_dashes_for_view()

        if getattr(self, "_cursor_item", None) is None:
            self._cursor_item = GLScatterPlotItem(
                pos=[],
                color=QColor(getattr(self, "plotCurrentColor", self.plotLineColor)),
                size=CURSOR_SIZE_PX,
                pxMode=True,
            )
            self._cursor_item.setGLOptions("translucent")
        if self._cursor_item not in self.ui.graphicsView.items:
            self.ui.graphicsView.addItem(self._cursor_item)

        if getattr(self, "_milling_tool_item", None) is None:
            self._milling_tool_item = MillingToolPreviewItem(getattr(self, "plotToolColor", "#4d99ff"))
        self._milling_tool_item.set_color(getattr(self, "plotToolColor", "#4d99ff"))
        if self._milling_tool_item not in self.ui.graphicsView.items:
            self.ui.graphicsView.addItem(self._milling_tool_item)
        if hasattr(self, "_update_stock_outline"):
            self._update_stock_outline()

    def _set_trace_geometry(self):
        """Pack new trace geometry once; GPU upload remains paint-lazy."""
        started = perf_counter()
        if getattr(self, "_toolpath_item", None) is None:
            self._toolpath_item = ToolpathVboItem()
        result = self.execution_result
        motions = result.motions if result is not None else ()
        self._toolpath_item.set_segments(
            segments := segments_from_render_points(
                self.render_points, motions, lathe_radius_view=getattr(self, "latheMode", False)
            ),
            len(motions),
        )
        LOGGER.debug(
            "toolpath_geometry_packed duration_ms=%.3f motions=%d render_points=%d segments=%d",
            (perf_counter() - started) * 1000.0,
            len(motions),
            len(self.render_points),
            len(segments),
        )

    def _dispose_trace_item(self):
        """Release trajectory buffers before the owning GL view disappears."""
        toolpath_item = getattr(self, "_toolpath_item", None)
        if toolpath_item is not None:
            toolpath_item.dispose()
        self._toolpath_item = None

    def _project_world_to_screen(self, x, y, z):
        """Project one world point to GLViewWidget pixel coordinates."""
        view = self.ui.graphicsView
        viewport = view.getViewport()
        try:
            projection = view.projectionMatrix(viewport, viewport)
        except TypeError:  # pyqtgraph < 0.14 compatibility
            projection = view.projectionMatrix(viewport)  # pylint: disable=no-value-for-parameter
        clip = projection * view.viewMatrix() * QVector4D(float(x), float(y), float(z), 1.0)
        w = clip.w()
        if abs(w) < 1e-12:
            return None
        ndc_x = clip.x() / w
        ndc_y = clip.y() / w
        vx, vy, vw, vh = viewport
        return (
            vx + (ndc_x + 1.0) * 0.5 * vw,
            vy + (1.0 - (ndc_y + 1.0) * 0.5) * vh,
        )

    def _pick_trace_at(self, position):
        """Select the nearest trajectory segment on Shift+Click in a 2D view."""
        bbox_picker = getattr(self, "_pick_stl_bbox_point", None)
        if bbox_picker is not None and bbox_picker(position):
            return True
        if getattr(self, "_stock_animation_active", False):
            return False
        view_mode = "lathe" if self.latheMode else getattr(self, "_view_mode", "3d")
        if view_mode not in {"lathe", "top", "front", "left"} or not self.render_points:
            return False

        px = float(position.x())
        py = float(position.y())
        best_distance = PICK_DISTANCE_PX
        best_motion = None
        projected_previous = self._project_world_to_screen(
            self.render_points[0].x, self.render_points[0].y, self.render_points[0].z
        )
        for current in self.render_points[1:]:
            projected_current = self._project_world_to_screen(current.x, current.y, current.z)
            if projected_previous is not None and projected_current is not None:
                distance = _point_segment_distance(
                    px, py, projected_previous[0], projected_previous[1], projected_current[0], projected_current[1]
                )
                if distance <= best_distance:
                    best_distance = distance
                    best_motion = current.motion_index
            projected_previous = projected_current

        result = self.execution_result
        if result is None or best_motion is None or not 0 <= best_motion < len(result.motions):
            return False
        motion_to_playback = getattr(self, "_motion_to_playback", tuple(range(len(result.motions))))
        target = motion_to_playback[best_motion] + 1
        current_value = self.ui.horizontalSlider.value() if hasattr(self.ui.horizontalSlider, "value") else None
        if current_value == target:
            self._sync_editor_to_motion(best_motion)
        else:
            self.ui.horizontalSlider.setValue(target)
        source_block = result.motions[best_motion].source_block
        if source_block is not None:
            self.ui.statusbar.showMessage(
                f"Trajectory source: line {source_block + 1}, motion {best_motion + 1} (Shift+Click)", 5000
            )
        return True

    def _sync_editor_to_motion(self, idx):
        result = self.execution_result
        if result is None or not 0 <= idx < len(result.motions):
            return
        block = result.motions[idx].source_block
        if block is None or block < 0 or block >= self.ui.editor.lines():
            return
        if self.ui.editor.getCursorPosition()[0] == block:
            return
        self._syncing_cursor = True
        try:
            with QSignalBlocker(self.ui.editor):
                self.ui.editor.setCursorPosition(block, 0)
            if hasattr(self, "updateStatusBar"):
                self.updateStatusBar()
        finally:
            self._syncing_cursor = False

    def clearPlot(self):
        """Reset authoritative execution and render/playback state."""
        if hasattr(self, "_clear_stock_animation"):
            self._clear_stock_animation()
        if hasattr(self, "_clear_stock_outline"):
            self._clear_stock_outline()
        self._stock_auto_suggestion = None
        self._dispose_trace_item()
        self.execution_result = None
        self._deferred_execution_result = None
        self._deferred_execution_source = None
        self.render_points = []
        self._motion_render_end = []
        self._playback_movements = ()
        self._playback_at_program_end = False
        self._motion_to_playback = ()
        self._source_motion_index = {}
        self._syncing_cursor = False
        self._fit_view_after_program_load = False
        self._drawing_item = None
        self._arc_item = None
        self._rapid_item = None
        self._cursor_item = None
        if getattr(self, "_milling_tool_item", None) is not None:
            self._milling_tool_item.hide_tool()
        self._lathe_grid_item = None
        self._lathe_grid_center = (0.0, 0.0)
        self._milling_grid_item = None
        self._milling_grid_center = (0.0, 0.0, 0.0)
        self._toolpath_bounds_source = self.render_points
        self._toolpath_bounds_cache = None
        self.timer.stop()
        self.step = 0
        for widget in (
            self.ui.lineEditX,
            self.ui.lineEditY,
            self.ui.lineEditZ,
            self.ui.lineEdit_I,
            self.ui.lineEdit_J,
            self.ui.lineEdit_K,
            self.ui.lineEditFeed,
        ):
            widget.clear()
        self.ui.horizontalSlider.setMinimum(0)
        self.ui.horizontalSlider.setMaximum(0)
        self.ui.horizontalSlider.setValue(0)
        self.ui.actionStep_Backward.setEnabled(False)
        self.ui.actionStep_Forward.setEnabled(False)
        self.ui.actionPlay.setChecked(False)
        self.ui.actionPlay.setEnabled(False)
        self.ui.actionStop.setEnabled(False)
        self.loadPlot()

    def valueHandler(self, value, *, sync_editor=True):
        """Display one logical motion and optionally synchronize the editor cursor."""
        result = self.execution_result
        if result is None or not result.motions:
            return
        if value <= 0:
            motion = result.motions[0]
            unit_scale = self._motion_unit_scales[0] if getattr(self, "_motion_unit_scales", ()) else 1.0
            self.ui.lineEditX.setText(_display_value(motion.start_x, unit_scale))
            self.ui.lineEditY.setText(_display_value(motion.start_y, unit_scale))
            self.ui.lineEditZ.setText(_display_value(motion.start_z, unit_scale))
            for widget in (self.ui.lineEdit_I, self.ui.lineEdit_J, self.ui.lineEdit_K, self.ui.lineEditFeed):
                widget.clear()
            if getattr(self, "_stock_animation_active", False):
                self._update_stock_animation_frame(0)
                return
            if getattr(self, "_toolpath_item", None) is None or self._cursor_item is None:
                self._create_trace_items()
            self._toolpath_item.set_visible_logical_count(0)
            self._cursor_item.setData(
                pos=[(motion.start_x, motion.start_y, motion.start_z)],
                color=QColor(self.plotCurrentColor),
                size=CURSOR_SIZE_PX,
                pxMode=True,
            )
            tool_item = getattr(self, "_milling_tool_item", None)
            if tool_item is not None:
                tool_item.hide_tool()
            return
        playback_index = max(0, min(len(self._playback_movements) - 1, value - 1))
        playback = self._playback_movements[playback_index]
        idx = playback.motion_end - 1
        motion = result.motions[idx]
        scales = getattr(self, "_motion_unit_scales", ())
        unit_scale = scales[idx] if idx < len(scales) else 1.0
        self.ui.lineEditX.setText(_display_value(motion.end_x, unit_scale))
        self.ui.lineEditY.setText(_display_value(motion.end_y, unit_scale))
        self.ui.lineEditZ.setText(_display_value(motion.end_z, unit_scale))
        i_value, k_value = _lathe_arc_offsets(motion) if self.latheMode else (motion.i, motion.k)
        self.ui.lineEdit_I.setText("" if i_value is None else _display_value(i_value, unit_scale))
        self.ui.lineEdit_J.setText("" if motion.j is None else _display_value(motion.j, unit_scale))
        self.ui.lineEdit_K.setText("" if k_value is None else _display_value(k_value, unit_scale))
        self.ui.lineEditFeed.setText(
            "Rapid" if motion.move == 0 else ("" if motion.feed is None else _display_value(motion.feed, unit_scale))
        )
        if getattr(self, "_stock_animation_active", False):
            self._update_stock_animation_frame(value)
            if sync_editor:
                self._sync_editor_to_motion(idx)
            return
        if getattr(self, "_toolpath_item", None) is None or self._cursor_item is None:
            self._create_trace_items()
        self._toolpath_item.set_visible_logical_count(idx + 1)
        end = self._motion_render_end[idx] if idx < len(self._motion_render_end) else len(self.render_points)
        if end > 0:
            point = self.render_points[min(end, len(self.render_points)) - 1]
            self._cursor_item.setData(
                pos=[(point.x, point.y, point.z)],
                color=QColor(self.plotCurrentColor),
                size=CURSOR_SIZE_PX,
                pxMode=True,
            )
        tool_item = getattr(self, "_milling_tool_item", None)
        if tool_item is not None:
            if self.latheMode:
                tool_item.hide_tool()
            else:
                tool_item.show_tool(
                    getattr(self, "millingTools", {}).get(motion.tool, DEFAULT_MILLING_TOOL),
                    (motion.end_x, motion.end_y, motion.end_z),
                    motion.tool_orientation,
                )
        if sync_editor:
            self._sync_editor_to_motion(idx)

    def loadPlot(self):
        """Redraw axes, background, and the active orthographic grid."""
        started = perf_counter()
        if getattr(self, "_stock_animation_active", False):
            self._load_stock_animation_plot()
            LOGGER.debug("plot_scene_loaded stock_animation=true duration_ms=%.3f", (perf_counter() - started) * 1000.0)
            return
        self.ui.graphicsView.clear()
        self._cursor_item = None
        self._lathe_grid_item = None
        self._lathe_grid_center = (0.0, 0.0)
        self._milling_grid_item = None
        self._milling_grid_center = (0.0, 0.0, 0.0)
        self.ui.graphicsView.setBackgroundGradient(
            getattr(self, "plotBackgroundGradient", False),
            self.plotBackground,
        )
        if self.plotGrid:
            if self.latheMode:
                self._lathe_grid_item = GLGridItem()
                self._lathe_grid_item.lineplot.setGLOptions(GRID_GL_OPTIONS)
                self._lathe_grid_item.setColor(QColor(self.plotGridColor))
                self._lathe_grid_item.rotate(90, 1, 0, 0)
                self.ui.graphicsView.addItem(self._lathe_grid_item)
            else:
                self._milling_grid_item = GLGridItem()
                self._milling_grid_item.lineplot.setGLOptions(GRID_GL_OPTIONS)
                self._milling_grid_item.setColor(QColor(self.plotGridColor))
                self._orient_milling_grid()
                self.ui.graphicsView.addItem(self._milling_grid_item)
            self._update_adaptive_grid()

        if self.plotAxes:
            if getattr(self, "_axis_triad_item", None) is None:
                self._axis_triad_item = AxisTriadItem()
            self.ui.graphicsView.addItem(self._axis_triad_item)

        stl_entries = getattr(self, "_stl_entries", ())
        for entry in stl_entries:
            if entry.overlay.item is not None:
                self.ui.graphicsView.addItem(entry.overlay.item)
        section_item = getattr(self, "_stl_section_item", None)
        if section_item is not None:
            self.ui.graphicsView.addItem(section_item)
        self._restore_selected_stl_overlays(stl_entries)
        if hasattr(self, "_update_stock_outline"):
            self._update_stock_outline()
        LOGGER.debug(
            "plot_scene_loaded stock_animation=false duration_ms=%.3f lathe=%s grid=%s axes=%s stl=%d items=%d",
            (perf_counter() - started) * 1000.0,
            self.latheMode,
            self.plotGrid,
            self.plotAxes,
            len(stl_entries),
            len(self.ui.graphicsView.items),
        )

    def _restore_selected_stl_overlays(self, stl_entries):
        if not hasattr(self, "stlObjectsDock"):
            return
        row = self.stlObjectsDock.objectList.currentRow()
        if 0 <= row < len(stl_entries):
            self._update_stl_pivot_marker(stl_entries[row].obj.world_pivot())
            self._update_stl_bbox_overlay(row)

    def _adaptive_grid_size(self):
        view = self.ui.graphicsView
        if view.isOrthographic():
            viewport_width = max(float(view.width()), 1.0)
            viewport_height = max(float(view.height()), 1.0)
            visible_height = view.orthographicWidth() * viewport_height / viewport_width
            fov = 60.0
            distance = visible_height / (2.0 * math.tan(math.radians(fov) * 0.5))
            return adaptive_grid_geometry(distance, fov, view.height(), viewport_width=view.width())
        return adaptive_grid_geometry(
            view.opts["distance"], view.opts["fov"], view.height(), viewport_width=view.width()
        )

    def _update_adaptive_grid(self):
        """Update the active 2D/orthographic grid after zoom, pan, or resize."""
        axis_triad = getattr(self, "_axis_triad_item", None)
        if axis_triad is not None:
            axis_triad.sync_screen_size()
        if self.latheMode:
            self._update_lathe_grid()
        else:
            self._update_milling_grid()

    def _update_lathe_grid(self):
        """Adapt the single XZ lathe grid to the current camera zoom."""
        grid = getattr(self, "_lathe_grid_item", None)
        if grid is None or not self.latheMode or not self.plotGrid:
            return
        spacing, size = self._adaptive_grid_size()
        if self.plotGridStep > 0:
            spacing = self.plotGridStep
        grid.setSize(size, size)
        grid.setSpacing(spacing, spacing)
        center = self.ui.graphicsView.opts["center"]
        snapped_x = round(center.x() / spacing) * spacing
        snapped_z = round(center.z() / spacing) * spacing
        old_x, old_z = getattr(self, "_lathe_grid_center", (0.0, 0.0))
        grid.translate(snapped_x - old_x, 0.0, snapped_z - old_z)
        self._lathe_grid_center = (snapped_x, snapped_z)

    def _orient_milling_grid(self):
        """Rotate the existing milling grid for the active view without rebuilding the scene."""
        grid = getattr(self, "_milling_grid_item", None)
        if grid is None:
            return
        grid.resetTransform()
        view_mode = getattr(self, "_view_mode", "3d")
        if view_mode == "front":
            grid.rotate(90, 1, 0, 0)
        elif view_mode == "left":
            grid.rotate(90, 0, 1, 0)
        self._milling_grid_center = (0.0, 0.0, 0.0)

    def _update_milling_grid(self):
        """Adapt the active milling grid in Top, Front, and Left views only."""
        grid = getattr(self, "_milling_grid_item", None)
        view_mode = getattr(self, "_view_mode", "3d")
        if grid is None or self.latheMode or not self.plotGrid:
            return

        spacing, size = self._adaptive_grid_size()
        if self.plotGridStep > 0:
            spacing = self.plotGridStep
        grid.setSize(size, size)
        grid.setSpacing(spacing, spacing)
        center = self.ui.graphicsView.opts["center"]
        if view_mode == "top":
            snapped = (round(center.x() / spacing) * spacing, round(center.y() / spacing) * spacing, 0.0)
        elif view_mode == "front":
            snapped = (round(center.x() / spacing) * spacing, 0.0, round(center.z() / spacing) * spacing)
        elif view_mode == "left":
            snapped = (0.0, round(center.y() / spacing) * spacing, round(center.z() / spacing) * spacing)
        else:
            snapped = (round(center.x() / spacing) * spacing, round(center.y() / spacing) * spacing, 0.0)

        old = getattr(self, "_milling_grid_center", (0.0, 0.0, 0.0))
        grid.translate(snapped[0] - old[0], snapped[1] - old[1], snapped[2] - old[2])
        self._milling_grid_center = snapped

    def plotCurLine(self):
        """Map a user-selected source line to playback when playback is idle."""
        # Playback/trackbar state is authoritative while Play is running.  Macro
        # expansion can revisit the same source lines many times; letting those
        # cursor updates drive the slider would jump back to the first occurrence
        # and can trap playback in a short loop.
        if self._syncing_cursor or getattr(self, "_plot_source_stale", False) or self.ui.actionPlay.isChecked():
            return
        line = self.ui.editor.getCursorPosition()[0]

        # Playback controls and the trackbar are authoritative.  Macro expansion
        # can produce many motions from the same source line; after a Step or
        # slider move, the programmatic editor cursor update may arrive after the
        # slider has already advanced.  If the editor already points at the source
        # line represented by the current playback frame, do not remap that line
        # back to its first expanded occurrence.
        value = self.ui.horizontalSlider.value()
        movements = getattr(self, "_playback_movements", ())
        result = self.execution_result
        if result is not None and 0 < value <= len(movements):
            current = movements[value - 1]
            motion_index = current.motion_end - 1
            if 0 <= motion_index < len(result.motions) and result.motions[motion_index].source_block == line:
                return

        idx = self._source_motion_index.get(line)
        if idx is not None:
            self.ui.horizontalSlider.setValue(idx + 1)

    def setView(self, fov, elevation, azimuth, use_calc_dist=True, dist_scale=6000):
        """Set camera view with optional distance recalculation."""
        if use_calc_dist:
            self.calcDist()
            bounds = self._cached_toolpath_bounds()
            if bounds is not None:
                self.ui.graphicsView.opts["center"] = QVector3D(*(low + (high - low) / 2.0 for low, high in bounds))
            dist = self.dist * dist_scale
        else:
            dist = 1.0
        self.ui.graphicsView.opts["fov"] = fov
        self.ui.graphicsView.setCameraPosition(distance=dist, elevation=elevation, azimuth=azimuth)

    def refreshPlotView(self):
        """Redraw scene items after user-facing visual options change."""
        started = perf_counter()
        self.loadPlot()
        self._create_trace_items()
        if self.execution_result is not None and self.execution_result.motions:
            self.valueHandler(self.ui.horizontalSlider.value(), sync_editor=False)
        LOGGER.info(
            "plot_visual_options_refreshed duration_ms=%.3f items=%d",
            (perf_counter() - started) * 1000.0,
            len(self.ui.graphicsView.items),
        )

    def _finish_camera_change(self):
        """Fit the new camera and reorient only the existing grid."""
        self._orient_milling_grid()
        self.fitToView()

    def _orthographic_orbit_started(self):
        """Mark a rotated fixed milling view as freely rotatable orthographic 3D."""
        if self.latheMode or getattr(self, "_view_mode", "3d") == "3d":
            return
        self._view_mode = "3d"
        self.ui.actionGrid.setEnabled(True)
        self._orient_milling_grid()
        self.fitToView()

    def view3d(self):
        """Set the standard CAD angle with a parallel 3D projection."""
        self._view_mode = "3d"
        self.ui.actionGrid.setEnabled(True)
        view = self.ui.graphicsView
        view.setProjectionMode("orthographic")
        if getattr(self, "rotaryKinematics", None) == "4ax_table_b":
            # Horizontal mill: +Y is screen-up; +X and +Z run to the right
            # on opposite diagonals. Only the camera changes; WCS stays fixed.
            view.opts["rotationMethod"] = "quaternion"
            basis = QMatrix4x4()
            basis.lookAt(QVector3D(-1, 1, 1), QVector3D(0, 0, 0), QVector3D(0, 1, 0))
            rotation = QQuaternion.fromRotationMatrix(basis.normalMatrix())
            view.opts["fov"] = 60
            view.setCameraPosition(distance=1.0, rotation=rotation)
        else:
            view.opts["rotationMethod"] = "euler"
            self.setView(60, 30, -45, use_calc_dist=False, dist_scale=1)
        self._finish_camera_change()
        LOGGER.info("plot_view_changed mode=3d")

    def viewTop(self):
        """Switch camera to a true top-down orthographic view."""
        self._view_mode = "top"
        self.ui.actionGrid.setEnabled(True)
        self.ui.graphicsView.opts["rotationMethod"] = "euler"
        self.ui.graphicsView.setProjectionMode("orthographic")
        self.setView(60, 90, -90, use_calc_dist=False)
        self._finish_camera_change()
        LOGGER.info("plot_view_changed mode=top")

    def viewFront(self):
        """Switch camera to a true front orthographic view."""
        self._view_mode = "front"
        self.ui.actionGrid.setEnabled(True)
        self.ui.graphicsView.opts["rotationMethod"] = "euler"
        self.ui.graphicsView.setProjectionMode("orthographic")
        self.setView(60, 0, -90, use_calc_dist=False)
        self._finish_camera_change()
        LOGGER.info("plot_view_changed mode=front")

    def viewLeft(self):
        """Switch camera to a true left orthographic view."""
        self._view_mode = "left"
        self.ui.actionGrid.setEnabled(True)
        self.ui.graphicsView.opts["rotationMethod"] = "euler"
        self.ui.graphicsView.setProjectionMode("orthographic")
        self.setView(60, 0, 180, use_calc_dist=False)
        self._finish_camera_change()
        LOGGER.info("plot_view_changed mode=left")

    def calcDist(self):
        """Calculate fit distance without moving the current camera center."""
        bounds = self._cached_toolpath_bounds()
        if bounds is None:
            return
        spans = tuple(high - low for low, high in bounds)
        diagonal = math.sqrt(sum(span * span for span in spans))
        self.dist = diagonal + diagonal * 0.5
