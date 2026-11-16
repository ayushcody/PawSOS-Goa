# Decisions

Newest at the bottom. Each entry: what we chose, why, what we gave up.

## D-001 Simulator is the primary demo path (10 Nov)
The local web simulator and real WhatsApp share one `ChannelAdapter` interface. We build and demo on the simulator first; WhatsApp is plugged in at slice 9.
Why: Meta approval and test-number setup can stall, and stage Wi-Fi can fail.
Gave up: early testing on a real phone.

## D-002 Claude model: `claude-opus-5-5`, set by env var (10 Nov)
**Replaced by D-090: the model is now `claude-haiku-5-5`.**
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

## D-050 Invented numbers go to the simulator, real numbers to WhatsApp (11 Nov)
Every invented number starts with `+91000000`, which no real Indian number does. `RoutedChannel` sends those to the simulator and everything else to WhatsApp. So one demo can mix both: a real phone reports, a placeholder team accepts in the simulator, the update returns to the phone. With WhatsApp off, nothing leaves the machine.
Gave up: a real phone playing a team. Team numbers are seed data, and seed data has no real numbers.

## D-051 The webhook answers Meta at once and works afterwards (11 Nov)
Triage can take several seconds; Meta resends a message if we are slow. We check the signature, return 200, then handle the message in a background task. Message ids already seen are skipped (kept in memory, so a restart forgets them). One person's messages are handled one at a time, so a photo and a location sent together land in the same report.

## D-052 No signature, no entry; half-configured means off (11 Nov)
Every webhook call must carry a valid `X-Hub-Signature-256` made with our app secret. If any of the four WhatsApp settings is missing, WhatsApp stays off and the webhook answers 503. There is no "skip the check in development" switch.

## D-053 The staff password now covers the simulator too (11 Nov)
Once ngrok is running the server is public. Without a password anyone with the address could type into `/sim` as any persona. `DASHBOARD_PASSWORD` protects `/sim` and `/dashboard`; the server warns at startup if WhatsApp is on and it is empty. `/health`, `/media/` and the webhook stay open (Meta must reach them).

## D-054 Phone numbers are masked in logs (11 Nov)
Real numbers now reach the server. Log lines and error messages never contain a full number or the access token.

## D-055 Known WhatsApp limits we accept for the hackathon (11 Nov)
Free-form messages only within 24 hours of the person's last message, so a day-before camp reminder to someone who booked earlier will be refused (we use no templates). Photos go out as a link to `PUBLIC_BASE_URL`, untested on real WhatsApp. The Graph API version is `WHATSAPP_API_VERSION` (default v27.0, the latest on 11 Nov 2026).

## D-056 A reset command for rehearsals, which deletes data on purpose (11 Nov)
`python -m seed.reset` shows what it would delete; with `--yes` it empties every case, report, alert, audit event, bite report and booking, then reloads seed and demo data. Needed because a rehearsal leaves an open case that the next rehearsal's report would merge into. It never runs by itself and prints the row counts first.

## D-057 Reminder timing is configurable for the demo (11 Nov)
`REMINDER_WINDOW_HOURS` (default 24) and `REMINDER_CHECK_SECONDS` (default 300). With 720 and 10, a booking made on stage gets its reminder about ten seconds later. The reminder wording says "coming up", so it stays true in the demo.

## D-058 Citizens see a health centre's name without the `[VERIFY]` tag (11 Nov)
The tag is a note for us and stays in the seed data and the database. The message to the person already says, in plain words, that the list has not been verified and to call ahead.

## D-059 The demo runs on the simulator; a real phone is an optional opening (11 Nov)
The simulator cannot fail on venue Wi-Fi or an expired Meta token. If triage fails on stage, the built-in human-review fallback carries the case forward, so no recorded triage result is replayed.
Gave up: the "replay a recorded triage" idea listed under risks in the plan.

