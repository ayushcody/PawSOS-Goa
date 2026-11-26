# PawSOS Goa

**One Goa-wide WhatsApp number for every animal emergency.** A citizen sends a photo and a location; PawSOS triages the photo, merges duplicate reports, alerts the nearest rescue team, escalates if nobody answers, and tells the citizen what happened at every step. No app to install.

Goa AI Hackathon 2026, Track 3: AI-Powered Emergency Management Platform for Animal Welfare Operations.

| | |
|---|---|
| Live site and a private demo you can try | https://goa.ayushchougula.in |
| Demo film (2 min 10 s, narrated) | https://goa.ayushchougula.in/demo |
| Officials' dashboard (invented demo data) | https://goa.ayushchougula.in/dashboard |
| Presentation (PDF) | [PawSOS_Goa_Presentation.pdf](app/static/site/files/PawSOS_Goa_Presentation.pdf) |
| Evidence and status (PDF) | [PawSOS_Goa_Evidence_and_Status.pdf](app/static/site/files/PawSOS_Goa_Evidence_and_Status.pdf) |
| Architecture | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), diagram: [architecture.jpg](app/static/site/img/architecture.jpg) |

## The problem

- Goa recorded 19,368 dog bite cases in 2025, about one every 27 minutes (Health Intelligence Bureau data tabled in the Goa Legislative Assembly, LAQ 097; reported by Goemkarponn, January 2026).
- In 2025, Canacona, Sankhalim, Valpoi and Mapusa held zero sterilisation camps, while Panaji's partner sterilised 2,918 dogs.
- Every municipality runs its own helpline, some with limited hours (Panaji's runs 8 am to 8 pm). A person who finds an injured animal has no single number to call.

## The solution

1. **Report.** A photo and a live location on WhatsApp open a case with an ID such as `PAW-0041`.
2. **Triage.** Claude reads the photo: species, urgency, aggression risk and two or three safe things to do while waiting. It never names a diagnosis.
3. **Merge duplicates.** Another report within 200 m and 2 hours of a similar open case joins it, so the team gets one alert, not two.
4. **Alert the nearest team** with the photo, a map link and Accept / Decline buttons.
5. **Escalate.** A decline, a closed team or no answer moves the case to the next team, then the taluka officer.
6. **Close the loop.** Accepted, on site, resolved: every reporter hears each step, then rates how it went.

Officials get one dashboard: every case on a map, an audit trail for each case, response times, sterilisation figures and a suggestion for where the next camp is needed. Bite reports get wound-care steps and the nearest health centre, and citizens can book a sterilisation camp slot.

**What makes it different:** it works on the app people already use; one number covers every municipality in Goa; a case is never lost or held up by the AI (if triage is slow or fails, the case is routed anyway and flagged for a person); and every change of state is checked by one state machine and written to an audit log.

## What is real today

From [docs/site/CLAIMS.md](docs/site/CLAIMS.md), which the website and film follow.

| Working, tested, run end to end | Built, tested only against stand-ins | Placeholders, not claimed |
|---|---|---|
| Report, triage, merge, route, escalate and close the loop | WhatsApp: receiving works; Meta blocks replies until the business is verified | Every rescue team and phone number is invented |
| Claude triage on a real street-dog photo (24 Nov; urgency differed between two runs of the same photo) | Telegram bot, Bhashini voice notes, Google Calendar sync | Service areas are approximate circles |
| Bite flow, camp booking, STATUS and CANCEL, after-rescue rating | Konkani, Marathi and Hindi replies: machine-drafted, not yet checked by a fluent reader | The health centre list is unconfirmed |
| Officials' dashboard with audit trail; public demo sandbox | | No accuracy, time saving or cost saving is claimed |

480 automated tests pass, with every outside service (Anthropic, WhatsApp, Telegram, Google, Bhashini) replaced by a stand-in.

## What comes next

1. **Go live on WhatsApp:** finish Meta business verification and get the three message templates approved.
2. **Real partners:** replace the placeholder teams with real municipal helplines, NGOs and taluka officers, and draw real service boundaries.
3. **Languages:** have fluent readers check the Konkani, Marathi and Hindi messages; switch on Bhashini voice notes.
4. **Triage quality:** run the model on a set of real photos with a vet, and tune the prompt before relying on urgency.
5. **Measure:** time from report to accepted and to resolved, per town, so councils can see whether it helps.

## How AI is used

- **In the product:** Claude (`claude-haiku-5-5`, set by `ANTHROPIC_MODEL`) reads each photo and returns a checked, structured answer. Its output never decides routing on its own, never claims a diagnosis, and a person can always override it. Real triage on the public demo is capped per visitor and per day.
- **In building it:** the code, tests and documents were written with AI help (Claude Code), reviewed by the team and checked by the test suite. The demo film's narration was generated with Gemini text-to-speech.

## Deployment

Every push to `main` runs the tests on GitHub Actions and, if they pass, deploys that commit to the server automatically. See [deploy/README.md](deploy/README.md).

## Setup

Needs Python 3.12 and Docker.

```bash
git clone https://github.com/ayushcody/PawSOS-Goa.git && cd PawSOS-Goa
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env          # the defaults work for local development
docker compose up -d          # local Postgres with PostGIS
.venv/bin/alembic upgrade head  # all migrations
.venv/bin/python -m seed.load  # zones, placeholder teams, health centres, demo camps
.venv/bin/python -m seed.demo  # optional: 40 invented cases for the dashboard (--clear removes them)
.venv/bin/uvicorn app.main:app --port 8040
```

Then open `http://localhost:8040/sim` for the WhatsApp simulator and `http://localhost:8040/dashboard` for the dashboard. The dashboard's map needs an internet connection. Set `DASHBOARD_PASSWORD` in `.env` before letting anyone else reach the server.

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

- [docs/site/CLAIMS.md](docs/site/CLAIMS.md): what the website and film may claim, with evidence
- [deploy/README.md](deploy/README.md): automatic deploys, and how to undo one
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
