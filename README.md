# PawSOS Goa

One Goa-wide WhatsApp number for animal emergencies. A citizen sends a photo and location; PawSOS triages it, merges duplicate reports, alerts the right local team, escalates if nobody answers, and tells the citizen what happened. No app to install.

Built for the Goa AI Hackathon 2026, Track 3: AI-Powered Emergency Management Platform for Animal Welfare Operations.

## Why

- Goa recorded 19,368 dog bite cases in 2025, about one every 27 minutes (Health Intelligence Bureau data tabled in the Goa Legislative Assembly, LAQ 097; reported by Goemkarponn, January 2026).
- In 2025, Canacona, Sankhalim, Valpoi and Mapusa held zero sterilisation camps, while Panaji's partner sterilised 2,918 dogs.
- Every municipality has its own helpline, some with limited hours.

## Status

In development. See [docs/PLAN.md](docs/PLAN.md) for progress. Nothing below runs yet; the commands become real in slice 1.

## Setup

```bash
git clone <repo-url> && cd PawSOS-Goa
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env          # then fill in the keys you have
.venv/bin/alembic upgrade head
.venv/bin/python -m seed.load
.venv/bin/uvicorn app.main:app --port 8040
```

Then open `http://localhost:8040/sim` for the WhatsApp simulator and `http://localhost:8040/dashboard` for the officials' dashboard.

## Tests

```bash
.venv/bin/pytest -q
```

## Docs

- [docs/SPEC.md](docs/SPEC.md): what we are building
- [docs/PLAN.md](docs/PLAN.md): slices, dates, progress
- [docs/DECISIONS.md](docs/DECISIONS.md): trade-offs and why

All seed data is synthetic. Zone centres and radii are approximate. Health centres are marked `[VERIFY]`.
