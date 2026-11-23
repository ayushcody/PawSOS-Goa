"""Real WhatsApp, through Meta's WhatsApp Business Cloud API.

Two directions:

  In:  Meta calls our webhook (POST /webhooks/whatsapp) for every message a
       person sends to our number. We check Meta's signature, answer 200 at
       once, and do the real work afterwards.
  Out: we call Meta's Graph API to send text, buttons and photos. Outside the
       24-hour window WhatsApp refuses those (error 131047); a message that
       has a template configured is then sent once more as that template.

Checked against Meta's documentation on 11 Nov 2026 (Graph API v27.0).
"""

import asyncio
import hashlib
import hmac
import json
import logging
import re
import secrets
from collections import OrderedDict, defaultdict
from dataclasses import dataclass
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app import messages
from app.booking.calendar import CalendarClient, get_calendar
from app.channels import media, templates
from app.channels.base import Button, ChannelAdapter, InboundMessage, Outbound
from app.config import get_settings
from app.contacts import language_for, saved_language
from app.conversation import handle_inbound
from app.db import new_session
from app.triage.service import Triager, get_triager
from app.voice import speech

log = logging.getLogger(__name__)

GRAPH_URL = "https://graph.facebook.com"
MAX_TEXT = 4096
MAX_BUTTON_BODY = 1024
MAX_BUTTON_TITLE = 20
MAX_BUTTONS = 3
MAX_TEMPLATE_PARAM = 600  # our own cap, so a filled-in template body stays under 1024
WINDOW_CLOSED = 131047  # Meta: more than 24 hours since the person last wrote to us
_MEDIA_ID = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")


