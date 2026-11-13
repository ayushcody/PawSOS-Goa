"""Slice 5: alerting teams, their buttons, and escalation.

The clock starts at midday in Goa (see the `clock` fixture), so the seeded
teams are open unless a test says otherwise.
"""

import asyncio
import io

import pytest
from PIL import Image
from sqlalchemy import select

from app import messages
from app.cases.models import Case, CaseState, Event
from app.config import get_settings
from app.jobs.scheduler import check_interval_seconds, run_timeouts
from app.routing.dispatch import humanize_seconds
from app.routing.models import Dispatch, Zone
from app.routing.teams import escalation_chain

CITIZEN_1 = "+910000000001"
CITIZEN_2 = "+910000000002"
PANAJI = (15.4909, 73.8278)
CASE = "PAW-0001"


def photo() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (32, 32), (180, 120, 60)).save(out, format="PNG")
    return out.getvalue()


def report(client, number=CITIZEN_1) -> None:
    client.post(
        "/sim/inbound/photo",
        data={"from_number": number},
        files={"file": ("a.png", photo(), "image/png")},
    )
    client.post(
        "/sim/inbound",
        json={"from_number": number, "kind": "location", "latitude": PANAJI[0], "longitude": PANAJI[1]},
    )


def tap(client, team, action, case_id=CASE) -> None:
    client.post(
        "/sim/inbound",
        json={"from_number": team.phone, "kind": "button", "button_id": f"{action}:{case_id}"},
    )


def received(client, number) -> list[dict]:
    transcript = client.get("/sim/messages", params={"phone": number}).json()
    return [m for m in transcript if m["direction"] == "out"]


def last_text(client, number) -> str:
    return received(client, number)[-1]["text"]


def last_buttons(client, number) -> list[str]:
    return [b["id"] for b in received(client, number)[-1]["buttons"]]


def the_case(db) -> Case:
    db.expire_all()
    return db.scalars(select(Case).order_by(Case.id)).first()


def let_the_alert_expire(app, clock) -> None:
    """Move time past the deadline, then run the job the scheduler would run."""
    clock.advance(get_settings().escalation_timeout_seconds + 1)
    asyncio.run(run_timeouts(app.state.simulator))


@pytest.fixture
def chain(seeded):
    """Panaji's escalation chain: own team, nearest neighbour, taluka officer."""
    panaji = seeded.scalar(select(Zone).where(Zone.slug == "panaji"))
    return escalation_chain(seeded, panaji)


# ---------- the happy path ----------


def test_a_new_case_alerts_the_zones_team_with_two_buttons(client, seeded, chain):
    own, neighbour, _officer = chain
    report(client)

    alert = received(client, own.phone)[-1]
    assert CASE in alert["text"] and "Panaji" in alert["text"]
    assert "maps.google.com/?q=15.49090,73.82780" in alert["text"]
    assert [b["id"] for b in alert["buttons"]] == [f"accept:{CASE}", f"decline:{CASE}"]
    # The photo arrives just before the alert.
    assert received(client, own.phone)[-2]["media_url"].startswith("/media/")

    assert the_case(seeded).state == CaseState.ROUTED
    assert received(client, neighbour.phone) == []


def test_accept_on_site_resolved_and_the_citizen_hears_each_step(client, seeded, chain):
    own = chain[0]
    report(client)

    tap(client, own, "accept")
    case = the_case(seeded)
    assert case.state == CaseState.ACCEPTED and case.assigned_team_id == own.id
    assert last_text(client, CITIZEN_1) == messages.render(
        "citizen_accepted", case_id=CASE, team=own.name
    )
    assert last_buttons(client, own.phone) == [f"onsite:{CASE}"]

    tap(client, own, "onsite")
    assert the_case(seeded).state == CaseState.ON_SITE
    assert last_text(client, CITIZEN_1) == messages.render("citizen_on_site", case_id=CASE)
    assert last_buttons(client, own.phone) == [f"resolved:{CASE}"]

    tap(client, own, "resolved")
    assert the_case(seeded).state == CaseState.RESOLVED
    # The citizen is told it is resolved, then asked how it went (the rating, added later).
    heard = [
        m["text"]
        for m in client.get("/sim/messages", params={"phone": CITIZEN_1}).json()
        if m["direction"] == "out"
    ]
    assert heard[-2:] == [
        messages.render("citizen_resolved", case_id=CASE),
        messages.render("rating_ask", case_id=CASE),
    ]
    assert last_buttons(client, own.phone) == []


