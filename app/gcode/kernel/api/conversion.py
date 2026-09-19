"""Conversions from internal interpreter models to the public kernel API."""

from __future__ import annotations

from ..frontend.lang import try_literal_int
from ..frontend.model import Motion, Program
from .types import SemanticInstruction, TraceMotion


def semantic_instructions(program: Program | None) -> tuple[SemanticInstruction, ...]:
    """Publish parsed AST nodes without exposing mutable interpreter state."""
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


def trace_motion(motion: Motion) -> TraceMotion:
    """Convert a native turning motion into the stable, flat public shape."""
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
        playback_group=motion.playback_group,
    )
