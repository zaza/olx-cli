KNOWN_RADII = frozenset({0, 2, 5, 10, 15, 30, 50, 75, 100})


def validate_radius(radius: int) -> None:
    if radius not in KNOWN_RADII:
        raise ValueError(
            f"radius must be one of {sorted(KNOWN_RADII)}, got {radius}"
        )