## D-060 Voice notes: the structure first, no real speech service (11 Nov)
`SpeechToText` is the interface. `StubSpeechToText` understands only the simulator's pretend voice notes (you type what was said). `BhashiniSpeechToText` is a marked placeholder that declines everything. `SPEECH_TO_TEXT` picks one: `stub` (default), `bhashini`, or `off`. A real WhatsApp voice note is downloaded, cannot be transcribed, and gets "please type your message".
Still to do for real voice: read Bhashini's current API documentation, write the call, test it against a stand-in.

## D-061 A voice note's words are treated like typed words, and said back first (11 Nov)
We reply "I heard: ..." so the person can correct a wrong transcript. Then the words go through the same paths as text: a bite report, BOOK, a greeting. Anything else is kept as a description on the person's report.
A case still needs a photo and a location: triage reads the photo, and routing needs the place.

## D-062 Audio is never stored (11 Nov)
A voice note is fetched, passed to the speech service once, and dropped. Only the words are kept, on the report. The audit event records the language and length, not the words.

## D-063 The reporter's own words go into the team alert, cleaned first (11 Nov)
Words typed between the photo and the location, and the words of a voice note, are kept on the person's report. The team alert shows them under the photo line as `Reporter says: "…"`, labelled when they came from a voice note. At most three reports' words, 200 characters each, and the whole alert stays within WhatsApp's 1024-character limit for a message with buttons. Reporter text is untrusted: invisible characters and quote marks are removed, links become "[link removed]" and phone numbers "[number removed]", so a team cannot mistake a reporter's words for our own lines.
Gave up: a link or a phone number a reporter meant to share never reaches the team. Typed words count only while a report is waiting for its photo or its location; words typed after the case opens are not added. If one report has both typed and spoken words, they are joined, and the whole note is labelled as a voice note.

## D-064 The CANCEL list lives in the BOOK conversation's row (11 Nov)
CANCEL shows a numbered list of the person's open cases and upcoming bookings. The list is stored in their `booking_drafts` row, with options written as `case:12` or `booking:5`, so no migration was needed. One row per person means a number they type has one meaning at a time: the newest list (camps, slots, or things to cancel) is the one they are answering, and a half-finished BOOK is dropped when CANCEL is sent.
Gave up: a table of its own, which would be cleaner. A person cannot have a BOOK conversation and a CANCEL list open together.

## D-065 Picking a number cancels at once; there is no "are you sure?" (11 Nov)
Replying `2` to the CANCEL list, or sending `CANCEL PAW-0042` or `CANCEL BK-0005`, cancels straight away. A worried person should not have to answer twice, and a wrongly cancelled report can be sent again with a new photo and location.
Gave up: protection against a mistyped number. A cancelled booking's place may be taken by someone else before the person books again.

## D-066 One reporter cannot cancel a case that others also reported (11 Nov)
**Replaced by D-084.**
If another person's report was merged into the case, CANCEL from one of them is refused: the case stays open for the others, the person is told so, and `cancel_refused_shared` is logged. Only a person with a report on the case can cancel it, and the "not found" answer is the same whether the case does not exist or belongs to someone else.
Gave up: a reporter who knows the animal is fine cannot close a shared case. Staff can, from the dashboard (D-072).

## D-067 A reporter can cancel in any open state, and the teams involved are told (11 Nov)
That includes On site: the reporter may know before we do that the animal has gone. Every alert still waiting for an answer is marked "cancelled", so the escalation job stops, and those teams and the team that accepted get a message (`team_stood_down` in the audit log). The cancel goes through the state machine like every other change.
Gave up: teams whose alert had already timed out are not told. A late Accept from them is refused, because the case is closed (D-026 applies only to open cases).

## D-068 A cancelled booking keeps its row, marked "cancelled" (11 Nov)
Its `status` becomes `cancelled` and the place is free again: places left, reminders and the dashboard count only `booked`. No migration was needed. We also try to delete the Google Calendar entry (`delete_event`); if that fails it is logged and the booking is still cancelled, as when creating it (D-036). Replaces "no cancel-a-booking yet" in D-040.
Not yet run against Google: the delete call is written from Google's documentation only.

