"""Slice 3: vision triage. The real Claude API is never called here."""

import asyncio
import io
from types import SimpleNamespace

import anthropic
import httpx
import pytest
from PIL import Image
from pydantic import ValidationError
from sqlalchemy import select

from app import messages
from app.cases import state_machine
from app.cases.models import Case, CaseState, Event
from app.triage.images import MAX_SIDE, prepare_for_vision
from app.triage.prompt import SYSTEM_PROMPT
from app.triage.schema import TriageResult
from app.triage.service import ClaudeTriager, TriageUnavailable, get_triager

CITIZEN_1 = "+910000000001"

GOOD = {
    "animal_visible": True,
    "species": "dog",
    "injury_type": "visible wound on hind leg",
    "urgency": "high",
    "aggression_risk": "low",
    "first_aid": ["Keep a safe distance.", "Keep other people and pets back."],
}


def photo_bytes(size=(64, 48)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, (180, 120, 60)).save(out, format="PNG")
    return out.getvalue()


def report_a_case(client, image: bytes | None = None) -> None:
    client.post(
        "/sim/inbound/photo",
        data={"from_number": CITIZEN_1},
        files={"file": ("dog.png", image or photo_bytes(), "image/png")},
    )
    client.post(
        "/sim/inbound",
        json={"from_number": CITIZEN_1, "kind": "location", "latitude": 15.4909, "longitude": 73.8278},
    )


def replies(client) -> list[str]:
    transcript = client.get("/sim/messages", params={"phone": CITIZEN_1}).json()
    return [m["text"] for m in transcript if m["direction"] == "out"]


class FakeTriager:
    """Stands in for Claude: returns a set result, or raises a set error."""

    def __init__(self, outcome) -> None:
        self.outcome = outcome
        self.calls = 0

    async def triage(self, image: bytes) -> TriageResult:
        self.calls += 1
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


# ---------- the whole flow, through the simulator ----------


def test_triage_result_is_saved_and_sent(app, client, db):
    fake = FakeTriager(TriageResult(**GOOD))
    app.dependency_overrides[get_triager] = lambda: fake

    report_a_case(client)

    case = db.scalars(select(Case)).one()
    assert fake.calls == 1
    assert case.state == CaseState.NEW  # triaged, then routed in slice 4
    assert (case.species, case.urgency, case.aggression_risk) == ("dog", "high", "low")
    assert case.first_aid == GOOD["first_aid"]
    assert case.triage_status == "ok"

    sent = replies(client)
    assert messages.render("case_created", case_id="PAW-0001") in sent
    final = sent[-1]
    assert "PAW-0001" in final
    assert "1. Keep a safe distance." in final
    assert messages.render("not_a_diagnosis") in final


def test_triage_writes_a_state_change_to_the_audit_log(app, client, db):
    app.dependency_overrides[get_triager] = lambda: FakeTriager(TriageResult(**GOOD))
    report_a_case(client)

    event = db.scalars(select(Event).where(Event.to_state == "TRIAGED")).one()
    assert (event.from_state, event.to_state, event.actor) == ("REPORTED", "TRIAGED", "triage")
    assert event.data["urgency"] == "high"


def test_aggressive_animal_adds_a_warning_first(app, client, db):
    result = TriageResult(**{**GOOD, "aggression_risk": "high"})
    app.dependency_overrides[get_triager] = lambda: FakeTriager(result)
    report_a_case(client)
    assert "1. " + messages.render("aggression_warning") in replies(client)[-1]


@pytest.mark.parametrize(
    "outcome",
    [
        TriageUnavailable("no valid reply after 2 attempts"),
        RuntimeError("something nobody expected"),
        TriageResult(**{**GOOD, "animal_visible": False, "species": "unclear"}),
    ],
    ids=["model unavailable", "unexpected crash", "no animal in photo"],
)
def test_when_triage_cannot_help_the_case_still_moves_on(app, client, db, outcome):
    app.dependency_overrides[get_triager] = lambda: FakeTriager(outcome)
    report_a_case(client)

    case = db.scalars(select(Case)).one()
    assert case.state == CaseState.NEW  # triaged, then routed in slice 4
    assert case.triage_status == "needs_review"
    assert case.urgency == "high"
    assert case.first_aid is None
    assert replies(client)[-1] == messages.render("triage_needs_review", case_id="PAW-0001")


def test_without_an_api_key_cases_go_to_human_review(client, db):
    report_a_case(client)  # the default test app has no triager
    case = db.scalars(select(Case)).one()
    assert case.triage_status == "needs_review"


# ---------- the Claude call itself, with a fake client ----------


