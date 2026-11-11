# PawSOS Goa

One Goa-wide WhatsApp number for animal emergencies. A citizen sends a photo and location; PawSOS triages it, merges duplicate reports, alerts the right local team, escalates if nobody answers, and tells the citizen what happened. No app to install.

Built for the Goa AI Hackathon 2026, Track 3: AI-Powered Emergency Management Platform for Animal Welfare Operations.

## Why

- Goa recorded 19,368 dog bite cases in 2025, about one every 27 minutes (Health Intelligence Bureau data tabled in the Goa Legislative Assembly, LAQ 097; reported by Goemkarponn, January 2026).
- In 2025, Canacona, Sankhalim, Valpoi and Mapusa held zero sterilisation camps, while Panaji's partner sterilised 2,918 dogs.
- Every municipality has its own helpline, some with limited hours.

## Status

In development. See [docs/PLAN.md](docs/PLAN.md) for progress. Working today, on the simulator: opening a case from a photo and a location, photo triage (tested with a stand-in for the model; the live call is not yet verified), placing the case in a zone, merging duplicate reports, alerting the zone's team with Accept and Decline buttons, escalating on a decline, a closed team or no answer, status updates to the reporter through to resolved, a bite flow that gives wash-the-wound guidance and the nearest listed health centre, booking a camp slot with BOOK (Google Calendar sync is written but not yet run against Google), and an officials' dashboard at `/dashboard` with a map, a case list with filters, sterilisation figures and a next-camp suggestion. Voice notes have their structure in place (an interface, a stand-in, and a simulated voice note in the simulator) but no real speech recognition yet. Real WhatsApp through Meta's Cloud API is written and tested against a stand-in, but has not yet been run with a real phone; see [docs/WHATSAPP_SETUP.md](docs/WHATSAPP_SETUP.md).

## Setup

Needs Python 3.12 and Docker.

```bash
git clone <repo-url> && cd PawSOS-Goa
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env          # the defaults work for local development
docker compose up -d          # local Postgres with PostGIS
.venv/bin/alembic upgrade head
.venv/bin/python -m seed.load  # zones, placeholder teams, health centres, demo camps
.venv/bin/python -m seed.demo  # optional: 40 invented cases for the dashboard (--clear removes them)
.venv/bin/uvicorn app.main:app --port 8040
```

Then open `http://localhost:8040/sim` for the WhatsApp simulator and `http://localhost:8040/dashboard` for the dashboard. The dashboard's map needs an internet connection. Set `DASHBOARD_PASSWORD` in `.env` before letting anyone else reach the server.

## Rehearsing the demo

```bash
.venv/bin/python -m seed.reset          # shows what a reset would delete
.venv/bin/python -m seed.reset --yes    # deletes all cases, bite reports and bookings, reloads demo data
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
- [docs/WHATSAPP_SETUP.md](docs/WHATSAPP_SETUP.md): connecting a real WhatsApp test number with ngrok

All seed data is synthetic, and demo cases are tagged "demo" on the dashboard. Zone centres and radii are approximate. Health centres are marked `[VERIFY]`.
