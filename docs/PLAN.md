# PawSOS Goa: plan

Deadline: **Mon 23 Nov 2026**. Plan written Tue 10 Nov 2026. That leaves 12 working days after today.

Slices 1 to 5 are the must-have demo. They are scheduled first and finish by Mon 16 Nov, with a rehearsal day on Tue 17 Nov before anything optional starts.

## Progress

| # | Slice | Target day | Status |
|---|-------|-----------|--------|
| 0 | Project memory (these docs) | Tue 10 Nov | Done 10 Nov |
| 1 | Skeleton, health check, simulator, echo bot | Wed 11 Nov | Done 10 Nov (a day early). `TODO(me)` open: fallback test in `tests/test_slice1.py` |
| 2 | Case creation with photo and location | Thu 12 Nov | Done 10 Nov (two days early). `TODO(me)` open: `in_goa()` in `app/cases/geo.py` |
| 3 | Vision triage | Fri 13 Nov | Committed 10 Nov. **Real API call still unverified**: no case in the database has a model result yet. `TODO(me)` open: four-steps test in `tests/test_slice3.py` |
| 4 | Zones, routing, dedup | Sat 14 Nov | Committed 10 Nov (four days early). Checked by tests and one live run by Claude; no hand-test cases seen in the database. `TODO(me)` open: overnight hours in `is_open()`, `app/routing/teams.py` |
| 5 | Volunteer dispatch, buttons, escalation | Sun 15 to Mon 16 Nov | Committed 10 Nov (five days early). Checked by tests and one live browser run by Claude; no hand-test cases seen in the database. `TODO(me)` open: `humanize_seconds()` in `app/routing/dispatch.py` |
| – | **Checkpoint: must-have demo rehearsal** | Tue 17 Nov | – |
| 6 | Bite flow | Wed 18 Nov | Committed 10 Nov (eight days early). Checked by tests and one live run by Claude. `TODO(me)` open: look-alike words test in `tests/test_slice6.py` |
| 7 | Booking with Google Calendar | Thu 19 Nov | Committed 10 Nov. Checked by tests and one live simulator run by Claude; no hand run by a person is recorded in the database. **Real Google Calendar sync not yet run** (needs the service account file and `CAMP_CALENDARS`). `TODO(me)` open: `format_time_range()` in `app/booking/flow.py` |
| 8 | Dashboard | Fri 20 Nov | Committed 11 Nov (nine days early). Checked by tests and one browser run by Claude; no new case from a hand run is recorded in the database, and the password prompt has not been tried in a browser. `TODO(me)` open: `case_sort_key()` in `app/dashboard/queries.py` |
| 9 | Real WhatsApp hookup with an ngrok guide | Sat 21 Nov | Committed 11 Nov (ten days early). Checked by tests against a stand-in for Meta, and a local dry run of the webhook by Claude. **No real WhatsApp message has been sent or received**: needs Ayush's Meta app and ngrok (`docs/WHATSAPP_SETUP.md`). `TODO(me)` open: `mask_number()` in `app/channels/whatsapp.py` |
| 11 | Demo script and seed polish | Sun 22 Nov | Committed 11 Nov (eleven days early). Claude ran the README setup and every demo step on a clean copy with a scratch database. **The script has not been rehearsed aloud or timed by a person, and not run with a real API key.** `TODO(me)` open: your own closing sentence in `docs/DEMO.md` |
| 10 | Voice notes (stretch) | Only if ahead | Skeleton built and committed 11 Nov: the interface, a stand-in, a simulated voice note in the simulator, and the reply flow. Checked by tests and one browser run by Claude. Real Bhashini speech recognition then written on 11 Nov (branch `pickup-tasks`, see below): **not run, no tests of its own, never tried with real keys.** `TODO(me)` open: `clean_transcript()` in `app/voice/speech.py` |
| – | Pick-up tasks from `docs/HANDOFF.md` | After the handoff | Written 11 Nov by Arnav on branch `pickup-tasks`, merged into `main` the same day. Run on the simulator and dashboard by Claude, five problems fixed, and tests added (see "First run, fixes and tests"). Fixes and tests committed 11 Nov. Not checked by a person; never tried against Meta, Bhashini or the real model. |
| – | **Freeze, final run-through, submit** | Mon 23 Nov, by noon | – |

## What is new since the handoff

Written on 11 Nov on branch `pickup-tasks`, after `docs/HANDOFF.md`, without being run. It has since been merged, run and tested: see "First run, fixes and tests" below. Reasons are in `docs/DECISIONS.md`, D-063 to D-078.

