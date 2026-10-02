"""Metric milling lengths, with explicit compatibility for unsplit records."""

import math


def milling_lengths(spec: dict) -> dict[str, float] | None:
    """Derive total length; never infer a cutting/body split from legacy length."""
    split = "fluteLength" in spec or "bodyLength" in spec
    try:
        if split:
            flute = float(spec["fluteLength"])
            body = float(spec["bodyLength"])
            length = flute + body
            if not all(math.isfinite(value) for value in (flute, body, length)) or flute <= 0 or body < 0:
                return None
            return {"fluteLength": flute, "bodyLength": body, "length": length}
        length = float(spec.get("length", 0.0))
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    return {"length": length} if math.isfinite(length) and length > 0 else None
