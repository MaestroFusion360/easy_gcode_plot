from __future__ import annotations

# pylint: disable=protected-access,c-extension-no-member  # White-box GL packing checks.
import numpy as np
import pytest
from PyQt6.QtGui import QMatrix4x4
from pyqtgraph.opengl.items.GLLinePlotItem import DirtyFlag

from app.gcode.kernel import execute
from app.gcode.trace_tools import render_trace
from app.ui.plot import toolpath_vbo
from app.ui.plot.toolpath_vbo import (
    ToolpathSegment,
    ToolpathVboItem,
    dashed_rapid_segments,
    segments_from_render_points,
    tool_color,
)


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


def test_indexed_approach_uses_current_table_frame_without_cross_part_bridge():
    result = execute("G90 G0 Z400\nB90\nG0 Z50\nM30", language="fanuc_mill", kinematics="4ax_table_b")
    segments = segments_from_render_points(render_trace(result), result.motions)
    assert len(segments) == 2
    assert segments[0].end == pytest.approx((0, 0, 400))
    assert segments[1].start == pytest.approx((400, 0, 0), abs=1e-8)
    assert segments[1].end == pytest.approx((50, 0, 0), abs=1e-8)
    assert min(segments[1].start[0], segments[1].end[0]) > 0


def test_sampled_segments_keep_modal_tool_for_coloring():
    result = execute("T1 M6\nG0 X1\nG1 X2 F100\nT2 M6\nG1 X3\nM30", language="fanuc_mill")
    segments = segments_from_render_points(render_trace(result), result.motions)
    assert [(segment.move, segment.tool) for segment in segments] == [(0, "T1"), (1, "T1"), (1, "T2")]


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


def test_tail_draws_the_whole_selected_motion_without_buffer_uploads(monkeypatch):
    item = ToolpathVboItem()
    item.set_segments(_segments(), logical_count=4)
    item.set_visible_logical_count(2)
    item.dirty_bits = DirtyFlag(0)
    vertices, colors = item.packed_vertices, item.packed_colors
    calls = []
    monkeypatch.setattr(toolpath_vbo.GL, "glDisableVertexAttribArray", lambda *a: calls.append(("disable", a)))
    monkeypatch.setattr(toolpath_vbo.GL, "glVertexAttrib4f", lambda *a: calls.append(("color", a)))
    monkeypatch.setattr(toolpath_vbo.GL, "glDrawArrays", lambda *a: calls.append(("draw", a)))
    monkeypatch.setattr(toolpath_vbo.GL, "glEnableVertexAttribArray", lambda *a: calls.append(("enable", a)))
    item.set_tail(1, "#ff00ff")
    assert item.tail_vertex_range == (2, 4)
    item._paint_tail()
    assert calls == [
        ("disable", (1,)),
        ("color", (1, 1.0, 0.0, 1.0, 1.0)),
        ("draw", (toolpath_vbo.GL.GL_LINES, 2, 4)),
        ("enable", (1,)),
    ]
    assert item.packed_vertices is vertices and item.packed_colors is colors
    assert item.dirty_bits == DirtyFlag(0)
    item.set_visible_logical_count(1)
    assert item.tail_vertex_range == (0, 0)
    item.set_tail(0, "#ff00ff")
    assert item.tail_vertex_range == (0, 2)
    item.set_visible_logical_count(0)
    assert item.tail_vertex_range == (0, 0)


def test_tail_follows_sampled_arc_and_disappears_for_hidden_rapid():
    result = execute("G17\nG0 X10\nG3 X0 Y10 I-10 J0 F100", language="fanuc_mill")
    item = ToolpathVboItem()
    item.set_segments(segments_from_render_points(render_trace(result), result.motions), 2)
    item.set_tail(1, "#ff00ff")
    first, count = item.tail_vertex_range
    assert first == 2 and count > 2
    assert first + count == len(item.packed_vertices)
    item.set_style(rapid_color="#ff0000", linear_color="#0000ff", arc_color="#008000", width=1.5, show_rapid=False)
    item.set_tail(0, "#ff00ff")
    assert item.tail_vertex_range == (0, 0)
    item.set_tail(1, "#ff00ff")
    assert item.tail_vertex_range == (0, len(item.packed_vertices))


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


