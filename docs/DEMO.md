# PawSOS Goa: the 3-minute demo

The demo runs on the simulator (`/sim`) and the dashboard (`/dashboard`), side by side. Real WhatsApp is an optional opening, used only if it was tested that morning.

**Status of this script (11 Nov).** Claude ran every step below through the simulator on a clean copy of the project, without talking, in about 36 seconds plus the 20-second escalation wait. Nobody has yet rehearsed it aloud with a stopwatch, and it has not been run with a real Claude API key. The times in the table are estimates until you rehearse.

The optional beats near the end (STATUS, CANCEL, LANGUAGE, the case panel, a staff action, response times) were written on 11 Nov from reading the code. **Nobody has run them yet, not even on the simulator.** Run each one before you plan to show it.

## What to say only if it is true

- Say "demo data" when the dashboard is on screen. The 40 cases and 23 bite reports on the map are invented and tagged.
- Say "placeholder teams". No real NGO or council is connected.
- Say "not a diagnosis". Triage describes what a photo shows and gives safe steps; it never names a condition.
- The health centre list is unconfirmed. Do not say PawSOS knows which centres stock anti-rabies treatment.
- Use only the figures in this script. They are the ones in `docs/SPEC.md` section 1.
- If you show Konkani, Marathi or Hindi, say "machine-drafted, not yet checked by a fluent reader".
- If you show the response-times panel, say "demo figures". The demo seed spaces each case's steps two minutes apart, so those times are invented.

## The day before

1. Put an Anthropic API key in `.env` (`ANTHROPIC_API_KEY=`) and run one report, so you have seen real triage work. Without a key the demo still runs: the citizen is told "a team member will look at your photo" and the case goes ahead at high urgency.
2. Save two photos of the same animal, taken from different angles, somewhere easy to reach on the laptop. Use your own photos.
3. Rehearse this script three times with a stopwatch. Cut steps 5 and 6 first if you run over.
4. Check the dashboard map on the venue's network if you can. The map needs the internet.

## Ten minutes before

1. Set these in `.env`:
   ```
   ESCALATION_TIMEOUT_SECONDS=20
   IGNORE_OPENING_HOURS=true
   REMINDER_WINDOW_HOURS=720
   REMINDER_CHECK_SECONDS=10
   ```
2. Start the database:
   ```bash
   docker compose up -d
   ```
3. Reset to a known state. **This deletes every case, bite report and booking in the database**, then reloads the demo data. Run it without `--yes` first to see what it would delete.
   ```bash
   .venv/bin/python -m seed.reset --yes
   ```
