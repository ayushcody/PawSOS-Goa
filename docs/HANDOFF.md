# PawSOS Goa: handoff for a new teammate

Written 11 Nov 2026 by Ayush (with Claude). Read this first. It tells you what the project is, how to run it, what is finished, and what you can pick up.

If you work with an AI assistant, paste this whole file into it. Claude Code also reads `CLAUDE.md` in the repository by itself.

## What the project is

One Goa-wide WhatsApp number for animal emergencies, no app. A citizen sends a photo and a location; PawSOS triages the photo, merges duplicate reports, alerts the local rescue team, escalates if nobody answers, and tells the citizen what happened. It also has a dog-bite flow, camp slot booking, and an officials' dashboard.

- **For:** Goa AI Hackathon 2026, Track 3 (AI-Powered Emergency Management Platform for Animal Welfare Operations).
- **Deadline:** Monday 23 Nov 2026.
- **Repository:** `https://github.com/ayushcody/PawSOS-Goa`, branch `main`.

## Get it running (about 10 minutes)

You need Python 3.12, Docker and git.

```bash
git clone https://github.com/ayushcody/PawSOS-Goa.git && cd PawSOS-Goa
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env
docker compose up -d
.venv/bin/alembic upgrade head
.venv/bin/python -m seed.load
.venv/bin/python -m seed.demo
.venv/bin/pytest -q
.venv/bin/uvicorn app.main:app --reload --port 8040
```

- The tests should end with **192 passed, 11 skipped**. The 11 skipped tests are Ayush's learning tasks (see "Leave these alone").
- Simulator (a fake WhatsApp in the browser): `http://localhost:8040/sim`
- Dashboard: `http://localhost:8040/dashboard`
- The database runs on port 5440 and the app on port 8040.

Everything works without any API key. Without `ANTHROPIC_API_KEY`, a photo is not triaged by the model: the citizen is told a team member will look at it, and the case carries on at high urgency.

**Try it:** in the simulator choose **Citizen 1**, press **Photo** and pick any image, then press **Location** and choose **Panaji**. Then switch to **Panaji partner team (placeholder)** and press **Accept**. `docs/DEMO.md` has the full 3-minute walk-through.

## Keys and secrets

- Each person keeps their own `.env`. It is in `.gitignore` and must never be committed.
- Never send a key through chat, and never paste one into an AI assistant. Type it into `.env` yourself.
- `.env.example` lists every setting with a safe default.

## Stack and layout

Python 3.12, FastAPI (one service), SQLAlchemy 2 with Alembic migrations (0001 to 0007), Postgres 17 with PostGIS in Docker, Anthropic Python SDK (model id from `ANTHROPIC_MODEL`, default `claude-opus-5-5`), APScheduler, WhatsApp Business Cloud API (Graph API v27.0), Google Calendar API, Leaflet.

```
app/channels     simulator and WhatsApp adapters; everything past here sees one message shape
app/conversation.py   decides what an incoming message means
app/cases        intake, the state machine, bite reports
app/triage       the vision model call and its checked schema
app/routing      zones, dedup, team alerts, escalation
app/booking      camps, BOOK conversation, Google Calendar
app/dashboard    the officials' page and its data
app/jobs         scheduled jobs (escalation deadlines, reminders)
app/voice        voice-note structure (no real speech recognition yet)
app/messages.py  every message sent to a person
seed/            zones, placeholder teams, health centres, camps, demo cases
migrations/      Alembic
tests/           pytest; every external service is replaced by a stand-in
docs/            SPEC, PLAN, DECISIONS, DEMO, ARCHITECTURE, WHATSAPP_SETUP
```

## Where things stand

- Every planned slice (1 to 11) is built and committed.
- 192 automated tests pass.
- **Nothing has been verified by a person or against a real external service.** No photo has been triaged by the real model, no booking has reached Google Calendar, and no real WhatsApp message has been sent or received. Claude ran each flow on the simulator; Ayush has not yet rehearsed them.

### Part by part

Each part is scored out of 100: code written 50, tests pass 20, run live on the simulator 10, run against the real external service 10, checked by hand by a person 10. These are judgements, not measurements.

