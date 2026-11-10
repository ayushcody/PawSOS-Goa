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
from sqlalchemy.orm import Session

from app import messages
from app.channels import media
from app.channels.base import ChannelAdapter, InboundMessage
from app.conversation import handle_inbound
from app.db import get_session
from app.triage.service import Triager, get_triager

PAGE = Path(__file__).with_name("simulator.html")

# Invented numbers. Never use real ones here.
PERSONAS = [
    {"number": "+910000000001", "label": "Citizen 1"},
    {"number": "+910000000002", "label": "Citizen 2"},
    {"number": "+910000000101", "label": "Team: Panaji (placeholder)"},
    {"number": "+910000000102", "label": "Team: Mapusa (placeholder)"},
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


class SimInbound(BaseModel):
    """What the simulator page may post as JSON. Photos go through /sim/inbound/photo."""

    from_number: str = Field(min_length=3, max_length=20)
    kind: Literal["text", "image", "location", "button"] = "text"
    text: str | None = Field(default=None, max_length=1000)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class SimulatorAdapter(ChannelAdapter):
    name = "simulator"

    def __init__(self) -> None:
        self._transcripts: dict[str, list[SimMessage]] = {}
        self._next_id = 1

    def _append(self, number: str, direction: Literal["in", "out"], text: str, **extra) -> None:
        entry = SimMessage(
            id=self._next_id, direction=direction, text=text, at=datetime.now(UTC), **extra
        )
        self._next_id += 1
        self._transcripts.setdefault(number, []).append(entry)

    def record_inbound(self, number: str, text: str, **extra) -> None:
        self._append(number, "in", text, **extra)

    async def send_text(self, to_number: str, text: str) -> None:
        self._append(to_number, "out", text)

    def transcript(self, number: str, after: int = 0) -> list[SimMessage]:
        return [m for m in self._transcripts.get(number, []) if m.id > after]


def build_router(channel: SimulatorAdapter) -> APIRouter:
    router = APIRouter(prefix="/sim", tags=["simulator"])
    SessionDep = Annotated[Session, Depends(get_session)]
    TriagerDep = Annotated[Triager | None, Depends(get_triager)]

    @router.get("", response_class=HTMLResponse)
    def page() -> str:
        return PAGE.read_text(encoding="utf-8")

    @router.get("/personas")
    def personas() -> list[dict[str, str]]:
        return PERSONAS

    @router.get("/locations")
    def locations() -> list[dict]:
        return LOCATION_PRESETS

    @router.post("/inbound")
    async def inbound(
        body: SimInbound, session: SessionDep, triager: TriagerDep
    ) -> dict[str, bool]:
        if body.kind == "location" and body.latitude is not None and body.longitude is not None:
            channel.record_inbound(
                body.from_number, "Location", latitude=body.latitude, longitude=body.longitude
            )
        else:
            channel.record_inbound(body.from_number, body.text or f"[{body.kind}]")
        message = InboundMessage(**body.model_dump())
        await handle_inbound(message, channel, session, triager)
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
            await channel.send_text(from_number, messages.render("photo_rejected"))
            return {"ok": False}

        channel.record_inbound(from_number, "Photo", media_url=f"/media/{name}")
        message = InboundMessage(
            from_number=from_number, kind="image", media_name=name, media_mime=mime
        )
        await handle_inbound(message, channel, session, triager)
        return {"ok": True}

    @router.get("/messages")
    def get_messages(phone: str, after: int = 0) -> list[SimMessage]:
        return channel.transcript(phone, after)

    return router
