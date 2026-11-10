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
