"""Slice 4: zones, the escalation chain, and merging duplicate reports."""

import io
import json
from datetime import time
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import select, text

from app import messages
from app.cases.models import Case, CaseState, Event, Report
from app.routing.dedup import similar_animal
from app.routing.models import Team, Zone
from app.routing.teams import escalation_chain, is_open
from app.routing.zones import find_zone
from app.triage.schema import TriageResult
from app.triage.service import get_triager
from seed.load import load_seed

CITIZEN_1 = "+910000000001"
CITIZEN_2 = "+910000000002"
PANAJI = (15.4909, 73.8278)
CALANGUTE = (15.5440, 73.7553)  # a village between zones: no zone's radius covers it
METRES_PER_DEGREE_LATITUDE = 111_320

SEED = Path(__file__).parent.parent / "seed"


def photo() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (32, 32), (180, 120, 60)).save(out, format="PNG")
    return out.getvalue()


def report(client, number, place=PANAJI, north_m=0) -> None:
    """Send a photo and a location. `north_m` moves the pin that many metres north."""
    client.post(
        "/sim/inbound/photo",
        data={"from_number": number},
        files={"file": ("a.png", photo(), "image/png")},
    )
    client.post(
        "/sim/inbound",
        json={
            "from_number": number,
            "kind": "location",
            "latitude": place[0] + north_m / METRES_PER_DEGREE_LATITUDE,
            "longitude": place[1],
        },
    )


def replies(client, number) -> list[str]:
    transcript = client.get("/sim/messages", params={"phone": number}).json()
    return [m["text"] for m in transcript if m["direction"] == "out"]


def cases(db) -> list[Case]:
    db.expire_all()
    return list(db.scalars(select(Case).order_by(Case.id)))


class SpeciesInTurn:
    """A fake triager that names a different species (and urgency) for each photo."""

    def __init__(self, *readings: tuple[str, str]) -> None:
        self.readings = list(readings)

    async def triage(self, image: bytes) -> TriageResult:
        species, urgency = self.readings.pop(0)
        return TriageResult(
            animal_visible=True,
            species=species,
            injury_type="visible wound",
            urgency=urgency,
            aggression_risk="low",
            first_aid=["Keep a safe distance.", "Keep others back."],
        )


def use_triager(app, triager) -> None:
    # One shared instance: FastAPI calls the override on every request.
    app.dependency_overrides[get_triager] = lambda: triager


# ---------- seed data ----------


def test_seed_has_the_14_urban_local_bodies(seeded):
    zones = seeded.scalars(select(Zone)).all()
    assert len(zones) == 14
    assert [z.slug for z in zones if z.kind == "corporation"] == ["panaji"]
    assert all(z.approximate for z in zones)


def test_every_zone_has_a_partner_team_and_a_taluka_officer(seeded):
    for zone in seeded.scalars(select(Zone)):
        chain = escalation_chain(seeded, zone)
        assert chain[0].zone_id == zone.id, zone.slug
        assert chain[-1].kind == "taluka_officer" and chain[-1].taluka == zone.taluka, zone.slug


def test_seed_phone_numbers_are_all_invented():
    teams = json.loads((SEED / "teams.json").read_text())["teams"]
    assert teams and all(t["phone"].startswith("+910000000") for t in teams)


def test_seed_files_say_they_are_approximate_or_placeholder():
    assert "APPROXIMATE" in json.loads((SEED / "zones.json").read_text())["_note"]
    assert "PLACEHOLDERS" in json.loads((SEED / "teams.json").read_text())["_note"]


def test_loading_seed_twice_does_not_duplicate(seeded):
    load_seed(seeded)
    seeded.commit()
    assert len(seeded.scalars(select(Zone)).all()) == 14
    assert len(seeded.scalars(select(Team)).all()) == 25


# ---------- zones ----------


def test_a_case_in_panaji_lands_in_the_panaji_zone(client, seeded):
    report(client, CITIZEN_1, PANAJI)

    case = cases(seeded)[0]
    assert case.state == CaseState.ROUTED
    assert seeded.get(Zone, case.zone_id).slug == "panaji"
    assert case.zone_is_approximate is False
    assert replies(client, CITIZEN_1)[-1] == messages.render(
        "zone_assigned", case_id="PAW-0001", zone="Panaji"
    )

    event = seeded.scalars(select(Event).where(Event.type == "zone_assigned")).one()
    assert event.data["zone"] == "panaji" and event.data["within_radius"] is True


def test_a_case_between_zones_goes_to_the_nearest_and_is_marked_approximate(client, seeded):
    report(client, CITIZEN_1, CALANGUTE)

    case = cases(seeded)[0]
    match = find_zone(seeded, case)
    assert match.zone.slug == "mapusa"
    assert not match.within_radius
    assert case.zone_is_approximate is True


def test_escalation_chain_is_own_team_then_neighbour_then_officer(seeded):
    panaji = seeded.scalar(select(Zone).where(Zone.slug == "panaji"))
    own, neighbour, officer = escalation_chain(seeded, panaji)

    assert own.kind == "partner" and own.zone_id == panaji.id
    assert neighbour.kind == "partner" and neighbour.zone_id != panaji.id
    assert officer.kind == "taluka_officer" and officer.taluka == "Tiswadi"


# ---------- opening hours ----------


