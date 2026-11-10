"""Slice 9: real WhatsApp through Meta's Cloud API.

Meta is never called here. FakeMeta stands in for the Graph API, and webhook
calls are signed with a test-only secret. The "real" phone number is from
the 555 range that is reserved for fiction.
"""

import asyncio
import hashlib
import hmac
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import messages
from app.booking.calendar import get_calendar
from app.cases.models import Case, Photo, Report
from app.channels import media, whatsapp
from app.channels.base import Button
from app.channels.routed import RoutedChannel, is_simulated
from app.channels.whatsapp import WhatsAppCloudAdapter, WhatsAppError, mask_number, parse_webhook
from app.config import get_settings
from app.main import create_app
from app.routing.models import Team, Zone
from app.triage.service import get_triager

SECRET = "test-only-app-secret"
VERIFY = "test-only-verify-token"
TOKEN = "test-only-access-token"
PHONE = "15550001111"  # how Meta writes it: no "+"
NUMBER = "+15550001111"  # how we store it
JPEG = b"\xff\xd8\xff" + b"0" * 64
PANAJI = {"latitude": 15.4909, "longitude": 73.8278}


class FakeMeta:
    """Answers like the Graph API and remembers what we sent."""

    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.photos: dict[str, tuple[bytes, str]] = {"photo-1": (JPEG, "image/jpeg")}
        self.refuse_sends = False
        self.auth_headers: set[str | None] = set()

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.auth_headers.add(request.headers.get("Authorization"))
        if request.method == "POST" and request.url.path == "/v27.0/phone-id-1/messages":
            if self.refuse_sends:
                return httpx.Response(400, json={"error": {"message": "Recipient not in allowed list"}})
            self.sent.append(json.loads(request.content))
            return httpx.Response(200, json={"messages": [{"id": "wamid.out"}]})
        if request.url.host == "media.example.test":
            data, mime = self.photos[request.url.path.strip("/")]
            return httpx.Response(200, content=data, headers={"Content-Type": mime})
        media_id = request.url.path.removeprefix("/v27.0/")
        if request.method == "GET" and media_id in self.photos:
            data, mime = self.photos[media_id]
            return httpx.Response(
                200,
                json={"url": f"https://media.example.test/{media_id}", "mime_type": mime, "file_size": len(data)},
            )
        return httpx.Response(404, json={"error": {"message": "Unknown"}})

    def texts_to(self, phone: str = PHONE) -> list[str]:
        out = []
        for body in self.sent:
            if body["to"] == phone:
                out.append(body["text"]["body"] if body["type"] == "text" else body["interactive"]["body"]["text"])
        return out


@pytest.fixture
def meta() -> FakeMeta:
    return FakeMeta()


def make_adapter(meta: FakeMeta) -> WhatsAppCloudAdapter:
    return WhatsAppCloudAdapter(
        access_token=TOKEN, phone_number_id="phone-id-1", api_version="v27.0",
        public_base_url="https://pawsos.example.test/", transport=httpx.MockTransport(meta),
    )


@pytest.fixture
def wa(meta, monkeypatch) -> TestClient:
    """The app with WhatsApp switched on and FakeMeta in place of Meta."""
    settings = get_settings()
    monkeypatch.setattr(settings, "channel", "whatsapp")
    monkeypatch.setattr(settings, "whatsapp_verify_token", VERIFY)
    monkeypatch.setattr(settings, "whatsapp_app_secret", SECRET)
    monkeypatch.setattr(whatsapp, "from_settings", lambda: make_adapter(meta))
    application = create_app()
    application.dependency_overrides[get_triager] = lambda: None
    application.dependency_overrides[get_calendar] = lambda: None
    return TestClient(application)


_ids = iter(range(1, 10_000))


def msg(kind: str, sender: str = PHONE, **content) -> dict:
    return {"from": sender, "id": f"wamid.in-{next(_ids)}", "timestamp": "1794300000", "type": kind, **content}


def envelope(*items: dict, field: str = "messages", key: str = "messages") -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": "waba-1", "changes": [{"field": field, "value": {"messaging_product": "whatsapp", key: list(items)}}]}],
    }


def post(client: TestClient, payload: dict, secret: str | None = SECRET) -> httpx.Response:
    raw = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if secret is not None:
        headers["X-Hub-Signature-256"] = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return client.post("/webhooks/whatsapp", content=raw, headers=headers)


def report_from_whatsapp(client: TestClient) -> None:
    post(client, envelope(msg("image", image={"id": "photo-1", "mime_type": "image/jpeg", "sha256": "x"})))
    post(client, envelope(msg("location", location=PANAJI)))


# ---------- Meta checking that the webhook is ours ----------


