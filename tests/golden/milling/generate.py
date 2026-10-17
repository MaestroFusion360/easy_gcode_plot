"""Generate reviewed candidates separately: see README.md before updating CSVs.

The references below transcribe these seventeen NC programs analytically. They
do not parse NC or use kernel geometry, expression, cycle or sampling helpers.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

# Direct script execution needs the repository root before importing test helpers.
# pylint: disable=wrong-import-position
from test_fanuc import (  # noqa: E402
    COUNTS,
    GOLDEN,
    HEADER,
    OPTIONS,
    assert_same_geometry,
    coordinates,
    run_fixture,
)

# pylint: enable=wrong-import-position


class _Path:
    """A list of explicitly specified reference primitives, in fixture units."""

    def __init__(self, scale=1):
        self.point = (0, 0, 0)
        self.scale = scale
        self.rows = []

    def add(self, move, end, center=None, plane=17, start=None, *, sweep=None, full_circle=None):
        start = self.point if start is None else start
        if start == end and center is None:
            return  # Explicit zero-displacement blocks do not emit motions.
        geometry = (None,) * 8
        if center is not None:
            u, v = {17: (0, 1), 18: (2, 0), 19: (1, 2)}[plane]
            a = math.atan2(start[v] - center[v], start[u] - center[u])
            b = math.atan2(end[v] - center[v], end[u] - center[u])
            full = (start[u] == end[u] and start[v] == end[v]) if full_circle is None else full_circle
            if sweep is None:
                sweep = 2 * math.pi if full else ((b - a) if move == 3 else (a - b)) % (2 * math.pi)
            radius = math.hypot(start[u] - center[u], start[v] - center[v])
            geometry = (
                plane,
                *(c * self.scale for c in center),
                radius * self.scale,
                sweep,
                int((move == 2) != (plane == 18)),
                int(full),
            )
        self.rows.append((move, *(c * self.scale for c in start), *(c * self.scale for c in end), *geometry))
        self.point = end


def _linear(name):
    # Each entry is (movement, endpoint); source modal words are resolved by hand.
    points = {
        "terraced_ramp": [
            (0, (-20, -15, 10)),
            (1, (-20, -15, 0)),
            (1, (20, -15, -1)),
            (1, (20, 15, -2)),
            (1, (-20, 15, -1)),
            (1, (-20, -15, -2)),
            (0, (-20, -15, 5)),
            (0, (-20, -15, 5)),
            (1, (-20, -15, -2)),
            (1, (20, -15, -3)),
            (1, (20, 15, -4)),
            (1, (-20, 15, -3)),
            (1, (-20, -15, -4)),
            (0, (-20, -15, 10)),
        ],
        "ramped_surface": [
            (0, (-30, -20, 15)),
            (1, (-30, -20, 2)),
            (1, (30, -20, -1)),
            (1, (30, -10, -2)),
            (1, (-30, -10, -1)),
            (1, (-30, 0, -2)),
            (1, (30, 0, -3)),
            (1, (30, 10, -2)),
            (1, (-30, 10, -3)),
            (1, (-30, 20, -4)),
            (1, (30, 20, -5)),
            (0, (30, 20, 15)),
        ],
        "incremental_xyz_raster": [
            (0, (-24, -12, 8)),
            (1, (-24, -12, 0)),
            (1, (24, -12, -1)),
            (1, (24, -4, -1.5)),
            (1, (-24, -4, -2.5)),
            (1, (-24, 4, -3)),
            (1, (24, 4, -4)),
            (1, (24, 12, -4.5)),
            (1, (-24, 12, -5.5)),
            (0, (-24, 12, 10)),
        ],
    }
    p = _Path()
    for move, end in points[name]:
        p.add(move, end)
    return p.rows


def _macro_expressions():
    p = _Path()

    def sin(a):
        return math.sin(math.radians(a))

    def cos(a):
        return math.cos(math.radians(a))

    def tan(a):
        return math.tan(math.radians(a))

    expression = ((3 + 0.8235) * 1.427 + 0.327187) * 12
    # Indirection: ROUND(SIN(expression)+SQRT(3.6))=3; #3=1.427;
    # FUP(#3)=2; #2=42. WHILE runs twice and GOTO skips #151=-1.
    ends = [
        (30, 42, 1.427 + 4.125),
        (42 - 15, 1.427 * 6.7, 42 / 2),
        (42 / 1.427, sin(42), cos(42)),
        (tan(42), math.degrees(math.atan(0.75 / 1.625)), math.sqrt(35)),
        (abs(-13.125162), 1, 1),
        (1, 1.427 - 4, (1.427 + 4.125) ** 2),
        (5 / tan(8.6), 6.2 + 14 / 3 - 2 * 8.32, (6.2 + 14) / 3 - 2 * 8.32),
        (math.sqrt(3.6), expression, sin(expression) + math.sqrt(3.6)),
        (42, 2, 7),
        (1, 0, 0),
        (0, 0, 1),
        (1, 0, 1),
        (11, 10, 11),
        (3, 3, 3),
    ]
    for end in ends:
        p.add(1, end)
    return p.rows


def _wcs():
    p = _Path()
    for ox, oy, oz in OPTIONS["wcs_test"]["wcs_offsets"].values():

        def add(move, x, y, z, center=None, *, offset=(ox, oy, oz)):
            dx, dy, dz = offset
            c = None if center is None else (center[0] + dx, center[1] + dy, z + dz)
            p.add(move, (x + dx, y + dy, z + dz), c)

        # WCS selection preserves physical Z until a Z word is executed.
        p.add(0, (ox, oy + 65.123, p.point[2]))
        for z in (100, 15, 2):
            add(0, 0, 65.123, z)
        add(1, 0, 65.123, -5.123)
        for move, x, y, center in [
            (1, 0, 55.123, None),
            (1, -39.556, 55.123, None),
            (3, -55.123, 39.556, (-39.556, 39.556)),
            (1, -55.123, -39.556, None),
            (3, -39.556, -55.123, (-39.556, -39.556)),
            (1, 39.556, -55.123, None),
            (3, 55.123, -39.556, (39.556, -39.556)),
            (1, 55.123, 39.556, None),
            (3, 39.556, 55.123, (39.556, 39.556)),
            (1, 0, 55.123, None),
            (1, 0, 65.123, None),
        ]:
            add(move, x, y, -5.123, center)
        add(1, 0, 65.123, 2)
        add(0, 0, 65.123, 15)
    p.add(0, (*p.point[:2], 0))
    p.add(0, (0, 0, 0))
    return p.rows


def _subprogram():
    p = _Path(25.4)
    p.add(0, (-2.6, -0.25, 0))
    p.add(0, (-2.6, -0.25, 1))
    p.add(0, (-2.6, -0.25, 0.1))
    p.add(1, (-2.6, -0.25, 0))
    for repeat in range(1, 11):
        z = -0.025 * repeat
        for move, x, y, center in [
            (1, -2.6, -0.25, None),
            (1, -2.25, -0.25, None),
            (1, -2.25, 1, None),
            (2, -2, 1.25, (-2, 1)),
            (1, 2, 1.25, None),
            (2, 2.25, 1, (2, 1)),
            (1, 2.25, -1, None),
            (2, 2, -1.25, (2, -1)),
            (1, -2, -1.25, None),
            (2, -2.25, -1, (-2, -1)),
            (1, -2.25, 0.25, None),
            (1, -2.6, 0.25, None),
        ]:
            p.add(move, (x, y, z), None if center is None else (*center, z))
        p.add(0, (-2.6, 0.25, z + 1))
        p.add(0, (-2.6, -0.25, z + 1))
        p.add(0, (-2.6, -0.25, z))
    # O10 returns in G91/G0. Main Z.1 is incremental; G1 Z0 and G0 X0 Y0
    # have no displacement. M98 does not restore the caller's modal modes.
    p.add(0, (-2.6, -0.25, -0.15))
    for repeat in range(1, 4):
        z = -0.15 - repeat * 0.025
        p.add(1, (*p.point[:2], z))
        p.add(1, (-2.6, 0.25, z))
        p.add(2, (-2.6, -0.25, z), (-2.6, 0, z))
        p.add(2, (-2.6, 0.25, z), (-2.6, 0, z))
        p.add(1, (-2.6, 0, z))
    p.add(0, (-2.6, 0, 1))
    p.add(0, (0, 0, 0))
    return p.rows


def _macro_circles(name):
    p = _Path()
    boss = name == "macro_boss_milling"
    if boss:
        p.add(0, (0, 100, 0))
    p.add(0, (0, 100 if boss else 0, 100))
    p.add(1, (0, 100 if boss else 0, 0))
    # Program R50; configured tool R25. G41 is outward for CW boss,
    # inward for CCW hole: tool-center radii 75 and 25 respectively.
    y, move, count, step = (75, 2, 200, 0.25) if boss else (-25, 3, 50, 1)
    p.add(1, (0, y, 0))
    for repeat in range(1, count + 1):
        p.add(move, (0, y, -repeat * step), (0, 0, -(repeat - 1) * step))
    p.add(move, (0, y, -50), (0, 0, -50))
    p.add(1, (0, 100 if boss else 0, -50))
    p.add(0, (0, 100 if boss else 0, 100))
    p.add(0, (0, 100 if boss else 0, 0))
    return p.rows


def _arcs(name):
    p = _Path(25.4 if name == "inch_spiral" else 1)
    if name in {"helical_bore", "inch_spiral"}:
        inch = name == "inch_spiral"
        r, top, initial, depths, move = (
            (0.25, 0.5, 0.05, [-0.05, -0.15, -0.25], 2) if inch else (8, 10, 1, [-1, -3, -5, -5], 3)
        )
        p.add(0, (r, 0, top))
        p.add(1, (r, 0, initial))
        for depth in depths:
            p.add(move, (r, 0, depth), (0, 0, p.point[2]))
        p.add(0, (r, 0, top))
    elif name == "radius_arc_ramp":
        p.add(0, (10, 0, 8))
        p.add(1, (10, 0, 0))
        for end in [(0, 10, -1), (-10, 0, -2), (0, -10, -3), (10, 0, -4)]:
            p.add(3, end, (0, 0, p.point[2]))
        p.add(0, (10, 0, 8))
    elif name == "multiplane_edges":
        p.add(0, (0, 0, 10))
        p.add(1, (0, 0, 0))
        p.add(1, (20, 0, -2))
        p.add(3, (30, 0, -12), (20, 0, -12), 18)
        p.add(1, (30, 10, -12))
        p.add(3, (30, 20, -2), (30, 10, -2), 19)
        p.add(3, (20, 30, -2), (20, 20, -2))
        p.add(1, (0, 30, 0))
        p.add(0, (0, 30, 10))
    else:
        assert name == "mixed_ijk_r_planes"
        p.add(0, (10, 0, 8))
        p.add(1, (10, 0, 0))
        p.add(3, (0, 10, -1), (0, 0, 0))
        p.add(2, (-10, 10, -11), (0, 10, -11), 18)
        p.add(3, (-10, 20, -1), (-10, 10, -1), 19)
        p.add(1, (-20, 20, -2))
        p.add(0, (-20, 20, 8))
    return p.rows


def _face():
    p = _Path()
    p.add(0, (0, 0, 100))
    # WHILE[10.3 - 2*n GE 0.2]: n=0..5, not n=6.
    for repeat in range(6):
        z = 10.3 - 2 * repeat
        p.add(1, (0, 0, z))
        p.add(1, (0, -100, z))
        p.add(2, (0, -100, z), (0, 0, z))
        p.add(1, (0, 0, z))
    p.add(0, (0, 0, 100))
    p.add(0, (0, 0, 0))
    return p.rows


def _drilling(name):
    p = _Path()
    if name == "tapping_fanuc":
        p.add(0, (-20, 20, 0))
        p.add(0, (-20, 20, 26))
        for x, y in [(-20, 20), (-20, -20), (20, -20), (20, 20)]:
            p.add(0, (x, y, p.point[2]))
            p.add(0, (x, y, 15))
            p.add(1, (x, y, 1))
            p.add(1, (x, y, 15))  # G84 retract is feed, not G0.
            p.add(0, (x, y, 16))
        p.add(0, (20, 20, 26))
    else:
        # First group absolute 30/150/270; second group 30 + 120 + 120.
        for angle in [30, 150, 270] * 2:
            x, y = 100 * math.cos(math.radians(angle)), 100 * math.sin(math.radians(angle))
            p.add(0, (x, y, p.point[2]))
            p.add(0, (x, y, -5))
            p.add(1, (x, y, -20))
            p.add(0, (x, y, -5))
        p.add(0, (*p.point[:2], 0))
    return p.rows


def _correction():
    """Closed-form offsets of the rounded CAM circles; no kernel join helpers."""
    p = _Path()
    for move, end in [
        (0, (8, -74.4, 0)),
        (0, (8, -74.4, 15)),
        (0, (8, -74.4, -18)),
        (1, (8, -74.4, -22)),
        (1, (8, -74.4, -24)),
        (1, (8.4, -70.4, -24)),
    ]:
        p.add(move, end)
    p.add(3, (0, -62, -24), (0, -70.4, -24))
    p.add(1, (-65, -62, -24))
    p.add(2, (-79, -48, -24), (-65, -48, -24))
    # CAM rounded a nominal R10 endpoint to (3.846,9.231). The existing
    # tolerance convention uses the mean endpoint radius for the resolved circle.
    inner = (10 + math.hypot(3.846, 9.231)) / 2 - 4
    outer = math.hypot(6.154, 14.769) + 4
    tangent = math.sqrt(inner**2 - 6**2)

    def radial(center, point, radius):
        dx, dy = point[0] - center[0], point[1] - center[1]
        factor = radius / math.hypot(dx, dy)
        return (center[0] + dx * factor, center[1] + dy * factor, -24)

    p.add(1, (-79, 18 + tangent, -24))
    p.add(3, radial((-85, 18), (-81.154, 27.231), inner), (-85, 18, -24))
    p.add(
        2,
        radial((-75, 42), (-68.846, 56.769), outer),
        (-75, 42, -24),
        start=radial((-75, 42), (-81.154, 27.231), outer),
    )
    p.add(2, radial((-75, 42), (-60.231, 48.154), outer), (-75, 42, -24))
    p.add(3, (-51 - tangent, 46, -24), (-51, 52, -24), start=radial((-51, 52), (-60.231, 48.154), inner))
    p.add(1, (51 + tangent, 46, -24))
    p.add(3, radial((51, 52), (60.231, 48.154), inner), (51, 52, -24))
    p.add(2, radial((75, 42), (89.769, 35.846), outer), (75, 42, -24), start=radial((75, 42), (60.231, 48.154), outer))
    p.add(2, radial((75, 42), (81.154, 27.231), outer), (75, 42, -24))
    p.add(3, (79, 18 + tangent, -24), (85, 18, -24), start=radial((85, 18), (81.154, 27.231), inner))
    p.add(1, (79, -48, -24))
    p.add(2, (65, -62, -24), (65, -48, -24))
    p.add(1, (0, -62, -24))
    p.add(3, (-8.4, -70.4, -24), (0, -70.4, -24))
    for move, end in [(1, (-8, -74.4, -24)), (0, (-8, -74.4, 15)), (0, (-8, -74.4, 0)), (0, (0, 0, 0))]:
        p.add(move, end)
    return p.rows


def reference(name):
    if name in {"terraced_ramp", "ramped_surface", "incremental_xyz_raster"}:
        return _linear(name)
    if name in {"macro_boss_milling", "macro_hole_milling"}:
        return _macro_circles(name)
    if name in {"helical_bore", "inch_spiral", "radius_arc_ramp", "multiplane_edges", "mixed_ijk_r_planes"}:
        return _arcs(name)
    if name in {"tapping_fanuc", "polar_drilling"}:
        return _drilling(name)
    return {
        "wcs_test": _wcs,
        "macro_b": _macro_expressions,
        "subprogram": _subprogram,
        "macro_face_milling": _face,
        "correction_fanuc": _correction,
    }[name]()


def bounds(rows):
    points = [row[start : start + 3] for row in rows for start in (1, 4)]
    for row in rows:
        if row[7] is None:
            continue
        u, v = {17: (0, 1), 18: (2, 0), 19: (1, 2)}[row[7]]
        center, radius = row[8:11], row[11]
        start_angle = math.atan2(row[1 + v] - center[v], row[1 + u] - center[u])
        for angle in (0, math.pi / 2, math.pi, 3 * math.pi / 2):
            progress = (angle - start_angle) % (2 * math.pi) if row[0] == 3 else (start_angle - angle) % (2 * math.pi)
            if progress <= row[12] + 1e-12:
                point = list(row[1:4])
                point[u], point[v] = center[u] + radius * math.cos(angle), center[v] + radius * math.sin(angle)
                points.append(point)
    return tuple(extreme(p[axis] for p in points) for axis in range(3) for extreme in (min, max))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="Candidate directory outside tests/golden/milling")
    output = parser.parse_args().out.resolve()
    if output == GOLDEN or GOLDEN in output.parents:
        parser.error("Generate candidates outside the accepted golden directory; review and copy explicitly")
    reviewed = {}
    for name in COUNTS:
        result = run_fixture(name)
        assert result.ok and result.complete and result.program_end == "M30", (name, result.diagnostics)
        assert not result.diagnostics, (name, result.diagnostics)
        actual, expected = coordinates(result.motions), reference(name)
        assert_same_geometry(actual, expected, name)
        assert all(
            a is None or abs(a - b) < 1e-8
            for motion, reference_row in zip(actual, expected, strict=True)
            for a, b in zip(motion, reference_row, strict=True)
        ), (name, "analytic review requires absolute error below 1e-8")
        # Independent checks of complete primitives, including bounds and circle equations.
        assert bounds(actual) == pytest.approx(bounds(expected), abs=1e-8), name
        for row in actual:
            assert all(value is None or math.isfinite(value) for value in row), name
            if row[7] is not None:
                axes = {17: (0, 1), 18: (0, 2), 19: (1, 2)}[row[7]]
                for point in (row[1:4], row[4:7]):
                    distance = math.hypot(*(point[a] - row[8 + a] for a in axes))
                    assert abs(distance - row[11]) < 1e-8, (name, row)
        reviewed[name] = actual
        print(f"{name}: {len(actual)} movements; bounds={bounds(expected)}; diagnostics=[]")
    output.mkdir(parents=True, exist_ok=True)
    for name, rows in reviewed.items():
        with (output / f"{name}.csv").open("w", encoding="ascii", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(HEADER)
            writer.writerows(tuple("" if v is None else format(v, ".12g") for v in row) for row in rows)


if __name__ == "__main__":
    main()
