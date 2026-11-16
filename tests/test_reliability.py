"""A rescue is never lost to a message that could not be sent, or to a restart (audit C1),
and the dashboard works with no internet (audit C2).

See docs/AUDIT.md. Before these fixes a failed reply to the reporter stopped the
case before any team was alerted, and the dashboard showed only "Loading…" when
the map library could not be fetched.
"""

import asyncio
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select, text

from app import messages
from app.cases import intake
from app.cases.models import Case, Event
from app.conversation import _triage_and_tell
from app.jobs.scheduler import run_recovery
from app.routing.models import Dispatch
from tests.whatsapp_fakes import PANAJI as WA_PANAJI
from tests.whatsapp_fakes import envelope, msg, post

CITIZEN = "+910000000001"
OTHER = "+910000000002"
PANAJI = (15.4909, 73.8278)
PANAJI_TEAM = "+910000000101"


def png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (32, 32), (180, 120, 60)).save(out, format="PNG")
    return out.getvalue()


def send_photo(client, number=CITIZEN):
    return client.post(
        "/sim/inbound/photo", data={"from_number": number}, files={"file": ("a.png", png(), "image/png")}
    )


def send_location(client, number=CITIZEN, place=PANAJI):
    return client.post(
        "/sim/inbound",
        json={"from_number": number, "kind": "location", "latitude": place[0], "longitude": place[1]},
    )


def texts_to(client, number) -> list[str]:
    return [m["text"] for m in client.get("/sim/messages", params={"phone": number}).json() if m["direction"] == "out"]


def cases(db) -> list[Case]:
    db.expire_all()
    return db.scalars(select(Case).order_by(Case.id)).all()


def alerts(db) -> list[Dispatch]:
    return db.scalars(select(Dispatch).where(Dispatch.status == "sent")).all()


def refuse_sends_to(app, number, when=lambda text: True):
    """Make every message to `number` that matches `when` fail, as a closed WhatsApp window would."""
    sim = app.state.simulator
    real = sim.send_text

    async def flaky(to, words):
        if to == number and when(words):
            raise RuntimeError("the channel refused this message")
        await real(to, words)

    sim.send_text = flaky
    sim.send_location_request = flaky


def age_cases(db, minutes: int) -> None:
    """Pretend every case was last changed `minutes` ago (database time, as the recovery job reads it)."""
    db.execute(text("UPDATE cases SET updated_at = now() - make_interval(mins => :m)"), {"m": minutes})
    db.commit()


def run_recovery_job(app) -> None:
    asyncio.run(run_recovery(app.state.channel))


# ---------- C1: a failed send never stops a case ----------


@pytest.mark.parametrize(
    "fails",
    [
        pytest.param(lambda words: True, id="every message to the reporter"),
        pytest.param(lambda words: "Case ID" in words, id="case created"),
        pytest.param(lambda words: "team member will look" in words, id="triage reply"),
        pytest.param(lambda words: "area" in words, id="zone assigned"),
    ],
)
def test_a_reporter_message_that_fails_does_not_stop_the_team_alert(app, seeded, fails):
    refuse_sends_to(app, CITIZEN, fails)
    client = TestClient(app)
    assert send_photo(client).status_code == 200
    assert send_location(client).status_code == 200

    [case] = cases(seeded)
    assert case.state == "ROUTED"
    assert [a.team_id for a in alerts(seeded)]  # a team has been alerted
    assert any("New case PAW-0001" in t for t in texts_to(client, PANAJI_TEAM))


def test_a_photo_is_kept_even_if_the_ask_for_location_cannot_be_sent(app, seeded):
    refuse_sends_to(app, CITIZEN, lambda words: "photo received" in words)
    client = TestClient(app)
    send_photo(client)
    send_location(client)
    assert cases(seeded)[0].state == "ROUTED"


def test_the_team_is_alerted_before_the_reporter_hears_anything_about_routing(client, seeded):
    send_photo(client)
    send_location(client)
    alert = client.get("/sim/messages", params={"phone": PANAJI_TEAM}).json()[-1]
    zone_line = next(
        m for m in client.get("/sim/messages", params={"phone": CITIZEN}).json() if "Panaji area" in m["text"]
    )
    assert alert["id"] < zone_line["id"]


def test_real_whatsapp_refusing_every_reply_still_alerts_a_team(wa, meta, seeded):
    """Today's situation (D-092): Meta receives messages but refuses every reply."""
    meta.refuse_sends = True
    post(wa, envelope(msg("image", image={"id": "photo-1", "mime_type": "image/jpeg", "sha256": "x"})))
    post(wa, envelope(msg("location", location=WA_PANAJI)))

    [case] = cases(seeded)
    assert case.state == "ROUTED"
    assert alerts(seeded)
    # The team is a placeholder, so its alert reached the simulator.
    assert any("New case PAW-0001" in t for t in texts_to(wa, PANAJI_TEAM))


