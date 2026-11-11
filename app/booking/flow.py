"""The BOOK conversation.

    BOOK            -> we list the upcoming camps, numbered
    "1"             -> we list that camp's free slots, numbered
    "2"             -> booked: saved, put on the camp's calendar, confirmed
    CANCEL          -> leaves the conversation at any point

A row in booking_drafts remembers where each person is, and which ids the
numbers we showed them stand for.

The same row also holds the CANCEL list (app/citizen.py): its options are
strings such as "case:12" or "booking:5" instead of ids. One row per person
means a number they type has exactly one meaning at a time.

Cancelling a booking (cancel_booking) marks it "cancelled", which frees the
place: places_left, reminders and the dashboard count only "booked".
"""

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import clock, messages
from app.booking.calendar import CalendarClient, calendar_id_for
from app.booking.models import Booking, BookingDraft, Camp, CampSlot
from app.cases.audit import log_event
from app.channels import templates
from app.channels.base import Outbound
from app.config import get_settings
from app.contacts import language_for

log = logging.getLogger(__name__)

GOA_TIME = ZoneInfo("Asia/Kolkata")
DRAFT_WINDOW = timedelta(minutes=15)
START_WORDS = {"book", "booking"}
CANCEL_WORDS = {"cancel", "stop", "exit"}


# ---------- wording helpers ----------


def format_date(moment: datetime) -> str:
    """ "Sat 28 Nov" """
    local = moment.astimezone(GOA_TIME)
    return f"{local:%a} {local.day} {local:%b}"


def format_time_range(start: datetime, end: datetime) -> str:
    """The slot's times as a person would read them.

    TODO(me): Ayush improves this. It currently gives "09:00 to 10:00".
    Make it give "9:00 am to 10:00 am", and "12:00 pm to 1:00 pm" for a
    midday slot (12-hour clock, no leading zero, lower-case am/pm).
    Then remove the @pytest.mark.skip on test_format_time_range in
    tests/test_slice7.py and run:
        .venv/bin/pytest -q tests/test_slice7.py -k time_range

    Hints: start.astimezone(GOA_TIME) is already done for you below.
    strftime("%I:%M %p") gives "09:00 AM"; you still need to drop the
    leading zero and lower-case it. Write a small helper for one time and
    call it twice.
    """
    start, end = start.astimezone(GOA_TIME), end.astimezone(GOA_TIME)
    return f"{start:%H:%M} to {end:%H:%M}"


def _msg(to: str, key: str, session: Session | None = None, **values: object) -> Outbound:
    """A message to a pet owner, in their own language when `session` is given."""
    language = language_for(session, to) if session is not None else None
    return Outbound(
        to=to,
        text=messages.render(key, language, **values),
        template=templates.fallback_for(key, values),  # None for most keys
    )


def _numbered(lines: list[str]) -> str:
    return "\n".join(f"{n}. {line}" for n, line in enumerate(lines, start=1))


# ---------- queries ----------


def upcoming_camps(session: Session) -> list[Camp]:
    """Camps that still have a slot in the future, soonest first."""
    first_slot = func.min(CampSlot.starts_at)
    return list(
        session.scalars(
            select(Camp)
            .join(CampSlot, CampSlot.camp_id == Camp.id)
            .where(CampSlot.starts_at > clock.now())
            .group_by(Camp.id)
            .order_by(first_slot)
        )
    )


def places_left(session: Session, slot: CampSlot) -> int:
    taken = session.scalar(
        select(func.count())
        .select_from(Booking)
        .where(Booking.slot_id == slot.id, Booking.status == "booked")
    )
    return slot.capacity - taken


def free_slots(session: Session, camp: Camp) -> list[tuple[CampSlot, int]]:
    slots = session.scalars(
        select(CampSlot)
        .where(CampSlot.camp_id == camp.id, CampSlot.starts_at > clock.now())
        .order_by(CampSlot.starts_at)
    )
    with_places = [(slot, places_left(session, slot)) for slot in slots]
    return [(slot, left) for slot, left in with_places if left > 0]


def active_draft(session: Session, number: str) -> BookingDraft | None:
    draft = session.get(BookingDraft, number)
    if draft is not None and draft.updated_at < clock.now() - DRAFT_WINDOW:
        session.delete(draft)
        session.flush()
        return None
    return draft


# ---------- the conversation ----------


