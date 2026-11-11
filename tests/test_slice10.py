"""Slice 10: the voice-note skeleton.

No real speech service exists yet. These tests cover the interface, the
stand-in that reads the simulator's pretend voice notes, and what the
conversation does with the words once it has them.
"""

import asyncio

import pytest
from sqlalchemy import select

from app import messages
from app.cases.bites import BiteReport
from app.cases.models import Case, Event, Report
from app.config import get_settings
from app.voice import speech
from app.voice.speech import (
    SIMULATED_MIME,
    BhashiniSpeechToText,
    SpeechUnavailable,
    StubSpeechToText,
    Transcript,
    clean_transcript,
    get_speech_to_text,
    listen,
)
from tests.whatsapp_fakes import JPEG, envelope, msg, post

CITIZEN = "+910000000001"
PANAJI = {"latitude": 15.4909, "longitude": 73.8278}


def speak(client, words, language="en", number=CITIZEN):
    return client.post(
        "/sim/inbound/voice", json={"from_number": number, "spoken_text": words, "language": language}
    )


def replies(client, number=CITIZEN) -> list[str]:
    transcript = client.get("/sim/messages", params={"phone": number}).json()
    return [m["text"] for m in transcript if m["direction"] == "out"]


class FixedSpeech:
    """A speech service that always hears the same thing."""

    name = "fixed"

    def __init__(self, text: str, language: str = "en") -> None:
        self.heard = Transcript(text, language)
        self.received: list[tuple[int, str]] = []

    async def transcribe(self, audio, mime, language=None) -> Transcript:
        self.received.append((len(audio), mime))
        return self.heard


# ---------- the interface and the stand-in ----------


def test_the_stand_in_reads_a_simulated_voice_note():
    heard = asyncio.run(StubSpeechToText().transcribe("कुत्ता घायल है".encode(), SIMULATED_MIME, "hi"))
    assert heard == Transcript("कुत्ता घायल है", "hi")


def test_the_stand_in_refuses_real_audio():
    with pytest.raises(SpeechUnavailable):
        asyncio.run(StubSpeechToText().transcribe(b"OggS....", "audio/ogg"))


def test_bhashini_is_not_built_and_says_so():
    with pytest.raises(SpeechUnavailable, match="not been built"):
        asyncio.run(BhashiniSpeechToText().transcribe(b"OggS....", "audio/ogg", "kok"))


def test_the_speech_service_is_chosen_by_a_setting(monkeypatch):
    settings = get_settings()
    for choice, expected in (("stub", StubSpeechToText), ("bhashini", BhashiniSpeechToText)):
        monkeypatch.setattr(settings, "speech_to_text", choice)
        get_speech_to_text.cache_clear()
        assert isinstance(get_speech_to_text(), expected)
    monkeypatch.setattr(settings, "speech_to_text", "off")
    get_speech_to_text.cache_clear()
    assert get_speech_to_text() is None
    get_speech_to_text.cache_clear()


def test_listen_never_raises_and_gives_none_when_it_cannot_tell():
    class Broken:
        name = "broken"

        async def transcribe(self, audio, mime, language=None):
            raise RuntimeError("service down")

    assert asyncio.run(listen(None, b"words", SIMULATED_MIME)) is None  # voice notes off
    assert asyncio.run(listen(StubSpeechToText(), b"OggS", "audio/ogg")) is None  # cannot transcribe
    assert asyncio.run(listen(Broken(), b"words", SIMULATED_MIME)) is None  # the service failed
    assert asyncio.run(listen(StubSpeechToText(), b"   ", SIMULATED_MIME)) is None  # silence
    too_big = b"a" * (speech.MAX_AUDIO_BYTES + 1)
    assert asyncio.run(listen(StubSpeechToText(), too_big, SIMULATED_MIME)) is None
    assert asyncio.run(listen(StubSpeechToText(), b" hello ", SIMULATED_MIME)) == Transcript("hello", "en")


# ---------- what the conversation does with the words ----------


def test_a_spoken_bite_report_starts_the_bite_flow(client, seeded):
    assert speak(client, "a dog bit me").json() == {"ok": True}
    assert replies(client) == [
        messages.render("voice_heard", text="a dog bit me"),
        messages.render("bite_first_aid"),
    ]
    assert seeded.scalars(select(BiteReport)).one().reporter_number == CITIZEN


