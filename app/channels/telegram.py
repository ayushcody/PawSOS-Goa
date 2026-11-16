"""Telegram, through the Bot API.

Why it is here: Meta will not deliver WhatsApp messages from a business that
has not been verified with company documents (D-092). A Telegram bot needs no
verification, and offers the same things we use on WhatsApp: photos, a one-tap
location button, reply buttons and voice notes.

Two directions:

  In:  we ask Telegram for new messages (getUpdates, "long polling"). The call
       waits up to 25 seconds for something to arrive, then we ask again. No
       public address is needed, so this works from a laptop with no tunnel.
  Out: we call sendMessage and sendPhoto.

A person on Telegram has no phone number we can see. Their chat id stands in
for it, written "tg:<chat id>" wherever the app expects a number.

The bot token is part of every Telegram address. httpx puts the address in its
error messages, so its errors are never logged or re-raised as they are: see
`_call`.

Checked against Telegram's documentation on 16 Nov 2026 (Bot API 10.4).
"""

import asyncio
import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app import messages
from app.booking.calendar import CalendarClient, get_calendar
from app.channels import media
from app.channels.base import Button, ChannelAdapter, InboundMessage
from app.channels.whatsapp import mask_number
from app.config import get_settings
from app.contacts import language_for, saved_language
from app.conversation import handle_inbound
from app.db import new_session
from app.triage.service import Triager, get_triager
from app.voice import speech

log = logging.getLogger(__name__)

API_URL = "https://api.telegram.org"
PREFIX = "tg:"
MAX_TEXT = 4096
MAX_CALLBACK_BYTES = 64  # Telegram's limit on a button's callback_data
POLL_SECONDS = 25  # how long one getUpdates call waits for a message
RETRY_SECONDS = 5  # pause after a failed call, so a dead network is not hammered
_CHAT_ID = re.compile(r"^-?\d{1,17}$")
_FILE_ID = re.compile(r"^[A-Za-z0-9_-]{1,255}$")
_FILE_PATH = re.compile(r"^[A-Za-z0-9_./-]{1,255}$")


class TelegramError(RuntimeError):
    """Telegram refused something, or could not be reached. Never contains the token."""


def is_telegram(number: str) -> bool:
    return number.startswith(PREFIX)


def address_for(chat_id: int | str) -> str:
    return f"{PREFIX}{chat_id}"


def _chat_id(number: str) -> str:
    chat_id = number.removeprefix(PREFIX)
    if not is_telegram(number) or not _CHAT_ID.match(chat_id):
        raise TelegramError("That is not a Telegram address.")
    return chat_id


# ---------- reading what Telegram sends ----------


@dataclass
class TelegramInbound:
    """One message or button tap from Telegram, before any file has been downloaded."""

    update_id: int
    from_number: str  # "tg:<chat id>"
    kind: str  # text, image, location, button, voice or unsupported
    text: str | None = None
    file_id: str | None = None
    file_size: int = 0
    media_mime: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    button_id: str | None = None
    callback_id: str | None = None  # a button tap must be acknowledged with this


