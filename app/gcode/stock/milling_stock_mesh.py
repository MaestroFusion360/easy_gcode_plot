"""Export triangles from GPU vertex-height readback; no CPU removal backend."""

import numpy as np

TRIANGLE_CORNERS = (0, 1, 2, 0, 2, 3)


def triangle_batches(stock, bounds=None, *, bottom=False):
    if bounds is None:
        for y in range(0, stock.ny, 128):
            for x in range(0, stock.nx, 128):
                yield from triangle_batches(
                    stock,
                    (x, min(stock.nx, x + 128), y, min(stock.ny, y + 128)),
                    bottom=bottom,
                )
        return
    x0, x1, y0, y1 = bounds
    h = stock.height[y0 : y1 + 1, x0 : x1 + 1]
    z = np.stack((h[:-1, :-1], h[:-1, 1:], h[1:, 1:], h[1:, :-1]), axis=-1)
    y, x = np.meshgrid(np.arange(y0, y1), np.arange(x0, x1), indexing="ij")
    vertices = np.empty(z.shape + (3,), dtype=np.float64)
    for corner, (ox, oy) in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))):
        vertices[..., corner, 0] = stock.spec.x_min + (x + ox) * stock.dx
        vertices[..., corner, 1] = stock.spec.y_min + (y + oy) * stock.dy
    vertices[..., 2] = z
    active = np.any(z > stock.spec.z_min, axis=-1)
    triangles = vertices[active][:, TRIANGLE_CORNERS].reshape(-1, 3, 3)
    yield _batch(triangles, stock)
    if bottom:
        base = vertices[active].copy()
        base[..., 2] = stock.spec.z_min
        yield _batch(base[:, (0, 2, 1, 0, 3, 2)].reshape(-1, 3, 3), stock)
    for outer, edge in (
        (y0 == 0, vertices[0][:, (0, 1)]),
        (x1 == stock.nx, vertices[:, -1, :, :][:, (1, 2)]),
        (y1 == stock.ny, vertices[-1, :, :, :][:, (2, 3)]),
        (x0 == 0, vertices[:, 0, :, :][:, (3, 0)]),
    ):
        if not outer:
            continue
        edge = np.asarray(edge).reshape(-1, 2, 3)
        wall = edge[:, (0, 0, 1, 1)].copy()
        wall[:, (1, 2), 2] = stock.spec.z_min
        yield _batch(wall[:, TRIANGLE_CORNERS].reshape(-1, 3, 3), stock)


def _batch(triangles, stock):
    cross = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    length = np.linalg.norm(cross, axis=1)
    valid = length > 0
    triangles, cross, length = triangles[valid], cross[valid], length[valid]
    normal = cross / length[:, None]
    cut = np.any(triangles[..., 2] < stock.spec.z_max, axis=1)
    return triangles, normal, cut, np.zeros(len(triangles), dtype=bool)
