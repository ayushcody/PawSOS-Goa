"""Every message PawSOS sends, in one place.

Keys describe the purpose ("echo", "ask_location"), never the language, so
Konkani ("kok") and Marathi ("mr") can be added beside "en" without touching
the code that sends them. Copy is short, calm and plain.
"""

DEFAULT_LANGUAGE = "en"

MESSAGES: dict[str, dict[str, str]] = {
    "welcome": {
        "en": (
            "Hello, this is PawSOS Goa. "
            "To report an animal that needs help, send a photo and your location."
        ),
    },
    "echo": {
        "en": "You said: {text}",
    },
    "unsupported": {
        "en": "Sorry, I can't read that kind of message yet. Please send text.",
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