def _parse_update(raw: dict[str, Any]) -> TelegramInbound | None:
    update_id = int(raw["update_id"])
    tap = raw.get("callback_query")
    if tap:
        chat = (tap.get("message") or {}).get("chat") or {}
        if chat.get("type") != "private":
            return None
        return TelegramInbound(
            update_id=update_id,
            from_number=address_for(int(chat["id"])),
            kind="button",
            button_id=str(tap.get("data") or "")[:MAX_CALLBACK_BYTES],
            callback_id=str(tap["id"]),
        )
    message = raw.get("message")
    if not message:
        return None
    chat = message.get("chat") or {}
    if chat.get("type") != "private":
        return None  # the bot talks to one person at a time, never in a group
    item = TelegramInbound(
        update_id=update_id, from_number=address_for(int(chat["id"])), kind="unsupported"
    )
    if message.get("photo"):
        # Telegram sends the same photo in several sizes; take the biggest.
        best = max(message["photo"], key=lambda size: int(size.get("width", 0)))
        item.kind, item.file_id = "image", str(best["file_id"])
        item.file_size = int(best.get("file_size") or 0)
        item.media_mime = "image/jpeg"  # Telegram re-encodes every photo as JPEG
    # TODO(me): Ayush adds photos sent "as a file". Telegram lets people attach a
    # picture without compression; it then arrives under "document", not "photo":
    #     {"document": {"file_id": "...", "mime_type": "image/png", "file_size": 12345}}
    # Right now that falls through to "unsupported" and the person is told we
    # cannot read it. Add an `elif message.get("document")` branch here that, only
    # when mime_type is image/jpeg, image/png or image/webp, sets kind "image",
    # file_id, file_size and media_mime from the document. Any other document
    # stays unsupported. Then remove the @pytest.mark.skip on
    # test_a_photo_sent_as_a_file_is_accepted in tests/test_telegram.py and run:
    #     .venv/bin/pytest -q tests/test_telegram.py -k file
    # Worth a thought: why check the mime type here when save_image checks it again?
    elif message.get("voice"):
        voice = message["voice"]
        item.kind, item.file_id = "voice", str(voice["file_id"])
        item.file_size = int(voice.get("file_size") or 0)
        item.media_mime = str(voice.get("mime_type") or "audio/ogg").split(";")[0].strip()
    elif message.get("location"):
        place = message["location"]
        item.kind = "location"
        item.latitude, item.longitude = float(place["latitude"]), float(place["longitude"])
    elif isinstance(message.get("text"), str):
        text = message["text"][:1000]
        # Telegram's own Start button sends "/start": treat it as a greeting.
        item.kind, item.text = "text", "hi" if text.strip().lower().startswith("/start") else text
    return item


def parse_updates(payload: Any) -> tuple[list[TelegramInbound], int | None]:
    """The messages in one getUpdates answer, and the highest update id seen.

    The id is returned even for updates we skip, so that a message we cannot
    read is not handed to us again for ever.
    """
    found: list[TelegramInbound] = []
    highest: int | None = None
    if not isinstance(payload, list):
        return found, highest
    for raw in payload:
        try:
            update_id = int(raw["update_id"])
        except (KeyError, TypeError, ValueError):
            continue
        highest = update_id if highest is None else max(highest, update_id)
        try:
            item = _parse_update(raw)
        except (KeyError, TypeError, ValueError, AttributeError):
            log.warning("Skipped a Telegram message we could not read.")
            continue
        if item is not None:
            found.append(item)
    return found, highest


# ---------- talking to Telegram ----------