def test_is_open_daytime_hours():
    opens, closes = time(8, 0), time(20, 0)
    assert is_open(opens, closes, time(8, 0))  # opening time counts as open
    assert is_open(opens, closes, time(13, 30))
    assert not is_open(opens, closes, time(20, 0))  # closing time counts as closed
    assert not is_open(opens, closes, time(7, 59))


def test_no_hours_means_always_open():
    assert is_open(None, None, time(3, 0))


@pytest.mark.skip(reason="TODO(me): make is_open() handle overnight hours in app/routing/teams.py")
def test_is_open_overnight():
    opens, closes = time(20, 0), time(6, 0)  # a night shift
    assert is_open(opens, closes, time(23, 0))
    assert is_open(opens, closes, time(2, 0))
    assert is_open(opens, closes, time(20, 0))
    assert not is_open(opens, closes, time(6, 0))
    assert not is_open(opens, closes, time(12, 0))


# ---------- merging duplicates ----------


def test_a_second_report_nearby_is_merged_and_both_people_are_told(client, seeded):
    report(client, CITIZEN_1)
    report(client, CITIZEN_2, north_m=150)

    first, second = cases(seeded)
    assert first.state == CaseState.ROUTED
    assert second.state == CaseState.MERGED
    assert second.merged_into_id == first.id

    # Both reports now belong to the case that stays open.
    owners = seeded.scalars(select(Report.case_id).order_by(Report.id)).all()
    assert owners == [first.id, first.id]

    assert replies(client, CITIZEN_2)[-1] == messages.render(
        "merged_new_reporter", case_id="PAW-0001"
    )
    assert replies(client, CITIZEN_1)[-1] == messages.render(
        "merged_earlier_reporter", case_id="PAW-0001", count=2
    )


def test_merging_is_in_the_audit_log_of_both_cases(client, seeded):
    report(client, CITIZEN_1)
    report(client, CITIZEN_2)
    first, second = cases(seeded)

    merged = seeded.scalars(select(Event).where(Event.to_state == "MERGED")).one()
    assert merged.case_id == second.id and merged.data["merged_into"] == "PAW-0001"
    noted = seeded.scalars(select(Event).where(Event.type == "report_merged_in")).one()
    assert noted.case_id == first.id


def test_a_report_250_metres_away_is_a_separate_case(client, seeded):
    report(client, CITIZEN_1)
    report(client, CITIZEN_2, north_m=250)
    assert [c.state for c in cases(seeded)] == [CaseState.ROUTED, CaseState.ROUTED]


def test_a_report_after_two_hours_is_a_separate_case(client, seeded):
    report(client, CITIZEN_1)
    seeded.execute(text("UPDATE cases SET created_at = now() - interval '2 hours 1 minute'"))
    seeded.commit()

    report(client, CITIZEN_2)
    assert [c.state for c in cases(seeded)] == [CaseState.ROUTED, CaseState.ROUTED]


def test_a_finished_case_is_never_merged_into(client, seeded):
    report(client, CITIZEN_1)
    seeded.execute(text("UPDATE cases SET state = 'RESOLVED'"))
    seeded.commit()

    report(client, CITIZEN_2)
    assert cases(seeded)[1].state == CaseState.ROUTED


def test_a_different_animal_in_the_same_place_is_a_separate_case(app, client, seeded):
    use_triager(app, SpeciesInTurn(("dog", "high"), ("cow", "high")))
    report(client, CITIZEN_1)
    report(client, CITIZEN_2)
    assert [c.state for c in cases(seeded)] == [CaseState.ROUTED, CaseState.ROUTED]


def test_the_same_animal_in_the_same_place_is_merged(app, client, seeded):
    use_triager(app, SpeciesInTurn(("dog", "low"), ("dog", "low")))
    report(client, CITIZEN_1)
    report(client, CITIZEN_2)
    assert cases(seeded)[1].state == CaseState.MERGED


def test_merging_keeps_the_more_urgent_reading(app, client, seeded):
    use_triager(app, SpeciesInTurn(
        ("dog", "medium"), ("dog", "critical")
    ))
    report(client, CITIZEN_1)
    report(client, CITIZEN_2)

    assert cases(seeded)[0].urgency == "critical"
    raised = seeded.scalars(select(Event).where(Event.type == "urgency_raised")).one()
    assert raised.data == {"from": "medium", "to": "critical", "because_of": "PAW-0002"}


def test_the_same_person_reporting_twice_is_told_it_was_added(client, seeded):
    report(client, CITIZEN_1)
    report(client, CITIZEN_1)
    assert replies(client, CITIZEN_1)[-1] == messages.render(
        "merged_same_reporter", case_id="PAW-0001"
    )


def test_a_third_report_tells_both_earlier_reporters(client, seeded):
    report(client, CITIZEN_1)
    report(client, CITIZEN_2)
    report(client, "+910000000003")

    update = messages.render("merged_earlier_reporter", case_id="PAW-0001", count=3)
    assert replies(client, CITIZEN_1)[-1] == update
    assert replies(client, CITIZEN_2)[-1] == update


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ("dog", "dog", True),
        ("dog", "cow", False),
        ("dog", None, True),  # triage could not tell: place and time decide
        ("unclear", "cat", True),
    ],
)
def test_similar_animal(a, b, expected):
    assert similar_animal(a, b) is expected
