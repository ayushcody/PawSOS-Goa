"""Every message PawSOS sends, in one place.

Keys describe the purpose ("ask_location", "case_created"), never the
language. English lives in MESSAGES; Konkani ("kok"), Marathi ("mr") and
Hindi ("hi") live in their own tables at the bottom of this file, one per
language so a fluent reader can check one language at a time. A key without
a translation falls back to English. Copy is short, calm and plain.

WARNING: every Konkani, Marathi and Hindi text in this file was drafted by a
machine (Claude) and has NOT been checked by a fluent reader. Each one MUST be
checked before real use; docs/TRANSLATIONS.md is the checklist. The bite
first-aid texts are safety-critical: check those first.

Messages to rescue teams (team_*, not_a_team, button_*) stay English on
purpose: teams are organisations, their alerts carry case IDs and links, and
WhatsApp button titles are limited to 20 characters.
"""

from datetime import date

DEFAULT_LANGUAGE = "en"
# Every language a person can choose, in the order of the LANGUAGE menu.
LANGUAGES = ("en", "kok", "mr", "hi")

MESSAGES: dict[str, dict[str, str]] = {
    "welcome": {
        "en": (
            "Hello, this is PawSOS Goa. "
            "To report an animal that needs help, send a photo and your location. "
            "To book a sterilisation or vaccination camp slot for your pet, reply BOOK. "
            "Reply STATUS to see your reports, CANCEL to cancel one. "
            "To change the language, reply LANGUAGE."
        ),
    },
    # --- choosing a language (app/contacts.py) ---
    "language_menu": {
        "en": (
            "Choose your language. Reply with a number:\n"
            "1. English\n2. कोंकणी (Konkani)\n3. मराठी (Marathi)\n4. हिंदी (Hindi)"
        ),
    },
    "language_set": {
        "en": "Done. Replies will now be in English. To change the language, reply LANGUAGE.",
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
    # After a typed or spoken description, when one thing is still missing.
    "note_ask_location": {
        "en": (
            "Thank you, noted. Now please share where the animal is: "
            "tap attach, then Location."
        ),
    },
    "note_ask_photo": {
        "en": (
            "Thank you, noted. Now please send a photo of the animal, "
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
    # Sent instead of "case_created" when an open case is close by: the person may be
    # merged into it, so they get no case ID until routing has decided.
    "case_checking_duplicate": {
        "en": (
            "Thank you, your report is in. We are checking whether someone has already "
            "reported this animal, and will send you the case ID in a moment. "
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
    # After a case is resolved: a rating, and the team's photo if they send one.
    "rating_ask": {
        "en": "How did it go with case {case_id}? Your answer helps us improve.",
    },
    # The one-tap button under a request for a location (Telegram; WhatsApp draws its own).
    "location_button": {"en": "Send my location"},
    "rating_good": {"en": "Good"},
    "rating_ok": {"en": "OK"},
    "rating_poor": {"en": "Poor"},
    "rating_thanks": {
        "en": "Thank you, your rating for case {case_id} is recorded.",
    },
    "rating_unavailable": {
        "en": (
            "Sorry, I could not record that. A rating can only come from a person who "
            "reported the case, once it is resolved."
        ),
    },
    "rescue_photo_caption": {
        "en": "Case {case_id}: the team sent this photo after attending to the animal.",
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
    "citizen_staff_assigned": {
        "en": (
            "Update on case {case_id}: our staff have asked {team} to help. "
            "We will message you here when they answer."
        ),
    },
    "citizen_staff_team_unavailable": {
        "en": (
            "Update on case {case_id}: {team} could not take it. "
            "Our staff are finding another team and will message you here."
        ),
    },
    "citizen_cancelled": {
        "en": (
            "Case {case_id} has been closed by PawSOS staff. "
            "If the animal still needs help, please send a new photo and location."
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
    # The reporter's own words, added to the team alert under the line above.
    "team_alert_reporter_says": {"en": 'Reporter says: "{text}"'},
    "team_alert_reporter_voice": {
        "en": 'Reporter says (voice note, may be misheard): "{text}"',
    },
    "team_accepted_ack": {
        "en": "Thank you. Case {case_id} is yours. Tap On site when you reach the animal.",
    },
    "team_on_site_ack": {
        "en": "Noted: on site for case {case_id}. Tap Resolved once the animal has been attended to.",
    },
    "team_resolved_ack": {
        "en": (
            "Case {case_id} is closed. Thank you. If you have a photo of the animal after "
            "the rescue, send it here in the next 30 minutes and we will pass it to the "
            "person who reported it."
        ),
    },
    "team_photo_passed_on": {
        "en": "Thank you. The photo has been passed to everyone who reported case {case_id}.",
    },
    "team_declined_ack": {
        "en": "Understood. Case {case_id} has been passed to the next team.",
    },
    "team_alert_expired": {
        "en": "No answer was received in time, so case {case_id} has been passed to the next team.",
    },
    # A team staff chose on the dashboard: no automatic team follows it.
    "team_declined_ack_staff": {
        "en": "Understood. Case {case_id} has gone back to PawSOS staff, who will find another team.",
    },
    "team_alert_expired_staff": {
        "en": (
            "No answer was received in time, so case {case_id} has gone back to PawSOS staff. "
            "No action needed."
        ),
    },
    "team_case_taken": {
        "en": "Case {case_id} has been taken by another team. No action needed.",
    },
    "team_not_waiting": {
        "en": "Case {case_id} is not waiting for an answer from you.",
    },
    "team_case_reassigned": {
        "en": "Case {case_id} has been passed to another team by PawSOS staff. No action needed.",
    },
    "team_case_cancelled_by_staff": {
        "en": "Case {case_id} has been closed by PawSOS staff. No action needed. Thank you.",
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
            "You will get no more updates on case {case_id}. Someone else also reported "
            "this animal, so the case stays open for them. Thank you for letting us know."
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
    "team_case_cancelled_by_reporter": {
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


def render(key: str, language: str | None = DEFAULT_LANGUAGE, **values: object) -> str:
    """Return the message for `key` in `language`, with {placeholders} filled in.

    Falls back to English when the language has no translation yet.
    Raises KeyError for an unknown key, so typos fail loudly in tests.
    """
    translations = MESSAGES[key]
    template = translations.get(language or DEFAULT_LANGUAGE, translations[DEFAULT_LANGUAGE])
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


# ---------- translations ----------
#
# MACHINE-DRAFTED, NOT YET CHECKED BY A FLUENT READER. See the warning at the
# top of this file and the checklist in docs/TRANSLATIONS.md.
#
# Rules followed: everyday words, not formal ones; every {placeholder} kept
# exactly; words the person must type (BOOK, STATUS, CANCEL, LANGUAGE), case IDs and
# WhatsApp's own "Location" label stay in Latin script. The bot says "we"
# where "I" would need a gendered verb. Keys left out here (team messages, and
# book_camp_line, which has no words) fall back to English.

KOK: dict[str, str] = {  # Konkani, Devanagari script
    "welcome": (
        "नमस्कार, हें PawSOS Goa. "
        "मदत जाय आशिल्ल्या जनावराची खबर दिवपाक, ताचो फोटो आनी तुमचें लोकेशन धाडात. "
        "तुमच्या पाळीव जनावराखातीर नसबंदी वा लसीकरण शिबिरांत वेळ बुक करपाक, BOOK अशें बरोवन धाडात. "
        "तुमच्यो खबरी पळोवंक STATUS, एक रद्द करपाक CANCEL बरोवन धाडात. "
        "भास बदलूंक, LANGUAGE वा भाषा अशें बरोवन धाडात."
    ),
    "language_menu": (
        "तुमची भास वेंचात. नंबर बरोवन धाडात:\n"
        "1. English\n2. कोंकणी (Konkani)\n3. मराठी (Marathi)\n4. हिंदी (Hindi)"
    ),
    "language_set": (
        "जालें. आतां सावन जापो कोंकणींत येतल्यो. "
        "भास बदलूंक, LANGUAGE वा भाषा अशें बरोवन धाडात."
    ),
    "how_to_report": (
        "मदत जाय आशिल्ल्या जनावराची खबर दिवपाक, दोन गजाली धाडात: "
        "जनावराचो फोटो, आनी जाग्याचें लोकेशन (📎 अटॅच दामात, मागीर Location)."
    ),
    "ask_location": (
        "देव बरें करूं, फोटो मेळ्ळो. आतां जनावर खंय आसा तें लोकेशन धाडात: "
        "📎 अटॅच दामात, मागीर Location."
    ),
    "ask_photo": (
        "देव बरें करूं, लोकेशन मेळ्ळें. आतां सुरक्षीत अंतरावयल्यान फोटो काडूंक जमत जाल्यार, "
        "जनावराचो फोटो धाडात."
    ),
    "note_ask_location": (
        "देव बरें करूं, तें बरोवन घेतलां. आतां जनावर खंय आसा तें लोकेशन धाडात: "
        "📎 अटॅच दामात, मागीर Location."
    ),
    "note_ask_photo": (
        "देव बरें करूं, तें बरोवन घेतलां. आतां सुरक्षीत अंतरावयल्यान फोटो काडूंक जमत जाल्यार, "
        "जनावराचो फोटो धाडात."
    ),
    "case_created": (
        "तुमची खबर नोंद जाली. केस नंबर: {case_id}. "
        "आमी सगळ्यांत लागींची टीम सोदतात आनी हांगाच तुमकां मेसेज करतले. "
        "उपकार करून जनावरापसून सुरक्षीत अंतर दवरात."
    ),
    "triage_result": "केस {case_id}: {urgency_line}\n\nतुमी वाट पळयतना:\n{steps}\n\n{disclaimer}",
    "urgency_low": "हें तातडीचें दिसना, तरी लेगीत टीमेक कळयतले.",
    "urgency_medium": "हाचेर बेगीन लक्ष दिवंक जाय.",
    "urgency_high": "हें तातडीचें दिसता.",
    "urgency_critical": "हें खूब तातडीचें दिसता. आमी आतांच एका टीमेक कळयतात.",
    "aggression_warning": "जनावर भियेल्लें वा रागार आशिल्लें आसूं येता. उपकार करून पयस रावात.",
    "not_a_diagnosis": (
        "ही फोटोवयल्यान दिल्ली सर्वसादारण सुरक्षेची सुचोवणी, निदान न्हय. "
        "प्रशिक्षीत टीम जनावराची तपासणी करतली."
    ),
    "triage_needs_review": (
        "केस {case_id}: टीमेचो एक वांगडी तुमचो फोटो पळयतलो. "
        "तोमेरेन, उपकार करून सुरक्षीत अंतर दवरात, हेरांक पयस दवरात, "
        "आनी जनावराक खावंक दिवंक वा हालोवंक नाकात."
    ),
    "zone_assigned": "केस {case_id} {zone} वाठारांत आसा. आमी आतां एका बचाव टीमेक कळयतात.",
    "merged_new_reporter": (
        "देव बरें करूं. ह्या जनावराची खबर आदींच कोणेंय दिल्या, देखून तुमची खबर "
        "केस {case_id} कडेन जोडल्या. उपकार करून आतां सावन तोच केस नंबर वापरात; "
        "तुमकां अपडेट हांगाच मेळटले."
    ),
    "merged_same_reporter": "तुमची नवी खबर तुमच्या केस {case_id} कडेन जोडल्या.",
    "merged_earlier_reporter": (
        "केस {case_id} चो अपडेट: आनीक एका मनशान त्याच जनावराची खबर दिल्या. "
        "आतां एकूण {count} खबरी जाल्यो."
    ),
    "citizen_accepted": "बरी खबर. {team} हांणी केस {case_id} घेतल्या आनी ते वाटेर आसात.",
    "citizen_on_site": "केस {case_id} चो अपडेट: टीम जनावरा कडेन पावल्या.",
    "citizen_resolved": (
        "केस {case_id} चें काम पुराय जालां. टीमेन जनावराची काळजी घेतल्या. "
        "खबर दिल्ल्या खातीर देव बरें करूं."
    ),
    "rating_ask": (
        "केस {case_id} विशीं तुमचो अणभव कसो आसलो? तुमची जाप आमकां सुदारपाक मदत करता."
    ),
    "rating_good": "बरो",
    "rating_ok": "ठीक",
    "rating_poor": "वायट",
    "rating_thanks": "देव बरें करूं, केस {case_id} खातीर तुमचें मत नोंद जालां.",
    "rating_unavailable": (
        "माफ करात, तें नोंद करपाक जालें ना. मत फकत केसची खबर दिवपी मनशाकडल्यान, "
        "केस पुराय जाल्या उपरांत घेतात."
    ),
    "rescue_photo_caption": "केस {case_id}: जनावराची काळजी घेतल्या उपरांत टीमेन हो फोटो धाडला.",
    "citizen_escalated": (
        "केस {case_id} चो अपडेट: पयल्या टीमेक ही केस घेवंक जमलें ना, "
        "देखून आमी फुडल्या टीमेक कळयलां."
    ),
    "citizen_no_team_yet": (
        "केस {case_id} चो अपडेट: आमकां अजून खंयचीच टीम मेळूंक ना. "
        "आमी यत्न करीत आसात आनी हांगाच तुमकां मेसेज करतले."
    ),
    "bite_first_aid": (
        "अशें जालें हाचें दुख्ख दिसता. उपकार करून आतांच हें करात:\n"
        "1. जखम साबू लावन व्हांवत्या उदकान 15 मिनटां धुवात.\n"
        "2. जखमेर तेल, हळद, मिरसांग वा खंयचोच घरगुती उपाय लावंक नाकात.\n"
        "3. जखम ल्हान आसली तरी, आयजच अँटी-रेबीज उपचारा खातीर आरोग्य केंद्राक वचात.\n\n"
        "तुमचें लोकेशन धाडात (📎 अटॅच दामात, मागीर Location), आमी आमच्या वळेरेंतलें "
        "सगळ्यांत लागींचें आरोग्य केंद्र सोदून दितले.\n\n"
        "ही सर्वसादारण प्रथमोपचाराची सुचोवणी, वैजकी सल्लो न्हय."
    ),
    "bite_nearest_centre": (
        "आमच्या वळेरेंतलें सगळ्यांत लागींचें आरोग्य केंद्र: {name}, सुमार {km} किमी पयस.\n"
        "{map_link}\n"
        "आयजच वचात आनी अँटी-रेबीज उपचार मागात. आमची वळेरी अजून तपासूंक ना, "
        "देखून जमत जाल्यार पयलीं फोन करात.\n\n"
        "जनावर अजून लागसार आसल्यार, ताचो फोटो आनी लोकेशन धाडात, आमी टीमेक कळयतले."
    ),
    "bite_no_centre": (
        "उपकार करून आयजच लागींच्या सरकारी हॉस्पिटलांत वचात आनी अँटी-रेबीज उपचार मागात.\n\n"
        "जनावर अजून लागसार आसल्यार, ताचो फोटो आनी लोकेशन धाडात, आमी टीमेक कळयतले."
    ),
    "book_choose_camp": (
        "मुखार येवपी शिबिरां:\n{options}\n\n"
        "शिबिराचो नंबर बरोवन धाडात, वा रद्द करपाक CANCEL बरयात."
    ),
    "book_no_camps": "आतां बुक करपाक खंयचेंच शिबीर ना. उपकार करून कांय दिसांनी परत पळयात.",
    "book_choose_slot": (
        "{camp}, {date}. मेकळे वेळ:\n{options}\n\n"
        "वेळेचो नंबर बरोवन धाडात, वा रद्द करपाक CANCEL बरयात."
    ),
    "book_slot_line": "{time} ({left} जागो उरल्यात)",
    "book_camp_full": "माफ करात, {camp} पुराय बुक जालां. हेर शिबिरां पळोवंक BOOK बरोवन धाडात.",
    "book_slot_full": "माफ करात, तो वेळ आतांच भरलो.",
    "book_invalid_choice": (
        "उपकार करून दाखयल्ल्या नंबरां मदलो एक नंबर बरोवन धाडात, वा रद्द करपाक CANCEL बरयात."
    ),
    "book_cancelled": "कांय हरकत ना, कांयच बुक जालें ना. परत सुरू करपाक BOOK बरोवन धाडात.",
    "book_already": "{camp} हांगा तुमचें आदींच बुकिंग आसा: {ref}, {date}, {time}.",
    "book_confirmed": (
        "बुक जालें. तुमचो रेफरन्स नंबर {ref}.\n"
        "{camp}\n{date}, {time}\n{venue}\n\n"
        "उपकार करून तुमच्या पाळीव जनावराक पट्टो घालून वा पिंजऱ्यांत घेवन येयात. "
        "आदल्या दिसा आमी तुमकां याद करून दितले."
    ),
    "book_reminder": (
        "याद करून दिवप: तुमच्या पाळीव जनावराचो शिबिरांतलो वेळ लागीं पावला.\n"
        "{camp}\n{date}, {time}\n{venue}\n"
        "रेफरन्स {ref}."
    ),
    "voice_heard": "हांवें आयकलें: \"{text}\"",
    "voice_noted": (
        "देव बरें करूं, हांवें तें बरोवन घेतलां. टीम धाडपाक जनावराचो फोटो "
        "आनी ताचें लोकेशन लेगीत जाय (📎 अटॅच दामात, मागीर Location)."
    ),
    "voice_not_understood": (
        "माफ करात, तो व्हॉइस नोट समजलो ना. "
        "उपकार करून तुमचो मेसेज टायप करात, वा फोटो आनी लोकेशन धाडात."
    ),
    "outside_goa": (
        "तें लोकेशन गोंया भायर दिसता. PawSOS फकत गोंयांत काम करता. "
        "उपकार करून पिन तपासात आनी परत धाडात."
    ),
    "photo_rejected": (
        "माफ करात, तो फोटो उगडूंक जमलो ना. उपकार करून 10 MB परस ल्हान JPEG वा PNG फोटो धाडात."
    ),
    "unsupported": "माफ करात, असलो मेसेज अजून वाचूंक जमना. उपकार करून फोटो आनी लोकेशन धाडात.",
    # added for staff-assigned expiry
    "citizen_staff_team_unavailable": (
        "केस {case_id} चो अपडेट: {team} हांकां ही केस घेवंक जमलें ना. "
        "आमचे स्टाफ दुसरी टीम सोदतात आनी हांगाच तुमकां मेसेज करतले."
    ),
    # added for the duplicate check
    "case_checking_duplicate": (
        "देव बरें करूं, तुमची खबर मेळ्ळी. ह्या जनावराची खबर आदींच कोणें दिल्या काय तें आमी "
        "तपासतात, आनी थोड्या वेळान तुमकां केस नंबर धाडटले. "
        "उपकार करून जनावरापसून सुरक्षीत अंतर दवरात."
    ),
    # --- staff actions, STATUS and CANCEL ---
    "citizen_staff_assigned": (
        "केस {case_id} चो अपडेट: आमच्या कर्मचाऱ्यांनी {team} हांकां मदत करपाक सांगलां. "
        "तांची जाप आयली काय आमी हांगाच तुमकां मेसेज करतले."
    ),
    "citizen_cancelled": (
        "PawSOS च्या कर्मचाऱ्यांनी केस {case_id} बंद केल्या. "
        "जनावराक अजून मदत जाय जाल्यार, उपकार करून नवो फोटो आनी लोकेशन धाडात."
    ),
    "status_header_cases": "तुमच्यो चालू खबरी:",
    "status_case_line": "{case_id}, {when} खबर दिल्ली: {state}.",
    "status_case_line_zone": "{case_id}, {when} खबर दिल्ली, {zone} वाठार: {state}.",
    "status_state_received": "खबर मेळ्ळी, आमी फोटो पळयतात",
    "status_state_finding_team": "आमी बचाव टीम सोदतात",
    "status_state_team_alerted": "बचाव टीमेक कळयलां",
    "status_state_still_looking": "आमी अजून एका टीमेक संपर्क करपाचो यत्न करीत आसात",
    "status_state_accepted": "{team} हांणी केस घेतल्या आनी ते वाटेर आसात",
    "status_state_on_site": "{team} जनावरा कडेन पावल्या",
    "status_header_bookings": "शिबिरांतलीं तुमचीं बुकिंगां:",
    "status_booking_line": "{ref}: {camp}, {date}, {time}.",
    "status_footer": "हातूंतलें एक रद्द करपाक, CANCEL बरोवन धाडात.",
    "status_nothing": (
        "आमचे कडेन तुमची खंयचीच चालू खबर वा शिबीर बुकिंग ना. "
        "मदत जाय आशिल्ल्या जनावराची खबर दिवपाक, ताचो फोटो आनी तुमचें लोकेशन धाडात. "
        "तुमच्या पाळीव जनावराखातीर शिबिरांत वेळ बुक करपाक, BOOK अशें बरोवन धाडात."
    ),
    "cancel_choose": (
        "तुमकां कितें रद्द करपाचें आसा?\n{options}\n\n"
        "नंबर बरोवन धाडात. कांयच रद्द करपाचें ना जाल्यार, हो मेसेज सोडून दियात."
    ),
    "cancel_case_line": "खबर {case_id} ({state})",
    "cancel_booking_line": "बुकिंग {ref}: {camp}, {date}, {time}",
    "cancel_invalid_choice": "उपकार करून दाखयल्ल्या नंबरां मदलो एक नंबर बरोवन धाडात.",
    "cancel_nothing": (
        "रद्द करपाक तुमचें कांयच चालू ना. "
        "तुमच्यो खबरी आनी बुकिंगां पळोवंक, केन्नाय STATUS बरोवन धाडात."
    ),
    "cancel_not_found": (
        "ह्या नंबरावयल्यान दिल्ली {ref} ही चालू खबर वा बुकिंग आमकां मेळूंक ना. "
        "तुमच्यो खबरी आनी बुकिंगां पळोवंक STATUS बरोवन धाडात."
    ),
    "case_cancel_closed": "केस {case_id} आदींच बंद जाल्या, देखून रद्द करपाक कांयच ना.",
    "case_cancel_shared": (
        "केस {case_id} विशीं तुमकां आतां मेसेज येवचे नात. ह्या जनावराची खबर आनीक कोणेंय "
        "दिल्या, देखून केस तांचे खातीर चालू उरतली. आमकां कळयल्ल्या खातीर देव बरें करूं."
    ),
    "case_cancelled": (
        "केस {case_id} रद्द जाल्या. आमकां कळयल्ल्या खातीर देव बरें करूं. "
        "जनावराक परत मदत जाय जाल्यार, नवो फोटो आनी लोकेशन धाडात."
    ),
    "case_cancelled_team_told": (
        "केस {case_id} रद्द जाल्या आनी आमी बचाव टीमेक कळयलां. "
        "आमकां कळयल्ल्या खातीर देव बरें करूं. "
        "जनावराक परत मदत जाय जाल्यार, नवो फोटो आनी लोकेशन धाडात."
    ),
    "booking_cancelled": (
        "बुकिंग {ref} ({camp}, {date}, {time}) रद्द जालें, आनी ती जागा आतां हेरांक मेकळी जाली. "
        "परत बुक करपाक, केन्नाय BOOK बरोवन धाडात."
    ),
    "booking_cancel_closed": "बुकिंग {ref} आतां चालू ना, देखून रद्द करपाक कांयच ना.",
}

MR: dict[str, str] = {  # Marathi
    "welcome": (
        "नमस्कार, हे PawSOS Goa आहे. "
        "मदतीची गरज असलेल्या प्राण्याची माहिती देण्यासाठी, त्याचा फोटो आणि तुमचे लोकेशन पाठवा. "
        "तुमच्या पाळीव प्राण्यासाठी नसबंदी किंवा लसीकरण शिबिरात वेळ बुक करण्यासाठी, "
        "BOOK असे लिहून पाठवा. "
        "तुमचे रिपोर्ट पाहण्यासाठी STATUS, एखादा रद्द करण्यासाठी CANCEL असे लिहून पाठवा. "
        "भाषा बदलण्यासाठी, LANGUAGE किंवा भाषा असे लिहून पाठवा."
    ),
    "language_menu": (
        "तुमची भाषा निवडा. नंबर लिहून पाठवा:\n"
        "1. English\n2. कोंकणी (Konkani)\n3. मराठी (Marathi)\n4. हिंदी (Hindi)"
    ),
    "language_set": (
        "झाले. आतापासून उत्तरे मराठीत येतील. "
        "भाषा बदलण्यासाठी, LANGUAGE किंवा भाषा असे लिहून पाठवा."
    ),
    "how_to_report": (
        "मदतीची गरज असलेल्या प्राण्याची माहिती देण्यासाठी दोन गोष्टी पाठवा: "
        "प्राण्याचा फोटो, आणि ठिकाणाचे लोकेशन (📎 अटॅच वर टॅप करा, मग Location)."
    ),
    "ask_location": (
        "धन्यवाद, फोटो मिळाला. आता प्राणी कुठे आहे ते लोकेशन पाठवा: "
        "📎 अटॅच वर टॅप करा, मग Location."
    ),
    "ask_photo": (
        "धन्यवाद, लोकेशन मिळाले. आता सुरक्षित अंतरावरून फोटो काढता येत असेल, "
        "तर प्राण्याचा फोटो पाठवा."
    ),
    "note_ask_location": (
        "धन्यवाद, ते नोंदवून घेतले आहे. आता प्राणी कुठे आहे ते लोकेशन पाठवा: "
        "📎 अटॅच वर टॅप करा, मग Location."
    ),
    "note_ask_photo": (
        "धन्यवाद, ते नोंदवून घेतले आहे. आता सुरक्षित अंतरावरून फोटो काढता येत असेल, "
        "तर प्राण्याचा फोटो पाठवा."
    ),
    "case_created": (
        "तुमचा रिपोर्ट नोंदवला आहे. केस नंबर: {case_id}. "
        "आम्ही सर्वात जवळची टीम शोधत आहोत आणि इथेच तुम्हाला मेसेज करू. "
        "कृपया प्राण्यापासून सुरक्षित अंतर ठेवा."
    ),
    "triage_result": "केस {case_id}: {urgency_line}\n\nतोपर्यंत हे करा:\n{steps}\n\n{disclaimer}",
    "urgency_low": "हे तातडीचे वाटत नाही, तरीही टीमला कळवले जाईल.",
    "urgency_medium": "याकडे लवकर लक्ष देणे गरजेचे आहे.",
    "urgency_high": "हे तातडीचे वाटते.",
    "urgency_critical": "हे खूप तातडीचे वाटते. आम्ही आत्ताच टीमला कळवत आहोत.",
    "aggression_warning": "प्राणी घाबरलेला किंवा चिडलेला असू शकतो. कृपया लांब राहा.",
    "not_a_diagnosis": (
        "ही फोटोवरून दिलेली सर्वसाधारण सुरक्षेची सूचना आहे, निदान नाही. "
        "प्रशिक्षित टीम प्राण्याची तपासणी करेल."
    ),
    "triage_needs_review": (
        "केस {case_id}: टीममधील एक सदस्य तुमचा फोटो पाहील. "
        "तोपर्यंत कृपया सुरक्षित अंतर ठेवा, इतरांना लांब ठेवा, "
        "आणि प्राण्याला खायला देऊ नका किंवा हलवू नका."
    ),
    "zone_assigned": "केस {case_id} {zone} भागात आहे. आम्ही आता बचाव टीमला कळवत आहोत.",
    "merged_new_reporter": (
        "धन्यवाद. या प्राण्याची माहिती आधीच कोणीतरी दिली आहे, म्हणून तुमचा रिपोर्ट "
        "केस {case_id} मध्ये जोडला आहे. कृपया आतापासून हाच केस नंबर वापरा; "
        "पुढचे अपडेट तुम्हाला इथेच मिळतील."
    ),
    "merged_same_reporter": "तुमचा नवीन रिपोर्ट तुमच्या केस {case_id} मध्ये जोडला आहे.",
    "merged_earlier_reporter": (
        "केस {case_id} बद्दल अपडेट: आणखी एका व्यक्तीने याच प्राण्याची माहिती दिली आहे. "
        "आता एकूण {count} रिपोर्ट झाले."
    ),
    "citizen_accepted": "चांगली बातमी. {team} ने केस {case_id} स्वीकारली आहे आणि ते निघाले आहेत.",
    "citizen_on_site": "केस {case_id} बद्दल अपडेट: टीम प्राण्याजवळ पोहोचली आहे.",
    "citizen_resolved": (
        "केस {case_id} पूर्ण झाली आहे. टीमने प्राण्याची काळजी घेतली आहे. "
        "माहिती दिल्याबद्दल धन्यवाद."
    ),
    "rating_ask": (
        "केस {case_id} बद्दल तुमचा अनुभव कसा होता? तुमच्या उत्तरामुळे आम्हाला सुधारणा करता येते."
    ),
    "rating_good": "चांगला",
    "rating_ok": "ठीक",
    "rating_poor": "वाईट",
    "rating_thanks": "धन्यवाद, केस {case_id} साठी तुमचे मत नोंदवले आहे.",
    "rating_unavailable": (
        "माफ करा, ते नोंदवता आले नाही. मत फक्त केसची माहिती देणाऱ्या व्यक्तीकडून, "
        "केस पूर्ण झाल्यावर घेतले जाते."
    ),
    "rescue_photo_caption": "केस {case_id}: प्राण्याची काळजी घेतल्यानंतर टीमने हा फोटो पाठवला आहे.",
    "citizen_escalated": (
        "केस {case_id} बद्दल अपडेट: पहिली टीम केस घेऊ शकली नाही, "
        "म्हणून आम्ही पुढच्या टीमला कळवले आहे."
    ),
    "citizen_no_team_yet": (
        "केस {case_id} बद्दल अपडेट: अजून कोणत्याही टीमशी संपर्क झालेला नाही. "
        "आम्ही प्रयत्न करत आहोत आणि इथेच तुम्हाला मेसेज करू."
    ),
    "bite_first_aid": (
        "हे घडले याचे वाईट वाटते. कृपया आत्ता हे करा:\n"
        "1. जखम साबण आणि वाहत्या पाण्याने 15 मिनिटे धुवा.\n"
        "2. जखमेवर तेल, हळद, मिरची किंवा कोणताही घरगुती उपाय लावू नका.\n"
        "3. जखम लहान असली तरी, आजच अँटी-रेबीज उपचारासाठी आरोग्य केंद्रात जा.\n\n"
        "तुमचे लोकेशन पाठवा (📎 अटॅच वर टॅप करा, मग Location), आम्ही आमच्या यादीतील "
        "सर्वात जवळचे आरोग्य केंद्र शोधू.\n\n"
        "ही सर्वसाधारण प्रथमोपचाराची माहिती आहे, वैद्यकीय सल्ला नाही."
    ),
    "bite_nearest_centre": (
        "आमच्या यादीतील सर्वात जवळचे आरोग्य केंद्र: {name}, सुमारे {km} किमी दूर.\n"
        "{map_link}\n"
        "आजच जा आणि अँटी-रेबीज उपचार मागा. आमची यादी अजून तपासलेली नाही, "
        "म्हणून शक्य असल्यास आधी फोन करा.\n\n"
        "प्राणी अजून जवळपास असल्यास, त्याचा फोटो आणि लोकेशन पाठवा, आम्ही टीमला कळवू."
    ),
    "bite_no_centre": (
        "कृपया आजच जवळच्या सरकारी रुग्णालयात जा आणि अँटी-रेबीज उपचार मागा.\n\n"
        "प्राणी अजून जवळपास असल्यास, त्याचा फोटो आणि लोकेशन पाठवा, आम्ही टीमला कळवू."
    ),
    "book_choose_camp": (
        "पुढील शिबिरे:\n{options}\n\n"
        "शिबिराचा नंबर लिहून पाठवा, किंवा रद्द करण्यासाठी CANCEL लिहा."
    ),
    "book_no_camps": "सध्या बुक करण्यासाठी कोणतेही शिबीर नाही. कृपया काही दिवसांनी पुन्हा पाहा.",
    "book_choose_slot": (
        "{camp}, {date}. उपलब्ध वेळा:\n{options}\n\n"
        "वेळेचा नंबर लिहून पाठवा, किंवा रद्द करण्यासाठी CANCEL लिहा."
    ),
    "book_slot_line": "{time} ({left} जागा शिल्लक)",
    "book_camp_full": "माफ करा, {camp} पूर्ण बुक झाले आहे. इतर शिबिरे पाहण्यासाठी BOOK असे लिहून पाठवा.",
    "book_slot_full": "माफ करा, ती वेळ आत्ताच भरली.",
    "book_invalid_choice": (
        "कृपया दाखवलेल्या नंबरांपैकी एक नंबर लिहून पाठवा, किंवा रद्द करण्यासाठी CANCEL लिहा."
    ),
    "book_cancelled": (
        "काही हरकत नाही, काहीही बुक झाले नाही. पुन्हा सुरू करण्यासाठी BOOK असे लिहून पाठवा."
    ),
    "book_already": "{camp} येथे तुमचे आधीच बुकिंग आहे: {ref}, {date}, {time}.",
    "book_confirmed": (
        "बुक झाले. तुमचा रेफरन्स नंबर {ref} आहे.\n"
        "{camp}\n{date}, {time}\n{venue}\n\n"
        "कृपया तुमच्या पाळीव प्राण्याला पट्ट्याने बांधून किंवा पिंजऱ्यात घेऊन या. "
        "आम्ही आदल्या दिवशी आठवण करून देऊ."
    ),
    "book_reminder": (
        "आठवण: तुमच्या पाळीव प्राण्याची शिबिरातील वेळ जवळ आली आहे.\n"
        "{camp}\n{date}, {time}\n{venue}\n"
        "रेफरन्स {ref}."
    ),
    "voice_heard": "मी ऐकले: \"{text}\"",
    "voice_noted": (
        "धन्यवाद, मी ते नोंदवून घेतले आहे. टीम पाठवण्यासाठी प्राण्याचा फोटो आणि त्याचे "
        "लोकेशनही हवे आहे (📎 अटॅच वर टॅप करा, मग Location)."
    ),
    "voice_not_understood": (
        "माफ करा, तो व्हॉइस नोट समजला नाही. "
        "कृपया तुमचा मेसेज टाइप करा, किंवा फोटो आणि लोकेशन पाठवा."
    ),
    "outside_goa": (
        "ते लोकेशन गोव्याबाहेरचे दिसते. PawSOS फक्त गोव्यासाठी आहे. "
        "कृपया पिन तपासा आणि पुन्हा पाठवा."
    ),
    "photo_rejected": (
        "माफ करा, तो फोटो उघडता आला नाही. कृपया 10 MB पेक्षा लहान JPEG किंवा PNG फोटो पाठवा."
    ),
    "unsupported": "माफ करा, असा मेसेज अजून वाचता येत नाही. कृपया फोटो आणि लोकेशन पाठवा.",
    # added for staff-assigned expiry
    "citizen_staff_team_unavailable": (
        "केस {case_id} बद्दल अपडेट: {team} ही केस घेऊ शकले नाहीत. "
        "आमचे कर्मचारी दुसरी टीम शोधत आहेत आणि इथेच तुम्हाला मेसेज करतील."
    ),
    # added for the duplicate check
    "case_checking_duplicate": (
        "धन्यवाद, तुमचा रिपोर्ट मिळाला. या प्राण्याची माहिती आधीच कोणी दिली आहे का "
        "हे आम्ही तपासत आहोत, आणि थोड्याच वेळात तुम्हाला केस नंबर पाठवू. "
        "कृपया प्राण्यापासून सुरक्षित अंतर ठेवा."
    ),
    # --- staff actions, STATUS and CANCEL ---
    "citizen_staff_assigned": (
        "केस {case_id} बद्दल अपडेट: आमच्या कर्मचाऱ्यांनी {team} ला मदत करण्यास सांगितले आहे. "
        "त्यांचे उत्तर आले की आम्ही इथेच तुम्हाला मेसेज करू."
    ),
    "citizen_cancelled": (
        "PawSOS च्या कर्मचाऱ्यांनी केस {case_id} बंद केली आहे. "
        "प्राण्याला अजूनही मदतीची गरज असल्यास, कृपया नवीन फोटो आणि लोकेशन पाठवा."
    ),
    "status_header_cases": "तुमचे चालू रिपोर्ट:",
    "status_case_line": "{case_id}, {when} रोजी नोंदवला: {state}.",
    "status_case_line_zone": "{case_id}, {when} रोजी नोंदवला, {zone} भाग: {state}.",
    "status_state_received": "रिपोर्ट मिळाला, आम्ही फोटो पाहत आहोत",
    "status_state_finding_team": "आम्ही बचाव टीम शोधत आहोत",
    "status_state_team_alerted": "बचाव टीमला कळवले आहे",
    "status_state_still_looking": "आम्ही अजूनही टीमशी संपर्क करण्याचा प्रयत्न करत आहोत",
    "status_state_accepted": "{team} ने केस स्वीकारली आहे आणि ते निघाले आहेत",
    "status_state_on_site": "{team} प्राण्याजवळ पोहोचली आहे",
    "status_header_bookings": "शिबिरातील तुमचे बुकिंग:",
    "status_booking_line": "{ref}: {camp}, {date}, {time}.",
    "status_footer": "यापैकी एखादे रद्द करण्यासाठी, CANCEL असे लिहून पाठवा.",
    "status_nothing": (
        "आमच्याकडे तुमचा कोणताही चालू रिपोर्ट किंवा शिबिर बुकिंग नाही. "
        "मदतीची गरज असलेल्या प्राण्याची माहिती देण्यासाठी, त्याचा फोटो आणि तुमचे लोकेशन पाठवा. "
        "तुमच्या पाळीव प्राण्यासाठी शिबिरात वेळ बुक करण्यासाठी, BOOK असे लिहून पाठवा."
    ),
    "cancel_choose": (
        "तुम्हाला काय रद्द करायचे आहे?\n{options}\n\n"
        "नंबर लिहून पाठवा. काहीही रद्द करायचे नसल्यास, या मेसेजकडे दुर्लक्ष करा."
    ),
    "cancel_case_line": "रिपोर्ट {case_id} ({state})",
    "cancel_booking_line": "बुकिंग {ref}: {camp}, {date}, {time}",
    "cancel_invalid_choice": "कृपया दाखवलेल्या नंबरांपैकी एक नंबर लिहून पाठवा.",
    "cancel_nothing": (
        "रद्द करण्यासारखे तुमचे काहीही चालू नाही. "
        "तुमचे रिपोर्ट आणि बुकिंग पाहण्यासाठी, कधीही STATUS असे लिहून पाठवा."
    ),
    "cancel_not_found": (
        "या नंबरवरून {ref} हा चालू रिपोर्ट किंवा बुकिंग आम्हाला सापडले नाही. "
        "तुमचे रिपोर्ट आणि बुकिंग पाहण्यासाठी STATUS असे लिहून पाठवा."
    ),
    "case_cancel_closed": "केस {case_id} आधीच बंद झाली आहे, म्हणून रद्द करण्यासारखे काहीही नाही.",
    "case_cancel_shared": (
        "केस {case_id} बद्दल तुम्हाला यापुढे मेसेज येणार नाहीत. या प्राण्याची माहिती आणखी "
        "कोणीतरी दिली आहे, म्हणून केस त्यांच्यासाठी चालू राहील. आम्हाला कळवल्याबद्दल धन्यवाद."
    ),
    "case_cancelled": (
        "केस {case_id} रद्द झाली आहे. आम्हाला कळवल्याबद्दल धन्यवाद. "
        "प्राण्याला पुन्हा मदत लागल्यास, नवीन फोटो आणि लोकेशन पाठवा."
    ),
    "case_cancelled_team_told": (
        "केस {case_id} रद्द झाली आहे आणि आम्ही बचाव टीमला कळवले आहे. "
        "आम्हाला कळवल्याबद्दल धन्यवाद. "
        "प्राण्याला पुन्हा मदत लागल्यास, नवीन फोटो आणि लोकेशन पाठवा."
    ),
    "booking_cancelled": (
        "बुकिंग {ref} ({camp}, {date}, {time}) रद्द झाले आहे, आणि ती जागा आता दुसऱ्या कोणासाठी "
        "मोकळी आहे. पुन्हा बुक करण्यासाठी, कधीही BOOK असे लिहून पाठवा."
    ),
    "booking_cancel_closed": "बुकिंग {ref} आता चालू नाही, म्हणून रद्द करण्यासारखे काहीही नाही.",
}

HI: dict[str, str] = {  # Hindi
    "welcome": (
        "नमस्ते, यह PawSOS Goa है। "
        "किसी जानवर को मदद चाहिए, तो उसकी फ़ोटो और अपनी लोकेशन भेजें। "
        "अपने पालतू जानवर के लिए नसबंदी या टीकाकरण कैंप में समय बुक करने के लिए BOOK लिखकर भेजें। "
        "अपनी रिपोर्ट देखने के लिए STATUS, कोई रद्द करने के लिए CANCEL लिखकर भेजें। "
        "भाषा बदलने के लिए LANGUAGE या भाषा लिखकर भेजें।"
    ),
    "language_menu": (
        "अपनी भाषा चुनें। नंबर लिखकर भेजें:\n"
        "1. English\n2. कोंकणी (Konkani)\n3. मराठी (Marathi)\n4. हिंदी (Hindi)"
    ),
    "language_set": (
        "हो गया। अब से जवाब हिंदी में आएँगे। भाषा बदलने के लिए LANGUAGE या भाषा लिखकर भेजें।"
    ),
    "how_to_report": (
        "किसी जानवर को मदद चाहिए, तो दो चीज़ें भेजें: "
        "जानवर की फ़ोटो, और जगह की लोकेशन (📎 अटैच पर टैप करें, फिर Location)।"
    ),
    "ask_location": (
        "धन्यवाद, फ़ोटो मिल गई। अब जानवर जहाँ है, उसकी लोकेशन भेजें: "
        "📎 अटैच पर टैप करें, फिर Location।"
    ),
    "ask_photo": (
        "धन्यवाद, लोकेशन मिल गई। अब अगर सुरक्षित दूरी से फ़ोटो ले सकें, "
        "तो जानवर की फ़ोटो भेजें।"
    ),
    "note_ask_location": (
        "धन्यवाद, यह नोट कर लिया है। अब जानवर जहाँ है, उसकी लोकेशन भेजें: "
        "📎 अटैच पर टैप करें, फिर Location।"
    ),
    "note_ask_photo": (
        "धन्यवाद, यह नोट कर लिया है। अब अगर सुरक्षित दूरी से फ़ोटो ले सकें, "
        "तो जानवर की फ़ोटो भेजें।"
    ),
    "case_created": (
        "आपकी रिपोर्ट दर्ज हो गई है। केस नंबर: {case_id}. "
        "हम सबसे पास की टीम ढूँढ रहे हैं और यहीं आपको मैसेज करेंगे। "
        "कृपया जानवर से सुरक्षित दूरी बनाए रखें।"
    ),
    "triage_result": "केस {case_id}: {urgency_line}\n\nजब तक टीम आए:\n{steps}\n\n{disclaimer}",
    "urgency_low": "यह तुरंत वाला मामला नहीं लगता, फिर भी टीम को बताया जाएगा।",
    "urgency_medium": "इस पर जल्दी ध्यान देना होगा।",
    "urgency_high": "लगता है इसे जल्दी मदद चाहिए।",
    "urgency_critical": "लगता है इसे तुरंत मदद चाहिए। हम अभी एक टीम को बता रहे हैं।",
    "aggression_warning": "जानवर डरा हुआ या गुस्से में हो सकता है। कृपया दूर रहें।",
    "not_a_diagnosis": (
        "यह फ़ोटो देखकर दी गई आम सुरक्षा सलाह है, डायग्नोसिस (निदान) नहीं। "
        "ट्रेनिंग वाली टीम जानवर की जाँच करेगी।"
    ),
    "triage_needs_review": (
        "केस {case_id}: टीम का एक सदस्य आपकी फ़ोटो देखेगा। "
        "तब तक कृपया सुरक्षित दूरी रखें, दूसरों को दूर रखें, "
        "और जानवर को न कुछ खिलाएँ, न उसे हिलाएँ।"
    ),
    "zone_assigned": "केस {case_id} {zone} इलाके में है। हम अभी एक रेस्क्यू टीम को बता रहे हैं।",
    "merged_new_reporter": (
        "धन्यवाद। इस जानवर की रिपोर्ट पहले ही हो चुकी है, इसलिए आपकी रिपोर्ट "
        "केस {case_id} में जोड़ दी गई है। कृपया अब से यही केस नंबर इस्तेमाल करें; "
        "आपको अपडेट यहीं मिलेंगे।"
    ),
    "merged_same_reporter": "आपकी नई रिपोर्ट आपके केस {case_id} में जोड़ दी गई है।",
    "merged_earlier_reporter": (
        "केस {case_id} का अपडेट: एक और व्यक्ति ने इसी जानवर की रिपोर्ट की है। "
        "अब कुल {count} रिपोर्ट हो गई हैं।"
    ),
    "citizen_accepted": "अच्छी ख़बर। {team} ने केस {case_id} ले लिया है और वे रास्ते में हैं।",
    "citizen_on_site": "केस {case_id} का अपडेट: टीम जानवर तक पहुँच गई है।",
    "citizen_resolved": (
        "केस {case_id} पूरा हो गया है। टीम ने जानवर की देखभाल कर दी है। "
        "रिपोर्ट करने के लिए धन्यवाद।"
    ),
    "rating_ask": (
        "केस {case_id} में आपका अनुभव कैसा रहा? आपके जवाब से हमें सुधार में मदद मिलती है।"
    ),
    "rating_good": "अच्छा",
    "rating_ok": "ठीक",
    "rating_poor": "ख़राब",
    "rating_thanks": "धन्यवाद, केस {case_id} के लिए आपकी राय दर्ज हो गई है।",
    "rating_unavailable": (
        "माफ़ कीजिए, यह दर्ज नहीं हो सका। राय सिर्फ़ केस की रिपोर्ट करने वाले से, "
        "केस पूरा होने के बाद ली जाती है।"
    ),
    "rescue_photo_caption": "केस {case_id}: जानवर की देखभाल के बाद टीम ने यह फ़ोटो भेजी है।",
    "citizen_escalated": (
        "केस {case_id} का अपडेट: पहली टीम यह केस नहीं ले सकी, "
        "इसलिए हमने अगली टीम को बता दिया है।"
    ),
    "citizen_no_team_yet": (
        "केस {case_id} का अपडेट: अभी तक किसी टीम से संपर्क नहीं हो पाया है। "
        "हम कोशिश कर रहे हैं और यहीं आपको मैसेज करेंगे।"
    ),
    "bite_first_aid": (
        "यह सुनकर दुख हुआ। कृपया अभी यह करें:\n"
        "1. घाव को साबुन और बहते पानी से 15 मिनट तक धोएँ।\n"
        "2. घाव पर तेल, हल्दी, मिर्च या कोई भी घरेलू नुस्खा न लगाएँ।\n"
        "3. घाव छोटा हो तब भी, आज ही एंटी-रेबीज़ इलाज के लिए स्वास्थ्य केंद्र जाएँ।\n\n"
        "अपनी लोकेशन भेजें (📎 अटैच पर टैप करें, फिर Location), हम अपनी सूची में से "
        "सबसे पास का स्वास्थ्य केंद्र ढूँढेंगे।\n\n"
        "यह आम फ़र्स्ट-एड (प्राथमिक उपचार) की जानकारी है, डॉक्टरी सलाह नहीं।"
    ),
    "bite_nearest_centre": (
        "हमारी सूची में सबसे पास का स्वास्थ्य केंद्र: {name}, लगभग {km} किमी दूर।\n"
        "{map_link}\n"
        "आज ही जाएँ और एंटी-रेबीज़ इलाज माँगें। हमारी सूची अभी जाँची नहीं गई है, "
        "इसलिए हो सके तो जाने से पहले फ़ोन कर लें।\n\n"
        "अगर जानवर अभी भी आसपास है, तो उसकी फ़ोटो और लोकेशन भेजें, हम एक टीम को बता देंगे।"
    ),
    "bite_no_centre": (
        "कृपया आज ही सबसे पास के सरकारी अस्पताल जाएँ और एंटी-रेबीज़ इलाज माँगें।\n\n"
        "अगर जानवर अभी भी आसपास है, तो उसकी फ़ोटो और लोकेशन भेजें, हम एक टीम को बता देंगे।"
    ),
    "book_choose_camp": (
        "आने वाले कैंप:\n{options}\n\n"
        "कैंप का नंबर लिखकर भेजें, या रद्द करने के लिए CANCEL लिखें।"
    ),
    "book_no_camps": "अभी बुक करने के लिए कोई कैंप नहीं है। कृपया कुछ दिनों में फिर देखें।",
    "book_choose_slot": (
        "{camp}, {date}. खाली समय:\n{options}\n\n"
        "समय का नंबर लिखकर भेजें, या रद्द करने के लिए CANCEL लिखें।"
    ),
    "book_slot_line": "{time} ({left} जगह बाकी)",
    "book_camp_full": (
        "माफ़ कीजिए, {camp} पूरा बुक हो चुका है। दूसरे कैंप देखने के लिए BOOK लिखकर भेजें।"
    ),
    "book_slot_full": "माफ़ कीजिए, यह समय अभी-अभी भर गया।",
    "book_invalid_choice": (
        "कृपया दिखाए गए नंबरों में से एक लिखकर भेजें, या रद्द करने के लिए CANCEL लिखें।"
    ),
    "book_cancelled": (
        "कोई बात नहीं, कुछ भी बुक नहीं हुआ। फिर से शुरू करने के लिए BOOK लिखकर भेजें।"
    ),
    "book_already": "{camp} में आपकी बुकिंग पहले से है: {ref}, {date}, {time}.",
    "book_confirmed": (
        "बुक हो गया। आपका रेफ़रेंस नंबर {ref} है।\n"
        "{camp}\n{date}, {time}\n{venue}\n\n"
        "कृपया अपने पालतू जानवर को पट्टे में या पिंजरे (कैरियर) में लेकर आएँ। "
        "हम एक दिन पहले आपको याद दिला देंगे।"
    ),
    "book_reminder": (
        "रिमाइंडर: आपके पालतू जानवर का कैंप का समय पास आ गया है।\n"
        "{camp}\n{date}, {time}\n{venue}\n"
        "रेफ़रेंस {ref}."
    ),
    "voice_heard": "मैंने सुना: \"{text}\"",
    "voice_noted": (
        "धन्यवाद, यह नोट कर लिया है। टीम भेजने के लिए जानवर की फ़ोटो और उसकी लोकेशन "
        "भी चाहिए (📎 अटैच पर टैप करें, फिर Location)।"
    ),
    "voice_not_understood": (
        "माफ़ कीजिए, वह वॉइस नोट समझ नहीं आया। "
        "कृपया अपना मैसेज टाइप करें, या फ़ोटो और लोकेशन भेजें।"
    ),
    "outside_goa": (
        "यह लोकेशन गोवा के बाहर की लगती है। PawSOS सिर्फ़ गोवा में काम करता है। "
        "कृपया पिन जाँचें और फिर से भेजें।"
    ),
    "photo_rejected": (
        "माफ़ कीजिए, यह फ़ोटो खुल नहीं पाई। कृपया 10 MB से छोटी JPEG या PNG फ़ोटो भेजें।"
    ),
    "unsupported": (
        "माफ़ कीजिए, इस तरह का मैसेज अभी पढ़ा नहीं जा सकता। कृपया फ़ोटो और लोकेशन भेजें।"
    ),
    # added for staff-assigned expiry
    "citizen_staff_team_unavailable": (
        "केस {case_id} का अपडेट: {team} यह केस नहीं ले सके। "
        "हमारा स्टाफ़ दूसरी टीम ढूँढ रहा है और यहीं आपको मैसेज करेगा।"
    ),
    # added for the duplicate check
    "case_checking_duplicate": (
        "धन्यवाद, आपकी रिपोर्ट मिल गई है। हम देख रहे हैं कि इस जानवर की रिपोर्ट पहले किसी ने "
        "की है या नहीं, और थोड़ी देर में आपको केस नंबर भेजेंगे। "
        "कृपया जानवर से सुरक्षित दूरी बनाए रखें।"
    ),
    # --- staff actions, STATUS and CANCEL ---
    "citizen_staff_assigned": (
        "केस {case_id} का अपडेट: हमारे स्टाफ़ ने {team} से मदद के लिए कहा है। "
        "उनका जवाब आते ही हम यहीं आपको मैसेज करेंगे।"
    ),
    "citizen_cancelled": (
        "PawSOS के स्टाफ़ ने केस {case_id} बंद कर दिया है। "
        "अगर जानवर को अब भी मदद चाहिए, तो कृपया नई फ़ोटो और लोकेशन भेजें।"
    ),
    "status_header_cases": "आपकी चालू रिपोर्ट:",
    "status_case_line": "{case_id}, {when} को रिपोर्ट की गई: {state}।",
    "status_case_line_zone": "{case_id}, {when} को रिपोर्ट की गई, {zone} इलाका: {state}।",
    "status_state_received": "रिपोर्ट मिल गई, हम फ़ोटो देख रहे हैं",
    "status_state_finding_team": "हम रेस्क्यू टीम ढूँढ रहे हैं",
    "status_state_team_alerted": "रेस्क्यू टीम को बता दिया गया है",
    "status_state_still_looking": "हम अभी भी किसी टीम से संपर्क करने की कोशिश कर रहे हैं",
    "status_state_accepted": "{team} ने केस ले लिया है और वे रास्ते में हैं",
    "status_state_on_site": "{team} जानवर तक पहुँच गई है",
    "status_header_bookings": "आपकी कैंप बुकिंग:",
    "status_booking_line": "{ref}: {camp}, {date}, {time}।",
    "status_footer": "इनमें से कोई रद्द करने के लिए CANCEL लिखकर भेजें।",
    "status_nothing": (
        "हमारे पास आपकी कोई चालू रिपोर्ट या कैंप बुकिंग नहीं है। "
        "किसी जानवर को मदद चाहिए, तो उसकी फ़ोटो और अपनी लोकेशन भेजें। "
        "अपने पालतू जानवर के लिए कैंप में समय बुक करने के लिए BOOK लिखकर भेजें।"
    ),
    "cancel_choose": (
        "आपको क्या रद्द करना है?\n{options}\n\n"
        "नंबर लिखकर भेजें। कुछ भी रद्द नहीं करना हो, तो इस मैसेज को छोड़ दें।"
    ),
    "cancel_case_line": "रिपोर्ट {case_id} ({state})",
    "cancel_booking_line": "बुकिंग {ref}: {camp}, {date}, {time}",
    "cancel_invalid_choice": "कृपया दिखाए गए नंबरों में से एक लिखकर भेजें।",
    "cancel_nothing": (
        "रद्द करने के लिए आपका कुछ भी चालू नहीं है। "
        "अपनी रिपोर्ट और बुकिंग देखने के लिए कभी भी STATUS लिखकर भेजें।"
    ),
    "cancel_not_found": (
        "इस नंबर से {ref} की कोई चालू रिपोर्ट या बुकिंग हमें नहीं मिली। "
        "अपनी रिपोर्ट और बुकिंग देखने के लिए STATUS लिखकर भेजें।"
    ),
    "case_cancel_closed": "केस {case_id} पहले ही बंद हो चुका है, इसलिए रद्द करने को कुछ नहीं है।",
    "case_cancel_shared": (
        "केस {case_id} के बारे में अब आपको मैसेज नहीं आएँगे। इस जानवर की रिपोर्ट किसी और ने "
        "भी की है, इसलिए केस उनके लिए खुला रहेगा। हमें बताने के लिए धन्यवाद।"
    ),
    "case_cancelled": (
        "केस {case_id} रद्द कर दिया गया है। हमें बताने के लिए धन्यवाद। "
        "अगर जानवर को फिर से मदद चाहिए, तो नई फ़ोटो और लोकेशन भेजें।"
    ),
    "case_cancelled_team_told": (
        "केस {case_id} रद्द कर दिया गया है और हमने रेस्क्यू टीम को बता दिया है। "
        "हमें बताने के लिए धन्यवाद। "
        "अगर जानवर को फिर से मदद चाहिए, तो नई फ़ोटो और लोकेशन भेजें।"
    ),
    "booking_cancelled": (
        "बुकिंग {ref} ({camp}, {date}, {time}) रद्द हो गई है, और वह जगह अब किसी और के लिए "
        "खाली है। फिर से बुक करने के लिए कभी भी BOOK लिखकर भेजें।"
    ),
    "booking_cancel_closed": "बुकिंग {ref} अब चालू नहीं है, इसलिए रद्द करने को कुछ नहीं है।",
}


# ---------- dates and place names ----------
#
# MACHINE-DRAFTED like the tables above; listed in docs/TRANSLATIONS.md for a
# fluent reader. English uses short forms ("Sat 28 Nov"); the other languages
# use full words, which read more naturally in Devanagari.

WEEKDAYS: dict[str, tuple[str, ...]] = {  # Monday first, as datetime.weekday() counts
    "en": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
    "kok": ("सोमार", "मंगळार", "बुधवार", "बिरेस्तार", "शुक्रार", "शेनवार", "आयतार"),
    "mr": ("सोमवार", "मंगळवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"),
    "hi": ("सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"),
}
MONTHS: dict[str, tuple[str, ...]] = {
    "en": ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
    "kok": (
        "जानेवारी", "फेब्रुवारी", "मार्च", "एप्रिल", "मे", "जून",
        "जुलय", "ऑगस्ट", "सप्टेंबर", "ऑक्टोबर", "नोव्हेंबर", "डिसेंबर",
    ),
    "mr": (
        "जानेवारी", "फेब्रुवारी", "मार्च", "एप्रिल", "मे", "जून",
        "जुलै", "ऑगस्ट", "सप्टेंबर", "ऑक्टोबर", "नोव्हेंबर", "डिसेंबर",
    ),
    "hi": (
        "जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून",
        "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर",
    ),
}

# The 14 municipal areas, as a Devanagari reader in Goa would write them.
# A name that is not here (a new zone, a camp's place) is shown as it is stored.
PLACE_NAMES: dict[str, dict[str, str]] = {
    "Panaji": {"kok": "पणजी", "mr": "पणजी", "hi": "पणजी"},
    "Mapusa": {"kok": "म्हापशें", "mr": "म्हापसा", "hi": "म्हापसा"},
    "Pernem": {"kok": "पेडणें", "mr": "पेडणे", "hi": "पेडणे"},
    "Bicholim": {"kok": "दिवचल", "mr": "डिचोली", "hi": "डिचोली"},
    "Sankhalim": {"kok": "सांखळी", "mr": "साखळी", "hi": "साखळी"},
    "Valpoi": {"kok": "वाळपय", "mr": "वाळपई", "hi": "वाळपई"},
    "Ponda": {"kok": "फोंडें", "mr": "फोंडा", "hi": "फोंडा"},
    "Mormugao": {"kok": "मुरगांव", "mr": "मुरगाव", "hi": "मुरगांव"},
    "Margao": {"kok": "मडगांव", "mr": "मडगाव", "hi": "मडगांव"},
    "Cuncolim": {"kok": "कुंकळ्ळी", "mr": "कुंकळ्ळी", "hi": "कुंकळ्ळी"},
    "Quepem": {"kok": "केपें", "mr": "केपे", "hi": "केपे"},
    "Curchorem-Cacora": {"kok": "कुडचडें-काकोडें", "mr": "कुडचडे-काकोडा", "hi": "कुडचडे-काकोडा"},
    "Sanguem": {"kok": "सांगें", "mr": "सांगे", "hi": "सांगे"},
    "Canacona": {"kok": "काणकोण", "mr": "काणकोण", "hi": "काणकोण"},
}


def date_words(day: date, language: str | None = DEFAULT_LANGUAGE) -> str:
    """ "Sat 28 Nov" in English; "शनिवार 28 नवंबर" in Hindi. `day` is already in Goa time."""
    language = language if language in WEEKDAYS else DEFAULT_LANGUAGE
    return f"{WEEKDAYS[language][day.weekday()]} {day.day} {MONTHS[language][day.month - 1]}"


def place_name(name: str, language: str | None = DEFAULT_LANGUAGE) -> str:
    """An area's name in the reader's script, or as stored when we have no version of it."""
    return PLACE_NAMES.get(name, {}).get(language or DEFAULT_LANGUAGE, name)


def _add_translations() -> None:
    """Put each translation beside its English. A key with no English fails loudly here."""
    for language, table in (("kok", KOK), ("mr", MR), ("hi", HI)):
        for key, text in table.items():
            MESSAGES[key][language] = text


_add_translations()
