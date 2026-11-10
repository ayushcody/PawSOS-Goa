"""The officials' dashboard: one page, and the JSON it draws from.

    GET /dashboard         the page (map, lists, counts)
    GET /dashboard/data    everything the page shows, as JSON

Both sit behind the staff password when one is set (see app/auth.py).
"""

from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.auth import require_password
from app.dashboard import queries
from app.db import get_session

PAGE = Path(__file__).with_name("page.html")


def build_router() -> APIRouter:
    router = APIRouter(
        prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(require_password)]
    )

    @router.get("", response_class=HTMLResponse)
    def page() -> str:
        return PAGE.read_text(encoding="utf-8")

    @router.get("/data")
    def data(
        session: Annotated[Session, Depends(get_session)],
        status: Literal["open", "closed", "all"] = "all",
        urgency: Literal["low", "medium", "high", "critical"] | None = None,
        zone: str | None = None,
    ) -> dict[str, Any]:
        return queries.dashboard_data(session, status=status, urgency=urgency, zone=zone)

    return router
