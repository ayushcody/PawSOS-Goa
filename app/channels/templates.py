"""WhatsApp template messages, for when the 24-hour window is closed.

WhatsApp only lets us send a free-form message to someone who has messaged us
in the last 24 hours. Outside that window only pre-approved templates go
through (Meta's error 131047). Rescue teams and people with a camp booking are
the ones most likely to be outside it.

Each message key below has a matching template in Meta Business Manager (see
docs/WHATSAPP_SETUP.md, "Templates"). The template's name comes from a
setting, so nothing is sent until someone has created and named it. PARAMS
gives the order of the template's {{1}}, {{2}}, ... placeholders; it must
match the body text in the setup guide.
"""

from collections.abc import Mapping

from app.channels.base import TemplateFallback
from app.config import get_settings

PARAMS: dict[str, tuple[str, ...]] = {
    "team_alert": ("case_id", "zone", "urgency", "seen", "map_link", "reports", "window"),
    "team_alert_expired": ("case_id",),
    "book_reminder": ("camp", "date", "time", "venue", "ref"),
}

# Message key -> the setting that holds its approved template name.
_SETTING = {
    "team_alert": "whatsapp_template_team_alert",
    "team_alert_expired": "whatsapp_template_team_alert_expired",
    "book_reminder": "whatsapp_template_book_reminder",
}


def fallback_for(
    key: str, values: Mapping[str, object], button_payloads: tuple[str, ...] = ()
) -> TemplateFallback | None:
    """The template to fall back to for this message, or None if the key has none.

    Safe to call for any key: most messages answer someone who has just written
    to us, so they have no template.
    """
    names = PARAMS.get(key)
    if names is None:
        return None
    return TemplateFallback(
        key=key,
        params=tuple(str(values.get(name, "")) for name in names),
        button_payloads=button_payloads,
    )


def template_name(key: str) -> str | None:
    """The approved template's name for this message key, or None if not configured."""
    setting = _SETTING.get(key)
    return (getattr(get_settings(), setting) or None) if setting else None
