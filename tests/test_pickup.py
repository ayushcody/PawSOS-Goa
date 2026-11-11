"""The pick-up work merged on 11 Nov: STATUS and CANCEL, languages, the
reporter's words in team alerts, dashboard case detail and staff actions,
WhatsApp templates, and Bhashini speech recognition.

Everything runs on the simulator or against stand-ins. Nothing here reaches
Meta, Bhashini or any other outside service.
"""

import asyncio
import json
import string
from datetime import date, timedelta

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app import messages
from app.booking.flow import places_left
from app.booking.models import Booking, CampSlot
from app.cases import state_machine
from app.cases.models import Case, Event, Report
from app.cases.models import CaseState as S
from app.cases.state_machine import InvalidTransition
from app.channels import templates
from app.channels.base import Button, Outbound
from app.channels.whatsapp import WhatsAppError
from app.config import get_settings
from app.contacts import language_for
from app.dashboard.queries import _percentile
from app.db import get_engine
from app.routing.dispatch import MAX_ALERT_CHARS, _defang
from app.routing.models import Dispatch, Team
from app.voice.speech import (
    SIMULATED_MIME,
    BhashiniSpeechToText,
    SpeechUnavailable,
    Transcript,
)
from tests.whatsapp_fakes import JPEG, PHONE, FakeMeta, make_adapter

ASHA = "+910000000001"
BINA = "+910000000002"
CHETAN = "+910000000003"
PANAJI_TEAM = "+910000000101"
MAPUSA_TEAM = "+910000000102"
PANAJI = {"latitude": 15.4909, "longitude": 73.8278}
MAPUSA = {"latitude": 15.5937, "longitude": 73.8142}


# ---------- helpers ----------


def say(client, words, number=ASHA):
    return client.post("/sim/inbound", json={"from_number": number, "kind": "text", "text": words})


def photo(client, number=ASHA):
    return client.post(
        "/sim/inbound/photo", data={"from_number": number}, files={"file": ("a.jpg", JPEG, "image/jpeg")}
    )


def locate(client, number=ASHA, place=PANAJI):
    return client.post("/sim/inbound", json={"from_number": number, "kind": "location", **place})


def speak(client, words, language="en", number=ASHA):
    return client.post(
        "/sim/inbound/voice", json={"from_number": number, "spoken_text": words, "language": language}
    )


def press(client, number, action, case_id="PAW-0001"):
    return client.post(
        "/sim/inbound", json={"from_number": number, "kind": "button", "button_id": f"{action}:{case_id}"}
    )


def report(client, number=ASHA, place=PANAJI, words=None):
    """A complete report: photo, optional description, location."""
    photo(client, number)
    if words:
        say(client, words, number)
    locate(client, number, place)


def replies(client, number=ASHA) -> list[str]:
    transcript = client.get("/sim/messages", params={"phone": number}).json()
    return [m["text"] for m in transcript if m["direction"] == "out"]


def last(client, number=ASHA) -> str:
    return replies(client, number)[-1]


def case(session: Session, public_id="PAW-0001") -> Case:
    session.expire_all()
    return session.scalars(select(Case).where(Case.public_id == public_id)).one()


def event_types(session: Session) -> list[str]:
    return list(session.scalars(select(Event.type).order_by(Event.id)))


def choose_language(client, choice, number=ASHA):
    say(client, "LANGUAGE", number)
    say(client, str(choice), number)


# ---------- STATUS ----------


def test_status_with_nothing_open_says_so(client, seeded):
    say(client, "STATUS")
    assert replies(client) == [messages.render("status_nothing")]


def test_status_lists_an_open_case_with_its_area_and_state(client, seeded):
    report(client)
    say(client, "status")
    answer = last(client)
    assert "PAW-0001" in answer and "Panaji area" in answer
    assert messages.render("status_state_team_alerted") in answer


def test_status_follows_the_case_as_it_moves(client, seeded):
    report(client)
    press(client, PANAJI_TEAM, "accept")
    say(client, "STATUS")
    assert "Panaji partner team (placeholder) has accepted it" in last(client)


def test_a_closed_case_is_no_longer_in_status(client, seeded):
    report(client)
    for action in ("accept", "onsite", "resolved"):
        press(client, PANAJI_TEAM, action)
    say(client, "STATUS")
    assert last(client) == messages.render("status_nothing")


def test_a_spoken_status_works(client, seeded):
    speak(client, "Status.")  # speech services add the full stop
    assert last(client) == messages.render("status_nothing")


# ---------- CANCEL a report ----------


