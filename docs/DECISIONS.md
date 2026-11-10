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

## Open
- Nothing right now.