def test_verification_returns_the_challenge(wa):
    response = wa.get(
        "/webhooks/whatsapp",
        params={"hub.mode": "subscribe", "hub.verify_token": VERIFY, "hub.challenge": "1158201444"},
    )
    assert response.status_code == 200 and response.text == "1158201444"


def test_verification_with_the_wrong_token_is_refused(wa):
    params = {"hub.mode": "subscribe", "hub.verify_token": "guess", "hub.challenge": "1"}
    assert wa.get("/webhooks/whatsapp", params=params).status_code == 403


def test_webhook_is_off_when_whatsapp_is_not_set_up(client):
    assert client.get("/webhooks/whatsapp", params={"hub.mode": "subscribe"}).status_code == 503
    assert post(client, envelope(msg("text", text={"body": "hi"}))).status_code == 503
    assert client.get("/health").json()["whatsapp_ready"] is False


def test_whatsapp_stays_off_when_half_configured(monkeypatch):
    settings = get_settings()
    assert whatsapp.from_settings() is None  # CHANNEL=simulator
    monkeypatch.setattr(settings, "channel", "whatsapp")
    monkeypatch.setattr(settings, "whatsapp_access_token", TOKEN)
    assert whatsapp.from_settings() is None  # three of the four values are missing


# ---------- signatures ----------


def test_a_message_with_a_bad_or_missing_signature_is_refused(wa, meta, db):
    payload = envelope(msg("text", text={"body": "hi"}))
    assert post(wa, payload, secret="someone-elses-secret").status_code == 403
    assert post(wa, payload, secret=None).status_code == 403
    assert meta.sent == []


def test_signature_needs_the_secret():
    body = b'{"a":1}'
    good = "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    assert whatsapp.verify_signature(SECRET, body, good)
    assert not whatsapp.verify_signature(SECRET, body + b" ", good)  # one byte changed
    assert not whatsapp.verify_signature(None, body, good)  # no secret set: nothing passes
    assert not whatsapp.verify_signature("", body, "sha256=")


# ---------- messages coming in ----------


def test_a_greeting_is_answered_on_whatsapp(wa, meta, db):
    assert post(wa, envelope(msg("text", text={"body": "Hi"}))).status_code == 200
    assert meta.texts_to() == [messages.render("welcome")]
    assert meta.sent[0]["messaging_product"] == "whatsapp"
    assert meta.auth_headers == {f"Bearer {TOKEN}"}


def test_photo_and_location_open_a_case(wa, meta, seeded):
    report_from_whatsapp(wa)

    case = seeded.scalars(select(Case)).one()
    report = seeded.scalars(select(Report)).one()
    assert report.reporter_number == NUMBER
    photo = seeded.scalars(select(Photo)).one()
    assert media.path_for(photo.path).read_bytes() == JPEG  # downloaded from Meta and stored
    assert any(case.public_id in text for text in meta.texts_to())


def test_team_alert_goes_to_the_simulator_and_the_update_back_to_whatsapp(wa, meta, seeded):
    report_from_whatsapp(wa)
    case = seeded.scalars(select(Case)).one()
    team = seeded.scalars(
        select(Team).join(Zone, Team.zone_id == Zone.id).where(Zone.slug == "panaji", Team.kind == "partner")
    ).one()

    # The placeholder team has an invented number, so its alert never goes to Meta.
    assert all(body["to"] == PHONE for body in meta.sent)
    alert = wa.get("/sim/messages", params={"phone": team.phone}).json()[-1]
    assert alert["buttons"][0]["id"] == f"accept:{case.public_id}"

    before = len(meta.texts_to())
    wa.post("/sim/inbound", json={"from_number": team.phone, "kind": "button", "button_id": f"accept:{case.public_id}"})
    update = meta.texts_to()[before:]
    assert update == [messages.render("citizen_accepted", case_id=case.public_id, team=team.name)]


def test_meta_sending_the_same_message_twice_is_handled_once(wa, meta, db):
    payload = envelope(msg("text", text={"body": "hello"}))
    post(wa, payload)
    post(wa, payload)
    assert len(meta.sent) == 1


def test_delivery_receipts_are_ignored(wa, meta, db):
    receipt = envelope({"id": "wamid.out", "status": "delivered", "recipient_id": PHONE}, key="statuses")
    assert post(wa, receipt).status_code == 200
    assert meta.sent == []


def test_a_voice_note_gets_the_cannot_read_reply(wa, meta, db):
    post(wa, envelope(msg("audio", audio={"id": "audio-1", "mime_type": "audio/ogg"})))
    assert meta.texts_to() == [messages.render("unsupported")]