def test_cancel_shows_a_numbered_list_and_a_number_cancels(client, seeded):
    report(client)
    say(client, "CANCEL")
    assert "1. Report PAW-0001" in last(client)

    say(client, "1")
    assert last(client) == messages.render("case_cancelled_team_told", case_id="PAW-0001")
    assert case(seeded).state == S.CANCELLED
    assert last(client, PANAJI_TEAM) == messages.render(
        "team_case_cancelled_by_reporter", case_id="PAW-0001"
    )
    assert seeded.scalars(select(Dispatch.status)).all() == ["cancelled"]
    assert "team_stood_down" in event_types(seeded)


def test_a_team_cannot_accept_a_case_its_reporter_cancelled(client, seeded):
    report(client)
    say(client, "CANCEL PAW-0001")
    press(client, PANAJI_TEAM, "accept")
    assert case(seeded).state == S.CANCELLED
    assert case(seeded).assigned_team_id is None


def test_cancel_by_case_id_needs_no_list(client, seeded):
    report(client)
    say(client, "cancel paw 1")  # voice notes drop the dash and the zeros
    assert case(seeded).state == S.CANCELLED


def test_nobody_can_cancel_another_persons_case(client, seeded):
    report(client)
    say(client, "CANCEL PAW-0001", BINA)
    assert case(seeded).state != S.CANCELLED
    # The answer is the same as for a case that does not exist.
    assert last(client, BINA) == messages.render("cancel_not_found", ref="PAW-0001")
    say(client, "CANCEL PAW-0999", BINA)
    assert last(client, BINA) == messages.render("cancel_not_found", ref="PAW-0999")


def test_cancel_with_nothing_open_says_so(client, seeded):
    say(client, "CANCEL")
    assert last(client) == messages.render("cancel_nothing")


def test_a_number_outside_the_cancel_list_asks_again(client, seeded):
    report(client)
    say(client, "CANCEL")
    say(client, "7")
    assert last(client) == messages.render("cancel_invalid_choice")
    assert case(seeded).state != S.CANCELLED


def test_a_closed_case_cannot_be_cancelled_twice(client, seeded):
    report(client)
    say(client, "CANCEL PAW-0001")
    say(client, "CANCEL PAW-0001")
    assert last(client) == messages.render("case_cancel_closed", case_id="PAW-0001")


# ---------- CANCEL on a case two people reported ----------


def shared_case(client):
    report(client, ASHA)
    report(client, BINA)  # same place: merged into PAW-0001


def test_one_reporter_of_a_shared_case_withdraws_and_the_case_stays_open(client, seeded):
    shared_case(client)
    say(client, "CANCEL PAW-0001", ASHA)

    assert last(client, ASHA) == messages.render("case_cancel_shared", case_id="PAW-0001")
    assert case(seeded).state == S.ROUTED
    assert "report_withdrawn" in event_types(seeded)
    assert seeded.scalars(select(Dispatch.status)).all() == ["sent"]  # the team is still asked

    # It is no longer theirs: not in STATUS, and no more updates.
    say(client, "STATUS", ASHA)
    assert last(client, ASHA) == messages.render("status_nothing")
    before = len(replies(client, ASHA))
    press(client, PANAJI_TEAM, "accept")
    assert len(replies(client, ASHA)) == before
    assert "accepted" in last(client, BINA)


def test_when_the_last_reporter_cancels_the_shared_case_is_cancelled(client, seeded):
    shared_case(client)
    say(client, "CANCEL PAW-0001", ASHA)
    say(client, "CANCEL PAW-0001", BINA)

    assert last(client, BINA) == messages.render("case_cancelled_team_told", case_id="PAW-0001")
    assert case(seeded).state == S.CANCELLED
    assert last(client, PANAJI_TEAM) == messages.render(
        "team_case_cancelled_by_reporter", case_id="PAW-0001"
    )


def test_a_person_who_withdrew_cannot_cancel_the_case_for_the_others(client, seeded):
    shared_case(client)
    say(client, "CANCEL PAW-0001", ASHA)
    say(client, "CANCEL PAW-0001", ASHA)
    assert last(client, ASHA) == messages.render("cancel_not_found", ref="PAW-0001")
    assert case(seeded).state == S.ROUTED


def test_a_person_who_withdrew_and_reports_again_gets_updates_again(client, seeded):
    shared_case(client)
    say(client, "CANCEL PAW-0001", ASHA)
    report(client, ASHA)  # they see the animal is still there
    press(client, PANAJI_TEAM, "accept")
    assert "accepted" in last(client, ASHA)


# ---------- CANCEL a booking ----------


def book(client, number=ASHA):
    for words in ("BOOK", "1", "2"):
        say(client, words, number)


def test_status_shows_a_booking_and_cancel_frees_the_place(client, seeded):
    book(client)
    booking = seeded.scalars(select(Booking)).one()
    slot = seeded.get(CampSlot, booking.slot_id)
    full = places_left(seeded, slot) + 1

    say(client, "STATUS")
    assert booking.reference in last(client)

    say(client, f"CANCEL {booking.reference}")
    assert "is cancelled" in last(client)
    seeded.expire_all()
    assert places_left(seeded, slot) == full

    book(client)  # the same person can book again
    assert last(client).startswith("Booked.")


