"""Settings, read from environment variables (and .env in development)."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    port: int = 8040
    public_base_url: str = "http://localhost:8040"
    channel: Literal["simulator", "whatsapp"] = "simulator"
    escalation_timeout_seconds: int = 600
    # For demos outside working hours: treat every team as open.
    ignore_opening_hours: bool = False

    # A booking is reminded once, this many hours before its slot; the job looks this often.
    # For a demo, a large window and a short check show a reminder seconds after booking.
    reminder_window_hours: int = 24
    reminder_check_seconds: int = 300

    # Default points at the local Docker database (docker-compose.yml).
    database_url: str = "postgresql+psycopg://pawsos:pawsos@localhost:5440/pawsos"
    media_dir: str = "uploads"

    # If set, /dashboard and /sim ask for this password. Empty means open (local development).
    dashboard_password: str | None = None

    google_service_account_file: str | None = None
    # One calendar per camp, written as "camp-slug=calendar-id,camp-slug=calendar-id".
    camp_calendars: str = ""

    # WhatsApp Business Cloud API. All four values are needed when CHANNEL=whatsapp.
    whatsapp_access_token: str | None = None
    whatsapp_phone_number_id: str | None = None
    whatsapp_verify_token: str | None = None  # a string we choose; Meta repeats it back once
    whatsapp_app_secret: str | None = None  # proves a webhook call really came from Meta
    whatsapp_api_version: str = "v27.0"
    # Approved template names, used only when WhatsApp refuses a message because the
    # person has not written in 24 hours. Empty means no template: the send fails as before.
    # See docs/WHATSAPP_SETUP.md, "Templates".
    whatsapp_template_language: str = "en"
    whatsapp_template_team_alert: str | None = None
    whatsapp_template_team_alert_expired: str | None = None
    whatsapp_template_book_reminder: str | None = None

    # Voice notes: "stub" understands only the simulator's pretend voice notes,
    # "bhashini" sends real voice notes to Bhashini (docs/VOICE_SETUP.md),
    # "off" declines every voice note.
    speech_to_text: Literal["off", "stub", "bhashini"] = "stub"
    # Bhashini's user id and ULCA API key; without both, real voice notes are declined.
    bhashini_user_id: str | None = None
    bhashini_api_key: str | None = None
    # Which Bhashini pipeline to use. This default is the "Initial Pipeline Models"
    # id from Bhashini's documentation, which offers speech recognition.
    bhashini_pipeline_id: str = "64392f96daac500b55c543cd"
    # The language assumed when a voice note comes without one (WhatsApp never says).
    bhashini_default_language: Literal["kok", "mr", "hi", "en"] = "kok"
    bhashini_timeout_seconds: float = 20.0
    # Voice notes arrive as OGG/Opus and are turned into WAV by ffmpeg before Bhashini.
    ffmpeg_path: str = "ffmpeg"

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-5-5"


@lru_cache
def get_settings() -> Settings:
    return Settings()
