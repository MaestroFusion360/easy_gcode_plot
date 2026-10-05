"""Translate executed native drilling holes without flattening the full program."""

from .common import _motion_in_active_wcs


def _number(value):
    formatted = f"{value:.12f}".rstrip("0").rstrip(".")
    return "0" if formatted == "-0" else formatted


def _axis(letter, value, scale):
    return letter + _number(value / scale)


def _can_use_initial_plane(motions, return_z):
    if motions[0].start_z == return_z:
        return True
    cutting_index = next(i for i, m in enumerate(motions) if m.move == 1)
    approach = next((m for m in motions[:cutting_index] if m.move == 0 and m.start_z != m.end_z), None)
    return approach is not None and min(approach.start_z, approach.end_z) <= return_z <= max(
        approach.start_z, approach.end_z
    )


def _hole_parameters(code, step, first):
    dwell = sum(s.value or 0 for s in step.signals if s.kind == "dwell")
    target = 84 if code == 84 else 82 if dwell else 81
    words = [f"G{target}", _axis("Z", first.end_z, step.unit_scale), _axis("R", first.start_z, step.unit_scale)]
    if target in {82, 84}:
        words.append("P" + _number(dwell * 1000))
    if first.feed is not None:
        words.append(_axis("F", first.feed, step.unit_scale))
    return target, " ".join(words)


def _hole_controls(step):
    return " ".join(
        letter + _number(value)
        for letter, value in step.words
        if letter in {"S", "M"} or (letter == "G" and value not in {0, 1, 2, 3, 90, 91, 290, 291})
    )


class NativeCycleEmitter:
    """Keep modal FANUC holes where equivalent; expand Siemens-specific pecks."""

    def __init__(self, result):
        self.result = result
        self.code = None
        self.template = None

    def _cancel(self, step, *, restore=True):
        lines = ["G80"] if self.template is not None else []
        if lines and restore:
            lines.append(f"G{step.modal_move}")
        self.template = None
        return lines

    def convert(self, step, block, motions):
        syntax = block.native_syntax
        kind = syntax.kind if syntax else None
        if kind in {"cycle", "cycle_cancel"}:
            lines = self._cancel(step)
            self.code = syntax.cycle_code if kind == "cycle" else None
            return "\n".join(lines)
        if self.code is None or not any(m.cycle_generated for m in motions):
            return None
        projected = [_motion_in_active_wcs(m, step, self.result) for m in motions]
        if self.code == 83:
            return self._expanded_pecks(step, projected)
        return self._canned_hole(step, projected)

    def _expanded_pecks(self, step, motions):
        lines = self._cancel(step)
        controls = _hole_controls(step)
        if controls:
            lines.append(controls)
        lines.append("G90")
        previous_feed = None
        for motion in motions:
            words = [f"G{motion.move}"]
            for axis, start, end in zip(
                "XYZ",
                (motion.start_x, motion.start_y, motion.start_z),
                (motion.end_x, motion.end_y, motion.end_z),
                strict=True,
            ):
                if start != end:
                    words.append(_axis(axis, end, step.unit_scale))
            if motion.move != 0 and motion.feed is not None and motion.feed != previous_feed:
                words.append(_axis("F", motion.feed, step.unit_scale))
                previous_feed = motion.feed
            lines.append(" ".join(words))
        lines.append(f"G{step.modal_move}" + (" G91" if not step.absolute else ""))
        return "\n".join(lines)

    def _canned_hole(self, step, motions):
        cutting = [m for m in motions if m.move == 1]
        if not cutting:
            raise ValueError("Native drilling conversion requires a nonzero cutting depth")
        first, last = cutting[0], motions[-1]
        target_code, parameters = _hole_parameters(self.code, step, first)
        # G98 needs RTP as its initial plane. Split only an existing monotone
        # approach rapid; otherwise use G99 and extend its return to RTP.
        # Native tapping feeds back to the safety plane, then rapids to RTP.
        # G99 G84 preserves that feed endpoint; RTP is a separate rapid.
        can_use_g98 = target_code != 84 and _can_use_initial_plane(motions, last.end_z)
        lines = []
        template = (parameters, last.end_z)
        if not can_use_g98 or template != self.template:
            lines = self._cancel(step)
        controls = _hole_controls(step)
        if controls:
            lines.append(controls)
        lines.append("G90")
        if self.template is None:
            lines.extend(self._start_hole(step, motions, first, last, target_code, parameters, can_use_g98))
            self.template = template
        else:
            lines.append(_axis("X", first.end_x, step.unit_scale) + " " + _axis("Y", first.end_y, step.unit_scale))
        if not can_use_g98:
            lines.extend(self._cancel(step, restore=False))
            lines.append("G0 " + _axis("Z", last.end_z, step.unit_scale))
            lines.append(f"G{step.modal_move}")
        if not step.absolute:
            lines.append("G91")
        return "\n".join(lines)

    @staticmethod
    def _start_hole(step, motions, first, last, target_code, parameters, initial_plane):
        scale = step.unit_scale
        xy = _axis("X", first.end_x, scale) + " " + _axis("Y", first.end_y, scale)
        lines = []
        if motions[0].start_x != first.end_x or motions[0].start_y != first.end_y:
            lines.append("G0 " + xy)
        if initial_plane and motions[0].start_z != last.end_z:
            lines.append("G0 " + _axis("Z", last.end_z, scale))
        if target_code == 84:
            lines.append("M29")
        lines.append(("G98 " if initial_plane else "G99 ") + parameters + " " + xy)
        return lines
