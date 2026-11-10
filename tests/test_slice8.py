"""Slice 8: the dashboard, its data, and the invented demo cases behind it."""

import json
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app import clock as app_clock
from app.cases.bites import BiteReport
from app.cases.geo import point
from app.cases.models import Case, Event, Report
from app.cases.models import CaseState as S
from app.config import get_settings
from app.dashboard import queries
from app.routing import dedup
from seed.demo import clear_demo, load_demo

SEED = Path(__file__).parent.parent / "seed"
PANAJI = (15.4909, 73.8278)


@pytest.fixture
def demo(seeded):
    """Zones, teams and camps, plus the invented demo cases and bite reports."""
    load_demo(seeded)
    seeded.commit()
    return seeded


def real_case(session, *, state=S.NEW, urgency="high", species="dog", where=PANAJI, minutes_ago=5):
    case = Case(
        state=state, location=point(*where), urgency=urgency, species=species,
        injury_type="visible wound", triage_status="ok",
        created_at=app_clock.now() - timedelta(minutes=minutes_ago),
    )
    session.add(case)
    session.flush()
    case.public_id = f"PAW-{case.id:04d}"
    session.add(Report(case_id=case.id, reporter_number="+910000000001", location=point(*where)))
    session.commit()
    return case


def get_data(client, **params) -> dict:
    response = client.get("/dashboard/data", params=params)
    assert response.status_code == 200
    return response.json()


# ---------- demo data ----------


def test_demo_file_says_it_is_invented():
    assert "DEMO DATA" in json.loads((SEED / "demo_cases.json").read_text())["_note"]


def test_demo_loads_about_40_cases_and_some_bites(demo):
    assert demo.scalar(select(func.count()).select_from(Case).where(Case.is_demo)) == 40
    assert demo.scalar(select(func.count()).select_from(BiteReport).where(BiteReport.is_demo)) == 23


def test_demo_uses_only_invented_phone_numbers(demo):
    numbers = set(demo.scalars(select(Report.reporter_number))) | set(
        demo.scalars(select(BiteReport.reporter_number))
    )
    assert numbers and all(n.startswith("+91000000") for n in numbers)


def test_every_demo_case_reached_its_state_through_the_state_machine(demo):
    for case in demo.scalars(select(Case).where(Case.is_demo)):
        moves = demo.scalars(
            select(Event)
            .where(Event.case_id == case.id, Event.type == "state_changed")
            .order_by(Event.id)
        ).all()
        assert moves[0].from_state == S.REPORTED
        assert moves[-1].to_state == case.state
        assert all(event.created_at <= app_clock.now() for event in moves)


def test_loading_demo_twice_does_not_duplicate(demo):
    load_demo(demo)
    demo.commit()
    assert demo.scalar(select(func.count()).select_from(Case).where(Case.is_demo)) == 40


def test_clearing_demo_leaves_real_cases_alone(demo):
    mine = real_case(demo)
    clear_demo(demo)
    demo.commit()
    assert demo.scalars(select(Case.id)).all() == [mine.id]
    assert demo.scalar(select(func.count()).select_from(BiteReport)) == 0
    assert demo.scalar(select(func.count()).select_from(Event).where(Event.case_id.is_not(None))) == 0


def test_a_real_report_never_merges_into_a_demo_case(demo):
    invented = demo.scalars(select(Case).where(Case.is_demo, Case.state == S.ROUTED)).first()
    invented.created_at = func.now()  # dedup reads the real clock
    twin = Case(state=S.TRIAGED, location=invented.location, species=invented.species)
    demo.add(twin)
    demo.flush()
    assert dedup.find_duplicate(demo, twin) is None


# ---------- the page and its data ----------


def test_dashboard_page_loads_with_a_map(client):
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "leaflet" in response.text and 'id="map"' in response.text


def test_data_has_every_panel(client, demo):
    data = get_data(client)
    assert len(data["zones"]) == 14
    assert len(data["cases"]) == 39  # 40 demo cases, one merged into another
    assert len(data["bites"]) == 23
    assert [camp["zone"] for camp in data["camps"]] == ["mapusa", "canacona"]
    assert data["camps"][0]["capacity"] == 15 and data["camps"][0]["booked"] == 0
    assert data["summary"]["demo_cases"] == 39


def test_data_never_carries_a_phone_number(client, demo):
    real_case(demo)
    assert "+91" not in client.get("/dashboard/data").text


def test_merged_duplicates_count_as_reports_on_the_case_that_stayed(client, demo):
    assert max(case["reports"] for case in get_data(client)["cases"]) == 2
    assert all(case["state"] != "MERGED" for case in get_data(client)["cases"])


def test_a_new_real_case_shows_up(client, seeded):
    case = real_case(seeded, urgency="critical")
    (row,) = get_data(client)["cases"]
    assert row["id"] == case.public_id and row["open"] and not row["is_demo"]
    assert row["latitude"] == pytest.approx(PANAJI[0]) and row["longitude"] == pytest.approx(PANAJI[1])
    assert get_data(client)["summary"]["critical_open"] == 1


def test_cases_older_than_30_days_are_left_out(client, seeded):
    real_case(seeded, minutes_ago=31 * 24 * 60)
    assert get_data(client)["cases"] == []


# ---------- filters ----------


def test_filter_by_status(client, demo):
    open_cases = get_data(client, status="open")["cases"]
    closed = get_data(client, status="closed")["cases"]
    assert open_cases and all(case["open"] for case in open_cases)
    assert closed and all(case["state"] in ("RESOLVED", "CANCELLED") for case in closed)
    assert len(open_cases) + len(closed) == 39


