"""The shape every channel shares.

A channel (the simulator, WhatsApp) turns whatever it receives into an
InboundMessage, and knows how to send text, buttons and photos back. Nothing
outside app/channels needs to know which channel is in use.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

MessageKind = Literal["text", "image", "location", "button"]


class InboundMessage(BaseModel):
    """One message from a person, in channel-neutral form.

    Built by a channel adapter, never straight from a web request: `media_name`
    must only ever be a name returned by app.channels.media.save_image.
    """

    from_number: str = Field(min_length=3, max_length=20)
    kind: MessageKind = "text"
    text: str | None = None
    media_name: str | None = None
    media_mime: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    button_id: str | None = Field(default=None, max_length=64)


@dataclass(frozen=True)
class Button:
    """A reply button. WhatsApp allows at most 3 per message, titles up to 20 characters."""

    id: str  # what comes back when it is tapped, e.g. "accept:PAW-0042"
    title: str


@dataclass
class Outbound:
    """A message waiting to be sent.

    The case logic returns a list of these instead of sending directly. That
    way the database work can be committed first, and the same logic can be
    used from a web request or from a background job.
    """

    to: str
    text: str
    buttons: list[Button] = field(default_factory=list)
    media_name: str | None = None  # a photo to send just before the text


class ChannelAdapter(ABC):
    """What the rest of the app may ask of a channel."""

    name: str

    @abstractmethod
    async def send_text(self, to_number: str, text: str) -> None:
        """Send a plain text message to one number."""

    @abstractmethod
    async def send_buttons(self, to_number: str, text: str, buttons: list[Button]) -> None:
        """Send a message with reply buttons under it."""

    @abstractmethod
    async def send_image(self, to_number: str, media_name: str) -> None:
        """Send a stored photo."""


async def deliver(channel: ChannelAdapter, outbox: list[Outbound]) -> None:
    """Send every message. One failed send must not stop the rest."""
    for message in outbox:
        try:
            if message.media_name:
                await channel.send_image(message.to, message.media_name)
            if message.buttons:
                await channel.send_buttons(message.to, message.text, message.buttons)
            else:
                await channel.send_text(message.to, message.text)
        except Exception:
            log.exception("Could not send a message on channel %s", channel.name)