- **Reporter's words in the team alert.** Words typed between the photo and the location, and voice-note words, appear in the alert as `Reporter says: "…"`, cleaned of links, phone numbers and hidden characters (D-063).
- **STATUS and CANCEL** (`app/citizen.py`). STATUS lists open cases and upcoming bookings. CANCEL lists them numbered; reply a number, or send `CANCEL PAW-0042` or `CANCEL BK-0005` (D-064 to D-068).
- **Dashboard case detail, staff actions, response times.** A panel per case with photos, triage, notes, alert history and audit trail; assign a team or cancel with a reason, behind the password; median and 90th percentile response times (D-070 to D-074).
- **WhatsApp templates** for the 24-hour window: team alerts, "no answer in time" and camp reminders (D-075).
- **Konkani, Marathi and Hindi.** Machine-drafted translations, a LANGUAGE menu, and each number's language saved in a new `contacts` table (migration 0008) (D-076, D-077).
- **Bhashini speech recognition** for real voice notes, through ffmpeg (D-078, `docs/VOICE_SETUP.md`).
- **Safer state changes.** A state change checks the database first, so a stale copy cannot reopen a closed case (D-069).

Also on this branch, written the same day:

- The new citizen messages (STATUS, CANCEL, staff notices) translated into Konkani, Marathi and Hindi and sent in the person's language; the welcome message mentions STATUS and CANCEL; greetings in Devanagari recognised.
- The second reporter no longer sees a temporary case ID before a merge, when an open case is nearby (D-079).
- Accurate wording when a team chosen by staff declines or does not answer (D-080).
- Triage asked to write the first-aid steps in the citizen's language (D-081).
- Fixes from a code review of the merged branch: a WhatsApp voice note no longer switches the sender to Konkani (D-082); a case cancelled or assigned while its photo is triaged stops the report flow quietly, and the escalation timer locks in the same order as everything else (D-083); typed descriptions appear in the dashboard's audit trail.

`docs/CHECKLIST.md` lists what to run, and what to expect, on the machine with Docker.

## First run, fixes and tests (11 Nov)

After the merge, Claude ran `docs/CHECKLIST.md` sections 2 and 3 on a scratch database through the simulator and the dashboard. Nearly everything behaved as written, with no server errors. Five problems were found and fixed (D-084 to D-088):

- **A shared case could never be cancelled by its reporters.** CANCEL on a shared case now withdraws that person: no more updates, and it leaves their STATUS. When the last reporter cancels, the case is cancelled and the team is told. Migration **0009** adds `reports.withdrawn_at`.
- **Bare links got through team alerts.** `EVIL.COM` is now removed; `pay.in` becomes `pay. in`, which keeps the words and stops a phone making it a link.
- **A typed description was answered with "photo received".** It is now answered with "Thank you, noted".
- **Dates and area names stayed in English inside translated replies.** Weekdays, months and the 14 area names now follow the reader's language (machine-drafted, listed in `docs/TRANSLATIONS.md`).
- **A location sent after a bite report and a photo went only to the bite report.** One location now answers both: the nearest health centre, and the animal's case.

`tests/test_pickup.py` adds 86 tests for the pick-up work and these fixes. The suite was then **278 passed, 11 skipped**.

**One-tap location (committed 12 Nov).** After a photo, a description or a bite report, the request for a location now carries a "Send location" button (D-089). Tested against a stand-in for Meta and clicked through on the simulator by Claude; the suite is now **286 passed, 11 skipped**. Not tried on a real phone.

**Rescue photo and rating (13 Nov).** When a team taps Resolved, each reporter is asked "How did it go?" with Good, OK and Poor buttons, and the team is invited to send a photo of the animal, which is passed to everyone who reported the case (D-091). Migration **0010** adds `rescue_photos` and `case_ratings`. 25 tests in `tests/test_aftercare.py`; the suite is **311 passed, 12 skipped**. Run end to end on the simulator by Claude. Not checked by a person, and not tried on a real phone. `TODO(me)` open: `satisfaction_percent()` in `app/cases/aftercare.py`.

**Dashboard search, filters and view settings (16 Nov, not yet committed).** The cases table has a toolbar (search, state and urgency chips, "Needs a person", area, date range, sort, a count, Clear filters) and the map shows the same filtered cases. Rows have Open, Copy ID and Cancel; cancel asks for a reason in an in-page dialog. A "View settings" panel is saved in the browser only (D-093). A full map key and clear empty states. Only `app/dashboard/page.html` changed; no server change and no new test. Checked by Claude in the browser pane at desktop and phone width; one demo case (PAW-0013) was cancelled in the development data during that check. Not checked by a person. `TODO(me)` open: `compareWaiting()` in `app/dashboard/page.html`, checked with `checkWaitingSort()` in the browser console.

