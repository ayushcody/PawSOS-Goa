"""Audit H2: triage may never hold up the first team alert for more than about 30 seconds.

One try of about 15 seconds, one retry, then the usual fallback (high urgency,
flagged for a person). The real Claude API is never called here.
"""

import asyncio
import time
from types import SimpleNamespace

import anthropic
import httpx
import pytest
from sqlalchemy import select

from app.cases.models import Case
from app.config import get_settings
from app.routing.models import Dispatch
from app.triage import flow as triage_flow
from app.triage.schema import TriageResult
from app.triage.service import ClaudeTriager, TriageUnavailable, get_triager
from tests.test_slice3 import GOOD, FakeMessages, photo_bytes, reply, report_a_case

REQUEST = httpx.Request("POST", "https://example.invalid")
NEVER = 20  # far longer than any limit under test; short enough that old code fails, not hangs
GUARD = 5  # these tests fail instead of hanging if the code under test waits


class HangingMessages:
    """A Claude API that accepts the request and then says nothing."""

    def __init__(self) -> None:
        self.calls = 0

    async def parse(self, **kwargs):
        self.calls += 1
        await asyncio.sleep(NEVER)


class HangingTriager:
    def __init__(self) -> None:
        self.calls = 0

    async def triage(self, image: bytes) -> TriageResult:
        self.calls += 1
        await asyncio.sleep(NEVER)


def status_error(status: int) -> anthropic.APIStatusError:
    response = httpx.Response(status, request=REQUEST)
    return anthropic.APIStatusError("refused", response=response, body=None)


def run(triager: ClaudeTriager):
    return asyncio.run(asyncio.wait_for(triager.triage(photo_bytes()), GUARD))


# ---------- the limits themselves ----------


def test_the_default_is_fifteen_seconds_a_try():
    assert get_settings().triage_timeout_seconds == 15


def test_the_real_client_waits_fifteen_seconds_and_leaves_the_retry_to_us(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    get_settings.cache_clear()
    get_triager.cache_clear()
    try:
        client = get_triager()._client
        assert client.timeout == 15  # was 60
        assert client.max_retries == 0  # was the SDK's 2: three tries of 60 seconds each
    finally:
        get_settings.cache_clear()
        get_triager.cache_clear()


# ---------- one try, one retry, then give up ----------


def test_a_call_that_never_answers_is_cut_off_and_tried_once_more():
    fake = HangingMessages()
    triager = ClaudeTriager(SimpleNamespace(messages=fake), "test-model", timeout=0.05)
    started = time.monotonic()
    with pytest.raises(TriageUnavailable, match="timed out"):
        run(triager)
    assert fake.calls == 2  # the first try and one retry, never a third
    assert time.monotonic() - started < 1  # two tries of 0.05 s each


def test_an_unreachable_api_is_tried_once_more_and_can_succeed():
    fake = FakeMessages([anthropic.APIConnectionError(request=REQUEST), reply(TriageResult(**GOOD))])
    assert run(ClaudeTriager(SimpleNamespace(messages=fake), "test-model")).species == "dog"
    assert len(fake.calls) == 2


def test_an_unreachable_api_gives_up_after_the_one_retry():
    unreachable = anthropic.APIConnectionError(request=REQUEST)
    fake = FakeMessages([unreachable, unreachable, reply(TriageResult(**GOOD))])
    with pytest.raises(TriageUnavailable, match="unreachable"):
        run(ClaudeTriager(SimpleNamespace(messages=fake), "test-model"))
    assert len(fake.calls) == 2


def test_the_sdks_own_timeout_counts_as_a_try():
    fake = FakeMessages([anthropic.APITimeoutError(request=REQUEST), reply(TriageResult(**GOOD))])
    assert run(ClaudeTriager(SimpleNamespace(messages=fake), "test-model")).urgency == "high"
    assert len(fake.calls) == 2


@pytest.mark.parametrize("status", [429, 500, 529])
def test_a_busy_or_broken_api_is_tried_once_more(status):
    fake = FakeMessages([status_error(status), reply(TriageResult(**GOOD))])
    assert run(ClaudeTriager(SimpleNamespace(messages=fake), "test-model")).species == "dog"
    assert len(fake.calls) == 2


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_a_request_the_api_rejects_is_not_tried_again(status):
    # Sending the same wrong request again cannot help, and only delays the team.
    fake = FakeMessages([status_error(status), reply(TriageResult(**GOOD))])
    with pytest.raises(TriageUnavailable):
        run(ClaudeTriager(SimpleNamespace(messages=fake), "test-model"))
    assert len(fake.calls) == 1


def test_a_timeout_and_an_invalid_reply_share_the_same_two_tries():
    from tests.test_slice3 import invalid_reply_error

    fake = FakeMessages([anthropic.APITimeoutError(request=REQUEST), invalid_reply_error()])
    with pytest.raises(TriageUnavailable):
        run(ClaudeTriager(SimpleNamespace(messages=fake), "test-model"))
    assert len(fake.calls) == 2  # not two tries for each kind of failure


# ---------- whatever the triager does, the case moves on ----------


def test_the_overall_limit_is_two_tries_long():
    assert triage_flow.triage_deadline_seconds() == 30


def test_a_triager_that_never_returns_cannot_hold_the_case(app, client, db, monkeypatch):
    """The last line of defence: even a triager with no timeout of its own is cut off."""
    monkeypatch.setattr(triage_flow, "triage_deadline_seconds", lambda: 0.1)
    hanging = HangingTriager()
    app.dependency_overrides[get_triager] = lambda: hanging

    started = time.monotonic()
    report_a_case(client)
    assert time.monotonic() - started < GUARD

    assert hanging.calls == 1
    case = db.scalars(select(Case)).one()
    assert case.triage_status == "needs_review"
    assert case.urgency == "high"  # the existing fallback
    assert case.state != "REPORTED"  # it moved on


def test_a_team_is_alerted_even_when_triage_never_answers(app, client, seeded, monkeypatch):
    monkeypatch.setattr(triage_flow, "triage_deadline_seconds", lambda: 0.1)
    app.dependency_overrides[get_triager] = lambda: HangingTriager()

    report_a_case(client)

    case = seeded.scalars(select(Case)).one()
    assert case.triage_status == "needs_review"
    assert len(seeded.scalars(select(Dispatch)).all()) == 1  # the first team has its alert
