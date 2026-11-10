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

## Open
- **Local database for tests and development** (decide in slice 2): Supabase project directly, or a local Postgres with PostGIS in Docker for tests. Leaning local for tests so they run offline.
