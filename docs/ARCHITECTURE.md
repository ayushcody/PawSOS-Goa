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

## Design choices

| Choice | Why |
|---|---|
| Channel adapter | The simulator and real WhatsApp run identical logic, so the demo has a fallback and tests need no network. |
| One state machine with a transitions table | A case can only move along listed transitions, and every move writes an audit row. |
| Structured output, validated, one retry, human fallback | Nothing unchecked from the model reaches a citizen, and a model failure never blocks a case. |
| Deadlines stored in the database, polled by a job | Escalation survives a restart. |
| Logic returns messages; the caller saves, then sends | A failed send cannot undo a saved case. |
| All outbound copy in one file under language-neutral keys | Konkani and Marathi can be added without code changes. |
| Signed webhook, masked phone numbers in logs, password on staff pages | Only Meta can post messages; personal numbers stay out of logs and off the dashboard. |
| The next-camp suggestion is a printed counting rule | Officials can see exactly why an area was suggested. |

## Stack

Python 3.12, FastAPI, SQLAlchemy and Alembic migrations, Postgres with PostGIS, Anthropic Python SDK (model id from configuration), APScheduler, WhatsApp Business Cloud API, Google Calendar API, Leaflet. Over 170 automated tests; every external service is replaced by a stand-in in tests.

## What is real and what is not (11 Nov; update before submitting)

| Part | Status |
|---|---|
| Report, dedup, routing, escalation, status updates, bite flow, booking, dashboard | Working on the simulator and covered by tests |
| Vision triage | Written and tested against a stand-in. **Not yet run against the real model.** |
| Real WhatsApp | Written and tested against a stand-in. **Not yet run with a real phone.** |
| Google Calendar sync | Written. **Not yet run against Google.** |
| Voice notes in Konkani, Marathi, Hindi | Not built |
| Zones | Approximate circles around 14 town centres, not official boundaries |
| Teams, camps, dashboard cases | Placeholders and demo data, labelled as such |
| Health centres | A list from general knowledge, every entry unconfirmed |
