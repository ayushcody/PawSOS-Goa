"""The officials' dashboard: one page, and the JSON it draws from.

    GET /dashboard         the page (map, lists, counts)
    GET /dashboard/data    everything the page shows, as JSON

If DASHBOARD_PASSWORD is set, both ask for it (any user name). Leave it
empty only on your own machine.
"""

import secrets
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session

from app.config import get_settings
from app.dashboard import queries
from app.db import get_session

PAGE = Path(__file__).with_name("page.html")
_basic = HTTPBasic(auto_error=False)


def require_password(
    credentials: Annotated[HTTPBasicCredentials | None, Depends(_basic)],
) -> None:
    expected = get_settings().dashboard_password
    if not expected:
        return
    # compare_digest takes the same time whether the guess is close or not.
    if credentials is None or not secrets.compare_digest(
        credentials.password.encode(), expected.encode()
    ):
        raise HTTPException(
            status_code=401,
            detail="Password required",
            headers={"WWW-Authenticate": 'Basic realm="PawSOS dashboard"'},
        )


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
