"""Meta's whole error body is kept and logged, so a refused send says exactly why.

Before this, only Meta's `message` and `code` survived. The subcode, the details and
the trace id (what tells a closed 24-hour window, the allowed list for a test number,
an expired token and a restricted account apart) were thrown away.
"""

import asyncio
import logging

import httpx
import pytest

from app.channels.base import Outbound, deliver
from app.channels.whatsapp import WhatsAppCloudAdapter, WhatsAppError

NUMBER = "+15550001111"  # the 555 range is reserved for fiction

# The shape of a real Graph API error (Meta's documentation, "Error codes").
RESTRICTED = {
    "error": {
        "message": "(#131031) Business Account locked",
        "type": "OAuthException",
        "code": 131031,
        "error_subcode": 2494010,
        "error_data": {
            "messaging_product": "whatsapp",
            "details": "Account has been locked. Verify your business to continue. Recipient 15550001111",
        },
        "fbtrace_id": "AbCdEfTrace123",
    }
}


def adapter(body: dict, status: int = 400) -> WhatsAppCloudAdapter:
    return WhatsAppCloudAdapter(
        access_token="test-only-access-token",
        phone_number_id="phone-id-1",
        api_version="v27.0",
        public_base_url="https://pawsos.example.test",
        transport=httpx.MockTransport(lambda request: httpx.Response(status, json=body)),
    )


def test_the_error_keeps_every_field_meta_sent():
    with pytest.raises(WhatsAppError) as caught:
        asyncio.run(adapter(RESTRICTED).send_text(NUMBER, "hello"))
    error = caught.value
    assert error.code == 131031
    assert error.subcode == 2494010
    assert error.details.startswith("Account has been locked")
    assert error.trace_id == "AbCdEfTrace123"
    text = str(error)
    for part in ("131031", "2494010", "OAuthException", "Verify your business", "AbCdEfTrace123"):
        assert part in text


def test_the_recipient_number_never_appears_even_if_meta_repeats_it():
    with pytest.raises(WhatsAppError) as caught:
        asyncio.run(adapter(RESTRICTED).send_text(NUMBER, "hello"))
    assert "15550001111" not in str(caught.value)
    assert "15550001111" not in str(caught.value.body)
    assert "test-only-access-token" not in str(caught.value)


def test_a_failed_send_logs_metas_full_error(caplog):
    with caplog.at_level(logging.WARNING):
        asyncio.run(deliver(adapter(RESTRICTED), [Outbound(to=NUMBER, text="hello")]))
    logged = caplog.text
    assert "2494010" in logged and "AbCdEfTrace123" in logged and "Verify your business" in logged
    assert "15550001111" not in logged


def test_an_answer_that_is_not_json_still_gives_a_readable_error():
    broken = WhatsAppCloudAdapter(
        access_token="t", phone_number_id="p", api_version="v27.0", public_base_url="https://x.test",
        transport=httpx.MockTransport(lambda request: httpx.Response(502, text="Bad gateway")),
    )
    with pytest.raises(WhatsAppError) as caught:
        asyncio.run(broken.send_text(NUMBER, "hello"))
    assert "502" in str(caught.value) and caught.value.code is None