class WhatsAppError(RuntimeError):
    """Meta refused something we asked for.

    `code` is Meta's error code, if it gave one. `body` is Meta's whole "error"
    object with the recipient's number removed; `subcode`, `details` and
    `trace_id` are pulled out of it, because they are what tells a closed
    24-hour window, a test number's allowed list, an expired token and a
    restricted account apart. Quote `trace_id` to Meta support.
    """

    def __init__(self, message: str, code: int | None = None, body: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.body = body or {}
        subcode = self.body.get("error_subcode")
        self.subcode = subcode if isinstance(subcode, int) else None
        error_data = self.body.get("error_data")
        self.details = str(error_data.get("details") or "") if isinstance(error_data, dict) else ""
        self.trace_id = str(self.body.get("fbtrace_id") or "")


def _without_number(value: Any, digits: str) -> Any:
    """Meta's error with every copy of the recipient's number replaced, at any depth."""
    if isinstance(value, str):
        return value.replace(digits, mask_number("+" + digits)) if digits else value
    if isinstance(value, dict):
        return {key: _without_number(item, digits) for key, item in value.items()}
    if isinstance(value, list):
        return [_without_number(item, digits) for item in value]
    return value


def mask_number(number: str) -> str:
    """A phone number made safe to write in a log.

    TODO(me): Ayush improves this. Right now every number becomes the same
    text, which is safe but makes logs hard to follow when two people write
    in at once. Make it keep only the last four digits:
        "+915550001111" -> "…1111"
        "12"            -> "…"      (too short to show anything safely)
    Rule: if the number has more than 6 characters, return "…" followed by
    its last 4 characters; otherwise return just "…".
    Then remove the @pytest.mark.skip on test_mask_number in
    tests/test_slice9.py and run:
        .venv/bin/pytest -q tests/test_slice9.py -k mask
    Worth a thought: why not show the first digits instead of the last?
    """
    return "(number hidden)"


# ---------- reading what Meta sends ----------


@dataclass
class WhatsAppInbound:
    """One message from Meta's webhook, before any photo has been downloaded."""

    message_id: str
    from_number: str  # with a leading "+"
    kind: str  # text, image, location, button, voice or unsupported
    text: str | None = None
    media_id: str | None = None
    media_mime: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    button_id: str | None = None


def verify_signature(app_secret: str | None, raw_body: bytes, header: str | None) -> bool:
    """Did this request really come from Meta?

    Meta signs the exact bytes of the body with our app secret (HMAC-SHA256)
    and sends the result in X-Hub-Signature-256 as "sha256=<hex>". We work
    out the same signature and compare. Without the secret, nothing passes.
    """
    if not app_secret or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


def _parse_message(raw: dict[str, Any]) -> WhatsAppInbound | None:
    sender, message_id = raw.get("from"), raw.get("id")
    if not sender or not message_id:
        return None  # Meta can omit "from" for people without a visible number; we cannot reply
    item = WhatsAppInbound(
        message_id=str(message_id), from_number="+" + str(sender).lstrip("+"), kind="unsupported"
    )
    kind = raw.get("type")
    if kind == "text":
        item.kind, item.text = "text", str(raw.get("text", {}).get("body", ""))[:1000]
    elif kind == "image":
        image = raw.get("image", {})
        item.kind, item.media_id = "image", image.get("id")
        item.media_mime = str(image.get("mime_type", "")).split(";")[0].strip()
    elif kind == "audio":  # a voice note, or any other audio clip
        audio = raw.get("audio", {})
        item.kind, item.media_id = "voice", audio.get("id")
        item.media_mime = str(audio.get("mime_type", "")).split(";")[0].strip()
    elif kind == "location":
        place = raw.get("location", {})
        item.kind = "location"
        item.latitude, item.longitude = float(place["latitude"]), float(place["longitude"])
    elif kind == "interactive" and raw.get("interactive", {}).get("type") == "button_reply":
        item.kind = "button"
        item.button_id = str(raw["interactive"]["button_reply"]["id"])[:64]
    elif kind == "button":  # a quick-reply button on a template; our id comes back as the payload
        item.kind = "button"
        item.button_id = str(raw["button"]["payload"])[:64]
    return item


def parse_webhook(payload: Any) -> list[WhatsAppInbound]:
    """Pull the messages out of Meta's nested envelope. Delivery receipts are ignored."""
    if not isinstance(payload, dict) or payload.get("object") != "whatsapp_business_account":
        return []
    found = []
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            if change.get("field") != "messages":
                continue
            for raw in (change.get("value") or {}).get("messages") or []:
                try:
                    item = _parse_message(raw)
                except (KeyError, TypeError, ValueError, AttributeError):
                    log.warning("Skipped a WhatsApp message we could not read.")
                    continue
                if item is not None:
                    found.append(item)
    return found


def parse_failed_statuses(payload: Any) -> list[tuple[str, int | None]]:
    """(message id, error code) for each of our messages Meta reports as failed.

    Meta may accept a message and only report later, in a status webhook,
    that it could not be delivered (for example error 131047).
    """
    if not isinstance(payload, dict) or payload.get("object") != "whatsapp_business_account":
        return []
    failed = []
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            if change.get("field") != "messages":
                continue
            for status in (change.get("value") or {}).get("statuses") or []:
                if not isinstance(status, dict) or status.get("status") != "failed":
                    continue
                if not status.get("id"):
                    continue
                errors = status.get("errors") or [{}]
                code = errors[0].get("code") if isinstance(errors[0], dict) else None
                failed.append((str(status["id"]), code if isinstance(code, int) else None))
    return failed


def _template_text(value: str) -> str:
    """A template parameter on one line and trimmed. We keep parameters free of
    newlines, tabs and runs of spaces, which Meta is reported to refuse."""
    flat = " ".join(value.split())
    if len(flat) > MAX_TEMPLATE_PARAM:
        flat = flat[: MAX_TEMPLATE_PARAM - 1].rstrip() + "…"
    return flat or "-"


# ---------- sending ----------


class WhatsAppCloudAdapter(ChannelAdapter):
    name = "whatsapp"

    def __init__(
        self,
        access_token: str,
        phone_number_id: str,
        api_version: str,
        public_base_url: str,
        transport: httpx.AsyncBaseTransport | None = None,  # tests pass a fake one
    ) -> None:
        self.phone_number_id = phone_number_id
        self.public_base_url = public_base_url.rstrip("/")
        # Messages Meta accepted that have a template to fall back to, by message id,
        # in case a status webhook later says they failed with 131047. Memory only.
        self._awaiting_status: OrderedDict[str, Outbound] = OrderedDict()
        self.client = httpx.AsyncClient(
            base_url=f"{GRAPH_URL}/{api_version}",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
            transport=transport,
        )

    async def _send(self, to_number: str, body: dict[str, Any]) -> str | None:
        """Send one message. Returns Meta's message id ("wamid..."), if it gave one."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number.lstrip("+"),
            **body,
        }
        response = await self.client.post(f"/{self.phone_number_id}/messages", json=payload)
        if response.status_code >= 400:
            raise self._refusal(response, to_number)
        try:
            return str(response.json()["messages"][0]["id"])
        except (ValueError, KeyError, IndexError, TypeError):
            return None

    @staticmethod
    def _refusal(response: httpx.Response, to_number: str) -> WhatsAppError:
        """Meta's answer to a refused send, as an error that carries (and logs) all of it."""
        try:
            error = response.json()["error"]
            if not isinstance(error, dict):
                raise TypeError
        except (ValueError, KeyError, TypeError):
            error = {}
        error = _without_number(error, to_number.lstrip("+"))
        code = error.get("code")
        code = code if isinstance(code, int) else None
        reason = error.get("message") or "no reason given"
        full = json.dumps(error, ensure_ascii=False, sort_keys=True) if error else "(no JSON error body)"
        log.warning(
            "WhatsApp refused a message to %s (HTTP %s): %s", mask_number(to_number), response.status_code, full
        )
        return WhatsAppError(
            f"WhatsApp refused a message to {mask_number(to_number)} "
            f"({response.status_code}): {reason}. Meta's full error: {full}",
            code=code,
            body=error,
        )

    @staticmethod
    def _text_body(text: str) -> dict[str, Any]:
        return {"type": "text", "text": {"body": text[:MAX_TEXT]}}

    @staticmethod
    def _buttons_body(text: str, buttons: list[Button]) -> dict[str, Any]:
        # WhatsApp's limits: three buttons, 20 characters each.
        replies = [
            {"type": "reply", "reply": {"id": b.id, "title": b.title[:MAX_BUTTON_TITLE]}}
            for b in buttons[:MAX_BUTTONS]
        ]
        return {
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": text[:MAX_BUTTON_BODY]},
                "action": {"buttons": replies},
            },
        }

    @staticmethod
    def _location_request_body(text: str) -> dict[str, Any]:
        # Meta's "location request message": the text with a Send location button.
        # The answer comes back as an ordinary location message. Checked against
        # Meta's documentation on 11 Nov 2026 (body text: at most 1024 characters).
        return {
            "type": "interactive",
            "interactive": {
                "type": "location_request_message",
                "body": {"text": text[:MAX_BUTTON_BODY]},
                "action": {"name": "send_location"},
            },
        }

    async def send_text(self, to_number: str, text: str) -> None:
        await self._send(to_number, self._text_body(text))

    async def send_location_request(self, to_number: str, text: str) -> None:
        try:
            await self._send(to_number, self._location_request_body(text))
        except WhatsAppError:
            # The button is a convenience. If Meta refuses it, the words alone
            # still tell the person how to share a location.
            log.warning(
                "WhatsApp refused a location request to %s; sending plain text instead.",
                mask_number(to_number),
            )
            await self.send_text(to_number, text)

    async def send_buttons(self, to_number: str, text: str, buttons: list[Button]) -> None:
        await self._send(to_number, self._buttons_body(text, buttons))

    async def send_template(
        self,
        to_number: str,
        template_name: str,
        language_code: str,
        body_params: tuple[str, ...] | list[str] = (),
        button_payloads: tuple[str, ...] | list[str] = (),
    ) -> str | None:
        """Send an approved template message. Works outside the 24-hour window.

        `body_params` fill the body's {{1}}, {{2}}, ... in order. `button_payloads`
        go to the template's quick-reply buttons in order; a tap comes back in the
        webhook as a "button" message carrying that payload.
        """
        components: list[dict[str, Any]] = []
        if body_params:
            components.append(
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": _template_text(p)} for p in body_params],
                }
            )
        for index, payload in enumerate(button_payloads):
            components.append(
                {
                    "type": "button",
                    "sub_type": "quick_reply",
                    "index": str(index),
                    "parameters": [{"type": "payload", "payload": payload}],
                }
            )
        template: dict[str, Any] = {"name": template_name, "language": {"code": language_code}}
        if components:
            template["components"] = components
        return await self._send(to_number, {"type": "template", "template": template})

    async def send(self, message: Outbound) -> None:
        """Photo, then text or buttons. Outside the 24-hour window: its template instead."""
        try:
            if message.media_name:
                await self.send_image(message.to, message.media_name)
            if message.request_location:
                await self.send_location_request(message.to, message.text)
                return
            if message.buttons:
                body = self._buttons_body(message.text, message.buttons)
            else:
                body = self._text_body(message.text)
            message_id = await self._send(message.to, body)
        except WhatsAppError as error:
            if error.code != WINDOW_CLOSED:
                raise
            await self._send_template_instead(message, error)
            return
        if message.template is not None and message_id:
            self._awaiting_status[message_id] = message
            while len(self._awaiting_status) > 1000:
                self._awaiting_status.popitem(last=False)

    async def _send_template_instead(self, message: Outbound, error: Exception) -> None:
        """The one retry: the same message as its approved template, if it has one."""
        fallback = message.template
        name = templates.template_name(fallback.key) if fallback else None
        if fallback is None or name is None:
            log.warning(
                "WhatsApp's 24-hour window is closed for %s and no template is configured "
                "for %s, so the message was not sent.",
                mask_number(message.to),
                fallback.key if fallback else "this message",
            )
            raise error
        log.info(
            "24-hour window closed for %s: sending template %s (%s) instead.",
            mask_number(message.to), name, fallback.key,
        )
        if message.media_name:
            log.info("The photo with %s is not sent: the template has no photo.", fallback.key)
        await self.send_template(
            message.to,
            name,
            get_settings().whatsapp_template_language,
            fallback.params,
            fallback.button_payloads,
        )

    async def on_failed_status(self, message_id: str, code: int | None) -> None:
        """Meta accepted one of our messages, then reported that it failed."""
        message = self._awaiting_status.pop(message_id, None)  # popped: retried at most once
        if code != WINDOW_CLOSED:
            log.warning("WhatsApp could not deliver a message (error %s).", code)
            return
        if message is None:
            log.warning(
                "WhatsApp's 24-hour window was closed for a message with no template "
                "(or one sent before a restart), so it was not delivered."
            )
            return
        try:
            await self._send_template_instead(message, WhatsAppError("24-hour window closed", code))
        except Exception:
            log.exception("Could not send a template to %s", mask_number(message.to))

    async def send_image(self, to_number: str, media_name: str) -> None:
        # Meta fetches the photo from us, so PUBLIC_BASE_URL must be reachable from outside.
        link = f"{self.public_base_url}/media/{media_name}"
        await self._send(to_number, {"type": "image", "image": {"link": link}})

    async def fetch_media(self, media_id: str) -> tuple[bytes, str]:
        """Download a photo someone sent. Two steps: ask where it is, then fetch it."""
        if not _MEDIA_ID.match(media_id):
            raise media.MediaError("That photo could not be found.")
        info = (await self.client.get(f"/{media_id}")).raise_for_status().json()
        if int(info.get("file_size", 0)) > media.MAX_BYTES:
            raise media.MediaError("That photo is larger than 10 MB.")
        url = str(info["url"])
        if not url.startswith("https://"):
            raise media.MediaError("That photo could not be found.")
        # The address is only good for five minutes, and needs our token too.
        photo = (await self.client.get(url)).raise_for_status()
        return photo.content, str(info.get("mime_type", "")).split(";")[0].strip()

    async def close(self) -> None:
        await self.client.aclose()