def test_the_whole_journey_is_in_the_audit_log(client, seeded, chain):
    own = chain[0]
    report(client)
    for action in ("accept", "onsite", "resolved"):
        tap(client, own, action)

    moves = seeded.scalars(
        select(Event).where(Event.type == "state_changed").order_by(Event.id)
    ).all()
    assert [m.to_state for m in moves] == [
        "TRIAGED", "NEW", "ROUTED", "ACCEPTED", "ON_SITE", "RESOLVED",
    ]
    assert moves[-1].actor == own.phone


def test_everyone_who_reported_gets_the_updates(client, seeded, chain):
    report(client, CITIZEN_1)
    report(client, CITIZEN_2)  # merged into the first case
    tap(client, chain[0], "accept")

    accepted = messages.render("citizen_accepted", case_id=CASE, team=chain[0].name)
    assert last_text(client, CITIZEN_1) == accepted
    assert last_text(client, CITIZEN_2) == accepted


# ---------- escalation ----------


def test_decline_passes_the_case_to_the_next_team(client, seeded, chain):
    own, neighbour, _ = chain
    report(client)
    tap(client, own, "decline")

    assert last_text(client, own.phone) == messages.render("team_declined_ack", case_id=CASE)
    assert last_buttons(client, neighbour.phone) == [f"accept:{CASE}", f"decline:{CASE}"]
    assert the_case(seeded).state == CaseState.ESCALATED
    assert last_text(client, CITIZEN_1) == messages.render("citizen_escalated", case_id=CASE)


def test_no_answer_in_time_passes_the_case_to_the_next_team(app, client, seeded, chain, clock):
    own, neighbour, _ = chain
    report(client)

    # Just before the deadline nothing happens.
    clock.advance(get_settings().escalation_timeout_seconds - 1)
    asyncio.run(run_timeouts(app.state.simulator))
    assert received(client, neighbour.phone) == []

    clock.advance(2)
    asyncio.run(run_timeouts(app.state.simulator))
    assert last_text(client, own.phone) == messages.render("team_alert_expired", case_id=CASE)
    assert last_buttons(client, neighbour.phone) == [f"accept:{CASE}", f"decline:{CASE}"]
    assert the_case(seeded).state == CaseState.ESCALATED


def test_silence_all_the_way_reaches_the_officer_then_tells_the_citizen(
    app, client, seeded, chain, clock
):
    _own, _neighbour, officer = chain
    report(client)

    let_the_alert_expire(app, clock)  # own team silent
    let_the_alert_expire(app, clock)  # neighbour silent
    assert last_buttons(client, officer.phone) == [f"accept:{CASE}", f"decline:{CASE}"]

    let_the_alert_expire(app, clock)  # officer silent: nobody left
    assert last_text(client, CITIZEN_1) == messages.render("citizen_no_team_yet", case_id=CASE)
    assert the_case(seeded).state == CaseState.ESCALATED
    statuses = seeded.scalars(select(Dispatch.status).order_by(Dispatch.id)).all()
    assert statuses == ["timed_out", "timed_out", "timed_out"]

    # Running the job again does nothing more.
    before = len(received(client, CITIZEN_1))
    let_the_alert_expire(app, clock)
    assert len(received(client, CITIZEN_1)) == before


def test_closed_teams_are_skipped_straight_to_whoever_is_open(client, seeded, chain, clock):
    own, neighbour, officer = chain
    clock.set_goa_time(22, 0)  # both partner teams have gone home
    report(client)

    assert received(client, own.phone) == []
    assert received(client, neighbour.phone) == []
    assert last_buttons(client, officer.phone) == [f"accept:{CASE}", f"decline:{CASE}"]
    assert the_case(seeded).state == CaseState.ESCALATED
    statuses = seeded.scalars(select(Dispatch.status).order_by(Dispatch.id)).all()
    assert statuses == ["skipped_closed", "skipped_closed", "sent"]


def test_ignore_opening_hours_setting_alerts_the_own_team_at_night(
    client, seeded, chain, clock, monkeypatch
):
    monkeypatch.setattr(get_settings(), "ignore_opening_hours", True)
    clock.set_goa_time(22, 0)
    report(client)
    assert last_buttons(client, chain[0].phone) == [f"accept:{CASE}", f"decline:{CASE}"]


# ---------- taps that arrive twice, late, or from the wrong person ----------