class TelegramAdapter(ChannelAdapter):
    name = "telegram"

    def __init__(
        self,
        bot_token: str,
        transport: httpx.AsyncBaseTransport | None = None,  # tests pass a fake one
    ) -> None:
        self._token = bot_token
        # Longer than POLL_SECONDS, so a quiet wait is not mistaken for a dead line.
        self.client = httpx.AsyncClient(base_url=API_URL, timeout=POLL_SECONDS + 10, transport=transport)
        self.offset: int | None = None  # the next update id to ask for

    async def _call(self, method: str, **kwargs: Any) -> Any:
        """Call one Bot API method and return its result.

        Every failure becomes a TelegramError with no address in it: httpx's own
        errors name the URL, and the URL contains the bot token.
        """
        try:
            response = await self.client.post(f"/bot{self._token}/{method}", **kwargs)
            body = response.json()
        except httpx.HTTPError as error:
            raise TelegramError(f"{method}: could not reach Telegram ({type(error).__name__}).") from None
        except ValueError:
            raise TelegramError(f"{method}: Telegram's answer was not JSON.") from None
        if not isinstance(body, dict) or not body.get("ok"):
            reason = body.get("description", "no reason given") if isinstance(body, dict) else "no reason given"
            raise TelegramError(f"{method}: Telegram refused ({response.status_code}): {reason}")
        return body.get("result")

    @staticmethod
    def _inline_keyboard(buttons: list[Button]) -> dict[str, Any]:
        # One button per row, so long titles are not cut short on a narrow phone.
        return {"inline_keyboard": [[{"text": b.title, "callback_data": b.id}] for b in buttons]}

    @staticmethod
    def _location_keyboard() -> dict[str, Any]:
        # A keyboard button with request_location sends the person's current
        # location when tapped. It arrives as an ordinary location message.
        label = messages.render("location_button")
        return {
            "keyboard": [[{"text": label, "request_location": True}]],
            "resize_keyboard": True,
            "one_time_keyboard": True,
        }

    async def _send_message(self, to_number: str, text: str, markup: dict[str, Any] | None) -> None:
        body: dict[str, Any] = {"chat_id": _chat_id(to_number), "text": text[:MAX_TEXT]}
        if markup is not None:
            body["reply_markup"] = markup
        await self._call("sendMessage", json=body)

    async def send_text(self, to_number: str, text: str) -> None:
        await self._send_message(to_number, text, None)

    async def send_buttons(self, to_number: str, text: str, buttons: list[Button]) -> None:
        for button in buttons:
            if len(button.id.encode()) > MAX_CALLBACK_BYTES:
                raise TelegramError("A button id is longer than Telegram allows.")
        await self._send_message(to_number, text, self._inline_keyboard(buttons))

    async def send_location_request(self, to_number: str, text: str) -> None:
        await self._send_message(to_number, text, self._location_keyboard())

    async def send_image(self, to_number: str, media_name: str) -> None:
        path = media.path_for(media_name)
        if path is None:
            raise TelegramError("That photo could not be found.")
        # Unlike WhatsApp, the photo is uploaded, so no public address is needed.
        await self._call(
            "sendPhoto",
            data={"chat_id": _chat_id(to_number)},
            files={"photo": (media_name, path.read_bytes())},
        )

    async def acknowledge_tap(self, callback_id: str) -> None:
        """Tell Telegram a button tap was received, which stops its spinner."""
        await self._call("answerCallbackQuery", json={"callback_query_id": callback_id})

    async def fetch_file(self, file_id: str, known_size: int = 0) -> bytes:
        """Download a photo or voice note. Two steps: ask where it is, then fetch it."""
        if not _FILE_ID.match(file_id) or known_size > media.MAX_BYTES:
            raise media.MediaError("That file could not be fetched.")
        info = await self._call("getFile", json={"file_id": file_id})
        path = str((info or {}).get("file_path") or "")
        if int((info or {}).get("file_size") or 0) > media.MAX_BYTES:
            raise media.MediaError("That file is larger than 10 MB.")
        if not _FILE_PATH.match(path) or ".." in path:
            raise media.MediaError("That file could not be fetched.")
        try:
            response = await self.client.get(f"/file/bot{self._token}/{path}")
        except httpx.HTTPError as error:
            raise TelegramError(f"download: could not reach Telegram ({type(error).__name__}).") from None
        if response.status_code != 200 or len(response.content) > media.MAX_BYTES:
            raise media.MediaError("That file could not be fetched.")
        return response.content

    async def prepare(self) -> None:
        """Run once before polling: getUpdates does not work while a webhook is set."""
        await self._call("deleteWebhook", json={})

    async def get_updates(self, wait_seconds: int = POLL_SECONDS) -> list[TelegramInbound]:
        """Ask for new messages. Asking with a higher offset confirms the earlier ones."""
        body: dict[str, Any] = {
            "timeout": wait_seconds,
            "allowed_updates": ["message", "callback_query"],
        }
        if self.offset is not None:
            body["offset"] = self.offset
        items, highest = parse_updates(await self._call("getUpdates", json=body))
        if highest is not None:
            self.offset = highest + 1
        return items

    async def close(self) -> None:
        await self.client.aclose()


def from_settings() -> TelegramAdapter | None:
    """The real adapter, or None when Telegram is switched off or has no token."""
    settings = get_settings()
    if settings.channel != "telegram":
        return None
    if not settings.telegram_bot_token:
        log.warning("CHANNEL=telegram but TELEGRAM_BOT_TOKEN is not set. Telegram stays off.")
        return None
    if not settings.dashboard_password:
        log.warning("Telegram is on but DASHBOARD_PASSWORD is empty: /sim and /dashboard are open.")
    return TelegramAdapter(bot_token=settings.telegram_bot_token)


# ---------- handling what arrives ----------


