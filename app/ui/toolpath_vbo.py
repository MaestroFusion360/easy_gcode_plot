"""VBO-backed toolpath item for the existing pyqtgraph OpenGL scene."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from OpenGL import GL
from PyQt6 import QtGui
from PyQt6.QtGui import QColor
from pyqtgraph.opengl import GLLinePlotItem
from pyqtgraph.opengl.items.GLLinePlotItem import DirtyFlag


@dataclass(frozen=True)
class ToolpathSegment:
    """One independently rendered segment owned by a logical kernel motion."""

    start: tuple[float, float, float]
    end: tuple[float, float, float]
    logical_index: int
    move: int


def segments_from_render_points(render_points, motions) -> tuple[ToolpathSegment, ...]:
    """Convert the sampled trace to ordered ``GL_LINES`` segment pairs."""
    segments: list[ToolpathSegment] = []
    for previous, current in zip(render_points, render_points[1:]):
        logical_index = current.motion_index
        if not 0 <= logical_index < len(motions):
            continue
        segments.append(
            ToolpathSegment(
                (previous.x, previous.y, previous.z),
                (current.x, current.y, current.z),
                logical_index,
                motions[logical_index].move,
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
        self.segments: tuple[ToolpathSegment, ...] = ()
        self.logical_to_exclusive_segment = np.zeros(1, dtype=np.int32)
        self.packed_vertices = np.empty((0, 3), dtype=np.float32)
        self.packed_colors = np.empty((0, 4), dtype=np.float32)
        self.visible_logical_count = 0
        self.visible_segment_count = 0
        self._rapid_color = _rgba("#d02020")
        self._linear_color = _rgba("#0000ff")
        self._arc_color = _rgba("#008000")
        self._gl_context = None
        super().__init__(
            pos=self.packed_vertices,
            color=self.packed_colors,
            width=1.5,
            antialias=True,
            mode="lines",
            glOptions="additive",
        )

    @property
    def logical_count(self) -> int:
        return len(self.logical_to_exclusive_segment) - 1

    @property
    def visible_vertex_count(self) -> int:
        return self.visible_segment_count * 2

    def set_segments(self, segments, logical_count: int) -> None:
        """Pack a complete sampled toolpath and mark both GPU buffers dirty."""
        self.segments = tuple(segments)
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

    def set_style(self, *, rapid_color, linear_color, arc_color, width: float) -> None:
        """Update only the color VBO when trajectory colors change."""
        colors = (_rgba(rapid_color), _rgba(linear_color), _rgba(arc_color))
        old_colors = (self._rapid_color, self._linear_color, self._arc_color)
        self.width = float(width)
        if colors != old_colors:
            self._rapid_color, self._linear_color, self._arc_color = colors
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
            color = (
                self._rapid_color
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
