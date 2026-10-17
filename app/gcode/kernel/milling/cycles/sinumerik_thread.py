import math

from ...resources import checkpoint
from .sinumerik_pockets import PocketPath, arguments, cutter_radius, unsupported


def execute_thread(context, syntax):
    state = context.machine_state
    p = arguments(syntax, state, 3, 13)
    if len(syntax.cycle_args) != 13 or any(p[i] is None for i in range(5, 13)):
        unsupported("CYCLE90 requires the classic thirteen positional parameters")
    tool = cutter_radius(state)
    rtp, rfp, safety, dp, relative, nominal, core, pitch, feed, move, kind, x, y = p
    depth = dp if dp is not None else rfp - (relative or 0)
    _validate(p, depth, tool)
    if move not in {2, 3}:
        unsupported("CYCLE90 CDIR must be 2 or 3")
    diameter = core if kind == 2 else nominal
    radius = diameter / 2 + (-tool if kind == 0 else tool)
    lead = radius / 2
    direction = 1 if depth > rfp else -1
    overshoot = _overshoot(p, tool, radius, diameter)
    path = PocketPath(context)
    if kind == 0:
        path.add(0, (x, y, rtp))
        path.add(0, (x, y, rfp + safety))
        path.add(1, (x, y, rfp - direction * overshoot), feed=feed * state.native_feed_scale * lead / radius)
        path.add(
            move, (x + radius, y, rfp), center=(x + lead, y, rfp), feed=feed * state.native_feed_scale * lead / radius
        )
    else:
        _external_entry(path, p, radius)
    checkpoint("cycle_iterations")
    revolutions = abs(depth - rfp) / pitch
    fraction = revolutions % 1
    if min(fraction, 1 - fraction) * math.tau * radius * state.unit_scale <= 1e-10:
        fraction, revolutions = 0, round(revolutions)
    angle = fraction * math.tau * (1 if move == 3 else -1)
    c, s = math.cos(angle), math.sin(angle)
    end = x + radius * c, y + radius * s, depth
    path.add(
        move, end, center=(x, y, rfp), feed=feed * state.native_feed_scale, turns=max(0, math.ceil(revolutions) - 1)
    )
    _departure(path, p, radius, direction * overshoot, (c, s), depth)
    return path.outcome()


def _validate(p, depth, tool):
    rtp, rfp, safety, _, _, nominal, core, pitch, feed, _, kind, _, _ = p
    if safety < 0 or depth == rfp or rtp < max(rfp, depth) + safety:
        unsupported("CYCLE90 requires a nonzero thread depth and a clear return plane")
    if not 0.001 <= pitch <= 2000 or feed <= 0 or kind not in {0, 1, 2}:
        unsupported("Invalid CYCLE90 pitch, feed or TYPTH")
    if core <= 0 or (kind != 2 and (nominal <= 0 or core > nominal)):
        unsupported("Require positive core/nominal thread diameters with KDIAM <= DIATH")
    if kind == 0 and 2 * tool >= nominal:
        unsupported("Internal thread diameter must exceed the cutter diameter")


def _overshoot(p, tool, radius, diameter):
    nominal, core, pitch, _, _, kind = p[5:11]
    if kind != 0:
        return pitch / 4 * (2 * tool + radius) / diameter
    if 2 * tool < 2 * nominal / 3:
        return pitch / 2 * (tool + nominal / 2) / nominal
    return pitch / 2 * core / nominal


def _external_entry(path, p, radius):
    rtp, rfp, safety, _, _, _, _, _, feed, move, _, x, y = p
    sign = 1 if move == 2 else -1
    start = x + 1.5 * radius, y + sign * radius / 2
    path.add(0, (*start, rtp))
    path.add(0, (*start, rfp + safety))
    path.add(
        5 - move, (x + radius, y, rfp), center=(x + 1.5 * radius, y, rfp), feed=feed * path.state.native_feed_scale / 2
    )


def _departure(path, p, radius, overshoot, orientation, depth):
    rtp, _, _, _, _, _, _, _, feed, move, kind, x, y = p
    c, s = orientation
    if kind == 0:
        end = x, y, depth + overshoot
        center = x + radius * c / 2, y + radius * s / 2, depth
        path.add(move, end, center=center, feed=feed * path.state.native_feed_scale / 2)
        path.add(0, (x, y, end[2]))
        path.add(0, (x, y, rtp))
    else:
        sign = 1 if move == 3 else -1
        end = x + radius * (1.5 * c - sign * s / 2), y + radius * (1.5 * s + sign * c / 2), depth + overshoot
        center = x + 1.5 * radius * c, y + 1.5 * radius * s, depth
        path.add(5 - move, end, center=center, feed=feed * path.state.native_feed_scale / 2)
        path.add(0, (*end[:2], rtp))
