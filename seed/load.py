"""Load seed data into the database. Safe to run again: it updates, never duplicates.

    .venv/bin/python -m seed.load
"""

import json
from datetime import time
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cases.bites import HealthCentre
from app.cases.geo import point
from app.db import get_engine
from app.routing.models import Team, Zone

SEED_DIR = Path(__file__).parent


def _read(name: str, key: str) -> list[dict]:
    return json.loads((SEED_DIR / name).read_text(encoding="utf-8"))[key]


def _time(value: str | None) -> time | None:
    return time.fromisoformat(value) if value else None


def load_seed(session: Session) -> dict[str, int]:
    zones: dict[str, Zone] = {}
    for row in _read("zones.json", "zones"):
        zone = session.scalar(select(Zone).where(Zone.slug == row["slug"])) or Zone(slug=row["slug"])
        zone.name = row["name"]
        zone.short_name = row["short_name"]
        zone.kind = row["kind"]
        zone.taluka = row["taluka"]
        zone.district = row["district"]
        zone.centre = point(row["latitude"], row["longitude"])
        zone.radius_m = row["radius_m"]
        zone.approximate = row["approximate"]
        session.add(zone)
        zones[row["slug"]] = zone
    session.flush()

    teams = _read("teams.json", "teams")
    for row in teams:
        team = session.scalar(select(Team).where(Team.phone == row["phone"])) or Team(
            phone=row["phone"]
        )
        team.name = row["name"]
        team.kind = row["kind"]
        team.zone_id = zones[row["zone"]].id if row["zone"] else None
        team.taluka = row["taluka"]
        team.opens_at = _time(row["opens_at"])
        team.closes_at = _time(row["closes_at"])
        session.add(team)
    session.flush()

    centres = _read("health_centres.json", "health_centres")
    for row in centres:
        centre = session.scalar(
            select(HealthCentre).where(HealthCentre.slug == row["slug"])
        ) or HealthCentre(slug=row["slug"])
        centre.name = row["name"]
        centre.kind = row["kind"]
        centre.location = point(row["latitude"], row["longitude"])
        centre.verified = False  # every entry is still marked [VERIFY]
        session.add(centre)
    session.flush()
    return {"zones": len(zones), "teams": len(teams), "health_centres": len(centres)}


if __name__ == "__main__":
    with Session(get_engine()) as session:
        counts = load_seed(session)
        session.commit()
    print(
        f"Loaded {counts['zones']} zones, {counts['teams']} teams "
        f"and {counts['health_centres']} health centres."
    )
