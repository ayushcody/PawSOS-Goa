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
            "To report an animal that needs help, send a photo and your location."
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
