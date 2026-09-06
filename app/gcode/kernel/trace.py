from __future__ import annotations

# Keyword assembly mirrors the execution-context contract directly.
# pylint: disable=use-dict-literal
from .interpreter import TraceRuntimeState, build_trace_execution_context, execute_trace_context_with_steps
from .tool_compensation import apply_tool_nose_compensation


def _build_trace_execution_kwargs(
    program,
    rough_cycles,
    finish_cycles,
    *,
    x_is_diameter: bool,
    pq_mm_for_g74758384: bool = False,
    supplementary_angles: bool = False,
    default_unit_scale: float = 1.0,
    skip_optional_blocks: bool,
    home_x: float,
    home_z: float,
    wcs_offsets: dict[int, tuple[float, float]] | None,
    emulate_g28_home: bool,
    eval_words_fn,
    try_wcs_from_gcode_fn,
    x_value_to_diameter_fn,
    x_delta_to_diameter_fn,
    motion_ctor,
    point_ctor,
) -> dict[str, object]:
    wcs_map = wcs_offsets or {}
    active_wcs = 54
    home_ox, home_oz = wcs_map.get(active_wcs, (0.0, 0.0))
    state = TraceRuntimeState(
        modal_x=float(home_x) - float(home_ox),
        modal_z=float(home_z) - float(home_oz),
        active_wcs=active_wcs,
        x_is_diameter=x_is_diameter,
        unit_scale=float(default_unit_scale),
    )

    def wcs_off(code: int) -> tuple[float, float]:
        return wcs_map.get(code, (0.0, 0.0))

    def to_machine(px: float, pz: float) -> tuple[float, float]:
        ox, oz = wcs_off(state.active_wcs)
        return px + ox, pz + oz

    ctx = build_trace_execution_context(program=program, initial_state=state, eval_words_fn=eval_words_fn)
    ctx.cycle_options = dict(pq_mm_for_g74758384=pq_mm_for_g74758384, supplementary_angles=supplementary_angles)
    return dict(
        program=program,
        ctx=ctx,
        rough_cycles=rough_cycles,
        finish_cycles=finish_cycles,
        skip_optional_blocks=skip_optional_blocks,
        emulate_g28_home=emulate_g28_home,
        x_is_diameter=x_is_diameter,
        home_x=home_x,
        home_z=home_z,
        eval_words_fn=eval_words_fn,
        try_wcs_from_gcode_fn=try_wcs_from_gcode_fn,
        to_machine_fn=to_machine,
        wcs_off_fn=wcs_off,
        x_value_to_diameter_fn=x_value_to_diameter_fn,
        x_delta_to_diameter_fn=x_delta_to_diameter_fn,
        motion_ctor=motion_ctor,
        point_ctor=point_ctor,
    )


def build_source_motion_trace_with_steps(
    program,
    rough_cycles,
    finish_cycles,
    *,
    x_is_diameter: bool,
    pq_mm_for_g74758384: bool = False,
    supplementary_angles: bool = False,
    default_unit_scale: float = 1.0,
    skip_optional_blocks: bool = False,
    home_x: float = 0.0,
    home_z: float = 0.0,
    wcs_offsets: dict[int, tuple[float, float]] | None = None,
    emulate_g28_home: bool = False,
    eval_words_fn,
    try_wcs_from_gcode_fn,
    x_value_to_diameter_fn,
    x_delta_to_diameter_fn,
    motion_ctor,
    point_ctor,
    tools: dict[str, dict[str, object]] | None = None,
):
    execution_kwargs = _build_trace_execution_kwargs(
        program,
        rough_cycles,
        finish_cycles,
        x_is_diameter=x_is_diameter,
        pq_mm_for_g74758384=pq_mm_for_g74758384,
        supplementary_angles=supplementary_angles,
        default_unit_scale=default_unit_scale,
        skip_optional_blocks=skip_optional_blocks,
        home_x=home_x,
        home_z=home_z,
        wcs_offsets=wcs_offsets,
        emulate_g28_home=emulate_g28_home,
        eval_words_fn=eval_words_fn,
        try_wcs_from_gcode_fn=try_wcs_from_gcode_fn,
        x_value_to_diameter_fn=x_value_to_diameter_fn,
        x_delta_to_diameter_fn=x_delta_to_diameter_fn,
        motion_ctor=motion_ctor,
        point_ctor=point_ctor,
    )
    motions, steps = execute_trace_context_with_steps(**execution_kwargs)
    return apply_tool_nose_compensation(motions, tools or {}), steps
