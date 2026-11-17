"""Small location helpers."""

import json
from functools import lru_cache
from pathlib import Path

from geoalchemy2 import WKTElement

# Goa's state boundary from OpenStreetMap, widened by 1 km and simplified (see the file's _note).
BOUNDARY_FILE = Path(__file__).resolve().parents[2] / "seed" / "goa_boundary.json"

Ring = list[tuple[float, float]]  # (longitude, latitude) points, as GeoJSON writes them


def point(latitude: float, longitude: float) -> WKTElement:
    """A PostGIS point. Note the order inside POINT(): longitude first, then latitude."""
    return WKTElement(f"POINT({longitude} {latitude})", srid=4326)


@lru_cache
def _goa() -> tuple[list[list[Ring]], tuple[float, float, float, float]]:
    """Goa's polygons (each an outer ring, then any holes), and a box around all of them."""
    data = json.loads(BOUNDARY_FILE.read_text(encoding="utf-8"))
    parts = data["coordinates"] if data["type"] == "MultiPolygon" else [data["coordinates"]]
    polygons = [[[(lng, lat) for lng, lat in ring] for ring in rings] for rings in parts]
    lngs = [lng for rings in polygons for lng, _ in rings[0]]
    lats = [lat for rings in polygons for _, lat in rings[0]]
    return polygons, (min(lngs), min(lats), max(lngs), max(lats))


def _inside_ring(lng: float, lat: float, ring: Ring) -> bool:
    """Ray casting: count how often a line going east from the point crosses the ring's edges."""
    inside = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1], strict=True):
        if (y1 > lat) != (y2 > lat) and lng < x1 + (lat - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def in_goa(latitude: float, longitude: float) -> bool:
    """Is this point in Goa, or within about 1 km of it?

    Checked against Goa's real state boundary, not a rectangle: a rectangle
    would take in a strip of Maharashtra and Karnataka. The boundary is
    widened by 1 km because wrongly turning away a real Goa report is the worse
    mistake: pins on a beach fall just seaward of the mapped coastline
    (Palolem by 260 m). The nearest towns outside Goa are at least 6 km beyond
    the boundary, so the margin does not let them in.
    """
    polygons, (west, south, east, north) = _goa()
    if not (west <= longitude <= east and south <= latitude <= north):
        return False  # quick answer for anywhere far away
    return any(
        _inside_ring(longitude, latitude, rings[0])
        and not any(_inside_ring(longitude, latitude, hole) for hole in rings[1:])
        for rings in polygons
    )
