"""Small public facade for the native FANUC CNC kernel."""

from __future__ import annotations

import re
from dataclasses import replace

from .api_types import Diagnostic, ExecutionResult, ExecutionStep, SemanticInstruction, TraceMotion
from .geometry import resolve_arc
from .lang import UndefinedMacroVariableError, try_literal_int
from .milling import execute_milling
from .milling_compensation import apply_milling_cutter_compensation
from .model import Motion, Point2, Program
from .program import eval_words, parse_program, try_wcs_from_gcode, x_delta_to_diameter, x_value_to_diameter
from .resources import ExecutionBudget, ExecutionLimits, SemanticError, active_budget
from .signals import program_end_code
from .trace import build_source_motion_trace_with_steps as _build_source_motion_trace_with_steps

SUPPORTED_LANGUAGES = frozenset({"fanuc_turn", "fanuc_mill"})
SUPPORTED_G_CODES = frozenset(
    {
        0,
        1,
        2,
        3,
        4,
        18,
        20,
        21,
        28,
        30,
        32,
        33,
        40,
        41,
        42,
        50,
        54,
        55,
        56,
        57,
        58,
        59,
        70,
        71,
        72,
        73,
        74,
        75,
        76,
        80,
        83,
        84,
        90,
        91,
        92,
        94,
        96,
        97,
        98,
        99,
        190,
        191,
    }
)
_LINE_RE = re.compile(r"\bline\s+(\d+)\b", re.IGNORECASE)


WcsOffset = tuple[float, float] | tuple[float, float, float]
WcsOffsets = dict[int, WcsOffset]


def _mill_wcs_offsets(wcs_offsets: WcsOffsets | None) -> dict[int, tuple[float, float, float]]:
    """Normalize public WCS values to XYZ for the milling kernel."""
    out = {}
    for code, values in (wcs_offsets or {}).items():
        if len(values) == 2:
            x, z = values
            out[code] = (float(x), 0.0, float(z))
        else:
            x, y, z = values
            out[code] = (float(x), float(y), float(z))
    return out


def _turn_wcs_offsets(wcs_offsets: WcsOffsets | None) -> dict[int, tuple[float, float]]:
    """Normalize public WCS values to XZ for the turning kernel."""
    out = {}
    for code, values in (wcs_offsets or {}).items():
        if len(values) == 2:
            x, z = values
        else:
            x, _y, z = values
        out[code] = (float(x), float(z))
    return out


def _execute_impl(
    source: str,
    language: str = "fanuc_turn",
    *,
    x_is_diameter: bool = True,
    skip_optional_blocks: bool = False,
    supplementary_angles: bool = False,
    pq_mm_for_g74758384: bool = False,
    default_unit_scale: float = 1.0,
    tools: dict[str, dict[str, object]] | None = None,
    home_x: float = 0.0,
    home_y: float = 0.0,
    home_z: float = 0.0,
    wcs_offsets: WcsOffsets | None = None,
    emulate_g28_home: bool = False,
) -> ExecutionResult:
    """Parse, compile, and trace a FANUC turning program.

    Unsupported position-changing commands fail closed at that block while
    preserving every trustworthy motion produced before it.
    """
    if language not in SUPPORTED_LANGUAGES:
        return ExecutionResult(
            ok=False,
            program=None,
            instructions=(),
            motions=(),
            diagnostics=(
                Diagnostic(
                    code="UNSUPPORTED_LANGUAGE",
                    message=f"Unsupported G-code language: {language}",
                ),
            ),
            executed_blocks=(),
        )

    if language == "fanuc_mill":
        return execute_milling(
            source,
            skip_optional_blocks=skip_optional_blocks,
            default_unit_scale=default_unit_scale,
            home=(home_x, home_y, home_z),
            wcs_offsets=_mill_wcs_offsets(wcs_offsets),
        )

    program: Program | None = None
    unsupported: tuple[Diagnostic, ...] = ()
    try:
        program = parse_program(source.splitlines())
        unsupported = _unsupported_g_diagnostics(program)
        rough, finish = [], []
        native_motions, trace_steps = _build_source_motion_trace_with_steps(
            program,
            rough,
            finish,
            x_is_diameter=x_is_diameter,
            pq_mm_for_g74758384=pq_mm_for_g74758384,
            supplementary_angles=supplementary_angles,
            default_unit_scale=default_unit_scale,
            skip_optional_blocks=skip_optional_blocks,
            home_x=home_x,
            home_z=home_z,
            wcs_offsets=_turn_wcs_offsets(wcs_offsets),
            emulate_g28_home=emulate_g28_home,
            eval_words_fn=eval_words,
            try_wcs_from_gcode_fn=try_wcs_from_gcode,
            x_value_to_diameter_fn=x_value_to_diameter,
            x_delta_to_diameter_fn=x_delta_to_diameter,
            motion_ctor=Motion,
            point_ctor=Point2,
            tools=tools,
        )
        unsupported += _fractional_code_diagnostics(program, trace_steps)
    except Exception as exc:
        return ExecutionResult(
            ok=False,
            program=program,
            instructions=_semantic_instructions(program),
            motions=(),
            diagnostics=unsupported + (_diagnostic_from_exception(exc, program),),
            executed_blocks=(),
        )

    signals = tuple(signal for step in trace_steps for signal in step.signals)
    return ExecutionResult(
        ok=not any(item.severity == "error" for item in unsupported),
        program=program,
        instructions=_semantic_instructions(program),
        motions=tuple(_trace_motion(motion) for motion in native_motions),
        diagnostics=unsupported,
        executed_blocks=tuple(
            dict.fromkeys(motion.source_block for motion in native_motions if motion.source_block is not None)
        ),
        signals=signals,
        program_end=program_end_code(signals),
        execution_steps=tuple(
            ExecutionStep(
                source_block=step.source_block,
                emitted_count=step.emitted_count,
                unit_scale=step.unit_scale,
                x_is_diameter=step.x_is_diameter,
                contour_definition=step.contour_definition,
                stop=step.stop,
                words=step.words,
                signals=step.signals,
                occurrence=occurrence,
                active_wcs=step.active_wcs,
                position=(step.modal_x, 0.0, step.modal_z),
                feed_mode=step.feed_mode,
                spindle_rpm=step.spindle_rpm,
                spindle_mode=step.spindle_mode,
                surface_speed_m_min=step.surface_speed_m_min,
                spindle_limit_rpm=step.spindle_limit_rpm,
                spindle_running=step.spindle_running,
            )
            for occurrence, step in enumerate(trace_steps)
        ),
    )


