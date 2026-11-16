# PawSOS Goa: independent audit

Audited Tue 17 Nov 2026 on `main` (commit `97b74e4`) plus the uncommitted Telegram and dashboard work in the working tree. No code was changed for the audit.

**Update, 17 Nov, later the same day: C1 and C2 are fixed** (D-094, D-095, `tests/test_reliability.py`; suite 356 passed, 13 skipped). The fix for C1 also covers the "case saved, never routed" half of H1, and M6's missing test. Everything else below is still open. The findings are left as written, so the evidence still matches what was found.

## 1. Summary

- **Verdict:** the happy path is solid. On the simulator, report, merge, timeout escalation, accept, on site, resolved, bite and BOOK all worked first time. The test suite passes (339 passed, 13 skipped). The weak spots are failure paths, and none of them has been tried against a real service.
- **Single biggest risk (C1):** if any message to the reporter fails to send, the case is saved but never triaged, routed or alerted. Nothing retries it and the dashboard does not flag it. Meta currently refuses every reply (D-092), so every real WhatsApp report today ends up stuck at `REPORTED`.
- **Second risk (C2):** without internet access to unpkg.com, the whole dashboard stays on "Loading…", not just the map. `docs/DEMO.md` says the opposite.
- **Not yet proven:** a real animal photo through the real model, a real Telegram bot, Google Calendar, Bhashini, and a timed rehearsal by a person.
- **Today is the 17 Nov freeze.** Most of the top 10 in section 5 are under an hour each. C1 and C2 should be fixed before any rehearsal.

## How this was checked

- I read every file in `app/`, `seed/`, `migrations/` and `tests/`, plus the docs.
- `.venv/bin/pytest -q`: with Docker stopped, **339 errors**, because every test needs the database, even pure unit tests. With Docker running, **339 passed, 13 skipped** in 37 s. `ruff check .` is clean.
- I wrote 9 reproduction tests in a scratch folder outside the repository, reusing `tests/conftest.py`. All 9 pass, so each one confirms the current behaviour described below. The key one is in the appendix.
- I ran the server on a separate scratch database (`pawsos_audit`, now dropped) with the DEMO.md settings and no API key, then ran the DEMO.md core script through the simulator's endpoints and opened the dashboard. Your development database was not touched.

**Verified** means I reproduced it (test or live run). **Suspected** means from reading only.

## 2. Findings

