"""Each person's language, remembered by phone number.

A person changes language by sending LANGUAGE (or भाषा / भास). We reply with
a numbered menu, and the next number they send within 15 minutes picks the
language. If someone with no saved language sends a voice note that the
speech service heard as Konkani, Marathi or Hindi, we adopt that language.
Everyone else gets English.

Call sites only need one line: messages.render(key, language_for(session, to), ...).
"""

from datetime import datetime, timedelta

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, Session, mapped_column

from app import clock, messages
from app.db import Base

MENU_WINDOW = timedelta(minutes=15)
COMMAND_WORDS = {"language", "lang", "bhasha", "भाषा", "भास"}
# The same order as the "language_menu" message: "2" means Konkani.
MENU_ORDER = messages.LANGUAGES
# Names a person might type instead of a number while the menu is open.
LANGUAGE_NAMES = {
    "english": "en",
    "konkani": "kok",
    "कोंकणी": "kok",
    "कोकणी": "kok",
    "marathi": "mr",
    "मराठी": "mr",
    "hindi": "hi",
    "हिंदी": "hi",
    "हिन्दी": "hi",
}
# Speech services may name Goan Konkani by its ISO 639-3 code.
_CODE_ALIASES = {"gom": "kok"}


class Contact(Base):
    """What we remember about one phone number. Only the language, for now."""

    __tablename__ = "contacts"

    number: Mapped[str] = mapped_column(String(20), primary_key=True)
    language: Mapped[str | None] = mapped_column(String(8))  # empty: never chosen, so English
    # Set when we sent the LANGUAGE menu, cleared once they answer.
    language_menu_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def normalise(code: str | None) -> str | None:
    """'hi-IN' -> 'hi', 'gom' -> 'kok'; None for a language we have no messages in."""
    if not code:
        return None
    base = code.strip().lower().replace("_", "-").split("-")[0]
    base = _CODE_ALIASES.get(base, base)
    return base if base in messages.LANGUAGES else None


def language_for(session: Session, number: str) -> str:
    """The language to write to this number in."""
    contact = session.get(Contact, number)
    if contact is None or not contact.language:
        return messages.DEFAULT_LANGUAGE
    return contact.language


def _contact(session: Session, number: str) -> Contact:
    contact = session.get(Contact, number)
    if contact is None:
        contact = Contact(number=number)
        session.add(contact)
    contact.updated_at = clock.now()
    return contact


def set_language(session: Session, number: str, language: str) -> None:
    code = normalise(language)
    if code is None:
        raise ValueError(f"No messages in language {language!r}")
    contact = _contact(session, number)
    contact.language = code
    contact.language_menu_at = None


def adopt_detected(session: Session, number: str, detected: str | None) -> bool:
    """Use the language a voice note was heard in, if this person never chose one.

    English is the default anyway, so only Konkani, Marathi or Hindi is saved.
    Returns True when something changed (the caller commits).
    """
    code = normalise(detected)
    if code is None or code == messages.DEFAULT_LANGUAGE:
        return False
    existing = session.get(Contact, number)
    if existing is not None and existing.language:
        return False
    _contact(session, number).language = code
    return True


def _menu_open(contact: Contact | None) -> bool:
    return (
        contact is not None
        and contact.language_menu_at is not None
        and contact.language_menu_at >= clock.now() - MENU_WINDOW
    )


def close_menu(session: Session, number: str) -> None:
    """Another conversation (BOOK) took over, so a number now means something else."""
    contact = session.get(Contact, number)
    if contact is not None and contact.language_menu_at is not None:
        contact.language_menu_at = None


def handle_text(session: Session, number: str, text: str) -> str | None:
    """If this text is about choosing a language, act on it and return the reply's key.

    Returns None for anything else, so the other flows can look at it. A number
    only counts as a language choice while the menu is open, and the caller
    closes the menu when BOOK takes over, so "2" for a camp is never read as
    "Konkani".
    """
    word = text.strip().lower()
    if word in COMMAND_WORDS:
        _contact(session, number).language_menu_at = clock.now()
        return "language_menu"

    contact = session.get(Contact, number)
    if not _menu_open(contact):
        return None
    if word.isdecimal():  # also accepts Devanagari digits such as "२"
        choice = int(word)
        if not 1 <= choice <= len(MENU_ORDER):
            return "language_menu"  # show the choices again
        set_language(session, number, MENU_ORDER[choice - 1])
        return "language_set"
    if word in LANGUAGE_NAMES:
        set_language(session, number, LANGUAGE_NAMES[word])
        return "language_set"
    return None
