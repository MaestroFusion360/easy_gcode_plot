"""Analytically review iTNC candidates; never overwrite accepted CSVs.

Uses the existing milling CSV format, path notation and comparison helper.
See heidenhain/README.md for scenarios awaiting full-trajectory acceptance.
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
from generate import _Path, bounds  # noqa: E402
from test_fanuc import GOLDEN, HEADER, assert_same_geometry, coordinates  # noqa: E402
from test_itnc_golden import COUNTS, ENDS, assert_execution, run_fixture  # noqa: E402

# pylint: enable=wrong-import-position


def _base():
    p = _Path()
    for move, end in [
        (0, (0, 0, 100)),
        (0, (-72, -72, 100)),
        (0, (-72, -72, 2)),
        (1, (-72, -72, -10)),
        (1, (-40, -72, -10)),
        (1, (-40, 30, -10)),
        (1, (40, 30, -10)),
        (1, (40, -30, -10)),
        (1, (-40, -30, -10)),
        (1, (-40, -72, -10)),
        (0, (-40, -72, 200)),
        (0, (-40, -72, 0)),
    ]:
        p.add(move, end)
    return p.rows


def _bore():
    p = _Path()
    p.add(0, (0, 0, 15))
    p.add(1, (0, 0, 2))
    p.add(1, (0, 0, 0))
    p.add(1, (7, 0, 0))

    def turns(radius, instructions):
        angle = 0
        for degrees, z in instructions:
            angle += degrees
            end = radius * math.cos(math.radians(angle)), radius * math.sin(math.radians(angle)), z
            p.add(3, end, (0, 0, p.point[2]), sweep=math.radians(degrees), full_circle=degrees % 360 == 0)

    turns(7, [(5400, -7.333), (2699.969, -11), (360, -11)])
    p.add(1, (0, 0, -11))
    for z in (5, 15, 2, 0):
        p.add(1, (0, 0, z))
    p.add(1, (10, 0, 0))
    turns(10, [(2834.989, -5.5), (2834.989, -11), (360, -11)])
    p.add(1, (0, 0, -11))
    p.add(1, (0, 0, 15))
    return p.rows


def _roundings():
    p = _Path()
    for move, end in [(0, (0, 0, 100)), (0, (-30, 70, 100)), (0, (-30, 70, 2)), (1, (-30, 70, -5)), (1, (7, 70, -5))]:
        p.add(move, end)
    vertices = [(10, 70), (10, 90), (70, 90), (90, 50), (90, 10), (50, 10), (10, 50), (10, 70)]
    # Nominal trim t=R*tan(theta/2). All corners turn clockwise, so RL/R3
    # increases each RND radius by 3 while retaining its nominal center.
    for a, vertex, b, radius in zip(vertices, vertices[1:], vertices[2:], (10, 5, 5, 10, 5, 5)):
        incoming = vertex[0] - a[0], vertex[1] - a[1]
        outgoing = b[0] - vertex[0], b[1] - vertex[1]
        u, v = [tuple(c / math.hypot(*vector) for c in vector) for vector in (incoming, outgoing)]
        theta = math.acos(max(-1, min(1, u[0] * v[0] + u[1] * v[1])))
        trim = radius * math.tan(theta / 2)
        start = vertex[0] - trim * u[0], vertex[1] - trim * u[1]
        end = vertex[0] + trim * v[0], vertex[1] + trim * v[1]
        center = start[0] + u[1] * radius, start[1] - u[0] * radius
        factor = (radius + 3) / radius
        shifted_start = tuple(center[i] + (start[i] - center[i]) * factor for i in range(2))
        shifted_end = tuple(center[i] + (end[i] - center[i]) * factor for i in range(2))
        p.add(1, (*shifted_start, -5))
        p.add(2, (*shifted_end, -5), (*center, -5))
    p.add(1, (7, 70, -5))
    p.add(1, (-30, 70, -5))
    p.add(0, (-30, 70, 100))
    return p.rows


def _chamfers():
    p = _Path()
    q = 3 / math.sqrt(2)
    # CHF10 trims 10 along each adjacent line; CHF20 trims 20. RL offsets
    # the diagonal by R3, with component shift 3/sqrt(2), not by 3 on each axis.
    for move, end, center in [
        (0, (0, 0, 250), None),
        (0, (-10, -10, 250), None),
        (1, (-10, -10, -5), None),
        (1, (2, -5, -5), None),
        (1, (2, 5, -5), None),
        (1, (2, 95, -5), None),
        (2, (5, 98, -5), (5, 95, -5)),
        (1, (85, 98, -5), None),
        (2, (85 + q, 95 + q, -5), (85, 95, -5)),
        (1, (95 + q, 85 + q, -5), None),
        (2, (98, 85, -5), (95, 85, -5)),
        (1, (98, 25, -5), None),
        (2, (95 + q, 25 - q, -5), (95, 25, -5)),
        (1, (75 + q, 5 - q, -5), None),
        (2, (75, 2, -5), (75, 5, -5)),
        (1, (5, 2, -5), None),
        (1, (-5, 2, -5), None),
        (0, (-5, 5, 250), None),
    ]:
        p.add(move, end, center)
    return p.rows


def reference(name):
    return {"bore_itnc530": _bore, "itnc530_base_pgm": _base, "6bas154": _roundings, "manual_chf": _chamfers}[name]()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    output = parser.parse_args().out.resolve()
    if output == GOLDEN or GOLDEN in output.parents:
        parser.error("Generate outside the accepted golden directory, then review and copy explicitly")
    reviewed = {}
    for name, count in COUNTS.items():
        result = run_fixture(name)
        assert_execution(result, name, ENDS[name])
        actual, expected = coordinates(result.motions), reference(name)
        assert_same_geometry(actual, expected, name, motion_count=count)
        assert all(
            a is None or abs(a - b) < 1e-8
            for row, expected_row in zip(actual, expected, strict=True)
            for a, b in zip(row, expected_row, strict=True)
        ), (name, "analytic review requires absolute error below 1e-8")
        assert bounds(actual) == pytest.approx(bounds(expected), abs=1e-8), name
        assert all(v is None or math.isfinite(v) for row in actual for v in row), name
        for row in actual:
            if row[7] is not None:
                for point in (row[1:4], row[4:7]):
                    assert math.hypot(point[0] - row[8], point[1] - row[9]) == pytest.approx(row[11], abs=1e-8)
        reviewed[name] = actual
        print(
            f"{name}: {count} movements; bounds={bounds(expected)}; "
            f"diagnostics={[(d.code, d.line) for d in result.diagnostics]}"
        )
    output.mkdir(parents=True, exist_ok=True)
    for name, rows in reviewed.items():
        with (output / f"{name}.csv").open("w", encoding="ascii", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(HEADER)
            writer.writerows(tuple("" if v is None else format(v, ".12g") for v in row) for row in rows)
    print("cycles_itnc530: full CSV withheld; full-trajectory independent review is still required")


if __name__ == "__main__":
    main()
