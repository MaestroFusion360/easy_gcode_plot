"""FANUC tip-reference directions in physical radial X/Z coordinates."""

TIP_DIRECTIONS: dict[int, tuple[int, int]] = {
    1: (1, 1),
    2: (1, -1),
    3: (-1, -1),
    4: (-1, 1),
    5: (0, 1),
    6: (1, 0),
    7: (0, -1),
    8: (-1, 0),
    9: (0, 0),
}
