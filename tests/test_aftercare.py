"""After a case is resolved: the reporter's rating and the team's rescue photo.

Everything runs on the simulator. Nothing here reaches an outside service.
"""

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app import messages
from app.cases.aftercare import Rating, RescuePhoto, satisfaction_percent
from app.cases.models import Case, Event, Photo
from app.cases.models import CaseState as S
from app.config import get_settings
from tests.whatsapp_fakes import JPEG

ASHA = "+910000000001"
BINA = "+910000000002"
PANAJI_TEAM = "+910000000101"
MAPUSA_TEAM = "+910000000102"
PANAJI = {"latitude": 15.4909, "longitude": 73.8278}
MAPUSA = {"latitude": 15.5937, "longitude": 73.8142}
CASE = "PAW-0001"


# ---------- helpers ----------


def say(client, words, number=ASHA):
    return client.post("/sim/inbound", json={"from_number": number, "kind": "text", "text": words})


def photo(client, number=ASHA):
    return client.post(
        "/sim/inbound/photo", data={"from_number": number}, files={"file": ("a.jpg", JPEG, "image/jpeg")}
    )


def locate(client, number=ASHA, place=PANAJI):
    return client.post("/sim/inbound", json={"from_number": number, "kind": "location", **place})


def press(client, number, button_id):
    return client.post(
        "/sim/inbound", json={"from_number": number, "kind": "button", "button_id": button_id}
    )


def report(client, number=ASHA, place=PANAJI):
    photo(client, number)
    locate(client, number, place)


def resolve(client, team=PANAJI_TEAM, case_id=CASE):
    for action in ("accept", "onsite", "resolved"):
        press(client, team, f"{action}:{case_id}")


def sent(client, number=ASHA) -> list[dict]:
    transcript = client.get("/sim/messages", params={"phone": number}).json()
    return [m for m in transcript if m["direction"] == "out"]


def last(client, number=ASHA) -> dict:
    return sent(client, number)[-1]


def event_types(session: Session) -> list[str]:
    return list(session.scalars(select(Event.type).order_by(Event.id)))


def ratings(session: Session) -> list[tuple[str, str]]:
    session.expire_all()
    return [(r.reporter_number, r.score) for r in session.scalars(select(Rating).order_by(Rating.id))]


# ---------- the rating ----------


def test_after_resolved_the_reporter_is_asked_how_it_went(client, seeded):
    report(client)
    resolve(client)
    resolved, ask = sent(client)[-2:]
    assert resolved["text"] == messages.render("citizen_resolved", case_id=CASE)
    assert ask["text"] == messages.render("rating_ask", case_id=CASE)
    assert ask["buttons"] == [
        {"id": f"rate:{CASE}:good", "title": "Good"},
        {"id": f"rate:{CASE}:ok", "title": "OK"},
        {"id": f"rate:{CASE}:poor", "title": "Poor"},
    ]


def test_a_tap_saves_the_rating_and_thanks_the_reporter(client, seeded):
    report(client)
    resolve(client)
    press(client, ASHA, f"rate:{CASE}:good")
    assert last(client)["text"] == messages.render("rating_thanks", case_id=CASE)
    assert ratings(seeded) == [(ASHA, "good")]
    rated = seeded.scalars(select(Event).where(Event.type == "case_rated")).one()
    assert rated.actor == ASHA and rated.data == {"score": "good"}


def test_a_second_tap_changes_the_rating_instead_of_adding_one(client, seeded):
    report(client)
    resolve(client)
    press(client, ASHA, f"rate:{CASE}:good")
    press(client, ASHA, f"rate:{CASE}:poor")
    assert ratings(seeded) == [(ASHA, "poor")]


def test_each_reporter_of_a_shared_case_is_asked_in_their_own_language(client, seeded):
    say(client, "LANGUAGE", BINA)
    say(client, "4", BINA)
    report(client, ASHA)
    report(client, BINA)  # merged into the same case
    resolve(client)

    assert last(client, ASHA)["text"] == messages.render("rating_ask", "en", case_id=CASE)
    hindi = last(client, BINA)
    assert hindi["text"] == messages.render("rating_ask", "hi", case_id=CASE)
    assert [b["title"] for b in hindi["buttons"]] == ["अच्छा", "ठीक", "ख़राब"]

    press(client, ASHA, f"rate:{CASE}:good")
    press(client, BINA, f"rate:{CASE}:ok")
    assert last(client, BINA)["text"] == messages.render("rating_thanks", "hi", case_id=CASE)
    assert ratings(seeded) == [(ASHA, "good"), (BINA, "ok")]


