"""A local stand-in for WhatsApp.

Chats live in memory, one transcript per phone number. The page at /sim posts
messages here exactly as WhatsApp's webhook will later, and polls for replies.
All numbers are invented.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.channels.base import ChannelAdapter, InboundMessage
from app.conversation import handle_inbound

PAGE = Path(__file__).with_name("simulator.html")

# Invented numbers. Never use real ones here.
PERSONAS = [
    {"number": "+910000000001", "label": "Citizen 1"},
    {"number": "+910000000002", "label": "Citizen 2"},
    {"number": "+910000000101", "label": "Team: Panaji (placeholder)"},
    {"number": "+910000000102", "label": "Team: Mapusa (placeholder)"},
]


class SimMessage(BaseModel):
    id: int
    direction: Literal["in", "out"]  # "in" = sent by the person, "out" = sent by PawSOS
    text: str
    at: datetime


class SimulatorAdapter(ChannelAdapter):
    name = "simulator"

    def __init__(self) -> None:
        self._transcripts: dict[str, list[SimMessage]] = {}
        self._next_id = 1

    def _append(self, number: str, direction: Literal["in", "out"], text: str) -> SimMessage:
        entry = SimMessage(
            id=self._next_id, direction=direction, text=text, at=datetime.now(UTC)
        )
        self._next_id += 1
        self._transcripts.setdefault(number, []).append(entry)
        return entry

    def record_inbound(self, number: str, text: str) -> SimMessage:
        return self._append(number, "in", text)

    async def send_text(self, to_number: str, text: str) -> None:
        self._append(to_number, "out", text)

    def transcript(self, number: str, after: int = 0) -> list[SimMessage]:
        return [m for m in self._transcripts.get(number, []) if m.id > after]


def build_router(channel: SimulatorAdapter) -> APIRouter:
    router = APIRouter(prefix="/sim", tags=["simulator"])

    @router.get("", response_class=HTMLResponse)
    def page() -> str:
        return PAGE.read_text(encoding="utf-8")

    @router.get("/personas")
    def personas() -> list[dict[str, str]]:
        return PERSONAS

    @router.post("/inbound")
    async def inbound(message: InboundMessage) -> dict[str, bool]:
        channel.record_inbound(message.from_number, message.text or f"[{message.kind}]")
        await handle_inbound(message, channel)
        return {"ok": True}

    @router.get("/messages")
    def get_messages(phone: str, after: int = 0) -> list[SimMessage]:
        return channel.transcript(phone, after)

    return router
