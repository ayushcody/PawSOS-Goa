# Decisions

Newest at the bottom. Each entry: what we chose, why, what we gave up.

## D-001 Simulator is the primary demo path (10 Nov)
The local web simulator and real WhatsApp share one `ChannelAdapter` interface. We build and demo on the simulator first; WhatsApp is plugged in at slice 9.
Why: Meta approval and test-number setup can stall, and stage Wi-Fi can fail.
Gave up: early testing on a real phone.

## D-002 Claude model: `claude-opus-5-5`, set by env var (10 Nov)
It accepts image input and the Python SDK can parse replies straight into a Pydantic model. The id is read from `ANTHROPIC_MODEL` so it can change without a code edit.
Gave up: nothing for the demo; cost is small at demo volume.

## D-003 Server-rendered dashboard (10 Nov)
FastAPI templates plus Leaflet from a script tag, no separate Vite build.
Why: one service, one command to run, less to break.
Gave up: a richer front end.

## D-004 Zones are centre point plus radius (10 Nov)
We do not have ward boundary polygons. Each urban local body gets an approximate centre and service radius, labelled approximate everywhere it shows.
Gave up: true ward-level routing. Real boundaries can replace the seed later without code changes.

## D-005 Port 8040 (10 Nov)
Avoids ports used by other projects on this machine.

## D-006 One entry point: `app/conversation.py` (10 Nov)
Every channel calls `handle_inbound(message, channel)`. It sits at the top level because it belongs to no single feature folder; it will hand off to cases, triage and routing.
Gave up: nothing; it can move if it grows.

## D-007 Simulator chats live in memory (10 Nov)
Transcripts clear when the server restarts. Cases will be in the database from slice 2; the chat window itself does not need to survive.

## D-008 Local Postgres with PostGIS in Docker for development and tests (10 Nov)
`docker compose up -d` starts it on port 5440 with two databases: `pawsos` (development) and `pawsos_test` (wiped by tests). Supabase gets the same migrations later by changing `DATABASE_URL`.
Why: tests run offline and cannot damage demo data.
Gave up: the official PostGIS image is Intel-only, so on Apple silicon it runs emulated (slower to start, fine for our size).

## D-009 A draft is a report with no case (10 Nov)
While we wait for the photo or the location, the report row simply has no `case_id`. A draft older than 30 minutes is ignored.
Why: no extra table, and the audit trail of what arrived when is kept.

## D-010 Plain (blocking) database calls (10 Nov)
SQLAlchemy is used in its ordinary synchronous style inside async handlers.
Why: far simpler to read and test. Gave up: throughput under heavy load, which a demo does not have.

## D-011 Photos on local disk under `uploads/` (10 Nov)
Saved with random names and served at `/media/<name>`. Only JPEG, PNG and WebP up to 10 MB, checked by type and by the first bytes of the file.
Gave up: durable storage. Supabase Storage can replace `app/channels/media.py` later.

## D-012 Plain text now gets "how to report" instead of an echo (10 Nov)
The slice 1 echo was scaffolding.

## D-013 Triage never blocks a rescue (10 Nov)
If the model is unreachable, declines, gives an unusable reply twice, cannot see an animal, or no API key is set, the case still moves to `TRIAGED` at urgency `high` with `triage_status = needs_review`, and the citizen gets fixed safe-distance guidance.
Why: a wasted trip costs less than a missed emergency.

## D-014 The not-a-diagnosis line is added by our code (10 Nov)
The prompt forbids diagnosis, and `messages.triage_message()` always appends the fixed line, so the promise does not depend on the model remembering it.

## D-015 The citizen hears back twice (10 Nov)
First the case ID, at once. Then the first-aid steps a few seconds later, when triage returns. The case is saved before triage starts, so a triage failure cannot lose it.

## D-016 Photos are shrunk before triage (10 Nov)
Longest side 1568 px, JPEG. Faster, cheaper, and always under the API's image size limit. The original stays on disk.

