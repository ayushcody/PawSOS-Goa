# PawSOS Goa

One Goa-wide WhatsApp number for animal emergencies. A citizen sends a photo and location; PawSOS triages it, merges duplicate reports, alerts the right local team, escalates if nobody answers, and tells the citizen what happened. No app to install.

Built for the Goa AI Hackathon 2026, Track 3: AI-Powered Emergency Management Platform for Animal Welfare Operations.

## Why

- Goa recorded 19,368 dog bite cases in 2025, about one every 27 minutes (Health Intelligence Bureau data tabled in the Goa Legislative Assembly, LAQ 097; reported by Goemkarponn, January 2026).
- In 2025, Canacona, Sankhalim, Valpoi and Mapusa held zero sterilisation camps, while Panaji's partner sterilised 2,918 dogs.
- Every municipality has its own helpline, some with limited hours.

## Status

In development. See [docs/PLAN.md](docs/PLAN.md) for progress (as of 11 Nov 2026).

| Part | How far it has been checked |
|---|---|
| Opening a case from a photo and a location; placing it in a zone; merging duplicate reports; alerting the zone's team with Accept and Decline; escalating on a decline, a closed team or no answer; status updates to the reporter through to resolved | Tests pass; run on the simulator by Claude |
| Bite flow: wash-the-wound guidance and the nearest listed health centre | Tests pass; run on the simulator by Claude |
| Booking a camp slot with BOOK | Tests pass; run on the simulator by Claude. Google Calendar sync written, **not yet run against Google** |
| Officials' dashboard at `/dashboard`: map, case list with filters, sterilisation figures, next-camp suggestion | Tests pass; run in a browser by Claude |
| Photo triage by Claude | Tests pass against a stand-in. **The live call has not been run** |
| Real WhatsApp through Meta's Cloud API | Tests pass against a stand-in. **Not yet run with a real phone**; see [docs/WHATSAPP_SETUP.md](docs/WHATSAPP_SETUP.md) |
| Voice-note structure: an interface, a stand-in, and a simulated voice note in the simulator | Tests pass; run on the simulator by Claude |
| Reporter's words in the team alert; STATUS and CANCEL; dashboard case detail, staff assign and cancel, response times; WhatsApp templates for the 24-hour window; Konkani, Marathi and Hindi replies with a LANGUAGE menu; Bhashini speech recognition | **Code written 11 Nov, not yet run.** Not run against a database or on the simulator, no tests of their own, never tried against Meta or Bhashini. The translations are machine-drafted and not yet checked by a fluent reader ([docs/TRANSLATIONS.md](docs/TRANSLATIONS.md)) |

Nothing has yet been checked by hand by a person.

## Setup

Needs Python 3.12 and Docker.

```bash
git clone <repo-url> && cd PawSOS-Goa
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env          # the defaults work for local development
docker compose up -d          # local Postgres with PostGIS
.venv/bin/alembic upgrade head  # all migrations, including 0008 (each person's language)
.venv/bin/python -m seed.load  # zones, placeholder teams, health centres, demo camps
.venv/bin/python -m seed.demo  # optional: 40 invented cases for the dashboard (--clear removes them)
.venv/bin/uvicorn app.main:app --port 8040
```

Then open `http://localhost:8040/sim` for the WhatsApp simulator and `http://localhost:8040/dashboard` for the dashboard. The dashboard's map needs an internet connection. Set `DASHBOARD_PASSWORD` in `.env` before letting anyone else reach the server.

If you already had the database from before 11 Nov, run `.venv/bin/alembic upgrade head` again to add migration 0008.

Optional settings, all in `.env.example` and all off or harmless by default:

- **Real voice notes:** `SPEECH_TO_TEXT=bhashini` with Bhashini keys, and `ffmpeg` installed on the machine (a system program, not a Python package). See [docs/VOICE_SETUP.md](docs/VOICE_SETUP.md). Not yet tried with real keys.
- **WhatsApp templates** for messages outside the 24-hour window: `WHATSAPP_TEMPLATE_LANGUAGE`, `WHATSAPP_TEMPLATE_TEAM_ALERT`, `WHATSAPP_TEMPLATE_TEAM_ALERT_EXPIRED`, `WHATSAPP_TEMPLATE_BOOK_REMINDER`. Empty means no template. See [docs/WHATSAPP_SETUP.md](docs/WHATSAPP_SETUP.md). Not yet tried against Meta.

## Rehearsing the demo

```bash
.venv/bin/python -m seed.reset          # shows what a reset would delete
.venv/bin/python -m seed.reset --yes    # deletes all cases, bite reports, bookings and saved languages, reloads demo data
```

Then restart the server and follow [docs/DEMO.md](docs/DEMO.md).

## Tests

```bash
.venv/bin/pytest -q
```

Tests use a separate `pawsos_test` database in the same container.

## Docs

- [docs/HANDOFF.md](docs/HANDOFF.md): start here if you are new: setup, status, and what to pick up
- [docs/SPEC.md](docs/SPEC.md): what we are building
- [docs/PLAN.md](docs/PLAN.md): slices, dates, progress
- [docs/DECISIONS.md](docs/DECISIONS.md): trade-offs and why
- [docs/DEMO.md](docs/DEMO.md): the 3-minute demo script, with a fallback path
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): the architecture on one page
- [docs/WHATSAPP_SETUP.md](docs/WHATSAPP_SETUP.md): connecting a real WhatsApp test number with ngrok, and the message templates
- [docs/VOICE_SETUP.md](docs/VOICE_SETUP.md): real voice notes through Bhashini
- [docs/TRANSLATIONS.md](docs/TRANSLATIONS.md): checklist for a fluent reader of the Konkani, Marathi and Hindi messages

All seed data is synthetic, and demo cases are tagged "demo" on the dashboard. Zone centres and radii are approximate. Health centres are marked `[VERIFY]`.