| # | Part | Done | What is finished | What is left |
|---|---|---|---|---|
| 1 | Report: photo and location open a case | 80% | Intake in either order, 30-minute drafts, case IDs, photo checks, audit log | Hand check. `in_goa()` accepts any location (Ayush's task) |
| 2 | Triage by vision model | 65% | Prompt, checked schema, one retry, human-review fallback, never a diagnosis | **Never run against the real model.** Needs an API key, then prompt tuning on real photos |
| 3 | Dedup: 200 m, 2 hours, similar animal | 80% | Merge, every reporter told, more urgent reading kept | Hand check. The second reporter briefly sees a second case ID before the merge |
| 4 | Routing and escalation | 80% | Zone lookup, Accept and Decline buttons, escalation on decline, closed hours or timeout; team, then next team, then taluka officer | Hand check. Overnight opening hours and the time wording are Ayush's tasks |
| 5 | Status updates to the citizen | 80% | Accepted, on site, resolved, escalated, no team yet | Hand check |
| 6 | Bite flow | 70% | Keyword detection (English, some Hindi and Marathi), first-aid text, nearest health centre, hotspot flag | First-aid wording not reviewed by a person. All 10 health centres are unconfirmed |
| 7 | Camp booking | 70% | BOOK conversation, capacity, one booking per person per camp, reminder job | **Google Calendar sync never run.** A booking cannot be cancelled |
| 8 | Dashboard | 85% | Map with layers, case list with filters, flagged cases, sterilisation figures, next-camp suggestion, optional password | Hand check. No case detail view and no staff actions |
| 9 | Real WhatsApp | 60% | Adapter, signed webhook, photo download, routing between real and invented numbers, setup guide | **Never run with a real phone.** Needs a Meta app and ngrok. The guide is untested |
| 10 | Voice notes | 30% | Interface, stand-in, simulated voice note in the simulator, reply flow | **No real speech recognition.** Bhashini is a placeholder |
| 11 | Konkani, Marathi, Hindi replies | 10% | Messages are stored under language-neutral keys | No translations written; no per-person language choice |
| 12 | Demo script (`docs/DEMO.md`) | 75% | 3-minute script, fallback table, every step run by Claude on a clean copy | Not rehearsed aloud or timed |
| 13 | Architecture page and README | 90% | One-page summary; README setup run from a clean copy | Status table needs updating before submission |
| 14 | Seed data | 90% as demo data | 14 zones, 25 placeholder teams, 10 health centres, 2 demo camps, 40 demo cases, 23 demo bite reports | Zones are approximate circles; teams and camps are invented. Real data is 0% |

Overall: about 90% of the code in the specification is written, about 80% is demo-ready on the simulator, and about 15% is verified for real.

## What you can pick up

These are not built and do not depend on Ayush. Tell Ayush which one you take so two people do not build the same thing.

| Task | Where | Size |
|---|---|---|
| Show the reporter's typed or spoken description to the team in the alert | `app/routing/dispatch.py`, `app/messages.py` | Small |
| A `STATUS` command (the citizen's open cases) and `CANCEL` for a report or booking | `app/conversation.py`, `app/cases/state_machine.py`, `app/booking/flow.py` | Medium |
| Case detail on the dashboard: photo, triage, audit trail | `app/dashboard/` | Medium |
| Staff actions on flagged cases (assign a team, cancel), behind the password | `app/dashboard/`, through the state machine | Medium |
| Konkani, Marathi and Hindi versions of the messages, and remembering each person's language | `app/messages.py`, a migration for the language column | Medium; the translations need a fluent reader to check them |
| Real speech recognition behind the existing interface | `app/voice/speech.py` (`BhashiniSpeechToText`) | Medium; needs Bhashini keys and a check of their current documentation |
| Response-time figures on the dashboard (report to accept, accept to resolved), from the audit events | `app/dashboard/queries.py` | Small |
| WhatsApp message templates, so messages after the 24-hour window are not refused | `app/channels/whatsapp.py` | Medium; needs the Meta app first |

Also useful, and needing no code: run the real-phone setup in `docs/WHATSAPP_SETUP.md` and correct the guide where it is wrong, or run one report with a real Anthropic API key and note what the triage says.

## Leave these alone

Eleven small `TODO(me)` tasks are Ayush's learning exercises, each with a skipped test. Please do not solve them: the fallback test (`tests/test_slice1.py`), `in_goa()`, the four-steps test, overnight `is_open()`, `humanize_seconds()`, the look-alike words test, `format_time_range()`, `case_sort_key()`, `mask_number()`, the demo's closing sentence, and `clean_transcript()`.

## Rules the project follows

- Never commit secrets; configuration comes from `.env` only.
- Synthetic data only: no real people's phone numbers anywhere. Invented numbers start with `+91000000`, and those are routed to the simulator.
- Use only the statistics in `docs/SPEC.md` section 1. Do not add other numbers.
- Every message sent to a person lives in `app/messages.py`, short and calm.
- A case changes state only through `app/cases/state_machine.py`, and every change writes an audit event.
- Triage never claims a diagnosis.
- Schema changes go through a new Alembic migration, written by hand, never manual SQL.
- Tests replace every external service (Anthropic, WhatsApp, Google, Bhashini) with a stand-in. No test may use the network.
- Record any trade-off in `docs/DECISIONS.md` (next number is D-063) and update `docs/PLAN.md` when something is finished.
- Say plainly what has been checked and how. "Tests pass" and "I tried it by hand" are different claims.

## Working together on GitHub

1. Ayush adds you as a collaborator on the repository (Settings, Collaborators, Add people). Accept the invitation email.
2. Before you start, get the latest code:
   ```bash
   git pull
   ```
3. Work on your own branch, named after the task:
   ```bash
   git checkout -b status-command
   ```
4. Before each commit, run the tests and the linter:
   ```bash
   .venv/bin/pytest -q
   ```
   ```bash
   .venv/bin/ruff check .
   ```
5. Push the branch and open a pull request for Ayush to read:
   ```bash
   git push -u origin status-command
   ```
6. If your change adds a migration, say so in the pull request, because two people adding migrations at once need to agree on the order.

## Where to read more

`docs/SPEC.md` (what), `docs/PLAN.md` (progress and what is unverified), `docs/DECISIONS.md` (62 decisions with reasons), `docs/DEMO.md`, `docs/ARCHITECTURE.md`, `docs/WHATSAPP_SETUP.md`, `CLAUDE.md` (commands and rules).