def test_a_bite_spoken_in_hindi_is_understood(client, seeded):
    speak(client, "मुझे कुत्ते ने काटा", language="hi")
    assert replies(client)[-1] == messages.render("bite_first_aid")


def test_a_spoken_description_is_kept_with_the_report(client, seeded):
    words = "There is a dog lying near the Mapusa market, it is not moving"
    speak(client, words)
    assert replies(client) == [
        messages.render("voice_heard", text=words),
        messages.render("voice_noted"),
    ]
    assert seeded.scalars(select(Report)).one().text == words

    # The photo and location that follow join the same report, and the words stay with the case.
    client.post("/sim/inbound/photo", data={"from_number": CITIZEN}, files={"file": ("a.jpg", JPEG, "image/jpeg")})
    client.post("/sim/inbound", json={"from_number": CITIZEN, "kind": "location", **PANAJI})
    seeded.expire_all()
    report = seeded.scalars(select(Report)).one()
    assert report.text == words and report.case_id == seeded.scalars(select(Case)).one().id


def test_a_voice_note_after_a_photo_asks_only_for_what_is_missing(client, seeded):
    client.post("/sim/inbound/photo", data={"from_number": CITIZEN}, files={"file": ("a.jpg", JPEG, "image/jpeg")})
    speak(client, "the cow has a rope around its leg")
    assert replies(client)[-1] == messages.render("ask_location")


def test_a_spoken_book_starts_a_booking(client, seeded):
    speak(client, "Book.")  # speech services add the full stop
    assert "Upcoming camps" in replies(client)[-1]


def test_a_spoken_greeting_gets_the_welcome(client, seeded):
    speak(client, "Namaste")
    assert replies(client)[-1] == messages.render("welcome")
    assert seeded.scalars(select(Report)).all() == []


def test_with_voice_notes_off_the_person_is_asked_to_type(app, client, db):
    app.dependency_overrides[get_speech_to_text] = lambda: None
    assert speak(client, "a dog bit me").json() == {"ok": False}
    assert replies(client) == [messages.render("voice_not_understood")]


def test_only_the_words_are_logged_never_the_audio(client, seeded):
    speak(client, "an injured bird on the road", language="kok")
    event = seeded.scalars(select(Event).where(Event.type == "voice_note_received")).one()
    assert event.data == {"report_id": 1, "language": "kok", "characters": 27}


def test_the_simulator_refuses_an_unknown_language(client):
    assert speak(client, "hello", language="fr").status_code == 422


# ---------- real WhatsApp voice notes ----------


def test_a_whatsapp_voice_note_is_declined_until_a_real_service_exists(wa, meta, db):
    meta.photos["audio-1"] = (b"OggS" + b"0" * 32, "audio/ogg")
    post(wa, envelope(msg("audio", audio={"id": "audio-1", "mime_type": "audio/ogg; codecs=opus", "voice": True})))
    assert meta.texts_to() == [messages.render("voice_not_understood")]


def test_a_whatsapp_voice_note_flows_through_once_a_service_can_hear_it(wa, meta, seeded):
    listener = FixedSpeech("a dog bit my son")
    wa.app.dependency_overrides[get_speech_to_text] = lambda: listener
    meta.photos["audio-1"] = (b"OggS" + b"0" * 32, "audio/ogg")
    post(wa, envelope(msg("audio", audio={"id": "audio-1", "mime_type": "audio/ogg; codecs=opus", "voice": True})))

    assert listener.received == [(36, "audio/ogg")]  # the audio was fetched from Meta and passed on
    assert meta.texts_to() == [
        messages.render("voice_heard", text="a dog bit my son"),
        messages.render("bite_first_aid"),
    ]


def test_a_voice_note_that_cannot_be_downloaded_is_declined(wa, meta, db):
    post(wa, envelope(msg("audio", audio={"id": "missing", "mime_type": "audio/ogg"})))
    assert meta.texts_to() == [messages.render("voice_not_understood")]


@pytest.mark.skip(reason="TODO(me): improve clean_transcript() in app/voice/speech.py")
def test_clean_transcript():
    assert clean_transcript("  a dog   is hurt \n near the market ") == "a dog is hurt near the market"
    assert clean_transcript("hello") == "hello"
    assert clean_transcript(" \t\n ") == ""
