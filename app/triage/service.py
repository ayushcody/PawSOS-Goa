"""Ask Claude to look at a photo and return a checked TriageResult.

The rest of the app depends only on the Triager interface, so tests swap in
a fake and never call the real API.
"""

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

ATTEMPTS = 2  # the first try, plus one retry if the reply does not fit the schema


class TriageUnavailable(Exception):
    """No usable triage result. The case must go to a person instead."""


class Triager(Protocol):
    async def triage(self, image: bytes, language: str = DEFAULT_LANGUAGE) -> TriageResult:
        """Assess one photo. The first-aid steps come back in `language` (a messages.LANGUAGES code)."""
        ...


class ClaudeTriager:
    def __init__(self, client: anthropic.AsyncAnthropic, model: str) -> None:
        self._client = client
        self._model = model

    async def triage(self, image: bytes, language: str = DEFAULT_LANGUAGE) -> TriageResult:
        try:
            jpeg, media_type = prepare_for_vision(image)
        except UnreadableImage as error:
            raise TriageUnavailable(str(error)) from error
        encoded = base64.standard_b64encode(jpeg).decode("ascii")

        for attempt in range(1, ATTEMPTS + 1):
            try:
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
            except anthropic.AuthenticationError as error:
                log.error("Triage: the Anthropic API key was rejected. Check ANTHROPIC_API_KEY.")
                raise TriageUnavailable("API key rejected") from error
            except anthropic.RateLimitError as error:
                log.warning("Triage: rate limited after the SDK's own retries.")
                raise TriageUnavailable("rate limited") from error
            except anthropic.APIStatusError as error:
                log.warning("Triage: API returned status %s.", error.status_code)
                raise TriageUnavailable(f"API status {error.status_code}") from error
            except anthropic.APIConnectionError as error:
                log.warning("Triage: could not reach the API.")
                raise TriageUnavailable("API unreachable") from error
            except (ValidationError, ValueError) as error:
                # The reply was not valid JSON or did not fit TriageResult.
                log.warning("Triage: invalid reply on attempt %s: %s", attempt, error)
                continue

            if response.stop_reason == "refusal":
                log.warning("Triage: the model declined on attempt %s.", attempt)
                continue
            if response.parsed_output is None:
                log.warning("Triage: no parsed output on attempt %s.", attempt)
                continue
            return response.parsed_output

        raise TriageUnavailable(f"no valid reply after {ATTEMPTS} attempts")


@lru_cache
def get_triager() -> Triager | None:
    """The app's triager, or None when no API key is set (cases then go to a person)."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        log.warning("ANTHROPIC_API_KEY is not set. Photos will be queued for human review.")
        return None
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=60.0)
    return ClaudeTriager(client, settings.anthropic_model)