4. Start the server (restart it if it was running, so the simulator's chats are empty):
   ```bash
   .venv/bin/uvicorn app.main:app --port 8040
   ```
5. Open two browser windows side by side: `http://localhost:8040/sim` on the left, `http://localhost:8040/dashboard` on the right.
6. In the simulator, check the persona list shows Citizen 1, 2 and 3 and the placeholder teams.

After a reset, your first case will be `PAW-0041`.

## The script

| Time | Do | Say |
|------|----|-----|
| 0:00 | Dashboard on screen. | "Goa recorded 19,368 dog bite cases in 2025. That is about one every 27 minutes. If you see an injured animal today, which number do you call? Every municipality has its own, and Panaji's helpline runs 8 am to 8 pm." |
| 0:20 | Simulator, **Citizen 1**. Press **Photo**, choose the first photo. Press **Location**, choose **Panaji**. | "PawSOS is one WhatsApp number for all of Goa. No app. I send a photo and my location." |
| 0:35 | Point at the replies: case ID, urgency, first-aid steps, the "not a diagnosis" line, "Panaji area". | "In seconds I have a case ID, how urgent it looks, and two or three safe things to do while I wait. This is guidance from a photo, not a diagnosis." |
| 0:55 | Switch to **Citizen 2**. Send the second photo and the same Panaji location. | "A second person walks past the same animal. PawSOS sees it is within 200 metres and 2 hours of an open case, and merges it. Both people get updates, and the team gets one alert, not two." |
| 1:15 | Switch to **Panaji partner team (placeholder)**. Show the alert with **Accept** and **Decline**. Do not press anything. | "The Panaji team gets the photo, a map link and two buttons. Suppose nobody answers." |
| 1:25 | Wait. The alert times out (20 seconds in the demo, 10 minutes in real use). Use the wait for the next line. | "Helplines go unanswered. PawSOS does not wait for ever: it escalates to the next nearest team, and then to the taluka officer. The citizen is told each time." |
| 1:45 | Switch to **Mormugao partner team (placeholder)**. Press **Accept**, then **On site**, then **Resolved**. | "The next team accepts, reaches the animal, and closes the case." |
| 2:00 | Switch to **Citizen 1**. Scroll through the updates. | "And the person who reported it is told at every step. The loop is closed." |
| 2:10 | Dashboard. Point at the map, then the sterilisation panel, then the suggestion card. | "For officials, every case and bite report is on one map. This is demo data. In 2025 Canacona, Sankhalim, Valpoi and Mapusa held zero sterilisation camps, while Panaji's partner sterilised 2,918 dogs. PawSOS counts bite reports by area and suggests where the next camp should go. It is a simple count, and the rule is printed on the page." |
| 2:35 | *(Cut if over time.)* Simulator, **Citizen 3**. Type `a dog bit me`. Then **Location**, **Panaji**. | "If someone is bitten, they get wash-the-wound steps at once and the nearest health centre on our list." |
| 2:45 | *(Cut if over time.)* Type `BOOK`, then `1`, then `2`. | "And a pet owner can book a camp slot in three messages." |
| 2:55 | Stop clicking. Face the judges. | "WhatsApp governance already works at scale: Andhra Pradesh's Mana Mitra runs 1,126 services and has served 58.2 lakh people. PawSOS brings that to animal emergencies in Goa." *(TODO(me): Ayush, replace or follow this with one closing sentence in your own words. What do you want the judges to remember?)* |

## If something fails

| What happens | What to do | What to say |
|---|---|---|
| Triage is slow or the API fails | Nothing. After one retry the app carries on: the citizen is told a team member will look at the photo, and the case is routed at high urgency. | "If the model is unavailable the case is not held up. It is flagged for a person and routed anyway." |
| The map is blank (no internet) | Keep going. The tiles, case list, sterilisation panel and suggestion still work. | "The map needs a connection; the rest of the dashboard does not." |
| The second report does not merge | Carry on with the first case. This happens if the two locations differ or an earlier rehearsal left data behind (you skipped the reset). | Skip the dedup line. |
| The alert does not time out | Press **Decline** as the Panaji team. A decline escalates in the same way. | "Or the team declines." |
| The server has crashed | Restart it with the command above. Cases are in the database and survive; the simulator's chat history does not. | "Everything is stored in the database, so a restart loses nothing." |
| Real WhatsApp does not answer | Switch to the simulator at once. Do not debug on stage. | "The simulator runs exactly the same logic." |

## Optional beats (only if time is left, or when a judge asks)

These sit outside the 3 minutes. Do not add them to the core script; use them if the core run finished early, or in the questions. Each one can be skipped on its own. Times are guesses: nobody has run these yet.

Before the demo, check that the server runs the code with these features (branch `pickup-tasks` or later) and that `.venv/bin/alembic upgrade head` has added migration 0008. The rehearsal reset also clears saved languages, so every persona starts in English.

| Length | Do | Say |
|------|----|-----|
| about 25 s, plus the triage wait | Simulator, **Citizen 3**. Press **Photo**, choose a photo. Press **Location**, choose **Margao** (not Panaji, so it does not merge into the first case). Do not answer as the Margao team. | "Another report, somewhere else in Goa." |
| about 15 s | Still **Citizen 3**. Type `STATUS`. | "Anyone can ask where their reports stand. They see each open case in plain words, and any camp booking." |
| about 25 s | Dashboard. Tap Citizen 3's new case in the case list (or **Case details** on its map pin). Point at the photo, the triage card, the alert history and the audit trail. | "Officials can open any case: the photo, what triage saw (not a diagnosis), which teams were asked and what they said, and every step with its time. No phone numbers are shown." |
| about 25 s | In the same panel, under **Send to a team**, choose **Mapusa partner team (placeholder)** and press **Alert this team**. Switch to that team in the simulator and show the alert. | "If no team is answering, staff can send the case to a team they choose. That team still has to accept." |
| about 20 s | Simulator, **Citizen 3**. Type `CANCEL`, then `1` (the case). Switch to **Mapusa partner team (placeholder)** and show the "cancelled" message. | "If the animal has gone, the reporter can cancel, and every team still involved is stood down, so nobody makes a wasted trip." |
| about 20 s | Still **Citizen 3**. Type `LANGUAGE`, then `4` (हिंदी). Type `hi`. Then `LANGUAGE` and `1` to switch back. | "People can choose Konkani, Marathi or Hindi. These translations are machine-drafted and not yet checked by a fluent reader." |
| about 15 s | Dashboard. Point at the **Response times** panel. | "From the audit log, the median and 90th percentile time from report to accepted, and accepted to resolved, by area. These are demo figures." |

If you are short of time, the case panel and STATUS are the two to keep.

### If an optional beat fails

| What happens | What to do | What to say |
|---|---|---|
| `STATUS`, `CANCEL` or `LANGUAGE` gets the "how to report" reply | The server is running older code. Skip the remaining beats. | Nothing; go to questions. |
| Citizen 3's report merged into another case | You chose Panaji, or an earlier rehearsal left a case in Margao. CANCEL will then be refused ("also reported by someone else"); skip the CANCEL beat. | "Merged reports stay open for everyone who reported them." |
| The case panel says it could not load the case | Close it and carry on with the list and the map. | Nothing. |
| **Alert this team** shows an error, or the case is not offered a team | The case may already be accepted or closed: staff can only send a case that is still waiting for a team. Skip the beat. | "Once a team has accepted, staff cancel instead of reassigning." |
| The browser asks for a password on the dashboard | Type `DASHBOARD_PASSWORD` from `.env` (any user name). | Nothing. |
| The Hindi reply comes back in English | That message has no translation yet; English is the fallback. Switch back with `LANGUAGE`, `1`. | "Anything not yet translated falls back to English." |

## Optional opening on a real phone

Only if you completed `docs/WHATSAPP_SETUP.md` that morning with a fresh access token. Replace the 0:20 step: send the photo and location from your phone, and show the replies arriving on it. Everything from 1:15 onwards stays in the simulator, because the placeholder teams live there.

## Questions you may be asked

- **Is the triage accurate?** It has not been evaluated. It describes what is visible, grades urgency, and gives safe generic steps. A trained team makes the real assessment.
- **Are these real teams and boundaries?** No. Teams are placeholders and service areas are approximate circles around town centres.
- **Where do the sterilisation figures come from?** They are the 2025 figures in our brief, for seven municipalities. The others show "No figure".
- **What happens outside working hours?** A closed team is skipped and the next team is alerted straight away.
- **Other languages?** Konkani, Marathi and Hindi versions of the citizen messages are written, and each person can choose with `LANGUAGE`. They were drafted by a machine and have not been checked by a fluent reader, so say so. Rescue teams are written to in English. Real speech recognition through Bhashini is written but has never been tried with real keys or a real voice note, so do not demo it as working; the simulator's pretend voice notes still use the stand-in.
- **Can a citizen cancel?** Yes, with `CANCEL`, unless someone else also reported the same animal; then the case stays open for them. Staff can cancel any open case from the dashboard, with a reason kept in the audit log.
