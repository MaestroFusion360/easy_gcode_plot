"""Rapid damage geometry, remaining material and reversible turning playback."""

import math
from copy import deepcopy

import pytest

from app.gcode.kernel import TraceMotion
from app.gcode.kernel.api_types import ArcGeometry
from app.gcode.stock import TurningStockSpec, TurningStockTimeline, turning_collision
from app.gcode.stock.turning_collision import polygon_area

TOOL = {"type": "groove", "width": 1, "insertLength": 2, "noseRadius": 0, "tipOrientation": 3}


def motion(move, x0=8, z0=3, x1=8, z1=-13):
    return TraceMotion(move, x0, z0, x1, z1, tool="T0101", x_scale=0.5)


def timeline(motions, **stock):
    return TurningStockTimeline(
        motions, TurningStockSpec(outer_diameter=20, length=10, resolution=0.5, **stock), {"T0101": TOOL}
    )


def area(stock):
    return sum(abs(polygon_area(polygon)) for regions in stock.collision_regions.values() for polygon in regions)


def test_rapid_marks_whole_swept_path_with_endpoints_outside_without_removal():
    stock = timeline([motion(0)])
    before = deepcopy((stock.inner, stock.outer, stock.material_intervals, stock.profile_breaks))
    stock.set_motion_count(1)
    assert area(stock) == pytest.approx(20)
    assert (stock.inner, stock.outer, stock.material_intervals, stock.profile_breaks) == before
    assert stock.revision == 1
    # Only the intersected radial band is marked, rather than the complete slice.
    assert {x for regions in stock.collision_regions.values() for polygon in regions for x, _z in polygon} == {4, 6}


def test_rapid_in_previously_removed_band_has_no_collision():
    stock = timeline([motion(1), motion(0)])
    stock.set_motion_count(1)
    before = deepcopy(stock.material_intervals)
    stock.set_motion_count(2)
    assert not stock.collision_regions
    assert stock.material_intervals == before


def test_rapid_inside_existing_bore_has_no_collision():
    stock = timeline([motion(0, x0=0, x1=0)], inner_diameter=8)
    stock.set_motion_count(1)
    assert not stock.collision_regions


def test_rapid_across_disconnected_material_marks_each_band_and_not_the_gap():
    stock = timeline([motion(1), motion(0, x0=4, z0=-5, x1=20, z1=-5)])
    stock.set_motion_count(2)
    assert area(stock) == pytest.approx(6)
    radial_ranges = {
        (min(x for x, _z in polygon), max(x for x, _z in polygon))
        for regions in stock.collision_regions.values()
        for polygon in regions
    }
    assert radial_ranges == {(2, 4), (6, 10)}


@pytest.mark.parametrize("x", [20, -24])
def test_radial_boundary_tangency_is_not_a_collision(x):
    stock = timeline([motion(0, x0=x, x1=x)])
    stock.set_motion_count(1)
    assert not stock.collision_regions


def test_front_face_tangency_is_not_a_collision():
    stock = timeline([motion(0, x0=0, z0=0, x1=16, z1=0)])
    stock.set_motion_count(1)
    assert not stock.collision_regions


def test_damage_survives_departure_and_is_clipped_by_later_cutting():
    stock = timeline(
        [
            motion(0),
            motion(0, x0=40, z0=3, x1=40, z1=-13),
            motion(1, x0=10, x1=10),
            motion(1),
        ]
    )
    stock.set_motion_count(1)
    marked = deepcopy(stock.collision_regions)
    stock.set_motion_count(2)
    assert stock.collision_regions == marked
    stock.set_motion_count(3)
    assert area(stock) == pytest.approx(10)
    assert all(x <= 5 for regions in stock.collision_regions.values() for polygon in regions for x, _z in polygon)
    stock.set_motion_count(4)
    assert not stock.collision_regions
    stock.set_motion_count(2)
    assert stock.collision_regions == marked