def test_a_number_typed_while_booking_goes_to_the_booking(client, seeded):
    report(client)  # so a CANCEL list would have something in it
    say(client, "LANGUAGE")  # and a language menu is open
    book(client)
    assert last(client).startswith("Booked.")
    assert case(seeded).state != S.CANCELLED
    assert language_for(seeded, ASHA) == "en"


# ---------- languages ----------


def test_language_menu_then_a_number_switches_the_replies(client, seeded):
    say(client, "LANGUAGE")
    assert last(client) == messages.render("language_menu")
    say(client, "4")
    assert last(client) == messages.render("language_set", "hi")
    say(client, "hi")
    assert last(client) == messages.render("welcome", "hi")
    assert language_for(seeded, ASHA) == "hi"


def test_a_number_outside_the_language_menu_shows_it_again(client, seeded):
    say(client, "LANGUAGE")
    say(client, "9")
    assert last(client) == messages.render("language_menu")
    assert language_for(seeded, ASHA) == "en"


def test_a_language_can_be_chosen_by_name(client, seeded):
    say(client, "भाषा")
    say(client, "मराठी")
    assert last(client) == messages.render("language_set", "mr")


def test_a_report_is_answered_in_the_persons_language_and_the_team_in_english(client, seeded):
    choose_language(client, 4)
    report(client)
    assert messages.render("case_created", "hi", case_id="PAW-0001") in replies(client)
    assert messages.render("zone_assigned", "hi", case_id="PAW-0001", zone="पणजी") in replies(client)
    assert last(client, PANAJI_TEAM).startswith("New case PAW-0001 in Panaji.")


def test_each_reporter_of_a_shared_case_is_told_in_their_own_language(client, seeded):
    choose_language(client, 3, BINA)
    shared_case(client)
    press(client, PANAJI_TEAM, "accept")
    team = "Panaji partner team (placeholder)"
    assert last(client, ASHA) == messages.render("citizen_accepted", "en", case_id="PAW-0001", team=team)
    assert last(client, BINA) == messages.render("citizen_accepted", "mr", case_id="PAW-0001", team=team)


def test_a_voice_note_in_hindi_sets_the_language_once(client, seeded):
    speak(client, "नमस्ते", language="hi")
    assert language_for(seeded, ASHA) == "hi"
    choose_language(client, 1)
    speak(client, "नमस्ते", language="hi")  # a choice the person made is kept
    assert language_for(seeded, ASHA) == "en"


def _placeholders(template: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(template) if name}


def test_every_translation_keeps_the_placeholders_of_its_english():
    for key, versions in messages.MESSAGES.items():
        for language, template in versions.items():
            assert _placeholders(template) == _placeholders(versions["en"]), (key, language)


def test_a_message_with_one_translation_has_all_three():
    for key, versions in messages.MESSAGES.items():
        assert len(versions) in (1, 4), key


# ---------- dates and place names in the reader's language ----------


def test_dates_are_written_in_the_readers_language():
    day = date(2026, 11, 28)  # a Saturday
    assert messages.date_words(day) == "Sat 28 Nov"
    assert messages.date_words(day, "hi") == "शनिवार 28 नवंबर"
    assert messages.date_words(day, "mr") == "शनिवार 28 नोव्हेंबर"
    assert messages.date_words(day, "kok") == "शेनवार 28 नोव्हेंबर"
    assert messages.date_words(day, "fr") == "Sat 28 Nov"  # unknown: English


def test_every_language_has_seven_days_and_twelve_months():
    for language in messages.LANGUAGES:
        assert len(messages.WEEKDAYS[language]) == 7 and len(messages.MONTHS[language]) == 12


def test_every_seeded_area_has_a_name_in_each_language(seeded):
    from app.routing.models import Zone

    for name in seeded.scalars(select(Zone.short_name)):
        for language in ("kok", "mr", "hi"):
            assert messages.place_name(name, language) != name, (name, language)
        assert messages.place_name(name, "en") == name
    assert messages.place_name("Somewhere new", "hi") == "Somewhere new"


def test_status_in_hindi_has_no_english_day_or_area(client, seeded, clock):
    choose_language(client, 4)
    report(client)
    say(client, "STATUS")
    answer = last(client)
    assert "पणजी" in answer and "Panaji" not in answer
    today = clock.now()
    assert messages.date_words(today, "hi") in answer
    assert f"{today:%a}" not in answer


def test_a_booking_in_marathi_has_its_date_in_marathi(client, seeded):
    choose_language(client, 3)
    book(client)
    slot = seeded.get(CampSlot, seeded.scalars(select(Booking.slot_id)).one())
    assert messages.date_words(slot.starts_at.astimezone(), "mr").split()[-1] in last(client)


