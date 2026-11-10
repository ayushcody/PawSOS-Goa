"""One shared password for the pages meant for staff: the dashboard and the simulator.

If DASHBOARD_PASSWORD is set, those pages ask for it (any user name). Leave
it empty only on your own machine: once the server is reachable from outside
(ngrok, a real deployment), anyone with the address could otherwise read the
dashboard or type into the simulator.
"""

import secrets
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.config import get_settings

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
            headers={"WWW-Authenticate": 'Basic realm="PawSOS staff pages"'},
        )
