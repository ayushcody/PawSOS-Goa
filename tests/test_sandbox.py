"""The public demo: private sandboxes, limits on real triage, cleanup, and the public dashboard.

The real Claude API is never called: a fake triager stands in.
"""

import io
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select, update

from app.cases.models import Case, CaseState, Report
from app.config import get_settings
from app.sandbox import core
from app.triage import limits
from app.triage.schema import TriageResult
from app.triage.service import get_triager

PANAJI = (15.4909, 73.8278)
MAPUSA = (15.5937, 73.8142)
REAL_CITIZEN = "+910000000001"

GOOD = {
    "animal_visible": True,
    "species": "dog",
    "injury_type": "visible wound on hind leg",
    "urgency": "high",
    "aggression_risk": "low",
    "first_aid": ["Keep a safe distance.", "Keep other people and pets back."],
}


class FakeTriager:
    def __init__(self) -> None:
        self.calls = 0

    async def triage(self, image: bytes) -> TriageResult:
        self.calls += 1
        return TriageResult(**GOOD)


@pytest.fixture(autouse=True)
def _fresh_limits():
    limits.reset()
    yield
    limits.reset()


@pytest.fixture
def setting(monkeypatch):
    """Change a setting for one test."""

    def change(name: str, value: str) -> None:
        monkeypatch.setenv(name, value)
        get_settings.cache_clear()

    yield change
    get_settings.cache_clear()


def png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (32, 32), (180, 120, 60)).save(out, format="PNG")
    return out.getvalue()


def visitor(app) -> TestClient:
    client = TestClient(app)
    assert client.get("/sandbox/session").status_code == 200
    return client


def report(client, who="c1", place=PANAJI) -> None:
    r = client.post("/sandbox/inbound/photo", data={"who": who}, files={"file": ("a.png", png(), "image/png")})
    assert r.status_code == 200
    r = client.post(
        "/sandbox/inbound", json={"who": who, "kind": "location", "latitude": place[0], "longitude": place[1]}
    )
    assert r.status_code == 200


def texts(client, who) -> list[str]:
    return [m["text"] for m in client.get("/sandbox/messages", params={"who": who}).json()]


def team_who(client) -> str:
    teams = client.get("/sandbox/session").json()["teams"]
    assert teams, "no team was alerted"
    return teams[0]["who"]


def all_cases(db) -> list[Case]:
    db.expire_all()
    return db.scalars(select(Case).order_by(Case.id)).all()


# ---------- numbers and cookies ----------


def test_sandbox_numbers_can_never_be_real_indian_mobiles():
    sid = core.new_id()
    for persona in core.CITIZENS:
        number = core.number_for(sid, persona)
        assert number.startswith("+910")  # Indian mobiles start 6 to 9
        assert len(number) == 13
        assert core.key_of(number) == core.key_for(sid)
    assert core.key_of("+910000000001") is None
    assert core.key_of("+919876543210") is None


def test_a_tampered_cookie_is_refused():
    signed = core.sign("123456")
    assert core.verify(signed) == "123456"
    assert core.verify("654321" + signed[6:]) is None
    assert core.verify("123456.0000") is None
    assert core.verify(None) is None


def test_messages_need_a_sandbox(app, seeded):
    assert TestClient(app).get("/sandbox/messages", params={"who": "c1"}).status_code == 401


# ---------- isolation ----------


def test_two_visitors_at_the_same_spot_get_separate_cases(app, seeded):
    alice, bob = visitor(app), visitor(app)
    report(alice)
    report(bob)
    cases = all_cases(seeded)
    assert len(cases) == 2
    assert all(c.state != CaseState.MERGED for c in cases)
    assert texts(alice, "c1") != texts(bob, "c1")


def test_within_one_sandbox_a_second_citizen_is_merged(app, seeded):
    alice = visitor(app)
    report(alice, "c1")
    report(alice, "c2")
    states = [c.state for c in all_cases(seeded)]
    assert CaseState.MERGED in states
    assert any("already been reported" in t for t in texts(alice, "c2"))


def test_a_real_report_never_merges_into_a_sandbox_case(app, seeded):
    alice = visitor(app)
    report(alice)
    staff = TestClient(app)
    staff.post("/sim/inbound/photo", data={"from_number": REAL_CITIZEN}, files={"file": ("a.png", png(), "image/png")})
    staff.post(
        "/sim/inbound",
        json={"from_number": REAL_CITIZEN, "kind": "location", "latitude": PANAJI[0], "longitude": PANAJI[1]},
    )
    cases = all_cases(seeded)
    assert len(cases) == 2
    assert all(c.state != CaseState.MERGED for c in cases)


def test_a_team_chat_shows_only_the_visitors_own_cases(app, seeded):
    alice, bob = visitor(app), visitor(app)
    report(alice)
    report(bob, place=MAPUSA)
    alice_cases = alice.get("/sandbox/session").json()["cases"]
    bob_cases = bob.get("/sandbox/session").json()["cases"]
    assert alice_cases and bob_cases and not set(alice_cases) & set(bob_cases)

    team = team_who(alice)
    seen = " ".join(texts(alice, team))
    assert alice_cases[0] in seen
    assert bob_cases[0] not in seen
    # Bob was never in touch with Alice's team, so he sees nothing there.
    assert all(alice_cases[0] not in t for t in texts(bob, team))