class TelegramReceiver:
    """Turns Telegram's messages into ours and hands them to the conversation."""

    def __init__(self, adapter: TelegramAdapter, outbound: ChannelAdapter) -> None:
        self.adapter = adapter
        self.outbound = outbound  # where replies go (it may route to the simulator)
        # One person's messages are handled one at a time, so a photo and a
        # location sent together always end up in the same report.
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._tasks: set[asyncio.Task[None]] = set()

    async def _to_inbound(
        self, item: TelegramInbound, listener: speech.SpeechToText | None, session: Session
    ) -> InboundMessage | None:
        """Our channel-neutral message, or None if we answered the person ourselves."""
        if item.kind == "image":
            try:
                data = await self.adapter.fetch_file(item.file_id or "", item.file_size)
                name = media.save_image(data, item.media_mime or "")
            except (media.MediaError, TelegramError):
                log.warning("Could not fetch a photo from %s.", mask_number(item.from_number))
                language = language_for(session, item.from_number)
                await self.outbound.send_text(item.from_number, messages.render("photo_rejected", language))
                return None
            return InboundMessage(
                from_number=item.from_number, kind="image", media_name=name, media_mime=item.media_mime
            )
        if item.kind == "voice":
            try:
                audio = await self.adapter.fetch_file(item.file_id or "", item.file_size)
            except (media.MediaError, TelegramError):
                audio = b""
            # The audio is used once and never stored; only the words are kept.
            saved = saved_language(session, item.from_number)
            heard = await speech.listen(listener, audio, item.media_mime or "", saved)
            # The language was assumed, not detected, so it must not be adopted.
            return InboundMessage(
                from_number=item.from_number, kind="voice", text=heard.text if heard else None, language=None
            )
        if item.kind == "unsupported":
            # An empty text message gets the "can't read that yet" reply.
            return InboundMessage(from_number=item.from_number, kind="text")
        return InboundMessage(
            from_number=item.from_number,
            kind=item.kind,
            text=item.text,
            latitude=item.latitude,
            longitude=item.longitude,
            button_id=item.button_id,
        )

    async def process(
        self,
        item: TelegramInbound,
        triager: Triager | None,
        calendar: CalendarClient | None,
        listener: speech.SpeechToText | None,
    ) -> None:
        if item.callback_id:
            try:
                await self.adapter.acknowledge_tap(item.callback_id)
            except TelegramError as error:
                log.warning("Could not acknowledge a button tap: %s", error)
        async with self._locks[item.from_number]:
            session = new_session()
            try:
                message = await self._to_inbound(item, listener, session)
                if message is not None:
                    await handle_inbound(message, self.outbound, session, triager, calendar)
                session.commit()
            except Exception as error:  # noqa: BLE001  (one bad message must not stop the poller)
                session.rollback()
                # Not log.exception: a traceback through httpx could show the token.
                log.error(
                    "Could not handle a Telegram message from %s (%s).",
                    mask_number(item.from_number),
                    type(error).__name__,
                )
            finally:
                session.close()

    async def poll_once(self, wait_seconds: int = POLL_SECONDS) -> int:
        """Fetch waiting messages and start handling each. Returns how many arrived."""
        items = await self.adapter.get_updates(wait_seconds)
        if not items:
            return 0
        triager, calendar, listener = get_triager(), get_calendar(), speech.get_speech_to_text()
        for item in items:
            # Triage can take several seconds: handle messages side by side, so
            # one slow photo does not hold up everybody else.
            task = asyncio.create_task(self.process(item, triager, calendar, listener))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
        return len(items)

    async def wait_until_idle(self) -> None:
        """Wait for every message in hand to be dealt with (used by tests and shutdown)."""
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    async def run(self) -> None:
        """Poll for ever. Started when the server starts, cancelled when it stops."""
        try:
            await self.adapter.prepare()
        except TelegramError as error:
            log.warning("Telegram start-up: %s", error)
        log.info("Telegram: listening for messages.")
        while True:
            try:
                await self.poll_once()
            except TelegramError as error:
                log.warning("Telegram: %s Trying again in %s seconds.", error, RETRY_SECONDS)
                await asyncio.sleep(RETRY_SECONDS)
