"""Ask Claude to look at a photo and return a checked TriageResult.

The rest of the app depends only on the Triager interface, so tests swap in
a fake and never call the real API.
"""

import asyncio
import base64
import logging
from functools import lru_cache
from typing import Protocol

import anthropic
from pydantic import ValidationError

from app.config import get_settings
from app.messages import DEFAULT_LANGUAGE
from app.triage.images import UnreadableImage, prepare_for_vision
from app.triage.prompt import SYSTEM_PROMPT, user_prompt
from app.triage.schema import TriageResult

log = logging.getLogger(__name__)

# The first try, plus one retry: whether the call timed out, the API was
# unreachable or busy, or the reply did not fit the schema. Never more, so a
# photo cannot hold up a rescue for longer than ATTEMPTS x the timeout.
ATTEMPTS = 2
# Statuses worth one more try. Any other 4xx means the request itself is wrong.
RETRY_STATUSES = {408, 409, 429}


class TriageUnavailable(Exception):
    """No usable triage result. The case must go to a person instead."""


class Triager(Protocol):
    async def triage(self, image: bytes, language: str = DEFAULT_LANGUAGE) -> TriageResult:
        """Assess one photo. The first-aid steps come back in `language` (a messages.LANGUAGES code)."""
        ...


class ClaudeTriager:
    def __init__(
        self, client: anthropic.AsyncAnthropic, model: str, timeout: float | None = None
    ) -> None:
        self._client = client
        self._model = model
        # Seconds one call may take, enforced here as well as in the client:
        # the client's timeout is per read, not for the whole answer.
        self._timeout = get_settings().triage_timeout_seconds if timeout is None else timeout

    async def triage(self, image: bytes, language: str = DEFAULT_LANGUAGE) -> TriageResult:
        try:
            jpeg, media_type = prepare_for_vision(image)
        except UnreadableImage as error:
            raise TriageUnavailable(str(error)) from error
        encoded = base64.standard_b64encode(jpeg).decode("ascii")

        problem = "no valid reply"
        for attempt in range(1, ATTEMPTS + 1):
            try:
                async with asyncio.timeout(self._timeout):
                    response = await self._client.messages.parse(
                        model=self._model,
                        max_tokens=16000,
                        system=SYSTEM_PROMPT,
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "image",
                                        "source": {
                                            "type": "base64",
                                            "media_type": media_type,
                                            "data": encoded,
                                        },
                                    },
                                    {"type": "text", "text": user_prompt(language)},
                                ],
                            }
                        ],
                        output_format=TriageResult,
                    )
            except (TimeoutError, anthropic.APITimeoutError):
                log.warning("Triage: no answer within %s s on attempt %s.", self._timeout, attempt)
                problem = "timed out"
                continue
            except anthropic.AuthenticationError as error:
                log.error("Triage: the Anthropic API key was rejected. Check ANTHROPIC_API_KEY.")
                raise TriageUnavailable("API key rejected") from error
            except anthropic.APIStatusError as error:
                log.warning("Triage: API returned status %s on attempt %s.", error.status_code, attempt)
                if error.status_code in RETRY_STATUSES or error.status_code >= 500:
                    problem = f"API status {error.status_code}"
                    continue
                raise TriageUnavailable(f"API status {error.status_code}") from error
            except anthropic.APIConnectionError:
                log.warning("Triage: could not reach the API on attempt %s.", attempt)
                problem = "API unreachable"
                continue
            except (ValidationError, ValueError) as error:
                # The reply was not valid JSON or did not fit TriageResult.
                log.warning("Triage: invalid reply on attempt %s: %s", attempt, error)
                problem = "invalid reply"
                continue

            # What the call used, so spending can be added up from the log.
            usage = getattr(response, "usage", None)
            if usage is not None:
                log.info(
                    "Triage: %s used %s input and %s output tokens.",
                    self._model, usage.input_tokens, usage.output_tokens,
                )
            if response.stop_reason == "refusal":
                log.warning("Triage: the model declined on attempt %s.", attempt)
                problem = "the model declined"
                continue
            if response.parsed_output is None:
                log.warning("Triage: no parsed output on attempt %s.", attempt)
                problem = "no valid reply"
                continue
            return response.parsed_output

        raise TriageUnavailable(f"{problem}, after {ATTEMPTS} attempts")


@lru_cache
def get_triager() -> Triager | None:
    """The app's triager, or None when no API key is set (cases then go to a person)."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        log.warning("ANTHROPIC_API_KEY is not set. Photos will be queued for human review.")
        return None
    # max_retries=0: the SDK would otherwise retry twice by itself, and the one
    # retry is ours (ATTEMPTS), so the worst case stays at two tries.
    client = anthropic.AsyncAnthropic(
        api_key=settings.anthropic_api_key, timeout=settings.triage_timeout_seconds, max_retries=0
    )
    return ClaudeTriager(client, settings.anthropic_model, timeout=settings.triage_timeout_seconds)
