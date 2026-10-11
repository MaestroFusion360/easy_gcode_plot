"""Cancellable completion of a pending milling seek before export."""


def finish_milling_seek(timeline, *, count, cancelled):
    while timeline.motion_count != count:
        if cancelled():
            raise InterruptedError("Stock seek cancelled")
        timeline.set_motion_count(count, time_budget=0.02)
    return timeline.snapshot()


_MIN_STOCK_RENDER_INTERVAL_SECONDS = 1.0 / 30.0
_MAX_STOCK_RENDER_INTERVAL_SECONDS = 0.25
_STOCK_RENDER_COST_MULTIPLIER = 2.0


def stock_render_interval_seconds(last_mesh_seconds: float) -> float:
    """Bound the shared rendering interval used by turning playback."""
    return min(
        _MAX_STOCK_RENDER_INTERVAL_SECONDS,
        max(_MIN_STOCK_RENDER_INTERVAL_SECONDS, last_mesh_seconds * _STOCK_RENDER_COST_MULTIPLIER),
    )