def handle_text(
    session: Session, number: str, text: str, calendar: CalendarClient | None
) -> list[Outbound] | None:
    """Reply if this text belongs to the BOOK conversation, otherwise return None."""
    word = text.strip().lower()

    if word in START_WORDS:
        return _show_camps(session, number)

    draft = active_draft(session, number)
    if draft is None or is_cancel_list(draft):
        return None  # the CANCEL list is answered in app/citizen.py
    if word in CANCEL_WORDS:
        session.delete(draft)
        return [_msg(number, "book_cancelled", session)]
    if not word.isdigit():
        return None  # something else entirely; let the other flows look at it

    choice = int(word)
    if not 1 <= choice <= len(draft.options):
        return [_msg(number, "book_invalid_choice", session)]
    chosen_id = draft.options[choice - 1]

    if draft.camp_id is None:
        return _show_slots(session, number, draft, session.get(Camp, chosen_id))
    return _book(session, number, draft, chosen_id, calendar)


def is_cancel_list(draft: BookingDraft) -> bool:
    """True when this row holds the CANCEL list rather than a BOOK conversation."""
    return bool(draft.options) and isinstance(draft.options[0], str)


def _show_camps(session: Session, number: str) -> list[Outbound]:
    camps = upcoming_camps(session)
    if not camps:
        return [_msg(number, "book_no_camps", session)]

    draft = session.get(BookingDraft, number) or BookingDraft(owner_number=number)
    draft.camp_id = None
    draft.options = [camp.id for camp in camps]
    draft.updated_at = clock.now()
    session.add(draft)

    lines = [
        messages.render(
            "book_camp_line",
            place=camp.short_name,
            services=camp.services,
            date=format_date(camp.slots[0].starts_at),
            venue=camp.venue,
        )
        for camp in camps
    ]
    return [_msg(number, "book_choose_camp", session, options=_numbered(lines))]


def _existing_booking(session: Session, number: str, camp: Camp) -> Booking | None:
    return session.scalar(
        select(Booking).where(
            Booking.owner_number == number, Booking.camp_id == camp.id, Booking.status == "booked"
        )
    )


def _show_slots(session: Session, number: str, draft: BookingDraft, camp: Camp) -> list[Outbound]:
    existing = _existing_booking(session, number, camp)
    if existing is not None:
        session.delete(draft)
        return [
            _msg(
                number,
                "book_already",
                session,
                ref=existing.reference,
                camp=camp.name,
                date=format_date(existing.slot.starts_at),
                time=format_time_range(existing.slot.starts_at, existing.slot.ends_at),
            )
        ]

    slots = free_slots(session, camp)
    if not slots:
        session.delete(draft)
        return [_msg(number, "book_camp_full", session, camp=camp.name)]

    draft.camp_id = camp.id
    draft.options = [slot.id for slot, _ in slots]
    draft.updated_at = clock.now()
    lines = [
        messages.render(
            "book_slot_line",
            language_for(session, number),
            time=format_time_range(slot.starts_at, slot.ends_at),
            left=left,
        )
        for slot, left in slots
    ]
    return [
        _msg(
            number,
            "book_choose_slot",
            session,
            camp=camp.name,
            date=format_date(slots[0][0].starts_at),
            options=_numbered(lines),
        )
    ]


def _book(
    session: Session,
    number: str,
    draft: BookingDraft,
    slot_id: int,
    calendar: CalendarClient | None,
) -> list[Outbound]:
    # Lock the slot row so two people cannot both take the last place.
    slot = session.scalar(select(CampSlot).where(CampSlot.id == slot_id).with_for_update())
    camp = session.get(Camp, slot.camp_id)
    if places_left(session, slot) <= 0:
        return [_msg(number, "book_slot_full", session), *_show_slots(session, number, draft, camp)]

    booking = Booking(slot_id=slot.id, camp_id=camp.id, owner_number=number, status="booked")
    session.add(booking)
    session.flush()
    session.delete(draft)

    synced = _sync_to_calendar(booking, slot, camp, calendar)
    log_event(
        session,
        "booking_created",
        actor=number,
        data={"booking": booking.reference, "camp": camp.slug, "calendar_synced": synced},
    )
    return [
        _msg(
            number,
            "book_confirmed",
            session,
            ref=booking.reference,
            camp=camp.name,
            date=format_date(slot.starts_at),
            time=format_time_range(slot.starts_at, slot.ends_at),
            venue=camp.venue,
        )
    ]


