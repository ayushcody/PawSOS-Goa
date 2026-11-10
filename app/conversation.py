"""The single entry point for every inbound message, whatever the channel.

A photo and a location open a case. The photo is triaged, the case is merged
into an existing one or placed in a zone, and a rescue team is alerted. Team
button taps come in here too.
"""

from sqlalchemy.orm import Session

from app import messages
from app.booking import flow as booking
from app.booking.calendar import CalendarClient
from app.cases import bites, intake
from app.cases.geo import in_goa
from app.cases.models import Case
from app.channels.base import ChannelAdapter, InboundMessage, deliver
from app.routing import dispatch
from app.routing.flow import route_case
from app.triage.flow import triage_case
from app.triage.service import Triager

GREETINGS = {"hi", "hello", "hey", "namaste", "start"}


async def handle_inbound(
    message: InboundMessage,
    channel: ChannelAdapter,
    session: Session,
    triager: Triager | None = None,
    calendar: CalendarClient | None = None,
) -> None:
    number = message.from_number

    async def reply(key: str, **values: object) -> None:
        await channel.send_text(number, messages.render(key, **values))

    if message.kind == "button" and message.button_id:
        # A rescue team tapped Accept, Decline, On site or Resolved.
        outbox = dispatch.handle_button(session, number, message.button_id)
        session.commit()
        await deliver(channel, outbox)
        return

    result: intake.IntakeResult | None = None

    if message.kind == "image" and message.media_name:
        result = intake.add_photo(
            session, number, message.media_name, message.media_mime or "image/jpeg"
        )
    elif (
        message.kind == "location"
        and message.latitude is not None
        and message.longitude is not None
    ):
        if not in_goa(message.latitude, message.longitude):
            await reply("outside_goa")
            return
        bite = bites.pending_for(session, number)
        if bite is not None:
            # They told us they were bitten, so this location is theirs, not an animal's.
            outcome = bites.add_location(session, bite, message.latitude, message.longitude)
            session.commit()
            if outcome.centre is None:
                await reply("bite_no_centre")
            else:
                centre = outcome.centre
                await reply(
                    "bite_nearest_centre",
                    name=centre.name,
                    km=centre.distance_km,
                    map_link=f"https://maps.google.com/?q={centre.latitude:.5f},{centre.longitude:.5f}",
                )
            return
        result = intake.add_location(session, number, message.latitude, message.longitude)

    if result is None:
        text = (message.text or "").strip()
        outbox = booking.handle_text(session, number, text, calendar) if text else None
        if message.kind == "text" and outbox is not None:
            session.commit()
            await deliver(channel, outbox)
        elif message.kind == "text" and text and bites.is_bite_report(text):
            # A person is hurt: answer at once, before anything else.
            bites.start(session, number)
            session.commit()
            await reply("bite_first_aid")
        elif message.kind == "text" and text:
            await reply("welcome" if text.lower() in GREETINGS else "how_to_report")
        else:
            await reply("unsupported")
        return

    if result.status == "need_location":
        await reply("ask_location")
    elif result.status == "need_photo":
        await reply("ask_photo")
    else:
        # Save the case and tell the citizen straight away. Triage takes a few
        # seconds and must never be able to undo the case.
        session.commit()
        await reply("case_created", case_id=result.case_id)
        await _triage_and_tell(session, result.case, triager, channel, number)


async def _triage_and_tell(
    session: Session, case: Case, triager: Triager | None, channel: ChannelAdapter, number: str
) -> None:
    triage = await triage_case(session, case, triager)
    session.commit()
    if triage is None:
        text = messages.render("triage_needs_review", case_id=case.public_id)
    else:
        text = messages.triage_message(
            case_id=case.public_id,
            urgency=triage.urgency,
            first_aid=triage.first_aid,
            aggressive=triage.aggression_risk == "high",
        )
    await channel.send_text(number, text)
    await _route_and_tell(session, case, channel, number)


async def _route_and_tell(
    session: Session, case: Case, channel: ChannelAdapter, number: str
) -> None:
    outcome = route_case(session, case)
    session.commit()

    async def tell(to: str, key: str, **values: object) -> None:
        await channel.send_text(to, messages.render(key, **values))

    primary = outcome.merged_into
    if primary is None:
        if outcome.zone is not None:
            await tell(number, "zone_assigned", case_id=case.public_id, zone=outcome.zone.short_name)
        outbox = dispatch.start_dispatch(session, case)
        session.commit()
        await deliver(channel, outbox)
        return

    if number in outcome.earlier_reporters:
        await tell(number, "merged_same_reporter", case_id=primary.public_id)
    else:
        await tell(number, "merged_new_reporter", case_id=primary.public_id)
    for other in outcome.earlier_reporters:
        if other != number:
            await tell(
                other, "merged_earlier_reporter", case_id=primary.public_id, count=outcome.report_count
            )
