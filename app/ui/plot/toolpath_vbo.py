"""VBO-backed toolpath item for the existing pyqtgraph OpenGL scene."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from math import hypot, isfinite

import numpy as np
from OpenGL import GL
from PyQt6 import QtGui
from PyQt6.QtGui import QColor, QVector4D
from pyqtgraph.opengl import GLLinePlotItem
from pyqtgraph.opengl.items.GLLinePlotItem import DirtyFlag

TOOLPATH_GL_OPTIONS = {
    GL.GL_DEPTH_TEST: True,
    GL.GL_BLEND: True,
    GL.GL_CULL_FACE: False,
    "glDepthFunc": (GL.GL_LEQUAL,),
    "glDepthMask": (False,),
    "glBlendFuncSeparate": (
        GL.GL_SRC_ALPHA,
        GL.GL_ONE_MINUS_SRC_ALPHA,
        GL.GL_ONE,
        GL.GL_ONE_MINUS_SRC_ALPHA,
    ),
}

DASH_ON_PX = 3.0
DASH_GAP_PX = 2.0


@lru_cache(maxsize=512)
def tool_color(tool: str | None) -> str | None:
    """Choose a stable, readable color from the programmed tool identifier."""
    if not tool:
        return None
    value = 2166136261
    for char in str(tool):
        value = ((value ^ ord(char)) * 16777619) & 0xFFFFFFFF
    value ^= value >> 16
    value = (value * 0x7FEB352D) & 0xFFFFFFFF
    value ^= value >> 15
    value = (value * 0x846CA68B) & 0xFFFFFFFF
    value ^= value >> 16
    hue = value % 360
    saturation = 170 + (value // 360) % 60
    brightness = 170 + (value // 21600) % 65
    return QColor.fromHsv(hue, saturation, brightness).name()


def dashed_rapid_segments(segment, matrix, viewport):
    """Split a rapid line into the same short screen-sized dashes as Print."""
    start = matrix * QVector4D(*segment.start, 1.0)
    end = matrix * QVector4D(*segment.end, 1.0)
    if abs(start.w()) < 1e-9 or abs(end.w()) < 1e-9 or start.w() * end.w() <= 0:
        return (segment,)
    pixels = hypot(
        (end.x() / end.w() - start.x() / start.w()) * viewport[0] / 2,
        (end.y() / end.w() - start.y() / start.w()) * viewport[1] / 2,
    )
    if not isfinite(pixels) or pixels <= DASH_ON_PX:
        return (segment,)
    pieces = []
    step = max(DASH_ON_PX + DASH_GAP_PX, pixels / 2048)
    for index in range(int(pixels / step) + 1):
        begin = index * step / pixels
        if begin >= 1:
            break
        finish = min((index * step + step * DASH_ON_PX / (DASH_ON_PX + DASH_GAP_PX)) / pixels, 1.0)
        begin = begin * start.w() / ((1 - begin) * end.w() + begin * start.w())
        finish = finish * start.w() / ((1 - finish) * end.w() + finish * start.w())
        point_a = tuple(a + (b - a) * begin for a, b in zip(segment.start, segment.end))
        point_b = tuple(a + (b - a) * finish for a, b in zip(segment.start, segment.end))
        pieces.append(ToolpathSegment(point_a, point_b, segment.logical_index, 0, segment.tool))
    return tuple(pieces)


@dataclass(frozen=True)
class ToolpathSegment:
    """One independently rendered segment owned by a logical kernel motion."""

    start: tuple[float, float, float]
    end: tuple[float, float, float]
    logical_index: int
    move: int
    tool: str | None = None


def segments_from_render_points(
    render_points, motions, motion_to_playback=None, *, lathe_radius_view=False
) -> tuple[ToolpathSegment, ...]:
    """Convert the sampled trace to ordered ``GL_LINES`` segment pairs."""
    segments: list[ToolpathSegment] = []
    for previous, current in zip(render_points, render_points[1:]):
        motion_index = current.motion_index
        if not 0 <= motion_index < len(motions):
            continue
        motion = motions[motion_index]
        if previous.motion_index != motion_index:
            # Indexing can move the tool tip between two linear trace motions.
            # Start the new segment at its own resolved start, not at the old end.
            start = (motion.start_x * (0.5 if lathe_radius_view else 1.0), motion.start_y, motion.start_z)
        else:
            start = (previous.x, previous.y, previous.z)
        end = (current.x, current.y, current.z)
        if start == end:
            continue
        logical_index = motion_index if motion_to_playback is None else motion_to_playback[motion_index]
        segments.append(
            ToolpathSegment(
                start,
                end,
                logical_index,
                motion.move,
                motion.tool,
            )
        )
    return tuple(segments)


def _rgba(value) -> tuple[float, float, float, float]:
    color = QColor(value)
    return tuple(float(channel) for channel in color.getRgbF())


class ToolpathVboItem(GLLinePlotItem):
    """A pyqtgraph scene item that keeps the complete toolpath in two VBOs.

    Geometry is packed as independent vertex pairs and uploaded only when
    ``set_segments`` changes it. Playback changes only the draw vertex count.
    """

    def __init__(self):
        self.source_segments: tuple[ToolpathSegment, ...] = ()
        self.segments: tuple[ToolpathSegment, ...] = ()
        self.logical_to_exclusive_segment = np.zeros(1, dtype=np.int32)
        self.packed_vertices = np.empty((0, 3), dtype=np.float32)
        self.packed_colors = np.empty((0, 4), dtype=np.float32)
        self.visible_logical_count = 0
        self.visible_segment_count = 0
        self._rapid_color = _rgba("#d02020")
        self._linear_color = _rgba("#0000ff")
        self._arc_color = _rgba("#008000")
        self.show_rapid = True
        self.dashed_rapid = False
        self.color_by_tool = False
        self._dash_signature = None
        self._gl_context = None
        super().__init__(
            pos=self.packed_vertices,
            color=self.packed_colors,
            width=1.5,
            antialias=True,
            mode="lines",
            glOptions=TOOLPATH_GL_OPTIONS,
        )

    @property
    def logical_count(self) -> int:
        return len(self.logical_to_exclusive_segment) - 1

    @property
    def visible_vertex_count(self) -> int:
        return self.visible_segment_count * 2

    def set_segments(self, segments, logical_count: int) -> None:
        """Pack a complete sampled toolpath and mark both GPU buffers dirty."""
        self.source_segments = tuple(segments)
        self._dash_signature = None
        self._repack(logical_count)

    def _repack(self, logical_count: int, matrix=None, viewport=None) -> None:
        """Apply display options while retaining the complete source path."""
        source = self.source_segments
        displayed = []
        for segment in source:
            if segment.move != 0:
                displayed.append(segment)
            elif self.show_rapid:
                if not self.dashed_rapid or matrix is None or viewport is None:
                    displayed.append(segment)
                else:
                    displayed.extend(dashed_rapid_segments(segment, matrix, viewport))
        self.segments = tuple(displayed)
        segment_count = len(self.segments)
        vertices = np.empty((segment_count * 2, 3), dtype=np.float32)
        for index, segment in enumerate(self.segments):
            vertices[index * 2] = segment.start
            vertices[index * 2 + 1] = segment.end
        self.packed_vertices = np.ascontiguousarray(vertices, dtype=np.float32)

        logical_count = max(0, int(logical_count))
        mapping = np.zeros(logical_count + 1, dtype=np.int32)
        segment_index = 0
        for logical_index in range(logical_count):
            while segment_index < segment_count and self.segments[segment_index].logical_index <= logical_index:
                segment_index += 1
            mapping[logical_index + 1] = segment_index
        self.logical_to_exclusive_segment = mapping
        self.packed_colors = self._packed_segment_colors()
        super().setData(pos=self.packed_vertices, color=self.packed_colors)
        self.set_visible_logical_count(logical_count)

    def set_style(
        self,
        *,
        rapid_color,
        linear_color,
        arc_color,
        width: float,
        show_rapid=True,
        dashed_rapid=False,
        color_by_tool=False,
    ) -> None:
        """Update only the color VBO when trajectory colors change."""
        colors = (_rgba(rapid_color), _rgba(linear_color), _rgba(arc_color))
        old_colors = (self._rapid_color, self._linear_color, self._arc_color)
        self.width = float(width)
        geometry_changed = (self.show_rapid, self.dashed_rapid) != (show_rapid, dashed_rapid)
        self.show_rapid = show_rapid
        self.dashed_rapid = dashed_rapid
        old_color_by_tool = self.color_by_tool
        self.color_by_tool = color_by_tool
        self._rapid_color, self._linear_color, self._arc_color = colors
        if geometry_changed:
            self._dash_signature = None
            visible = self.visible_logical_count
            self._repack(self.logical_count)
            self.set_visible_logical_count(visible)
            return
        if colors != old_colors or color_by_tool != old_color_by_tool:
            self.packed_colors = self._packed_segment_colors()
            super().setData(color=self.packed_colors)
        else:
            self.update()

    def set_visible_logical_count(self, logical_count: int) -> None:
        """Reveal a logical prefix without slicing or uploading VBO data."""
        clamped = max(0, min(int(logical_count), self.logical_count))
        self.visible_logical_count = clamped
        self.visible_segment_count = int(self.logical_to_exclusive_segment[clamped])
        self.update()

    def update_dashes_for_view(self) -> None:
        """Pack screen-sized dashes at an explicit view change, never during paint."""
        view = self.view()
        if not (self.dashed_rapid and self.show_rapid) or view is None:
            return
        viewport = (max(view.width(), 1), max(view.height(), 1))
        region = view.getViewport()
        matrix = view.projectionMatrix(region, region) * view.viewMatrix()
        signature = (tuple(matrix.data()), viewport)
        if signature == self._dash_signature:
            return
        visible = self.visible_logical_count
        self._repack(self.logical_count, matrix, viewport)
        self.set_visible_logical_count(visible)
        self._dash_signature = signature

    def segment_range_for_logical(self, logical_index: int) -> tuple[int, int]:
        """Return the CPU metadata range used by picking/selection overlays."""
        if not 0 <= logical_index < self.logical_count:
            return (0, 0)
        return (
            int(self.logical_to_exclusive_segment[logical_index]),
            int(self.logical_to_exclusive_segment[logical_index + 1]),
        )

    def _packed_segment_colors(self) -> np.ndarray:
        colors = np.empty((len(self.segments) * 2, 4), dtype=np.float32)
        for index, segment in enumerate(self.segments):
            assigned_color = tool_color(segment.tool) if self.color_by_tool else None
            color = (
                _rgba(assigned_color)
                if assigned_color
                else self._rapid_color
                if segment.move == 0
                else self._arc_color
                if segment.move in (2, 3)
                else self._linear_color
            )
            colors[index * 2] = color
            colors[index * 2 + 1] = color
        return np.ascontiguousarray(colors, dtype=np.float32)

    def initializeGL(self) -> None:
        """Track context lifetime; QOpenGLBuffer creation remains paint-lazy."""
        context = QtGui.QOpenGLContext.currentContext()  # pylint: disable=c-extension-no-member
        if context is None or context is self._gl_context:
            return
        self._disconnect_context()
        self._gl_context = context
        context.aboutToBeDestroyed.connect(self._context_about_to_be_destroyed)

    def _context_about_to_be_destroyed(self) -> None:
        view = self.view()
        if view is not None:
            try:
                view.makeCurrent()
            except RuntimeError:
                # The Python item can outlive the underlying QOpenGLWidget.
                pass
        self._destroy_gpu_buffers()
        self._gl_context = None

    def _disconnect_context(self) -> None:
        if self._gl_context is None:
            return
        try:
            self._gl_context.aboutToBeDestroyed.disconnect(self._context_about_to_be_destroyed)
        except (RuntimeError, TypeError):
            pass
        self._gl_context = None

    def _destroy_gpu_buffers(self) -> None:
        self.m_vbo_position.destroy()
        self.m_vbo_color.destroy()
        self.dirty_bits |= DirtyFlag.POSITION | DirtyFlag.COLOR

    def dispose(self) -> None:
        """Release GPU and CPU resources while the owning view still exists."""
        view = self.view()
        if view is not None:
            try:
                if view.isValid():
                    view.makeCurrent()
            except RuntimeError:
                pass
        self._disconnect_context()
        self._destroy_gpu_buffers()
        self.segments = ()
        self.source_segments = ()
        self.logical_to_exclusive_segment = np.zeros(1, dtype=np.int32)
        self.packed_vertices = np.empty((0, 3), dtype=np.float32)
        self.packed_colors = np.empty((0, 4), dtype=np.float32)
        self.pos = self.packed_vertices
        self.color = self.packed_colors
        self.visible_logical_count = 0
        self.visible_segment_count = 0

    def paint(self) -> None:
        """Draw the visible vertex prefix from the full resident VBOs."""
        if self.visible_vertex_count <= 0 or self.pos is None:
            return
        self.setupGLState()

        matrix = np.array(self.mvpMatrix().data(), dtype=np.float32)
        context = QtGui.QOpenGLContext.currentContext()  # pylint: disable=c-extension-no-member
        if context is None:
            return

        if DirtyFlag.POSITION in self.dirty_bits:
            self.upload_vbo(self.m_vbo_position, self.packed_vertices)
        if DirtyFlag.COLOR in self.dirty_bits:
            self.upload_vbo(self.m_vbo_color, self.packed_colors)
        self.dirty_bits = DirtyFlag(0)

        program = self.getShaderProgram()
        enabled_locations = []

        self.m_vbo_position.bind()
        GL.glVertexAttribPointer(0, 3, GL.GL_FLOAT, False, 0, None)
        self.m_vbo_position.release()
        enabled_locations.append(0)

        self.m_vbo_color.bind()
        GL.glVertexAttribPointer(1, 4, GL.GL_FLOAT, False, 0, None)
        self.m_vbo_color.release()
        enabled_locations.append(1)

        enable_antialias = self.antialias and not context.isOpenGLES()
        if enable_antialias:
            GL.glEnable(GL.GL_LINE_SMOOTH)
            GL.glEnable(GL.GL_BLEND)
            GL.glBlendFuncSeparate(
                GL.GL_SRC_ALPHA,
                GL.GL_ONE_MINUS_SRC_ALPHA,
                GL.GL_ONE,
                GL.GL_ONE_MINUS_SRC_ALPHA,
            )
            GL.glHint(GL.GL_LINE_SMOOTH_HINT, GL.GL_NICEST)

        surface_format = context.format()
        core_forward_compatible = (
            surface_format.profile() == surface_format.OpenGLContextProfile.CoreProfile
            and not surface_format.testOption(surface_format.FormatOption.DeprecatedFunctions)
        )
        if not core_forward_compatible:
            GL.glLineWidth(self.width)

        for location in enabled_locations:
            GL.glEnableVertexAttribArray(location)
        with program:
            location = GL.glGetUniformLocation(program, "u_mvp")
            GL.glUniformMatrix4fv(location, 1, False, matrix)
            GL.glDrawArrays(GL.GL_LINES, 0, self.visible_vertex_count)
        for location in enabled_locations:
            GL.glDisableVertexAttribArray(location)

        if enable_antialias:
            GL.glDisable(GL.GL_LINE_SMOOTH)
            GL.glDisable(GL.GL_BLEND)
        GL.glLineWidth(1.0)
