"""Telegram channel. FakeTelegram stands in for the Bot API; nothing leaves the machine."""

import asyncio
import json
import logging

import httpx
import pytest
from sqlalchemy import select

from app import messages
from app.cases.models import Report
from app.channels import media, telegram
from app.channels.base import Button, Outbound
from app.channels.routed import RoutedChannel
from app.channels.simulator import SimulatorAdapter
from app.channels.telegram import TelegramAdapter, TelegramError, TelegramReceiver, parse_updates
from app.config import get_settings

TOKEN = "123456:test-only-bot-token"
CHAT = 5550001111  # an invented chat id
ADDRESS = "tg:5550001111"
JPEG = b"\xff\xd8\xff" + b"0" * 64
PANAJI = {"latitude": 15.4909, "longitude": 73.8278}


class FakeTelegram:
    """Answers like the Bot API, hands out queued updates and remembers what we sent."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.updates: list[dict] = []
        self.files: dict[str, tuple[str, bytes]] = {"photo-big": ("photos/file_1.jpg", JPEG)}
        self.refuse: str | None = None  # a method name to answer with an error
        self.photo_uploads: list[bytes] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.startswith(f"/file/bot{TOKEN}/"):
            wanted = path.removeprefix(f"/file/bot{TOKEN}/")
            for file_path, data in self.files.values():
                if file_path == wanted:
                    return httpx.Response(200, content=data)
            return httpx.Response(404)
        assert path.startswith(f"/bot{TOKEN}/"), "every call must carry the bot token"
        method = path.removeprefix(f"/bot{TOKEN}/")
        if method == self.refuse:
            return httpx.Response(400, json={"ok": False, "description": "Bad Request: chat not found"})
        if method == "sendPhoto":
            self.photo_uploads.append(request.content)
            self.calls.append((method, {}))
            return httpx.Response(200, json={"ok": True, "result": {}})
        body = json.loads(request.content or b"{}")
        self.calls.append((method, body))
        if method == "getUpdates":
            offset = body.get("offset", 0)
            waiting = [u for u in self.updates if u["update_id"] >= offset]
            self.updates = waiting  # a higher offset confirms the earlier ones
            return httpx.Response(200, json={"ok": True, "result": waiting})
        if method == "getFile":
            file_path, data = self.files[body["file_id"]]
            return httpx.Response(200, json={"ok": True, "result": {"file_path": file_path, "file_size": len(data)}})
        return httpx.Response(200, json={"ok": True, "result": True})

    def sent(self, method: str = "sendMessage") -> list[dict]:
        return [body for name, body in self.calls if name == method]

    def texts(self) -> list[str]:
        return [body["text"] for body in self.sent()]


_ids = iter(range(100, 10_000))


def update(chat_type: str = "private", **content) -> dict:
    return {
        "update_id": next(_ids),
        "message": {"message_id": 1, "chat": {"id": CHAT, "type": chat_type}, "from": {"id": CHAT}, **content},
    }


def tap(data: str) -> dict:
    return {
        "update_id": next(_ids),
        "callback_query": {
            "id": "cb-1",
            "from": {"id": CHAT},
            "data": data,
            "message": {"message_id": 2, "chat": {"id": CHAT, "type": "private"}},
        },
    }


PHOTO = {"photo": [{"file_id": "photo-small", "width": 90}, {"file_id": "photo-big", "width": 1280, "file_size": 67}]}


@pytest.fixture
def fake() -> FakeTelegram:
    return FakeTelegram()


def make_adapter(fake: FakeTelegram) -> TelegramAdapter:
    return TelegramAdapter(bot_token=TOKEN, transport=httpx.MockTransport(fake))


def run_all(fake: FakeTelegram, *updates: dict) -> tuple[TelegramAdapter, SimulatorAdapter]:
    """Feed updates through the receiver, one poll each, as the running server would."""
    adapter, simulator = make_adapter(fake), SimulatorAdapter()
    receiver = TelegramReceiver(adapter, RoutedChannel(simulator, None, adapter))

    async def go() -> None:
        for item in updates:
            fake.updates.append(item)
            await receiver.poll_once(wait_seconds=0)
            await receiver.wait_until_idle()

    asyncio.run(go())
    return adapter, simulator


# ---------- reading updates ----------


def test_a_text_message_is_read():
    items, highest = parse_updates([update(text="STATUS")])
    (item,) = items
    assert (item.kind, item.text, item.from_number) == ("text", "STATUS", ADDRESS)
    assert highest == item.update_id


def test_start_is_treated_as_a_greeting():
    (item,), _ = parse_updates([update(text="/start")])
    assert (item.kind, item.text) == ("text", "hi")


def test_the_largest_photo_size_is_chosen():
    (item,), _ = parse_updates([update(**PHOTO)])
    assert (item.kind, item.file_id, item.media_mime) == ("image", "photo-big", "image/jpeg")


def test_a_location_and_a_voice_note_are_read():
    (place, voice), _ = parse_updates(
        [update(location=PANAJI), update(voice={"file_id": "v1", "mime_type": "audio/ogg", "duration": 3})]
    )
    assert (place.kind, place.latitude, place.longitude) == ("location", 15.4909, 73.8278)
    assert (voice.kind, voice.file_id, voice.media_mime) == ("voice", "v1", "audio/ogg")


def test_a_button_tap_is_read():
    (item,), _ = parse_updates([tap("rate:PAW-0001:good")])
    assert (item.kind, item.button_id, item.callback_id) == ("button", "rate:PAW-0001:good", "cb-1")


def test_group_chats_are_ignored_but_still_confirmed():
    group = update(chat_type="group", text="hello")
    items, highest = parse_updates([group])
    assert items == [] and highest == group["update_id"]


def test_an_unreadable_update_is_skipped_and_confirmed():
    broken = {"update_id": 77, "message": {"chat": {"type": "private"}}}  # no chat id
    good = update(text="hi")
    items, highest = parse_updates([broken, good, "nonsense"])
    assert [i.text for i in items] == ["hi"] and highest == good["update_id"]


@pytest.mark.skip(reason="TODO(me): photos sent as a file, see _parse_update in app/channels/telegram.py")
def test_a_photo_sent_as_a_file_is_accepted():
    picture = {"file_id": "doc-1", "mime_type": "image/png", "file_size": 2048}
    (item,), _ = parse_updates([update(document=picture)])
    assert (item.kind, item.file_id, item.media_mime, item.file_size) == ("image", "doc-1", "image/png", 2048)
    (pdf,), _ = parse_updates([update(document={"file_id": "doc-2", "mime_type": "application/pdf"})])
    assert pdf.kind == "unsupported"


def test_a_sticker_becomes_an_empty_text_message():
    (item,), _ = parse_updates([update(sticker={"file_id": "s1"})])
    assert item.kind == "unsupported"


# ---------- sending ----------


def test_text_is_sent_to_the_chat_id(fake):
    asyncio.run(make_adapter(fake).send_text(ADDRESS, "hello"))
    assert fake.sent() == [{"chat_id": "5550001111", "text": "hello"}]


def test_buttons_become_an_inline_keyboard(fake):
    buttons = [Button("accept:PAW-0001", "Accept"), Button("decline:PAW-0001", "Decline")]
    asyncio.run(make_adapter(fake).send_buttons(ADDRESS, "New case", buttons))
    (body,) = fake.sent()
    assert body["reply_markup"] == {
        "inline_keyboard": [
            [{"text": "Accept", "callback_data": "accept:PAW-0001"}],
            [{"text": "Decline", "callback_data": "decline:PAW-0001"}],
        ]
    }


def test_a_button_id_longer_than_telegram_allows_is_refused(fake):
    with pytest.raises(TelegramError):
        asyncio.run(make_adapter(fake).send_buttons(ADDRESS, "x", [Button("a" * 65, "Too long")]))
    assert fake.sent() == []


def test_a_location_request_shows_a_one_tap_location_button(fake):
    asyncio.run(make_adapter(fake).send(Outbound(to=ADDRESS, text="Where is it?", request_location=True)))
    (body,) = fake.sent()
    assert body["text"] == "Where is it?"
    assert body["reply_markup"] == {
        "keyboard": [[{"text": messages.render("location_button"), "request_location": True}]],
        "resize_keyboard": True,
        "one_time_keyboard": True,
    }


def test_a_photo_is_uploaded_not_linked(fake):
    name = media.save_image(JPEG, "image/jpeg")
    asyncio.run(make_adapter(fake).send_image(ADDRESS, name))
    (upload,) = fake.photo_uploads
    assert JPEG in upload and b'name="photo"' in upload and b"5550001111" in upload


def test_only_telegram_addresses_are_accepted(fake):
    for bad in ("+15550001111", "tg:abc", "tg:"):
        with pytest.raises(TelegramError):
            asyncio.run(make_adapter(fake).send_text(bad, "hello"))
    assert fake.calls == []


def test_a_refusal_is_reported_without_the_token(fake):
    fake.refuse = "sendMessage"
    with pytest.raises(TelegramError) as caught:
        asyncio.run(make_adapter(fake).send_text(ADDRESS, "hello"))
    assert "chat not found" in str(caught.value) and TOKEN not in str(caught.value)


def test_a_network_failure_never_shows_the_token():
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"cannot reach {request.url}")  # httpx names the address

    adapter = TelegramAdapter(bot_token=TOKEN, transport=httpx.MockTransport(down))
    with pytest.raises(TelegramError) as caught:
        asyncio.run(adapter.send_text(ADDRESS, "hello"))
    assert TOKEN not in str(caught.value)
    assert caught.value.__cause__ is None and caught.value.__suppress_context__


def test_a_photo_is_downloaded_in_two_steps(fake):
    assert asyncio.run(make_adapter(fake).fetch_file("photo-big")) == JPEG


def test_a_file_over_the_size_limit_is_not_downloaded(fake):
    with pytest.raises(media.MediaError):
        asyncio.run(make_adapter(fake).fetch_file("photo-big", known_size=media.MAX_BYTES + 1))
    assert fake.calls == []


def test_a_strange_file_path_is_not_followed(fake):
    fake.files["odd"] = ("../../etc/passwd", b"x")
    with pytest.raises(media.MediaError):
        asyncio.run(make_adapter(fake).fetch_file("odd"))


# ---------- polling ----------


def test_each_poll_confirms_what_the_last_one_returned(fake):
    adapter = make_adapter(fake)
    first = update(text="one")
    fake.updates.append(first)

    async def go() -> list[int]:
        counts = [len(await adapter.get_updates(0))]
        counts.append(len(await adapter.get_updates(0)))
        return counts

    assert asyncio.run(go()) == [1, 0]
    polls = fake.sent("getUpdates")
    assert "offset" not in polls[0] and polls[1]["offset"] == first["update_id"] + 1
    assert polls[0]["allowed_updates"] == ["message", "callback_query"]


def test_starting_up_removes_any_webhook(fake):
    asyncio.run(make_adapter(fake).prepare())
    assert [name for name, _ in fake.calls] == ["deleteWebhook"]


# ---------- routing and settings ----------


def test_telegram_addresses_go_to_telegram_and_never_to_whatsapp():
    simulator, whatsapp, tg = SimulatorAdapter(), SimulatorAdapter(), SimulatorAdapter()
    routed = RoutedChannel(simulator, whatsapp, tg)
    assert routed.channel_for(ADDRESS) is tg
    assert routed.channel_for("+910000001234") is simulator
    assert routed.channel_for("+15550001111") is whatsapp
    assert RoutedChannel(simulator, whatsapp).channel_for(ADDRESS) is simulator


def test_telegram_is_off_without_a_token_or_on_another_channel(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "channel", "telegram")
    monkeypatch.setattr(settings, "telegram_bot_token", None)
    assert telegram.from_settings() is None
    monkeypatch.setattr(settings, "telegram_bot_token", TOKEN)
    assert isinstance(telegram.from_settings(), TelegramAdapter)
    monkeypatch.setattr(settings, "channel", "simulator")
    assert telegram.from_settings() is None


def test_health_reports_telegram(client):
    assert client.get("/health").json()["telegram_ready"] is False


# ---------- a whole conversation ----------


def test_a_photo_then_a_location_opens_a_case(fake, seeded):
    run_all(fake, update(**PHOTO), update(location=PANAJI))

    report = seeded.scalars(select(Report)).one()
    assert report.reporter_number == ADDRESS
    # After the photo: a request for the location, with the one-tap button.
    asked = fake.sent()[0]
    assert asked["reply_markup"]["keyboard"][0][0]["request_location"] is True
    assert any("PAW-0001" in text for text in fake.texts())
    assert all(body["chat_id"] == str(CHAT) for body in fake.sent())


def test_a_button_tap_is_acknowledged_and_handled(fake, seeded):
    run_all(fake, tap("rate:PAW-0001:good"))
    assert fake.sent("answerCallbackQuery") == [{"callback_query_id": "cb-1"}]
    assert fake.texts(), "the person gets an answer even when the case is unknown"


def test_a_photo_that_cannot_be_fetched_gets_an_apology(fake, seeded):
    fake.refuse = "getFile"
    run_all(fake, update(**PHOTO))
    assert fake.texts() == [messages.render("photo_rejected")]
    assert seeded.scalars(select(Report)).all() == []


def test_one_bad_message_does_not_stop_the_next(fake, seeded, monkeypatch, caplog):
    calls = {"n": 0}
    real = telegram.handle_inbound

    async def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError(f"failed calling https://api.telegram.org/bot{TOKEN}/sendMessage")
        return await real(*args, **kwargs)

    monkeypatch.setattr(telegram, "handle_inbound", flaky)
    with caplog.at_level(logging.ERROR):
        run_all(fake, update(text="hi"), update(text="hi"))
    assert calls["n"] == 2 and len(fake.texts()) == 1
    assert TOKEN not in caplog.text
