"""Export option contracts and export-mode constants."""

from __future__ import annotations

from dataclasses import dataclass, replace

from ..comments import DEFAULT_COMMENT_STYLE, normalize_comment_style

TURN_FULL_PROGRAM_MODE = 0
MILL_FULL_PROGRAM_MODE = 1
EXPANDED_EXECUTION_MODE = 2
PLOT_DATA_MODE = 3
DXF_MODE = 4


@dataclass(frozen=True)
class ExportOptions:
    # 0: relative IJK, 1: absolute IJK, 2: R arcs, 3: linearized arcs,
    # 4: plot-data style (all logical motions emitted as point-to-point moves).
    arc_mode: int = 0
    incremental: bool = False
    force_addresses: bool = False
    sequence_numbers: bool = False
    sequence_start: int = 1
    sequence_increment: int = 1
    sequence_spacing: bool = False
    delimiter: bool = False
    leading_zero: bool = False
    start_program: str = ""
    end_program: str = ""
    safety_line: bool = False
    analysis_banner: bool = True
    linearization_tolerance: float = 0.0005
    include_execution_events: bool = True
    comment_style: str = DEFAULT_COMMENT_STYLE
    include_comments: bool = True
    output_unit_scale: float = 1.0
    output_unit_code: str = ""
    synthesize_program_number: bool = True


def _turn_program_options(options: ExportOptions | None) -> ExportOptions:
    base = options or ExportOptions()
    return replace(
        base,
        arc_mode=2,
        incremental=False,
        force_addresses=False,
        analysis_banner=False,
    )


def _mill_program_options(options: ExportOptions | None) -> ExportOptions:
    base = options or ExportOptions()
    return replace(
        base,
        arc_mode=0,
        incremental=False,
        force_addresses=False,
        analysis_banner=False,
    )


def _window_export_options(window, *, arc_mode: int) -> ExportOptions:
    return ExportOptions(
        arc_mode=arc_mode,
        incremental=bool(window.incrMode),
        force_addresses=bool(window.forceAdr),
        sequence_numbers=bool(window.seqNum),
        sequence_start=int(window.seqNumStart),
        sequence_increment=int(window.seqNumIncr),
        sequence_spacing=bool(window.seqNumSpacing),
        delimiter=bool(window.delim),
        leading_zero=bool(window.leadingZero),
        start_program=str(window.startPgmExp or ""),
        end_program=str(window.endPgmExp or ""),
        safety_line=bool(window.safLine),
        comment_style=normalize_comment_style(getattr(window, "commentStyle", DEFAULT_COMMENT_STYLE)),
    )
