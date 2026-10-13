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
        assert len(actual) == len(expected)
        for result, reference in zip(actual, expected, strict=True):
            np.testing.assert_allclose(result, reference, rtol=1e-13, atol=1e-13)


def test_native_profile_spans_match_existing_horizontal_intersections(native):
    rng = random.Random(221)
    z = [i * 0.1 for i in range(-100, 101)]
    for _ in range(50):
        polygon = turning_stock._convex_hull([(rng.uniform(-10, 10), rng.uniform(-8, 8)) for _ in range(16)])
        expected = [(i, span) for i, value in enumerate(z) if (span := turning_stock._horizontal_span(polygon, value))]
        actual = native.swept_profile_spans(polygon, z, 0, len(z) - 1)
        assert [i for i, _span in actual] == [i for i, _span in expected]
        np.testing.assert_array_equal([span for _i, span in actual], [span for _i, span in expected])
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
    for count in counts:
        accelerated.set_motion_count(count)
        expected.append(deepcopy((accelerated.material_intervals, accelerated.collision_regions)))
    monkeypatch.setattr(turning_collision, "_native_clip_regions", None)
    monkeypatch.setattr(turning_stock, "_native_swept_profile_spans", None)
    reference = TurningStockTimeline(result.motions, spec, tools)
    for count, (material, regions) in zip(counts, expected, strict=True):
        reference.set_motion_count(count)
        assert reference.material_intervals == material
        assert reference.collision_regions.keys() == regions.keys()
        for index, polygons in regions.items():
            assert len(reference.collision_regions[index]) == len(polygons)
            for actual, python in zip(polygons, reference.collision_regions[index], strict=True):
                np.testing.assert_allclose(actual, python, rtol=1e-13, atol=1e-13)


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