## D-069 A state change trusts the database, not the copy in memory (11 Nov)
`transition()` now locks the case row and refuses if the state in the database is not the one the caller loaded. So a stale copy cannot bring a closed case back: for example, triage finishing after the reporter cancelled. A merge also locks the case it would merge into; if that case has just closed, the new report becomes a case of its own.
Gave up: one extra locked read per state change. The request that loses the race gets an error instead of carrying on.

## D-070 The case detail panel shows everything except phone numbers (11 Nov)
Tapping a case on the dashboard opens a panel with its photos, the triage result (marked "not a diagnosis"), how many reports and people, the reporters' words, the history of alerts, and the full audit trail in plain words. Reporters appear as "Reporter 1", "Reporter 2". Photos are served by id at `/dashboard/photos/{id}`, behind the staff password, instead of as `/media/` links.
Gave up: staff cannot see who to call back. `/media/` itself stays open, because WhatsApp fetches photos from it (D-048, D-053).

## D-071 Staff assign a team by sending it the normal alert (11 Nov)
"Assign" on the dashboard sends the chosen team the usual alert with Accept and Decline; the team must still accept. Only a case waiting for a team (New, Team alerted, Escalated) can be assigned, and any other team still being asked is stood down. The staff alert is placed after the end of the automatic chain, so if this team declines or does not answer, the case comes back to staff flagged "no team" instead of going round the chain again. An accepted case cannot be reassigned; staff cancel it instead.
Gave up: staff cannot force a team to take a case, or move a case away from a team that has accepted.

## D-072 Staff cancel with a reason that stays in the audit log (11 Nov)
Cancelling from the dashboard needs a short reason. It is kept in the audit log, for staff only. Reporters get a calm, general message (closed by PawSOS staff; send a new photo and location if the animal still needs help), because a note written for colleagues may not suit them. Teams that were alerted or had accepted are told.
Gave up: with one shared staff password, the audit log says "Staff", not which person.

## D-073 Staff actions refuse requests from other websites (11 Nov)
The browser re-sends the dashboard password by itself, so another website could make a staff member's browser assign or cancel a case. The two staff actions refuse a request whose `Sec-Fetch-Site` or `Origin` header shows it came from somewhere other than the dashboard.
Gave up: this is a header check, not a full anti-forgery token. A tool that sends neither header (such as `curl` with the password) is let through, which suits scripts.

