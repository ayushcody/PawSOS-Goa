# PawSOS Goa: architecture on one page

One Goa-wide WhatsApp number for animal emergencies: report, triage, dedup, route, close the loop. One Python service, one database.

```
 Citizen's phone                       Rescue team's phone
       |  WhatsApp                            ^  WhatsApp (buttons)
       v                                      |
 +-----------------------------------------------------------+
 |  Channel adapters   WhatsApp Cloud API  |  web simulator   |
 +-----------------------------------------------------------+
       |  one message shape for every channel
       v
 +-----------------------------------------------------------+
 |  Conversation      photo + location -> case               |
 |  Triage            Claude vision -> checked JSON          |
 |  Dedup             200 m, 2 hours, similar animal         |
 |  Routing           zone -> team -> next team -> officer   |
 |  State machine     the only place a case changes state    |
 |  Bite flow | Booking | Scheduled jobs                     |
 |  STATUS and CANCEL | each number's language               |
 +-----------------------------------------------------------+
       |                         |                    |
       v                         v                    v
  Postgres + PostGIS       Google Calendar      Dashboard (Leaflet)
  cases, audit log         one per camp         map, list, counts
```

## How a report moves

1. **In.** A photo and a location arrive from WhatsApp or the simulator. Both become the same `InboundMessage`, so nothing past the adapter knows which channel was used.
2. **Case.** The two together open a case (`PAW-0041`) in state `REPORTED`.
3. **Triage.** The photo goes to Claude. The reply must fit a fixed schema: species, what is visible, urgency, aggression risk, and two or three safe steps. A reply that does not fit is asked for once more; after that the case is flagged for a person and carries on at high urgency. The prompt and the copy forbid a diagnosis.
4. **Dedup.** PostGIS looks for an open case within 200 metres and 2 hours with a similar animal. If there is one, the report is merged into it and every reporter is told.
5. **Route.** The nearest zone's team is alerted with Accept and Decline buttons. A closed team, a decline, or 10 minutes of silence passes the case to the next nearest team, then the taluka officer.
6. **Close the loop.** Accepted, on site, resolved: each step is sent to everyone who reported it.

```
REPORTED -> TRIAGED -> MERGED
                    -> NEW -> ROUTED <-> ESCALATED -> ACCEPTED -> ON_SITE -> RESOLVED
any open state -> CANCELLED
```

A change of state locks the case row and checks the database first, so a stale copy (say, triage finishing after the reporter cancelled) cannot reopen a closed case.

## Modules added on 11 Nov

These were written after the handoff on branch `pickup-tasks`. They have since been merged, run on the simulator and covered by `tests/test_pickup.py`. None has been tried against a real outside service.

