"""The single entry point for every inbound message, whatever the channel.

A photo and a location open a case. The photo is triaged, the case is merged
into an existing one or placed in a zone, and a rescue team is alerted. Team
button taps come in here too.

Words are tried in this order: the BOOK conversation (it owns a number typed
mid-booking, and CANCEL there only leaves it), then STATUS and CANCEL
(app/citizen.py), then bite words, then everything else.
"""

from sqlalchemy.orm import Session

from app import citizen, contacts, messages
from app.booking import flow as booking
from app.booking.calendar import CalendarClient
from app.cases import bites, intake
from app.cases.geo import in_goa
from app.cases.models import Case
from app.channels.base import ChannelAdapter, InboundMessage, deliver
from app.routing import dedup, dispatch
from app.routing.flow import RoutingOutcome, route_case
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
        await channel.send_text(
            number, messages.render(key, contacts.language_for(session, number), **values)
        )

    if message.kind == "button" and message.button_id:
        # A rescue team tapped Accept, Decline, On site or Resolved.
        outbox = dispatch.handle_button(session, number, message.button_id)
        session.commit()
        await deliver(channel, outbox)
        return

    if message.kind == "voice":
        if contacts.adopt_detected(session, number, message.language):
            session.commit()  # spoken in Konkani, Marathi or Hindi: answer in it from now on
        heard = (message.text or "").strip()
        if not heard:
            await reply("voice_not_understood")
            return
        # Say back what we understood, so the person can correct us.
        await reply("voice_heard", text=heard)

    # Typed words and a voice note's words are treated alike from here on.
    is_words = message.kind in ("text", "voice")
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
        # Speech services add full stops: a spoken "Book." must still mean BOOK.
        command = text.strip(" .!?") if message.kind == "voice" else text
        language_key = contacts.handle_text(session, number, command) if is_words else None
        if language_key is not None:
            # LANGUAGE, or the number they picked from its menu.
            session.commit()
            await reply(language_key)
            return
        outbox = booking.handle_text(session, number, command, calendar) if command else None
        if is_words and command and outbox is None:
            # STATUS, CANCEL, or a number answering the CANCEL list.
            outbox = citizen.handle_text(session, number, command, calendar)
        if is_words and outbox is not None:
            contacts.close_menu(session, number)  # from here on a number is for BOOK
            session.commit()
            await deliver(channel, outbox)
        elif is_words and text and bites.is_bite_report(text):
            # A person is hurt: answer at once, before anything else.
            bites.start(session, number)
            session.commit()
            await reply("bite_first_aid")
        elif message.kind == "voice" and text.lower().strip(" .!") not in GREETINGS:
            # A spoken description of the animal: keep it with the report.
            result = intake.add_note(session, number, text, message.language)
        elif (
            message.kind == "text"
            and text.lower().strip(" .!") not in GREETINGS
            and intake.has_open_draft(session, number)
        ):
            # Typed words between the photo and the location describe the animal.
            result = intake.add_note(session, number, text, None, spoken=False)
        elif is_words and text:
            await reply("welcome" if text.lower().strip(" .!") in GREETINGS else "how_to_report")
        else:
            await reply("unsupported")
        if result is None:
            return

    if result.status == "need_both":
        await reply("voice_noted")
    elif result.status == "need_location":
        await reply("ask_location")
    elif result.status == "need_photo":
        await reply("ask_photo")
    else:
        # Save the case and tell the citizen straight away. Triage takes a few
        # seconds and must never be able to undo the case.
        session.commit()
        if dedup.might_be_duplicate(session, result.case):
            # Someone may have reported this animal already. Thank them without a
            # case ID, so they never see one that vanishes in a merge a moment later;
            # the ID they should use comes once routing has decided (D-020).
            await reply("case_checking_duplicate")
            await _triage_and_tell(session, result.case, triager, channel, number, id_sent=False)
        else:
            await reply("case_created", case_id=result.case_id)
            await _triage_and_tell(session, result.case, triager, channel, number)


async def _triage_and_tell(
    session: Session,
    case: Case,
    triager: Triager | None,
    channel: ChannelAdapter,
    number: str,
    *,
    id_sent: bool = True,
) -> None:
    """Triage, route, and tell the reporter. id_sent=False: they have no case ID yet.

    Then the triage reply waits until routing has decided, so the only case ID
    the person ever sees is the one that stays open: the earlier case after a
    merge (its message explains why), or this case, announced with "case_created".
    """
    language = contacts.language_for(session, number)
    triage = await triage_case(session, case, triager, language)
    session.commit()

    def triage_text(case_id: str) -> str:
        if triage is None:
            return messages.render("triage_needs_review", language, case_id=case_id)
        return messages.triage_message(
            case_id=case_id,
            urgency=triage.urgency,
            first_aid=triage.first_aid,
            aggressive=triage.aggression_risk == "high",
            language=language,
        )

    if id_sent:
        await channel.send_text(number, triage_text(case.public_id))
    outcome = route_case(session, case)
    session.commit()
    if not id_sent:
        if outcome.merged_into is None:
            await channel.send_text(
                number, messages.render("case_created", language, case_id=case.public_id)
            )
        # After a merge the first-aid steps still come from this person's own photo.
        await channel.send_text(number, triage_text((outcome.merged_into or case).public_id))
    await _tell_routing_outcome(session, case, outcome, channel, number)


async def _tell_routing_outcome(
    session: Session,
    case: Case,
    outcome: RoutingOutcome,
    channel: ChannelAdapter,
    number: str,
) -> None:
    async def tell(to: str, key: str, **values: object) -> None:
        await channel.send_text(
            to, messages.render(key, contacts.language_for(session, to), **values)
        )

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
