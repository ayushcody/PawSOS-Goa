"""Alerting teams, handling their button taps, and escalating.

Each alert to a team is one row in `dispatches`. A team can Accept or
Decline. A decline, a closed team, or no answer before `expires_at` moves the
case to the next team in the chain, and finally to the taluka officer.

Everything here only changes the database and returns the messages to send.
The caller commits first, then delivers them.
"""

import re
import unicodedata
from datetime import timedelta

from geoalchemy2 import Geometry
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session

from app import clock, messages
from app.cases import state_machine
from app.cases.audit import log_event
from app.cases.models import Case, Event, Photo, Report
from app.cases.models import CaseState as S
from app.channels import templates
from app.channels.base import Button, Outbound
from app.config import get_settings
from app.contacts import language_for
from app.routing.flow import reporters_of
from app.routing.models import Dispatch, Team, Zone
from app.routing.teams import escalation_chain, team_is_open

BUTTON_ID = re.compile(r"^(accept|decline|onsite|resolved):(PAW-\d{4,})$")
WAITING_FOR_A_TEAM = (S.ROUTED, S.ESCALATED)


def humanize_seconds(seconds: int) -> str:
    """Say a length of time the way a person would.

    TODO(me): Ayush improves this. A team alert currently ends "Please answer
    within 600 seconds", which nobody says. Make it return:
        600 -> "10 minutes"     60 -> "1 minute"     20 -> "20 seconds"
        1   -> "1 second"       90 -> "90 seconds"  (only whole minutes become minutes)
    Then remove the @pytest.mark.skip on test_humanize_seconds in
    tests/test_slice5.py and run:
        .venv/bin/pytest -q tests/test_slice5.py -k humanize
    """
    return f"{seconds} seconds"


# ---------- small helpers ----------


def _msg(
    to: str,
    key: str,
    buttons: list[Button] | None = None,
    language: str = messages.DEFAULT_LANGUAGE,  # teams are written to in English
    **values: object,
) -> Outbound:
    return Outbound(
        to=to,
        text=messages.render(key, language, **values),
        buttons=buttons or [],
        template=templates.fallback_for(key, values),  # None for most keys
    )


def _tell_reporters(session: Session, case: Case, key: str, **values: object) -> list[Outbound]:
    return [
        _msg(number, key, language=language_for(session, number), case_id=case.public_id, **values)
        for number in reporters_of(session, case)
    ]


def _is_open(team: Team) -> bool:
    return get_settings().ignore_opening_hours or team_is_open(team, clock.now())


# WhatsApp's limit for the body of a message with buttons (MAX_BUTTON_BODY in whatsapp.py).
MAX_ALERT_CHARS = 1024
MAX_NOTES_IN_ALERT = 3  # a merged case can have many reports; the team sees the first few
MAX_NOTE_CHARS = 200