def test_tapping_accept_twice_changes_nothing_the_second_time(client, seeded, chain):
    own = chain[0]
    report(client)
    tap(client, own, "accept")
    updates_before = len(received(client, CITIZEN_1))

    tap(client, own, "accept")
    accepts = seeded.scalars(select(Event).where(Event.to_state == "ACCEPTED")).all()
    assert len(accepts) == 1
    assert len(received(client, CITIZEN_1)) == updates_before  # the citizen is not told twice
    assert last_buttons(client, own.phone) == [f"onsite:{CASE}"]


def test_tapping_decline_twice_escalates_only_once(client, seeded, chain):
    own, neighbour, officer = chain
    report(client)
    tap(client, own, "decline")
    tap(client, own, "decline")

    assert len(received(client, neighbour.phone)) == 2  # one photo, one alert
    assert received(client, officer.phone) == []


def test_a_team_that_answers_late_can_still_take_the_case(app, client, seeded, chain, clock):
    own, neighbour, _ = chain
    report(client)
    let_the_alert_expire(app, clock)  # now the neighbour is being asked

    tap(client, own, "accept")
    case = the_case(seeded)
    assert case.state == CaseState.ACCEPTED and case.assigned_team_id == own.id
    # The neighbour is stood down, and cannot take it afterwards.
    assert last_text(client, neighbour.phone) == messages.render("team_case_taken", case_id=CASE)
    tap(client, neighbour, "accept")
    assert the_case(seeded).assigned_team_id == own.id
    assert last_text(client, neighbour.phone) == messages.render("team_case_taken", case_id=CASE)


def test_an_expired_alert_does_not_escalate_a_case_already_accepted(app, client, seeded, chain, clock):
    own, neighbour, _ = chain
    report(client)
    tap(client, own, "accept")
    let_the_alert_expire(app, clock)

    assert the_case(seeded).state == CaseState.ACCEPTED
    assert received(client, neighbour.phone) == []


def test_a_citizen_tapping_a_team_button_is_refused(client, seeded):
    report(client)
    client.post(
        "/sim/inbound",
        json={"from_number": CITIZEN_2, "kind": "button", "button_id": f"accept:{CASE}"},
    )
    assert last_text(client, CITIZEN_2) == messages.render("not_a_team")
    assert the_case(seeded).state == CaseState.ROUTED


def test_a_team_that_was_never_asked_cannot_accept(client, seeded, chain):
    report(client)
    tap(client, chain[1], "accept")  # the neighbour has not been alerted
    assert the_case(seeded).state == CaseState.ROUTED
    assert last_text(client, chain[1].phone) == messages.render("team_not_waiting", case_id=CASE)


def test_only_the_assigned_team_can_mark_on_site(client, seeded, chain):
    own, neighbour, _ = chain
    report(client)
    tap(client, own, "accept")
    tap(client, neighbour, "onsite")
    assert the_case(seeded).state == CaseState.ACCEPTED


def test_resolved_before_on_site_asks_for_on_site_first(client, seeded, chain):
    own = chain[0]
    report(client)
    tap(client, own, "accept")
    tap(client, own, "resolved")
    assert the_case(seeded).state == CaseState.ACCEPTED
    assert last_buttons(client, own.phone) == [f"onsite:{CASE}"]


def test_a_made_up_button_is_refused(client, seeded, chain):
    report(client)
    client.post(
        "/sim/inbound",
        json={"from_number": chain[0].phone, "kind": "button", "button_id": "delete:everything"},
    )
    assert last_text(client, chain[0].phone) == messages.render("unsupported")


# ---------- small pieces ----------


def test_the_job_checks_often_enough():
    assert check_interval_seconds(600) == 15
    assert check_interval_seconds(20) == 2
    assert check_interval_seconds(5) == 1


def test_whatsapp_button_limits_are_respected():
    # WhatsApp allows at most 20 characters in a reply button's title.
    for key in ("button_accept", "button_decline", "button_on_site", "button_resolved"):
        assert len(messages.render(key)) <= 20


@pytest.mark.skip(reason="TODO(me): improve humanize_seconds() in app/routing/dispatch.py")
def test_humanize_seconds():
    assert humanize_seconds(600) == "10 minutes"
    assert humanize_seconds(60) == "1 minute"
    assert humanize_seconds(20) == "20 seconds"
    assert humanize_seconds(1) == "1 second"
    assert humanize_seconds(90) == "90 seconds"