# ---------- the reporter's words in the team alert ----------


def test_a_typed_description_is_thanked_for_and_reaches_the_team(client, seeded):
    photo(client)
    say(client, "brown dog limping near the bus stand")
    assert last(client) == messages.render("note_ask_location")
    locate(client)
    assert 'Reporter says: "brown dog limping near the bus stand"' in last(client, PANAJI_TEAM)
    assert "description_typed" in event_types(seeded)


def test_a_description_sent_after_the_location_asks_for_the_photo(client, seeded):
    locate(client)
    say(client, "a cow with a rope on its leg")
    assert last(client) == messages.render("note_ask_photo")


def test_a_spoken_description_is_marked_as_possibly_misheard(client, seeded):
    speak(client, "एक कुत्ता सड़क पर घायल पड़ा है", language="hi")
    report(client)
    assert "voice note, may be misheard" in last(client, PANAJI_TEAM)
    assert "एक कुत्ता सड़क पर घायल पड़ा है" in last(client, PANAJI_TEAM)


def test_a_greeting_is_not_kept_as_a_description(client, seeded):
    photo(client)
    say(client, "hello")
    locate(client)
    assert "Reporter says" not in last(client, PANAJI_TEAM)


def test_links_and_phone_numbers_are_taken_out_of_reporter_words(client, seeded):
    report(client, words="see evil.com/x or EVIL.COM or http://x.co, ring 98220 12345")
    alert = last(client, PANAJI_TEAM)
    assert "evil" not in alert.lower() and "x.co" not in alert
    assert "98220" not in alert
    assert alert.count("[link removed]") == 3 and "[number removed]" in alert
    assert alert.count("https://") == 1  # only our own map link


@pytest.mark.parametrize(
    ("words", "cleaned"),
    [
        ("visit EVIL.COM now", "visit [link removed] now"),
        ("visit Evil.Net/pay now", "visit [link removed] now"),
        ("www.bad.example/x", "[link removed]"),
        # Endings that are also everyday words keep their words but can no longer be a link.
        ("pay.in and bad.me", "pay. in and bad. me"),
        ("near the market.It is bleeding", "near the market. It is bleeding"),
        ("seen on 10.11.2026 at 5.30", "seen on 10.11.2026 at 5.30"),
        ("call +91 98220-12345", "call [number removed]"),
        ("house 1234, lane 5", "house 1234, lane 5"),
        ('he said "come"', "he said come"),
        ("evil\u200b.com", "[link removed]"),  # a hidden character cannot split a link
        ("ｅｖｉｌ．ｃｏｍ", "[link removed]"),  # full-width letters
    ],
)
def test_defang(words, cleaned):
    assert _defang(words) == cleaned


def test_a_very_long_description_keeps_the_alert_inside_whatsapps_limit(client, seeded):
    report(client, words="the dog is hurt and lying by the road " * 25)
    alert = last(client, PANAJI_TEAM)
    assert len(alert) <= MAX_ALERT_CHARS
    assert "…" in alert and "Location: https://maps.google.com" in alert


# ---------- a second report of the same animal ----------


def test_the_second_reporter_never_sees_a_case_id_that_vanishes(client, seeded):
    shared_case(client)
    heard = replies(client, BINA)
    assert messages.render("case_checking_duplicate") in heard
    assert not any("PAW-0002" in line for line in heard)
    assert last(client, BINA) == messages.render("merged_new_reporter", case_id="PAW-0001")


def test_a_first_report_still_gets_its_case_id_at_once(client, seeded):
    report(client)
    assert replies(client)[1] == messages.render("case_created", case_id="PAW-0001")


# ---------- a bite report and an animal report at the same time ----------


def test_one_location_answers_a_bite_and_a_waiting_photo(client, seeded):
    say(client, "a dog bit me")
    photo(client)
    locate(client)
    heard = replies(client)
    assert any(line.startswith("Nearest health centre") for line in heard)
    assert messages.render("case_created", case_id="PAW-0001") in heard
    assert case(seeded).state == S.ROUTED


def test_a_bite_location_with_no_photo_waiting_opens_no_case(client, seeded):
    say(client, "a dog bit me")
    locate(client)
    assert last(client).startswith("Nearest health centre")
    assert seeded.scalars(select(Case)).all() == []
    assert seeded.scalars(select(Report)).all() == []


# ---------- dashboard: one case in detail ----------