def test_a_reporter_who_withdrew_is_not_asked(client, seeded):
    report(client, ASHA)
    report(client, BINA)
    say(client, f"CANCEL {CASE}", ASHA)
    before = len(sent(client, ASHA))
    resolve(client)
    assert len(sent(client, ASHA)) == before
    assert last(client, BINA)["text"] == messages.render("rating_ask", case_id=CASE)


@pytest.mark.parametrize(
    ("who", "button"),
    [
        (BINA, f"rate:{CASE}:good"),  # someone who did not report it
        (PANAJI_TEAM, f"rate:{CASE}:good"),  # the team rating its own work
        (ASHA, "rate:PAW-0999:good"),  # a case that does not exist
    ],
)
def test_only_a_reporter_of_the_case_can_rate_it(client, seeded, who, button):
    report(client)
    resolve(client)
    press(client, who, button)
    assert last(client, who)["text"] == messages.render("rating_unavailable")
    assert ratings(seeded) == []


def test_a_case_that_is_not_resolved_cannot_be_rated(client, seeded):
    report(client)
    press(client, ASHA, f"rate:{CASE}:good")
    assert last(client)["text"] == messages.render("rating_unavailable")
    assert ratings(seeded) == []


def test_a_made_up_score_is_not_a_rating(client, seeded):
    report(client)
    resolve(client)
    press(client, ASHA, f"rate:{CASE}:excellent")
    assert ratings(seeded) == []


def test_tapping_resolved_twice_asks_for_a_rating_once(client, seeded):
    report(client)
    resolve(client)
    press(client, PANAJI_TEAM, f"resolved:{CASE}")
    asks = [m for m in sent(client) if m["text"] == messages.render("rating_ask", case_id=CASE)]
    assert len(asks) == 1


def test_every_rating_button_title_fits_whatsapps_limit():
    for language in messages.LANGUAGES:
        for score in ("good", "ok", "poor"):
            assert len(messages.render(f"rating_{score}", language)) <= 20, (language, score)


# ---------- the rescue photo ----------


def test_the_team_is_invited_to_send_a_photo(client, seeded):
    report(client)
    resolve(client)
    assert last(client, PANAJI_TEAM)["text"] == messages.render("team_resolved_ack", case_id=CASE)
    assert "photo" in last(client, PANAJI_TEAM)["text"]


def test_a_photo_from_the_team_is_passed_to_the_reporter(client, seeded):
    report(client)
    resolve(client)
    photo(client, PANAJI_TEAM)

    seeded.expire_all()
    stored = seeded.scalars(select(RescuePhoto)).one()
    assert stored.case_id == seeded.scalars(select(Case.id)).one()

    picture, caption = sent(client)[-2:]
    assert picture["media_url"] == f"/media/{stored.path}"
    assert caption["text"] == messages.render("rescue_photo_caption", case_id=CASE)
    assert last(client, PANAJI_TEAM)["text"] == messages.render("team_photo_passed_on", case_id=CASE)
    assert "rescue_photo_received" in event_types(seeded)

    # It is not mistaken for a new report: no draft, no second case.
    assert seeded.scalars(select(Photo)).all() == [seeded.scalars(select(Photo)).first()]
    assert len(seeded.scalars(select(Case)).all()) == 1


def test_every_reporter_gets_the_photo_with_a_caption_in_their_language(client, seeded):
    say(client, "LANGUAGE", BINA)
    say(client, "3", BINA)
    report(client, ASHA)
    report(client, BINA)
    resolve(client)
    photo(client, PANAJI_TEAM)
    assert last(client, ASHA)["text"] == messages.render("rescue_photo_caption", "en", case_id=CASE)
    assert last(client, BINA)["text"] == messages.render("rescue_photo_caption", "mr", case_id=CASE)


def test_only_the_first_photo_is_the_rescue_photo(client, seeded):
    report(client)
    resolve(client)
    photo(client, PANAJI_TEAM)
    photo(client, PANAJI_TEAM)  # a second one starts an ordinary report from the team
    assert len(seeded.scalars(select(RescuePhoto)).all()) == 1
    assert last(client, PANAJI_TEAM)["text"] == messages.render("ask_location")


def test_a_photo_sent_long_after_resolving_is_an_ordinary_report(client, seeded):
    report(client)
    resolve(client)
    # The audit log is stamped by the database, so the test ages the event itself.
    seeded.execute(
        text("UPDATE events SET created_at = created_at - interval '31 minutes' WHERE to_state = :s"),
        {"s": S.RESOLVED},
    )
    seeded.commit()
    photo(client, PANAJI_TEAM)
    assert seeded.scalars(select(RescuePhoto)).all() == []
    assert last(client, PANAJI_TEAM)["text"] == messages.render("ask_location")