## D-017 State machine brought forward from slice 4 (10 Nov)
Triage is the first real state change (`REPORTED -> TRIAGED`), so `app/cases/state_machine.py` and its full transitions table landed in slice 3.

## D-018 A declined triage request goes to a person, not to another model (10 Nov)
The API can re-run a declined request on a fallback model. We do not use that: one retry, then human review, keeps the behaviour easy to explain.

## D-019 "Similar animal" means same species, or species unknown (10 Nov)
Two reports within 200 m and 2 hours merge when triage names the same species, or when it could not name one for either report. Then place and time decide.
Gave up: two different animals at one spot may merge when triage failed. The team on site sees both photos.

## D-020 A merged case keeps its ID as a pointer (10 Nov)
The later case moves to `MERGED` with `merged_into_id` set, and its reports move to the case that stays open. The open case keeps the more urgent of the two urgency readings.
Known rough edge: the second reporter is first told a new case ID, then that it was added to the earlier case. Fixing it means running dedup before the first reply; left for polish.

## D-021 Escalation chain (10 Nov)
Own zone's partner team, then the nearest neighbouring zone's partner team, then the taluka officer. Built and tested in slice 4; slice 5 walks it.

## D-022 Seed covers zones and teams only so far (10 Nov)
Health centres arrive with the bite flow (slice 6), camps with booking (slice 7), demo cases with the dashboard (slice 8).

## D-023 One polling job for timeouts, not one timer per alert (10 Nov)
Each alert stores its deadline in the `dispatches` table. A single APScheduler job runs every few seconds and moves on any alert past its deadline.
Why: nothing is lost when the server restarts, and tests can run the same function with the clock moved forward.
Gave up: escalation can be late by up to a tenth of the timeout (at most 15 seconds).

## D-024 Logic returns messages, the caller sends them (10 Nov)
Dispatch functions change the database and return a list of `Outbound` messages. The caller commits, then delivers. The same code serves button taps and the background job, and a failed send cannot undo saved state.

## D-025 Taps are safe to repeat (10 Nov)
A second Accept, Decline, On site or Resolved tap repeats the acknowledgement and changes nothing. The case row is locked while a tap is handled, so two taps arriving together are handled in turn.

## D-026 A late Accept still counts (10 Nov)
A team whose alert timed out can still accept while nobody else has. The team being asked at that moment is told the case was taken.
Why: a late yes is better than waiting for the next team.

## D-027 On site must come before Resolved (10 Nov)
Tapping Resolved first re-sends the On site prompt. It keeps the lifecycle exactly as specified.

## D-028 When the whole chain is silent, the case stays ESCALATED (10 Nov)
The reporter is told we are still trying, and `chain_exhausted` is logged. Nothing re-alerts automatically; the dashboard (slice 8) should surface these.

## D-029 `IGNORE_OPENING_HOURS` for demos at night (10 Nov)
Seeded partner teams close at 18:00 (Panaji 20:00). Set it to `true` to treat every team as open.

## D-030 A bite report is separate from an animal case (10 Nov)
It is about a person, so it has its own `bite_reports` table and does not alert a rescue team. The reply invites the person to also report the animal with a photo and location.

## D-031 Bite first aid is fixed copy, not model output (10 Nov)
Wash with soap and running water for 15 minutes, no home remedies, go for anti-rabies treatment today. It is sent the moment a bite is mentioned, before we ask for a location, and it says it is not medical advice.

## D-032 Health centres are real public hospitals, all marked [VERIFY] (10 Nov)
Ten entries with approximate locations and no phone numbers. Whether each offers anti-rabies treatment is unconfirmed, and the message to the citizen says the list is not verified. Must be confirmed with the Directorate of Health Services before real use.

## D-033 Hotspot rule: 3 bites within 500 m in 30 days (10 Nov)
Our own simple threshold for the demo, not an official definition. The third bite and later ones are flagged `is_hotspot`.