def test_rapid_visibility_dashes_and_tool_colors_preserve_playback_mapping():
    assert tool_color("T1") != tool_color("T10")
    item = ToolpathVboItem()
    source = (
        ToolpathSegment((0, 0, 0), (10, 0, 0), 0, 0, "T1"),
        ToolpathSegment((10, 0, 0), (20, 0, 0), 1, 1, "T1"),
        ToolpathSegment((20, 0, 0), (30, 0, 0), 2, 1, "T2"),
    )
    item.set_segments(source, logical_count=3)
    item.set_style(
        rapid_color="#d02020",
        linear_color="#0000ff",
        arc_color="#008000",
        width=1.5,
        show_rapid=True,
        dashed_rapid=True,
        color_by_tool=True,
    )
    item._repack(3, QMatrix4x4(), (100, 100))
    assert len(item.segments) > len(source)
    assert all(segment.move == 0 for segment in item.segments[: item.segment_range_for_logical(0)[1]])
    assert item.packed_colors[0].tolist() == pytest.approx(item.packed_colors[-3].tolist())
    assert item.packed_colors[0].tolist() == pytest.approx(list(toolpath_vbo._rgba(tool_color("T1"))))
    assert item.packed_colors[-1].tolist() == pytest.approx(list(toolpath_vbo._rgba(tool_color("T2"))))
    item.set_visible_logical_count(1)
    visible = item.visible_segment_count
    item.set_style(
        rapid_color="#d02020",
        linear_color="#0000ff",
        arc_color="#008000",
        width=1.5,
        show_rapid=False,
        dashed_rapid=True,
        color_by_tool=True,
    )
    assert item.source_segments == source
    assert item.segment_range_for_logical(0) == (0, 0)
    assert item.visible_segment_count == 0
    assert visible > 0


def test_rapid_dashes_match_print_sized_pixels_even_for_long_moves():
    segment = ToolpathSegment((0, 0, 0), (2, 0, 0), 0, 0)
    pieces = dashed_rapid_segments(segment, QMatrix4x4(), (700, 500))
    assert len(pieces) > 90
    widths = [(piece.end[0] - piece.start[0]) * 700 / 2 for piece in pieces[:-1]]
    assert all(width == pytest.approx(3, abs=0.01) for width in widths)
    gaps = [(later.start[0] - earlier.end[0]) * 700 / 2 for earlier, later in zip(pieces, pieces[1:])]
    assert all(gap == pytest.approx(2, abs=0.01) for gap in gaps)


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


def test_camera_change_does_not_repack_during_paint(monkeypatch):
    item = ToolpathVboItem()
    item.set_segments(_segments(), logical_count=4)
    item.dashed_rapid = True
    initial_vertices = item.packed_vertices

    class View:
        def width(self):
            return 700

        def height(self):
            return 500

    monkeypatch.setattr(item, "view", lambda: View())
    monkeypatch.setattr(item, "mvpMatrix", lambda: QMatrix4x4())
    monkeypatch.setattr(item, "setupGLState", lambda: None)
    monkeypatch.setattr(toolpath_vbo.QtGui.QOpenGLContext, "currentContext", lambda: None)
    item.paint()
    assert item.packed_vertices is initial_vertices
    assert item._dash_signature is None


@pytest.mark.parametrize("logical_count", [-1, 0, 99])
def test_visible_logical_count_is_clamped(logical_count):
    item = ToolpathVboItem()
    item.set_segments(_segments(), logical_count=4)
    item.set_visible_logical_count(logical_count)
    assert 0 <= item.visible_logical_count <= 4


@pytest.mark.parametrize("reference", ["G91 G28 Z0", "G53 Z0"])
def test_three_axis_reference_and_next_approach_are_contiguous(reference):
    result = execute(f"G90 G0 Z50\n{reference}\nG90 G0 X10 Z20\nM30", language="fanuc_mill", home_z=400)
    assert result.ok and result.complete, result.diagnostics
    segments = segments_from_render_points(render_trace(result), result.motions)
    assert len(segments) == 3
    for previous, current in zip(segments, segments[1:]):
        assert current.start == pytest.approx(previous.end)