| ID | Sev | Area | Finding | Evidence | V/S | Suggested fix | Effort |
|---|---|---|---|---|---|---|---|
| C1 | Critical | Reliability | A failed send to the reporter stops the case flow. `case_created` is sent before triage (`conversation.py:187`), the triage text before routing (`:240`), and `zone_assigned` before team dispatch (`:271`). If any of these raises, the exception escapes. The case is already committed, so it stays `REPORTED`, `TRIAGED` or `NEW` with no team alerted. No job looks for stuck cases, and the dashboard's `_attention()` (`queries.py:95`) does not flag them. The WhatsApp and Telegram handlers swallow the error and only log it (`whatsapp.py:540`, `telegram.py:389`). | Scratch tests `test_failed_reply_send_leaves_case_unrouted_forever` and `…_triaged_unrouted`: state stays `REPORTED`/`TRIAGED`, 0 dispatches, the timer job does nothing, `attention` is null. With Meta blocking replies (D-092), this is every real WhatsApp report. | Verified | Send citizen messages through `deliver()`, which swallows errors per message. Route and dispatch **before** telling the citizen. Add a scheduler job that pushes any case left in `REPORTED`/`TRIAGED`/`NEW` for more than 2 minutes through triage fallback and routing. Flag those cases in `_attention`. | S–M |
| C2 | Critical | Demo | The dashboard depends entirely on Leaflet from unpkg. `L.map(...)` at `page.html:584` runs at the top level of the only script. If `L` is undefined, the script stops, so the case list, "Need a person", the suggestion card and the counts all stay "Loading…". DEMO.md's fallback row ("the rest of the dashboard does not [need a connection]") is false. | Loaded the page with the Leaflet URL pointed at an unreachable host: `ReferenceError: L is not defined`, and every panel stayed on "Loading…". | Verified | Copy `leaflet.js`/`leaflet.css` into the repo and serve them locally. Also wrap the map setup in `if (window.L)` so the lists still render if it fails. Tiles will still need internet. | S |
| H1 | High | Reliability | A message can be lost on restart or crash. WhatsApp answers 200 and then processes in `BackgroundTasks` (`whatsapp.py:581`). Telegram's next `getUpdates` runs as soon as the tasks are started and confirms them (`telegram.py:409`, `:296`). If the process dies during triage, that message is gone, or its case is stuck as in C1. The `_SeenIds` dedup is held in memory only (`whatsapp.py:451`). | Read only. | Suspected | The stuck-case sweeper from C1 covers the "case saved, not routed" half. Accept losing a half-sent draft for the hackathon. | S (with C1) |
| H2 | High | AI triage | Triage can hold up the team alert for minutes. Routing waits for triage. The client is `timeout=60.0` with the SDK's default retries (`service.py:114`), so a slow or unreachable API can delay the first alert by about 3 minutes. That contradicts "triage must never block a rescue" (`triage/flow.py:3`). | Read only. Triage latency on a real photo has never been measured. | Suspected | `timeout=15, max_retries=1`. Better still, route on fallback urgency first and update the urgency when triage returns. | S |
| H3 | High | Demo / AI | Without `ANTHROPIC_API_KEY`, the 0:35 beat in DEMO.md has nothing to point at. Every case says "a team member will look at your photo", urgency is always HIGH, and there are no first-aid steps. Only two real calls have ever been made, on a drawn test picture (PLAN.md, 13 Nov). | Live run: every reply was `triage_needs_review`; the team alert said "The photo has not been assessed". | Verified | Put a key in `.env`. Run 5 real animal photos, record urgency and latency, and keep two good photos for the demo. | S |
| H4 | High | Location | `in_goa()` returns `True` for everything (`geo.py:31`). A pin in Mumbai becomes a case "in the Pernem area" and the Pernem team is alerted. | Scratch test `test_mumbai_location_opens_a_goa_case`: reply "Case PAW-0001 is in the Pernem area. We are alerting a rescue team now." | Verified | This is Ayush's `TODO(me)` (bounding box, about 5 lines; the tests already exist). | S |
| H5 | High | Bite flow | A bite word sends an animal emergency down the human bite flow. "A dog has been bitten by another dog and is bleeding on the road" gets wound-washing advice, and the next location returns a health centre. No rescue case is opened. The last line ("If the animal is still nearby, send its photo…") partly recovers it. | Scratch test `test_animal_bitten_text_goes_to_human_bite_flow`; `bites.py:32-37`; `conversation.py:144`. | Verified | Count it as a human bite only for first-person or person wording ("bit me", "I was bitten", "bit my son"). For bare "bitten", ask with two buttons: "Were you bitten?" / "An animal is hurt". | S |
| H6 | High | Demo | DEMO.md's 20-second timeout applies to every team. In the live run, Mormugao also timed out while the presenter would still be talking. The reporters then got the **same** "the first team could not take it" message twice (wrong the second time), and the taluka officer was alerted. Accepting late still works, so the demo recovers, but the screen looks messy. | Live run, case PAW-0041: two identical `citizen_escalated` lines; officer alerted, then "taken by another team". | Verified | Demo timeout of 30–40 s. Use a second message key ("we have alerted another team") from the second escalation on. | S |
| H7 | High | Security | `/sim` and `/dashboard` are open when `DASHBOARD_PASSWORD` is empty, which is the default; there is only a log warning (`whatsapp.py:438`). `/sim/inbound` accepts any `from_number`. Anyone who can reach the server can tap Accept as any team, make the bot message any real WhatsApp number or `tg:` chat id, and read any transcript through `/sim/messages?phone=`. This matters once ngrok is used. Telegram polling needs no public URL, so the Telegram path is safe by default. | Scratch test `test_sim_lets_anyone_act_as_a_team` (state → `ACCEPTED`); `simulator.py:146-158, 205-207`. | Verified | Refuse to start when `CHANNEL` is not `simulator` and the password is empty. When a real channel is on, reject `/sim` numbers that do not start with `+91000000`. | S |
| M1 | Medium | Dedup | "Similar animal" is loose. With no API key, `species` is always None, so **any** two reports within 200 m and 2 hours merge (a cat into a dog). With a key, an "unclear" result merges into anything. Two reports triaged at the same moment can also miss each other, or the older case can merge into the newer one, because `find_duplicate` only considers routed states (`dedup.py:59` vs `:72`). | Scratch tests `test_no_api_key_any_two_animals_within_200m_merge` and `test_cat_after_unknown_species_merges`. The race is from reading only. | Verified / race Suspected | Fine for the demo. After the hackathon, merge on unknown species only when the distance is under 50 m. | M |
| M2 | Medium | Routing | When the chain is exhausted the case sits in `ESCALATED` with no pending alert. Only the dashboard "no team" flag remains: nothing retries, and staff get no message. | `dispatch.py:305-313`; seeded demo cases PAW-0028/0030 show "No team has taken this case". | Verified | Fine for the demo. Later, alert the taluka officer again on a timer. | S |
| M3 | Medium | AI safety | The first-aid steps reach the citizen unchecked. Only the prompt forbids "touch, lift, feed". Nothing in `TriageResult` (`schema.py:41`) rejects such a step, and non-English steps cannot be keyword-checked at all. The text that photo-injection could change is `first_aid`, which goes only to the sender, and `injury_type` (160 characters), which goes to the team. Routing never depends on urgency, so prompt injection cannot stop a case reaching a team. | Read only. | Suspected | Keep the model's urgency and species. Send fixed, reviewed first-aid steps from `messages.py`, chosen by urgency and aggression and already translated. Or at least add an English denylist in the validator that falls back to the fixed steps. | S |
| M4 | Medium | Privacy | Full phone numbers are kept indefinitely in `events.actor` next to exact coordinates (`intake.py:62-68`), and in `reports`, `contacts`, `bookings` and `bite_reports`. There is no retention rule. Photos are served at `/media/{name}` without the password (`main.py:63`); the names are random, but anyone with a link can open the photo. The dashboard and case detail never show a number. | Scratch test `test_dashboard_data_has_no_phone_numbers` passes. Storage is from reading. | Verified (dashboard) / Suspected (rest) | For the demo: one sentence in ARCHITECTURE.md on what is kept. Later: a retention job, and hash the numbers kept in `events.actor`. | S |
| M5 | Medium | Booking | Times are correct in Asia/Kolkata. But the reminder fires whenever a slot is within the next 24 hours (`flow.py:383-399`), not "the day before": a booking made 3 hours ahead is reminded at once, at any hour. `_book` does not re-check that the slot is still in the future (`flow.py:251`). Double booking is prevented by the conversation flow, not by a database constraint. | Live run (720 h window): reminder about 10 s after booking, as configured. | Verified | Fine for the demo. Later: skip the reminder for bookings made inside the window, and add quiet hours. | S |
| M6 | Medium | Tests | `test_one_refused_message_does_not_stop_the_conversation` (`test_slice9.py:207`) only checks that Meta gets a 200, so it passes with C1 present. There is no test for a send failure in the middle of a case, for the dashboard without Leaflet, or for restart recovery. Every test, even pure functions, needs Postgres, because the autouse session fixture fails the run. | Test read; 339 errors with Docker stopped. | Verified | Add the appendix test (inverted) when fixing C1. Optionally mark DB-free tests so they run without Docker. | S |
| M7 | Medium | Voice | `ffmpeg` runs through blocking `subprocess.run` inside the async path (`speech.py:213`). Each real voice note freezes the whole server for up to the ffmpeg timeout. This only happens with `SPEECH_TO_TEXT=bhashini`. | Read only. | Suspected | Use `asyncio.to_thread(...)`. | S |
| L1 | Low | Demo | `GET /` returns 404 "Not Found". A judge who types the base URL sees an error. | Server log during the run. | Verified | Redirect `/` to `/dashboard`. | S |
| L2 | Low | Routing | The team alert is not updated after a merge or an urgency raise. Panaji still shows "Reports so far: 1" after the second report. | Live run. | Verified | Leave as is. | – |
| L3 | Low | Aftercare | A team's rescue photo is forwarded to every reporter unseen (`aftercare.py:174-181`). It could be graphic. | Read only. | Suspected | Leave it for the demo, or send a link the reporter chooses to open. | S |
| L4 | Low | Spec | The spec says "live location". WhatsApp Cloud API live-location shares are likely to arrive as unsupported and get "can't read that". Telegram live locations do arrive as `location`. | Read only. | Suspected | Test it on a phone. Mention "share current location" in the copy. | S |
| L5 | Low | Intake | A location sent more than 30 minutes after the photo starts a new draft, and the bot asks for the photo again (`intake.py:19`). | Read only. | Suspected | Leave as is. | – |