## D-074 Response times come from the audit log: median and 90th percentile (11 Nov)
The dashboard shows report to accepted, and accepted to resolved, overall and per zone. "Report" is the `case_created` event (or the case's creation time); "accepted" and "resolved" are the first moves to those states. It covers the same cases as the case list: the last 30 days, merged duplicates left out. The 90th percentile uses linear interpolation. Only cases that reached a step count for it.
Gave up: cases still waiting are left out, so while many cases are open the figures look better than the truth; the page says they are left out. Demo cases are included, and the demo seed spaces each step two minutes apart, so with demo data loaded the figures are invented.

## D-075 WhatsApp templates are a one-time fallback, for three messages (11 Nov)
Every message is sent free-form first. If Meta refuses it with error 131047 (the 24-hour window is closed), it is sent once more as its approved template, if one is configured: team alerts, "no answer in time" notices, and camp reminders. Meta can also report the refusal later, in a status webhook; for that we remember up to 1000 recent messages, in memory. A template alert carries no photo, and the photo line and the reporter's words go on one line of at most 600 characters. Template names come from the `WHATSAPP_TEMPLATE_*` settings, in one language (`WHATSAPP_TEMPLATE_LANGUAGE`). Replaces "we use no templates" in D-055.
Gave up: a message refused later is lost if the server restarted in between. Every other message outside the window is still refused. Not yet tried against Meta: no template has been created, approved or sent.

## D-076 Each number's language is remembered, and changed with LANGUAGE (11 Nov)
A new `contacts` table (migration 0008) holds one language per phone number. `LANGUAGE` or `भाषा` opens a menu (1 English, 2 कोंकणी, 3 मराठी, 4 हिंदी) that stays open for 15 minutes. As soon as BOOK, STATUS or CANCEL answers a message, the menu closes, so a number means one thing. A voice note heard as Konkani, Marathi or Hindi sets the language only if the person never chose one, and never switches anyone to English. Rescue teams are always written to in English. The rehearsal reset clears this table.
Gave up: typed text is not checked for its language, so a person writing in Hindi gets English until they send LANGUAGE.

## D-077 Konkani, Marathi and Hindi copy is machine-drafted and says "we" (11 Nov)
Every translation in the `KOK`, `MR` and `HI` tables of `app/messages.py` was drafted by Claude. The bot says "we" where "I" would need a gendered verb. A missing translation falls back to English. Each text must be checked by a fluent reader before real use; `docs/TRANSLATIONS.md` is the checklist.
Gave up: nothing has been checked by a person yet. Until then the translations are demo copy.

## D-078 Real voice notes go to Bhashini through ffmpeg, Konkani by default (11 Nov)
`BhashiniSpeechToText` makes Bhashini's two calls: a config call (which speech model serves each language, kept for 6 hours) and a compute call (the config is fetched once more if Bhashini refuses the key with 401 or 403). The first speech model listed for a language is used. WhatsApp sends OGG/Opus, which Bhashini does not list, so `ffmpeg` (a system program, not a Python package) turns it into 16 kHz mono WAV in memory. ffmpeg may read only audio container formats, and only from the pipe, so a crafted file cannot make it open other files or fetch addresses. WhatsApp gives no hint of the language, so `BHASHINI_DEFAULT_LANGUAGE` (default `kok`) is assumed; the read-back (D-061) lets people correct a wrong transcript. Clips are cut at 120 seconds, and ones over 30 seconds ask Bhashini to split on silence. The default pipeline id is in the code. The simulator's pretend voice notes still use the stand-in. Replaces the placeholder in D-060.
Gave up: a Marathi or Hindi voice note is first heard as Konkani unless the default is changed. Not yet tried with real Bhashini keys or a real voice note.

## D-079 No temporary case ID when an open case is nearby (11 Nov)
Before telling a new reporter their case ID, a cheap check looks for any case within the dedup radius and time window, by place only (open cases, and ones still being triaged). If there is one, the person gets "your report is in, we are checking whether someone has already reported this animal" with no ID; triage and routing run first, and they then get either the earlier case's ID (merged) or their own (`case_created`). With nothing nearby, nothing changes. Fixes the rough edge noted in D-020.
Gave up: a different animal nearby also triggers the check, so that person gets their ID a few seconds later. A case created just after the check can still cause the old behaviour; closing that needs a lock. After a merge the first-aid reply carries the earlier case's ID but this person's own urgency reading. If something fails between the acknowledgement and routing, the person never gets an ID (the case is still saved and on the dashboard).

## D-080 A team chosen by staff that declines or times out hands the case back to staff (11 Nov)
An alert at or past the end of the automatic chain was sent by staff (D-071). When that team declines or does not answer, the team is told the case has gone back to PawSOS staff, and the reporter is told that team could not take it and staff are finding another. The case state and the "no team" flag are unchanged.
Gave up: the staff variant has no WhatsApp template, so outside the 24-hour window the team does not get the expiry notice. The last automatic team in a chain still hears "passed to the next team" although nobody follows; left alone so slice 5 is unchanged.

## D-081 First-aid steps are written in the reporter's language (11 Nov)
Triage passes the reporter's saved language to the model, which is asked to write `first_aid` in it. Species, urgency, aggression risk and `injury_type` stay in English, because the schema checks them and teams read `injury_type`. The no-diagnosis rule applies in every language. English keeps the old call, so the test stand-ins still work.
Gave up: `case.first_aid` is stored in that language, so the dashboard shows it in Konkani, Marathi or Hindi. Not tried against the real model; Devanagari steps may run past the 200-character limit per step, which leads to the retry and then human review.

## D-082 A WhatsApp voice note is heard in the person's saved language, and never changes it (11 Nov)
WhatsApp does not say which language a voice note is in. Bhashini is asked to listen in the person's saved language if they have one, otherwise in `BHASHINI_DEFAULT_LANGUAGE`. That language is an assumption, not a detection, so it is never saved for the person. Without this, any first voice note would have switched the sender to Konkani for good. Amends D-076: on WhatsApp, a language is now saved only through LANGUAGE.
Gave up: a person who has never chosen a language is still heard as Konkani first.

## D-083 When a case moves on mid-flow, the newer change wins quietly; locks go case first (11 Nov)
If a reporter or staff cancel or assign a case while its photo is still being triaged or routed, the state machine refuses the stale step (D-069). The report flow now catches that, rolls back its unfinished part and stops, instead of failing the request. The escalation timer now locks the case before the alert, like button taps, cancels and staff actions, so two of them can never wait on each other forever; a case someone is handling is left for the timer's next tick.
Gave up: a reporter whose case is cancelled during the duplicate check never gets a case ID, which is fine because the case is closed.

## D-084 CANCEL on a shared case withdraws that reporter; the last one to cancel closes it (11 Nov)
Replaces D-066. The first run showed that when every reporter of a merged case sent CANCEL, each was told it "stays open for them", the team stayed alerted and everyone kept getting updates. Now CANCEL on a shared case marks that person's reports as withdrawn (`reports.withdrawn_at`, migration 0009) and logs `report_withdrawn`: they get no more updates and the case leaves their STATUS. `reporters_of` leaves withdrawn reports out, so when the last remaining reporter cancels, the case is cancelled as usual. A person who withdrew and reports the animal again has a new report and is back on the list.
Gave up: a new column and migration. The dashboard's report count still includes withdrawn reports.

## D-085 Bare links in reporter words: remove the known endings in any case, and split the rest (11 Nov)
`EVIL.COM` got through because the list of web endings was matched in lower case only; it is now matched in any case. Endings that are also everyday words (`pay.in`, `bad.me`) cannot be removed without eating sentences typed with no space after a full stop ("market.It is bleeding"). So any full stop left with a letter on both sides gets a space after it: the words stay, and no phone turns them into a link.
Gave up: "pay. in" looks slightly odd. A capitalised word after a missing space that happens to be a web ending ("shop.Live wire") is now removed as a link.

## D-086 A typed or spoken description gets its own thank-you (11 Nov)
After a photo, a typed description was answered with "photo received, now share the location" a second time, as if the words had been ignored. New keys `note_ask_location` and `note_ask_photo` thank the person for the description and ask for what is still missing.
Gave up: two more keys to translate.

## D-087 Dates and area names follow the reader's language (11 Nov)
Translated replies carried "Wed 11 Nov" and "Mapusa" in English. `app/messages.py` now has weekday, month and place-name tables per language, used by `format_date` and wherever an area is named to a citizen. Team alerts stay in English. All of it is machine-drafted and listed in `docs/TRANSLATIONS.md`.
Gave up: camp names, venues and services are seed data and stay in English; the time range stays as it is because `format_time_range` is Ayush's `TODO(me)`.

## D-088 One location answers a bite report and a waiting photo (11 Nov)
A person who had said they were bitten, then sent a photo of the animal and a location, got only the nearest health centre: the photo stayed waiting. Now, when a photo is waiting, the same location also completes the animal's report. With no photo waiting, the behaviour is unchanged (the location is the person's, and no case is opened).
Gave up: the animal's case uses the person's location, which may be some way from the animal if they have already moved.

