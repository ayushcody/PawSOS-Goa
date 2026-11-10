# PawSOS Goa

One Goa-wide WhatsApp number for animal emergencies. A citizen sends a photo and location; PawSOS triages it, merges duplicate reports, alerts the right local team, escalates if nobody answers, and tells the citizen what happened. No app to install.

Built for the Goa AI Hackathon 2026, Track 3: AI-Powered Emergency Management Platform for Animal Welfare Operations.

## Why

- Goa recorded 19,368 dog bite cases in 2025, about one every 27 minutes (Health Intelligence Bureau data tabled in the Goa Legislative Assembly, LAQ 097; reported by Goemkarponn, January 2026).
- In 2025, Canacona, Sankhalim, Valpoi and Mapusa held zero sterilisation camps, while Panaji's partner sterilised 2,918 dogs.
- Every municipality has its own helpline, some with limited hours.

## Status

In development. See [docs/PLAN.md](docs/PLAN.md) for progress. Working today, on the simulator: opening a case from a photo and a location, photo triage (tested with a stand-in for the model; the live call is not yet verified), placing the case in a zone, merging duplicate reports, alerting the zone's team with Accept and Decline buttons, escalating on a decline, a closed team or no answer, status updates to the reporter through to resolved, and a bite flow that gives wash-the-wound guidance and the nearest listed health centre. Booking, the dashboard and real WhatsApp are not built yet.

## Setup

Needs Python 3.12 and Docker.

```bash
git clone <repo-url> && cd PawSOS-Goa
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env          # the defaults work for local development
docker compose up -d          # local Postgres with PostGIS
.venv/bin/alembic upgrade head
.venv/bin/python -m seed.load  # zones, placeholder teams, health centres
.venv/bin/uvicorn app.main:app --port 8040
```

Then open `http://localhost:8040/sim` for the WhatsApp simulator.

## Tests

```bash
.venv/bin/pytest -q
```

Tests use a separate `pawsos_test` database in the same container.

## Docs

- [docs/SPEC.md](docs/SPEC.md): what we are building
- [docs/PLAN.md](docs/PLAN.md): slices, dates, progress
- [docs/DECISIONS.md](docs/DECISIONS.md): trade-offs and why

All seed data is synthetic. Zone centres and radii are approximate. Health centres are marked `[VERIFY]`.