def test_a_photo_before_the_case_is_resolved_is_an_ordinary_report(client, seeded):
    report(client)
    press(client, PANAJI_TEAM, f"accept:{CASE}")
    photo(client, PANAJI_TEAM)
    assert seeded.scalars(select(RescuePhoto)).all() == []


def test_another_teams_photo_is_not_attached_to_the_case(client, seeded):
    report(client)
    resolve(client)
    photo(client, MAPUSA_TEAM)
    assert seeded.scalars(select(RescuePhoto)).all() == []
    assert last(client, MAPUSA_TEAM)["text"] == messages.render("ask_location")


def test_a_citizens_photo_still_starts_a_report(client, seeded):
    report(client)
    resolve(client)
    photo(client, ASHA)
    assert seeded.scalars(select(RescuePhoto)).all() == []
    assert last(client)["text"] == messages.render("ask_location")


def test_with_two_resolved_cases_the_photo_goes_to_the_latest(client, seeded):
    report(client, ASHA, PANAJI)
    resolve(client, PANAJI_TEAM, "PAW-0001")
    report(client, BINA, PANAJI)  # the first is closed, so this is a new case
    resolve(client, PANAJI_TEAM, "PAW-0002")
    photo(client, PANAJI_TEAM)
    assert last(client, BINA)["text"] == messages.render("rescue_photo_caption", case_id="PAW-0002")
    photo(client, PANAJI_TEAM)  # the next photo is for the earlier case
    assert last(client, ASHA)["text"] == messages.render("rescue_photo_caption", case_id="PAW-0001")


# ---------- on the dashboard ----------


def test_the_case_panel_shows_the_rescue_photo_and_the_ratings(client, seeded):
    report(client)
    resolve(client)
    photo(client, PANAJI_TEAM)
    press(client, ASHA, f"rate:{CASE}:good")

    response = client.get(f"/dashboard/cases/{CASE}")
    detail = response.json()
    assert len(detail["rescue_photos"]) == 1
    assert detail["ratings"]["good"] == 1 and detail["ratings"]["total"] == 1
    labels = [event["label"] for event in detail["events"]]
    assert "The team sent a photo after the rescue" in labels
    assert "A reporter rated how it went" in labels
    for number in (ASHA, ASHA.lstrip("+"), PANAJI_TEAM.lstrip("+")):
        assert number not in response.text  # ratings are counted, never attributed

    served = client.get(detail["rescue_photos"][0]["url"])
    assert served.status_code == 200 and served.content == JPEG
    assert client.get("/dashboard/rescue-photos/999").status_code == 404


def test_the_dashboard_counts_ratings_and_says_when_there_are_none(client, seeded):
    empty = client.get("/dashboard/data").json()["ratings"]
    assert empty["total"] == 0 and empty["satisfaction_percent"] is None

    report(client, ASHA)
    report(client, BINA)
    resolve(client)
    press(client, ASHA, f"rate:{CASE}:good")
    press(client, BINA, f"rate:{CASE}:poor")
    counted = client.get("/dashboard/data").json()["ratings"]
    assert (counted["good"], counted["ok"], counted["poor"], counted["total"]) == (1, 0, 1, 2)


def test_the_rescue_photo_needs_the_staff_password_when_one_is_set(client, seeded, monkeypatch):
    report(client)
    resolve(client)
    photo(client, PANAJI_TEAM)
    monkeypatch.setattr(get_settings(), "dashboard_password", "test-only-password")
    assert client.get("/dashboard/rescue-photos/1").status_code == 401


def test_a_reset_clears_ratings_and_rescue_photos(client, seeded):
    from seed.reset import reset

    report(client)
    resolve(client)
    photo(client, PANAJI_TEAM)
    press(client, ASHA, f"rate:{CASE}:good")
    seeded.commit()
    reset(seeded)
    seeded.commit()
    assert seeded.scalars(select(Rating)).all() == []
    assert seeded.scalars(select(RescuePhoto)).all() == []


@pytest.mark.skip(reason="TODO(me): write satisfaction_percent() in app/cases/aftercare.py")
def test_satisfaction_percent():
    assert satisfaction_percent(3, 1, 0) == 75
    assert satisfaction_percent(1, 1, 1) == 33
    assert satisfaction_percent(2, 0, 0) == 100
    assert satisfaction_percent(0, 2, 2) == 0
    assert satisfaction_percent(0, 0, 0) is None  # no ratings is not 0%