def test_case_detail_shows_the_trail_and_never_a_phone_number(client, seeded):
    report(client, words="limping near the bus stand")
    press(client, PANAJI_TEAM, "accept")
    response = client.get("/dashboard/cases/PAW-0001")
    assert response.status_code == 200
    detail = response.json()

    assert detail["state"] == S.ACCEPTED and detail["open"] is True
    assert detail["team"] == "Panaji partner team (placeholder)"
    assert detail["reporters"] == 1 and detail["reports"] == 1
    assert detail["notes"][0]["reporter"] == "Reporter 1"
    assert detail["notes"][0]["text"] == "limping near the bus stand"
    assert len(detail["photos"]) == 1
    labels = [event["label"] for event in detail["events"]]
    assert "Description received (typed)" in labels and "Case opened" in labels
    for number in (ASHA, PANAJI_TEAM, ASHA.lstrip("+"), PANAJI_TEAM.lstrip("+")):
        assert number not in response.text


def test_case_detail_for_an_unknown_case_is_404(client, seeded):
    assert client.get("/dashboard/cases/PAW-0404").status_code == 404


def test_a_stored_photo_is_served_by_its_id(client, seeded):
    report(client)
    served = client.get("/dashboard/photos/1")
    assert served.status_code == 200 and served.content == JPEG
    assert client.get("/dashboard/photos/999").status_code == 404


def test_a_withdrawal_is_in_the_case_history(client, seeded):
    shared_case(client)
    say(client, "CANCEL PAW-0001", ASHA)
    labels = [e["label"] for e in client.get("/dashboard/cases/PAW-0001").json()["events"]]
    assert "A reporter withdrew; the case stays open for the others" in labels


# ---------- dashboard: staff actions ----------


def team_id(session: Session, phone: str) -> int:
    return session.scalars(select(Team.id).where(Team.phone == phone)).one()


def test_staff_send_a_case_to_another_team(client, seeded):
    report(client)
    response = client.post(
        "/dashboard/cases/PAW-0001/assign",
        json={"team_id": team_id(seeded, MAPUSA_TEAM), "note": "Panaji van is out"},
    )
    assert response.status_code == 200

    assert last(client, MAPUSA_TEAM).startswith("New case PAW-0001 in Panaji.")
    assert last(client, PANAJI_TEAM) == messages.render("team_case_reassigned", case_id="PAW-0001")
    assert last(client) == messages.render(
        "citizen_staff_assigned", case_id="PAW-0001", team="Mapusa partner team (placeholder)"
    )
    assert "team_assigned_by_staff" in event_types(seeded)

    press(client, MAPUSA_TEAM, "accept")
    assert case(seeded).state == S.ACCEPTED
    assert case(seeded).assigned_team_id == team_id(seeded, MAPUSA_TEAM)


def test_the_team_that_was_stood_down_can_no_longer_accept(client, seeded):
    report(client)
    client.post("/dashboard/cases/PAW-0001/assign", json={"team_id": team_id(seeded, MAPUSA_TEAM)})
    press(client, PANAJI_TEAM, "accept")
    assert case(seeded).state == S.ROUTED and case(seeded).assigned_team_id is None


def test_when_the_staff_chosen_team_declines_the_case_comes_back_to_staff(client, seeded):
    report(client)
    client.post("/dashboard/cases/PAW-0001/assign", json={"team_id": team_id(seeded, MAPUSA_TEAM)})
    press(client, MAPUSA_TEAM, "decline")

    assert case(seeded).state == S.ESCALATED
    flagged = client.get("/dashboard/data").json()["attention"]
    assert [(c["id"], c["attention"]) for c in flagged] == [("PAW-0001", "no_team")]
    assert "could not take" in last(client)


def test_staff_cannot_assign_a_closed_case_or_an_unknown_team(client, seeded):
    report(client)
    assert client.post("/dashboard/cases/PAW-0001/assign", json={"team_id": 9999}).status_code == 404
    say(client, "CANCEL PAW-0001")
    response = client.post(
        "/dashboard/cases/PAW-0001/assign", json={"team_id": team_id(seeded, MAPUSA_TEAM)}
    )
    assert response.status_code == 409


def test_staff_cancel_tells_the_reporter_in_their_language_without_the_reason(client, seeded):
    choose_language(client, 4)
    report(client)
    reason = "Duplicate of a phone call to the helpline"
    response = client.post("/dashboard/cases/PAW-0001/cancel", json={"reason": reason})
    assert response.status_code == 200 and response.json()["state"] == S.CANCELLED

    assert last(client) == messages.render("citizen_cancelled", "hi", case_id="PAW-0001")
    assert reason not in last(client)
    assert last(client, PANAJI_TEAM) == messages.render(
        "team_case_cancelled_by_staff", case_id="PAW-0001"
    )
    cancelled = seeded.scalars(select(Event).where(Event.to_state == S.CANCELLED)).one()
    assert cancelled.actor == "staff" and cancelled.data["reason"] == reason


