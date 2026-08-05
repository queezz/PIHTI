"""
dwgpreview -- extract the embedded preview image from a DWG file.

The DWG format stores an optional preview in an "image data" section marked
by a 16-byte sentinel. The section holds a small record table pointing at a
BMP (headerless -- the 14-byte BITMAPFILEHEADER must be synthesized), a WMF,
or on newer versions a PNG. No external library needed.
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


def dwg_version(buf: bytes) -> str:
    return buf[:6].decode("ascii", "replace")


def _find_section(buf: bytes) -> int | None:
    """Locate the image-data section, preferring the header pointer."""
    # bytes 0x0D..0x11 hold the absolute offset of the preview sentinel
    if len(buf) > 0x11:
        (ptr,) = struct.unpack_from("<I", buf, 0x0D)
        if 0 < ptr < len(buf) - 16 and buf[ptr : ptr + 16] == SENTINEL_START:
            return ptr + 16
    # fall back to scanning
    idx = buf.find(SENTINEL_START)
    return idx + 16 if idx >= 0 else None


def _bmp_with_file_header(payload: bytes) -> bytes:
    """Re-attach the BITMAPFILEHEADER that DWG strips from stored BMPs."""
    if len(payload) < 40:
        raise ValueError("BMP payload too short")
    hdr_size, = struct.unpack_from("<I", payload, 0)
    bit_count, = struct.unpack_from("<H", payload, 14)
    clr_used, = struct.unpack_from("<I", payload, 32)

    if bit_count <= 8:
        palette = clr_used if clr_used else (1 << bit_count)
    else:
        palette = 0
    # BI_BITFIELDS (compression == 3) adds three 4-byte colour masks
    compression, = struct.unpack_from("<I", payload, 16)
    masks = 12 if compression == 3 else 0

    offset = 14 + hdr_size + masks + palette * 4
    size = 14 + len(payload)
    return b"BM" + struct.pack("<IHHI", size, 0, 0, offset) + payload


def extract_preview(path) -> tuple[str, bytes] | None:
    """Return (kind, image_bytes) or None when the DWG carries no preview."""
    buf = Path(path).read_bytes()
    pos = _find_section(buf)
    if pos is None:
        return None

    try:
        # overall size (RL) then the record count (RC)
        (_overall,) = struct.unpack_from("<I", buf, pos)
        count = buf[pos + 4]
        recs = []
        p = pos + 5
        for _ in range(count):
            code = buf[p]
            start, size = struct.unpack_from("<II", buf, p + 1)
            recs.append((code, start, size))
            p += 9
    except (struct.error, IndexError):
        return None

    for code, start, size in recs:
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


def _trim_border(img, tol=6):
    """Crop a uniform border matching the corner colour."""
    from PIL import Image, ImageChops

    bg = Image.new("RGB", img.size, img.getpixel((0, 0)))
    diff = ImageChops.difference(img, bg).convert("L")
    box = diff.point(lambda v: 255 if v > tol else 0).getbbox()
    if not box:
        return img
    # keep a small margin so strokes are not clipped
    x0, y0, x1, y1 = box
    pad = 2
    return img.crop(
        (
            max(x0 - pad, 0),
            max(y0 - pad, 0),
            min(x1 + pad, img.width),
            min(y1 + pad, img.height),
        )
    )


def render_preview(
    path, size=512, background=(255, 255, 255), normalize_dark=True, max_upscale=2.5
):
    """Extract the DWG preview and normalize it to a square PIL RGBA image.

    Embedded DWG previews are small (180x180 here) and their backdrop follows
    whatever the drawing's model/paper space colour was, so they range from
    near-black to pale blue. To sit consistently beside the mesh renders the
    border is trimmed, dark backdrops are inverted to dark-on-light line art,
    and upscaling is capped so a 180px source is not blown up into mush.
    """
    from PIL import Image, ImageOps

    found = extract_preview(path)
    if found is None:
        return None, None
    kind, data = found
    if kind == "wmf":
        return None, kind  # Pillow cannot decode WMF without a Windows backend

    img = Image.open(BytesIO(data))
    img.load()
    img = img.convert("RGB")

    # Invert only when the image as a whole is dark, i.e. genuine light-on-dark
    # model-space line art. Keying off the corner pixel alone is wrong: a
    # paper-space preview is a white sheet on a dark backdrop, and inverting
    # that turns the sheet solid black.
    if normalize_dark:
        stat = img.convert("L")
        mean = sum(i * c for i, c in enumerate(stat.histogram())) / (
            stat.width * stat.height
        )
        if mean < 100:
            img = ImageOps.invert(img)

    img = _trim_border(img)

    # never upscale a tiny source more than max_upscale; softness looks worse
    # than a smaller, crisp image centred on the card
    fit = size / max(img.width, img.height)
    factor = min(fit, max_upscale)
    target = (max(1, round(img.width * factor)), max(1, round(img.height * factor)))
    resample = Image.LANCZOS if factor < 1 else Image.BICUBIC
    img = img.resize(target, resample)

    canvas = Image.new("RGBA", (size, size), tuple(background) + (255,))
    canvas.paste(img, ((size - img.width) // 2, (size - img.height) // 2))
    return canvas, kind
