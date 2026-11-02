"""Geohash encoding and the coarse area shown on the public board.

A geohash is a base-32 encoding of interleaved latitude and longitude bits, so
truncating it to N characters is the same as discarding the low-order bits of
both coordinates: a prefix names a rectangular cell, and every point inside
that cell shares it. That is the whole mechanism for the coarse area.

Precision is a constant, not a parameter a caller can lower by accident.
"""
from __future__ import annotations

BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"

# Six characters is roughly 1.2 km by 0.6 km at mid latitudes. Cells are not
# square and not a constant size: longitude cells narrow towards the poles.
PUBLIC_PRECISION = 6


def encode(latitude: float, longitude: float, precision: int = 12) -> str:
    if not -90.0 <= latitude <= 90.0 or not -180.0 <= longitude <= 180.0:
        raise ValueError("Coordinates out of range.")
    if not 1 <= precision <= 12:
        raise ValueError("Precision must be between 1 and 12.")
    lat_range, lon_range = [-90.0, 90.0], [-180.0, 180.0]
    out, bit, value, even = [], 0, 0, True
    while len(out) < precision:
        if even:
            middle = sum(lon_range) / 2
            if longitude > middle:
                value = (value << 1) | 1
                lon_range[0] = middle
            else:
                value <<= 1
                lon_range[1] = middle
        else:
            middle = sum(lat_range) / 2
            if latitude > middle:
                value = (value << 1) | 1
                lat_range[0] = middle
            else:
                value <<= 1
                lat_range[1] = middle
        even = not even
        bit += 1
        if bit == 5:
            out.append(BASE32[value])
            bit, value = 0, 0
    return "".join(out)


def bounds(geohash: str) -> tuple[float, float, float, float]:
    """South, west, north, east of the cell a geohash names."""
    lat_range, lon_range = [-90.0, 90.0], [-180.0, 180.0]
    even = True
    for character in geohash:
        index = BASE32.find(character)
        if index < 0:
            raise ValueError(f"{character!r} is not a geohash character.")
        for shift in range(4, -1, -1):
            bit = (index >> shift) & 1
            target = lon_range if even else lat_range
            middle = sum(target) / 2
            target[0 if bit else 1] = middle
            even = not even
    return lat_range[0], lon_range[0], lat_range[1], lon_range[1]


def cell_centre(geohash: str) -> tuple[float, float]:
    """The centre of the cell, which is what the public board plots.

    The board never plots the real point. A pin at the cell centre carries
    exactly the information the prefix already carries, and no more.
    """
    south, west, north, east = bounds(geohash)
    return (south + north) / 2, (west + east) / 2


def coarse(latitude: float, longitude: float) -> str:
    return encode(latitude, longitude, PUBLIC_PRECISION)


def cell_size_metres(geohash: str) -> tuple[float, float]:
    """Rough height and width of a cell, for the interface to state honestly."""
    import math

    south, west, north, east = bounds(geohash)
    height = (north - south) * 111_320
    width = (east - west) * 111_320 * math.cos(math.radians((south + north) / 2))
    return height, width