def _shorten(text: str, limit: int) -> str:
    """One line of at most `limit` characters, cut at a word where possible."""
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat
    cut = flat[: limit - 1]
    if " " in cut[limit // 2 :]:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(" ,.;:-") + "…"


_LINK = re.compile(r"(?i)\b(?:https?://|www\.)\S+|\b[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}\b(?:/\S*)?")
_LONG_NUMBER = re.compile(r"\+?\(?\d[\d\s().-]{7,}\d")
_QUOTES = re.compile(r"[\"“”'‘’`]")
_INVISIBLE = re.compile("[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff]")


def _defang(words: str) -> str:
    """Reporter words are untrusted: a team must not mistake them for our own lines.

    Hidden characters and quote marks go first, so they cannot split a link to
    slip past the checks. Then links and phone numbers are replaced (the real
    map link is added by us).
    """
    words = unicodedata.normalize("NFKC", words)
    words = _QUOTES.sub("", _INVISIBLE.sub("", words))
    words = _LINK.sub("[link removed]", words)
    return _LONG_NUMBER.sub("[number removed]", words)


def _reporter_notes(session: Session, case: Case) -> list[tuple[str, bool]]:
    """What reporters said about the animal: (words, came from a voice note), oldest first.

    Merged reports have already moved to this case, so all of them are here.
    The same words from two reports are shown once.
    """
    rows = session.execute(
        select(Report.id, Report.text)
        .where(Report.case_id == case.id, Report.text.is_not(None))
        .order_by(Report.id)
    ).all()
    if not rows:
        return []
    report_id = Event.data["report_id"].as_integer()
    spoken = set(
        session.scalars(
            select(report_id).where(
                Event.type == "voice_note_received", report_id.in_([r.id for r in rows])
            )
        )
    )
    notes: dict[str, tuple[str, bool]] = {}
    for row in rows:
        words = _defang(" ".join(row.text.split()))
        if words:
            notes.setdefault(words.casefold(), (words, row.id in spoken))
    return list(notes.values())


def _reporter_lines(notes: list[tuple[str, bool]], room: int) -> list[str]:
    """The reporters' words as alert lines, using at most `room` characters in all."""
    lines: list[str] = []
    for words, spoken in notes[:MAX_NOTES_IN_ALERT]:
        key = "team_alert_reporter_voice" if spoken else "team_alert_reporter_says"
        overhead = len(messages.render(key, text="")) + 1  # + the newline before it
        fit = min(MAX_NOTE_CHARS, room - overhead)
        if fit < 20:
            break  # not enough room left to say anything useful
        line = messages.render(key, text=_shorten(words, fit))
        lines.append(line)
        room -= len(line) + 1
    return lines


def _alert_message(session: Session, case: Case, team: Team) -> Outbound:
    latitude, longitude = session.execute(
        select(
            func.ST_Y(cast(Case.location, Geometry)),  # latitude
            func.ST_X(cast(Case.location, Geometry)),  # longitude
        ).where(Case.id == case.id)
    ).one()
    zone = session.get(Zone, case.zone_id)
    report_count = session.scalar(
        select(func.count()).select_from(Report).where(Report.case_id == case.id)
    )
    photo = session.scalar(
        select(Photo.path)
        .join(Report, Photo.report_id == Report.id)
        .where(Report.case_id == case.id)
        .order_by(Photo.id)
        .limit(1)
    )
    if case.triage_status == "ok":
        seen = messages.render(
            "team_alert_seen", species=case.species, injury=case.injury_type
        )
    else:
        seen = messages.render("team_alert_not_triaged")
    values: dict[str, object] = {
        "case_id": case.public_id,
        "zone": zone.short_name,
        "urgency": (case.urgency or "unknown").upper(),
        "seen": seen,
        "map_link": f"https://maps.google.com/?q={latitude:.5f},{longitude:.5f}",
        "reports": report_count,
        "window": humanize_seconds(get_settings().escalation_timeout_seconds),
    }
    text = messages.render("team_alert", **values)
    # What the reporters said goes under the photo line, kept inside WhatsApp's limit.
    notes = _reporter_notes(session, case)
    lines = _reporter_lines(notes, MAX_ALERT_CHARS - len(text)) if notes else []
    if lines:
        values["seen"] = "\n".join([seen, *lines])
        text = messages.render("team_alert", **values)
    buttons = [
        Button(f"accept:{case.public_id}", messages.render("button_accept")),
        Button(f"decline:{case.public_id}", messages.render("button_decline")),
    ]
    return Outbound(
        to=team.phone,
        text=text,
        media_name=photo,
        buttons=buttons,
        template=templates.fallback_for("team_alert", values, tuple(b.id for b in buttons)),
    )


def _latest_dispatch(session: Session, case: Case, team: Team) -> Dispatch | None:
    return session.scalar(
        select(Dispatch)
        .where(Dispatch.case_id == case.id, Dispatch.team_id == team.id)
        .order_by(Dispatch.id.desc())
        .limit(1)
    )


# ---------- alerting ----------


def start_dispatch(session: Session, case: Case) -> list[Outbound]:
    """Alert the first available team for a NEW case."""
    if case.zone_id is None:
        return []  # no zones loaded, nobody to alert
    return _alert_next(session, case, after_position=-1, tell_reporters=False)


def _alert_next(
    session: Session, case: Case, *, after_position: int, tell_reporters: bool
) -> list[Outbound]:
    """Alert the next open team after `after_position` in the chain."""
    chain = escalation_chain(session, session.get(Zone, case.zone_id))
    now = clock.now()

    if case.state == S.NEW:
        state_machine.transition(session, case, S.ROUTED, actor="routing")

    for position in range(after_position + 1, len(chain)):
        team = chain[position]
        if not _is_open(team):
            session.add(
                Dispatch(case_id=case.id, team_id=team.id, position=position, status="skipped_closed")
            )
            log_event(
                session, "team_skipped_closed", case_id=case.id, actor="routing",
                data={"team": team.name},
            )
            continue

        timeout = timedelta(seconds=get_settings().escalation_timeout_seconds)
        session.add(
            Dispatch(
                case_id=case.id, team_id=team.id, position=position,
                status="sent", expires_at=now + timeout,
            )
        )
        if position > 0 and case.state == S.ROUTED:
            state_machine.transition(
                session, case, S.ESCALATED, actor="routing", data={"to_team": team.name}
            )
        log_event(
            session, "team_alerted", case_id=case.id, actor="routing",
            data={"team": team.name, "position": position},
        )
        outbox = [_alert_message(session, case, team)]
        if tell_reporters:
            outbox += _tell_reporters(session, case, "citizen_escalated")
        return outbox

    # Nobody left to ask.
    if case.state == S.ROUTED:
        state_machine.transition(
            session, case, S.ESCALATED, actor="routing", data={"reason": "chain_exhausted"}
        )
    log_event(session, "chain_exhausted", case_id=case.id, actor="routing")
    return _tell_reporters(session, case, "citizen_no_team_yet")


def process_timeouts(session: Session) -> list[Outbound]:
    """Move on from every alert that has gone unanswered past its deadline."""
    due = session.scalars(
        select(Dispatch)
        .where(Dispatch.status == "sent", Dispatch.expires_at <= clock.now())
        .order_by(Dispatch.id)
        .with_for_update(skip_locked=True)  # a button tap on the same alert waits its turn
    ).all()

    outbox: list[Outbound] = []
    for dispatch in due:
        case = session.get(Case, dispatch.case_id)
        team = session.get(Team, dispatch.team_id)
        dispatch.status = "timed_out"
        dispatch.responded_at = clock.now()
        log_event(
            session, "alert_timed_out", case_id=case.id, actor="timer", data={"team": team.name}
        )
        if case.state in WAITING_FOR_A_TEAM:
            outbox.append(_msg(team.phone, "team_alert_expired", case_id=case.public_id))
            outbox += _alert_next(
                session, case, after_position=dispatch.position, tell_reporters=True
            )
    return outbox


# ---------- button taps ----------


def handle_button(session: Session, number: str, button_id: str) -> list[Outbound]:
    match = BUTTON_ID.match(button_id)
    if match is None:
        return [_msg(number, "unsupported")]
    action, public_id = match.groups()

    team = session.scalar(select(Team).where(Team.phone == number))
    if team is None:
        return [_msg(number, "not_a_team")]

    # Lock the case row: two taps arriving together are handled one after the other.
    case = session.scalar(select(Case).where(Case.public_id == public_id).with_for_update())
    if case is None:
        return [_msg(number, "team_not_waiting", case_id=public_id)]

    handler = {"accept": _accept, "decline": _decline, "onsite": _on_site, "resolved": _resolved}
    return handler[action](session, case, team)


def _on_site_prompt(case: Case, team: Team) -> Outbound:
    return _msg(
        team.phone, "team_accepted_ack", case_id=case.public_id,
        buttons=[Button(f"onsite:{case.public_id}", messages.render("button_on_site"))],
    )


def _resolved_prompt(case: Case, team: Team) -> Outbound:
    return _msg(
        team.phone, "team_on_site_ack", case_id=case.public_id,
        buttons=[Button(f"resolved:{case.public_id}", messages.render("button_resolved"))],
    )


def _not_yours(case: Case, team: Team) -> list[Outbound]:
    taken = case.assigned_team_id is not None and case.assigned_team_id != team.id
    return [_msg(team.phone, "team_case_taken" if taken else "team_not_waiting", case_id=case.public_id)]


def _accept(session: Session, case: Case, team: Team) -> list[Outbound]:
    # Tapped Accept again: say the same thing again, change nothing.
    if case.assigned_team_id == team.id:
        if case.state == S.ACCEPTED:
            return [_on_site_prompt(case, team)]
        if case.state == S.ON_SITE:
            return [_resolved_prompt(case, team)]

    dispatch = _latest_dispatch(session, case, team)
    # A team whose alert timed out may still say yes, as long as nobody else has.
    if (
        dispatch is None
        or dispatch.status not in ("sent", "timed_out")
        or case.state not in WAITING_FOR_A_TEAM
    ):
        return _not_yours(case, team)

    now = clock.now()
    dispatch.status = "accepted"
    dispatch.responded_at = now
    outbox: list[Outbound] = []

    # Anyone else still being asked is stood down.
    others = session.scalars(
        select(Dispatch).where(
            Dispatch.case_id == case.id, Dispatch.status == "sent", Dispatch.id != dispatch.id
        )
    )
    for other in others:
        other.status = "cancelled"
        other.responded_at = now
        other_team = session.get(Team, other.team_id)
        outbox.append(_msg(other_team.phone, "team_case_taken", case_id=case.public_id))

    case.assigned_team_id = team.id
    state_machine.transition(session, case, S.ACCEPTED, actor=team.phone, data={"team": team.name})
    outbox.append(_on_site_prompt(case, team))
    outbox += _tell_reporters(session, case, "citizen_accepted", team=team.name)
    return outbox


def _decline(session: Session, case: Case, team: Team) -> list[Outbound]:
    dispatch = _latest_dispatch(session, case, team)
    ack = _msg(team.phone, "team_declined_ack", case_id=case.public_id)
    if dispatch is not None and dispatch.status == "declined":
        return [ack]  # tapped Decline again
    if dispatch is None or dispatch.status != "sent" or case.state not in WAITING_FOR_A_TEAM:
        return _not_yours(case, team)

    dispatch.status = "declined"
    dispatch.responded_at = clock.now()
    log_event(session, "team_declined", case_id=case.id, actor=team.phone, data={"team": team.name})
    return [ack] + _alert_next(
        session, case, after_position=dispatch.position, tell_reporters=True
    )


def _on_site(session: Session, case: Case, team: Team) -> list[Outbound]:
    if case.assigned_team_id != team.id:
        return _not_yours(case, team)
    if case.state == S.ON_SITE:
        return [_resolved_prompt(case, team)]  # tapped On site again
    if case.state != S.ACCEPTED:
        return [_msg(team.phone, "team_not_waiting", case_id=case.public_id)]

    state_machine.transition(session, case, S.ON_SITE, actor=team.phone)
    return [_resolved_prompt(case, team)] + _tell_reporters(session, case, "citizen_on_site")


def _resolved(session: Session, case: Case, team: Team) -> list[Outbound]:
    if case.assigned_team_id != team.id:
        return _not_yours(case, team)
    ack = _msg(team.phone, "team_resolved_ack", case_id=case.public_id)
    if case.state == S.RESOLVED:
        return [ack]  # tapped Resolved again
    if case.state == S.ACCEPTED:
        return [_on_site_prompt(case, team)]  # On site comes first
    if case.state != S.ON_SITE:
        return [_msg(team.phone, "team_not_waiting", case_id=case.public_id)]

    state_machine.transition(session, case, S.RESOLVED, actor=team.phone)
    return [ack] + _tell_reporters(session, case, "citizen_resolved")


# ---------- the reporter cancelled ----------


def stand_down(session: Session, case: Case) -> list[Outbound]:
    """Stop every pending alert for a case its reporter has cancelled, and tell the teams.

    Pending alerts become "cancelled", so process_timeouts (which only looks
    at "sent") never escalates them. Teams still waiting to answer, and the
    team that accepted, are told. Call this before moving the case to CANCELLED.
    """
    now = clock.now()
    teams: dict[int, Team] = {}
    pending = session.scalars(
        select(Dispatch)
        .where(Dispatch.case_id == case.id, Dispatch.status == "sent")
        .with_for_update()  # waits for a timer that is moving this alert along
    )
    for dispatch in pending:
        dispatch.status = "cancelled"
        dispatch.responded_at = now
        teams[dispatch.team_id] = session.get(Team, dispatch.team_id)
    if case.assigned_team_id is not None:
        teams[case.assigned_team_id] = session.get(Team, case.assigned_team_id)
    for team in teams.values():
        log_event(
            session, "team_stood_down", case_id=case.id, actor="routing", data={"team": team.name}
        )
    return [_msg(team.phone, "team_case_cancelled_by_reporter", case_id=case.public_id) for team in teams.values()]


# ---------- staff actions (from the dashboard) ----------

STAFF_CAN_ASSIGN = (S.NEW, S.ROUTED, S.ESCALATED)


def assign_team(
    session: Session, case: Case, team: Team, actor: str = "staff", note: str | None = None
) -> list[Outbound]:
    """Staff send a case to a team they chose on the dashboard.

    The team gets the usual alert with Accept and Decline, and anyone else
    still being asked is stood down. The alert is placed after the end of the
    automatic chain, so if this team declines or does not answer in time the
    case comes back to staff flagged "no team", instead of going round the
    chain again. Only a case still waiting for a team can be assigned: raises
    InvalidTransition otherwise, and ValueError if the case has no area.
    """
    if case.state not in STAFF_CAN_ASSIGN:
        raise state_machine.InvalidTransition(case.state, S.ROUTED)
    if case.zone_id is None:
        raise ValueError("This case has no area, so it cannot be sent to a team.")

    now = clock.now()
    outbox: list[Outbound] = []
    waiting = session.scalars(
        select(Dispatch).where(Dispatch.case_id == case.id, Dispatch.status == "sent")
    ).all()
    for other in waiting:
        other.status = "cancelled"
        other.responded_at = now
        if other.team_id != team.id:
            other_team = session.get(Team, other.team_id)
            outbox.append(_msg(other_team.phone, "team_case_reassigned", case_id=case.public_id))

    data = {"team": team.name, "reason": note or "assigned by staff"}
    if case.state != S.ROUTED:
        state_machine.transition(session, case, S.ROUTED, actor=actor, data=data)

    chain = escalation_chain(session, session.get(Zone, case.zone_id))
    timeout = timedelta(seconds=get_settings().escalation_timeout_seconds)
    session.add(
        Dispatch(
            case_id=case.id, team_id=team.id, position=len(chain),
            status="sent", expires_at=now + timeout,
        )
    )
    log_event(session, "team_assigned_by_staff", case_id=case.id, actor=actor, data=data)
    outbox.append(_alert_message(session, case, team))
    outbox += _tell_reporters(session, case, "citizen_staff_assigned", team=team.name)
    return outbox
