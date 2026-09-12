from __future__ import annotations

from dataclasses import replace

# Keyword assembly mirrors the execution-context contract directly.
# pylint: disable=use-dict-literal
from .interpreter import TraceRuntimeState, build_trace_execution_context, execute_trace_context_with_steps
from .model import ProfileSegment
from .profile import apply_corner_direct_programming
from .tool_compensation import apply_tool_nose_compensation


def _source_motion_owners(motions, steps) -> list[int]:
    owners: list[int] = []
    for step_index, step in enumerate(steps):
        owners.extend([step_index] * int(step.emitted_count))
    if len(owners) != len(motions):
        raise RuntimeError("Trace motion ownership is inconsistent before direct programming expansion")
    return owners


def _step_word_map(step) -> dict[str, float]:
    return {str(letter): float(value) for letter, value in step.words}


def _connected(a, b, tolerance: float = 1e-7) -> bool:
    return abs(a.end.x - b.start.x) <= tolerance and abs(a.end.z - b.start.z) <= tolerance


def _is_direct_line_motion(motion) -> bool:
    return motion.move == 1 and motion.source_kind == "motion"


def _apply_source_corner_direct_programming(motions, steps):
    """Expand FANUC G1 C/R corner programming on the resolved source trace.

    Cycle P/Q contours already pass through ``build_profile_segments`` and must
    not be processed a second time.  Ordinary source G1 motions are grouped
    into connected runs, converted to the same ``ProfileSegment`` contract,
    expanded by the shared profile helper, and converted back while preserving
    source/tool/compensation ownership.
    """
    if not motions or not steps:
        return list(motions), list(steps)

    owners = _source_motion_owners(motions, steps)
    result = []
    result_owners: list[int] = []
    index = 0

    while index < len(motions):
        current = motions[index]
        if not _is_direct_line_motion(current):
            result.append(current)
            result_owners.append(owners[index])
            index += 1
            continue

        end = index
        while (
            end + 1 < len(motions)
            and _is_direct_line_motion(motions[end + 1])
            and _connected(motions[end], motions[end + 1])
        ):
            end += 1

        run = motions[index : end + 1]
        run_owners = owners[index : end + 1]
        segments: list[ProfileSegment] = []
        has_corner_command = False

        for local_index, (motion, owner) in enumerate(zip(run, run_owners)):
            step = steps[owner]
            words = _step_word_map(step)
            chamfer = abs(words.get("C", 0.0) * float(step.unit_scale))
            fillet = abs(words.get("R", 0.0) * float(step.unit_scale))
            has_corner_command = has_corner_command or chamfer > 1e-12 or fillet > 1e-12
            segments.append(
                ProfileSegment(
                    block=local_index,
                    move=1,
                    start=motion.start,
                    end=motion.end,
                    has_radius=False,
                    radius=0.0,
                    has_center=False,
                    center=motion.start,
                    corner_chamfer=chamfer,
                    corner_radius_cmd=fillet,
                )
            )

        if has_corner_command and len(segments) >= 2:
            expanded = apply_corner_direct_programming(segments)
            for segment in expanded:
                template_index = int(segment.block)
                template = run[template_index]
                owner = run_owners[template_index]
                result.append(
                    replace(
                        template,
                        move=segment.move,
                        start=segment.start,
                        end=segment.end,
                        radius=segment.radius if segment.move in (2, 3) and segment.has_radius else None,
                        i=None,
                        k=None,
                    )
                )
                result_owners.append(owner)
        else:
            result.extend(run)
            result_owners.extend(run_owners)

        index = end + 1

    emitted_counts = [0] * len(steps)
    for owner in result_owners:
        emitted_counts[owner] += 1
    updated_steps = [replace(step, emitted_count=emitted_counts[step_index]) for step_index, step in enumerate(steps)]
    return result, updated_steps


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
    motions, steps = _apply_source_corner_direct_programming(motions, steps)
    return apply_tool_nose_compensation(motions, tools or {}), steps
