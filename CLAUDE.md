# PawSOS Goa

One Goa-wide WhatsApp number for animal emergencies: report, triage, dedup, route, close the loop. Goa AI Hackathon 2026, Track 3. Deadline **23 Nov 2026**.

Read `docs/SPEC.md` (what), `docs/PLAN.md` (when, progress), `docs/DECISIONS.md` (why).

## Commands

```bash
python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"   # setup
.venv/bin/uvicorn app.main:app --reload --port 8040             # run; simulator at /sim
.venv/bin/pytest -q                                             # tests
.venv/bin/alembic upgrade head                                  # migrations (from slice 2)
.venv/bin/python -m seed.load                                   # seed data (from slice 4)
```

## Layout

```
app/channels  app/cases  app/triage  app/routing  app/booking  app/dashboard  app/jobs
app/messages.py   every outbound message
seed/             zones, teams, health centres, camps, demo cases
migrations/       Alembic
tests/            pytest, external APIs mocked
docs/             SPEC, PLAN, DECISIONS, DEMO, ARCHITECTURE
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
- Claude model id comes from `ANTHROPIC_MODEL` (default `claude-opus-5-5`).

## How we work

One slice at a time (order in `docs/PLAN.md`): short plan, explain new concepts, implement with tests, run them, tell Ayush what to test by hand, wait for confirmation, commit, update PLAN.md. Leave one `TODO(me)` per slice for Ayush and review it kindly. Slices 1 to 5 are protected. If behind, say so and propose cuts from the PLAN cut order.
