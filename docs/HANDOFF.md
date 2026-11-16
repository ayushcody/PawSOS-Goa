# PawSOS Goa: handoff for a new teammate

Written 11 Nov 2026 by Ayush (with Claude), and updated later on 11 Nov after the pick-up tasks were written on branch `pickup-tasks`. Read this first. It tells you what the project is, how to run it, what is finished, and what you can pick up.

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

- The tests should end with **339 passed, 13 skipped**. The 13 skipped tests are Ayush's learning tasks (see "Leave these alone").
- `alembic upgrade head` applies every migration, including 0008 (each person's language). Run it again if your database is older.
- For real voice notes you also need `ffmpeg` installed (see `docs/VOICE_SETUP.md`). Nothing else needs it.
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

Python 3.12, FastAPI (one service), SQLAlchemy 2 with Alembic migrations (0001 to 0008), Postgres 17 with PostGIS in Docker, Anthropic Python SDK (model id from `ANTHROPIC_MODEL`, default `claude-haiku-5-5`), APScheduler, WhatsApp Business Cloud API (Graph API v27.0), Google Calendar API, Leaflet, Bhashini (speech), ffmpeg.

```
app/channels     simulator and WhatsApp adapters; everything past here sees one message shape
                 (templates.py: WhatsApp templates for the 24-hour window)
app/conversation.py   decides what an incoming message means
app/citizen.py   STATUS and CANCEL
app/contacts.py  each phone number's language, and the LANGUAGE menu
app/cases        intake, the state machine, bite reports
app/triage       the vision model call and its checked schema
app/routing      zones, dedup, team alerts, escalation
app/booking      camps, BOOK conversation, Google Calendar
app/dashboard    the officials' page and its data; actions.py: staff cancel a case
app/jobs         scheduled jobs (escalation deadlines, reminders)
app/voice        voice notes: a stand-in, and Bhashini (written, never tried with real keys)
app/messages.py  every message sent to a person, in English, Konkani, Marathi and Hindi
seed/            zones, placeholder teams, health centres, camps, demo cases
migrations/      Alembic
tests/           pytest; every external service is replaced by a stand-in
docs/            SPEC, PLAN, DECISIONS, DEMO, ARCHITECTURE, WHATSAPP_SETUP, TELEGRAM_SETUP, VOICE_SETUP, TRANSLATIONS
```

## Where things stand

- Every planned slice (1 to 11) is built and committed. On `main`, 311 automated tests pass.
- After the handoff, the pick-up tasks were written on branch `pickup-tasks` (rows 10, 11 and 15 to 18 below). It was written without being run, then merged into `main` on 11 Nov. Claude then ran it on the simulator and dashboard, fixed five problems and added `tests/test_pickup.py` (`docs/PLAN.md`, "First run, fixes and tests"). **Still true: no person has checked it by hand, and nothing has been tried against Meta, Bhashini or the real model.** `docs/PLAN.md`, "What is new since the handoff", lists it; `docs/DECISIONS.md` D-063 to D-078 give the reasons.
- **Nothing has been verified by a person or against a real external service.** No photo has been triaged by the real model, no booking has reached Google Calendar, no real WhatsApp message has been sent or received, and no voice note has reached Bhashini. Claude ran the slice 1 to 11 flows on the simulator; Ayush has not yet rehearsed them.

### Part by part

Each part is scored out of 100: code written 50, tests pass 20, run live on the simulator 10, run against the real external service 10, checked by hand by a person 10. These are judgements, not measurements. Code written after the handoff earns only the "code written" points until it is run and tested.

| # | Part | Done | What is finished | What is left |
|---|---|---|---|---|
| 1 | Report: photo and location open a case | 80% | Intake in either order, 30-minute drafts, case IDs, photo checks, audit log | Hand check. `in_goa()` accepts any location (Ayush's task) |
| 2 | Triage by vision model | 65% | Prompt, checked schema, one retry, human-review fallback, never a diagnosis | **Never run against the real model.** Needs an API key, then prompt tuning on real photos. Written on `pickup-tasks`, not run: first-aid steps in the citizen's language (D-081) |
| 3 | Dedup: 200 m, 2 hours, similar animal | 80% | Merge, every reporter told, more urgent reading kept. A merge now locks the case it joins (written, not run) | Hand check. Written on `pickup-tasks`, not run: no temporary case ID when an open case is nearby (D-079) |
| 4 | Routing and escalation | 80% | Zone lookup, Accept and Decline buttons, escalation on decline, closed hours or timeout; team, then next team, then taluka officer | Hand check. Overnight opening hours and the time wording are Ayush's tasks |
| 5 | Status updates to the citizen | 80% | Accepted, on site, resolved, escalated, no team yet | Hand check. The STATUS command is row 16 |
| 6 | Bite flow | 70% | Keyword detection (English, some Hindi and Marathi), first-aid text, nearest health centre, hotspot flag | First-aid wording not reviewed by a person. All 10 health centres are unconfirmed |
| 7 | Camp booking | 70% | BOOK conversation, capacity, one booking per person per camp, reminder job | **Google Calendar sync never run.** Cancelling a booking is written (row 16) but not run, and removing its calendar entry has never been run against Google |
| 8 | Dashboard | 85% | Map with layers, case list with filters, flagged cases, sterilisation figures, next-camp suggestion, optional password | Hand check. Case detail, staff actions and response times are row 17 |
| 9 | Real WhatsApp | 60% | Adapter, signed webhook, photo download, routing between real and invented numbers, setup guide | **Never run with a real phone.** Needs a Meta app and ngrok. The guide is untested. Templates are row 18 |
| 10 | Voice notes | 45% | Interface, stand-in, simulated voice note in the simulator, reply flow (tested, run on the simulator). Bhashini speech recognition through ffmpeg, and a setup guide (`docs/VOICE_SETUP.md`): written, not run, no tests of its own | **Never tried with real Bhashini keys or a real voice note.** Whether the default pipeline offers Konkani is unknown |
| 11 | Konkani, Marathi, Hindi replies | 40% | Translations of 44 citizen messages in each language, the LANGUAGE menu, each number's language saved (migration 0008), language taken from a voice note. Written, not run | **All translations machine-drafted, none checked by a fluent reader** (`docs/TRANSLATIONS.md`). The STATUS, CANCEL and staff messages are translated too (written, not run) |
| 12 | Demo script (`docs/DEMO.md`) | 75% | 3-minute script, fallback table, every step run by Claude on a clean copy. Optional beats for the new features added 11 Nov, not run | Not rehearsed aloud or timed |
| 13 | Architecture page and README | 90% | One-page summary; README setup run from a clean copy. Status tables updated 11 Nov | Update the status tables again once the new work has been run |
| 14 | Seed data | 90% as demo data | 14 zones, 25 placeholder teams, 10 health centres, 2 demo camps, 40 demo cases, 23 demo bite reports | Zones are approximate circles; teams and camps are invented. Real data is 0% |
| 15 | Reporter's words in the team alert | 50% | Typed words between photo and location, and voice-note words, shown as `Reporter says: "…"`; links, numbers and hidden characters removed. Written, not run | Run it; tests |
| 16 | STATUS and CANCEL | 45% | STATUS lists open cases and bookings; CANCEL by number or by ID; cancel stands teams down; a cancelled booking frees its place. Written, not run | Run it; tests. New messages are translated (machine-drafted, unchecked) |
| 17 | Dashboard case detail, staff actions, response times | 50% | Case panel with photos, triage, notes, alert history, audit trail; staff assign a team or cancel with a reason; median and 90th percentile response times. Written, not run | Run it in a browser; tests. Accurate wording when a staff-chosen team declines is written, not run (D-080) |
| 18 | WhatsApp templates for the 24-hour window | 50% | Fallback to an approved template for team alerts, "no answer in time" and camp reminders; the three templates are described in `docs/WHATSAPP_SETUP.md`. Written, not run | **Never tried against Meta.** Needs the Meta app and three approved templates |

Overall: nearly all of the code in the specification is now written, tested against stand-ins and run on the simulator by Claude. About 15% is verified for real (unchanged: no real service has run and no person has checked it by hand). Some rows in the table above still say "not run"; the status in `docs/PLAN.md` is the current one.

## What you can pick up

The eight coding tasks first listed here have all been written, on branch `pickup-tasks` (pull request into `main`), and are now merged, run on the simulator and tested. The same branch also has the follow-ups in `docs/PLAN.md` ("What is new since the handoff") and decisions D-063 to D-083. `docs/CHECKLIST.md` is the list that was used for the first run.

| Task | Where | State |
|---|---|---|
| Show the reporter's typed or spoken description to the team in the alert | `app/routing/dispatch.py`, `app/messages.py` | Built, tested, run on the simulator |
| A `STATUS` command and `CANCEL` for a report or booking | `app/citizen.py`, `app/booking/flow.py`, `app/routing/dispatch.py` | Built, tested, run on the simulator |
| Case detail on the dashboard: photo, triage, audit trail | `app/dashboard/` | Built, tested, run on the simulator |
| Staff actions (assign a team, cancel), behind the password | `app/dashboard/routes.py`, `actions.py`, `app/routing/dispatch.py` | Built, tested, run on the simulator |
| Konkani, Marathi and Hindi messages, and each person's language | `app/messages.py`, `app/contacts.py`, migration 0008 | Built, tested, run on the simulator; translations not checked |
| Real speech recognition | `app/voice/speech.py` (`BhashiniSpeechToText`) | Built, tested against a stand-in; never tried with real keys |
| Response-time figures on the dashboard | `app/dashboard/queries.py` | Built, tested, run on the simulator |
| WhatsApp templates for the 24-hour window | `app/channels/templates.py`, `whatsapp.py` | Built, tested against a stand-in; never tried against Meta |

What is open now. These do not depend on Ayush; tell him which one you take so two people do not do the same thing.

| Task | What it needs | Size |
|---|---|---|
| Run the new flows on a machine with Docker and fix what breaks | Python 3.12, Docker; follow `docs/CHECKLIST.md` line by line | Medium |
| Write tests for the new features (STATUS/CANCEL, LANGUAGE and `contacts`, dashboard detail and staff actions, response times, template fallback, duplicate check, typed descriptions, reporter-word cleaning) | Docker; every external service replaced by a stand-in, as in the existing tests | Medium |
| Fix the link cleaning in team alerts: since the last change, bare domains are caught only in lowercase and from a short list, so `EVIL.COM`, `pay.in` or `bad.me` reach the team unchanged. Match case-insensitively against a full list of web endings while still keeping sentences like `market.It is bleeding` (`_LINK` and `_TLDS` in `app/routing/dispatch.py`) | Nothing external | Small |
| Check the Konkani, Marathi and Hindi messages | A fluent reader for each of the three languages; `docs/TRANSLATIONS.md` is the checklist | Small per language |
| Try real voice notes | Bhashini keys (registration needs approval, so start early), ffmpeg, and a real phone on WhatsApp; follow `docs/VOICE_SETUP.md` and correct it | Medium |
| Try real WhatsApp, with templates | A Meta developer app, ngrok, three templates created and approved; follow `docs/WHATSAPP_SETUP.md` and correct it | Medium |
| Try real triage | A real Anthropic API key in your own `.env`; run one report and note what the triage says | Small |

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
- Record any trade-off in `docs/DECISIONS.md` (next number is D-084) and update `docs/PLAN.md` when something is finished.
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

`docs/SPEC.md` (what), `docs/PLAN.md` (progress and what is unverified), `docs/DECISIONS.md` (78 decisions with reasons), `docs/DEMO.md`, `docs/ARCHITECTURE.md`, `docs/WHATSAPP_SETUP.md`, `docs/VOICE_SETUP.md`, `docs/TRANSLATIONS.md`, `CLAUDE.md` (commands and rules).
