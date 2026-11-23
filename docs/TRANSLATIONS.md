# Translations: checklist for a fluent reader

**Every Konkani, Marathi and Hindi message in `app/messages.py` was drafted by a machine (Claude) on 11 Nov 2026 (the STATUS, CANCEL and staff-update messages were added later the same day). None has been checked by a fluent reader. Each one MUST be checked before PawSOS is used with real people.** Until then, treat them as demo copy.

The texts are in `app/messages.py`, in three tables at the bottom of the file: `KOK` (Konkani), `MR` (Marathi), `HI` (Hindi). The English for each key is in `MESSAGES` near the top. Read one language at a time, side by side with the English, and tick the box when the text is right.

## What to check

- **Meaning**: says the same as the English, nothing added, nothing left out. This matters most for the bite messages, which are safety advice.
- **Plain words**: everyday language a worried person reads in five seconds, not formal or Sanskritised words. Konkani is in Devanagari script, as used officially in Goa.
- **Placeholders**: anything in `{curly brackets}` (such as `{case_id}`) must stay exactly as it is. The app fills it in. A script check already confirms none is missing or extra.
- **Latin words**: `BOOK`, `STATUS`, `CANCEL`, `LANGUAGE`, case IDs such as `PAW-0042` and booking references such as `BK-0005`, `PawSOS Goa`, `JPEG`, `PNG`, `MB` and WhatsApp's `Location` label stay in Latin script, because that is what the person types or sees on screen.
- **Grammar and gender**: the bot says "we" (आमी, आम्ही, हम) where "I" would need a gendered verb. Check that verbs agree, especially with "केस" (case), whose gender may differ by language.
- **The attach button**: the drafts say "📎 अटॅच / अटैच" for WhatsApp's attach button. Change it if people say it differently.

## Not translated on purpose

- **Messages to rescue teams** (every `team_*` key, such as `team_alert`, `team_accepted_ack`, `team_case_reassigned`, `team_case_cancelled_by_staff`, `team_case_cancelled_by_reporter`, and `not_a_team`) and the **buttons** (`button_accept`, `button_decline`, `button_on_site`, `button_resolved`) stay in English: teams are organisations, their alerts carry case IDs and links, and WhatsApp limits button titles to 20 characters.
- `book_camp_line` has no words of its own (place, services, date, venue come from the camp data).

## Also still in English inside translated messages

- Camp names, venues and services come from the seed data in English.
- Times ("09:00 to 10:00") are the same in every language.
- First-aid steps after a photo come from the triage model, which writes them in English.
- Case states in the STATUS list ("a rescue team has been alerted") are translated, but the team name inside them comes from the seed data in English.

## Checklist

Tick `[x]` when checked. Put the reviewer's name and the date at the bottom.

### Safety-critical: check these first

| Key | Konkani | Marathi | Hindi |
|---|---|---|---|
| `bite_first_aid` | [ ] | [ ] | [ ] |
| `bite_nearest_centre` | [ ] | [ ] | [ ] |
| `bite_no_centre` | [ ] | [ ] | [ ] |
| `aggression_warning` | [ ] | [ ] | [ ] |
| `not_a_diagnosis` | [ ] | [ ] | [ ] |
| `triage_needs_review` | [ ] | [ ] | [ ] |

### Getting started and choosing a language

| Key | Konkani | Marathi | Hindi |
|---|---|---|---|
| `welcome` | [ ] | [ ] | [ ] |
| `language_menu` | [ ] | [ ] | [ ] |
| `language_set` | [ ] | [ ] | [ ] |
| `how_to_report` | [ ] | [ ] | [ ] |

`welcome` now also tells people about STATUS and CANCEL: check that sentence too.

### Reporting an animal

