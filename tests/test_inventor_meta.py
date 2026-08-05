import struct
import uuid
from pathlib import Path

from pihti_dedup.inventor_meta import (
    extract_preview,
    mass_properties,
    parse_property_set,
    read_document,
    read_preview,
)

DESIGN_TRACKING = "32853F0F-3444-11D1-9E93-0060B03C1CA6"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def lpwstr(value: str) -> bytes:
    payload = (value + "\0").encode("utf-16-le")
    return struct.pack("<II", 31, len(value) + 1) + payload


def i4(value: int) -> bytes:
    return struct.pack("<Ii", 3, value)


def r8(value: float) -> bytes:
    return struct.pack("<Id", 5, value)


def clipboard_blob(payload: bytes) -> bytes:
    """VT_CF wrapped the way Inventor writes a preview: 16 bytes, then the image."""

    wrapper = b"\xff\xff\xff\xff" + struct.pack("<III", 3, 4, 4) + payload
    return struct.pack("<II", 71, len(wrapper)) + wrapper


def section(properties: list[tuple[int, bytes]]) -> bytes:
    index = b""
    body = b""
    start = 8 + 8 * len(properties)
    for pid, value in properties:
        index += struct.pack("<II", pid, start + len(body))
        padded = value + b"\0" * ((4 - len(value) % 4) % 4)
        body += padded
    return struct.pack("<II", start + len(body), len(properties)) + index + body


def property_set(sections: list[tuple[str, bytes]]) -> bytes:
    header = struct.pack("<HHI", 0xFFFE, 0, 2) + b"\0" * 16 + struct.pack("<I", len(sections))
    offset = 28 + 20 * len(sections)
    directory = b""
    body = b""
    for fmtid, payload in sections:
        directory += uuid.UUID(fmtid).bytes_le + struct.pack("<I", offset + len(body))
        body += payload
    return header + directory + body


def test_design_tracking_is_matched_by_fmtid_under_a_scrambled_stream_name() -> None:
    blob = property_set(
        [
            (
                DESIGN_TRACKING,
                section(
                    [
                        (1, i4(1200)),
                        (5, lpwstr("B_probe_bearing")),
                        (20, lpwstr("PAEK 樹脂")),
                        (29, lpwstr("Probe bearing")),
                        (41, lpwstr("zetsu")),
                        (58, r8(6.6)),
                        (60, r8(5.0)),
                        (61, r8(1.32)),
                        (62, i4(17)),
                    ]
                ),
            )
        ]
    )

    sections = parse_property_set(blob, stream="\x05Qsm4Vw0dTdU")

    assert len(sections) == 1
    assert sections[0].name == "Design Tracking Properties"
    assert sections[0].props[5] == "B_probe_bearing"
    assert sections[0].props[20] == "PAEK 樹脂"
    assert sections[0].props[41] == "zetsu"
    fields = {"valid_massprops": 17, "mass": 6.6, "volume": 5.0, "density": 1.32}
    assert mass_properties(fields) == {"mass": 6.6, "volume": 5.0, "density": 1.32}


def test_unknown_fmtid_falls_back_to_the_set_name_in_property_255() -> None:
    blob = property_set(
        [
            (
                "11111111-2222-3333-4444-555555555555",
                section([(255, lpwstr("Design Tracking Properties")), (5, lpwstr("UFC-152"))]),
            )
        ]
    )

    sections = parse_property_set(blob)

    assert sections[0].name == "Design Tracking Properties"
    assert sections[0].props[5] == "UFC-152"


def test_mass_properties_need_the_valid_flag_and_the_value() -> None:
    assert mass_properties({"mass": 6.6, "volume": 5.0}) == {}
    assert mass_properties({"valid_massprops": 0, "mass": 6.6}) == {}
    assert mass_properties({"valid_massprops": 17}) == {}
    assert mass_properties({"valid_massprops": 17, "density": 8.0}) == {"density": 8.0}


def test_preview_is_lifted_out_of_the_clipboard_wrapper() -> None:
    image = PNG_MAGIC + b"synthetic preview payload" * 4
    blob = property_set([(DESIGN_TRACKING, section([(1, i4(1200)), (17, clipboard_blob(image))]))])

    preview = extract_preview(parse_property_set(blob))

    assert preview is not None
    assert preview.image_format == "png"
    assert preview.media_type == "image/png"
    assert preview.data == image


def test_headerless_dib_preview_becomes_a_loadable_bitmap() -> None:
    dib = struct.pack("<IiiHHIIiiII", 40, 4, 4, 1, 24, 0, 48, 2835, 2835, 0, 0) + b"\x10" * 48
    blob = property_set([(DESIGN_TRACKING, section([(17, clipboard_blob(dib))]))])

    preview = extract_preview(parse_property_set(blob))

    assert preview is not None
    assert preview.image_format == "bmp"
    assert preview.media_type == "image/bmp"
    assert preview.data.startswith(b"BM")
    assert preview.data.endswith(dib)


def test_a_file_that_is_not_an_ole_document_reports_instead_of_raising(tmp_path: Path) -> None:
    broken = tmp_path / "imported.ipt"
    broken.write_bytes(b"STEP import, not a compound document")

    document = read_document(broken)

    assert document.ok is False
    assert document.error == "not an OLE compound document"
    assert document.fields == {}
    assert document.preview is None
    assert document.mass_properties() == {}
    assert read_preview(broken) is None
