"""Shrink a photo before sending it to the vision model.

Phone photos are often several megabytes. A smaller JPEG is quicker to send,
cheaper to read, and stays well under the API's image size limit, with no
loss that matters for triage.
"""

import io

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_SIDE = 1568


class UnreadableImage(ValueError):
    pass


def prepare_for_vision(data: bytes) -> tuple[bytes, str]:
    """Return (jpeg_bytes, "image/jpeg"), at most MAX_SIDE pixels on the long side."""
    try:
        image = Image.open(io.BytesIO(data))
        image = ImageOps.exif_transpose(image)  # respect the phone's rotation
        image = image.convert("RGB")
    except (UnidentifiedImageError, OSError) as error:
        raise UnreadableImage("The photo could not be opened") from error
    image.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=85)
    return out.getvalue(), "image/jpeg"