def _sync_to_calendar(
    booking: Booking, slot: CampSlot, camp: Camp, calendar: CalendarClient | None
) -> bool:
    """Put the booking on the camp's calendar. A failure here never loses the booking."""
    calendar_id = calendar_id_for(camp.slug)
    if calendar is None or calendar_id is None:
        return False
    try:
        booking.calendar_event_id = calendar.create_event(
            calendar_id=calendar_id,
            summary=f"PawSOS booking {booking.reference}",
            # Only the last four digits: the calendar may be shared with camp volunteers.
            description=(
                f"{camp.name}\nPet owner: number ending {booking.owner_number[-4:]}\n"
                f"Reference: {booking.reference}"
            ),
            start=slot.starts_at,
            end=slot.ends_at,
        )
        return True
    except Exception:
        log.exception("Calendar sync failed for %s", booking.reference)
        return False


# ---------- a person's own bookings, and cancelling one ----------


def upcoming_bookings(session: Session, number: str) -> list[tuple[Booking, CampSlot, Camp]]:
    """This person's bookings whose slot is still ahead, soonest first."""
    rows = session.execute(
        select(Booking, CampSlot, Camp)
        .join(CampSlot, Booking.slot_id == CampSlot.id)
        .join(Camp, Booking.camp_id == Camp.id)
        .where(
            Booking.owner_number == number,
            Booking.status == "booked",
            CampSlot.starts_at > clock.now(),
        )
        .order_by(CampSlot.starts_at)
    ).all()
    return [(booking, slot, camp) for booking, slot, camp in rows]


def booking_values(booking: Booking, slot: CampSlot, camp: Camp) -> dict[str, str]:
    """What a message needs to name one booking."""
    return {
        "ref": booking.reference,
        "camp": camp.name,
        "date": format_date(slot.starts_at),
        "time": format_time_range(slot.starts_at, slot.ends_at),
    }


def cancel_booking(
    session: Session, number: str, booking_id: int, calendar: CalendarClient | None
) -> list[Outbound]:
    """Cancel one of this person's future bookings, freeing its place."""
    # Locked, so a reminder or a second CANCEL waits its turn.
    booking = session.scalar(
        select(Booking)
        .where(Booking.id == booking_id, Booking.owner_number == number)
        .with_for_update()
    )
    if booking is None:
        return [_msg(number, "cancel_not_found", session, ref=f"BK-{booking_id:04d}")]
    slot = session.get(CampSlot, booking.slot_id)
    if booking.status != "booked" or slot.starts_at <= clock.now():
        return [_msg(number, "booking_cancel_closed", session, ref=booking.reference)]

    camp = session.get(Camp, booking.camp_id)
    booking.status = "cancelled"
    removed = _remove_from_calendar(booking, camp, calendar)
    log_event(
        session,
        "booking_cancelled",
        actor=number,
        data={"booking": booking.reference, "camp": camp.slug, "calendar_removed": removed},
    )
    return [_msg(number, "booking_cancelled", session, **booking_values(booking, slot, camp))]


def _remove_from_calendar(booking: Booking, camp: Camp, calendar: CalendarClient | None) -> bool:
    """Take the booking off the camp's calendar. A failure here never undoes the cancel."""
    calendar_id = calendar_id_for(camp.slug)
    if calendar is None or calendar_id is None or not booking.calendar_event_id:
        return False
    try:
        calendar.delete_event(calendar_id=calendar_id, event_id=booking.calendar_event_id)
        return True
    except Exception:
        log.exception("Calendar removal failed for %s", booking.reference)
        return False


# ---------- reminders ----------


def due_reminders(session: Session) -> list[Outbound]:
    """Remind everyone whose slot starts within the reminder window (24 hours), once each."""
    now = clock.now()
    window = timedelta(hours=get_settings().reminder_window_hours)
    rows = session.execute(
        select(Booking, CampSlot, Camp)
        .join(CampSlot, Booking.slot_id == CampSlot.id)
        .join(Camp, Booking.camp_id == Camp.id)
        .where(
            Booking.status == "booked",
            Booking.reminder_sent_at.is_(None),
            CampSlot.starts_at > now,
            CampSlot.starts_at <= now + window,
        )
        .order_by(Booking.id)
        .with_for_update(of=Booking, skip_locked=True)
    ).all()

    outbox = []
    for booking, slot, camp in rows:
        booking.reminder_sent_at = now
        outbox.append(
            _msg(
                booking.owner_number,
                "book_reminder",
                session,
                ref=booking.reference,
                camp=camp.name,
                date=format_date(slot.starts_at),
                time=format_time_range(slot.starts_at, slot.ends_at),
                venue=camp.venue,
            )
        )
    return outbox