## D-089 After a photo, ask for the location with WhatsApp's "Send location" button (11 Nov)
WhatsApp cannot carry a photo and a location in one message. To make the second step one tap, the three messages that ask for a location (after a photo, after a description, and after a bite report) are sent as Meta's location request message: the same words with a Send location button. The answer arrives as an ordinary location message, so nothing else changes. The simulator shows the same button, which opens its place picker. Checked against Meta's documentation on 11 Nov 2026. If Meta refuses the button, the words alone are sent.
Gave up: the words still say "tap attach, then Location", which stays true but does not mention the button; rewording needs three more translations checked. Not yet tried on a real phone.

## D-090 The model is `claude-haiku-5-5`, not an Opus model (13 Nov)
Ayush's decision, on cost: Haiku 5.5 is priced at $0.10 per million input tokens and $0.50 per million output tokens (prompts up to 100K tokens), against $4 and $20 for Opus 5.5. It accepts image input and structured output, and the triage call needed no code change: it sets no thinking, sampling or tool-choice options that Haiku 5.5 refuses. The default in `app/config.py`, `.env.example` and the docs is changed; `ANTHROPIC_MODEL` still overrides it.
Gave up: a smaller model may read hard photos less well. That is to be measured on real photos, not assumed.

## D-091 After Resolved: a three-button rating, and the team's photo passed to reporters (13 Nov)
The loop closed with a line of text. Now each reporter is asked how it went with three reply buttons (Good, OK, Poor: WhatsApp allows three), one rating per person per case, changeable by tapping again. The team is invited to send one photo of the animal within 30 minutes of resolving; it is stored in `rescue_photos` and sent to every reporter with a caption. A photo from a team outside that window, or a second photo, is an ordinary report as before. Ratings are shown on the dashboard as counts only, never by person. Both are in a new module, `app/cases/aftercare.py`, and neither changes a case's state.
Gave up: a team cannot send the photo before tapping Resolved, or more than one. The 30-minute window is measured on the database's clock, so tests age the audit event to try it. A rating is not asked for when staff or the reporter cancel a case.

