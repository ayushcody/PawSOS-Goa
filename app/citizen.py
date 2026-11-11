"""STATUS and CANCEL: a citizen asks about, or withdraws, their own reports and bookings.

    STATUS              -> their open cases and upcoming camp bookings
    CANCEL              -> the same, numbered; they reply with a number
    "2"                 -> that one is cancelled
    CANCEL PAW-0042     -> cancels that case straight away
    CANCEL BK-0005      -> cancels that booking straight away

The numbered list lives in the person's booking_drafts row (see
app/booking/flow.py), so a number they type means one thing at a time: a camp,
a slot, or something to cancel. Every choice is checked again when it is made.

Only a person who reported a case may cancel it, and only when nobody else
reported the same animal: a merged case stays open for the other reporters.
Cancelling goes through the state machine, stops pending alerts, and tells
any team that was alerted or had accepted.
"""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clock, messages
from app.booking import flow as booking
from app.booking.calendar import CalendarClient
from app.booking.models import BookingDraft
from app.cases import state_machine
from app.cases.audit import log_event
from app.cases.intake import format_case_id
from app.cases.models import Case, Report
from app.cases.models import CaseState as S
from app.channels.base import Outbound
from app.routing import dispatch
from app.routing.flow import reporters_of
from app.routing.models import Team, Zone

STATUS_WORDS = {"status", "my status", "my cases", "my reports", "my bookings"}
CANCEL_WORD = "cancel"
CLOSED = (S.MERGED, S.RESOLVED, S.CANCELLED)

# "cancel paw-0042", "cancel PAW 42", "cancel bk-0005". Voice notes may drop the dash.
_CANCEL_REF = re.compile(r"^cancel\s+(paw|bk)\s*-?\s*(\d{1,6})$")
# "cancel 2": a choice from the list, said with the command word.
_CANCEL_CHOICE = re.compile(r"^cancel\s+(\d{1,3})$")

STATE_KEYS = {
    S.REPORTED: "status_state_received",
    S.TRIAGED: "status_state_received",
    S.NEW: "status_state_finding_team",
    S.ROUTED: "status_state_team_alerted",
    S.ESCALATED: "status_state_still_looking",
    S.ACCEPTED: "status_state_accepted",
    S.ON_SITE: "status_state_on_site",
}


def _msg(to: str, key: str, **values: object) -> Outbound:
    return Outbound(to=to, text=messages.render(key, **values))


def _normalise(text: str) -> str:
    """Lower case, single spaces, no trailing punctuation: "Status." means STATUS."""
    return " ".join(text.lower().split()).strip(" .!?,")


# ---------- the entry point ----------


def handle_text(
    session: Session, number: str, text: str, calendar: CalendarClient | None
) -> list[Outbound] | None:
    """Reply if this text is STATUS, CANCEL or a choice from the CANCEL list, otherwise None."""
    word = _normalise(text)

    if word in STATUS_WORDS:
        return status(session, number)
    if word == CANCEL_WORD:
        return _show_cancel_list(session, number)

    ref = _CANCEL_REF.match(word)
    if ref is not None:
        kind, digits = ref.groups()
        _drop_cancel_list(session, number)
        if kind == "paw":
            public_id = format_case_id(int(digits))
            return _cancel_case(session, number, Case.public_id == public_id, public_id)
        return booking.cancel_booking(session, number, int(digits), calendar)

    choice = _CANCEL_CHOICE.match(word)
    digits = choice.group(1) if choice else word
    if not digits.isdigit():
        return None
    draft = booking.active_draft(session, number)
    if draft is None or not booking.is_cancel_list(draft):
        # A bare number with no list open is not ours; "cancel 2" still shows the list.
        return _show_cancel_list(session, number) if choice else None
    return _choose(session, number, draft, int(digits), calendar)


# ---------- STATUS ----------


def open_cases(session: Session, number: str) -> list[Case]:
    """Open cases this number has a report on, oldest first. Merged reports count."""
    reported = select(Report.case_id).where(
        Report.reporter_number == number, Report.case_id.is_not(None)
    )
    return list(
        session.scalars(
            select(Case)
            .where(Case.id.in_(reported), Case.state.not_in(CLOSED))
            .order_by(Case.created_at)
        )
    )


def _when(case: Case) -> str:
    local = case.created_at.astimezone(booking.GOA_TIME)
    return f"{booking.format_date(case.created_at)}, {local:%H:%M}"


def _state_words(session: Session, case: Case) -> str:
    team = session.get(Team, case.assigned_team_id) if case.assigned_team_id else None
    key = STATE_KEYS.get(S(case.state), "status_state_received")
    if team is None and key in ("status_state_accepted", "status_state_on_site"):
        key = "status_state_team_alerted"
    return messages.render(key, team=team.name if team else "")


