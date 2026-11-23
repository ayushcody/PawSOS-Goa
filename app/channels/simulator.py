"""A local stand-in for WhatsApp.

Chats live in memory, one transcript per phone number. The page at /sim posts
messages here exactly as WhatsApp's webhook will later, and polls for replies.
All numbers are invented.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Form, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import messages
from app.auth import require_password
from app.booking.calendar import CalendarClient, get_calendar
from app.channels import media
from app.channels.base import Button, ChannelAdapter, InboundMessage
from app.contacts import language_for
from app.conversation import handle_inbound
from app.db import get_session
from app.routing.models import Team
from app.triage.service import Triager, get_triager
from app.voice import speech

PAGE = Path(__file__).with_name("simulator.html")

# Invented numbers. Never use real ones here.
CITIZENS = [
    {"number": "+910000000001", "label": "Citizen 1"},
    {"number": "+910000000002", "label": "Citizen 2"},
    {"number": "+910000000003", "label": "Citizen 3"},
]

# Approximate town centres, for the simulator's location picker only.
LOCATION_PRESETS = [
    {"label": "Panaji (approx.)", "latitude": 15.4909, "longitude": 73.8278},
    {"label": "Mapusa (approx.)", "latitude": 15.5937, "longitude": 73.8142},
    {"label": "Margao (approx.)", "latitude": 15.2832, "longitude": 73.9862},
    {"label": "Vasco da Gama (approx.)", "latitude": 15.3982, "longitude": 73.8113},
    {"label": "Ponda (approx.)", "latitude": 15.4027, "longitude": 74.0078},
    {"label": "Outside Goa: Mumbai (approx.)", "latitude": 19.0760, "longitude": 72.8777},
]


class SimMessage(BaseModel):
    id: int
    direction: Literal["in", "out"]  # "in" = sent by the person, "out" = sent by PawSOS
    text: str
    at: datetime
    media_url: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    buttons: list[dict[str, str]] = []
    location_request: bool = False  # the message has a "Send location" button


class SimInbound(BaseModel):
    """What the simulator page may post as JSON. Photos go through /sim/inbound/photo."""

    from_number: str = Field(min_length=3, max_length=20)
    kind: Literal["text", "image", "location", "button"] = "text"
    text: str | None = Field(default=None, max_length=1000)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    button_id: str | None = Field(default=None, max_length=64)


class SimVoice(BaseModel):
    """A pretend voice note: the simulator has no microphone, so you type what was said."""

    from_number: str = Field(min_length=3, max_length=20)
    spoken_text: str = Field(min_length=1, max_length=1000)
    language: Literal["en", "hi", "mr", "kok"] = "en"


class SimulatorAdapter(ChannelAdapter):
    name = "simulator"

    def __init__(self) -> None:
        self._transcripts: dict[str, list[SimMessage]] = {}
        self._next_id = 1

    # A public demo server runs for weeks: keep only the newest messages per number.
    MAX_PER_NUMBER = 1000

    def _append(self, number: str, direction: Literal["in", "out"], text: str, **extra) -> None:
        entry = SimMessage(
            id=self._next_id, direction=direction, text=text, at=datetime.now(UTC), **extra
        )
        self._next_id += 1
        chat = self._transcripts.setdefault(number, [])
        chat.append(entry)
        if len(chat) > self.MAX_PER_NUMBER:
            del chat[: len(chat) - self.MAX_PER_NUMBER]

    def prune(self, before: datetime) -> int:
        """Forget chats whose last message is older than `before`. Returns how many."""
        stale = [n for n, chat in self._transcripts.items() if not chat or chat[-1].at < before]
        for number in stale:
            del self._transcripts[number]
        return len(stale)

    def record_inbound(self, number: str, text: str, **extra) -> None:
        self._append(number, "in", text, **extra)

    async def send_text(self, to_number: str, text: str) -> None:
        self._append(to_number, "out", text)

    async def send_buttons(self, to_number: str, text: str, buttons: list[Button]) -> None:
        self._append(
            to_number, "out", text, buttons=[{"id": b.id, "title": b.title} for b in buttons]
        )

    async def send_image(self, to_number: str, media_name: str) -> None:
        self._append(to_number, "out", "Photo", media_url=f"/media/{media_name}")

    async def send_location_request(self, to_number: str, text: str) -> None:
        self._append(to_number, "out", text, location_request=True)

    def transcript(self, number: str, after: int = 0) -> list[SimMessage]:
        return [m for m in self._transcripts.get(number, []) if m.id > after]


def build_router(channel: SimulatorAdapter, outbound: ChannelAdapter | None = None) -> APIRouter:
    """`channel` keeps the chat transcripts. Replies go out through `outbound`, which
    may send some of them to real WhatsApp instead (see app/channels/routed.py)."""
    outbound = outbound or channel
    router = APIRouter(
        prefix="/sim", tags=["simulator"], dependencies=[Depends(require_password)]
    )
    SessionDep = Annotated[Session, Depends(get_session)]
    TriagerDep = Annotated[Triager | None, Depends(get_triager)]
    CalendarDep = Annotated[CalendarClient | None, Depends(get_calendar)]
    SpeechDep = Annotated[speech.SpeechToText | None, Depends(speech.get_speech_to_text)]

    @router.get("", response_class=HTMLResponse)
    def page() -> str:
        return PAGE.read_text(encoding="utf-8")

    @router.get("/personas")
    def personas(session: SessionDep) -> list[dict[str, str]]:
        """Citizens, plus every seeded team so you can play their side too."""
        try:
            teams = session.scalars(select(Team).order_by(Team.id)).all()
        except SQLAlchemyError:
            teams = []  # database not running: the chat page still loads
        return CITIZENS + [{"number": t.phone, "label": t.name} for t in teams]

    @router.get("/locations")
    def locations() -> list[dict]:
        return LOCATION_PRESETS

    @router.post("/inbound")
    async def inbound(
        body: SimInbound, session: SessionDep, triager: TriagerDep, calendar: CalendarDep
    ) -> dict[str, bool]:
        if body.kind == "location" and body.latitude is not None and body.longitude is not None:
            channel.record_inbound(
                body.from_number, "Location", latitude=body.latitude, longitude=body.longitude
            )
        else:
            channel.record_inbound(body.from_number, body.text or f"[{body.kind}]")
        message = InboundMessage(**body.model_dump())
        await handle_inbound(message, outbound, session, triager, calendar)
        return {"ok": True}

    @router.post("/inbound/photo")
    async def inbound_photo(
        from_number: Annotated[str, Form(min_length=3, max_length=20)],
        file: UploadFile,
        session: SessionDep,
        triager: TriagerDep,
    ) -> dict[str, bool]:
        data = await file.read(media.MAX_BYTES + 1)
        mime = file.content_type or ""
        try:
            name = media.save_image(data, mime)
        except media.MediaError:
            channel.record_inbound(from_number, "[a file that could not be read]")
            language = language_for(session, from_number)
            await channel.send_text(from_number, messages.render("photo_rejected", language))
            return {"ok": False}

        channel.record_inbound(from_number, "Photo", media_url=f"/media/{name}")
        message = InboundMessage(
            from_number=from_number, kind="image", media_name=name, media_mime=mime
        )
        await handle_inbound(message, outbound, session, triager, None)
        return {"ok": True}

    @router.post("/inbound/voice")
    async def inbound_voice(
        body: SimVoice, session: SessionDep, calendar: CalendarDep, listener: SpeechDep
    ) -> dict[str, bool]:
        channel.record_inbound(
            body.from_number,
            f"Voice note, simulated ({speech.LANGUAGES[body.language]}): {body.spoken_text}",
        )
        # The words travel as the "audio", through the same interface real audio will use.
        heard = await speech.listen(
            listener, body.spoken_text.encode(), speech.SIMULATED_MIME, body.language
        )
        message = InboundMessage(
            from_number=body.from_number,
            kind="voice",
            text=heard.text if heard else None,
            language=heard.language if heard else None,
        )
        await handle_inbound(message, outbound, session, None, calendar)
        return {"ok": heard is not None}

    @router.get("/messages")
    def get_messages(phone: str, after: int = 0) -> list[SimMessage]:
        return channel.transcript(phone, after)

    return router
