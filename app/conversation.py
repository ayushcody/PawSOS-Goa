"""The single entry point for every inbound message, whatever the channel.

Slice 3: a photo and a location open a case, and the photo is triaged.
Later slices add routing, but the signature stays the same.
"""

from sqlalchemy.orm import Session

from app import messages
from app.cases import intake
from app.cases.geo import in_goa
from app.cases.models import Case
from app.channels.base import ChannelAdapter, InboundMessage
from app.triage.flow import triage_case
from app.triage.service import Triager

GREETINGS = {"hi", "hello", "hey", "namaste", "start"}


async def handle_inbound(
    message: InboundMessage,
    channel: ChannelAdapter,
    session: Session,
    triager: Triager | None = None,
) -> None:
    number = message.from_number

    async def reply(key: str, **values: object) -> None:
        await channel.send_text(number, messages.render(key, **values))

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
        result = intake.add_location(session, number, message.latitude, message.longitude)

    if result is None:
        text = (message.text or "").strip()
        if message.kind == "text" and text:
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
