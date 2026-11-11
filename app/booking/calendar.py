"""Putting bookings on a camp's Google Calendar.

The rest of the app talks to the CalendarClient interface, so tests use a
fake and the app keeps working when Google is not set up: the booking is
always saved in our own database first, and the calendar entry is an extra.
"""

import logging
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from app.config import get_settings

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
GOA_TIMEZONE = "Asia/Kolkata"


class CalendarClient(Protocol):
    def create_event(
        self, calendar_id: str, summary: str, description: str, start: datetime, end: datetime
    ) -> str:
        """Create an event and return its id."""
        ...

    def delete_event(self, calendar_id: str, event_id: str) -> None:
        """Remove an event, e.g. when its booking is cancelled."""
        ...


class GoogleCalendar:
    def __init__(self, service_account_file: str) -> None:
        # Imported here so the app starts even if Google's libraries have a problem.
        import google_auth_httplib2
        import httplib2
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        credentials = service_account.Credentials.from_service_account_file(
            service_account_file, scopes=SCOPES
        )
        # A 10 second limit, so a slow Google never freezes a chat reply for long.
        http = google_auth_httplib2.AuthorizedHttp(credentials, http=httplib2.Http(timeout=10))
        self._service = build("calendar", "v3", http=http, cache_discovery=False)

    def create_event(
        self, calendar_id: str, summary: str, description: str, start: datetime, end: datetime
    ) -> str:
        body = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start.isoformat(), "timeZone": GOA_TIMEZONE},
            "end": {"dateTime": end.isoformat(), "timeZone": GOA_TIMEZONE},
        }
        event = self._service.events().insert(calendarId=calendar_id, body=body).execute()
        return event["id"]

    def delete_event(self, calendar_id: str, event_id: str) -> None:
        # Not yet run against Google. events.delete is the documented call;
        # a missing event raises, and the caller logs it and carries on.
        self._service.events().delete(calendarId=calendar_id, eventId=event_id).execute()


def calendar_id_for(camp_slug: str) -> str | None:
    """Look up a camp's calendar in CAMP_CALENDARS, written as "slug=id,slug=id"."""
    for pair in get_settings().camp_calendars.split(","):
        slug, _, calendar_id = pair.strip().partition("=")
        if slug == camp_slug and calendar_id:
            return calendar_id
    return None


@lru_cache
def get_calendar() -> CalendarClient | None:
    """The app's calendar client, or None when Google is not set up."""
    path = get_settings().google_service_account_file
    if not path:
        return None
    if not Path(path).is_file():
        log.warning("GOOGLE_SERVICE_ACCOUNT_FILE is set but %s does not exist.", path)
        return None
    try:
        return GoogleCalendar(path)
    except Exception:
        log.exception("Could not set up Google Calendar. Bookings will be saved without it.")
        return None