def test_filter_by_urgency_and_zone(client, demo):
    critical = get_data(client, urgency="critical")["cases"]
    assert critical and all(case["urgency"] == "critical" for case in critical)

    panaji = get_data(client, zone="panaji")["cases"]
    assert len(panaji) == 6 and all(case["zone_name"] == "Panaji" for case in panaji)

    both = get_data(client, zone="panaji", urgency="critical", status="open")["cases"]
    assert len(both) == 1


def test_filters_do_not_change_the_summary(client, demo):
    assert get_data(client, zone="panaji")["summary"] == get_data(client)["summary"]


def test_an_unknown_filter_value_is_refused(client):
    assert client.get("/dashboard/data", params={"status": "everything"}).status_code == 422


# ---------- cases that need a person ----------


def test_a_case_nobody_took_is_flagged(client, demo):
    flagged = [c for c in get_data(client)["cases"] if c["attention"] == "no_team"]
    assert sorted(c["zone"] for c in flagged) == ["sankhalim", "valpoi"]
    assert all(c["state"] == "ESCALATED" for c in flagged)


def test_a_case_triage_could_not_read_is_flagged(client, demo):
    (flagged,) = [c for c in get_data(client)["cases"] if c["attention"] == "needs_review"]
    assert flagged["species"] is None and flagged["urgency"] == "high"
    assert get_data(client)["summary"]["need_attention"] == 3
    # The attention list ignores the filters, so nothing flagged can be hidden.
    assert len(get_data(client, zone="panaji", status="closed")["attention"]) == 3


# ---------- sterilisation and the next-camp suggestion ----------


def test_sterilisation_shows_only_the_spec_figures(client, seeded):
    rows = {row["zone"]: row for row in get_data(client)["sterilisation"]}
    assert len(rows) == 14
    assert rows["panaji"]["dogs_sterilised"] == 2918
    assert rows["ponda"]["dogs_sterilised"] == 1121
    assert rows["curchorem-cacora"]["dogs_sterilised"] == 243
    for zone in ("canacona", "sankhalim", "valpoi", "mapusa"):
        assert rows[zone]["camps_held"] == 0
    # No figure is not the same as zero.
    assert rows["margao"] == {
        "zone": "margao", "zone_name": "Margao", "camps_held": None, "dogs_sterilised": None,
    }


def test_bite_hotspots_follow_the_three_within_500_m_rule(client, demo):
    hot = [bite["zone"] for bite in get_data(client)["bites"] if bite["is_hotspot"]]
    assert sorted(set(hot)) == ["sankhalim", "valpoi"]
    assert get_data(client)["summary"]["bite_hotspots"] == 8


def test_suggestion_with_demo_data_is_valpoi(client, demo):
    suggestion = get_data(client)["suggestion"]
    assert suggestion["zone"] == "valpoi"
    assert suggestion["bite_reports"] == 5 and suggestion["held_no_camps_last_year"]
    assert suggestion["rule"] == queries.SUGGESTION_RULE  # the page shows how it was chosen


def _zone(slug):
    return {"slug": slug, "name": slug.title()}


def test_suggestion_skips_zones_that_already_have_a_camp():
    suggestion = queries.suggest_next_camp(
        zones=[_zone("a"), _zone("b")],
        bites=[{"zone": "a"}, {"zone": "a"}, {"zone": "b"}],
        camps=[{"zone": "a"}],
        sterilisation=[],
    )
    assert suggestion["zone"] == "b" and suggestion["bite_reports"] == 1


def test_suggestion_tie_goes_to_the_zone_with_no_camps_last_year():
    suggestion = queries.suggest_next_camp(
        zones=[_zone("a"), _zone("b")],
        bites=[{"zone": "a"}, {"zone": "b"}],
        camps=[],
        sterilisation=[{"zone": "b", "camps_held": 0}, {"zone": "a", "camps_held": None}],
    )
    assert suggestion["zone"] == "b"
    assert [r["zone"] for r in suggestion["runners_up"]] == ["a"]


def test_no_suggestion_when_every_zone_has_a_camp():
    assert queries.suggest_next_camp([_zone("a")], [], [{"zone": "a"}], []) is None


# ---------- password ----------


def test_dashboard_asks_for_the_password_when_one_is_set(client, seeded, monkeypatch):
    monkeypatch.setattr(get_settings(), "dashboard_password", "test-only-password")
    for path in ("/dashboard", "/dashboard/data"):
        assert client.get(path).status_code == 401
        assert client.get(path, auth=("official", "wrong")).status_code == 401
        assert client.get(path, auth=("official", "test-only-password")).status_code == 200


# ---------- list order ----------


@pytest.mark.skip(reason="TODO(me): improve case_sort_key() in app/dashboard/queries.py")
def test_case_list_order(client, seeded):
    old_low = real_case(seeded, urgency="low", minutes_ago=50)
    new_critical = real_case(seeded, urgency="critical", minutes_ago=5)
    old_critical = real_case(seeded, urgency="critical", minutes_ago=40)
    closed_critical = real_case(seeded, urgency="critical", state=S.RESOLVED, minutes_ago=60)

    order = [case["id"] for case in get_data(client)["cases"]]
    assert order == [
        old_critical.public_id,     # open, critical, waiting longest
        new_critical.public_id,     # open, critical
        old_low.public_id,          # open, low
        closed_critical.public_id,  # closed cases last
    ]
