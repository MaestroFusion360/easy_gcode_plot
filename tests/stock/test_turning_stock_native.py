"""Compiled turning geometry must match the source reference, including real cycle playback."""

# pylint: disable=protected-access

import random
from copy import deepcopy
from statistics import median
from time import perf_counter

import numpy as np
import pytest

from app.gcode.execution.program import execute_program
from app.gcode.stock import TurningStockSpec, TurningStockTimeline, turning_collision, turning_stock


@pytest.fixture(scope="module")
def native():
    return pytest.importorskip("app.gcode.stock._native_turning_collision")


def _polygons_close(first, second, tolerance=1e-9):
    """Compare convex boundaries independent of vertex order and collinear vertices."""
    if not first or not second:
        return not first and not second
    for source, target in ((first, second), (second, first)):
        points = np.asarray(source, dtype=float)
        starts = np.asarray(target, dtype=float)
        edges = np.roll(starts, -1, axis=0) - starts
        lengths_squared = np.sum(edges * edges, axis=1)
        offsets = points[:, None, :] - starts
        progress = np.sum(offsets * edges, axis=2) / np.where(lengths_squared > 0, lengths_squared, 1)
        nearest = starts + np.clip(progress, 0, 1)[:, :, None] * edges
        distances = np.linalg.norm(points[:, None, :] - nearest, axis=2)
        if not np.all(np.min(distances, axis=1) <= tolerance):
            return False
    return True


def _regions_close(first, second):
    """Compare damage regions as geometric sets, ignoring duplicate polygons."""
    return all(
        any(_polygons_close(polygon, candidate) for candidate in target)
        for source, target in ((first, second), (second, first))
        for polygon in source
    )


def test_region_comparison_ignores_duplicates_but_detects_missing_or_changed_shapes():
    square = ((0, 0), (2, 0), (2, 2), (0, 2))
    subdivided = ((2, 2), (2, 0), (1, 0), (0, 0), (0, 2), (2, 2))
    rounded = tuple((x + 1e-12, z) for x, z in subdivided)
    shifted = tuple((x + 1e-6, z) for x, z in square)
    assert _regions_close((square,), (subdivided, rounded))
    assert _regions_close((subdivided, rounded), (square,))
    assert _regions_close((), ())
    for first, second in (((square,), (square, shifted)), ((square,), (shifted,)), ((square,), ())):
        assert not _regions_close(first, second)
        assert not _regions_close(first=second, second=first)


def test_polygon_comparison_ignores_representation_but_detects_geometry_changes():
    square = ((0, 0), (2, 0), (2, 2), (0, 2))
    subdivided = ((2, 2), (2, 0), (1, 0), (0, 0), (0, 2), (2, 2))
    assert _polygons_close(square, subdivided)
    assert _polygons_close(square, tuple((x + 1e-12, z) for x, z in subdivided))
    assert not _polygons_close(square, tuple((x + 1e-6, z) for x, z in subdivided))
    assert not _polygons_close(square, ((0, 0), (2, 0), (0, 2)))


def test_native_clipping_matches_python_for_convex_sweeps_and_disconnected_bands(native):
    rng = random.Random(222)
    bands = (((0, -5), (4, -5), (5, 5), (1, 5)), ((7, -5), (10, -5), (10, 5), (6, 5)))
    regions = [(), ((4, -5), (7, -5), (7, 5), (5, 5))]
    regions.extend(
        turning_stock._convex_hull([(rng.uniform(-12, 12), rng.uniform(-10, 10)) for _ in range(12)])
        for _ in range(200)
    )
    for region in regions:
        expected = turning_collision._clip_regions_python((region,), bands)
        actual = native.clip_regions((region,), bands)
        assert _regions_close(actual, expected)