def from_settings() -> WhatsAppCloudAdapter | None:
    """The real adapter, or None when WhatsApp is switched off or half-configured."""
    settings = get_settings()
    if settings.channel != "whatsapp":
        return None
    needed = {
        "WHATSAPP_ACCESS_TOKEN": settings.whatsapp_access_token,
        "WHATSAPP_PHONE_NUMBER_ID": settings.whatsapp_phone_number_id,
        "WHATSAPP_VERIFY_TOKEN": settings.whatsapp_verify_token,
        "WHATSAPP_APP_SECRET": settings.whatsapp_app_secret,
    }
    missing = [name for name, value in needed.items() if not value]
    if missing:
        log.warning("CHANNEL=whatsapp but %s not set. WhatsApp stays off.", ", ".join(missing))
        return None
    if not settings.dashboard_password:
        log.warning("WhatsApp is on but DASHBOARD_PASSWORD is empty: /sim and /dashboard are open.")
    return WhatsAppCloudAdapter(
        access_token=settings.whatsapp_access_token,
        phone_number_id=settings.whatsapp_phone_number_id,
        api_version=settings.whatsapp_api_version,
        public_base_url=settings.public_base_url,
    )


# ---------- the webhook ----------


class _SeenIds:
    """Message ids we have already handled. Meta sends a message again if we are slow."""

    def __init__(self, limit: int = 5000) -> None:
        self._ids: OrderedDict[str, None] = OrderedDict()
        self._limit = limit

    def first_time(self, message_id: str) -> bool:
        if message_id in self._ids:
            return False
        self._ids[message_id] = None
        if len(self._ids) > self._limit:
            self._ids.popitem(last=False)
        return True