def test_staff_cancel_needs_a_reason_and_an_open_case(client, seeded):
    report(client)
    assert client.post("/dashboard/cases/PAW-0001/cancel", json={"reason": " x "}).status_code == 422
    assert case(seeded).state == S.ROUTED
    client.post("/dashboard/cases/PAW-0001/cancel", json={"reason": "test cancel"})
    again = client.post("/dashboard/cases/PAW-0001/cancel", json={"reason": "test cancel"})
    assert again.status_code == 409


@pytest.mark.parametrize(
    "headers",
    [{"Origin": "https://evil.example"}, {"Sec-Fetch-Site": "cross-site"}],
)
def test_staff_actions_from_another_website_are_refused(client, seeded, headers):
    report(client)
    response = client.post(
        "/dashboard/cases/PAW-0001/cancel", json={"reason": "from elsewhere"}, headers=headers
    )
    assert response.status_code == 403
    assert case(seeded).state == S.ROUTED


def test_staff_actions_need_the_password_when_one_is_set(client, seeded, monkeypatch):
    report(client)
    monkeypatch.setattr(get_settings(), "dashboard_password", "test-only-password")
    refused = client.post("/dashboard/cases/PAW-0001/cancel", json={"reason": "no password"})
    assert refused.status_code == 401
    allowed = client.post(
        "/dashboard/cases/PAW-0001/cancel",
        json={"reason": "with password"},
        auth=("staff", "test-only-password"),
    )
    assert allowed.status_code == 200


# ---------- dashboard: response times ----------


def test_percentile_interpolates_between_ranks():
    assert _percentile([10.0], 0.9) == 10.0
    assert _percentile([0.0, 100.0], 0.5) == 50.0
    assert _percentile([1.0, 2.0, 3.0, 4.0, 5.0], 0.9) == pytest.approx(4.6)


def test_response_times_come_from_the_audit_log(client, seeded):
    report(client)
    for action in ("accept", "onsite", "resolved"):
        press(client, PANAJI_TEAM, action)
    # The audit log is stamped by the database, so the test spaces the events out itself.
    opened = seeded.scalars(select(Event.created_at).where(Event.type == "case_created")).one()
    for state, minutes in ((S.ACCEPTED, 5), (S.RESOLVED, 25)):
        seeded.execute(
            text("UPDATE events SET created_at = :at WHERE to_state = :state"),
            {"at": opened + timedelta(minutes=minutes), "state": state},
        )
    seeded.commit()

    overall = client.get("/dashboard/data").json()["response_times"]["overall"]
    assert overall["report_to_accept"] == {"cases": 1, "median_seconds": 300, "p90_seconds": 300}
    assert overall["accept_to_resolve"] == {"cases": 1, "median_seconds": 1200, "p90_seconds": 1200}


def test_a_case_still_waiting_is_not_counted_in_response_times(client, seeded):
    report(client)
    overall = client.get("/dashboard/data").json()["response_times"]["overall"]
    assert overall["report_to_accept"]["cases"] == 0
    assert overall["report_to_accept"]["median_seconds"] is None


# ---------- the state machine trusts the database, not a stale copy ----------


def test_a_stale_copy_cannot_reopen_a_closed_case(client, seeded):
    report(client)
    stale = case(seeded)
    assert stale.state == S.ROUTED
    seeded.commit()

    with Session(get_engine()) as other:  # someone else cancels it meanwhile
        fresh = other.scalars(select(Case)).one()
        state_machine.transition(other, fresh, S.CANCELLED, actor="staff")
        other.commit()

    # `stale` still says ROUTED in memory; ROUTED to ACCEPTED would be allowed.
    with pytest.raises(InvalidTransition):
        state_machine.transition(seeded, stale, S.ACCEPTED, actor=PANAJI_TEAM)
    seeded.rollback()
    assert case(seeded).state == S.CANCELLED


# ---------- WhatsApp templates when the 24-hour window is closed ----------


class ClosedWindowMeta(FakeMeta):
    """Meta when the person last wrote more than 24 hours ago: only templates go through."""

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/messages"):
            body = json.loads(request.content)
            if body["type"] != "template":
                return httpx.Response(
                    400, json={"error": {"message": "Re-engagement message", "code": 131047}}
                )
        return super().__call__(request)


ALERT_VALUES = {
    "case_id": "PAW-0042", "zone": "Panaji", "urgency": "HIGH", "seen": "dog: limping",
    "map_link": "https://maps.google.com/?q=15.49090,73.82780", "reports": 1, "window": "600 seconds",
}


def alert_outbound() -> Outbound:
    payloads = ("accept:PAW-0042", "decline:PAW-0042")
    return Outbound(
        to="+" + PHONE,
        text=messages.render("team_alert", **ALERT_VALUES),
        buttons=[Button(id=payloads[0], title="Accept"), Button(id=payloads[1], title="Decline")],
        template=templates.fallback_for("team_alert", ALERT_VALUES, payloads),
    )


