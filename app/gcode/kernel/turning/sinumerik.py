"""Native SINUMERIK G290 and bounded ISO Dialect T execution over the same AST."""

from dataclasses import replace

from ..compensation.turning import apply_tool_nose_compensation
from ..conversion import trace_motion
from ..frontend.model import Point2
from ..frontend.sinumerik_turning import parse_sinumerik_turning_program
from ..machine.diagnostics import diagnostic_from_exception
from ..machine.execution import semantic_instructions
from ..milling.sinumerik_flow import build_native_loop_maps, native_flow_destination
from ..milling.sinumerik_parameters import compile_variables, parameter_value
from ..resources import checkpoint
from ..types import ExecutionResult, ExecutionStep
from .sinumerik_cycles import execute_cycle
from .sinumerik_motion import _frame, _switch_mode, evaluate, position_block
from .sinumerik_state import TurningState, unsupported

_FLOW_KINDS = {"while", "endwhile", "if_goto", "goto", "invalid_flow"}


def _dispatch(state, block, words):
    syntax = block.native_syntax
    if _switch_mode(state, block, words):
        return
    if syntax.kind == "words":
        position_block(state, words, syntax, block)
        return
    if not state.native:
        unsupported("Native Siemens commands require G290")
    if syntax.kind in {"message", "workpiece", "turning_label"}:
        return
    if syntax.kind == "programmed_frame":
        _frame(state, syntax)
    elif syntax.kind in {"parameter_assignment", "real_declaration", "named_assignment"}:
        state.siemens_variables = compile_variables(syntax, state)
        if syntax.parameter_assignment:
            number, expression = syntax.parameter_assignment
            state.siemens_parameters[number] = parameter_value(
                expression, state.siemens_parameters, state.siemens_variables
            )
    elif syntax.kind == "turning_cycle":
        execute_cycle(state, syntax, block)
    else:
        unsupported("Unsupported Siemens turning construct: " + syntax.kind)


def _step(state, block, values, counts, occurrence):
    motion_count, event_count, signal_count = counts
    point = state.machine(state.position)
    return ExecutionStep(
        block.index,
        len(state.motions) - motion_count,
        unit_scale=state.unit_scale,
        x_is_diameter=True,
        absolute=state.absolute,
        words=values,
        position=(point.x * 2, 0, point.z),
        programmed_position=(state.position.x * 2, 0, state.position.z),
        active_wcs=state.active_wcs,
        feed_mode=state.feed_mode,
        spindle_rpm=state.spindle_rpm,
        spindle_mode=state.spindle_mode,
        surface_speed_m_min=state.spindle_speed if state.spindle_mode == "css" else None,
        spindle_limit_rpm=state.spindle_limit_rpm,
        spindle_running=state.spindle_running,
        modal_move=state.modal_move,
        occurrence=occurrence,
        signals=tuple(state.signals[signal_count:]),
        events=tuple(state.events[event_count:]),
        sinumerik_parameters=tuple(sorted(state.siemens_parameters.items())),
        sinumerik_variables=tuple(sorted(state.siemens_variables.items())),
    )


def execute_sinumerik_turning(
    source,
    *,
    parsed_program=None,
    tools=None,
    tool_resolver=None,
    home=(0, 0),
    wcs_offsets=None,
    default_unit_scale=1.0,
    x_is_diameter=True,
    iso_system="A",
    skip_optional_blocks=False,
    emulate_home=False,
    include_instructions=True,
    tolerance=0.01,
    solution_line=True,
    correction_enabled=True,
):
    state = TurningState(
        offsets=dict(wcs_offsets or {}),
        home=Point2(home[0] / 2, home[1]),
        unit_scale=default_unit_scale,
        feed_scale=default_unit_scale,
        diameter_mode="DIAMON" if x_is_diameter else "DIAMOF",
        iso_system=iso_system,
        emulate_home=emulate_home,
        tolerance=tolerance,
        sinumerik_840d_sl=solution_line,
    )
    state.position = state.programmed(state.home)
    block = None
    failed = False
    try:
        state.program = parsed_program or parse_sinumerik_turning_program(source)
        state.tools = tool_resolver(state.program) if tool_resolver else dict(tools or {})
        pairs = build_native_loop_maps(state.program)
        pc, occurrences = 0, {}
        while 0 <= pc < len(state.program.blocks):
            block = state.program.blocks[pc]
            checkpoint("executed_blocks")
            if block.optional_skip and skip_optional_blocks:
                pc += 1
                continue
            words, values = evaluate(block, state)
            counts = len(state.motions), len(state.events), len(state.signals)
            syntax = block.native_syntax
            if syntax.kind in _FLOW_KINDS:
                if not state.native:
                    unsupported("Siemens control flow requires G290")
                next_pc = native_flow_destination(state.program.ast.nodes[pc], pc, state.program, state, pairs)
            else:
                _dispatch(state, block, words)
                next_pc = pc + 1
            occurrence = occurrences.get(block.index, 0)
            state.steps.append(_step(state, block, values, counts, occurrence))
            occurrences[block.index] = occurrence + 1
            if state.ended:
                break
            pc = next_pc
        if correction_enabled:
            state.motions = apply_tool_nose_compensation(state.motions, state.tools)
    except Exception as exc:
        diagnostic = diagnostic_from_exception(exc, state.program)
        if diagnostic.line is None and block is not None:
            diagnostic = replace(diagnostic, line=block.index + 1, raw=block.raw)
        state.diagnostics.append(diagnostic)
        failed = True
    motions = tuple(
        replace(
            trace_motion(m), source_arc_type=1, threading=thread, feed_mode="per_revolution" if thread else "per_minute"
        )
        for m, thread in zip(state.motions, state.threading, strict=True)
    )
    return ExecutionResult(
        ok=not failed,
        program=state.program,
        instructions=semantic_instructions(state.program) if include_instructions and state.program else (),
        motions=motions,
        diagnostics=tuple(state.diagnostics),
        executed_blocks=tuple(step.source_block for step in state.steps),
        complete=not failed,
        language="fanuc_turn",
        source_dialect="sinumerik",
        program_end=state.ended,
        execution_steps=tuple(state.steps),
        events=tuple(state.events),
        signals=tuple(state.signals),
    )