class FakeMessages:
    def __init__(self, outcomes: list) -> None:
        self.outcomes = outcomes
        self.calls: list[dict] = []

    async def parse(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def reply(parsed, stop_reason="end_turn"):
    return SimpleNamespace(parsed_output=parsed, stop_reason=stop_reason)


def invalid_reply_error() -> ValidationError:
    try:
        TriageResult(**{**GOOD, "urgency": "sort of bad"})
    except ValidationError as error:
        return error
    raise AssertionError("expected a ValidationError")


def run_triage(outcomes: list):
    fake = FakeMessages(outcomes)
    triager = ClaudeTriager(SimpleNamespace(messages=fake), "test-model")
    return fake, lambda: asyncio.run(triager.triage(photo_bytes()))


def test_claude_call_sends_the_photo_and_the_schema():
    fake, go = run_triage([reply(TriageResult(**GOOD))])
    assert go().species == "dog"

    call = fake.calls[0]
    assert call["model"] == "test-model"
    assert call["output_format"] is TriageResult
    assert call["system"] == SYSTEM_PROMPT
    image_block = call["messages"][0]["content"][0]
    assert image_block["type"] == "image"
    assert image_block["source"]["media_type"] == "image/jpeg"


def test_one_invalid_reply_is_retried():
    fake, go = run_triage([invalid_reply_error(), reply(TriageResult(**GOOD))])
    assert go().urgency == "high"
    assert len(fake.calls) == 2


def test_two_invalid_replies_give_up():
    fake, go = run_triage([invalid_reply_error(), invalid_reply_error()])
    with pytest.raises(TriageUnavailable):
        go()
    assert len(fake.calls) == 2  # one try plus one retry, never more


def test_a_declined_request_is_retried_then_gives_up():
    _fake, go = run_triage([reply(None, "refusal"), reply(None, "refusal")])
    with pytest.raises(TriageUnavailable):
        go()


def test_an_unreachable_api_gives_up_after_one_retry():
    error = anthropic.APIConnectionError(request=httpx.Request("POST", "https://example.invalid"))
    fake, go = run_triage([error, error])
    with pytest.raises(TriageUnavailable):
        go()
    assert len(fake.calls) == 2  # the SDK no longer retries; the one retry is ours (audit H2)


def test_a_file_that_is_not_an_image_never_reaches_the_api():
    fake = FakeMessages([])
    triager = ClaudeTriager(SimpleNamespace(messages=fake), "test-model")
    with pytest.raises(TriageUnavailable):
        asyncio.run(triager.triage(b"\x89PNG\r\n\x1a\n not really"))
    assert fake.calls == []


def test_large_photos_are_shrunk():
    jpeg, media_type = prepare_for_vision(photo_bytes(size=(4000, 3000)))
    assert media_type == "image/jpeg"
    assert max(Image.open(io.BytesIO(jpeg)).size) == MAX_SIDE


# ---------- what we promise about the wording ----------


def test_prompt_forbids_diagnosis_and_unsafe_advice():
    prompt = SYSTEM_PROMPT.lower()
    assert "not making a diagnosis" in prompt
    assert "never suggest touching" in prompt


def test_schema_refuses_one_first_aid_step():
    with pytest.raises(ValidationError):
        TriageResult(**{**GOOD, "first_aid": ["Keep a safe distance."]})


@pytest.mark.skip(reason="TODO(me): Ayush writes this one")
def test_schema_refuses_four_first_aid_steps():
    # TODO(me): the product promises "2 to 3" first-aid steps. The test above
    # proves one step is refused. Prove four steps are refused too.
    #
    # 1. Build a TriageResult the same way, with a first_aid list of four steps.
    # 2. Expect pydantic's ValidationError, using pytest.raises as above.
    # 3. Delete the @pytest.mark.skip line and run:
    #        .venv/bin/pytest -q tests/test_slice3.py -k four
    #
    # Stretch: add a third test that a step longer than 200 characters is
    # refused. (Hint: "x" * 201.) Then read _two_or_three_short_steps in
    # app/triage/schema.py and check your tests cover each `raise` in it.
    ...


# ---------- the state machine ----------


def test_every_listed_transition_is_allowed():
    for from_state, targets in state_machine.TRANSITIONS.items():
        for to_state in targets:
            assert state_machine.can_transition(from_state, to_state)


def test_every_state_has_an_entry_in_the_table():
    assert set(state_machine.TRANSITIONS) == set(CaseState)


def test_final_states_lead_nowhere():
    for state in (CaseState.MERGED, CaseState.RESOLVED, CaseState.CANCELLED):
        assert state_machine.TRANSITIONS[state] == set()


def test_an_unlisted_transition_is_refused_and_changes_nothing(client, db):
    report_a_case(client)
    case = db.scalars(select(Case)).one()  # triaged, then NEW

    with pytest.raises(state_machine.InvalidTransition):
        state_machine.transition(db, case, CaseState.RESOLVED, actor="test")
    assert case.state == CaseState.NEW  # triaged, then routed in slice 4