def test_only_some_messages_have_a_template():
    fallback = templates.fallback_for("team_alert", ALERT_VALUES)
    assert fallback.params == tuple(str(ALERT_VALUES[name]) for name in templates.PARAMS["team_alert"])
    assert templates.fallback_for("welcome", {}) is None


def test_a_template_name_comes_from_settings(monkeypatch):
    assert templates.template_name("team_alert") is None
    monkeypatch.setattr(get_settings(), "whatsapp_template_team_alert", "pawsos_team_alert")
    assert templates.template_name("team_alert") == "pawsos_team_alert"
    assert templates.template_name("welcome") is None


def test_outside_the_window_the_alert_goes_as_its_template(monkeypatch):
    monkeypatch.setattr(get_settings(), "whatsapp_template_team_alert", "pawsos_team_alert")
    meta = ClosedWindowMeta()
    adapter = make_adapter(meta)
    asyncio.run(adapter.send(alert_outbound()))

    (sent,) = meta.sent
    assert sent["type"] == "template" and sent["to"] == PHONE
    assert sent["template"]["name"] == "pawsos_team_alert"
    body, *buttons = sent["template"]["components"]
    assert body["parameters"][0]["text"] == "PAW-0042"
    assert len(body["parameters"]) == len(templates.PARAMS["team_alert"])
    assert len(buttons) == 2
    assert "accept:PAW-0042" in json.dumps(buttons)


def test_outside_the_window_with_no_template_set_up_nothing_is_sent(monkeypatch):
    monkeypatch.setattr(get_settings(), "whatsapp_template_team_alert", None)
    meta = ClosedWindowMeta()
    # The refusal is passed on, so the caller logs the failed send like any other.
    with pytest.raises(WhatsAppError):
        asyncio.run(make_adapter(meta).send(alert_outbound()))
    assert meta.sent == []


def test_inside_the_window_the_ordinary_message_is_sent(monkeypatch):
    monkeypatch.setattr(get_settings(), "whatsapp_template_team_alert", "pawsos_team_alert")
    meta = FakeMeta()
    asyncio.run(make_adapter(meta).send(alert_outbound()))
    assert [body["type"] for body in meta.sent] == ["interactive"]


def test_a_template_parameter_is_kept_on_one_line(monkeypatch):
    monkeypatch.setattr(get_settings(), "whatsapp_template_team_alert", "pawsos_team_alert")
    meta = ClosedWindowMeta()
    values = {**ALERT_VALUES, "seen": 'dog: limping\nReporter says: "by the\tbus   stand"'}
    message = alert_outbound()
    message.template = templates.fallback_for("team_alert", values)
    asyncio.run(make_adapter(meta).send(message))
    seen = meta.sent[0]["template"]["components"][0]["parameters"][3]["text"]
    assert seen == 'dog: limping Reporter says: "by the bus stand"'


# ---------- Bhashini speech recognition (against a stand-in) ----------

CONFIG_ANSWER = {
    "pipelineResponseConfig": [
        {
            "taskType": "asr",
            "config": [
                {"serviceId": "asr-hi-1", "language": {"sourceLanguage": "hi"}},
                {"serviceId": "asr-gom-1", "language": {"sourceLanguage": "gom"}},
            ],
        }
    ],
    "pipelineInferenceAPIEndPoint": {
        "callbackUrl": "https://bhashini.example.test/compute",
        "inferenceApiKey": {"name": "Authorization", "value": "test-only-inference-key"},
    },
}


class FakeBhashini:
    def __init__(self, heard: str = "कुत्ता घायल है") -> None:
        self.heard = heard
        self.config_calls: list[httpx.Request] = []
        self.compute_calls: list[dict] = []
        self.reject_key_times = 0
        self.config_status = 200

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.host == "bhashini.example.test":
            if self.reject_key_times:
                self.reject_key_times -= 1
                return httpx.Response(401)
            assert request.headers["Authorization"] == "test-only-inference-key"
            self.compute_calls.append(json.loads(request.content))
            return httpx.Response(
                200, json={"pipelineResponse": [{"taskType": "asr", "output": [{"source": self.heard}]}]}
            )
        self.config_calls.append(request)
        return httpx.Response(self.config_status, json=CONFIG_ANSWER)


def bhashini(fake: FakeBhashini, monkeypatch, **overrides) -> BhashiniSpeechToText:
    service = BhashiniSpeechToText(
        user_id="test-only-user", api_key="test-only-key", pipeline_id="test-only-pipeline",
        transport=httpx.MockTransport(fake), **overrides,
    )
    # ffmpeg is an outside program: the test hands back a pretend WAV instead of running it.
    monkeypatch.setattr(service, "_to_wav", lambda audio: b"RIFF" + b"0" * 100)
    return service