Checked and fine (Verified unless marked):
- Accepting a resolved case is refused ("taken by another team").
- A failed or absent triage still routes the case at HIGH and flags it "needs review".
- Escalation deadlines live in `dispatches.expires_at`, so a restart does not lose a timer (from reading).
- Every team is closed at 23:00, but taluka officers have no hours, so a case still reaches someone.
- `X-Hub-Signature-256` uses HMAC with `compare_digest`, and a missing secret means nothing passes (existing tests).
- The verify token is compared in constant time.
- No secrets in git history (pattern scan for Anthropic, Meta, Google and Telegram tokens and private keys).
- No real-looking `+91` numbers in the repository.
- Media is checked for type, magic bytes and a 10 MB limit; WhatsApp media ids are checked by regex; Telegram file paths are checked against `..`.

## 3. Spec coverage

| Spec item | Status | Notes |
|---|---|---|
| 1 Report: photo and location | Built | In either order, with a 30-minute draft. |
| 1 Report: live location | Partly | A pin works; WhatsApp live location is unproven (L4). |
| 1 Report: voice note in Konkani, Marathi, Hindi or English | Partly | Simulator stand-in only. Bhashini is written but never run (M7). Konkani availability is unknown. |
| 2 Triage (species, injury, urgency, aggression, 2–3 steps, no diagnosis) | Built, barely proven | Never run on a real animal photo (H3). Output safety rests on the prompt only (M3). |
| 3 Dedup (200 m, 2 h, similar animal, all reporters told) | Built | Looser than "similar" (M1). |
| 4 Route by municipality or ward | Built differently | Nearest of 14 approximate circles. No wards. Any location is accepted (H4). |
| 4 Alert on WhatsApp with Accept / Decline | Built differently | Teams are simulator placeholders. Real WhatsApp sending is blocked by Meta; Telegram is the live citizen channel. |
| 4 Escalate on closed team or 10 minutes to next team, then taluka officer | Built | Overnight hours are wrong (TODO); hidden by `IGNORE_OPENING_HOURS` in the demo. |
| 5 Close the loop (accepted, on site, resolved, with case ID) | Built | Wrong wording on the second escalation (H6). |
| 6 Bite flow (nearest centre, hotspot flag) | Built | Over-triggers on animal bites (H5). Centres unverified. |
| 7 BOOK a camp slot | Built | |
| 7 Google Calendar sync | Built, never run | |
| 7 Reminder the day before | Built differently | "Within 24 hours", sent once (M5). |
| 8 Dashboard (map, list, filters, sterilisation counts, next-camp suggestion) | Built | Fails completely offline (C2). |
| Lifecycle: all 10 states, transitions table, audit event per change | Built | Code also allows `ESCALATED → ACCEPTED`, which the diagram does not show; that is sensible. `case_created` is written directly, not through `transition()`, which is acceptable for the initial state. States can still get stuck (C1, M2). |
| Data on Supabase | Built differently | Local Docker Postgres with PostGIS. Supabase never set up. |
| Deliverable: working demo on WhatsApp | Missing | Replaced by Telegram (D-092), which has never been run with a real bot. |
| Deliverables: tests passing, README, DEMO, ARCHITECTURE | Built | Tests need Docker. DEMO fallback table is wrong (C2). |

