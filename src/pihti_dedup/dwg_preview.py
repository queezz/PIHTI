"""Extract the preview image AutoCAD embeds in a DWG file.

A DWG stores an optional preview in an "image data" section marked by a 16-byte
sentinel. The section holds a small record table pointing at a BMP (headerless —
the 14-byte `BITMAPFILEHEADER` has to be synthesized), a WMF, or on newer
versions a PNG. Reading it needs no external library, which is why DWG previews
are in-house here while STEP needs an optional extra.

The embedded previews in this workspace are 180×180 paper-space sheets, so they
are grid-quality only: `render_preview` caps the upscale at 2.5× and centres the
result on a card rather than blowing a tiny source up into mush.

`extract_preview` deliberately imports nothing optional, so the container format
can be exercised without Pillow. `render_preview` needs Pillow and imports it at
call time.

Nothing here writes to a CAD file.
"""

from __future__ import annotations

import struct
from io import BytesIO
from pathlib import Path

SENTINEL_START = bytes.fromhex("1F256D07D43628289D57CA3F9D44102B")
SENTINEL_END = bytes.fromhex("E0DA96F8D7D3BF8762A835C062BBEFD4")

CODE_HEADER = 1
CODE_BMP = 2
CODE_WMF = 3
CODE_PNG = 6

#: Below this mean luminance the preview is genuine light-on-dark line art.
DARK_MEAN = 100
#: A 180 px source blown past this looks worse than a smaller, crisp image.
MAX_UPSCALE = 2.5


def dwg_version(buf: bytes) -> str:
    return buf[:6].decode("ascii", "replace")


def _find_section(buf: bytes) -> int | None:
    """Locate the image-data section, preferring the header pointer."""

    # Bytes 0x0D..0x11 hold the absolute offset of the preview sentinel.
    if len(buf) > 0x11:
        (pointer,) = struct.unpack_from("<I", buf, 0x0D)
        if 0 < pointer < len(buf) - 16 and buf[pointer : pointer + 16] == SENTINEL_START:
            return pointer + 16
    index = buf.find(SENTINEL_START)
    return index + 16 if index >= 0 else None


def _bmp_with_file_header(payload: bytes) -> bytes:
    """Re-attach the `BITMAPFILEHEADER` that DWG strips from a stored BMP."""

    if len(payload) < 40:
        raise ValueError("BMP payload too short")
    (header_size,) = struct.unpack_from("<I", payload, 0)
    (bit_count,) = struct.unpack_from("<H", payload, 14)
    (colors_used,) = struct.unpack_from("<I", payload, 32)
    (compression,) = struct.unpack_from("<I", payload, 16)

    palette = (colors_used or (1 << bit_count)) if bit_count <= 8 else 0
    masks = 12 if compression == 3 else 0  # BI_BITFIELDS adds three colour masks
    offset = 14 + header_size + masks + palette * 4
    return b"BM" + struct.pack("<IHHI", 14 + len(payload), 0, 0, offset) + payload


def extract_preview(path: Path | str) -> tuple[str, bytes] | None:
    """Return `(kind, image_bytes)`, or None when the DWG carries no preview."""

    buf = Path(path).read_bytes()
    position = _find_section(buf)
    if position is None:
        return None

    try:
        # An overall size (RL) then the record count (RC), then 9 bytes each.
        struct.unpack_from("<I", buf, position)
        count = buf[position + 4]
        records = []
        cursor = position + 5
        for _ in range(count):
            code = buf[cursor]
            start, size = struct.unpack_from("<II", buf, cursor + 1)
            records.append((code, start, size))
            cursor += 9
    except (struct.error, IndexError):
        return None

    for code, start, size in records:
        if code not in (CODE_BMP, CODE_WMF, CODE_PNG):
            continue
        if size <= 0 or start <= 0 or start + size > len(buf):
            continue
        payload = buf[start : start + size]
        if code == CODE_BMP:
            try:
                return "bmp", _bmp_with_file_header(payload)
            except (ValueError, struct.error):
                continue
        if code == CODE_PNG:
            return "png", payload
        if code == CODE_WMF:
            return "wmf", payload
    return None


def _trim_border(image, tolerance: int = 6):
    """Crop a uniform border matching the corner colour."""

    from PIL import Image, ImageChops

    backdrop = Image.new("RGB", image.size, image.getpixel((0, 0)))
    difference = ImageChops.difference(image, backdrop).convert("L")
    box = difference.point(lambda value: 255 if value > tolerance else 0).getbbox()
    if not box:
        return image
    x0, y0, x1, y1 = box
    pad = 2  # keep a small margin so strokes are not clipped
    return image.crop(
        (max(x0 - pad, 0), max(y0 - pad, 0), min(x1 + pad, image.width), min(y1 + pad, image.height))
    )


def render_preview(
    path: Path | str,
    size: int = 512,
    background: tuple = (255, 255, 255),
    normalize_dark: bool = True,
    max_upscale: float = MAX_UPSCALE,
):
    """Extract the DWG preview and normalize it to a square PIL RGBA image.

    Returns `(image, kind)`; `image` is None when there is no preview or the
    stored kind is WMF, which Pillow cannot decode without a Windows backend.

    Inversion keys on the image's mean luminance, never on the corner pixel: a
    paper-space preview is a white sheet on a dark backdrop, and keying off the
    corner would invert that sheet to solid black.
    """

    from PIL import Image, ImageOps

    found = extract_preview(path)
    if found is None:
        return None, None
    kind, data = found
    if kind == "wmf":
        return None, kind

    image = Image.open(BytesIO(data))
    image.load()
    image = image.convert("RGB")

    if normalize_dark:
        grey = image.convert("L")
        mean = sum(value * count for value, count in enumerate(grey.histogram())) / (
            grey.width * grey.height
        )
        if mean < DARK_MEAN:
            image = ImageOps.invert(image)

    image = _trim_border(image)

    factor = min(size / max(image.width, image.height), max_upscale)
    target = (max(1, round(image.width * factor)), max(1, round(image.height * factor)))
    image = image.resize(target, Image.LANCZOS if factor < 1 else Image.BICUBIC)

    canvas = Image.new("RGBA", (size, size), tuple(background) + (255,))
    canvas.paste(image, ((size - image.width) // 2, (size - image.height) // 2))
    return canvas, kind
