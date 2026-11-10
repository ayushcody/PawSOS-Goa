"""Where incoming photos are kept.

Every channel saves photos here, so the rest of the app only ever sees a file
name. Names are random, so one cannot be guessed from another.
"""

import re
import uuid
from pathlib import Path

from app.config import get_settings

MAX_BYTES = 10 * 1024 * 1024

# mime type -> (file extension, how a real file of that type begins)
_TYPES: dict[str, tuple[str, bytes]] = {
    "image/jpeg": (".jpg", b"\xff\xd8\xff"),
    "image/png": (".png", b"\x89PNG\r\n\x1a\n"),
    "image/webp": (".webp", b"RIFF"),
}
_NAME = re.compile(r"^[0-9a-f]{32}\.(jpg|png|webp)$")


class MediaError(ValueError):
    """The upload is not a photo we accept."""


def _dir() -> Path:
    path = Path(get_settings().media_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_image(data: bytes, mime: str) -> str:
    """Save a photo and return its file name."""
    if mime not in _TYPES:
        raise MediaError("Only JPEG, PNG or WebP photos are accepted.")
    if len(data) > MAX_BYTES:
        raise MediaError("That photo is larger than 10 MB.")
    extension, signature = _TYPES[mime]
    if not data.startswith(signature):
        raise MediaError("That file does not look like a photo.")
    name = uuid.uuid4().hex + extension
    (_dir() / name).write_bytes(data)
    return name


def path_for(name: str) -> Path | None:
    """The file for a saved photo, or None. Rejects anything that is not one of our names."""
    if not _NAME.match(name):
        return None
    path = _dir() / name
    return path if path.is_file() else None
