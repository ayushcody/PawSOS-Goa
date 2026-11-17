"""Who was bitten? A person gets bite first aid; a bitten animal gets a rescue case (audit H5).

Before this, any bite word sent the person down the human bite flow: "a dog has
been bitten by another dog and is bleeding" got wound-washing advice and a
health centre, and no rescue case. Now:

    a person was bitten     -> bite first aid and the nearest health centre, as before
    an animal was bitten    -> the words describe the rescue report; photo and location open a case
    it is not clear         -> one question with two buttons, "A person was bitten" / "An animal is hurt"
"""

import io

import pytest
from PIL import Image
from sqlalchemy import select

from app import messages
from app.cases.bites import BiteReport, bite_kind, is_bite_report
from app.cases.models import Case, Report

CITIZEN = "+910000000001"
PANAJI = (15.4909, 73.8278)

PERSON = [
    "I was bitten",
    "A dog BIT ME",
    "a dog bit a child",
    "i got bit by a stray",
    "I've been bitten by a dog near the market",
    "my son was bitten by a dog",
    "the dog bit my hand",
    "a monkey bit him",
    "bitten by a dog",  # no subject: the sender
    "Got bitten by a stray near the bus stand",
    "कुत्ते ने काटा",
    # A person and an animal: the person's first aid comes first (its reply also asks for the animal).
    "a dog bit me and then the dog was bitten by another dog",
]
ANIMAL = [
    "A dog has been bitten by another dog and is bleeding on the road",
    "my cat was bitten by a snake",
    "the puppy got bit by something, its leg is swollen",
    "a snake bit the dog",
    "two dogs fighting, one bit a kitten",
    "stray dogs biting a calf near the temple",
    "the cow is bitten on its neck",
]
UNCLEAR = [
    "dog bite",
    "it is biting people",
    "bitten",
    "there is a biting dog outside the school",
]
NOT_A_BITE = ["the dog is limping", "a rabbit is stuck", "a bit of blood on its leg"]


@pytest.mark.parametrize("words", PERSON)
def test_a_person_bitten_is_a_person_bite(words):
    assert bite_kind(words) == "person"


@pytest.mark.parametrize("words", ANIMAL)
def test_an_animal_bitten_is_an_animal_bite(words):
    assert bite_kind(words) == "animal"


@pytest.mark.parametrize("words", UNCLEAR)
def test_a_bite_with_no_clear_victim_is_unclear(words):
    assert bite_kind(words) == "unclear"


@pytest.mark.parametrize("words", NOT_A_BITE)
def test_words_with_no_bite_are_not_a_bite(words):
    assert bite_kind(words) is None


@pytest.mark.parametrize("words", PERSON + ANIMAL + UNCLEAR)
def test_every_kind_still_counts_as_mentioning_a_bite(words):
    assert is_bite_report(words)


# ---------- in the conversation ----------


def png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (32, 32), (180, 120, 60)).save(out, format="PNG")
    return out.getvalue()


def say(client, words):
    client.post("/sim/inbound", json={"from_number": CITIZEN, "kind": "text", "text": words})


def tap(client, button_id):
    client.post("/sim/inbound", json={"from_number": CITIZEN, "kind": "button", "button_id": button_id})


def send_photo(client):
    client.post("/sim/inbound/photo", data={"from_number": CITIZEN}, files={"file": ("a.png", png(), "image/png")})


def send_location(client, place=PANAJI):
    client.post(
        "/sim/inbound",
        json={"from_number": CITIZEN, "kind": "location", "latitude": place[0], "longitude": place[1]},
    )


def outgoing(client) -> list[dict]:
    return [m for m in client.get("/sim/messages", params={"phone": CITIZEN}).json() if m["direction"] == "out"]


def last_text(client) -> str:
    return outgoing(client)[-1]["text"]


def cases(db) -> list[Case]:
    db.expire_all()
    return db.scalars(select(Case)).all()


def bite_reports(db) -> list[BiteReport]:
    db.expire_all()
    return db.scalars(select(BiteReport)).all()


def test_an_animal_bitten_by_an_animal_opens_a_rescue_case(client, seeded):
    say(client, ANIMAL[0])
    assert last_text(client) == messages.render("voice_noted")  # asks for the photo and location
    send_photo(client)
    send_location(client)

    [case] = cases(seeded)
    assert case.public_id == "PAW-0001"
    assert bite_reports(seeded) == []
    report = seeded.scalars(select(Report).where(Report.case_id == case.id)).one()
    assert report.text == ANIMAL[0]  # the team sees the reporter's words


def test_an_animal_bite_described_after_the_photo_asks_for_the_location(client, seeded):
    send_photo(client)
    say(client, "my cat was bitten by a snake")
    assert last_text(client) == messages.render("note_ask_location")
    send_location(client)
    assert len(cases(seeded)) == 1 and bite_reports(seeded) == []


def test_a_person_bite_still_goes_straight_to_first_aid(client, seeded):
    say(client, "a dog bit me")
    assert last_text(client) == messages.render("bite_first_aid")
    assert len(bite_reports(seeded)) == 1


def test_an_unclear_bite_asks_who_was_bitten_with_two_buttons(client, seeded):
    say(client, "dog bite")
    question = outgoing(client)[-1]
    assert question["text"] == messages.render("bite_which")
    assert [b["id"] for b in question["buttons"]] == ["bite:person", "bite:animal"]
    assert [b["title"] for b in question["buttons"]] == [
        messages.render("bite_choice_person"),
        messages.render("bite_choice_animal"),
    ]
    assert bite_reports(seeded) == [] and cases(seeded) == []


def test_answering_a_person_was_bitten_gives_first_aid_and_the_health_centre(client, seeded):
    say(client, "dog bite")
    tap(client, "bite:person")
    assert last_text(client) == messages.render("bite_first_aid")
    send_location(client)
    assert "health centre" in last_text(client).lower()
    [bite] = bite_reports(seeded)
    assert bite.location is not None
    assert cases(seeded) == []


def test_answering_an_animal_is_hurt_opens_a_rescue_case(client, seeded):
    say(client, "dog bite")
    tap(client, "bite:animal")
    assert last_text(client) == messages.render("voice_noted")
    send_photo(client)
    send_location(client)
    [case] = cases(seeded)
    assert bite_reports(seeded) == []
    report = seeded.scalars(select(Report).where(Report.case_id == case.id)).one()
    assert report.text == "dog bite"


def test_answering_an_animal_is_hurt_after_a_photo_asks_for_the_location(client, seeded):
    send_photo(client)
    say(client, "dog bite")
    tap(client, "bite:animal")
    assert last_text(client) == messages.render("note_ask_location")


def test_the_question_is_asked_in_the_persons_language(client, seeded):
    say(client, "LANGUAGE")
    say(client, "4")  # Hindi
    say(client, "dog bite")
    question = outgoing(client)[-1]
    assert question["text"] == messages.render("bite_which", "hi")
    assert question["buttons"][0]["title"] == messages.render("bite_choice_person", "hi")


@pytest.mark.parametrize("language", ["en", "kok", "mr", "hi"])
def test_button_titles_fit_whatsapps_20_characters(language):
    for key in ("bite_choice_person", "bite_choice_animal"):
        assert len(messages.render(key, language)) <= 20
