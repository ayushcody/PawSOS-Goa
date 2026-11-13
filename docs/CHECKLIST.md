# Checklist: run the pick-up work

**Update, later on 11 Nov:** the branch is merged into `main`. Claude ran sections 2 and 3 on a machine with Docker; the results, five fixes and the new tests are in `docs/PLAN.md` ("First run, fixes and tests"). The expected test result is now **311 passed, 12 skipped**, and migrations end at `0010`. The text below is the original first-run list, kept for a hand check by a person.

Everything on `pickup-tasks` was written on 11 Nov on a machine without Docker. **None of it has been run against a database, on the simulator, or against a real service, and the new features have no tests of their own.** This page is the first run. Tick each line, and write down anything that differs from "Expect".

## 1. Set up (about 10 minutes)

```bash
git fetch && git checkout pickup-tasks
.venv/bin/pip install -e ".[dev]"
docker compose up -d
.venv/bin/alembic upgrade head        # adds migration 0008 (the contacts table)
.venv/bin/python -m seed.load
.venv/bin/python -m seed.demo
.venv/bin/ruff check .
.venv/bin/pytest -q
.venv/bin/uvicorn app.main:app --reload --port 8040
```

- [ ] `alembic upgrade head` ends at `0008`.
- [ ] `pytest`: expect **192 passed, 11 skipped**, as on `main` (no tests were added; one test in `test_slice10.py` was renamed and one now expects a Hindi reply). Any failure here is a bug on this branch: note the test name.
- [ ] Optional, for real voice notes only: `ffmpeg -version` works.

## 2. On the simulator (`http://localhost:8040/sim`)

Use **Citizen 1** unless a line says otherwise. Run `.venv/bin/python -m seed.reset --yes` first for a clean start.

**Typed description in the team alert**
- [ ] Press **Photo**, type `brown dog limping near the bus stand`, then **Location → Panaji**.
  Expect: a case ID, then the triage reply. Switch to **Panaji partner team**: the alert has a line `Reporter says: "brown dog limping near the bus stand"`.
- [ ] Repeat with a link in the words (`see evil.com/x`). Expect: `[link removed]` in the alert.

**No temporary case ID before a merge**
- [ ] As **Citizen 2**, report the same place (Photo, then Location → Panaji) within 2 hours.
  Expect: "we are checking whether someone has already reported this animal" with **no** case ID, then the **first** case's ID and the merge message. Citizen 1 is told another person reported it.

**STATUS and CANCEL**
- [ ] Citizen 1 sends `STATUS`. Expect: the open case in plain words, with its area.
- [ ] Send `CANCEL`. Expect: a numbered list. Reply `1`.
  Expect, if the case is shared with Citizen 2: "You will get no more updates … stays open for them", and the case leaves Citizen 1's STATUS. When Citizen 2 then cancels too, the case is cancelled. Otherwise: "cancelled, and we have told the rescue team"; the team gets "cancelled by the person who reported it".
- [ ] Send `BOOK`, book a slot, then `STATUS` (the booking shows), then `CANCEL BK-…`. Expect: the place is free again (book it again to check).
- [ ] Mid-BOOK, type a number: it must still go to the booking, not to CANCEL or LANGUAGE.

**Languages**
- [ ] Send `LANGUAGE`, then `4`. Expect: the reply in Hindi. Send `hi`: the welcome comes in Hindi and mentions STATUS and CANCEL.
- [ ] Send `STATUS` and report a case: every citizen reply is in Hindi; the team alert stays in English.
- [ ] Send `LANGUAGE`, then `1` to go back to English.
- [ ] `seed.reset --yes` puts everyone back to English.

**Cancel while the photo is being looked at** (only matters with a real `ANTHROPIC_API_KEY`, when triage takes seconds)
- [ ] Send Photo and Location, then `CANCEL` and `1` at once. Expect: the case is cancelled and nothing after it errors (no 500 in the server log); no team is alerted.

## 3. On the dashboard (`http://localhost:8040/dashboard`)

- [ ] Click a case. Expect: a side panel with the photo, triage (with "not a diagnosis"), report count without phone numbers, notes (typed ones labelled typed), alerts, and the audit trail.
- [ ] On an open case waiting for a team, choose a team and press **Alert this team**. Expect: that team gets the normal alert; the reporter is told staff asked that team. As that team, press **Decline**. Expect: the team hears the case went back to staff; the reporter hears the team could not take it; the case is flagged "no team".
- [ ] **Cancel case** with a reason. Expect: the reporter gets a calm "closed by PawSOS staff" message in their language; the reason is only in the audit trail.
- [ ] The **response times** panel shows figures. With demo data they are invented (events two minutes apart), so say "demo figures".
- [ ] At phone width (about 380 px) the panel fills the screen and closes with Esc.
- [ ] Behind a proxy that rewrites the Host header, staff actions return 403 (the cross-site check compares Origin with Host). Plain ngrok is fine.

## 4. Needs keys or a person (not for the first run)

- **Fluent readers** for Konkani, Marathi and Hindi: `docs/TRANSLATIONS.md`. Start with the bite and safety messages.
- **Real triage**: set `ANTHROPIC_API_KEY`, send real photos, check first aid comes back in Hindi for a Hindi user (D-081).
- **Bhashini**: keys and ffmpeg, `docs/VOICE_SETUP.md`.
- **WhatsApp**: Meta app and the three templates, `docs/WHATSAPP_SETUP.md`.
- **Google Calendar**: a synced booking, then cancel it; the calendar entry should disappear.

## Known gaps on this branch

- (Fixed, D-085) Link cleaning in team alerts missed bare domains in capitals or with everyday-word endings.
- STATUS or CANCEL sent during the few seconds of the duplicate check shows the case ID that is about to be merged away.
- STATUS, CANCEL and LANGUAGE are recognised only as English words (LANGUAGE also as भाषा).
- (Fixed) The new features now have tests in `tests/test_pickup.py`.
- Ayush's skipped exercise in `tests/test_slice1.py` (the fallback test) hints at rendering `welcome` in Konkani and expecting English. Konkani now exists, so that hint needs another language (say `"fr"`) before he does the exercise. Left for Ayush, as `TODO(me)` items are his.
