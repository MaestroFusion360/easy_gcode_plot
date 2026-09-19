"""Machine-neutral axial peck and retract mechanics."""

from __future__ import annotations

from dataclasses import dataclass

from ..api.resources import checkpoint, require_progress


@dataclass(frozen=True)
class AxialPeck:
    feed_start: float
    depth: float
    retract: float | None


@dataclass(frozen=True)
class AxialMove:
    """One scalar rapid/feed segment in a machine-specific axial cycle."""

    move: int
    start: float
    end: float


def axial_pecks(
    start: float,
    target: float,
    step: float,
    *,
    retract_distance: float,
    full_retract: bool,
    retract_after_final: bool,
    tolerance: float,
) -> tuple[AxialPeck, ...]:
    """Return scalar peck positions; callers retain machine-specific interpretation."""
    direction = 1.0 if target > start else -1.0
    step = abs(step)
    retract_distance = abs(retract_distance)
    last_depth = start
    feed_start = start
    result: list[AxialPeck] = []
    while (target - last_depth) * direction > tolerance:
        checkpoint("cycle_iterations")
        depth = last_depth + direction * step
        if (target - depth) * direction < 0.0:
            depth = target
        require_progress(last_depth, depth)
        reached_target = abs(depth - target) <= tolerance
        retract = None
        if not reached_target or retract_after_final:
            retract = start if full_retract else depth - direction * retract_distance
            if (retract - start) * direction < 0.0:
                retract = start
        result.append(AxialPeck(feed_start, depth, retract))
        last_depth = depth
        if retract is not None:
            feed_start = start if full_retract else retract
    return tuple(result)


def axial_cycle_moves(
    start: float,
    target: float,
    *,
    step: float | None = None,
    retract_distance: float = 0.0,
    full_retract: bool = False,
    retract_after_final: bool = False,
    return_to: float | None = None,
    return_feed: bool = False,
    tolerance: float = 1e-9,
) -> tuple[AxialMove, ...]:
    """Build a machine-neutral scalar drilling/tapping path.

    G-code interpretation stays with the machine mode. This function only owns
    the common feed/peck/retract/return mechanics once parameters are resolved.
    """
    moves: list[AxialMove] = []
    current = start
    if step is not None and abs(step) > tolerance:
        for peck in axial_pecks(
            start,
            target,
            step,
            retract_distance=retract_distance,
            full_retract=full_retract,
            retract_after_final=retract_after_final,
            tolerance=tolerance,
        ):
            if abs(peck.depth - peck.feed_start) > tolerance:
                moves.append(AxialMove(1, peck.feed_start, peck.depth))
            current = peck.depth
            if peck.retract is not None and abs(peck.retract - peck.depth) > tolerance:
                moves.append(AxialMove(0, peck.depth, peck.retract))
                current = peck.retract
    elif abs(target - start) > tolerance:
        moves.append(AxialMove(1, start, target))
        current = target

    if return_to is not None and abs(return_to - current) > tolerance:
        moves.append(AxialMove(1 if return_feed else 0, current, return_to))
    return tuple(moves)