def _semantic_instructions(program: Program | None) -> tuple[SemanticInstruction, ...]:
    if program is None or program.ast is None:
        return ()
    out: list[SemanticInstruction] = []
    for node in program.ast.nodes:
        g_codes = tuple(
            code for word in node.words if word.letter == "G" and (code := try_literal_int(word.expr)) is not None
        )
        m_codes = tuple(
            code for word in node.words if word.letter == "M" and (code := try_literal_int(word.expr)) is not None
        )
        out.append(
            SemanticInstruction(
                kind=node.kind,
                block_index=node.block_index,
                raw=node.raw,
                words=tuple((word.letter, word.expr) for word in node.words),
                g_codes=g_codes,
                m_codes=m_codes,
                nlabel=node.nlabel,
                olabel=node.olabel,
            )
        )
    return tuple(out)


def _trace_motion(motion: Motion) -> TraceMotion:
    return TraceMotion(
        move=motion.move,
        start_x=motion.start.x,
        start_z=motion.start.z,
        end_x=motion.end.x,
        end_z=motion.end.z,
        radius=motion.radius,
        feed=motion.feed,
        i=motion.i,
        k=motion.k,
        source_block=motion.source_block,
        source_nlabel=motion.source_nlabel,
        source_raw=motion.source_raw,
        source_kind=motion.source_kind,
        compensation_mode=motion.compensation_mode,
        tool=motion.tool,
        compensation_applied=motion.compensation_applied,
        plane=18,
        cycle_generated=motion.source_kind == "cycle",
    )


def _diagnostic_from_exception(exc: Exception, program: Program | None) -> Diagnostic:
    message = str(exc)
    code = "EXECUTION_ERROR"
    lowered = message.lower()
    current: BaseException | None = exc
    seen: set[int] = set()
    undefined_macro = False
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, UndefinedMacroVariableError):
            undefined_macro = True
            break
        current = current.__cause__ or current.__context__
    if undefined_macro or "undefined macro variable" in lowered:
        code = "UNDEFINED_MACRO"
    elif "missing goto target" in lowered or "missing if/goto target" in lowered:
        code = "FLOW_TARGET_MISSING"
    elif "m98 targets missing" in lowered:
        code = "SUBPROGRAM_MISSING"
    elif "call depth exceeds" in lowered:
        code = "CALL_DEPTH_EXCEEDED"
    elif "m98" in lowered:
        code = "SUBPROGRAM_ERROR"
    elif "guard reached" in lowered:
        code = "EXECUTION_GUARD"
    elif "g83/g84 cycle remains active" in lowered:
        code = "UNCLOSED_CYCLE"

    line = None
    match = _LINE_RE.search(message)
    if match is not None:
        line = int(match.group(1))

    raw = None
    if program is not None and line is not None and 1 <= line <= len(program.blocks):
        raw = program.blocks[line - 1].raw
    current = exc
    while current is not None:
        if isinstance(current, SemanticError):
            return Diagnostic(current.code, message, status=current.status, line=line, raw=raw)
        current = current.__cause__
    return Diagnostic(code=code, message=message, status="malformed", line=line, raw=raw)


