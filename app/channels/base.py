"""The shape every channel shares.

A channel (the simulator, WhatsApp) turns whatever it receives into an
InboundMessage, and knows how to send text back. Nothing outside
app/channels needs to know which channel is in use.
"""

from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel, Field

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


class ChannelAdapter(ABC):
    """What the rest of the app may ask of a channel."""

    name: str

    @abstractmethod
    async def send_text(self, to_number: str, text: str) -> None:
        """Send a plain text message to one number."""
