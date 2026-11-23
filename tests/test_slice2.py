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


def replies(client, number) -> list[str]:
    transcript = client.get("/sim/messages", params={"phone": number}).json()
    return [m["text"] for m in transcript if m["direction"] == "out"]


def last_reply(client, number) -> str:
    return replies(client, number)[-1]


def test_photo_then_location_opens_a_case(client, db):
    send_photo(client, CITIZEN_1)
    assert last_reply(client, CITIZEN_1) == messages.render("ask_location")
    assert db.scalars(select(Case)).all() == []

    send_location(client, CITIZEN_1)
    case = db.scalars(select(Case)).one()
    assert case.public_id == "PAW-0001"
    assert messages.render("case_created", case_id="PAW-0001") in replies(client, CITIZEN_1)


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
    assert [e.type for e in events][:3] == ["photo_received", "location_received", "case_created"]
    created = events[2]
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


# --- in_goa(): Goa's real boundary (seed/goa_boundary.json), widened by 1 km ---

MUMBAI = (19.0760, 72.8777)

INSIDE_GOA = {
    "Panaji": (15.4909, 73.8278),
    "Mapusa": (15.5937, 73.8142),
    "Margao": (15.2832, 73.9862),
    "Vasco da Gama": (15.3982, 73.8113),
    "Pernem (north)": (15.7230, 73.7950),
    "Terekhol fort (northern tip)": (15.7230, 73.6870),
    "Valpoi (east)": (15.5320, 74.1370),
    "Mollem (east)": (15.3880, 74.2140),
    "Canacona (south)": (15.0100, 74.0230),
    # On the sand, just seaward of the mapped coastline: the 1 km margin keeps them in.
    "Palolem beach": (15.0100, 74.0170),
    "Polem (southern tip)": (14.9000, 74.0900),
    "Baga beach": (15.5560, 73.7510),
}

OUTSIDE_GOA = {
    "Mumbai": MUMBAI,
    "Bengaluru": (12.9716, 77.5946),
    # The nearest towns across the border, each at least 6 km beyond it.
    "Karwar, Karnataka": (14.8136, 74.1297),
    "Dodamarg, Maharashtra": (15.7557, 74.0177),
    "Sawantwadi, Maharashtra": (15.9050, 73.8210),
    "Anmod ghat, Karnataka side": (15.4300, 74.3700),
    "Londa, Karnataka": (15.4660, 74.5160),
    "Belagavi, Karnataka": (15.8497, 74.4977),
    "Arabian Sea, 23 km off Panaji": (15.4000, 73.5000),
}


@pytest.mark.parametrize("place", INSIDE_GOA)
def test_places_in_goa_are_in_goa(place):
    assert in_goa(*INSIDE_GOA[place])


@pytest.mark.parametrize("place", OUTSIDE_GOA)
def test_places_outside_goa_are_not(place):
    assert not in_goa(*OUTSIDE_GOA[place])


def test_a_mumbai_pin_does_not_open_a_case(client, db):
    send_photo(client, CITIZEN_1)
    send_location(client, CITIZEN_1, *MUMBAI)
    assert db.scalars(select(Case)).all() == []
    assert last_reply(client, CITIZEN_1) == messages.render("outside_goa")


def test_the_out_of_goa_reply_offers_to_send_the_location_again(client, db):
    send_photo(client, CITIZEN_1)
    send_location(client, CITIZEN_1, *MUMBAI)
    last = client.get("/sim/messages", params={"phone": CITIZEN_1}).json()[-1]
    assert last["location_request"] is True  # a one-tap "Send location" button


def test_the_out_of_goa_reply_is_polite_and_says_where_to_turn():
    reply = messages.render("outside_goa")
    assert reply.startswith("Thank you")
    assert "only in Goa" in reply
    assert "local" in reply  # who to contact outside Goa


def test_after_a_wrong_pin_the_right_one_still_opens_the_case(client, db):
    send_photo(client, CITIZEN_1)
    send_location(client, CITIZEN_1, *MUMBAI)
    send_location(client, CITIZEN_1)  # Panaji: the photo is still waiting
    assert db.scalars(select(Case)).one().public_id == "PAW-0001"


def test_a_bite_reported_outside_goa_gets_the_out_of_goa_reply(client, db):
    client.post("/sim/inbound", json={"from_number": CITIZEN_1, "kind": "text", "text": "a dog bit me"})
    send_location(client, CITIZEN_1, *MUMBAI)
    assert last_reply(client, CITIZEN_1) == messages.render("outside_goa")