**Audit fixes C1 and C2 (17 Nov, not yet committed).** An independent audit (`docs/AUDIT.md`) found that a reply that could not be sent stopped a case before any team was alerted, and that the dashboard was blank without internet. Now a case is routed and its team alerted before the reporter is told anything, a failed send is logged and skipped, and a job moves on any real case left in REPORTED, TRIAGED or NEW for over 2 minutes (D-094). Leaflet is served by the app and the page works without it (D-095). 17 tests in `tests/test_reliability.py` (the seven send-failure tests fail on the old code); the suite is **356 passed, 13 skipped**. Checked by Claude in the browser pane with Leaflet removed, and with a stuck case on a scratch database picked up by the running server's job. Not checked by a person, and not tried against Meta or a real Telegram bot.

**Telegram channel (16 Nov, not yet committed).** Real WhatsApp was connected but Meta blocks every reply until the business is verified with documents (D-092), so Telegram is now the live channel: `app/channels/telegram.py`, `docs/TELEGRAM_SETUP.md`. 28 tests in `tests/test_telegram.py` against a stand-in for Telegram; the suite is **339 passed, 13 skipped**. **Not yet tried with a real bot**: that needs a token from @BotFather in `.env`. `TODO(me)` open: photos sent as a file, in `_parse_update`.

**Model changed to Haiku (13 Nov).** The default is now `claude-haiku-5-5` (D-090). **First real triage calls made that day:** two calls on a drawn test picture, each about 2,200 input and 400 output tokens, and the model correctly said no real animal was visible. No real animal photo has been triaged yet.

What that run did not cover: the staff cancel button's confirmation box and the phone-width layout (the test browser could not show either), a real photo in the case panel, a cancel sent during a real triage call, and every real service.

## Still to verify by a person (as of 11 Nov)

- **Real Claude triage**: no `ANTHROPIC_API_KEY` has been set, so the live call has never run.
- **Slices 2 to 6 by hand in the simulator**: Ayush has not clicked through them yet. Do this before the Tue 17 Nov checkpoint at the latest.
- **The pick-up features by hand**: STATUS, CANCEL, LANGUAGE, the dashboard case panel, a staff assign and a staff cancel. Claude has run them and they have tests, but no person has clicked through them. In the dashboard, check the staff cancel confirmation box, the panel at phone width, and a real photo in the panel.
- **Konkani, Marathi and Hindi copy**: needs a fluent reader for each language (`docs/TRANSLATIONS.md`).
- **Real Bhashini voice notes**: needs Bhashini keys and ffmpeg (`docs/VOICE_SETUP.md`). Never tried.
- **WhatsApp templates**: need the Meta app, three templates created and approved, and their names in `.env` (`docs/WHATSAPP_SETUP.md`). Never tried.
- **Calendar entry removed when a booking is cancelled**: written from Google's documentation; never run.
- **Real Google Calendar sync**: never run; needs the Google Cloud setup and two calendar IDs in `.env`.
- **The demo, aloud, with a stopwatch**: `docs/DEMO.md` times are estimates. Rehearse three times; cut the bite and BOOK steps first if over.
- **Real WhatsApp end to end**: tried 14 to 16 Nov. Receiving works; sending is blocked by Meta until the business is verified (D-092). Telegram is used instead.
- **Real Telegram end to end**: never run. Follow `docs/TELEGRAM_SETUP.md`; the guide itself is untested until then.
- **Dashboard on the demo machine and network**: the map loads Leaflet and map tiles from the internet. Check it on the venue's connection, and set `DASHBOARD_PASSWORD` before the server is reachable from outside (slice 9).
- **Bite first-aid wording and the health centre list**: Ayush to read the copy in `app/messages.py`; every centre in `seed/health_centres.json` is unconfirmed.

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
- `SpeechToText` interface and stub, then real Bhashini only if Sun 22 Nov has spare hours.

## If we fall behind: cut order

1. Slice 10 voice (already a stretch).
2. Google Calendar sync in slice 7: keep booking in our own table, show the calendar event as "would sync".
3. Slice 9 real WhatsApp: demo on the simulator only, and say so.
4. Slice 6 bite flow: reduce to a static reply with the nearest health centre.
5. Never cut: slices 1 to 5, the dashboard map, the demo script.

## Risks

- **Meta setup delays.** Mitigation: the simulator is the primary demo path from day 1; Meta setup starts Fri 13 Nov.
- **Live vision call fails on stage.** Mitigation: after one retry the case is flagged for a person and carries on at high urgency, so the demo continues (D-059).
- **One-day slices are tight.** Slice 5 has two days, and Tue 17 Nov is a buffer.
