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

## Open
- Nothing right now.
