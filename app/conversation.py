"""The single entry point for every inbound message, whatever the channel.

Slice 2: a photo and a location open a case. Later slices add triage and
routing, but the signature stays the same.
"""

from sqlalchemy.orm import Session

from app import messages
from app.cases import intake
from app.cases.geo import in_goa
from app.channels.base import ChannelAdapter, InboundMessage

GREETINGS = {"hi", "hello", "hey", "namaste", "start"}


async def handle_inbound(
    message: InboundMessage, channel: ChannelAdapter, session: Session
) -> None:
    number = message.from_number

    async def reply(key: str, **values: object) -> None:
        await channel.send_text(number, messages.render(key, **values))

    if message.kind == "image" and message.media_name:
        result = intake.add_photo(
            session, number, message.media_name, message.media_mime or "image/jpeg"
        )
        await _reply_for(result, reply)
        return

    if message.kind == "location" and message.latitude is not None and message.longitude is not None:
        if not in_goa(message.latitude, message.longitude):
            await reply("outside_goa")
            return
        result = intake.add_location(session, number, message.latitude, message.longitude)
        await _reply_for(result, reply)
        return

    text = (message.text or "").strip()
    if message.kind == "text" and text:
        await reply("welcome" if text.lower() in GREETINGS else "how_to_report")
        return

    await reply("unsupported")


async def _reply_for(result: intake.IntakeResult, reply) -> None:
    if result.status == "case_created":
        await reply("case_created", case_id=result.case_id)
    elif result.status == "need_location":
        await reply("ask_location")
    else:
        await reply("ask_photo")
