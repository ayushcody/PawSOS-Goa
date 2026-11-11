"""Stand-ins for Meta, shared by the WhatsApp tests.

FakeMeta answers like the Graph API and remembers what we sent. Webhook
calls are signed with a test-only secret. The "real" phone number is from
the 555 range that is reserved for fiction.
"""

import hashlib
import hmac
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.booking.calendar import get_calendar
from app.channels import whatsapp
from app.channels.whatsapp import WhatsAppCloudAdapter
from app.config import get_settings
from app.main import create_app
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
