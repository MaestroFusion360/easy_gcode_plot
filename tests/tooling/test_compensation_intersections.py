"""Regressions for compensation intersections at tangency and small scales."""

import math
import random

import pytest

from app.gcode.kernel.api.types import TraceMotion
from app.gcode.kernel.compensation.geometry import (
    TurningPrimitive,
    Vec2,
    line_circle_intersections,
    line_intersection,
)
from app.gcode.kernel.compensation.milling.engine import apply_milling_cutter_compensation
from app.gcode.kernel.compensation.milling.joins import _join_steady_motion, _line_arc_intersections
from app.gcode.kernel.compensation.milling.projection import _ProjectedMotion
from app.gcode.kernel.compensation.turning.joins import join_primitives
from app.gcode.kernel.frontend.model import Motion, Point2


def _primitives(domain, start, end, center, radius, contact):
    opposite = (2 * center[0] - contact[0], 2 * center[1] - contact[1])
    if domain == "milling":
        source = TraceMotion(1, 0, 0, 1, 0, plane=17)
        return (
            _ProjectedMotion(source, 17, start, end, 0, 0),
            _ProjectedMotion(source, 17, contact, opposite, 0, 0, center, radius),
        )
    source = Motion(1, Point2(0, 0), Point2(1, 0))
    return (
        TurningPrimitive(source, Vec2(*start), Vec2(*end)),
        TurningPrimitive(source, Vec2(*contact), Vec2(*opposite), Vec2(*center)),
    )


def _intersections(domain, line, arc):
    if domain == "milling":
        return _line_arc_intersections(line, arc)
    return [(point.x, point.y) for point in line_circle_intersections(line, arc)]


@pytest.mark.parametrize("domain", ["milling", "turning"])
@pytest.mark.parametrize("scale", [1e-4, 1.0, 1e3])
def test_rotated_translated_tangents_have_exactly_one_candidate(domain, scale):
    rng = random.Random(210)
    for _ in range(2000):
        center = (rng.uniform(-500, 500) * scale, rng.uniform(-500, 500) * scale)
        radius = rng.uniform(20, 300) * scale
        angle = rng.uniform(-math.pi, math.pi)
        nx, ny = math.cos(angle), math.sin(angle)
        contact = center[0] + radius * nx, center[1] + radius * ny
        length = rng.uniform(20, 500) * scale
        start = contact[0] + length * ny, contact[1] - length * nx
        end = contact[0] - length * ny, contact[1] + length * nx
        line, arc = _primitives(domain, start, end, center, radius, contact)
        points = _intersections(domain, line, arc)
        assert len(points) == 1
        assert points[0] == pytest.approx(contact, rel=0, abs=1e-9 * scale)


@pytest.mark.parametrize("domain", ["milling", "turning"])
@pytest.mark.parametrize("length", [1e-5, 10.0, 1e5])
@pytest.mark.parametrize("gap, count", [(-1e-6, 2), (0.0, 1), (1e-6, 0)])
def test_secants_and_separated_lines_are_not_confused_with_tangency(domain, length, gap, count):
    radius = 300.0
    height = radius + gap
    line, arc = _primitives(domain, (-length, height), (length, height), (0, 0), radius, (0, radius))
    points = _intersections(domain, line, arc)
    assert len(points) == count
    if count == 2:
        expected = math.sqrt((radius - height) * (radius + height))
        assert points[0] == pytest.approx((-expected, height))
        assert points[1] == pytest.approx((expected, height))


@pytest.mark.parametrize("domain", ["milling", "turning"])
def test_zero_length_line_does_not_produce_candidates(domain):
    line, arc = _primitives(domain, (0, 10), (0, 10), (0, 0), 10, (0, 10))
    assert _intersections(domain, line, arc) == []


@pytest.mark.parametrize("length", [1e-5, 1e-3, 1.0, 1e3])
def test_short_perpendicular_turning_lines_intersect(length):
    source = Motion(1, Point2(0, 0), Point2(1, 0))
    first = TurningPrimitive(source, Vec2(0, 0), Vec2(length, 0))
    second = TurningPrimitive(source, Vec2(length / 2, -length / 2), Vec2(length / 2, length / 2))
    assert line_intersection(first, second) == [Vec2(length / 2, 0)]


@pytest.mark.parametrize("domain", ["milling", "turning"])
def test_tangent_join_retargets_both_primitives_to_the_same_point(domain):
    # Rotated/translated tangent that the old quadratic calculation rejected.
    center = (-15.781046943586148, 348.53547696165754)
    start = (-102.36268604964846, 396.80104445771406)
    end = (-26.566590648801473, 249.99808668267917)
    contact = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
    radius = math.hypot(contact[0] - center[0], contact[1] - center[1])
    line, arc = _primitives(domain, start, end, center, radius, contact)
    if domain == "turning":
        point = join_primitives(line, arc)
        assert (point.x, point.y) == pytest.approx(contact)
    else:
        joined = _join_steady_motion(line, arc, 41, 1.0, 0.01)
        assert joined is not None
        previous, current, transition = joined
        assert previous.end == current.start
        assert current.start == pytest.approx(contact)
        assert transition is None


@pytest.mark.parametrize("angle", [30, 60, 90, 120])
def test_outside_corner_compensation_preserves_ramp_end_heights(angle):
    def motion(start, end):
        return TraceMotion(
            1,
            start[0],
            start[2],
            end[0],
            end[2],
            start_y=start[1],
            end_y=end[1],
            plane=17,
            compensation_mode=41,
            tool="T1",
        )

    dx, dy = 10 * math.cos(math.radians(angle)), -10 * math.sin(math.radians(angle))
    motions = [
        motion((-10, 0, 0), (0, 0, 0)),
        motion((0, 0, 0), (10, 0, 10)),
        motion((10, 0, 10), (10 + dx, dy, 15)),
    ]
    result = apply_milling_cutter_compensation(motions, {"T1": {"type": "mill_flat", "diameter": 2}})
    assert len(result) == 4
    assert result[1].end_x == pytest.approx(10)
    assert (result[1].start_z, result[1].end_z) == (0, 10)
    assert result[2].source_kind == "cutter_compensation_transition"
    assert (result[2].start_z, result[2].end_z) == (10, 10)
    assert (result[3].start_z, result[3].end_z) == (10, 15)
