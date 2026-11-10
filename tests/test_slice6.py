"""Slice 6: the bite flow."""

import json
from pathlib import Path

import pytest
from sqlalchemy import select, text

from app import messages
from app.cases.bites import BiteReport, HealthCentre, is_bite_report
from app.cases.models import Case, Event, Report

CITIZEN_1 = "+910000000001"
PANAJI = (15.4909, 73.8278)
MARGAO = (15.2832, 73.9862)
SEED = Path(__file__).parent.parent / "seed"


def say(client, number, words) -> None:
    client.post("/sim/inbound", json={"from_number": number, "kind": "text", "text": words})


def send_location(client, number, place=PANAJI) -> None:
    client.post(
        "/sim/inbound",
        json={"from_number": number, "kind": "location", "latitude": place[0], "longitude": place[1]},
    )


def last_reply(client, number) -> str:
    transcript = client.get("/sim/messages", params={"phone": number}).json()
    return [m["text"] for m in transcript if m["direction"] == "out"][-1]


def test_saying_you_were_bitten_gets_first_aid_at_once(client, db):
    say(client, CITIZEN_1, "A dog bit me near the bus stand")

    reply = last_reply(client, CITIZEN_1)
    assert reply == messages.render("bite_first_aid")
    assert "soap and running water for 15 minutes" in reply
    assert "not medical advice" in reply
    assert db.scalars(select(BiteReport)).one().location is None


def test_location_after_a_bite_gives_the_nearest_health_centre(client, seeded):
    say(client, CITIZEN_1, "I was bitten")
    send_location(client, CITIZEN_1, PANAJI)

    reply = last_reply(client, CITIZEN_1)
    assert "Goa Medical College and Hospital, Bambolim" in reply
    assert "maps.google.com/?q=15.46330,73.85760" in reply
    assert "call ahead" in reply

    bite = seeded.scalars(select(BiteReport)).one()
    centre = seeded.get(HealthCentre, bite.health_centre_id)
    assert centre.slug == "gmc-bambolim"


def test_the_nearest_centre_depends_on_where_you_are(client, seeded):
    say(client, CITIZEN_1, "bitten by a dog")
    send_location(client, CITIZEN_1, MARGAO)
    assert "South Goa District Hospital, Margao" in last_reply(client, CITIZEN_1)


def test_a_bite_location_does_not_open_an_animal_case(client, seeded):
    say(client, CITIZEN_1, "I was bitten")
    send_location(client, CITIZEN_1)
    assert seeded.scalars(select(Case)).all() == []
    assert seeded.scalars(select(Report)).all() == []


def test_the_next_location_goes_back_to_the_animal_flow(client, seeded):
    say(client, CITIZEN_1, "I was bitten")
    send_location(client, CITIZEN_1)
    send_location(client, CITIZEN_1)  # the bite is already located
    assert last_reply(client, CITIZEN_1) == messages.render("ask_photo")


def test_bites_are_in_the_audit_log(client, seeded):
    say(client, CITIZEN_1, "I was bitten")
    send_location(client, CITIZEN_1)

    events = seeded.scalars(select(Event).order_by(Event.id)).all()
    assert [e.type for e in events] == ["bite_reported", "bite_located"]
    assert events[1].data["bites_nearby"] == 1
    assert events[1].data["is_hotspot"] is False


def test_three_bites_close_together_make_a_hotspot(client, seeded):
    for number in ("+910000000001", "+910000000002", "+910000000003"):
        say(client, number, "a dog bit me")
        send_location(client, number, PANAJI)

    flags = seeded.scalars(select(BiteReport.is_hotspot).order_by(BiteReport.id)).all()
    assert flags == [False, False, True]


def test_old_bites_do_not_count_towards_a_hotspot(client, seeded):
    for number in ("+910000000001", "+910000000002"):
        say(client, number, "a dog bit me")
        send_location(client, number, PANAJI)
    seeded.execute(text("UPDATE bite_reports SET created_at = now() - interval '31 days'"))
    seeded.commit()

    say(client, "+910000000003", "a dog bit me")
    send_location(client, "+910000000003", PANAJI)
    assert seeded.scalars(select(BiteReport.is_hotspot).order_by(BiteReport.id)).all()[-1] is False


def test_saying_it_twice_keeps_one_report(client, db):
    say(client, CITIZEN_1, "I was bitten")
    say(client, CITIZEN_1, "the dog bit me!!")
    assert len(db.scalars(select(BiteReport)).all()) == 1


def test_without_health_centres_the_advice_is_still_given(client, db):
    say(client, CITIZEN_1, "I was bitten")
    send_location(client, CITIZEN_1)
    assert last_reply(client, CITIZEN_1) == messages.render("bite_no_centre")


def test_every_seeded_health_centre_is_marked_verify():
    data = json.loads((SEED / "health_centres.json").read_text())
    assert "[VERIFY]" in data["_note"]
    assert all("[VERIFY]" in centre["name"] for centre in data["health_centres"])
    assert all("phone" not in centre for centre in data["health_centres"])


@pytest.mark.parametrize(
    "words",
    ["I was bitten", "dog bite", "A dog BIT ME", "a dog bit a child", "it is biting people", "कुत्ते ने काटा"],
)
def test_bite_words_are_recognised(words):
    assert is_bite_report(words)


@pytest.mark.skip(reason="TODO(me): Ayush writes this one")
def test_words_that_only_look_like_bite_are_not_bite_reports():
    # TODO(me): is_bite_report() must not fire on words that merely contain
    # "bit". A message like "there is a hurt rabbit" is about an animal, and
    # sending that person bite first aid would be wrong.
    #
    # 1. Use @pytest.mark.parametrize, like the test above, with at least
    #    these messages: "there is a hurt rabbit", "a bit of blood on its leg",
    #    "it has a habit of sleeping here", "hello".
    # 2. Assert `not is_bite_report(words)` for each.
    # 3. Delete the @pytest.mark.skip line and run:
    #        .venv/bin/pytest -q tests/test_slice6.py -k look_like
    #
    # Stretch: read _BITE_WORDS in app/cases/bites.py and find one more
    # sentence a real person might type that it gets wrong, in either
    # direction. Add it as a test. If it fails, that is a real bug you found.
    ...
