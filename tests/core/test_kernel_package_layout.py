"""Contracts for the modular ``app.gcode.kernel`` package layout.

These tests pin the canonical package structure introduced by the structural
refactor and the thin compatibility shims that keep historical module paths
working for callers.
"""

from __future__ import annotations

# Local imports keep the canonical-vs-alias comparisons explicit per test.
# pylint: disable=import-outside-toplevel
import importlib

import pytest

from app.gcode import kernel

LEGACY_REEXPORTS = [
    ("app.gcode.kernel.model", "Motion", "app.gcode.kernel.frontend.model"),
    ("app.gcode.kernel.ast", "MotionAstNode", "app.gcode.kernel.frontend.ast"),
    ("app.gcode.kernel.lang", "lex_words", "app.gcode.kernel.frontend.lang"),
    ("app.gcode.kernel.program", "parse_program", "app.gcode.kernel.frontend.program"),
    ("app.gcode.kernel.io", "read_nc_text", "app.gcode.kernel.frontend.io"),
    ("app.gcode.kernel.api_types", "ExecutionResult", "app.gcode.kernel.api.types"),
    ("app.gcode.kernel.api_conversion", "trace_motion", "app.gcode.kernel.api.conversion"),
    ("app.gcode.kernel.resources", "SemanticError", "app.gcode.kernel.api.resources"),
    ("app.gcode.kernel.geometry", "resolve_arc", "app.gcode.kernel.geometry.arcs"),
    ("app.gcode.kernel.profile", "build_profile_segments", "app.gcode.kernel.geometry"),
    ("app.gcode.kernel.coordinates", "milling_wcs_offsets", "app.gcode.kernel.geometry.coordinates"),
    ("app.gcode.kernel.events", "PROGRAM_START", "app.gcode.kernel.runtime.events"),
    ("app.gcode.kernel.signals", "signals_for_words", "app.gcode.kernel.runtime.signals"),
    ("app.gcode.kernel.execution", "classify_block_codes", "app.gcode.kernel.runtime.execution"),
    ("app.gcode.kernel.diagnostics", "diagnostic_from_exception", "app.gcode.kernel.runtime.diagnostics"),
    ("app.gcode.kernel.trace_metadata", "threading_step_flags", "app.gcode.kernel.runtime.trace_metadata"),
    ("app.gcode.kernel.interpreter", "dispatch_motion_block", "app.gcode.kernel.runtime.interpreter.dispatch"),
    ("app.gcode.kernel.interpreter_types", "TraceRuntimeState", "app.gcode.kernel.runtime.interpreter.types"),
    ("app.gcode.kernel.trace", "build_source_motion_trace_with_steps", "app.gcode.kernel.runtime.trace"),
]


@pytest.mark.parametrize(("legacy_name", "attribute", "canonical_name"), LEGACY_REEXPORTS)
def test_legacy_module_paths_reexport_canonical_objects(legacy_name, attribute, canonical_name):
    legacy = importlib.import_module(legacy_name)
    canonical = importlib.import_module(canonical_name)
    assert getattr(legacy, attribute) is getattr(canonical, attribute)


def test_historical_package_root_exports_remain_available():
    from app.gcode.kernel.api import SUPPORTED_LANGUAGES
    from app.gcode.kernel.milling import MillState
    from app.gcode.kernel.runtime import CycleContext, CycleOutcome, apply_cycle_outcome, expand_cycle_block
    from app.gcode.kernel.turning.cycles import (
        add_feed_orthogonal,
        add_motion,
        add_motion_with_meta,
        add_rapid_orthogonal,
    )

    assert SUPPORTED_LANGUAGES == frozenset({"fanuc_turn", "fanuc_mill"})
    assert MillState.__module__ == "app.gcode.kernel.milling.state"
    assert expand_cycle_block.__module__ == "app.gcode.kernel.runtime.expansion.engine"
    assert CycleContext.__module__ == "app.gcode.kernel.runtime.cycles"
    assert CycleOutcome.__module__ == "app.gcode.kernel.runtime.cycles"
    assert apply_cycle_outcome.__module__ == "app.gcode.kernel.runtime.cycles"
    assert add_motion.__module__ == "app.gcode.kernel.turning.cycles.common"
    assert add_motion_with_meta.__module__ == "app.gcode.kernel.turning.cycles.common"
    assert add_feed_orthogonal.__module__ == "app.gcode.kernel.turning.cycles.common"
    assert add_rapid_orthogonal.__module__ == "app.gcode.kernel.turning.cycles.common"


def test_public_facade_is_the_canonical_api_engine():
    from app.gcode.kernel.api.engine import execute as canonical_execute

    assert kernel.execute is canonical_execute


def test_split_modules_own_one_responsibility():
    from app.gcode.kernel.geometry import direct, profile_arcs, profile_clip
    from app.gcode.kernel.milling import executor as milling_executor
    from app.gcode.kernel.milling import motion as milling_motion
    from app.gcode.kernel.milling import state as milling_state
    from app.gcode.kernel.runtime import execution, trace
    from app.gcode.kernel.runtime.expansion import (
        drilling,
        finishing,
        peck,
        roughing,
        threading,
        turning,
    )
    from app.gcode.kernel.runtime.expansion import (
        engine as expansion_engine,
    )
    from app.gcode.kernel.runtime.interpreter import dispatch
    from app.gcode.kernel.runtime.interpreter import engine as interpreter_engine

    assert callable(expansion_engine.expand_cycle_block)
    assert callable(turning._expand_g90)  # pylint: disable=protected-access
    assert callable(drilling._expand_g83)  # pylint: disable=protected-access
    assert callable(roughing._expand_g71)  # pylint: disable=protected-access
    assert callable(peck._expand_g74)  # pylint: disable=protected-access
    assert callable(threading._expand_g76)  # pylint: disable=protected-access
    assert callable(finishing._expand_g70)  # pylint: disable=protected-access
    assert callable(direct.build_profile_segments)
    assert callable(profile_arcs.arc_center_from_r)
    assert callable(profile_clip.try_find_entry_on_profile)
    assert callable(dispatch.dispatch_motion_block)
    assert callable(interpreter_engine.execute_trace_step)
    assert callable(milling_executor.execute_milling)
    assert callable(milling_motion._emit_milling_motions)  # pylint: disable=protected-access
    assert callable(milling_state._apply_pre_flow_modal_state)  # pylint: disable=protected-access
    assert callable(execution.dispatch_macro_flow)
    assert callable(trace.build_source_motion_trace_with_steps)


def test_milling_public_entry_point_matches_package_reexport():
    from app.gcode.kernel.milling import execute_milling as package_entry
    from app.gcode.kernel.milling.executor import execute_milling as module_entry

    assert package_entry is module_entry


def test_historical_cycle_packages_alias_canonical_modules():
    legacy_turning = importlib.import_module("app.gcode.kernel.lathe_cycles.g71")
    canonical_turning = importlib.import_module("app.gcode.kernel.turning.cycles.g71")
    legacy_milling = importlib.import_module("app.gcode.kernel.milling.drilling")
    canonical_milling = importlib.import_module("app.gcode.kernel.milling.cycles.drilling")

    assert legacy_turning is canonical_turning
    assert legacy_milling is canonical_milling
