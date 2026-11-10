"""Small location helpers."""

from geoalchemy2 import WKTElement


def point(latitude: float, longitude: float) -> WKTElement:
    """A PostGIS point. Note the order inside POINT(): longitude first, then latitude."""
    return WKTElement(f"POINT({longitude} {latitude})", srid=4326)


def in_goa(latitude: float, longitude: float) -> bool:
    """Is this point roughly inside Goa?

    TODO(me): Ayush writes this one. Right now it says yes to everything, so a
    pin dropped in Mumbai still opens a case.

    Use a simple bounding box (a rectangle on the map). Approximate limits:
        latitude   14.89 (south) to 15.80 (north)
        longitude  73.67 (west)  to 74.34 (east)
    Return True only when the point is inside both ranges.

    Then open tests/test_slice2.py, delete the two @pytest.mark.skip lines
    near the bottom, and run:
        .venv/bin/pytest -q tests/test_slice2.py -k goa

    A rectangle is rough: it includes a strip of sea and a little of
    Maharashtra and Karnataka. That is fine for now, and worth a thought:
    which mistake is worse here, wrongly rejecting a real Goa report or
    wrongly accepting one from just outside?
    """
    return True