## D-092 Telegram is the live channel for the demo; WhatsApp stays in the code (16 Nov)
Real WhatsApp was set up on 14 to 16 Nov: token, app secret, webhook and incoming messages all worked. Replies did not. Meta's WhatsApp Manager says "Account restricted. Before you can begin messaging, you will need to verify your business", and every reply failed with error 131031. Verification needs registered-business documents, which the team does not have, and there is no test-mode way round it. A Telegram bot needs no verification, payment or public address, and offers what we use: photos, a one-tap location button (`request_location`), inline reply buttons and voice notes.
How: `app/channels/telegram.py`, switched on with `CHANNEL=telegram` and `TELEGRAM_BOT_TOKEN`. Messages are fetched by long polling (`getUpdates`) from one background task, so no webhook or tunnel is needed. A Telegram person is stored as `tg:<chat id>` where a phone number is expected (it fits the 20-character columns, so no migration). `RoutedChannel` sends `tg:` addresses to Telegram and never to WhatsApp.
The bot token is part of every Telegram address and httpx names the address in its errors, so those errors are replaced before they are raised or logged; two tests check the token never appears.
Gave up: the pitch says "one WhatsApp number", and the demo will show Telegram; say plainly that WhatsApp is built and blocked only by Meta's business verification. Teams are still the simulator's placeholders; a real team phone on Telegram is not built. Photos sent "as a file" are not accepted yet. Polling means one server per bot. Not yet tried with a real bot.

