"""Turning a voice note into text.

The rest of the app talks to the SpeechToText interface. Two services sit
behind it: a stand-in that only understands the simulator's pretend voice
notes, and Bhashini (India's language platform) for real voice notes in
Konkani, Marathi, Hindi and English.

We never keep the audio. Only the words are stored, with the report.
"""

import asyncio
import base64
import logging
import shutil
import subprocess
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)

LANGUAGES = {"en": "English", "hi": "Hindi", "mr": "Marathi", "kok": "Konkani"}
MAX_AUDIO_BYTES = 5 * 1024 * 1024
MAX_TRANSCRIPT_LENGTH = 1000
# The simulator has no microphone. Its "voice note" is the words themselves,
# sent as bytes under this made-up type.
SIMULATED_MIME = "text/x-simulated-voice"


@dataclass
class Transcript:
    text: str
    language: str  # a key of LANGUAGES


class SpeechUnavailable(Exception):
    """The voice note could not be turned into text."""


class SpeechToText(Protocol):
    name: str

    async def transcribe(self, audio: bytes, mime: str, language: str | None = None) -> Transcript:
        """Return what was said, or raise SpeechUnavailable."""
        ...


def clean_transcript(text: str) -> str:
    """Tidy what a speech service returns before we show or store it.

    TODO(me): Ayush improves this. Speech services often return odd spacing:
    "  a dog   is hurt \\n near the market ". Right now we only trim the ends.
    Make it also turn every run of spaces, tabs and line breaks inside the
    text into one single space, so that example becomes
    "a dog is hurt near the market".
    Hint: text.split() with no arguments splits on any whitespace and drops
    the empty pieces; " ".join(...) puts the words back together.
    Then remove the @pytest.mark.skip on test_clean_transcript in
    tests/test_slice10.py and run:
        .venv/bin/pytest -q tests/test_slice10.py -k clean
    """
    return text.strip()


class StubSpeechToText:
    """A stand-in. It reads the simulator's pretend voice notes and nothing else."""

    name = "stub"

    async def transcribe(self, audio: bytes, mime: str, language: str | None = None) -> Transcript:
        if mime != SIMULATED_MIME:
            raise SpeechUnavailable("The stand-in cannot listen to real audio.")
        text = audio.decode("utf-8", errors="replace")
        return Transcript(text=text, language=language if language in LANGUAGES else "en")


# ---------- Bhashini ----------
#
# Written from Bhashini's public API documentation, read 11 Nov 2026. NOT yet
# tried with real keys.
#   How the calls fit together: https://dibd-bhashini.gitbook.io/bhashini-apis/
#   Config call:   https://dibd-bhashini.gitbook.io/bhashini-apis/pipeline-config-call
#                  (and its /request-payload and /response-payload pages)
#   Compute call:  https://dibd-bhashini.gitbook.io/bhashini-apis/pipeline-compute-call
#                  (and its /request-payload and /response-payload pages)
#   ASR models per language:
#                  https://dibd-bhashini.gitbook.io/bhashini-apis/available-models-for-usage
#   Pipeline ids:  https://dibd-bhashini.gitbook.io/bhashini-apis/pipeline-search-call
#   Language codes and audio formats (ULCA schema):
#                  https://github.com/ULCA-IN/ulca/blob/master/specs/common-schemas.yml
#
# Two calls. The config call (our ULCA user id and API key) says which speech
# models exist for each language and returns a callback URL plus a separate
# inference key. The compute call sends the audio there with that key. The
# config answer is kept for a while, so most voice notes need only one call.
# The docs do not name the HTTP method; both calls are POSTs with a JSON body,
# as in Bhashini's own examples and client libraries.

BHASHINI_CONFIG_URL = "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline"
CONFIG_CACHE_SECONDS = 6 * 60 * 60
# Our language keys and the codes Bhashini may use for them. ULCA lists both
# "gom" (Goan Konkani) and "kok" (Konkani); we take whichever the config call offers.
BHASHINI_CODES = {"en": ("en",), "hi": ("hi",), "mr": ("mr",), "kok": ("gom", "kok")}
# WhatsApp voice notes are OGG/Opus, which is not in ULCA's list of audio
# formats, so every clip is turned into 16 kHz mono WAV with ffmpeg first.
SAMPLE_RATE = 16000
WAV_BYTES_PER_SECOND = SAMPLE_RATE * 2  # mono, 16-bit
MAX_AUDIO_SECONDS = 120
# The docs say the "vad" pre-processor lets audio longer than 30 seconds through.
VAD_AFTER_SECONDS = 30
FFMPEG_TIMEOUT_SECONDS = 20


@dataclass
class _PipelineConfig:
    callback_url: str
    key_header: str
    key_value: str
    service_ids: dict[str, str]  # Bhashini language code -> ASR service id
    fetched_at: float


