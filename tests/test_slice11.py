"""Slice 11: demo polish. The reset command, the reminder demo setting, and wording."""

import asyncio
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app import clock as app_clock
from app import messages
from app.booking.models import Booking, Camp
from app.cases.bites import BiteReport
from app.cases.geo import point
from app.cases.models import Case, Event, Report
from app.cases.models import CaseState as S
from app.config import get_settings
from app.jobs.scheduler import run_reminders
from app.routing.models import Team, Zone
from seed.reset import activity_counts, reset

DOCS = Path(__file__).parent.parent / "docs"
GOA = ZoneInfo("Asia/Kolkata")
OWNER = "+910000000003"


def say(client, words, number=OWNER) -> None:
    client.post("/sim/inbound", json={"from_number": number, "kind": "text", "text": words})


def replies(client, number=OWNER) -> list[str]:
    transcript = client.get("/sim/messages", params={"phone": number}).json()
    return [m["text"] for m in transcript if m["direction"] == "out"]


# ---------- reset ----------


def test_reset_clears_activity_keeps_reference_data_and_reloads_demo(seeded):
    case = Case(state=S.NEW, location=point(15.49, 73.82), created_at=app_clock.now())
    seeded.add(case)
    seeded.flush()
    seeded.add(Report(case_id=case.id, reporter_number="+910000000001"))
    seeded.add(BiteReport(reporter_number="+910000000002"))
    seeded.commit()
    assert activity_counts(seeded)["cases"] == 1

    loaded = reset(seeded)
    seeded.commit()

    assert loaded == {"cases": 40, "bites": 23}
    assert seeded.scalar(select(func.count()).select_from(Case).where(Case.is_demo.is_(False))) == 0
    assert seeded.scalar(select(func.min(Case.public_id))) == "PAW-0001"  # numbering starts again
    assert seeded.scalar(select(func.count()).select_from(Zone)) == 14
    assert seeded.scalar(select(func.count()).select_from(Team)) == 25
    assert seeded.scalar(select(func.count()).select_from(Camp)) == 2
    assert seeded.scalar(select(func.count()).select_from(Event).where(Event.case_id.is_(None))) == 0


# ---------- reminder demo setting ----------


def test_a_wide_reminder_window_reminds_soon_after_booking(app, client, seeded, clock, monkeypatch):
    clock.set(datetime(2026, 11, 20, 12, 0, tzinfo=GOA))  # eight days before the Mapusa camp
    for word in ("BOOK", "1", "2"):
        say(client, word)
    assert seeded.scalars(select(Booking)).one().reminder_sent_at is None

    asyncio.run(run_reminders(app.state.simulator))
    assert not any(text.startswith("Reminder:") for text in replies(client))  # 24 hours: too early

    monkeypatch.setattr(get_settings(), "reminder_window_hours", 720)
    asyncio.run(run_reminders(app.state.simulator))
    asyncio.run(run_reminders(app.state.simulator))
    assert sum(text.startswith("Reminder:") for text in replies(client)) == 1  # once only


# ---------- wording ----------


def test_the_bite_reply_names_the_centre_without_our_internal_tag(client, seeded):
    say(client, "a dog bit me")
    client.post(
        "/sim/inbound",
        json={"from_number": OWNER, "kind": "location", "latitude": 15.4909, "longitude": 73.8278},
    )
    reply = replies(client)[-1]
    assert "Goa Medical College and Hospital, Bambolim," in reply
    assert "[VERIFY]" not in reply
    assert "has not been verified" in reply  # the caveat stays, in plain words


def test_the_merge_message_tells_the_person_which_case_id_to_use():
    text = messages.render("merged_new_reporter", case_id="PAW-0041")
    assert "PAW-0041" in text and "use that case ID" in text


# ---------- the documents judges will read ----------

# Every statistic the spec allows. Anything else that looks like a statistic is a mistake.
ALLOWED_FIGURES = {"19,368", "2,918", "1,121", "243", "1,126", "58.2"}


def test_demo_and_architecture_docs_use_only_the_spec_statistics():
    for name in ("DEMO.md", "ARCHITECTURE.md"):
        text = (DOCS / name).read_text(encoding="utf-8")
        # Numbers written with a thousands comma, or lakh figures.
        figures = set(re.findall(r"\b\d{1,3},\d{3}\b", text)) | set(re.findall(r"\b(\d+(?:\.\d+)?) lakh", text))
        assert figures <= ALLOWED_FIGURES, f"{name} has a figure that is not in the spec: {figures - ALLOWED_FIGURES}"


def test_demo_script_has_a_fallback_and_stays_honest():
    text = (DOCS / "DEMO.md").read_text(encoding="utf-8").lower()
    assert "if something fails" in text
    assert "not a diagnosis" in text
    assert "demo data" in text


def test_reminder_window_default_is_a_day():
    assert get_settings().reminder_window_hours == 24
    assert get_settings().reminder_check_seconds == 300
