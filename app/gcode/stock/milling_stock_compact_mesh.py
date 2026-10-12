"""Compact the calculated heightfield exactly, without replay or refinement."""

# pylint: disable=use-implicit-booleaness-not-len  # ndarray truthiness is ambiguous.

import numpy as np

from app.gcode.stock.milling_stock_mesh import TRIANGLE_CORNERS, _batch


def _check(cancelled):
    if cancelled is not None and cancelled():
        raise InterruptedError("Stock STL export cancelled")


def _leaves(stock, cancelled):
    h = stock.height
    low = np.minimum.reduce((h[:-1, :-1], h[:-1, 1:], h[1:, :-1], h[1:, 1:]))
    high = np.maximum.reduce((h[:-1, :-1], h[:-1, 1:], h[1:, :-1], h[1:, 1:]))
    levels = [(low, high)]
    while max(low.shape) > 1:
        _check(cancelled)
        padding = ((0, low.shape[0] % 2), (0, low.shape[1] % 2))
        low = np.pad(low, padding, constant_values=np.inf)
        high = np.pad(high, padding, constant_values=-np.inf)
        low = np.minimum.reduce((low[::2, ::2], low[::2, 1::2], low[1::2, ::2], low[1::2, 1::2]))
        high = np.maximum.reduce((high[::2, ::2], high[::2, 1::2], high[1::2, ::2], high[1::2, 1::2]))
        levels.append((low, high))
    nodes = np.array([[0, 0]], dtype=np.int64)
    leaves = []
    for level in reversed(range(len(levels))):
        _check(cancelled)
        low, high = levels[level]
        nodes = nodes[(nodes[:, 0] < low.shape[0]) & (nodes[:, 1] < low.shape[1])]
        if not len(nodes):
            break
        minimum, maximum = low[nodes[:, 0], nodes[:, 1]], high[nodes[:, 0], nodes[:, 1]]
        wet = maximum > stock.spec.z_min
        finished = wet & ((minimum == maximum) | (level == 0))
        origin = nodes[finished] * (1 << level)
        ends = np.minimum(origin + (1 << level), (stock.ny, stock.nx))
        leaves.append(np.column_stack((origin, ends)))
        split = nodes[wet & ~finished]
        nodes = (split[:, None, :] * 2 + np.array(((0, 0), (0, 1), (1, 0), (1, 1)))).reshape(-1, 2)
    return np.concatenate(leaves) if leaves else np.empty((0, 4), dtype=np.int64)


def _polygon(stock, bounds, horizontal, vertical):
    y0, x0, y1, x1 = bounds
    perimeter = []
    for keys, line, first, last, stride, reverse, swap in (
        (horizontal, y0, x0, x1, stock.nx + 1, False, False),
        (vertical, x1, y0, y1, stock.ny + 1, False, True),
        (horizontal, y1, x0, x1, stock.nx + 1, True, False),
        (vertical, x0, y0, y1, stock.ny + 1, True, True),
    ):
        begin, end = np.searchsorted(keys, (line * stride + first, line * stride + last), side="left")
        points = keys[begin : end + 1] % stride
        if reverse:
            points = points[::-1]
        # Each corner is the first point of exactly one edge.
        for point in points[:-1]:
            perimeter.append((line, point) if swap else (point, line))
    xy = np.asarray(perimeter)
    vertices = np.column_stack(
        (
            stock.spec.x_min + xy[:, 0] * stock.dx,
            stock.spec.y_min + xy[:, 1] * stock.dy,
            stock.height[xy[:, 1], xy[:, 0]],
        )
    )
    return vertices


def _closed_batches(triangles, stock):
    yield _batch(triangles, stock)
    base = triangles[:, (0, 2, 1)].copy()
    base[..., 2] = stock.spec.z_min
    yield _batch(base, stock)


def compact_triangle_batches(stock, cancelled=None):
    leaves = _leaves(stock, cancelled)
    if not len(leaves):
        return
    y0, x0, y1, x1 = leaves.T
    xs, ys = np.stack((x0, x1, x1, x0), axis=1), np.stack((y0, y0, y1, y1), axis=1)
    horizontal = np.unique(ys * (stock.nx + 1) + xs)
    vertical = np.unique(xs * (stock.ny + 1) + ys)
    unit = (y1 - y0 == 1) & (x1 - x0 == 1)
    for first in range(0, len(leaves), 16384):
        _check(cancelled)
        last = first + 16384
        x, y = xs[first:last][unit[first:last]], ys[first:last][unit[first:last]]
        vertices = np.stack(
            (stock.spec.x_min + x * stock.dx, stock.spec.y_min + y * stock.dy, stock.height[y, x]), axis=-1
        )
        mixed = np.any(vertices[..., 2] <= stock.spec.z_min, axis=1)
        triangles = vertices[~mixed][:, TRIANGLE_CORNERS].reshape(-1, 3, 3)
        patches = vertices[mixed]
        centre = np.repeat(patches.mean(axis=1)[:, None], 4, axis=1)
        fan = np.stack((patches, np.roll(patches, -1, axis=1), centre), axis=2).reshape(-1, 3, 3)
        yield from _closed_batches(np.concatenate((triangles, fan)), stock)
    patches = []
    for bounds in leaves[~unit]:
        _check(cancelled)
        vertices = _polygon(stock, bounds, horizontal, vertical)
        centre = np.repeat(vertices.mean(axis=0)[None], len(vertices), axis=0)
        patches.append(np.stack((vertices, np.roll(vertices, -1, axis=0), centre), axis=1))
        if len(patches) == 1024:
            yield from _closed_batches(np.concatenate(patches), stock)
            patches.clear()
    if patches:
        yield from _closed_batches(np.concatenate(patches), stock)
    # The perimeter uses the same leaf vertices as the top and bottom.
    for keys, line, stride, swap, reverse in (
        (horizontal, 0, stock.nx + 1, False, False),
        (vertical, stock.nx, stock.ny + 1, True, False),
        (horizontal, stock.ny, stock.nx + 1, False, True),
        (vertical, 0, stock.ny + 1, True, True),
    ):
        _check(cancelled)
        begin, end = np.searchsorted(keys, (line * stride, (line + 1) * stride))
        values = keys[begin:end] % stride
        if reverse:
            values = values[::-1]
        x, y = (np.full_like(values, line), values) if swap else (values, np.full_like(values, line))
        vertices = np.column_stack(
            (stock.spec.x_min + x * stock.dx, stock.spec.y_min + y * stock.dy, stock.height[y, x])
        )
        edges = np.stack((vertices[:-1], vertices[1:]), axis=1)
        walls = edges[:, (0, 0, 1, 1)].copy()
        walls[:, (1, 2), 2] = stock.spec.z_min
        yield _batch(walls[:, TRIANGLE_CORNERS].reshape(-1, 3, 3), stock)
