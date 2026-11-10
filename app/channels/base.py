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
    """One message from a person, in channel-neutral form."""

    from_number: str = Field(min_length=3, max_length=20)
    kind: MessageKind = "text"
    text: str | None = None


class ChannelAdapter(ABC):
    """What the rest of the app may ask of a channel."""

    name: str

    @abstractmethod
    async def send_text(self, to_number: str, text: str) -> None:
        """Send a plain text message to one number."""