def test_arbitrary_seek_and_repeated_playback_restore_exact_damage_without_duplicates():
    motions = [motion(0), motion(1, x0=10, x1=10), motion(0, x0=16, x1=16), motion(1)]
    stock = timeline(motions)
    states = []
    for count in range(len(motions) + 1):
        stock.set_motion_count(count)
        states.append(deepcopy((stock.material_intervals, stock.collision_regions)))
    for count in [0, 4, 1, 3, 2, 4, 0, 1, 4, 2]:
        stock.set_motion_count(count)
        assert (stock.material_intervals, stock.collision_regions) == states[count]
        revision = stock.revision
        stock.set_motion_count(count)
        assert stock.revision == revision
    assert not timeline(motions).collision_regions


def test_diagonal_collision_keeps_actual_swept_edges_inside_profile_cells():
    stock = timeline([motion(0, x0=0, z0=-5.2, x1=16, z1=-1.2)])
    stock.set_motion_count(1)
    assert stock.collision_regions
    # Exact clipping retains the sub-cell start, rather than marking its whole Z cell.
    assert min(z for regions in stock.collision_regions.values() for p in regions for _x, z in p) == pytest.approx(-5.2)
    assert any(
        a[0] != b[0] and a[1] != b[1]
        for regions in stock.collision_regions.values()
        for polygon in regions
        for a, b in zip(polygon, (*polygon[1:], polygon[0]))
    )


def test_rapid_on_negative_x_uses_the_same_axisymmetric_material():
    stock = timeline([motion(0, x0=-12, x1=-12)])
    stock.set_motion_count(1)
    assert area(stock) == pytest.approx(20)
    assert all(4 <= x <= 6 for regions in stock.collision_regions.values() for p in regions for x, _z in p)


@pytest.mark.parametrize("move", [2, 3])
def test_arc_cut_clips_damage_without_changing_cutting_result(move):
    cut = TraceMotion(
        move,
        10,
        -2,
        10,
        -6,
        tool="T0101",
        x_scale=0.5,
        arc=ArcGeometry((5, 0, -4), 2, math.pi, 18, clockwise=move == 2, full_circle=False),
    )
    stock = timeline([motion(0), cut])
    stock.set_motion_count(1)
    marked = deepcopy(stock.collision_regions)
    stock.set_motion_count(2)
    assert 0 < area(stock) < 20
    reference = timeline([cut])
    reference.set_motion_count(1)
    assert stock.material_intervals == reference.material_intervals
    assert stock.profile_breaks == reference.profile_breaks
    stock.set_motion_count(1)
    assert stock.collision_regions == marked


@pytest.mark.parametrize(
    "tool_type", ["diamond_80", "diamond_35", "square", "triangle", "round", "groove", "thread", "drill", "tap"]
)
def test_rapid_uses_existing_geometry_for_all_supported_turning_tools(tool_type):
    tool = {**TOOL, "type": tool_type, "diameter": 4, "length": 12}
    stock = TurningStockTimeline([motion(0)], TurningStockSpec(20, 10, resolution=0.5), {"T0101": tool})
    stock.set_motion_count(1)
    assert stock.collision_regions
    assert stock.material_intervals == stock.initial_material_intervals


def test_same_rapid_sweep_does_not_duplicate_existing_regions():
    stock = timeline([motion(0), motion(0)])
    stock.set_motion_count(1)
    marked = deepcopy(stock.collision_regions)
    stock.set_motion_count(2)
    assert stock.collision_regions == marked


def test_rapid_does_not_reclip_existing_damage_or_rebuild_unchanged_sections(monkeypatch):
    stock = timeline([motion(0), motion(0)])
    stock.set_motion_count(1)
    sections = {index: cached[1] for index, cached in stock._material_section_cache.items()}  # pylint: disable=protected-access
    clip = turning_collision.clip_regions
    calls = []

    def record(regions, bands):
        # One sweep and its mirror; previously stored marks must not be added here.
        assert len(regions) == 2
        calls.append(regions)
        return clip(regions, bands)

    monkeypatch.setattr(turning_collision, "clip_regions", record)
    stock.set_motion_count(2)
    assert calls
    assert all(stock._material_section_cache[index][1] is section for index, section in sections.items())  # pylint: disable=protected-access
