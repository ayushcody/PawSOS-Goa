# PawSOS Goa: plan

Deadline: **Mon 23 Nov 2026**. Plan written Tue 10 Nov 2026. That leaves 12 working days after today.

Slices 1 to 5 are the must-have demo. They are scheduled first and finish by Mon 16 Nov, with a rehearsal day on Tue 17 Nov before anything optional starts.

## Progress

| # | Slice | Target day | Status |
|---|-------|-----------|--------|
| 0 | Project memory (these docs) | Tue 10 Nov | Done 10 Nov |
| 1 | Skeleton, health check, simulator, echo bot | Wed 11 Nov | Done 10 Nov (a day early). `TODO(me)` open: fallback test in `tests/test_slice1.py` |
| 2 | Case creation with photo and location | Thu 12 Nov | Done 10 Nov (two days early). `TODO(me)` open: `in_goa()` in `app/cases/geo.py` |
| 3 | Vision triage | Fri 13 Nov | Not started |
| 4 | Zones, routing, dedup | Sat 14 Nov | Not started |
| 5 | Volunteer dispatch, buttons, escalation | Sun 15 to Mon 16 Nov | Not started |
| – | **Checkpoint: must-have demo rehearsal** | Tue 17 Nov | – |
| 6 | Bite flow | Wed 18 Nov | Not started |
| 7 | Booking with Google Calendar | Thu 19 Nov | Not started |
| 8 | Dashboard | Fri 20 Nov | Not started |
| 9 | Real WhatsApp hookup with an ngrok guide | Sat 21 Nov | Not started |
| 11 | Demo script and seed polish | Sun 22 Nov | Not started |
| 10 | Voice notes (stretch) | Only if ahead | Not started |
| – | **Freeze, final run-through, submit** | Mon 23 Nov, by noon | – |

## What I need from you, and when

Each of these comes with click-by-click steps on the day. Secrets go in `.env`, never in chat.

| By | What | Why so early |
|----|------|--------------|
| Thu 12 Nov | Supabase project (free tier) with PostGIS enabled | Slice 2 stores cases |
| Fri 13 Nov | Anthropic API key | Slice 3 triage |
| Fri 13 Nov | Start Meta developer app and WhatsApp test number | Not needed until slice 9, but Meta setup can stall, so start it a week ahead |
| Thu 19 Nov | Google Cloud project with Calendar API and a service account | Slice 7 |
| Sat 21 Nov | ngrok account, a phone for the live test | Slice 9 |

## Slices and acceptance criteria

Every slice ends the same way: tests pass, you test by hand, you confirm, I commit and update this file. Each slice leaves one `TODO(me)` for you to write.

### 1. Skeleton, health check, simulator, echo bot (Wed 11 Nov)
- `GET /health` returns ok.
- `ChannelAdapter` interface with two inbound types to start (text, and a generic message envelope) and `send_text`.
- Simulator page at `/sim`: a chat window that posts to the same handler the WhatsApp webhook will use. You can pick which phone number you are (citizen or team) so one browser can play both sides.
- Echo bot: whatever you type comes back.
- `app/messages.py` exists with the first keys.
- New concepts explained: webhooks, the adapter pattern.

### 2. Case creation with photo and location (Thu 12 Nov)
- Simulator can send a photo and a location pin.
- Photo plus location from one number creates a case with an ID like `PAW-0042`, state `REPORTED`.
- Tables via migrations: cases, reports, photos, events. Every change writes an event.
- Citizen gets a confirmation with the case ID. If only one of photo or location arrives, the bot asks for the other.
- New concepts: migrations, PostGIS points.

### 3. Vision triage (Fri 13 Nov)
- Photo goes to Claude; the reply parses into a Pydantic `TriageResult` (species, injury type, urgency, aggression risk, 2 to 3 first-aid steps).
- One retry on invalid output; after that the case is flagged for a human and still moves on at urgency `high`.
- Prompt forbids diagnosis; a test checks the first-aid copy carries the "not a diagnosis" line.
- Case moves `REPORTED -> TRIAGED`. Tests mock the Anthropic client.
- New concepts: structured output, validation and retry.

