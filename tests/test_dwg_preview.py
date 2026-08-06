"""The DWG embedded-preview container, on synthetic DWG buffers.

No DWG from the workspace is committed as a fixture; every buffer here is
assembled to the shape `dwg_preview` reads: a sentinel, a record table, and one
payload.
"""

import struct
from io import BytesIO
from pathlib import Path

import pytest

from pihti_dedup import dwg_preview
from pihti_dedup.dwg_preview import CODE_BMP, CODE_HEADER, CODE_PNG, CODE_WMF, SENTINEL_START

SENTINEL_AT = 64
TABLE_AT = SENTINEL_AT + 16
PAYLOAD_AT = TABLE_AT + 5 + 2 * 9


def make_dwg(code: int, payload: bytes, *, pointer: int | None = None) -> bytes:
    """A minimal DWG-shaped buffer carrying one preview record."""

    buffer = bytearray(b"AC1032".ljust(SENTINEL_AT, b"\0"))
    struct.pack_into("<I", buffer, 0x0D, SENTINEL_AT if pointer is None else pointer)
    buffer += SENTINEL_START
    buffer += struct.pack("<I", len(payload) + 23)  # overall size
    buffer += bytes([2])  # record count
    buffer += bytes([CODE_HEADER]) + struct.pack("<II", 0, 0)
    buffer += bytes([code]) + struct.pack("<II", PAYLOAD_AT, len(payload))
    assert len(buffer) == PAYLOAD_AT
    return bytes(buffer + payload)


def png_bytes(color=(180, 180, 180), size=(180, 180)) -> bytes:
    Image = pytest.importorskip("PIL.Image")
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def headerless_bmp(color=(180, 180, 180), size=(180, 180)) -> bytes:
    """A BMP with its 14-byte BITMAPFILEHEADER stripped, as DWG stores it."""

    Image = pytest.importorskip("PIL.Image")
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format="BMP")
    return buffer.getvalue()[14:]


def test_a_png_record_is_returned_verbatim(tmp_path: Path) -> None:
    payload = png_bytes()
    path = tmp_path / "sheet.dwg"
    path.write_bytes(make_dwg(CODE_PNG, payload))

    assert dwg_preview.extract_preview(path) == ("png", payload)
    assert dwg_preview.dwg_version(path.read_bytes()) == "AC1032"


def test_a_bmp_record_gets_its_stripped_file_header_back(tmp_path: Path) -> None:
    Image = pytest.importorskip("PIL.Image")
    path = tmp_path / "sheet.dwg"
    path.write_bytes(make_dwg(CODE_BMP, headerless_bmp()))

    kind, data = dwg_preview.extract_preview(path)

    assert kind == "bmp"
    assert data[:2] == b"BM"
    assert Image.open(BytesIO(data)).size == (180, 180)  # the reattached header parses


def test_the_sentinel_is_found_by_scan_when_the_header_pointer_lies(tmp_path: Path) -> None:
    payload = png_bytes()
    path = tmp_path / "sheet.dwg"
    path.write_bytes(make_dwg(CODE_PNG, payload, pointer=0xDEAD))

    assert dwg_preview.extract_preview(path) == ("png", payload)


def test_a_dwg_without_a_preview_section_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "bare.dwg"
    path.write_bytes(b"AC1032".ljust(512, b"\0"))

    assert dwg_preview.extract_preview(path) is None
    assert dwg_preview.render_preview(path) == (None, None)


def test_a_truncated_record_table_returns_none_rather_than_raising(tmp_path: Path) -> None:
    path = tmp_path / "cut.dwg"
    body = bytearray(b"AC1032".ljust(SENTINEL_AT, b"\0"))
    struct.pack_into("<I", body, 0x0D, SENTINEL_AT)
    path.write_bytes(bytes(body + SENTINEL_START + struct.pack("<I", 99) + bytes([4])))

    assert dwg_preview.extract_preview(path) is None


def test_a_record_pointing_outside_the_file_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "bad.dwg"
    buffer = bytearray(make_dwg(CODE_PNG, png_bytes()))
    struct.pack_into("<II", buffer, TABLE_AT + 5 + 9 + 1, PAYLOAD_AT, 10_000_000)
    path.write_bytes(bytes(buffer))

    assert dwg_preview.extract_preview(path) is None


def test_a_wmf_preview_is_recognised_but_not_rendered(tmp_path: Path) -> None:
    path = tmp_path / "old.dwg"
    path.write_bytes(make_dwg(CODE_WMF, b"\xd7\xcd\xc6\x9a" + b"\0" * 60))

    assert dwg_preview.extract_preview(path)[0] == "wmf"
    # Pillow cannot decode WMF without a Windows backend, so the caller gets a
    # placeholder rather than a broken image.
    assert dwg_preview.render_preview(path) == (None, "wmf")


def test_dark_line_art_is_inverted_but_a_light_sheet_is_left_alone(tmp_path: Path) -> None:
    pytest.importorskip("PIL")
    dark = tmp_path / "model.dwg"
    light = tmp_path / "paper.dwg"
    dark.write_bytes(make_dwg(CODE_PNG, png_bytes(color=(18, 18, 22))))
    light.write_bytes(make_dwg(CODE_PNG, png_bytes(color=(238, 238, 238))))

    dark_image, dark_kind = dwg_preview.render_preview(dark, size=256)
    light_image, _ = dwg_preview.render_preview(light, size=256)

    assert dark_kind == "png"
    assert dark_image.size == (256, 256)
    # Inversion keys on mean luminance, so the dark backdrop comes back light...
    assert dark_image.convert("L").getpixel((128, 128)) > 200
    # ...and a pale paper-space sheet is not turned into a black rectangle.
    assert light_image.convert("L").getpixel((128, 128)) > 200


def test_a_small_source_is_capped_at_the_upscale_limit_and_centred(tmp_path: Path) -> None:
    pytest.importorskip("PIL")
    path = tmp_path / "small.dwg"
    path.write_bytes(make_dwg(CODE_PNG, png_bytes(color=(140, 140, 150), size=(40, 40))))

    image, _ = dwg_preview.render_preview(path, size=512, background=(255, 255, 255))

    assert image.size == (512, 512)
    # 40 px capped at 2.5x is ~100 px on a 512 card, so the corners stay backdrop.
    assert image.convert("RGB").getpixel((4, 4)) == (255, 255, 255)
    assert image.convert("RGB").getpixel((256, 256)) != (255, 255, 255)