def _case_line(session: Session, case: Case) -> str:
    zone = session.get(Zone, case.zone_id) if case.zone_id else None
    values = {"case_id": case.public_id, "when": _when(case), "state": _state_words(session, case)}
    if zone is None:
        return messages.render("status_case_line", **values)
    return messages.render("status_case_line_zone", zone=zone.short_name, **values)


def status(session: Session, number: str) -> list[Outbound]:
    cases = open_cases(session, number)
    bookings = booking.upcoming_bookings(session, number)
    if not cases and not bookings:
        return [_msg(number, "status_nothing")]

    parts = []
    if cases:
        lines = [_case_line(session, case) for case in cases]
        parts.append("\n".join([messages.render("status_header_cases"), *lines]))
    if bookings:
        lines = [
            messages.render("status_booking_line", **booking.booking_values(*row)) for row in bookings
        ]
        parts.append("\n".join([messages.render("status_header_bookings"), *lines]))
    parts.append(messages.render("status_footer"))
    return [Outbound(to=number, text="\n\n".join(parts))]


# ---------- CANCEL: the numbered list ----------


def _show_cancel_list(session: Session, number: str) -> list[Outbound]:
    cases = open_cases(session, number)
    bookings = booking.upcoming_bookings(session, number)
    if not cases and not bookings:
        _drop_cancel_list(session, number)
        return [_msg(number, "cancel_nothing")]

    options: list[str] = []
    lines: list[str] = []
    for case in cases:
        options.append(f"case:{case.id}")
        lines.append(
            messages.render(
                "cancel_case_line", case_id=case.public_id, state=_state_words(session, case)
            )
        )
    for row in bookings:
        options.append(f"booking:{row[0].id}")
        lines.append(messages.render("cancel_booking_line", **booking.booking_values(*row)))

    # Replaces any half-finished BOOK conversation: the newest list is the one they answer.
    draft = session.get(BookingDraft, number) or BookingDraft(owner_number=number)
    draft.camp_id = None
    draft.options = options
    draft.updated_at = clock.now()
    session.add(draft)
    numbered = "\n".join(f"{n}. {line}" for n, line in enumerate(lines, start=1))
    return [_msg(number, "cancel_choose", options=numbered)]


def _drop_cancel_list(session: Session, number: str) -> None:
    draft = session.get(BookingDraft, number)
    if draft is not None and booking.is_cancel_list(draft):
        session.delete(draft)


def _choose(
    session: Session,
    number: str,
    draft: BookingDraft,
    choice: int,
    calendar: CalendarClient | None,
) -> list[Outbound]:
    if not 1 <= choice <= len(draft.options):
        return [_msg(number, "cancel_invalid_choice")]
    kind, _, ident = draft.options[choice - 1].partition(":")
    session.delete(draft)
    if kind == "case":
        return _cancel_case(session, number, Case.id == int(ident), None)
    return booking.cancel_booking(session, number, int(ident), calendar)


# ---------- CANCEL: one case ----------


def _locked_case(session: Session, condition) -> Case | None:
    # Locked like a team's button tap, so a cancel and an Accept are handled one after the other.
    return session.scalar(
        select(Case).where(condition).with_for_update().execution_options(populate_existing=True)
    )


def _cancel_case(session: Session, number: str, condition, ref: str | None) -> list[Outbound]:
    case = _locked_case(session, condition)
    if case is not None and case.state == S.MERGED and case.merged_into_id is not None:
        # They used the case ID they saw before the merge: their report now lives here.
        case = _locked_case(session, Case.id == case.merged_into_id)

    reporters = reporters_of(session, case) if case is not None else []
    if case is None or number not in reporters:
        # Same answer whether the case does not exist or is someone else's.
        return [_msg(number, "cancel_not_found", ref=ref or (case.public_id if case else ""))]
    if case.state in CLOSED:
        return [_msg(number, "case_cancel_closed", case_id=case.public_id)]
    if any(other != number for other in reporters):
        log_event(
            session, "cancel_refused_shared", case_id=case.id, actor=number,
            data={"reporters": len(reporters)},
        )
        return [_msg(number, "case_cancel_shared", case_id=case.public_id)]

    team_messages = dispatch.stand_down(session, case)
    state_machine.transition(
        session, case, S.CANCELLED, actor=number, data={"by": "reporter"}
    )
    key = "case_cancelled_team_told" if team_messages else "case_cancelled"
    return [_msg(number, key, case_id=case.public_id), *team_messages]
