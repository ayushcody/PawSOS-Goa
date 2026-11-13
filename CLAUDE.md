# PawSOS Goa

One Goa-wide WhatsApp number for animal emergencies: report, triage, dedup, route, close the loop. Goa AI Hackathon 2026, Track 3. Deadline **23 Nov 2026**.

Read `docs/SPEC.md` (what), `docs/PLAN.md` (when, progress), `docs/DECISIONS.md` (why).

## Commands

```bash
python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"   # setup
docker compose up -d                                            # local Postgres + PostGIS on port 5440
.venv/bin/alembic upgrade head                                  # apply migrations
.venv/bin/uvicorn app.main:app --reload --port 8040             # run; simulator at /sim
.venv/bin/pytest -q                                             # tests (need the database running)
.venv/bin/alembic revision -m "what changed"                    # new migration, then write it by hand
.venv/bin/python -m seed.load                                   # zones and placeholder teams; safe to rerun
.venv/bin/python -m seed.demo                                   # 40 invented cases for the dashboard; --clear removes them
.venv/bin/python -m seed.reset                                  # shows what a rehearsal reset would delete; --yes does it
```

## Layout

```
app/channels  app/cases  app/triage  app/routing  app/booking  app/dashboard  app/jobs  app/voice
app/messages.py   every outbound message
seed/             zones, teams, health centres, camps, demo cases
migrations/       Alembic
tests/            pytest, external APIs mocked
docs/             SPEC, PLAN, DECISIONS, DEMO, ARCHITECTURE, WHATSAPP_SETUP, VOICE_SETUP,
                  TRANSLATIONS, CHECKLIST
```

## Hard rules

- Never commit secrets. Config from env vars only (`.env`, see `.env.example`).
- Synthetic data only: no real people's phone numbers anywhere.
- Use only the statistics in `docs/SPEC.md` section 1. Do not invent numbers.
- All outbound copy in `app/messages.py`, keyed, short and calm.
- Case state changes only through `app/cases/state_machine.py`; every change writes an audit event.
- Triage never claims a diagnosis.
- Schema changes through migrations, never manual SQL.
- Tests mock every external API (Anthropic, WhatsApp, Google, Bhashini).
- Claude model id comes from `ANTHROPIC_MODEL` (default `claude-haiku-5-5`). Do not use an Opus model in this project.

## How we work

One slice at a time (order in `docs/PLAN.md`): short plan, explain new concepts, implement with tests, run them, tell Ayush what to test by hand, wait for confirmation, commit, update PLAN.md. Leave one `TODO(me)` per slice for Ayush and review it kindly. Slices 1 to 5 are protected. If behind, say so and propose cuts from the PLAN cut order.