def test_native_profile_spans_match_existing_horizontal_intersections(native):
    rng = random.Random(221)
    z = [i * 0.1 for i in range(-100, 101)]
    for _ in range(50):
        polygon = turning_stock._convex_hull([(rng.uniform(-10, 10), rng.uniform(-8, 8)) for _ in range(16)])
        expected = [(i, span) for i, value in enumerate(z) if (span := turning_stock._horizontal_span(polygon, value))]
        actual = native.swept_profile_spans(polygon, z, 0, len(z) - 1)
        assert [i for i, _span in actual] == [i for i, _span in expected]
        np.testing.assert_allclose(
            [span for _i, span in actual], [span for _i, span in expected], rtol=1e-13, atol=1e-13
        )
    assert native.swept_profile_spans((), z, 0, 1) == []
    with pytest.raises(IndexError):
        native.swept_profile_spans(polygon, z, -1, len(z))


def test_basic_turning_cycles_native_matches_python_and_rewind(native, fixture_text, monkeypatch):
    result, tools, _ = execute_program(fixture_text("turning/basic_turning_cycles.NC"), language="fanuc_turn")
    assert result.ok and result.complete
    spec = TurningStockSpec(305, 225.7, resolution=0.5, front_z=1)
    counts = [0, 53, 366, 599, 718, 938, 1162, 1717, 2475, 3000, 3989, len(result.motions), 599, 0, len(result.motions)]
    monkeypatch.setattr(turning_collision, "_native_clip_regions", native.clip_regions)
    monkeypatch.setattr(turning_stock, "_native_swept_profile_spans", native.swept_profile_spans)
    accelerated = TurningStockTimeline(result.motions, spec, tools)
    expected = []
    native_states = {}
    for count in counts:
        accelerated.set_motion_count(count)
        state = deepcopy((accelerated.material_intervals, accelerated.collision_regions))
        if count in native_states:
            assert state == native_states[count], f"Native rewind diverged at motion_count={count}"
        native_states[count] = state
        expected.append(state)
    monkeypatch.setattr(turning_collision, "_native_clip_regions", None)
    monkeypatch.setattr(turning_stock, "_native_swept_profile_spans", None)
    reference = TurningStockTimeline(result.motions, spec, tools)
    python_states = {}
    for count, (material, regions) in zip(counts, expected, strict=True):
        reference.set_motion_count(count)
        state = deepcopy((reference.material_intervals, reference.collision_regions))
        if count in python_states:
            assert state == python_states[count], f"Python rewind diverged at motion_count={count}"
        python_states[count] = state
        assert len(reference.material_intervals) == len(material)
        for slice_index, (actual_intervals, native_intervals) in enumerate(
            zip(reference.material_intervals, material, strict=True)
        ):
            assert len(actual_intervals) == len(native_intervals), (count, slice_index)
            np.testing.assert_allclose(
                actual_intervals,
                native_intervals,
                rtol=0,
                atol=1e-12,
                err_msg=f"motion_count={count}, slice={slice_index}",
            )
        assert reference.collision_regions.keys() == regions.keys()
        for index, polygons in regions.items():
            reference_polygons = reference.collision_regions[index]
            assert _regions_close(polygons, reference_polygons), (
                f"motion_count={count}, collision={index}: native/Python damage geometry differs "
                f"({len(polygons)} native polygons, {len(reference_polygons)} Python polygons)"
            )


@pytest.mark.performance
def test_basic_turning_cycles_keeps_native_speedup(native, fixture_text, monkeypatch, record_property):
    result, tools, _ = execute_program(fixture_text("turning/basic_turning_cycles.NC"), language="fanuc_turn")
    spec = TurningStockSpec(305, 225.7, resolution=0.5, front_z=1)
    samples = {True: [], False: []}
    for repeat in range(3):
        for accelerated in (True, False) if repeat % 2 == 0 else (False, True):
            monkeypatch.setattr(turning_collision, "_native_clip_regions", native.clip_regions if accelerated else None)
            monkeypatch.setattr(
                turning_stock, "_native_swept_profile_spans", native.swept_profile_spans if accelerated else None
            )
            stock = TurningStockTimeline(result.motions, spec, tools)
            started = perf_counter()
            stock.set_motion_count(len(result.motions))
            samples[accelerated].append(perf_counter() - started)
    ratio = median(samples[True]) / median(samples[False])
    record_property("native_to_python_turning_ratio", ratio)
    assert ratio < 0.65, f"Native turning stock lost its speedup on basic_turning_cycles.NC: ratio={ratio:.3f}"
