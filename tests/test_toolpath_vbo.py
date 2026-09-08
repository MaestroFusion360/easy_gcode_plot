from __future__ import annotations

import numpy as np
import pytest
from pyqtgraph.opengl.items.GLLinePlotItem import DirtyFlag

from app.gcode.kernel import execute
from app.gcode.trace_tools import render_trace
from app.ui import toolpath_vbo
from app.ui.toolpath_vbo import ToolpathSegment, ToolpathVboItem, segments_from_render_points


def _segments():
    return (
        ToolpathSegment((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), 0, 0),
        ToolpathSegment((1.0, 0.0, 0.0), (2.0, 1.0, 0.0), 1, 1),
        ToolpathSegment((2.0, 1.0, 0.0), (3.0, 2.0, 0.0), 1, 1),
        ToolpathSegment((3.0, 2.0, 0.0), (4.0, 2.0, 0.0), 3, 2),
    )


def test_toolpath_vbo_packs_independent_float32_segment_pairs():
    item = ToolpathVboItem()
    item.set_segments(_segments(), logical_count=4)

    assert item.packed_vertices.shape == (8, 3)
    assert item.packed_vertices.dtype == np.float32
    assert item.packed_vertices.flags.c_contiguous
    assert item.packed_colors.shape == (8, 4)
    assert item.packed_colors.dtype == np.float32
    assert item.packed_colors.flags.c_contiguous
    assert item.logical_to_exclusive_segment.tolist() == [0, 1, 3, 3, 4]
    assert item.segment_range_for_logical(1) == (1, 3)
    assert item.segment_range_for_logical(2) == (3, 3)


def test_expanded_arc_segments_keep_their_logical_motion_mapping():
    result = execute("G90 G17 G0 X10 Y0\nG3 X0 Y10 I-10 J0 F100\nM30", language="fanuc_mill")
    points = render_trace(result, arc_points_per_circle=32)
    segments = segments_from_render_points(points, result.motions)
    item = ToolpathVboItem()
    item.set_segments(segments, logical_count=len(result.motions))

    assert len(segments) > len(result.motions)
    assert item.segment_range_for_logical(0) == (0, 1)
    assert item.segment_range_for_logical(1)[1] == len(segments)
    assert all(segment.move == 3 for segment in segments[1:])


def test_playback_changes_only_draw_prefix_without_dirtying_vbos():
    item = ToolpathVboItem()
    item.set_segments(_segments(), logical_count=4)
    vertices = item.packed_vertices
    colors = item.packed_colors
    dirty = item.dirty_bits

    item.set_visible_logical_count(2)
    assert item.visible_segment_count == 3
    assert item.visible_vertex_count == 6
    assert item.packed_vertices is vertices
    assert item.packed_colors is colors
    assert item.dirty_bits == dirty

    item.set_visible_logical_count(1)
    assert item.visible_segment_count == 1
    item.set_visible_logical_count(4)
    assert item.visible_segment_count == 4
    assert item.dirty_bits == dirty


def test_style_change_dirties_color_vbo_but_not_geometry_vbo():
    item = ToolpathVboItem()
    item.set_segments(_segments(), logical_count=4)
    item.dirty_bits = DirtyFlag(0)
    vertices = item.packed_vertices

    item.set_style(rapid_color="#111233", linear_color="#445566", arc_color="#778899", width=3.0)

    assert item.packed_vertices is vertices
    assert DirtyFlag.POSITION not in item.dirty_bits
    assert DirtyFlag.COLOR in item.dirty_bits
    assert item.width == 3.0


def test_reloading_and_empty_geometry_reuses_item_and_resets_mapping():
    item = ToolpathVboItem()
    item.set_segments(_segments(), logical_count=4)
    item.set_segments((), logical_count=0)

    assert item.segments == ()
    assert item.logical_to_exclusive_segment.tolist() == [0]
    assert item.packed_vertices.shape == (0, 3)
    assert item.visible_vertex_count == 0


def test_paint_uploads_each_dirty_buffer_once_across_playback(monkeypatch):
    class _Buffer:
        def bind(self):
            return True

        def release(self):
            pass

    class _Context:
        def isOpenGLES(self):
            return False

        def format(self):
            return _Format()

    class _Format:
        OpenGLContextProfile = type("Profile", (), {"CoreProfile": 1})
        FormatOption = type("Option", (), {"DeprecatedFunctions": 1})

        def profile(self):
            return 0

        def testOption(self, _option):
            return False

    class _Program:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    item = ToolpathVboItem()
    item.set_segments(_segments(), logical_count=4)
    item.m_vbo_position = _Buffer()
    item.m_vbo_color = _Buffer()
    uploads = []
    item.upload_vbo = lambda buffer, array: uploads.append((buffer, array))
    item.setupGLState = lambda: None
    item.mvpMatrix = lambda: type("Matrix", (), {"data": lambda self: [0.0] * 16})()
    item.getShaderProgram = lambda: _Program()
    monkeypatch.setattr(  # pylint: disable=c-extension-no-member
        toolpath_vbo.QtGui.QOpenGLContext,  # pylint: disable=c-extension-no-member
        "currentContext",
        lambda: _Context(),
    )
    for name in (
        "glVertexAttribPointer",
        "glEnable",
        "glBlendFuncSeparate",
        "glHint",
        "glLineWidth",
        "glEnableVertexAttribArray",
        "glUniformMatrix4fv",
        "glDrawArrays",
        "glDisableVertexAttribArray",
        "glDisable",
    ):
        monkeypatch.setattr(toolpath_vbo.GL, name, lambda *_args: None)
    monkeypatch.setattr(toolpath_vbo.GL, "glGetUniformLocation", lambda *_args: 0)

    item.paint()
    assert len(uploads) == 2
    item.set_visible_logical_count(1)
    item.paint()
    item.set_visible_logical_count(4)
    item.paint()
    assert len(uploads) == 2
    assert item.dirty_bits == DirtyFlag(0)


@pytest.mark.parametrize("logical_count", [-1, 0, 99])
def test_visible_logical_count_is_clamped(logical_count):
    item = ToolpathVboItem()
    item.set_segments(_segments(), logical_count=4)
    item.set_visible_logical_count(logical_count)
    assert 0 <= item.visible_logical_count <= 4
