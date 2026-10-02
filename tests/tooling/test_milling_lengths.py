"""Milling length partitions, legacy compatibility and persistent geometry."""

import math

import pytest

from app.tools.definitions import MILLING_TOOL_TYPES
from app.tools.discovery import discover_tools
from app.tools.library import KIND_MILLING, ToolLibrary
from app.tools.milling_geometry import milling_geometry, milling_geometry_key, milling_tool_profile
from app.tools.milling_lengths import milling_lengths
from app.tools.validation import normalized_milling_tools, normalized_tools


@pytest.mark.parametrize("tool_type", sorted(MILLING_TOOL_TYPES))
def test_split_lengths_are_authoritative_for_every_milling_type(tool_type):
    raw = {"type": tool_type, "diameter": 10, "fluteLength": 25, "bodyLength": 15, "length": 999}
    spec = normalized_milling_tools({"T1": raw})["T1"]
    assert spec["fluteLength"] == 25
    assert spec["bodyLength"] == 15
    assert spec["length"] == 40
    assert "shaftLength" not in spec
    assert raw["length"] == 999
    assert milling_geometry(raw)["length"] == 40
    profile = milling_tool_profile(spec)
    assert max(z for z, _radius in profile) == 40
    assert any(z == 25 for z, _radius in profile)
    assert profile[-1][0] == 40
    assert all(left[0] <= right[0] for left, right in zip(profile, profile[1:]))


@pytest.mark.parametrize(
    "lengths",
    [
        {"fluteLength": 25},
        {"bodyLength": 15},
        {"fluteLength": 0, "bodyLength": 15},
        {"fluteLength": -1, "bodyLength": 15},
        {"fluteLength": 25, "bodyLength": -1},
        {"fluteLength": math.nan, "bodyLength": 15},
        {"fluteLength": 25, "bodyLength": math.inf},
        {"fluteLength": 1e308, "bodyLength": 1e308},
        {"fluteLength": None, "bodyLength": 15},
        {"fluteLength": "unknown", "bodyLength": 15},
    ],
)
def test_invalid_or_partial_split_cannot_fall_back_to_legacy_total(lengths):
    spec = {"type": "mill_flat", "diameter": 10, "length": 50, **lengths}
    assert milling_lengths(spec) is None
    assert normalized_milling_tools({"T1": spec}) == {}
    assert milling_geometry(spec) is None
    assert milling_tool_profile(spec) == ()


def test_zero_body_length_is_valid():
    spec = {"type": "mill_flat", "diameter": 10, "fluteLength": 25, "bodyLength": 0}
    assert normalized_milling_tools({"T1": spec})["T1"]["length"] == 25
    assert milling_tool_profile(spec) == ((0, 5), (25, 5))


def test_legacy_length_is_preserved_without_inventing_split():
    raw = {"type": "mill_flat", "diameter": 10, "length": 73}
    spec = normalized_milling_tools({"T1": raw})["T1"]
    assert milling_lengths(spec) == {"length": 73}
    assert "fluteLength" not in spec and "bodyLength" not in spec
    assert milling_tool_profile(spec) == ((0, 5), (73, 5))


@pytest.mark.parametrize("tool_type", ["face_mill", "slot_mill"])
def test_new_stepped_cutters_have_one_cutting_length(tool_type):
    raw = {"type": tool_type, "diameter": 40, "fluteLength": 12, "bodyLength": 58, "cuttingHeight": 60}
    spec = normalized_milling_tools({"T1": raw})["T1"]
    assert "cuttingHeight" not in spec
    profile = milling_tool_profile(spec)
    assert (12, 20) in profile
    assert (12, 12) in profile
    assert profile[-1] == (70, 12)


def test_small_flute_profile_does_not_exceed_cutting_length():
    spec = {"type": "slot_mill", "diameter": 10, "fluteLength": 0.05, "bodyLength": 1}
    profile = milling_tool_profile(spec)
    assert (0.05, 5) in profile and (0.05, 3) in profile
    assert profile[-1] == (1.05, 3)
    assert all(left[0] <= right[0] for left, right in zip(profile, profile[1:]))


def test_taper_ends_at_flute_and_body_is_cylindrical():
    spec = {"type": "taper_ball_mill", "diameter": 6, "taperAngle": 6, "fluteLength": 20, "bodyLength": 30}
    profile = milling_tool_profile(spec)
    assert profile[-2][0] == 20
    assert profile[-1] == (50, profile[-2][1])
    other = {**spec, "fluteLength": 30, "bodyLength": 20}
    assert milling_geometry_key(spec) != milling_geometry_key(other)
    assert milling_tool_profile(other)[-1][1] > profile[-1][1]


def test_split_survives_sqlite_round_trip_and_loading_does_not_migrate_legacy(tmp_path):
    legacy = {"type": "mill_flat", "diameter": 10, "length": 73}
    split = normalized_milling_tools(
        {"T2": {"type": "mill_flat", "diameter": 10, "fluteLength": 25, "bodyLength": 15}}
    )["T2"]
    path = str(tmp_path / "tools.db")
    with ToolLibrary(path) as library:
        library.save_tool(KIND_MILLING, "T1", legacy)
        library.save_tool(KIND_MILLING, "T2", split)
    with ToolLibrary(path) as library:
        before = library.tools_by_kind(KIND_MILLING)
        loaded = normalized_milling_tools(before)
        assert loaded["T2"] == split
        assert milling_lengths(loaded["T1"]) == {"length": 73}
        assert library.tools_by_kind(KIND_MILLING) == before


def test_turning_axial_lengths_are_unchanged():
    spec = normalized_tools({"T0101": {"type": "drill", "diameter": 10, "length": 73}})["T0101"]
    assert spec["length"] == 73
    assert "fluteLength" not in spec and "bodyLength" not in spec


def test_discovery_converts_explicit_pair_to_metric_and_total_alone_stays_unsplit():
    tools = discover_tools("G20\nT1 (FLAT END MILL D.25 FL1 BL.5)\nG21\nT2 (TAPER BALL MILL D6 L73)\n", turning=False)
    assert tools["T1"]["fluteLength"] == pytest.approx(25.4)
    assert tools["T1"]["bodyLength"] == pytest.approx(12.7)
    assert tools["T1"]["length"] == pytest.approx(38.1)
    assert milling_lengths(tools["T2"]) == {"length": 73}