| Key | Konkani | Marathi | Hindi |
|---|---|---|---|
| `ask_location` | [ ] | [ ] | [ ] |
| `ask_photo` | [ ] | [ ] | [ ] |
| `case_created` | [ ] | [ ] | [ ] |
| `triage_result` | [ ] | [ ] | [ ] |
| `urgency_low` | [ ] | [ ] | [ ] |
| `urgency_medium` | [ ] | [ ] | [ ] |
| `urgency_high` | [ ] | [ ] | [ ] |
| `urgency_critical` | [ ] | [ ] | [ ] |
| `zone_assigned` | [ ] | [ ] | [ ] |
| `merged_new_reporter` | [ ] | [ ] | [ ] |
| `merged_same_reporter` | [ ] | [ ] | [ ] |
| `merged_earlier_reporter` | [ ] | [ ] | [ ] |
| `outside_goa` | [ ] | [ ] | [ ] |
| `photo_rejected` | [ ] | [ ] | [ ] |
| `unsupported` | [ ] | [ ] | [ ] |

### Updates on a case

| Key | Konkani | Marathi | Hindi |
|---|---|---|---|
| `citizen_accepted` | [ ] | [ ] | [ ] |
| `citizen_on_site` | [ ] | [ ] | [ ] |
| `citizen_resolved` | [ ] | [ ] | [ ] |
| `citizen_escalated` | [ ] | [ ] | [ ] |
| `citizen_no_team_yet` | [ ] | [ ] | [ ] |
| `citizen_staff_assigned` | [ ] | [ ] | [ ] |
| `citizen_cancelled` | [ ] | [ ] | [ ] |

### STATUS and CANCEL

The `status_state_*` texts are fragments that go after a colon in `status_case_line` and in brackets in `cancel_case_line`: read them inside the full line. `status_booking_line` and `cancel_booking_line` are mostly placeholders; check only the word and the punctuation.

| Key | Konkani | Marathi | Hindi |
|---|---|---|---|
| `status_header_cases` | [ ] | [ ] | [ ] |
| `status_case_line` | [ ] | [ ] | [ ] |
| `status_case_line_zone` | [ ] | [ ] | [ ] |
| `status_state_received` | [ ] | [ ] | [ ] |
| `status_state_finding_team` | [ ] | [ ] | [ ] |
| `status_state_team_alerted` | [ ] | [ ] | [ ] |
| `status_state_still_looking` | [ ] | [ ] | [ ] |
| `status_state_accepted` | [ ] | [ ] | [ ] |
| `status_state_on_site` | [ ] | [ ] | [ ] |
| `status_header_bookings` | [ ] | [ ] | [ ] |
| `status_booking_line` | [ ] | [ ] | [ ] |
| `status_footer` | [ ] | [ ] | [ ] |
| `status_nothing` | [ ] | [ ] | [ ] |
| `cancel_choose` | [ ] | [ ] | [ ] |
| `cancel_case_line` | [ ] | [ ] | [ ] |
| `cancel_booking_line` | [ ] | [ ] | [ ] |
| `cancel_invalid_choice` | [ ] | [ ] | [ ] |
| `cancel_nothing` | [ ] | [ ] | [ ] |
| `cancel_not_found` | [ ] | [ ] | [ ] |
| `case_cancel_closed` | [ ] | [ ] | [ ] |
| `case_cancel_shared` | [ ] | [ ] | [ ] |
| `case_cancelled` | [ ] | [ ] | [ ] |
| `case_cancelled_team_told` | [ ] | [ ] | [ ] |
| `booking_cancelled` | [ ] | [ ] | [ ] |
| `booking_cancel_closed` | [ ] | [ ] | [ ] |

### Booking a camp slot

| Key | Konkani | Marathi | Hindi |
|---|---|---|---|
| `book_choose_camp` | [ ] | [ ] | [ ] |
| `book_no_camps` | [ ] | [ ] | [ ] |
| `book_choose_slot` | [ ] | [ ] | [ ] |
| `book_slot_line` | [ ] | [ ] | [ ] |
| `book_camp_full` | [ ] | [ ] | [ ] |
| `book_slot_full` | [ ] | [ ] | [ ] |
| `book_invalid_choice` | [ ] | [ ] | [ ] |
| `book_cancelled` | [ ] | [ ] | [ ] |
| `book_already` | [ ] | [ ] | [ ] |
| `book_confirmed` | [ ] | [ ] | [ ] |
| `book_reminder` | [ ] | [ ] | [ ] |

