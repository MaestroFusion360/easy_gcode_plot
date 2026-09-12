from __future__ import annotations

from dataclasses import replace

from PyQt6.QtWidgets import QApplication

from app.gcode.kernel import execute
from app.gcode.trace_tools import render_trace
from app.main_window import MainWindow
from app.ui.playback import build_playback_movements

QT_APP = QApplication.instance() or QApplication([])


G71_WITH_OFFSET_ARCS = """N3 T1111
G0 X72 Z1
G71 U2.5 R0.2
G71 P21 Q22 U-0.2 W0.1 F0.25
N21 G0 X89.8
G1 Z0
X87.8 R1
X84.45 A20 R1.8
Z-30.05
X75.5 C1
N22 Z-145
G0 Z100
"""


def _playback(result):
    return build_playback_movements(result.motions)[0]


def test_plain_and_arc_commands_are_one_playback_position_each():
    linear = execute("G0 X100 Z5\nG1 X80 Z0")
    arcs = execute("G0 X20 Z0\nG2 X10 Z-5 R5\nG3 X20 Z-10 R5")

    assert len(_playback(linear)) == len(linear.motions) == 2
    assert len(_playback(arcs)) == len(arcs.motions) == 3


def test_arc_tessellation_density_does_not_change_playback_count():
    result = execute("G0 X20 Z0\nG2 X10 Z-5 R5")
    low_density = render_trace(result, arc_points_per_circle=12)
    high_density = render_trace(result, arc_points_per_circle=720)

    assert len(high_density) > len(low_density)
    assert len(_playback(result)) == 2


def test_simplified_programming_uses_real_transition_motions_not_samples():
    result = execute("G0 X90 Z1\nG1 Z0\nX87.8 R1\nX84.45 A20 R1.8\nZ-30.05\nX75.5 C1\nZ-40")

    assert result.ok, result.diagnostics
    assert len(_playback(result)) == len(result.motions)
    assert any(motion.move in (2, 3) for motion in result.motions)


def test_g71_offset_approximation_is_grouped_but_real_cycle_moves_remain():
    result = execute(G71_WITH_OFFSET_ARCS)
    playback = _playback(result)

    assert result.ok, result.diagnostics
    assert len(playback) < len(result.motions)
    assert any(item.motion_end - item.motion_start > 1 for item in playback)
    assert sum(item.motion_end - item.motion_start == 1 for item in playback) > 5
    assert {result.motions[item.motion_end - 1].move for item in playback} >= {0, 1}


def test_cycle_and_macro_expansion_motions_are_not_collapsed(fixture_text):
    cycle = execute(fixture_text("turning/drill.nc"))
    macro = execute(fixture_text("milling/macro_b.nc"), language="fanuc_mill")

    assert cycle.ok and macro.ok
    assert len(_playback(cycle)) == len(cycle.motions)
    assert len(_playback(macro)) == len(macro.motions)
    assert len(macro.motions) > 10


def test_only_explicit_consecutive_approximation_groups_collapse():
    base = execute("G0 X10\nG1 X9\nG1 X8\nG0 X20").motions
    motions = (
        base[0],
        replace(base[1], playback_group=7),
        replace(base[2], playback_group=7),
        base[3],
    )
    playback, reverse = build_playback_movements(motions)

    assert [(item.motion_start, item.motion_end) for item in playback] == [(0, 1), (1, 3), (3, 4)]
    assert reverse == (0, 1, 1, 2)


def test_grouped_playback_keeps_stock_timeline_on_detailed_range_boundary():
    # pylint: disable=protected-access
    window = MainWindow()
    window.autoUpdateEnabled = False
    window.ui.actionLatheMode.setChecked(True)
    window.tools = {"T1111": {"type": "od_80", "noseRadius": 0.8, "tipOrientation": 3}}
    window.ui.editor.setText(G71_WITH_OFFSET_ARCS)
    assert window.updateData()
    window.applyStockSettings(
        {
            "enabled": True,
            "outer_diameter": 100.0,
            "inner_diameter": 0.0,
            "length": 170.0,
            "front_allowance": 5.0,
            "resolution": 2.0,
        }
    )
    window.ui.actionPlay.setChecked(True)

    grouped_index = next(
        index for index, item in enumerate(window._playback_movements) if item.motion_end - item.motion_start > 1
    )
    window.ui.horizontalSlider.setValue(grouped_index + 1)
    assert window._stock_timeline.motion_count == window._playback_movements[grouped_index].motion_end
    window.ui.horizontalSlider.setValue(grouped_index)
    expected = 0 if grouped_index == 0 else window._playback_movements[grouped_index - 1].motion_end
    assert window._stock_timeline.motion_count == expected
    window.deleteLater()
