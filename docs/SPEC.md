# PawSOS Goa: specification

One Goa-wide WhatsApp number for animal emergencies. No app to install.

Entry for the Goa AI Hackathon 2026, Track 3: AI-Powered Emergency Management Platform for Animal Welfare Operations. Deadline: **Monday 23 November 2026**.

## 1. The problem

Use only these facts in docs and the demo. Do not add statistics that are not listed here.

- Goa recorded **19,368 dog bite cases in 2025** (stray and pet), about one every 27 minutes. Source: Health Intelligence Bureau data tabled in the Goa Legislative Assembly (LAQ 097), reported by Goemkarponn, January 2026.
- Sterilisation is uneven. In 2025, **Canacona, Sankhalim, Valpoi and Mapusa held zero camps**, while Panaji's partner sterilised **2,918** dogs, Ponda **1,121** and Curchorem-Cacora **243**.
- Helplines are fragmented. Each municipality has its own number, run by the council or a partner NGO. Some have limited hours (Panaji's runs 8 am to 8 pm).
- The channel is proven. Andhra Pradesh's Mana Mitra WhatsApp governance platform runs **1,126 services** and has served **58.2 lakh people**.

## 2. The product

| # | Feature | What happens |
|---|---------|--------------|
| 1 | Report | A citizen sends a photo and live location, or a voice note in Konkani, Marathi, Hindi or English. |
| 2 | Triage | A vision model returns species, injury type, urgency (low / medium / high / critical), aggression risk, and 2 to 3 safe first-aid instructions for the citizen. It never claims a diagnosis. |
| 3 | Dedup | A report within 200 m and 2 hours of an open case with a similar animal is merged into that case. Every reporter is notified. |
| 4 | Route | Find the municipality or ward for the location and alert that area's partner team on WhatsApp with Accept / Decline buttons. If the team is closed (outside its hours) or nobody accepts in 10 minutes, escalate to the next team, then to the taluka officer. |
| 5 | Close the loop | The citizen gets status updates (accepted, on site, resolved), each with the case ID. |
| 6 | Bite flow | If the user reports a bite, immediately send the nearest health centre offering anti-rabies treatment, and flag the location as a bite hotspot. |
| 7 | Booking | A pet owner replies BOOK and picks a sterilisation or vaccination camp slot. The slot syncs to Google Calendar. A reminder goes out the day before. |
| 8 | Dashboard | A web page for officials: Leaflet map (bites, rescues, camps), case list with filters, sterilisation counts per municipality, and a suggestion for where the next camp should go. |

## 3. Case lifecycle

```
Reported -> Triaged -> Merged (into an open case)
                    -> New -> Routed -> Accepted -> On site -> Resolved (reporter told)
                               |  ^
                               v  |
                             Escalated
Any open state -> Cancelled
```

States: `REPORTED`, `TRIAGED`, `MERGED`, `NEW`, `ROUTED`, `ESCALATED`, `ACCEPTED`, `ON_SITE`, `RESOLVED`, `CANCELLED`.

The state machine lives in one module (`app/cases/state_machine.py`) with an explicit transitions table. Any transition not in the table is rejected. Every transition writes a row to the `events` audit log.

## 4. Architecture

| Part | Choice | Notes |
|------|--------|-------|
| Channel | WhatsApp Business Cloud API (Meta test number in development) | Behind a channel adapter interface. The same logic runs through a **local web-based WhatsApp simulator**, which is also the on-stage fallback. The simulator is built in slice 1. |
| Orchestrator | Python 3.12 + FastAPI, one service | |
| AI | Anthropic Python SDK, model `claude-opus-5-5` (supports image input) | Structured output parsed into a Pydantic model; retry once on invalid output. Model id lives in config, not in code. |
| Voice | Bhashini speech-to-text behind an interface | Stub first; real integration is a stretch goal. |
| Data | Supabase Postgres with PostGIS | Tables: cases, reports, photos, teams, zones, camps, bookings, events. Migrations only, no manual SQL. |
| Calendar | Google Calendar API | One calendar per camp. |
| Jobs | APScheduler | Escalation timers and reminders. Move to Redis only if needed. |
| Dashboard | One page with Leaflet, fed by one JSON endpoint | Keep it simple. See D-043. |

### Modules

```
app/
  channels/    adapter interface, simulator, WhatsApp Cloud API
  cases/       models, state machine, audit log
  triage/      vision call, Pydantic schema, retry
  routing/     zones, team lookup, dedup, escalation order
  booking/     camps, slots, Google Calendar
  dashboard/   pages and JSON for the map
  jobs/        scheduler, escalation timers, reminders
  voice/       speech-to-text interface and stand-in
  messages.py  every outbound message, keyed, language-agnostic keys
```

## 5. Seed data (`seed/`)

- Goa's 14 urban local bodies: the Corporation of the City of Panaji plus 13 municipal councils. Centre points and service radii are **approximate** and labelled so.
- Placeholder partner teams with fake phone numbers and opening hours.
- A few health centres, each marked `[VERIFY]`.
- 2 upcoming demo camps.
- About 40 realistic demo cases across Goa for the dashboard.
- Never real people's phone numbers.

## 6. Rules

- Never commit secrets. Config comes from environment variables only.
- All outbound copy lives in `app/messages.py`: short, calm, plain language. Keys are language-agnostic so Konkani and Marathi can be added later.
- Every case event goes to the audit table.
- Triage never claims a diagnosis and gives only safe first-aid steps.
- When a decision has trade-offs, pick the simplest option that works for the demo, record it in `docs/DECISIONS.md`, and move on.
- When unsure about an external API, check its official docs.

## 7. Final deliverables

- Working demo on WhatsApp and on the simulator
- Dashboard
- Tests passing
- README setup in under 10 commands
- 3-minute demo script in `docs/DEMO.md`
- One-page architecture summary for the judges (`docs/ARCHITECTURE.md`)