def build_router(adapter: WhatsAppCloudAdapter | None, outbound: ChannelAdapter) -> APIRouter:
    """`adapter` talks to Meta; `outbound` is where replies go (it may route to the simulator)."""
    router = APIRouter(prefix="/webhooks/whatsapp", tags=["whatsapp"])
    seen = _SeenIds()
    # One person's messages are handled one at a time, so a photo and a
    # location sent together always end up in the same report.
    locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    def _require_adapter() -> WhatsAppCloudAdapter:
        if adapter is None:
            raise HTTPException(status_code=503, detail="WhatsApp is not set up on this server.")
        return adapter

    async def _to_inbound(
        item: WhatsAppInbound, listener: speech.SpeechToText | None, session: Session
    ) -> InboundMessage | None:
        """Our channel-neutral message, or None if we answered the person ourselves."""
        if item.kind == "image":
            try:
                data, mime = await _require_adapter().fetch_media(item.media_id or "")
                name = media.save_image(data, mime or item.media_mime or "")
            except (media.MediaError, httpx.HTTPError, KeyError, ValueError):
                log.warning("Could not fetch a photo from %s.", mask_number(item.from_number))
                language = language_for(session, item.from_number)
                await outbound.send_text(
                    item.from_number, messages.render("photo_rejected", language)
                )
                return None
            return InboundMessage(
                from_number=item.from_number, kind="image", media_name=name, media_mime=mime
            )
        if item.kind == "voice":
            try:
                audio, mime = await _require_adapter().fetch_media(item.media_id or "")
            except (media.MediaError, httpx.HTTPError, KeyError, ValueError):
                audio, mime = b"", ""
            # The audio is used once and never stored; only the words are kept.
            # WhatsApp never says which language a voice note is in. Listen in the
            # person's own language if we know it, else the speech service's default.
            saved = saved_language(session, item.from_number)
            heard = await speech.listen(listener, audio, mime or item.media_mime or "", saved)
            return InboundMessage(
                from_number=item.from_number,
                kind="voice",
                text=heard.text if heard else None,
                # Not a detection: the language was assumed, so it must not be adopted.
                language=None,
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

    async def _process(
        item: WhatsAppInbound,
        triager: Triager | None,
        calendar: CalendarClient | None,
        listener: speech.SpeechToText | None,
    ) -> None:
        async with locks[item.from_number]:
            session = new_session()
            try:
                message = await _to_inbound(item, listener, session)
                if message is not None:
                    await handle_inbound(message, outbound, session, triager, calendar)
                session.commit()
            except Exception:
                session.rollback()
                log.exception("Could not handle a WhatsApp message from %s", mask_number(item.from_number))
            finally:
                session.close()

    @router.get("", response_class=PlainTextResponse)
    def verify(
        mode: Annotated[str, Query(alias="hub.mode")] = "",
        token: Annotated[str, Query(alias="hub.verify_token")] = "",
        challenge: Annotated[str, Query(alias="hub.challenge")] = "",
    ) -> str:
        """Meta calls this once when the webhook is saved, to check the address is ours."""
        _require_adapter()
        expected = get_settings().whatsapp_verify_token or ""
        if mode != "subscribe" or not secrets.compare_digest(token.encode(), expected.encode()):
            raise HTTPException(status_code=403, detail="Wrong verify token.")
        return challenge

    @router.post("")
    async def receive(
        request: Request,
        background: BackgroundTasks,
        triager: Annotated[Triager | None, Depends(get_triager)],
        calendar: Annotated[CalendarClient | None, Depends(get_calendar)],
        listener: Annotated[speech.SpeechToText | None, Depends(speech.get_speech_to_text)],
    ) -> dict[str, bool]:
        _require_adapter()
        raw = await request.body()
        signature = request.headers.get("X-Hub-Signature-256")
        if not verify_signature(get_settings().whatsapp_app_secret, raw, signature):
            raise HTTPException(status_code=403, detail="Bad signature.")
        try:
            payload = json.loads(raw)
        except ValueError:
            raise HTTPException(status_code=400, detail="Not JSON.") from None

        # Answer Meta straight away; triage can take several seconds and Meta
        # would otherwise send the same message again.
        for item in parse_webhook(payload):
            if seen.first_time(item.message_id):
                background.add_task(_process, item, triager, calendar, listener)
        # A message Meta accepted may fail later. Outside the 24-hour window we
        # retry it once as its template (on_failed_status forgets it after that).
        for message_id, code in parse_failed_statuses(payload):
            background.add_task(_require_adapter().on_failed_status, message_id, code)
        return {"ok": True}

    return router
