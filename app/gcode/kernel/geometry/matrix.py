"""Shared 3D matrix primitives; column vectors and degrees."""

import math

Vector = tuple[float, float, float]
Matrix = tuple[Vector, Vector, Vector]
IDENTITY: Matrix = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def multiply(a: Matrix, b: Matrix) -> Matrix:
    rows = (tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))
    return tuple(rows)  # type: ignore[return-value]


def transpose(a: Matrix) -> Matrix:
    return tuple(tuple(a[j][i] for j in range(3)) for i in range(3))  # type: ignore[return-value]


def rotation(axis: Vector, degrees: float) -> Matrix:
    x, y, z = axis
    radians = math.radians(degrees)
    c, s = math.cos(radians), math.sin(radians)
    t = 1.0 - c
    return (
        (t * x * x + c, t * x * y - s * z, t * x * z + s * y),
        (t * x * y + s * z, t * y * y + c, t * y * z - s * x),
        (t * x * z - s * y, t * y * z + s * x, t * z * z + c),
    )


def transform_vector(orientation: Matrix, vector: Vector) -> Vector:
    return tuple(sum(row[i] * vector[i] for i in range(3)) for row in orientation)  # type: ignore[return-value]


def transform_point(orientation: Matrix, point: Vector) -> Vector:
    return transform_vector(orientation, point)
