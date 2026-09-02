"""Regression tests that drive the real parsing pipeline with embedded G-code samples.

The programs are stored inline in ``tests/gcode_samples.py`` (mirroring small
files that used to live in ``tmp/cnc programs``) so the suite never touches the
filesystem for fixtures. Running them needs a QPA backend, therefore the
``QT_QPA_PLATFORM=offscreen`` variable is set in ``conftest.py``.
"""

from collections import Counter

import pytest
from gcode_samples import GCODE_SAMPLES
from PyQt6.QtCore import QEventLoop, QSettings, QTimer
from PyQt6.QtWidgets import QApplication

from app import main_window


@pytest.fixture(scope="module")
def qapp():
    """Return the shared QApplication instance (Qt allows only one)."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(scope="module")
def window(qapp, tmp_path_factory):
    """Return a MainWindow whose settings live in a temporary, empty config."""
    config = tmp_path_factory.mktemp("cfg") / "config.ini"
    original = main_window.get_settings
    main_window.get_settings = lambda: QSettings(str(config), QSettings.Format.IniFormat)
    try:
        win = main_window.MainWindow()
    finally:
        main_window.get_settings = original
    return win


def _load(window, name):
    """Put a named sample into the editor and run the parse pipeline."""
    window.ui.editor.setText(GCODE_SAMPLES[name])
    window.updateData()


def _bounds(points):
    """Return ((xmin,xmax),(ymin,ymax),(zmin,zmax)) of the toolpath points."""
    axes = list(zip(*points))
    return tuple((min(a), max(a)) for a in axes)


def _assert_bounds(actual, expected, tolerance=0.05):
    for (amin, amax), (emin, emax) in zip(actual, expected):
        assert amin == pytest.approx(emin, abs=tolerance)
        assert amax == pytest.approx(emax, abs=tolerance)


# Snapshot of the current parser behaviour for each embedded program.
# Any change in the parsing/interpolation logic must be reflected here.
EXPECTED = {
    "full_circle": {
        "points": 1273,
        "moves": {0: 6, 1: 11, 2: 4},
        "bounds": ((-50.1, 50.1), (-50.097, 50.097), (-3.0, 100.0)),
        "planes": [17],
        "tools": [1],
    },
    "contour": {
        "points": 339,
        "moves": {0: 20, 1: 9, 3: 4},
        "bounds": ((-55.123, 55.123), (-55.123, 65.123), (-5.123, 100.0)),
        "planes": [17],
        "tools": [0, 1],
    },
    "drill_g81": {
        "points": 64,
        "moves": {0: 30},
        "bounds": ((-96.593, 96.593), (-96.593, 96.593), (-20.0, 100.0)),
        "planes": [17],
        "tools": [0, 1],
    },
    "drill_g83": {
        "points": 532,
        "moves": {0: 30},
        "bounds": ((-96.593, 96.593), (-96.593, 96.593), (-20.0, 100.0)),
        "planes": [17],
        "tools": [0, 1],
    },
    "planes_g17_18_19": {
        "points": 268,
        "moves": {0: 33, 1: 3, 2: 2, 3: 1},
        "bounds": ((0.0, 50.0), (0.0, 50.0), (0.0, 100.0)),
        "planes": [17, 18, 19],
        "tools": [0, 1],
    },
    "helix_vint_360": {
        "points": 7781,
        "moves": {0: 19, 1: 2, 3: 26},
        "bounds": ((-15.0, 15.0), (-14.999, 14.999), (-20.0, 10.0)),
        "planes": [17],
        "tools": [0, 1],
    },
}


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_sample_matches_snapshot(window, name):
    """Parsing a known program must reproduce the stored trajectory metrics."""
    _load(window, name)
    expected = EXPECTED[name]

    assert len(window.lst_points) == expected["points"]
    assert len(window.lst_block) == expected["points"]
    assert Counter(window.lstMove) == expected["moves"]
    _assert_bounds(_bounds(window.lst_points), expected["bounds"])
    assert sorted(set(window.lstArcPlane)) == expected["planes"]
    assert sorted(set(window.lstTool)) == expected["tools"]


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_point_estimator_matches_real(window, name):
    """The cheap point counter used for auto-refresh must agree with addMotion."""
    _load(window, name)
    estimated = window._countProgramPoints()  # pylint: disable=protected-access
    assert estimated == len(window.lst_points)


_SMALL_PROGRAM = "G90 G17\nG0 X0 Y0 Z5\nG1 X50 Y0 F500\nG2 X100 Y0 I25 J0 F800\nG0 Z50\nM30"


def _process_events_for(ms):
    """Run the Qt event loop so the debounce timer can fire."""
    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    timer.setInterval(ms)
    timer.timeout.connect(loop.quit)
    timer.start()
    loop.exec()


def test_auto_refresh_small_program(window):
    """A small program must refresh itself after editing settles."""
    window.ui.editor.setText(_SMALL_PROGRAM)
    _process_events_for(900)
    assert len(window.lst_points) > 0
    assert window.ui.actionPlay.isEnabled()


def test_no_auto_refresh_when_too_many_points(window):
    """A few lines with many G2 arcs must stay manual (point-based gating)."""
    n_arcs = main_window.AUTO_REFRESH_MAX_POINTS // 300 + 5
    text = "G90 G17\nG0 X-50.1 Y0\nG1 Z5 F500\n"
    text += "G2 X-50.1 I50.1 J0 F500\n" * n_arcs

    window.ui.editor.setText(text)
    _process_events_for(900)
    assert len(window.lst_points) == 0
    assert not window.ui.actionPlay.isEnabled()


def test_g81_drill_cycle_reaches_depth(window):
    """G81 canned cycle must expand to points down to the programmed Z."""
    _load(window, "drill_g81")
    assert 81 in set(window.lstCycleDrill)
    assert 80 in set(window.lstCycleDrill)
    zmin = min(p[2] for p in window.lst_points)
    assert zmin == pytest.approx(-20.0, abs=0.05)
    assert len(window.lst_points) > 10


def test_g83_peck_cycle_creates_extra_points(window):
    """G83 pecking expands each hole into many small moves."""
    _load(window, "drill_g83")
    assert 83 in set(window.lstCycleDrill)
    zmin = min(p[2] for p in window.lst_points)
    assert zmin == pytest.approx(-20.0, abs=0.05)
    assert len(window.lst_points) > len(window.lstMove)


def test_all_arc_planes_are_seen(window):
    """Programs switching G17/G18/G19 must record every used plane."""
    _load(window, "planes_g17_18_19")
    assert set(window.lstArcPlane) == {17, 18, 19}
    assert 2 in set(window.lstMove)
    assert 3 in set(window.lstMove)


def test_helix_interpolates_many_points_down_to_depths(window):
    """A 360-degree helical ramp must produce a long continuous toolpath."""
    _load(window, "helix_vint_360")
    assert len(window.lst_points) > 5000
    zmin = min(p[2] for p in window.lst_points)
    assert zmin == pytest.approx(-20.0, abs=0.05)
    xmax = max(p[0] for p in window.lst_points)
    assert xmax == pytest.approx(15.0, abs=0.05)


def test_circle_path_encloses_full_radius(window):
    """Full-circle interpolation must keep points within the program radius."""
    _load(window, "full_circle")
    radius = max((p[0] ** 2 + p[1] ** 2) ** 0.5 for p in window.lst_points)
    assert radius == pytest.approx(50.1, abs=0.1)
    assert len(window.lst_points) > 1000