## D-034 Bite detection is by keyword (10 Nov)
English words plus a few Hindi and Marathi ones, matched as whole words so "rabbit" and "a bit of blood" do not trigger it. It will miss phrasings we did not list; those people get the normal "how to report" reply.

## D-035 Booking by numbered replies, not buttons (10 Nov)
BOOK lists camps, a number picks one, a number picks a slot. WhatsApp allows only three reply buttons, and a camp can have more slots than that. Numbers work the same on every channel.

## D-036 The booking is saved first; the calendar entry is an extra (10 Nov)
If Google is not configured, is slow (10 second limit) or fails, the person still gets their booking and reference. `calendar_event_id` stays empty and the audit event records `calendar_synced: false`.
Gave up: automatic retry of a failed sync.

## D-037 Calendar IDs come from `CAMP_CALENDARS` in `.env` (10 Nov)
Written as `camp-slug=calendar-id,camp-slug=calendar-id`. They differ per Google account, so they are configuration, not seed data.

## D-038 The calendar entry shows only the last four digits of the owner's number (10 Nov)
The calendar may be shared with camp volunteers.

## D-039 Reminder rule: once, within the 24 hours before the slot (10 Nov)
A job checks every five minutes. Someone who books less than 24 hours ahead gets the reminder at the next check, shortly after the confirmation.

## D-040 One booking per phone number per camp; no cancel-a-booking yet (10 Nov)
CANCEL only leaves the conversation. Cancelling a confirmed booking is not built.

## D-041 Demo camps have fixed dates: 28 and 29 Nov 2026 (10 Nov)
After the hackathon demo (23 Nov) and clearly labelled as invented. BOOK shows nothing once they pass; change the dates in `seed/camps.json` and reload to demo later.

## D-042 One module registers every table (10 Nov)
`app/models.py` imports all model modules. Tables refer to each other across modules, and importing them piecemeal caused a circular import.

## D-043 The dashboard is one static page plus one JSON endpoint (10 Nov)
`/dashboard` serves a fixed HTML file; it fetches `/dashboard/data` and redraws every 15 seconds, so a case reported during the demo appears on the map without a reload. The spec said server-rendered pages; this needs no template library and is the same pattern as the simulator.

## D-044 Leaflet and map tiles come from the internet (10 Nov)
Leaflet loads from the unpkg CDN (with integrity hashes) and tiles from OpenStreetMap. Without a connection the map is blank; the tiles, lists and counts still work.
Gave up: an offline map.

## D-045 Demo cases are flagged, separate, and inert (10 Nov)
`python -m seed.demo` loads 40 invented cases and 23 invented bite reports, marked `is_demo`, tagged "demo" on the dashboard, and removable with `--clear`. Each case is walked through the real state machine so its audit trail is real in shape. They have no dispatch rows, so the escalation job never alerts anyone about them, and a real report never merges into one.
Known side effect: demo bite reports do count when the live bite flow checks for a hotspot nearby.

## D-046 Sterilisation panel shows only the spec's figures (10 Nov)
Seven municipalities have a 2025 figure in SPEC section 1. The other seven show "No figure". An empty column means unknown, never zero.

## D-047 The next-camp suggestion is a counting rule (10 Nov)
Among municipalities with no camp scheduled: most bite reports to PawSOS in the last 30 days; a tie goes to one that held no camps in 2025. The rule is printed on the page, and it is described as a count, not a prediction.

## D-048 Optional dashboard password; no phone numbers on the dashboard (10 Nov)
If `DASHBOARD_PASSWORD` is set, `/dashboard` and `/dashboard/data` ask for it (HTTP Basic, any user name). Empty means open, for local work only. Reporter numbers are never sent to the page.
Not covered: photos under `/media/` are reachable by anyone who has the link; names are random and unguessable. No per-user accounts.

## D-049 The dashboard reads the last 30 days and filters in Python (10 Nov)
Fine at hackathon scale. A real deployment would filter in SQL and page the list.

## Open
- Nothing right now.
