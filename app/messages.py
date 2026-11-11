"""Every message PawSOS sends, in one place.

Keys describe the purpose ("ask_location", "case_created"), never the
language, so Konkani ("kok") and Marathi ("mr") can be added beside "en"
without touching the code that sends them. Copy is short, calm and plain.
"""

DEFAULT_LANGUAGE = "en"

MESSAGES: dict[str, dict[str, str]] = {
    "welcome": {
        "en": (
            "Hello, this is PawSOS Goa. "
            "To report an animal that needs help, send a photo and your location. "
            "To book a sterilisation or vaccination camp slot for your pet, reply BOOK."
        ),
    },
    "how_to_report": {
        "en": (
            "To report an animal that needs help, send two things: "
            "a photo of the animal, and the location (tap attach, then Location)."
        ),
    },
    "ask_location": {
        "en": (
            "Thank you, photo received. Now please share where the animal is: "
            "tap attach, then Location."
        ),
    },
    "ask_photo": {
        "en": (
            "Thank you, location received. Now please send a photo of the animal, "
            "if you can take one from a safe distance."
        ),
    },
    "case_created": {
        "en": (
            "Your report is logged. Case ID: {case_id}. "
            "We are finding the nearest team and will message you here. "
            "Please keep a safe distance from the animal."
        ),
    },
    "triage_result": {
        "en": "Case {case_id}: {urgency_line}\n\nWhile you wait:\n{steps}\n\n{disclaimer}",
    },
    "urgency_low": {"en": "this does not look urgent, but a team will still be told."},
    "urgency_medium": {"en": "this needs attention soon."},
    "urgency_high": {"en": "this looks urgent."},
    "urgency_critical": {"en": "this looks very urgent. We are alerting a team now."},
    "aggression_warning": {
        "en": "The animal may be frightened or aggressive. Please stay well back.",
    },
    "not_a_diagnosis": {
        "en": (
            "This is general safety guidance from a photo, not a diagnosis. "
            "A trained team will assess the animal."
        ),
    },
    "triage_needs_review": {
        "en": (
            "Case {case_id}: a team member will look at your photo. "
            "Until then, please keep a safe distance, keep others away, "
            "and do not feed or move the animal."
        ),
    },
    "zone_assigned": {
        "en": "Case {case_id} is in the {zone} area. We are alerting a rescue team now.",
    },
    "merged_new_reporter": {
        "en": (
            "Thank you. This animal has already been reported, so your report has been "
            "added to case {case_id}. Please use that case ID from now on; you will get updates here."
        ),
    },
    "merged_same_reporter": {
        "en": "Your new report has been added to your case {case_id}.",
    },
    "merged_earlier_reporter": {
        "en": (
            "Update on case {case_id}: another person has reported the same animal. "
            "That makes {count} reports."
        ),
    },
    # --- updates to the person who reported ---
    "citizen_accepted": {
        "en": "Good news. {team} has accepted case {case_id} and is on the way.",
    },
    "citizen_on_site": {
        "en": "Update on case {case_id}: the team has reached the animal.",
    },
    "citizen_resolved": {
        "en": (
            "Case {case_id} is resolved. The team has attended to the animal. "
            "Thank you for reporting."
        ),
    },
    "citizen_escalated": {
        "en": "Update on case {case_id}: the first team could not take it, so we have alerted the next team.",
    },
    "citizen_no_team_yet": {
        "en": (
            "Update on case {case_id}: we have not reached a team yet. "
            "We are still trying and will message you here."
        ),
    },
    # --- messages to rescue teams ---
    "team_alert": {
        "en": (
            "New case {case_id} in {zone}. Urgency: {urgency}.\n"
            "{seen}\n"
            "Location: {map_link}\n"
            "Reports so far: {reports}.\n"
            "Please answer within {window}."
        ),
    },
    "team_alert_seen": {
        "en": "From the photo (not a diagnosis): {species}, {injury}.",
    },
    "team_alert_not_triaged": {
        "en": "The photo has not been assessed. Please look at it yourself.",
    },
    "team_accepted_ack": {
        "en": "Thank you. Case {case_id} is yours. Tap On site when you reach the animal.",
    },
    "team_on_site_ack": {
        "en": "Noted: on site for case {case_id}. Tap Resolved once the animal has been attended to.",
    },
    "team_resolved_ack": {
        "en": "Case {case_id} is closed. Thank you.",
    },
    "team_declined_ack": {
        "en": "Understood. Case {case_id} has been passed to the next team.",
    },
    "team_alert_expired": {
        "en": "No answer was received in time, so case {case_id} has been passed to the next team.",
    },
    "team_case_taken": {
        "en": "Case {case_id} has been taken by another team. No action needed.",
    },
    "team_not_waiting": {
        "en": "Case {case_id} is not waiting for an answer from you.",
    },
    "not_a_team": {
        "en": "Those buttons are for rescue teams only.",
    },
    "button_accept": {"en": "Accept"},
    "button_decline": {"en": "Decline"},
    "button_on_site": {"en": "On site"},
    "button_resolved": {"en": "Resolved"},
    # --- bite flow ---
    "bite_first_aid": {
        "en": (
            "I am sorry that happened. Please do this now:\n"
            "1. Wash the wound with soap and running water for 15 minutes.\n"
            "2. Do not put oil, turmeric, chilli or any home remedy on it.\n"
            "3. Go to a health centre today for anti-rabies treatment, even if the wound is small.\n\n"
            "Share your location (tap attach, then Location) and I will find the nearest "
            "health centre on our list.\n\n"
            "This is general first-aid guidance, not medical advice."
        ),
    },
    "bite_nearest_centre": {
        "en": (
            "Nearest health centre on our list: {name}, about {km} km away.\n"
            "{map_link}\n"
            "Go today and ask for anti-rabies treatment. Our list has not been verified yet, "
            "so please call ahead if you can.\n\n"
            "If the animal is still nearby, send its photo and location and we will alert a team."
        ),
    },
    "bite_no_centre": {
        "en": (
            "Please go to the nearest government hospital today and ask for anti-rabies treatment.\n\n"
            "If the animal is still nearby, send its photo and location and we will alert a team."
        ),
    },
    # --- booking a camp slot ---
    "book_choose_camp": {
        "en": "Upcoming camps:\n{options}\n\nReply with the number of the camp, or CANCEL.",
    },
    "book_camp_line": {"en": "{place}: {services}, {date}. {venue}"},
    "book_no_camps": {
        "en": "There are no upcoming camps to book right now. Please check again soon.",
    },
    "book_choose_slot": {
        "en": "{camp}, {date}. Free slots:\n{options}\n\nReply with the number of the slot, or CANCEL.",
    },
    "book_slot_line": {"en": "{time} ({left} places left)"},
    "book_camp_full": {
        "en": "Sorry, {camp} is fully booked. Reply BOOK to see other camps.",
    },
    "book_slot_full": {"en": "Sorry, that slot has just filled up."},
    "book_invalid_choice": {
        "en": "Please reply with one of the numbers shown, or CANCEL.",
    },
    "book_cancelled": {
        "en": "No problem, nothing was booked. Reply BOOK to start again.",
    },
    "book_already": {
        "en": "You already have a booking at {camp}: {ref}, {date}, {time}.",
    },
    "book_confirmed": {
        "en": (
            "Booked. Your reference is {ref}.\n"
            "{camp}\n{date}, {time}\n{venue}\n\n"
            "Please bring your pet on a leash or in a carrier. "
            "We will remind you the day before."
        ),
    },
    "book_reminder": {
        "en": (
            "Reminder: your pet's camp slot is coming up.\n"
            "{camp}\n{date}, {time}\n{venue}\n"
            "Reference {ref}."
        ),
    },
    # --- STATUS and CANCEL ---
    "status_header_cases": {"en": "Your open reports:"},
    "status_case_line": {"en": "{case_id}, reported {when}: {state}."},
    "status_case_line_zone": {"en": "{case_id}, reported {when}, {zone} area: {state}."},
    "status_state_received": {"en": "received, we are looking at the photo"},
    "status_state_finding_team": {"en": "we are finding a rescue team"},
    "status_state_team_alerted": {"en": "a rescue team has been alerted"},
    "status_state_still_looking": {"en": "we are still trying to reach a team"},
    "status_state_accepted": {"en": "{team} has accepted it and is on the way"},
    "status_state_on_site": {"en": "{team} has reached the animal"},
    "status_header_bookings": {"en": "Your camp bookings:"},
    "status_booking_line": {"en": "{ref}: {camp}, {date}, {time}."},
    "status_footer": {"en": "To cancel one of these, reply CANCEL."},
    "status_nothing": {
        "en": (
            "You have no open reports or camp bookings with us. "
            "To report an animal that needs help, send a photo and your location. "
            "To book a camp slot for your pet, reply BOOK."
        ),
    },
    "cancel_choose": {
        "en": (
            "What would you like to cancel?\n{options}\n\n"
            "Reply with the number. To keep everything, just ignore this message."
        ),
    },
    "cancel_case_line": {"en": "Report {case_id} ({state})"},
    "cancel_booking_line": {"en": "Booking {ref}: {camp}, {date}, {time}"},
    "cancel_invalid_choice": {"en": "Please reply with one of the numbers shown."},
    "cancel_nothing": {
        "en": "You have nothing open to cancel. Reply STATUS any time to see your reports and bookings.",
    },
    "cancel_not_found": {
        "en": "I could not find an open report or booking {ref} from this number. Reply STATUS to see yours.",
    },
    "case_cancel_closed": {
        "en": "Case {case_id} is already closed, so there is nothing to cancel.",
    },
    "case_cancel_shared": {
        "en": (
            "Case {case_id} was also reported by someone else, so it stays open for them. "
            "Thank you for letting us know."
        ),
    },
    "case_cancelled": {
        "en": (
            "Case {case_id} is cancelled. Thank you for letting us know. "
            "If the animal needs help again, send a new photo and location."
        ),
    },
    "case_cancelled_team_told": {
        "en": (
            "Case {case_id} is cancelled and we have told the rescue team. "
            "Thank you for letting us know. "
            "If the animal needs help again, send a new photo and location."
        ),
    },
    "team_case_cancelled": {
        "en": "Case {case_id} has been cancelled by the person who reported it. No action needed.",
    },
    "booking_cancelled": {
        "en": (
            "Booking {ref} ({camp}, {date}, {time}) is cancelled, and the place is free for someone else. "
            "Reply BOOK any time to book again."
        ),
    },
    "booking_cancel_closed": {
        "en": "Booking {ref} is no longer active, so there is nothing to cancel.",
    },
    # --- voice notes ---
    "voice_heard": {"en": "I heard: \"{text}\""},
    "voice_noted": {
        "en": (
            "Thank you, I have noted that. To send a team I also need a photo of the animal "
            "and its location (tap attach, then Location)."
        ),
    },
    "voice_not_understood": {
        "en": (
            "Sorry, I could not understand that voice note. "
            "Please type your message, or send a photo and a location."
        ),
    },
    "outside_goa": {
        "en": (
            "That location looks outside Goa. PawSOS covers Goa only. "
            "Please check the pin and send it again."
        ),
    },
    "photo_rejected": {
        "en": "Sorry, I could not read that photo. Please send a JPEG or PNG under 10 MB.",
    },
    "unsupported": {
        "en": "Sorry, I can't read that kind of message yet. Please send a photo and a location.",
    },
}


def render(key: str, language: str = DEFAULT_LANGUAGE, **values: object) -> str:
    """Return the message for `key` in `language`, with {placeholders} filled in.

    Falls back to English when the language has no translation yet.
    Raises KeyError for an unknown key, so typos fail loudly in tests.
    """
    translations = MESSAGES[key]
    template = translations.get(language, translations[DEFAULT_LANGUAGE])
    return template.format(**values)


def triage_message(
    case_id: str,
    urgency: str,
    first_aid: list[str],
    aggressive: bool = False,
    language: str = DEFAULT_LANGUAGE,
) -> str:
    """The message a citizen gets after triage. It always ends with the not-a-diagnosis line."""
    steps = list(first_aid)
    if aggressive:
        steps.insert(0, render("aggression_warning", language))
    return render(
        "triage_result",
        language,
        case_id=case_id,
        urgency_line=render(f"urgency_{urgency}", language),
        steps="\n".join(f"{n}. {step}" for n, step in enumerate(steps, start=1)),
        disclaimer=render("not_a_diagnosis", language),
    )
