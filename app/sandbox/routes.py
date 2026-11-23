"""The public demo's endpoints: /sandbox/*.

A visitor plays two citizens and every team their cases reach. Everything goes
through the same handle_inbound as WhatsApp and the staff simulator, so the demo
runs the real logic. No password: isolation and limits come from app/sandbox/core.py
and app/triage/limits.py instead.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import messages
from app.channels import media
from app.channels.base import ChannelAdapter, InboundMessage
from app.channels.simulator import LOCATION_PRESETS, SimMessage, SimulatorAdapter
from app.config import get_settings
from app.contacts import language_for
from app.conversation import handle_inbound
from app.db import get_session
from app.routing.models import Team
from app.sandbox import core
from app.triage import limits
from app.triage.service import Triager, get_triager

COOKIE = "pawsos_sandbox"
CITIZEN_LABELS = {"c1": "You", "c2": "A passer-by"}
BUTTON_WORDS = {"accept": "Accept", "decline": "Decline", "onsite": "On site", "resolved": "Resolved"}


class SandboxInbound(BaseModel):
    who: str = Field(min_length=2, max_length=12)
    kind: Literal["text", "location", "button"] = "text"
    text: str | None = Field(default=None, max_length=500)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    button_id: str | None = Field(default=None, max_length=64)


def client_address(request: Request) -> str:
    header = get_settings().client_ip_header
    if header and request.headers.get(header):
        return request.headers[header]
    return request.client.host if request.client else "unknown"


def rate_limited(request: Request) -> None:
    # The page polls with GETs every couple of seconds; writes are what need a tight limit.
    reading = request.method == "GET"
    if not limits.allow_request(client_address(request), reading=reading):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a minute.")


def build_router(channel: SimulatorAdapter, outbound: ChannelAdapter) -> APIRouter:
    router = APIRouter(prefix="/sandbox", tags=["sandbox"], dependencies=[Depends(rate_limited)])
    SessionDep = Annotated[Session, Depends(get_session)]
    TriagerDep = Annotated[Triager | None, Depends(get_triager)]
    CookieDep = Annotated[str | None, Cookie(alias=COOKIE)]

    def sandbox_id(cookie: str | None) -> str:
        found = core.verify(cookie)
        if found is None:
            raise HTTPException(status_code=401, detail="Open /sandbox/session first.")
        return found

    def teams_by_who(session: Session) -> dict[str, Team]:
        return {f"t{t.id}": t for t in session.scalars(select(Team).order_by(Team.id))}

    def team_view(team: Team, cases: set[str], after: int = 0) -> list[SimMessage]:
        """A team's chat, cut down to messages about this sandbox's cases."""
        return [
            m for m in channel.transcript(team.phone, after)
            if core.mentioned_cases(m.text, m.buttons) & cases
        ]

    @router.get("/session")
    def session_info(
        request: Request, response: Response, session: SessionDep, cookie: CookieDep = None
    ) -> dict:
        """Start a sandbox, or describe the visitor's current one."""
        sid = core.verify(cookie)
        if sid is None:
            sid = core.new_id()
            response.set_cookie(
                COOKIE, core.sign(sid), max_age=get_settings().sandbox_ttl_hours * 3600,
                # Behind the HTTPS proxy, uvicorn's --proxy-headers makes the scheme https.
                httponly=True, samesite="lax", secure=request.url.scheme == "https",
            )
        key = core.key_for(sid)
        cases = core.case_ids(session, key)
        teams = [
            {"who": who, "label": team.name}
            for who, team in teams_by_who(session).items()
            if cases and team_view(team, cases)
        ]
        return {
            "citizens": [{"who": w, "label": label} for w, label in CITIZEN_LABELS.items()],
            "teams": teams,
            "locations": [p for p in LOCATION_PRESETS],
            "cases": sorted(cases),
        }

    @router.get("/messages")
    def get_messages(
        who: str, session: SessionDep, after: int = 0, cookie: CookieDep = None
    ) -> list[SimMessage]:
        sid = sandbox_id(cookie)
        if who in core.CITIZENS:
            return channel.transcript(core.number_for(sid, who), after)
        team = teams_by_who(session).get(who)
        if team is None:
            raise HTTPException(status_code=404, detail="No such chat.")
        return team_view(team, core.case_ids(session, core.key_for(sid)), after)

    @router.post("/inbound")
    async def inbound(
        body: SandboxInbound, session: SessionDep, triager: TriagerDep, cookie: CookieDep = None
    ) -> dict[str, bool]:
        sid = sandbox_id(cookie)
        key = core.key_for(sid)

        if body.who in core.CITIZENS:
            number = core.number_for(sid, body.who)
            # Citizens may tap their own buttons (rating, "was a person bitten?"): the
            # handlers check the number is a reporter of that case.
            if body.kind == "button":
                channel.record_inbound(number, body.text or "[button]")
            elif body.kind == "location":
                if body.latitude is None or body.longitude is None:
                    raise HTTPException(status_code=400, detail="A location needs both coordinates.")
                channel.record_inbound(number, "Location", latitude=body.latitude, longitude=body.longitude)
            else:
                channel.record_inbound(number, body.text or "")
            message = InboundMessage(
                from_number=number, kind=body.kind, text=body.text,
                latitude=body.latitude, longitude=body.longitude, button_id=body.button_id,
            )
            # The budget is spent only if this message completes a report and triage runs.
            await handle_inbound(message, outbound, session, limits.capped(triager, key), None)
            return {"ok": True}

        # A team: only its buttons, and only for this sandbox's own cases.
        team = teams_by_who(session).get(body.who)
        if team is None or body.kind != "button" or not body.button_id:
            raise HTTPException(status_code=400, detail="Teams answer with the buttons only.")
        action, _, case_id = body.button_id.partition(":")
        if action not in BUTTON_WORDS or not core.owns_case(session, key, case_id):
            raise HTTPException(status_code=403, detail="That case is not in your demo.")
        channel.record_inbound(team.phone, f"{BUTTON_WORDS[action]} ({case_id})")
        message = InboundMessage(from_number=team.phone, kind="button", button_id=body.button_id)
        await handle_inbound(message, outbound, session, None, None)
        return {"ok": True}

    @router.post("/inbound/photo")
    async def inbound_photo(
        who: Annotated[str, Form(max_length=12)],
        file: UploadFile,
        session: SessionDep,
        triager: TriagerDep,
        cookie: CookieDep = None,
    ) -> dict[str, bool]:
        sid = sandbox_id(cookie)
        if who not in core.CITIZENS:
            raise HTTPException(status_code=400, detail="Only citizens send photos.")
        number = core.number_for(sid, who)
        data = await file.read(media.MAX_BYTES + 1)
        mime = file.content_type or ""
        try:
            name = media.save_image(data, mime)
        except media.MediaError:
            channel.record_inbound(number, "[a file that could not be read]")
            await channel.send_text(number, messages.render("photo_rejected", language_for(session, number)))
            return {"ok": False}

        channel.record_inbound(number, "Photo", media_url=f"/media/{name}")
        message = InboundMessage(from_number=number, kind="image", media_name=name, media_mime=mime)
        await handle_inbound(message, outbound, session, limits.capped(triager, core.key_for(sid)), None)
        return {"ok": True}

    return router