## D-093 The dashboard finds and filters cases in the browser, with view settings kept in the browser (16 Nov)
Why: an admin could not search for a case, see only critical or unassigned ones, sort the list, or tell what each map marker meant; cancel used the browser's `confirm()`, which cannot be tested in the browser pane.
What: `app/dashboard/page.html` only; no server change, because `/dashboard/data` already returned every field. A toolbar above the table (search by case ID, area or species; state and urgency chips; "Needs a person"; area; date range; sort, also by clicking column headers; a count such as "8 of 45 cases"; Clear filters). The same filtered cases are drawn on the map. Each row has Open, Copy ID and Cancel; cancel asks for a reason in an in-page `<dialog>` and uses the existing `/cancel` endpoint, so the state machine is untouched. A "View settings" panel (sections shown, table density, columns, auto-refresh with Refresh now, filters when the page opens, Reset to defaults) is saved in `localStorage` under `pawsos.dashboard.view.v1`, read and written inside try/catch and checked value by value. A full map key and two empty states ("no cases match" and "no cases in 30 days").
Choices made: the state chip for cases with no team yet says "Waiting for a team", not "Open", because the status sentence already uses "open" for every unfinished case. Area is a drop-down, not chips: 14 areas would bury the toolbar. Auto-refresh defaults to 30 seconds (it was a fixed 15). The page now downloads all cases once and never sends filters to the server; the `status`, `urgency` and `zone` parameters of `/dashboard/data` still work and are still tested, but the page no longer uses them.
Gave up: no accounts, no server-side preferences, no saved named views, no bulk actions, no export, no "assign" from the row (it needs the team list, which only the case panel loads). "Any time" equals "Last 30 days" because the server only loads 30 days. Bite reports and camps are not filtered. The page has no automated test; it was checked by hand in the browser pane (each filter, sort and setting, a reload, Reset, the cancel dialog by keyboard, phone width, blocked storage).

## D-094 A message that cannot be sent never stops a case; stalled cases are moved on by a job (17 Nov)
Why: the audit (`docs/AUDIT.md`, C1) found that the reporter was told "case created", the triage result and the area *before* the team was alerted, and a failed send raised out of the flow. The case stayed in REPORTED, TRIAGED or NEW for ever, with no team alerted and no flag on the dashboard. With Meta refusing every reply (D-092) that was every real WhatsApp report. A server stop during triage did the same.
What: in `app/conversation.py` every message to a citizen goes through `deliver()`, which logs a failed send and carries on. A new case is triaged, routed and its team alert saved and sent **before** anything about it is sent to the reporter; the reporter's messages keep their order. `app/cases/recovery.py` adds a job (every 30 seconds) that finds real cases that have sat in REPORTED, TRIAGED or NEW for more than 2 minutes, by database time: one still waiting for triage goes on at high urgency, flagged for review (as when the model is unavailable), then it is merged or routed, a team is alerted, and the reporter gets the case ID again. The dashboard flags such a case "No team has been alerted yet" (`not_routed`). Demo cases are never touched.
Choices made: 2 minutes, because a normal triage call is well under the model's 60-second timeout; if the job takes over a case whose triage is still running, the state machine refuses the late result and the flow stops quietly (tested). A NEW case with no area (no zones loaded) is left for staff rather than retried every 30 seconds.
Gave up: a message lost before its case was saved (a photo whose download failed, a draft never completed) is not recovered. The model's timeout and retries are unchanged (audit H2), so a very slow model call can still be taken over by the job.

## D-095 Leaflet is served by the app, and the dashboard works without it (17 Nov)
Why: the audit (C2) found that with no internet the whole dashboard stayed on "Loading…", because Leaflet came from unpkg.com and the page's only script stopped at `L.map(...)`. DEMO.md said the opposite.
What: Leaflet 1.9.4 (`leaflet.js`, `leaflet.css`, its control images and BSD licence) is in `app/static/leaflet`, served at `/static`, byte-identical to the CDN copy (the page keeps the same integrity hashes). The map is set up only when Leaflet loaded; otherwise the map box says "The map could not load" and every list, figure and the case panel still work. Map tiles still come from OpenStreetMap, so they need a connection; without one the markers are drawn on a blank background.
Gave up: no offline tiles.

## Open
- Nothing right now.