def _unsupported_g_diagnostics(program: Program) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    for block in program.blocks:
        if any(word.letter == "Y" for word in block.parsed_words):
            diagnostics.append(
                Diagnostic(
                    code="UNSUPPORTED_AXIS",
                    message="Y-axis motion is not modeled for fanuc_turn",
                    severity="error",
                    status="unsupported",
                    line=block.index + 1,
                    raw=block.raw,
                )
            )
        for word in block.parsed_words:
            if word.letter != "G":
                continue
            try:
                value = float(word.expr)
            except ValueError:
                continue
            code = int(value)
            if value == code and code not in SUPPORTED_G_CODES:
                affects_geometry = code in {17, 19} or any(
                    item.letter in {"X", "Z", "U", "W"} for item in block.parsed_words
                )
                diagnostics.append(
                    Diagnostic(
                        code="UNSUPPORTED_G_CODE",
                        message=f"G{code} is not modeled for fanuc_turn",
                        severity="error" if affects_geometry else "warning",
                        status="unsupported" if affects_geometry else "unverified",
                        line=block.index + 1,
                        raw=block.raw,
                    )
                )
    return tuple(diagnostics)


def _fractional_code_diagnostics(program: Program, steps) -> tuple[Diagnostic, ...]:
    """Report evaluated fractional G/M words without coercing them to integer codes."""
    diagnostics: list[Diagnostic] = []
    seen: set[tuple[int, str, float]] = set()
    for step in steps:
        block_index = step.source_block
        if block_index is None or not 0 <= block_index < len(program.blocks):
            continue
        block = program.blocks[block_index]
        affects_geometry = any(item.letter in {"X", "Z", "U", "W"} for item in block.parsed_words)
        for letter, raw_value in step.words:
            if letter not in {"G", "M"}:
                continue
            value = float(raw_value)
            if value.is_integer():
                continue
            key = (block_index, letter, value)
            if key in seen:
                continue
            seen.add(key)
            is_g = letter == "G"
            diagnostics.append(
                Diagnostic(
                    code="UNSUPPORTED_G_CODE" if is_g else "UNSUPPORTED_M_CODE",
                    message=f"{letter}{value:g} is not modeled for fanuc_turn",
                    severity="error" if is_g and affects_geometry else "warning",
                    status="unsupported" if is_g and affects_geometry else "unverified",
                    line=block.index + 1,
                    raw=block.raw,
                )
            )
    return tuple(diagnostics)


def execute(source, language="fanuc_turn", *, limits=None, cancelled=None, source_arc_type=1, **options):
    """Execute once; resolve geometry and publish a self-contained immutable result."""
    budget = ExecutionBudget(limits or ExecutionLimits(), cancelled)
    token = active_budget.set(budget)
    milling_tools = options.pop("milling_tools", None)
    try:
        result = _execute_impl(source, language, **options)
        motions = []
        cursor = 0
        for step in result.execution_steps:
            for motion in result.motions[cursor : cursor + step.emitted_count]:
                motion = replace(
                    motion,
                    x_scale=0.5 if language == "fanuc_turn" else 1.0,
                    feed_mode=step.feed_mode,
                    spindle_rpm=step.spindle_rpm,
                    spindle_mode=step.spindle_mode,
                    surface_speed_m_min=step.surface_speed_m_min,
                    spindle_limit_rpm=step.spindle_limit_rpm,
                    spindle_running=step.spindle_running,
                    compensation_status="APPLIED"
                    if motion.compensation_applied
                    else ("UNVERIFIED" if motion.compensation_mode in (41, 42) else "NOT_APPLIED"),
                    threading=any(k == "G" and v in (32, 33, 76, 92) for k, v in step.words),
                )
                motions.append(resolve_arc(motion, source_arc_type=source_arc_type))
            cursor += step.emitted_count
        if not result.execution_steps:
            motions = list(result.motions)
        diagnostics = result.diagnostics
        if language == "fanuc_mill":
            motions = apply_milling_cutter_compensation(motions, milling_tools or {})
            if any(m.compensation_mode in (41, 42) and not m.compensation_applied for m in motions):
                diagnostics = diagnostics + (
                    Diagnostic(
                        "UNVERIFIED_CUTTER_COMPENSATION",
                        "G41/G42 requires a configured T1-T99 milling cutter and supported "
                        "resolved line/arc/helix geometry",
                        "warning",
                        "unverified",
                    ),
                )
        return replace(
            result,
            motions=tuple(motions),
            diagnostics=diagnostics,
            complete=result.ok,
            language=language,
            executed_blocks=tuple(step.source_block for step in result.execution_steps),
        )
    except Exception as exc:
        diagnostic = _diagnostic_from_exception(exc, None)
        return ExecutionResult(False, None, (), (), (diagnostic,), (), complete=False, language=language)
    finally:
        active_budget.reset(token)
