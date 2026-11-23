# What the website may claim

The source of truth for every claim on the product website and in the demo film. Written 24 Nov 2026 from
`README.md`, `docs/PLAN.md`, `docs/AUDIT.md` and `docs/DECISIONS.md`. Update it when something is verified; the site copy follows it.

**Rule:** only the first table becomes a plain claim. The second is shown as "built, not yet live-tested". The third is not shown as a feature.

## 1. Verified (automated tests pass, and run end to end on the simulator)

| Capability | Evidence |
|---|---|
| A photo plus a location opens a case with an ID (`PAW-0041`) | Tests; simulator runs by Claude (PLAN slices 1–2) |
| Reports outside Goa are refused | Freeze fix 2, "a real Goa boundary" (commit `e822334`) |
| Duplicate reports within 200 m and 2 hours of a similar open case are merged; every reporter is told | Tests; simulator run (slice 4) |
| The zone's team is alerted with Accept and Decline buttons | Tests; browser run (slice 5) |
| A decline, a closed team or no answer escalates to the next team, then the taluka officer | Tests; simulator run, audit live run 17 Nov |
| The reporter is told at each step: accepted, on site, resolved | Tests; simulator run |
| A case is routed even when triage fails or is slow; it is flagged "needs a person" at high urgency | Tests (`test_reliability.py`, `test_triage_timeout.py`); audit live run |
| A failed message send never stops a case; stuck cases are picked up by a job | D-094, 17 tests in `test_reliability.py` |
| Bite flow: wash-the-wound steps and the nearest listed health centre | Tests; simulator run (slice 6). The health centre list is **unconfirmed** |
| Camp booking with BOOK, and a reminder | Tests; simulator run (slice 7) |
| STATUS and CANCEL for citizens | Tests (`test_pickup.py`); simulator run by Claude |
| After a rescue: a team photo to reporters, and a Good/OK/Poor rating | 25 tests in `test_aftercare.py` |
| Officials' dashboard: map, case list with search and filters, case detail with audit trail, sterilisation panel, next-camp suggestion, response times | Tests; browser runs by Claude |
| The dashboard works without internet except the map tiles | D-095, checked in the browser with Leaflet removed |
| Dashboard data never shows a phone number; logs mask numbers | Audit test `test_dashboard_data_has_no_phone_numbers` |
| Every state change goes through one state machine and writes an audit event | `app/cases/state_machine.py`; tests |
| Test suite | 464 passed, 11 skipped on 24 Nov (`freeze-fixes` plus the uncommitted triage-timeout work); re-count before publishing |

## 2. Built, tested only against stand-ins (say "not yet live-tested")

| Capability | Status |
|---|---|
| Claude photo triage (`claude-haiku-5-5`): species, injury, urgency, aggression, 2–3 safe steps, never a diagnosis | **Run live on 24 Nov** on one real street-dog photo, twice (PAW-0050 via the public sandbox, about 6 s; PAW-0051 via the simulator). Both gave three safe steps and the "not a diagnosis" line. **Urgency differed between runs on the same photo** (medium, then low). Claim: "works on a real photo"; never claim accuracy |
| WhatsApp Cloud API | Receiving works; Meta blocks replies until the business is verified (D-092) |
| Telegram bot | Tests against a stand-in; never run with a real bot |
| Voice notes through Bhashini | Written; never run with real keys |
| Google Calendar sync for camp slots | Written; never run against Google |
| Konkani, Marathi and Hindi replies | Machine-drafted; not checked by a fluent reader |

## 3. Not done (never present as a feature)

- Real partner teams, councils or NGOs. All teams are placeholders.
- Real service boundaries. Zones are approximate circles around town centres.
- Any measured triage accuracy, response-time improvement or cost saving.
- A timed rehearsal by a person; hand testing by a person.

## Numbers allowed anywhere on the site or in the film

Only `docs/SPEC.md` section 1:
- 19,368 dog bite cases in Goa in 2025, about one every 27 minutes (Health Intelligence Bureau data tabled in the Goa Legislative Assembly, LAQ 097; Goemkarponn, Jan 2026).
- In 2025 Canacona, Sankhalim, Valpoi and Mapusa held zero sterilisation camps; Panaji's partner sterilised 2,918 dogs, Ponda 1,121, Curchorem-Cacora 243.
- Each municipality has its own helpline; Panaji's runs 8 am to 8 pm.
- Andhra Pradesh's Mana Mitra WhatsApp platform runs 1,126 services and has served 58.2 lakh people.

Product parameters (200 m, 2 hours, 10 minutes) are design values, not results. Dashboard figures are **demo data** and must be labelled so.