def test_a_visitor_cannot_press_buttons_on_someone_elses_case(app, seeded):
    alice, bob = visitor(app), visitor(app)
    report(alice)
    case_id = alice.get("/sandbox/session").json()["cases"][0]
    team = team_who(alice)

    refused = bob.post("/sandbox/inbound", json={"who": team, "kind": "button", "button_id": f"accept:{case_id}"})
    assert refused.status_code == 403
    assert all_cases(seeded)[0].state != CaseState.ACCEPTED

    ok = alice.post("/sandbox/inbound", json={"who": team, "kind": "button", "button_id": f"accept:{case_id}"})
    assert ok.status_code == 200
    assert all_cases(seeded)[0].state == CaseState.ACCEPTED
    assert any("has accepted case" in t for t in texts(alice, "c1"))


def test_teams_only_answer_with_buttons(app, seeded):
    alice = visitor(app)
    report(alice)
    team = team_who(alice)
    r = alice.post("/sandbox/inbound", json={"who": team, "kind": "text", "text": "hello"})
    assert r.status_code == 400


# ---------- limits ----------


def test_real_triage_is_capped_per_visitor(app, seeded, setting):
    setting("SANDBOX_TRIAGE_PER_HOUR", "1")
    fake = FakeTriager()
    app.dependency_overrides[get_triager] = lambda: fake
    alice = visitor(app)

    report(alice, place=PANAJI)
    report(alice, place=MAPUSA)  # far enough not to merge

    assert fake.calls == 1
    first, second = all_cases(seeded)
    assert first.triage_status == "ok"
    assert second.triage_status != "ok"  # went on without triage
    assert second.state not in (CaseState.REPORTED, CaseState.TRIAGED)  # and was still routed


def test_the_daily_cap_covers_every_visitor(app, seeded, setting):
    setting("TRIAGE_DAILY_CAP", "1")
    fake = FakeTriager()
    app.dependency_overrides[get_triager] = lambda: fake
    report(visitor(app), place=PANAJI)
    report(visitor(app), place=MAPUSA)
    assert fake.calls == 1


def test_too_many_requests_are_refused(app, seeded, setting):
    setting("SANDBOX_REQUESTS_PER_MINUTE", "3")
    client = visitor(app)
    send = lambda: client.post("/sandbox/inbound", json={"who": "c1", "kind": "text", "text": "hi"}).status_code
    codes = [send() for _ in range(5)]
    assert codes[:3] == [200, 200, 200]
    assert codes[3:] == [429, 429]
    # Polling has a larger allowance, so the page keeps updating.
    assert client.get("/sandbox/session").status_code == 200


def test_a_refused_check_does_not_spend_another_budget():
    rules = limits.SlidingWindow()
    assert rules.allow_all([("day", 5, 60), ("hour", 1, 60)])
    assert not rules.allow_all([("day", 5, 60), ("hour", 1, 60)])
    # The day budget was only spent once.
    assert rules.allow_all([("day", 2, 60)])
    assert not rules.allow_all([("day", 2, 60)])


# ---------- cleanup ----------


def test_cleanup_deletes_old_sandbox_cases_only(app, seeded):
    alice = visitor(app)
    report(alice)
    report(alice, "c2")  # merged into the first
    staff = TestClient(app)
    staff.post("/sim/inbound/photo", data={"from_number": REAL_CITIZEN}, files={"file": ("a.png", png(), "image/png")})
    staff.post(
        "/sim/inbound",
        json={"from_number": REAL_CITIZEN, "kind": "location", "latitude": MAPUSA[0], "longitude": MAPUSA[1]},
    )
    assert len(all_cases(seeded)) == 3

    # Nothing is old enough yet.
    assert core.cleanup(seeded) == 0
    seeded.commit()

    seeded.execute(update(Case).values(created_at=datetime.now(UTC) - timedelta(hours=25)))
    seeded.execute(update(Report).values(created_at=datetime.now(UTC) - timedelta(hours=25)))
    seeded.commit()
    assert core.cleanup(seeded) == 2  # the sandbox case and the one merged into it
    seeded.commit()

    left = all_cases(seeded)
    assert len(left) == 1
    numbers = seeded.scalars(select(Report.reporter_number)).all()
    assert numbers == [REAL_CITIZEN]


# ---------- the public dashboard ----------


def test_public_dashboard_is_read_only_and_hides_photos(app, seeded, setting):
    setting("DASHBOARD_PASSWORD", "staff-secret")
    setting("PUBLIC_DASHBOARD", "true")
    report(visitor(app))
    public = TestClient(app)

    assert public.get("/dashboard").status_code == 200
    data = public.get("/dashboard/data").json()
    assert data["public_view"] is True
    assert all(c["photo_url"] is None for c in data["cases"])

    case_id = data["cases"][0]["id"]
    detail = public.get(f"/dashboard/cases/{case_id}").json()
    assert detail["photos"] == [] and detail["photos_hidden"] is True

    assert public.get("/dashboard/photos/1").status_code == 401
    cancel = public.post(f"/dashboard/cases/{case_id}/cancel", json={"reason": "test"})
    assert cancel.status_code == 401

    staff = TestClient(app)
    assert staff.get(f"/dashboard/cases/{case_id}", auth=("staff", "staff-secret")).json()["photos"]


def test_without_public_dashboard_the_password_is_still_needed(app, seeded, setting):
    setting("DASHBOARD_PASSWORD", "staff-secret")
    assert TestClient(app).get("/dashboard/data").status_code == 401