| Module | What it does |
|---|---|
| `app/citizen.py` | STATUS (a person's open cases and upcoming bookings) and CANCEL (a numbered list, or `CANCEL PAW-0042` / `CANCEL BK-0005`). The CANCEL list is kept in the person's `booking_drafts` row, so a number has one meaning at a time. A case cancel goes through the state machine and stands down any team still involved. |
| `app/contacts.py` | Each phone number's language, the LANGUAGE menu, and adopting the language a voice note was heard in. Messages to that number are rendered from the matching table in `app/messages.py` (`KOK`, `MR`, `HI`); teams always get English. |
| `app/channels/templates.py` | Which WhatsApp template stands in for which message (team alert, "no answer in time", camp reminder) when the 24-hour window is closed, and the order of its placeholders. The WhatsApp adapter tries the normal message first and the template once. |
| `app/dashboard/actions.py` | Staff cancel a case with a reason. Staff assigning a team lives in `app/routing/dispatch.py` (`assign_team`), beside the other alerts. Both return messages; the route saves, then sends, as everywhere else. |
| `app/dashboard/routes.py`, `queries.py` | New: the case detail (`/dashboard/cases/{id}`), photos by id behind the password (`/dashboard/photos/{id}`), the two staff actions (POST, refused when sent from another website), and response times from the audit log. |
| `app/voice/speech.py` | `BhashiniSpeechToText`: ffmpeg turns WhatsApp's OGG/Opus into WAV in memory, then Bhashini's config and compute calls return the words. |

## Tables

| Table | Holds |
|---|---|
| `cases`, `reports`, `photos`, `events` | A case, each person's report of it (with their words), its photos, and the audit log |
| `zones`, `teams`, `dispatches` | Service areas, rescue teams and officers, and each alert sent to a team |
| `bite_reports`, `health_centres` | Bite reports and the unconfirmed list of centres |
| `camps`, `camp_slots`, `bookings`, `booking_drafts`, `sterilisation_counts` | Camps and their slots, bookings (`booked` or `cancelled`), each person's place in BOOK or their CANCEL list, and the 2025 figures |
| `contacts` (migration 0008, new) | One row per phone number: its chosen language and when the LANGUAGE menu was sent. Cleared by the rehearsal reset |

## Design choices

| Choice | Why |
|---|---|
| Channel adapter | The simulator and real WhatsApp run identical logic, so the demo has a fallback and tests need no network. |
| One state machine with a transitions table | A case can only move along listed transitions, and every move writes an audit row. |
| Structured output, validated, one retry, human fallback | Nothing unchecked from the model reaches a citizen, and a model failure never blocks a case. |
| Deadlines stored in the database, polled by a job | Escalation survives a restart. |
| Logic returns messages; the caller saves, then sends | A failed send cannot undo a saved case. |
| All outbound copy in one file under language-neutral keys | Konkani, Marathi and Hindi were added as tables beside the English, without changing the call sites' keys. A missing translation falls back to English. |
| Reporter words treated as untrusted | Links, phone numbers, quote marks and hidden characters are removed before a reporter's words go into a team alert. |
| Signed webhook, masked phone numbers in logs, password on staff pages | Only Meta can post messages; personal numbers stay out of logs and off the dashboard. |
| The next-camp suggestion is a printed counting rule | Officials can see exactly why an area was suggested. |

## Stack

Python 3.12, FastAPI, SQLAlchemy and Alembic migrations, Postgres with PostGIS, Anthropic Python SDK (model id from configuration), APScheduler, WhatsApp Business Cloud API, Google Calendar API, Leaflet, Bhashini for speech, and ffmpeg (a system program) to convert voice notes. 192 automated tests passed on 11 Nov before the pick-up work; every external service is replaced by a stand-in in tests. The suite has not been re-run since that work, and the new modules have no tests of their own.

## What is real and what is not (11 Nov; update before submitting)

| Part | Status |
|---|---|
| Report, dedup, routing, escalation, status updates, bite flow, booking, dashboard | Working on the simulator and covered by tests |
| Vision triage | Written and tested against a stand-in. **Not yet run against the real model.** |
| Real WhatsApp | Written and tested against a stand-in. **Not yet run with a real phone.** |
| Google Calendar sync | Written. **Not yet run against Google.** |
| Voice notes in Konkani, Marathi, Hindi | Interface and a stand-in for the simulator, tested. Bhashini speech recognition written on 11 Nov. **Not run, and never tried with real keys.** |
| STATUS and CANCEL, reporter's words in the alert, case detail, staff actions, response times | Working on the simulator and covered by tests. **Not yet checked by a person.** |
| Konkani, Marathi and Hindi replies | Written on 11 Nov, machine-drafted. **Not run, and not checked by a fluent reader.** |
| WhatsApp templates for the 24-hour window | Written on 11 Nov. **Not run, and never tried against Meta.** |
| Zones | Approximate circles around 14 town centres, not official boundaries |
| Teams, camps, dashboard cases | Placeholders and demo data, labelled as such |
| Health centres | A list from general knowledge, every entry unconfirmed |