**Built but not in the spec:** STATUS and CANCEL; LANGUAGE and Konkani, Marathi and Hindi copy; reporter words in team alerts; staff assign and cancel; response-time figures; ratings and rescue photos; WhatsApp templates; the Telegram channel; dashboard filters and view settings.

That is a lot of scope added while the protected slices 1 to 5 have never been run by a person. None of it is broken in a way I found, but each item adds demo surface. Keep it out of the core 3 minutes.

## 4. Where I disagree with HANDOFF.md

HANDOFF.md is stale and contradicts itself:
- It says 311 tests pass in "Where things stand" and 339 in setup.
- Rows 15 to 18 say "written, not run", but PLAN.md says they were run and tested.
- It says "no real triage call", but PLAN.md records two on 13 Nov.
- It has no row for Telegram, which is now the live channel.

| # | Part | HANDOFF | Mine | Why |
|---|---|---|---|---|
| 1 | Report | 80% | 65% | `in_goa` is a no-op (H4), and a send failure strands the case (C1). |
| 2 | Triage | 65% | 55% | Two calls on a drawn picture are not a real run. Latency is unmeasured (H2) and first-aid output is unchecked (M3). |
| 4 | Routing and escalation | 80% | 65% | Dispatch depends on a reporter send succeeding (C1). Overnight hours are wrong. |
| 8 | Dashboard | 85% | 65% | The whole page is blank without unpkg (C2), and stuck cases are not flagged. |
| 9 | Real WhatsApp | 60% | 25% | Receiving works, sending is blocked, and because of C1 every inbound real report gets stuck. |
| – | Telegram (missing row) | – | 50% | Code and 28 tests against a stand-in, never run with a real bot, and C1 applies to it. |
| 12 | Demo script | 75% | 55% | Fallback table wrong (C2), the 0:35 beat needs a key (H3), 20-second timeouts on every team (H6), never timed aloud, and the "optional opening on a real phone" is WhatsApp, which cannot send. |
| 6 | Bite flow | 70% | 60% | Over-triggers (H5). |