def test_bhashini_transcribes_a_voice_note(monkeypatch):
    fake = FakeBhashini()
    service = bhashini(fake, monkeypatch)
    heard = asyncio.run(service.transcribe(b"OggS....", "audio/ogg", "hi"))

    assert heard == Transcript("कुत्ता घायल है", "hi")
    (config_call,) = fake.config_calls
    assert config_call.headers["userID"] == "test-only-user"
    assert config_call.headers["ulcaApiKey"] == "test-only-key"
    task = fake.compute_calls[0]["pipelineTasks"][0]["config"]
    assert task["serviceId"] == "asr-hi-1" and task["language"] == {"sourceLanguage": "hi"}
    assert task["audioFormat"] == "wav" and task["samplingRate"] == 16000


def test_bhashini_uses_its_own_code_for_konkani_and_asks_for_the_models_once(monkeypatch):
    fake = FakeBhashini(heard="सुणें दुखयलां")
    service = bhashini(fake, monkeypatch)
    first = asyncio.run(service.transcribe(b"OggS", "audio/ogg", "kok"))
    asyncio.run(service.transcribe(b"OggS", "audio/ogg", None))  # no language: Konkani by default

    assert first.language == "kok"
    assert [c["pipelineTasks"][0]["config"]["serviceId"] for c in fake.compute_calls] == ["asr-gom-1"] * 2
    assert len(fake.config_calls) == 1  # the answer is kept for later voice notes


def test_bhashini_fetches_a_fresh_key_once_when_the_old_one_is_refused(monkeypatch):
    fake = FakeBhashini()
    fake.reject_key_times = 1
    heard = asyncio.run(bhashini(fake, monkeypatch).transcribe(b"OggS", "audio/ogg", "hi"))
    assert heard.text == "कुत्ता घायल है"
    assert len(fake.config_calls) == 2

    fake.reject_key_times = 2  # refused again after the fresh key: give up
    with pytest.raises(SpeechUnavailable):
        asyncio.run(bhashini(fake, monkeypatch).transcribe(b"OggS", "audio/ogg", "hi"))


@pytest.mark.parametrize(
    ("setup", "match"),
    [
        (lambda fake: setattr(fake, "config_status", 401), "refused"),
        (lambda fake: setattr(fake, "config_status", 500), "config call failed"),
        (lambda fake: setattr(fake, "heard", "   "), "heard no words"),
    ],
)
def test_bhashini_failures_become_speech_unavailable(monkeypatch, setup, match):
    fake = FakeBhashini()
    setup(fake)
    with pytest.raises(SpeechUnavailable, match=match):
        asyncio.run(bhashini(fake, monkeypatch).transcribe(b"OggS", "audio/ogg", "hi"))


def test_bhashini_says_when_the_pipeline_has_no_model_for_a_language(monkeypatch):
    with pytest.raises(SpeechUnavailable, match="no speech model for Marathi"):
        asyncio.run(bhashini(FakeBhashini(), monkeypatch).transcribe(b"OggS", "audio/ogg", "mr"))


def test_bhashini_without_keys_declines_real_audio_but_reads_simulated_notes():
    service = BhashiniSpeechToText()
    with pytest.raises(SpeechUnavailable, match="not set up"):
        asyncio.run(service.transcribe(b"OggS", "audio/ogg", "hi"))
    heard = asyncio.run(service.transcribe(b"hello", SIMULATED_MIME, "en"))
    assert heard == Transcript("hello", "en")


def test_bhashini_without_ffmpeg_declines_the_voice_note():
    service = BhashiniSpeechToText(
        user_id="test-only-user", api_key="test-only-key", pipeline_id="test-only-pipeline",
        ffmpeg="no-such-program-on-this-machine",
    )
    with pytest.raises(SpeechUnavailable, match="ffmpeg is not installed"):
        asyncio.run(service.transcribe(b"OggS", "audio/ogg", "hi"))


def test_an_unreachable_bhashini_is_speech_unavailable(monkeypatch):
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    service = BhashiniSpeechToText(
        user_id="test-only-user", api_key="test-only-key", pipeline_id="test-only-pipeline",
        transport=httpx.MockTransport(down),
    )
    monkeypatch.setattr(service, "_to_wav", lambda audio: b"RIFF" + b"0" * 100)
    with pytest.raises(SpeechUnavailable, match="Could not reach Bhashini"):
        asyncio.run(service.transcribe(b"OggS", "audio/ogg", "hi"))


# ---------- the rehearsal reset ----------


def test_a_reset_puts_everyone_back_to_english(client, seeded):
    from seed.reset import reset

    choose_language(client, 4)
    assert language_for(seeded, ASHA) == "hi"
    seeded.commit()
    reset(seeded)
    seeded.commit()
    seeded.expire_all()
    assert language_for(seeded, ASHA) == "en"

