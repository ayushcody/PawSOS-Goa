"""Slice 2: a photo and a location open a case."""

from datetime import timedelta

import pytest
from sqlalchemy import select, text

from app import messages
from app.cases import intake
from app.cases.geo import in_goa
from app.cases.models import Case, Event, Photo, Report

CITIZEN_1 = "+910000000001"
CITIZEN_2 = "+910000000002"
PANAJI = (15.4909, 73.8278)

# The smallest file that starts like a real PNG. Enough for our checks.
TINY_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def send_photo(client, number, data=TINY_PNG, mime="image/png"):
    return client.post(
        "/sim/inbound/photo",
        data={"from_number": number},
        files={"file": ("dog.png", data, mime)},
    )


def send_location(client, number, latitude=PANAJI[0], longitude=PANAJI[1]):
    return client.post(
        "/sim/inbound",
        json={"from_number": number, "kind": "location", "latitude": latitude, "longitude": longitude},
    )


def last_reply(client, number) -> str:
    transcript = client.get("/sim/messages", params={"phone": number}).json()
    return [m for m in transcript if m["direction"] == "out"][-1]["text"]


def test_photo_then_location_opens_a_case(client, db):
    send_photo(client, CITIZEN_1)
    assert last_reply(client, CITIZEN_1) == messages.render("ask_location")
    assert db.scalars(select(Case)).all() == []

    send_location(client, CITIZEN_1)
    case = db.scalars(select(Case)).one()
    assert case.public_id == "PAW-0001"
    assert case.state == "REPORTED"
    assert last_reply(client, CITIZEN_1) == messages.render("case_created", case_id="PAW-0001")


def test_location_then_photo_opens_a_case(client, db):
    send_location(client, CITIZEN_1)
    assert last_reply(client, CITIZEN_1) == messages.render("ask_photo")

    send_photo(client, CITIZEN_1)
    assert db.scalars(select(Case)).one().public_id == "PAW-0001"


def test_case_keeps_the_location_and_the_photo(client, db):
    send_photo(client, CITIZEN_1)
    send_location(client, CITIZEN_1)

    # ST_Y is latitude and ST_X is longitude: PostGIS stores longitude first.
    latitude, longitude = db.execute(
        text("SELECT ST_Y(location::geometry), ST_X(location::geometry) FROM cases")
    ).one()
    assert (round(latitude, 4), round(longitude, 4)) == PANAJI

    report = db.scalars(select(Report)).one()
    assert report.case_id is not None
    photo = db.scalars(select(Photo)).one()
    assert photo.report_id == report.id
    assert client.get(f"/media/{photo.path}").status_code == 200


def test_every_step_is_in_the_audit_log(client, db):
    send_photo(client, CITIZEN_1)
    send_location(client, CITIZEN_1)

    events = db.scalars(select(Event).order_by(Event.id)).all()
    assert [e.type for e in events] == ["photo_received", "location_received", "case_created"]
    created = events[-1]
    assert created.case_id is not None
    assert created.to_state == "REPORTED"
    assert created.actor == CITIZEN_1


def test_two_people_do_not_complete_each_others_reports(client, db):
    send_photo(client, CITIZEN_1)
    send_location(client, CITIZEN_2)
    assert db.scalars(select(Case)).all() == []
    assert last_reply(client, CITIZEN_2) == messages.render("ask_photo")


def test_a_new_photo_after_a_case_starts_a_new_report(client, db):
    send_photo(client, CITIZEN_1)
    send_location(client, CITIZEN_1)
    send_photo(client, CITIZEN_1)
    assert last_reply(client, CITIZEN_1) == messages.render("ask_location")
    assert len(db.scalars(select(Case)).all()) == 1

    send_location(client, CITIZEN_1)
    assert [c.public_id for c in db.scalars(select(Case).order_by(Case.id))] == [
        "PAW-0001",
        "PAW-0002",
    ]


def test_an_old_half_finished_report_is_not_reused(client, db):
    send_photo(client, CITIZEN_1)
    stale = intake.DRAFT_WINDOW + timedelta(minutes=1)
    db.execute(text("UPDATE reports SET created_at = now() - :age"), {"age": stale})
    db.commit()

    send_location(client, CITIZEN_1)
    assert db.scalars(select(Case)).all() == []
    assert last_reply(client, CITIZEN_1) == messages.render("ask_photo")


def test_a_file_that_is_not_a_photo_is_refused(client, db):
    send_photo(client, CITIZEN_1, data=b"%PDF-1.7 not a photo", mime="application/pdf")
    assert last_reply(client, CITIZEN_1) == messages.render("photo_rejected")
    assert db.scalars(select(Report)).all() == []


def test_a_file_only_pretending_to_be_a_photo_is_refused(client, db):
    send_photo(client, CITIZEN_1, data=b"<script>alert(1)</script>", mime="image/png")
    assert last_reply(client, CITIZEN_1) == messages.render("photo_rejected")
    assert db.scalars(select(Photo)).all() == []


def test_media_route_refuses_made_up_names(client):
    assert client.get("/media/..%2F..%2F.env").status_code == 404
    assert client.get("/media/secret.txt").status_code == 404


def test_format_case_id():
    assert intake.format_case_id(7) == "PAW-0007"
    assert intake.format_case_id(12345) == "PAW-12345"


# --- TODO(me): Ayush implements in_goa() in app/cases/geo.py, then removes the skips ---


@pytest.mark.skip(reason="TODO(me): implement in_goa() in app/cases/geo.py")
def test_in_goa():
    assert in_goa(15.4909, 73.8278)  # Panaji
    assert in_goa(15.0100, 74.0230)  # Canacona, far south
    assert not in_goa(19.0760, 72.8777)  # Mumbai
    assert not in_goa(12.9716, 77.5946)  # Bengaluru


@pytest.mark.skip(reason="TODO(me): implement in_goa() in app/cases/geo.py")
def test_a_location_outside_goa_does_not_open_a_case(client, db):
    send_photo(client, CITIZEN_1)
    send_location(client, CITIZEN_1, latitude=19.0760, longitude=72.8777)
    assert last_reply(client, CITIZEN_1) == messages.render("outside_goa")
    assert db.scalars(select(Case)).all() == []