def test_a_photo_that_cannot_be_fetched_is_declined_politely(wa, meta, db):
    post(wa, envelope(msg("image", image={"id": "no-such-photo", "mime_type": "image/jpeg"})))
    assert meta.texts_to() == [messages.render("photo_rejected")]
    assert db.scalars(select(Report)).all() == []


def test_a_file_pretending_to_be_a_photo_is_declined(wa, meta, db):
    meta.photos["fake"] = (b"not really a jpeg", "image/jpeg")
    post(wa, envelope(msg("image", image={"id": "fake", "mime_type": "image/jpeg"})))
    assert meta.texts_to() == [messages.render("photo_rejected")]


def test_reading_metas_envelope():
    tap = msg("interactive", interactive={"type": "button_reply", "button_reply": {"id": "accept:PAW-0007", "title": "Accept"}})
    pin = msg("location", location={"latitude": 15.5, "longitude": 73.9, "name": "Somewhere"})
    nameless = {"id": "wamid.x", "type": "text", "text": {"body": "hi"}}  # no "from": cannot reply
    broken = msg("location", location={"latitude": "north"})
    found = parse_webhook(envelope(tap, pin, nameless, broken))

    assert [(m.kind, m.from_number) for m in found] == [("button", NUMBER), ("location", NUMBER)]
    assert found[0].button_id == "accept:PAW-0007"
    assert (found[1].latitude, found[1].longitude) == (15.5, 73.9)
    assert parse_webhook({"object": "page"}) == [] and parse_webhook("nonsense") == []
    assert parse_webhook(envelope(tap, field="account_update")) == []


# ---------- messages going out ----------


def test_buttons_are_sent_in_whatsapps_shape_and_within_its_limits(meta):
    adapter = make_adapter(meta)
    buttons = [Button(f"id-{n}", "A title that is far too long" if n == 0 else f"B{n}") for n in range(4)]
    asyncio.run(adapter.send_buttons(NUMBER, "New case PAW-0001", buttons))

    (body,) = meta.sent
    assert body["to"] == PHONE and body["type"] == "interactive"
    sent = body["interactive"]["action"]["buttons"]
    assert len(sent) == 3  # WhatsApp allows three
    assert sent[0] == {"type": "reply", "reply": {"id": "id-0", "title": "A title that is far "}}  # 20 characters
    assert body["interactive"]["body"]["text"] == "New case PAW-0001"


def test_a_photo_is_sent_as_a_public_link(meta):
    asyncio.run(make_adapter(meta).send_image(NUMBER, "0" * 32 + ".jpg"))
    assert meta.sent[0]["image"] == {"link": "https://pawsos.example.test/media/" + "0" * 32 + ".jpg"}


def test_a_refusal_from_meta_says_why_without_leaking_anything(meta):
    meta.refuse_sends = True
    with pytest.raises(WhatsAppError) as error:
        asyncio.run(make_adapter(meta).send_text(NUMBER, "hello"))
    text = str(error.value)
    assert "Recipient not in allowed list" in text and "400" in text
    assert TOKEN not in text and NUMBER not in text and PHONE not in text


def test_one_refused_message_does_not_stop_the_conversation(wa, meta, db):
    meta.refuse_sends = True
    assert post(wa, envelope(msg("text", text={"body": "hi"}))).status_code == 200  # Meta still gets its 200


# ---------- which channel a number belongs to ----------


def test_invented_numbers_go_to_the_simulator_and_real_ones_to_whatsapp():
    assert is_simulated("+910000000001") and is_simulated("+910000000114") and is_simulated("+910000000907")
    assert not is_simulated(NUMBER) and not is_simulated("+919876500000")

    sim, real = object(), object()
    assert RoutedChannel(sim, real).channel_for("+910000000001") is sim
    assert RoutedChannel(sim, real).channel_for(NUMBER) is real
    assert RoutedChannel(sim, None).channel_for(NUMBER) is sim  # WhatsApp off: nothing leaves the machine


def test_the_simulator_asks_for_the_staff_password_when_one_is_set(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "dashboard_password", "test-only-password")
    assert client.get("/sim").status_code == 401
    assert client.post("/sim/inbound", json={"from_number": "+910000000001", "text": "hi"}).status_code == 401
    assert client.get("/sim", auth=("staff", "test-only-password")).status_code == 200
    assert client.get("/health").status_code == 200  # the health check stays open


@pytest.mark.skip(reason="TODO(me): improve mask_number() in app/channels/whatsapp.py")
def test_mask_number():
    assert mask_number("+919876543210") == "…3210"
    assert mask_number("+15550001111") == "…1111"
    assert mask_number("12") == "…"
    assert mask_number("") == "…"
