"""Slice 1: health check, simulator, text replies.

The echo bot from slice 1 was replaced in slice 2: plain text now gets a
short "how to report" reply instead of being repeated back.
"""

import pytest
from fastapi.testclient import TestClient

from app import messages

CITIZEN_1 = "+910000000001"
CITIZEN_2 = "+910000000002"


def send(client: TestClient, number: str, text: str) -> None:
    res = client.post("/sim/inbound", json={"from_number": number, "kind": "text", "text": text})
    assert res.status_code == 200


def chat(client: TestClient, number: str, after: int = 0) -> list[dict]:
    return client.get("/sim/messages", params={"phone": number, "after": after}).json()


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_simulator_page_loads(client):
    res = client.get("/sim")
    assert res.status_code == 200
    assert "PawSOS" in res.text


def test_text_gets_how_to_report(client):
    send(client, CITIZEN_1, "there is a hurt dog near the market")
    transcript = chat(client, CITIZEN_1)
    assert [m["direction"] for m in transcript] == ["in", "out"]
    assert transcript[0]["text"] == "there is a hurt dog near the market"
    assert transcript[1]["text"] == messages.render("how_to_report")


def test_greeting_gets_welcome(client):
    send(client, CITIZEN_1, "Hi")
    assert chat(client, CITIZEN_1)[-1]["text"] == messages.render("welcome")


def test_chats_are_separate_per_number(client):
    send(client, CITIZEN_1, "one")
    send(client, CITIZEN_2, "two")
    assert [m["text"] for m in chat(client, CITIZEN_1) if m["direction"] == "in"] == ["one"]
    assert [m["text"] for m in chat(client, CITIZEN_2) if m["direction"] == "in"] == ["two"]


def test_after_returns_only_newer_messages(client):
    send(client, CITIZEN_1, "first")
    last_seen = chat(client, CITIZEN_1)[-1]["id"]
    send(client, CITIZEN_1, "second")
    newer = chat(client, CITIZEN_1, after=last_seen)
    assert [m["direction"] for m in newer] == ["in", "out"]
    assert newer[0]["text"] == "second"


def test_message_with_nothing_readable_gets_a_polite_reply(client):
    res = client.post("/sim/inbound", json={"from_number": CITIZEN_1, "kind": "image"})
    assert res.status_code == 200
    assert chat(client, CITIZEN_1)[-1]["text"] == messages.render("unsupported")


def test_render_fills_placeholders():
    assert "PAW-0042" in messages.render("case_created", case_id="PAW-0042")


def test_render_unknown_key_fails_loudly():
    with pytest.raises(KeyError):
        messages.render("no_such_message")


@pytest.mark.skip(reason="TODO(me): Ayush writes this one")
def test_render_falls_back_to_english():
    # TODO(me): messages.render() promises to fall back to English when a
    # language has no translation yet. Prove it.
    #
    # 1. Call messages.render("welcome", language="kok")  (Konkani, not added yet)
    # 2. Assert the result equals messages.render("welcome")
    # 3. Delete the @pytest.mark.skip line above and run:
    #        .venv/bin/pytest -q tests/test_slice1.py -k fallback
    #
    # Stretch: what should happen for render("case_created", language="kok")
    # if you forget to pass case_id=...? Write a second test that pins that down.
    ...
