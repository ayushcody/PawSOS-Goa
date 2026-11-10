"""The single entry point for every inbound message, whatever the channel.

Slice 1: an echo bot. Later slices grow this into case creation, triage and
routing, but the signature stays the same.
"""

from app import messages
from app.channels.base import ChannelAdapter, InboundMessage

GREETINGS = {"hi", "hello", "hey", "namaste", "start"}


async def handle_inbound(message: InboundMessage, channel: ChannelAdapter) -> None:
    if message.kind != "text" or not (message.text or "").strip():
        await channel.send_text(message.from_number, messages.render("unsupported"))
        return

    text = message.text.strip()
    if text.lower() in GREETINGS:
        await channel.send_text(message.from_number, messages.render("welcome"))
        return

    await channel.send_text(message.from_number, messages.render("echo", text=text))