class BhashiniSpeechToText:
    """Bhashini speech recognition. Without its keys it declines every voice note."""

    name = "bhashini"

    def __init__(
        self,
        user_id: str | None = None,
        api_key: str | None = None,
        pipeline_id: str | None = None,
        default_language: str = "kok",
        timeout_seconds: float = 20.0,
        ffmpeg: str = "ffmpeg",
        transport: httpx.AsyncBaseTransport | None = None,  # tests put a stand-in here
    ) -> None:
        self.user_id = user_id
        self.api_key = api_key
        self.pipeline_id = pipeline_id
        self.default_language = default_language if default_language in LANGUAGES else "kok"
        self.timeout = timeout_seconds
        self.ffmpeg = ffmpeg
        self.transport = transport
        self._config: _PipelineConfig | None = None
        self._config_lock = asyncio.Lock()

    @property
    def configured(self) -> bool:
        return bool(self.user_id and self.api_key and self.pipeline_id)

    async def transcribe(self, audio: bytes, mime: str, language: str | None = None) -> Transcript:
        if mime == SIMULATED_MIME:
            # The simulator's pretend voice notes keep working when Bhashini is chosen.
            return await StubSpeechToText().transcribe(audio, mime, language)
        if not self.configured:
            raise SpeechUnavailable(
                "Bhashini is not set up: BHASHINI_USER_ID, BHASHINI_API_KEY and "
                "BHASHINI_PIPELINE_ID are needed."
            )
        ours = language if language in LANGUAGES else self.default_language
        wav = await asyncio.to_thread(self._to_wav, audio)
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
                config = await self._pipeline_config(client)
                code, service_id = self._pick_service(config, ours)
                try:
                    text = await self._compute(client, config, code, service_id, wav)
                except _KeyRejected:
                    # The inference key may have been replaced: ask again once.
                    self._config = None
                    config = await self._pipeline_config(client)
                    code, service_id = self._pick_service(config, ours)
                    text = await self._compute(client, config, code, service_id, wav)
        except httpx.TimeoutException as error:
            raise SpeechUnavailable("Bhashini did not answer in time.") from error
        except httpx.HTTPError as error:
            raise SpeechUnavailable(
                f"Could not reach Bhashini ({type(error).__name__})."
            ) from error
        if not text.strip():
            raise SpeechUnavailable("Bhashini heard no words.")
        return Transcript(text=text, language=ours)

    # -- audio --

    def _to_wav(self, audio: bytes) -> bytes:
        """The clip as 16 kHz mono 16-bit WAV, made by ffmpeg. Runs in a worker thread."""
        program = shutil.which(self.ffmpeg)
        if program is None:
            raise SpeechUnavailable(
                "ffmpeg is not installed, so the voice note cannot be converted."
            )
        # Read from stdin, write mono 16-bit WAV at SAMPLE_RATE to stdout, nothing on disk.
        command = [
            program,
            *("-hide_banner", "-loglevel", "error", "-nostdin", "-i", "pipe:0"),
            *("-vn", "-ac", "1", "-ar", str(SAMPLE_RATE), "-t", str(MAX_AUDIO_SECONDS)),
            *("-acodec", "pcm_s16le", "-f", "wav", "pipe:1"),
        ]
        try:
            done = subprocess.run(
                command,
                input=audio,
                capture_output=True,
                timeout=FFMPEG_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise SpeechUnavailable(f"ffmpeg failed ({type(error).__name__}).") from error
        if done.returncode != 0 or len(done.stdout) <= 44:  # 44 bytes is an empty WAV header
            raise SpeechUnavailable("ffmpeg could not read the voice note.")
        return done.stdout

    # -- the config call --

    async def _pipeline_config(self, client: httpx.AsyncClient) -> _PipelineConfig:
        async with self._config_lock:
            cached = self._config
            if cached and time.monotonic() - cached.fetched_at < CONFIG_CACHE_SECONDS:
                return cached
            response = await client.post(
                BHASHINI_CONFIG_URL,
                headers={"userID": self.user_id or "", "ulcaApiKey": self.api_key or ""},
                json={
                    # No language here, so the answer lists the speech models for every language.
                    "pipelineTasks": [{"taskType": "asr"}],
                    "pipelineRequestConfig": {"pipelineId": self.pipeline_id},
                },
            )
            if response.status_code in (401, 403):
                raise SpeechUnavailable("Bhashini refused BHASHINI_USER_ID or BHASHINI_API_KEY.")
            if response.status_code != 200:
                raise SpeechUnavailable(f"Bhashini's config call failed ({response.status_code}).")
            self._config = _parse_config(_json(response))
            log.info(
                "Bhashini speech models found for: %s",
                ", ".join(sorted(self._config.service_ids)) or "none",
            )
            return self._config

    @staticmethod
    def _pick_service(config: _PipelineConfig, ours: str) -> tuple[str, str]:
        for code in BHASHINI_CODES[ours]:
            if code in config.service_ids:
                return code, config.service_ids[code]
        raise SpeechUnavailable(
            f"This Bhashini pipeline has no speech model for {LANGUAGES[ours]}."
        )

    # -- the compute call --

    async def _compute(
        self,
        client: httpx.AsyncClient,
        config: _PipelineConfig,
        code: str,
        service_id: str,
        wav: bytes,
    ) -> str:
        task_config: dict[str, Any] = {
            "language": {"sourceLanguage": code},
            "serviceId": service_id,
            "audioFormat": "wav",
            "samplingRate": SAMPLE_RATE,
        }
        if len(wav) / WAV_BYTES_PER_SECOND > VAD_AFTER_SECONDS:
            task_config["preProcessors"] = ["vad"]
        response = await client.post(
            config.callback_url,
            headers={config.key_header: config.key_value},
            json={
                "pipelineTasks": [{"taskType": "asr", "config": task_config}],
                "inputData": {"audio": [{"audioContent": base64.b64encode(wav).decode("ascii")}]},
            },
        )
        if response.status_code in (401, 403):
            raise _KeyRejected()
        if response.status_code != 200:
            raise SpeechUnavailable(f"Bhashini's speech call failed ({response.status_code}).")
        try:
            outputs = _json(response)["pipelineResponse"][0]["output"]
            return " ".join(str(part.get("source") or "") for part in outputs)
        except (KeyError, IndexError, TypeError, AttributeError) as error:
            raise SpeechUnavailable("Bhashini's answer was not in the expected shape.") from error


class _KeyRejected(SpeechUnavailable):
    """The compute call refused the inference key. Caught once to fetch a fresh key."""

    def __init__(self) -> None:
        super().__init__("Bhashini refused the inference key.")


def _json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError as error:
        raise SpeechUnavailable("Bhashini's answer was not JSON.") from error


def _parse_config(body: Any) -> _PipelineConfig:
    """Pull the callback URL, inference key and per-language speech models out of the config answer."""
    try:
        endpoint = body["pipelineInferenceAPIEndPoint"]
        key = endpoint["inferenceApiKey"]
        service_ids: dict[str, str] = {}
        for task in body["pipelineResponseConfig"]:
            if task.get("taskType") != "asr":
                continue
            for entry in task.get("config", []):
                code = entry["language"]["sourceLanguage"]
                # The first model listed for a language is the one we use.
                service_ids.setdefault(code, entry["serviceId"])
        config = _PipelineConfig(
            callback_url=str(endpoint["callbackUrl"]),
            key_header=str(key["name"]),
            key_value=str(key["value"]),
            service_ids=service_ids,
            fetched_at=time.monotonic(),
        )
    except (KeyError, TypeError) as error:
        raise SpeechUnavailable(
            "Bhashini's config answer was not in the expected shape."
        ) from error
    if not config.callback_url.startswith("https://") or not config.key_value:
        raise SpeechUnavailable("Bhashini's config answer had no usable address or key.")
    return config


@lru_cache
def get_speech_to_text() -> SpeechToText | None:
    """The app's speech service, chosen by SPEECH_TO_TEXT. None means voice notes are off."""
    settings = get_settings()
    choice = settings.speech_to_text
    if choice == "stub":
        return StubSpeechToText()
    if choice == "bhashini":
        service = BhashiniSpeechToText(
            user_id=settings.bhashini_user_id,
            api_key=settings.bhashini_api_key,
            pipeline_id=settings.bhashini_pipeline_id,
            default_language=settings.bhashini_default_language,
            timeout_seconds=settings.bhashini_timeout_seconds,
            ffmpeg=settings.ffmpeg_path,
        )
        if not service.configured:
            log.warning(
                "SPEECH_TO_TEXT=bhashini, but the Bhashini keys are not set. "
                "Real voice notes will be declined."
            )
        elif shutil.which(settings.ffmpeg_path) is None:
            log.warning(
                "SPEECH_TO_TEXT=bhashini, but ffmpeg was not found. Voice notes will be declined."
            )
        return service
    return None


async def listen(
    service: SpeechToText | None, audio: bytes, mime: str, language: str | None = None
) -> Transcript | None:
    """What was said, or None if we could not tell. Never raises."""
    if service is None or not audio or len(audio) > MAX_AUDIO_BYTES:
        return None
    try:
        heard = await service.transcribe(audio, mime, language)
    except SpeechUnavailable as reason:
        log.info("Voice note not transcribed: %s", reason)
        return None
    except Exception:
        log.exception("The speech service failed")
        return None
    text = clean_transcript(heard.text)[:MAX_TRANSCRIPT_LENGTH]
    return Transcript(text=text, language=heard.language) if text else None
