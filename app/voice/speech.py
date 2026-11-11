"""Turning a voice note into text.

The rest of the app talks to the SpeechToText interface, so the real service
(Bhashini, for Konkani, Marathi, Hindi and English) can be added later
without touching anything else. Until then there is a stand-in that only
understands the simulator's pretend voice notes.

We never keep the audio. Only the words are stored, with the report.
"""

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from app.config import get_settings

log = logging.getLogger(__name__)

LANGUAGES = {"en": "English", "hi": "Hindi", "mr": "Marathi", "kok": "Konkani"}
MAX_AUDIO_BYTES = 5 * 1024 * 1024
MAX_TRANSCRIPT_LENGTH = 1000
# The simulator has no microphone. Its "voice note" is the words themselves,
# sent as bytes under this made-up type.
SIMULATED_MIME = "text/x-simulated-voice"


@dataclass
class Transcript:
    text: str
    language: str  # a key of LANGUAGES


class SpeechUnavailable(Exception):
    """The voice note could not be turned into text."""


class SpeechToText(Protocol):
    name: str

    async def transcribe(self, audio: bytes, mime: str, language: str | None = None) -> Transcript:
        """Return what was said, or raise SpeechUnavailable."""
        ...


def clean_transcript(text: str) -> str:
    """Tidy what a speech service returns before we show or store it.

    TODO(me): Ayush improves this. Speech services often return odd spacing:
    "  a dog   is hurt \\n near the market ". Right now we only trim the ends.
    Make it also turn every run of spaces, tabs and line breaks inside the
    text into one single space, so that example becomes
    "a dog is hurt near the market".
    Hint: text.split() with no arguments splits on any whitespace and drops
    the empty pieces; " ".join(...) puts the words back together.
    Then remove the @pytest.mark.skip on test_clean_transcript in
    tests/test_slice10.py and run:
        .venv/bin/pytest -q tests/test_slice10.py -k clean
    """
    return text.strip()


class StubSpeechToText:
    """A stand-in. It reads the simulator's pretend voice notes and nothing else."""

    name = "stub"

    async def transcribe(self, audio: bytes, mime: str, language: str | None = None) -> Transcript:
        if mime != SIMULATED_MIME:
            raise SpeechUnavailable("The stand-in cannot listen to real audio.")
        text = audio.decode("utf-8", errors="replace")
        return Transcript(text=text, language=language if language in LANGUAGES else "en")


class BhashiniSpeechToText:
    """NOT BUILT YET. The place where the real Bhashini call will go.

    To build it: read Bhashini's current API documentation, send the audio
    with the language hint, and return a Transcript. It needs BHASHINI_USER_ID
    and BHASHINI_API_KEY from .env, and a test that replaces the HTTP call
    with a stand-in. Until then every voice note is politely declined.
    """

    name = "bhashini"

    async def transcribe(self, audio: bytes, mime: str, language: str | None = None) -> Transcript:
        raise SpeechUnavailable("The Bhashini integration has not been built yet.")


@lru_cache
def get_speech_to_text() -> SpeechToText | None:
    """The app's speech service, chosen by SPEECH_TO_TEXT. None means voice notes are off."""
    choice = get_settings().speech_to_text
    if choice == "stub":
        return StubSpeechToText()
    if choice == "bhashini":
        log.warning("SPEECH_TO_TEXT=bhashini, but that integration is not built. Voice notes will be declined.")
        return BhashiniSpeechToText()
    return None


async def listen(
    service: SpeechToText | None, audio: bytes, mime: str, language: str | None = None
) -> Transcript | None:
    """What was said, or None if we could not tell. Never raises."""
    if service is None or not audio or len(audio) > MAX_AUDIO_BYTES:
        return None
    try:
        heard = await service.transcribe(audio, mime, language)
    except SpeechUnavailable as reason:
        log.info("Voice note not transcribed: %s", reason)
        return None
    except Exception:
        log.exception("The speech service failed")
        return None
    text = clean_transcript(heard.text)[:MAX_TRANSCRIPT_LENGTH]
    return Transcript(text=text, language=heard.language) if text else None