# ---------- C1: a case left behind by a restart is moved on ----------


def stuck_case(db, number=CITIZEN, place=PANAJI) -> Case:
    """A case saved just before the server stopped: photo and location in, nothing else done."""
    intake.add_photo(db, number, "0" * 32 + ".png", "image/png")
    result = intake.add_location(db, number, *place)
    db.commit()
    return result.case


def test_a_case_stuck_before_triage_is_routed_by_the_recovery_job(app, seeded):
    client = TestClient(app)
    stuck_case(seeded)
    age_cases(seeded, 3)

    run_recovery_job(app)

    [case] = cases(seeded)
    assert case.state == "ROUTED"
    assert case.triage_status == "needs_review" and case.urgency == "high"
    assert any("New case PAW-0001" in t for t in texts_to(client, PANAJI_TEAM))
    assert texts_to(client, CITIZEN) == [messages.render("case_created", case_id="PAW-0001")]
    assert seeded.scalar(select(Event).where(Event.type == "case_recovered")) is not None


@pytest.mark.parametrize("state", ["TRIAGED", "NEW"])
def test_a_case_stuck_after_triage_is_routed_too(app, seeded, state):
    case = stuck_case(seeded)
    if state == "NEW":
        from app.routing.flow import route_case
        from app.triage.flow import mark_for_review

        mark_for_review(seeded, case, "test")
        route_case(seeded, case)
    else:
        from app.triage.flow import mark_for_review

        mark_for_review(seeded, case, "test")
    seeded.commit()
    assert cases(seeded)[0].state == state
    age_cases(seeded, 3)

    run_recovery_job(app)
    assert cases(seeded)[0].state == "ROUTED"
    assert len(alerts(seeded)) == 1


def test_a_case_still_being_triaged_is_left_alone(app, seeded):
    stuck_case(seeded)  # just now: triage may still be running
    run_recovery_job(app)
    assert cases(seeded)[0].state == "REPORTED"
    assert alerts(seeded) == []


def test_a_stuck_case_next_to_an_open_one_is_merged_not_alerted_twice(app, seeded):
    client = TestClient(app)
    send_photo(client, OTHER)
    send_location(client, OTHER)  # an open, routed case
    stuck_case(seeded)
    age_cases(seeded, 3)

    run_recovery_job(app)

    first, second = cases(seeded)
    assert second.state == "MERGED" and second.merged_into_id == first.id
    assert len(alerts(seeded)) == 1
    assert texts_to(client, CITIZEN)[-1] == messages.render("merged_new_reporter", case_id=first.public_id)


def test_triage_finishing_after_the_recovery_job_stops_quietly(app, seeded):
    """The job took the case over; the late triage must not route it a second time."""
    case = stuck_case(seeded)
    age_cases(seeded, 3)
    run_recovery_job(app)

    seeded.expire_all()
    asyncio.run(_triage_and_tell(seeded, case, None, app.state.channel, CITIZEN))
    assert cases(seeded)[0].state == "ROUTED"
    assert len(alerts(seeded)) == 1


def test_demo_cases_are_never_touched(app, seeded):
    stuck_case(seeded)
    seeded.execute(text("UPDATE cases SET is_demo = true"))
    seeded.commit()
    age_cases(seeded, 3)
    run_recovery_job(app)
    assert cases(seeded)[0].state == "REPORTED"


def test_the_dashboard_flags_a_case_no_team_has_been_alerted_about(client, seeded):
    stuck_case(seeded)
    assert client.get("/dashboard/data").json()["attention"] == []  # just reported: not yet a worry

    age_cases(seeded, 3)
    [row] = client.get("/dashboard/data").json()["attention"]
    assert row["id"] == "PAW-0001" and row["attention"] == "not_routed"


# ---------- C2: the dashboard needs no internet ----------


def test_the_dashboard_serves_its_own_copy_of_leaflet(client):
    page = client.get("/dashboard").text
    assert "unpkg.com" not in page
    assert '<script src="/static/leaflet/leaflet.js"' in page
    js = client.get("/static/leaflet/leaflet.js")
    css = client.get("/static/leaflet/leaflet.css")
    assert js.status_code == 200 and b"Leaflet" in js.content[:200]
    assert css.status_code == 200
    assert client.get("/static/leaflet/images/layers.png").status_code == 200


def test_the_dashboard_still_draws_its_lists_if_the_map_cannot_load(client):
    # Checked by hand in a browser with leaflet.js removed; here, that every use of the map is guarded.
    page = client.get("/dashboard").text
    assert 'const HAS_MAP = typeof window.L !== "undefined";' in page
    assert "\nconst map = L.map(" not in page  # a bare top-level call would stop the whole script