### Voice notes

| Key | Konkani | Marathi | Hindi |
|---|---|---|---|
| `voice_heard` | [ ] | [ ] | [ ] |
| `voice_noted` | [ ] | [ ] | [ ] |
| `voice_not_understood` | [ ] | [ ] | [ ] |

71 keys in each of 3 languages: 213 texts.

### Commands and words the app understands

These are in `app/contacts.py` and `app/conversation.py`, not `app/messages.py`. `STATUS` and `CANCEL` are understood in English only (`app/citizen.py`). Check that people would really type them.

| What | Words | Checked |
|---|---|---|
| Open the language menu | `LANGUAGE`, `lang`, `bhasha`, `भाषा`, `भास` | [ ] |
| Greetings that get the welcome message (`GREETINGS` in `app/conversation.py`) | `hi`, `hello`, `hey`, `namaste`, `namaskar`, `start`, `नमस्कार`, `नमस्ते`, `हॅलो`, `हेलो`, `हैलो`, `हाय` | [ ] |
| Pick a language while the menu is open | `1` to `4` (Devanagari digits `१` to `४` work too), or `english`, `konkani`, `कोंकणी`, `कोकणी`, `marathi`, `मराठी`, `hindi`, `हिंदी`, `हिन्दी` | [ ] |

## Rating and rescue photo (added 13 Nov, machine-drafted)

- [ ] `rating_ask`, `rating_thanks`, `rating_unavailable`, `rescue_photo_caption`, in all three languages.
- [ ] The three button titles, `rating_good`, `rating_ok`, `rating_poor` (at most 20 characters each): Konkani "बरो / ठीक / वायट", Marathi "चांगला / ठीक / वाईट", Hindi "अच्छा / ठीक / ख़राब". Check that each reads naturally as an answer to "how did it go?".

## Out of Goa, and who was bitten (added 17 Nov, machine-drafted)

- [ ] The reworded `outside_goa` (it now thanks the person, says to contact the local municipality or an animal welfare group outside Goa, and asks for the current location again), in all three languages.
- [ ] `bite_which`, the question asked when a bite message does not say who was bitten, in all three languages. It must read as calm and quick to answer.
- [ ] The two button titles, `bite_choice_person` and `bite_choice_animal` (at most 20 characters each): Konkani "मनशाक चाबलां / जनावर जखमी जालां", Marathi "माणसाला चावले / प्राणी जखमी आहे", Hindi "इंसान को काटा है / जानवर घायल है". Check that each is a natural answer to the question. The word for "bitten" matters most: check "चाबलां" for Konkani.

## Dates and place names (added 11 Nov, machine-drafted)

These are in `app/messages.py` under "dates and place names". Please check each one.

- [ ] `WEEKDAYS` and `MONTHS` for Konkani, Marathi and Hindi (for example "शेनवार 28 नोव्हेंबर", "शनिवार 28 नवंबर").
- [ ] `PLACE_NAMES`: the 14 areas as a Devanagari reader in Goa would write them. Check the Konkani forms especially (म्हापशें, पेडणें, दिवचल, सांखळी, वाळपय, फोंडें, मुरगांव, मडगांव, केपें, कुडचडें-काकोडें, सांगें), and whether Hindi readers expect the same names as Marathi.
- [ ] `note_ask_location`, `note_ask_photo` and the reworded `case_cancel_shared`, in all three languages.

## Keys added later

Other features may add English-only keys after this list was written. They fall back to English until translated. Before release, compare this list with the keys in `MESSAGES` and add any new citizen-facing ones here.

## Sign-off

| Language | Checked by | Date |
|---|---|---|
| Konkani | | |
| Marathi | | |
| Hindi | | |
