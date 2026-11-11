"""The officials' dashboard: one page, and the JSON it draws from.

    GET  /dashboard                      the page (map, lists, counts)
    GET  /dashboard/data                 everything the page shows, as JSON
    GET  /dashboard/cases/{id}           one case in detail (photos, triage, audit trail)
    GET  /dashboard/photos/{photo_id}    a stored photo, looked up by its id
    POST /dashboard/cases/{id}/assign    staff send the case to a team   {"team_id": 3, "note": "..."}
    POST /dashboard/cases/{id}/cancel    staff close the case            {"reason": "..."}

All of them sit behind the staff password when one is set (see app/auth.py).
The two POSTs take JSON only, so a plain form on another site cannot fire them.
"""

from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, StringConstraints
from sqlalchemy.orm import Session

from app.auth import require_password
from app.cases.models import Case, Photo
from app.cases.state_machine import InvalidTransition
from app.channels import media
from app.channels.base import ChannelAdapter, deliver
from app.dashboard import actions, queries
from app.db import get_session
from app.routing import dispatch
from app.routing.models import Team

PAGE = Path(__file__).with_name("page.html")
STAFF = "staff"  # the actor recorded in the audit log; there is one shared staff password


class AssignBody(BaseModel):
    team_id: int
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None


class CancelBody(BaseModel):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]


def build_router(channel: ChannelAdapter) -> APIRouter:
    """`channel` sends the messages that staff actions produce (see app/channels/routed.py)."""
    router = APIRouter(
        prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(require_password)]
    )
    SessionDep = Annotated[Session, Depends(get_session)]

    def case_or_404(session: Session, case_id: str, *, lock: bool = False) -> Case:
        case = queries.find_case(session, case_id, lock=lock)
        if case is None:
            raise HTTPException(status_code=404, detail=f"No case {case_id}")
        return case

    @router.get("", response_class=HTMLResponse)
    def page() -> str:
        return PAGE.read_text(encoding="utf-8")

    @router.get("/data")
    def data(
        session: SessionDep,
        status: Literal["open", "closed", "all"] = "all",
        urgency: Literal["low", "medium", "high", "critical"] | None = None,
        zone: str | None = None,
    ) -> dict[str, Any]:
        return queries.dashboard_data(session, status=status, urgency=urgency, zone=zone)

    @router.get("/cases/{case_id}")
    def case_detail(case_id: str, session: SessionDep) -> dict[str, Any]:
        return queries.case_detail(session, case_or_404(session, case_id))

    @router.get("/photos/{photo_id}")
    def photo(photo_id: int, session: SessionDep) -> FileResponse:
        # Looked up by id, and the stored name is checked again by media.path_for,
        # so no request can reach a file that is not one of our saved photos.
        stored = session.get(Photo, photo_id)
        path = media.path_for(stored.path) if stored else None
        if path is None:
            raise HTTPException(status_code=404, detail="Not found")
        return FileResponse(path, media_type=stored.mime)

    @router.post("/cases/{case_id}/assign")
    async def assign(case_id: str, body: AssignBody, session: SessionDep) -> dict[str, Any]:
        case = case_or_404(session, case_id, lock=True)
        team = session.get(Team, body.team_id)
        if team is None:
            raise HTTPException(status_code=404, detail="No such team")
        try:
            outbox = dispatch.assign_team(session, case, team, actor=STAFF, note=body.note or None)
        except InvalidTransition:
            raise HTTPException(
                status_code=409,
                detail=f"{case_id} is not waiting for a team (it is {case.state}), "
                "so it cannot be sent to one.",
            ) from None
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from None
        session.commit()  # save first, then send: a failed send must not undo the change
        await deliver(channel, outbox)
        return queries.case_detail(session, case)

    @router.post("/cases/{case_id}/cancel")
    async def cancel(case_id: str, body: CancelBody, session: SessionDep) -> dict[str, Any]:
        case = case_or_404(session, case_id, lock=True)
        try:
            outbox = actions.cancel_case(session, case, body.reason, actor=STAFF)
        except InvalidTransition:
            raise HTTPException(
                status_code=409, detail=f"{case_id} is already closed ({case.state})."
            ) from None
        session.commit()
        await deliver(channel, outbox)
        return queries.case_detail(session, case)

    return router
