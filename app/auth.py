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


def is_staff(credentials: HTTPBasicCredentials | None) -> bool:
    """True when no password is set, or the right one was given."""
    expected = get_settings().dashboard_password
    if not expected:
        return True
    # compare_digest takes the same time whether the guess is close or not.
    return credentials is not None and secrets.compare_digest(
        credentials.password.encode(), expected.encode()
    )


def staff_or_public(
    credentials: Annotated[HTTPBasicCredentials | None, Depends(_basic)],
) -> bool:
    """For read-only dashboard pages. With PUBLIC_DASHBOARD on, anyone may look; the
    result says whether they are staff, so photos can be left out for everyone else."""
    if is_staff(credentials):
        return True
    if get_settings().public_dashboard:
        return False
    require_password(credentials)
    return True


def require_password(
    credentials: Annotated[HTTPBasicCredentials | None, Depends(_basic)],
) -> None:
    if not is_staff(credentials):
        raise HTTPException(
            status_code=401,
            detail="Password required",
            headers={"WWW-Authenticate": 'Basic realm="PawSOS staff pages"'},
        )