I agree with HANDOFF's overall "about 15% verified for real" figure, and with its rule that "tests pass" and "a person tried it" are different claims.

## 5. Top 10 to fix before the 17 Nov feature freeze (in order, each a day or less)

1. **C1:** route and dispatch before telling the reporter, send through `deliver()`, add a stuck-case sweeper, and flag stuck cases in `_attention`. Add the inverted appendix test.
2. **C2:** serve Leaflet locally, guard with `if (window.L)`, and correct DEMO.md's fallback row.
3. **H3 + H2:** set a real key, triage 5 real photos, record latency, and set `timeout=15, max_retries=1`.
4. **H6:** set the demo timeout to 30–40 s and add a "next team" escalation message so the second escalation reads correctly.
5. **H7:** refuse to start with a real channel and no password, and restrict `/sim` numbers when a real channel is on.
6. **H5:** tighten bite detection to first-person wording, or ask with two buttons.
7. **H4:** Ayush's `in_goa()` TODO (5 lines, tests ready).
8. **M3:** use fixed, reviewed first-aid steps, or at least a denylist fallback.
9. **L1:** redirect `/` to `/dashboard`.
10. Bring HANDOFF.md and README's status table in line with PLAN.md, and add Telegram. Point DEMO.md's "real phone" opening at Telegram, not WhatsApp.

## 6. Things that need you, by hand

- **Rehearse the core script aloud three times with a stopwatch**, after fixes 1 to 4. Nobody has timed it.
- **Create a real Telegram bot** and run `docs/TELEGRAM_SETUP.md` end to end from your phone: photo, location button, STATUS. The guide itself is untested.
- **Run real triage** on your own animal photos and read every first-aid line yourself. Decide whether you trust free-text steps from the model, or want the fixed ones (M3).
- **Check the venue network** for unpkg.com and tile.openstreetmap.org. Take a screenshot of the dashboard as a last-resort slide.
- **Start Docker before the demo.** Without it the server cannot store anything and the tests all error.
- **Set `DASHBOARD_PASSWORD`** before anything is reachable from outside your laptop.
- **Decide what to say about WhatsApp.** Meta business verification is your call. Until it is done, do not claim the product works on WhatsApp.
- **Read the bite first-aid copy** and call or check at least the Panaji-area health centres in `seed/health_centres.json`.
- **Find fluent readers** for the Konkani, Marathi and Hindi copy, or keep those languages out of the demo.
- **Your `TODO(me)` tasks:** `in_goa()` matters for correctness. `humanize_seconds()` shows on screen ("Please answer within 20 seconds" is fine, but "600 seconds" is not). The rest are polish.

## Appendix: the C1 reproduction

Put this in `tests/` while fixing C1, then invert the asserts: after a failed send the case must still reach a team.

```python
def test_failed_reply_send_leaves_case_unrouted_forever(app, seeded, clock):
    sim = app.state.simulator
    real = sim.send_text
    async def flaky(to, text):
        if to == "+910000000001" and "PAW-" in text:
            raise RuntimeError("channel refused")   # e.g. WhatsApp 131047, Telegram 5xx
        await real(to, text)
    sim.send_text = flaky
    client = TestClient(app, raise_server_exceptions=False)
    send_photo(client, "+910000000001")
    assert send_loc(client, "+910000000001", 15.4909, 73.8278).status_code == 500
    [case] = cases(seeded)
    assert case.state == "REPORTED"                          # never triaged or routed
    assert seeded.scalars(select(Dispatch)).all() == []      # no team alerted
    clock.advance(get_settings().escalation_timeout_seconds + 1)
    asyncio.run(run_timeouts(app.state.simulator))
    assert cases(seeded)[0].state == "REPORTED"              # the timer does not rescue it
    row = [c for c in client.get("/dashboard/data").json()["cases"] if c["id"] == case.public_id][0]
    assert row["attention"] is None                          # and nobody is told to look
```

The other eight reproductions (bite misrouting, Mumbai pin, loose dedup, `/sim` impersonation, no phone numbers on the dashboard, accept after resolved) are in the audit session's scratch folder and can be recreated from the descriptions above.
