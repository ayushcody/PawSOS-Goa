"""Load seed data into the database. Safe to run again: it updates, never duplicates.

    .venv/bin/python -m seed.load
"""

import json
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

import app.models  # noqa: F401  (registers every table)
from app.booking.models import Camp, CampSlot, SterilisationCount
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

    goa = ZoneInfo("Asia/Kolkata")
    camps = _read("camps.json", "camps")
    for row in camps:
        camp = session.scalar(select(Camp).where(Camp.slug == row["slug"])) or Camp(slug=row["slug"])
        camp.name = row["name"]
        camp.short_name = row["short_name"]
        camp.services = row["services"]
        camp.venue = row["venue"]
        camp.zone_id = zones[row["zone"]].id
        camp.location = point(row["latitude"], row["longitude"])
        session.add(camp)
        session.flush()
        day = date.fromisoformat(row["date"])
        for slot_row in row["slots"]:
            starts_at = datetime.combine(day, time.fromisoformat(slot_row["start"]), tzinfo=goa)
            slot = session.scalar(
                select(CampSlot).where(CampSlot.camp_id == camp.id, CampSlot.starts_at == starts_at)
            ) or CampSlot(camp_id=camp.id, starts_at=starts_at)
            slot.ends_at = datetime.combine(day, time.fromisoformat(slot_row["end"]), tzinfo=goa)
            slot.capacity = slot_row["capacity"]
            session.add(slot)
    session.flush()

    sterilisation = json.loads((SEED_DIR / "sterilisation_2025.json").read_text(encoding="utf-8"))
    for row in sterilisation["counts"]:
        zone_id, year = zones[row["zone"]].id, sterilisation["year"]
        count = session.scalar(
            select(SterilisationCount).where(
                SterilisationCount.zone_id == zone_id, SterilisationCount.year == year
            )
        ) or SterilisationCount(zone_id=zone_id, year=year)
        count.camps_held = row.get("camps_held")  # missing stays empty: "no figure"
        count.dogs_sterilised = row.get("dogs_sterilised")
        session.add(count)
    session.flush()
    return {
        "zones": len(zones),
        "teams": len(teams),
        "health_centres": len(centres),
        "camps": len(camps),
    }


if __name__ == "__main__":
    with Session(get_engine()) as session:
        counts = load_seed(session)
        session.commit()
    print(
        f"Loaded {counts['zones']} zones, {counts['teams']} teams, "
        f"{counts['health_centres']} health centres and {counts['camps']} camps."
    )
