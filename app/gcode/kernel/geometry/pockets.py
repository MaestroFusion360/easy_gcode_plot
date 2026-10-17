import math


def rectangle_contour(a, b, radius, clockwise=False):
    sign = -1 if clockwise else 1

    def point(x, y):
        return x, sign * y

    yield point(a, b - radius), None
    for end, center in (
        ((a - radius, b), (a - radius, b - radius)),
        ((-a + radius, b), None),
        ((-a, b - radius), (-a + radius, b - radius)),
        ((-a, -b + radius), None),
        ((-a + radius, -b), (-a + radius, -b + radius)),
        ((a - radius, -b), None),
        ((a, -b + radius), (a - radius, -b + radius)),
        ((a, b - radius), None),
    ):
        yield point(*end), point(*center) if center is not None and radius > 1e-10 else None


def equal_steps(distance, maximum):
    count = max(1, math.ceil(distance / maximum)) if maximum > 0 else 1
    for index in range(1, count + 1):
        yield distance * index / count
