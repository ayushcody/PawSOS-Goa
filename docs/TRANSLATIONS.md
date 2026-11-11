# Translations: checklist for a fluent reader

**Every Konkani, Marathi and Hindi message in `app/messages.py` was drafted by a machine (Claude) on 11 Nov 2026. None has been checked by a fluent reader. Each one MUST be checked before PawSOS is used with real people.** Until then, treat them as demo copy.

The texts are in `app/messages.py`, in three tables at the bottom of the file: `KOK` (Konkani), `MR` (Marathi), `HI` (Hindi). The English for each key is in `MESSAGES` near the top. Read one language at a time, side by side with the English, and tick the box when the text is right.

## What to check

- **Meaning**: says the same as the English, nothing added, nothing left out. This matters most for the bite messages, which are safety advice.
- **Plain words**: everyday language a worried person reads in five seconds, not formal or Sanskritised words. Konkani is in Devanagari script, as used officially in Goa.
- **Placeholders**: anything in `{curly brackets}` (such as `{case_id}`) must stay exactly as it is. The app fills it in. A script check already confirms none is missing or extra.
- **Latin words**: `BOOK`, `CANCEL`, `LANGUAGE`, case IDs such as `PAW-0042`, `PawSOS Goa`, `JPEG`, `PNG`, `MB` and WhatsApp's `Location` label stay in Latin script, because that is what the person types or sees on screen.
- **Grammar and gender**: the bot says "we" (आमी, आम्ही, हम) where "I" would need a gendered verb. Check that verbs agree, especially with "केस" (case), whose gender may differ by language.
- **The attach button**: the drafts say "📎 अटॅच / अटैच" for WhatsApp's attach button. Change it if people say it differently.

## Not translated on purpose

- **Messages to rescue teams** (`team_alert`, `team_alert_seen`, `team_alert_not_triaged`, `team_accepted_ack`, `team_on_site_ack`, `team_resolved_ack`, `team_declined_ack`, `team_alert_expired`, `team_case_taken`, `team_not_waiting`, `not_a_team`) and the **buttons** (`button_accept`, `button_decline`, `button_on_site`, `button_resolved`) stay in English: teams are organisations, their alerts carry case IDs and links, and WhatsApp limits button titles to 20 characters.
- `book_camp_line` has no words of its own (place, services, date, venue come from the camp data).

## Also still in English inside translated messages

- Camp names, venues and services, and zone names, come from the seed data in English.
- Dates in booking messages ("Sat 28 Nov") come from `format_date` in `app/booking/flow.py`.
- First-aid steps after a photo come from the triage model, which writes them in English.
- `photo_rejected` has translations, but the simulator and WhatsApp adapters still send it in English (they do not look up the person's language).

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

44 keys in each of 3 languages: 132 texts.

### Commands and words the app understands

These are in `app/contacts.py`, not `app/messages.py`. Check that people would really type them.

| What | Words | Checked |
|---|---|---|
| Open the language menu | `LANGUAGE`, `lang`, `bhasha`, `भाषा`, `भास` | [ ] |
| Pick a language while the menu is open | `1` to `4` (Devanagari digits `१` to `४` work too), or `english`, `konkani`, `कोंकणी`, `कोकणी`, `marathi`, `मराठी`, `hindi`, `हिंदी`, `हिन्दी` | [ ] |

## Keys added later

Other features may add English-only keys after this list was written. They fall back to English until translated. Before release, compare this list with the keys in `MESSAGES` and add any new citizen-facing ones here.

## Sign-off

| Language | Checked by | Date |
|---|---|---|
| Konkani | | |
| Marathi | | |
| Hindi | | |