### 4. Zones, routing, dedup (Sat 14 Nov)
- `seed/` holds the 14 urban local bodies with approximate centres and radii, teams, hours.
- A location maps to a zone (nearest centre within radius, else nearest overall, labelled approximate).
- A report within 200 m and 2 hours of an open case with the same species merges into it; all reporters are told.
- Case moves `TRIAGED -> NEW` or `TRIAGED -> MERGED`.
- State machine module with the explicit transitions table and tests for every allowed and one rejected transition.
- New concepts: state machines, `ST_DWithin`.

### 5. Volunteer dispatch, buttons, escalation (Sun 15 to Mon 16 Nov)
- Team gets an alert with Accept / Decline buttons (simulator renders buttons).
- Accept: `ROUTED -> ACCEPTED`; then On site and Resolved buttons. The citizen is told at each step, with the case ID.
- Closed team, a Decline, or 10 minutes of silence escalates to the next team, then the taluka officer.
- Escalation timer runs on APScheduler; the delay is configurable so the demo can use 20 seconds.
- New concepts: scheduled jobs, idempotent button handling.

### Checkpoint (Tue 17 Nov)
Full run on the simulator: report, triage, duplicate report merged, routed, timeout escalation, accepted, on site, resolved. Fix anything shaky. If slices 1 to 5 are not solid by the end of this day, I say so plainly and we cut from the list below.

### 6. Bite flow (Wed 18 Nov)
- "I was bitten" (text or a menu option) returns the nearest seeded health centre, wash-the-wound guidance, and records a bite hotspot.
- Health centres are marked `[VERIFY]` in seed data and the message says to call ahead.

### 7. Booking with Google Calendar (Thu 19 Nov)
- BOOK lists the 2 demo camps, then slots; picking one creates a booking and a Calendar event on that camp's calendar.
- Reminder job the day before. Calendar API mocked in tests.

### 8. Dashboard (Fri 20 Nov)
- `/dashboard`: Leaflet map with layers (bites, rescues, camps), case list with filters, sterilisation counts per municipality (the SPEC numbers), next-camp suggestion.
- About 40 seeded demo cases.
- The suggestion rule is simple and explained on the page: most bite reports, fewest camps.

### 9. Real WhatsApp hookup (Sat 21 Nov)
- `WhatsAppCloudAdapter` implements the same interface: webhook verification, signature check, text, image, location, interactive buttons.
- `docs/WHATSAPP_SETUP.md` with the ngrok guide.
- One real end-to-end run from your phone.

### 11. Demo script and seed polish (Sun 22 Nov)
- `docs/DEMO.md` (3 minutes, with a simulator fallback path), `docs/ARCHITECTURE.md` (one page), README checked from a clean clone.

### 10. Voice notes (stretch)
- `SpeechToText` interface and stub land in slice 2 or 3 so the seam exists. Real Bhashini only if Sun 22 Nov has spare hours.

## If we fall behind: cut order

1. Slice 10 voice (already a stretch).
2. Google Calendar sync in slice 7: keep booking in our own table, show the calendar event as "would sync".
3. Slice 9 real WhatsApp: demo on the simulator only, and say so.
4. Slice 6 bite flow: reduce to a static reply with the nearest health centre.
5. Never cut: slices 1 to 5, the dashboard map, the demo script.

## Risks

- **Meta setup delays.** Mitigation: the simulator is the primary demo path from day 1; Meta setup starts Fri 13 Nov.
- **Live vision call fails on stage.** Mitigation: a recorded triage result can be replayed for the demo photo (labelled as recorded if used).
- **One-day slices are tight.** Slice 5 has two days, and Tue 17 Nov is a buffer.
