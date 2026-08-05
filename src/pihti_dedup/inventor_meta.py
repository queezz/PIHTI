"""Read iProperties and the embedded preview from Inventor OLE documents.

`.ipt`, `.iam`, `.idw`, and `.ipn` files are OLE compound documents that carry
MS-OLEPS property sets. This module parses them directly, so no Inventor
installation, COM automation, or Windows-only API is required; `olefile` only
provides the compound-file container.

Two facts drive the shape of this module:

- Inventor writes its property-set streams under scrambled names, so a stream is
  identified by its FMTID and never by its stream name. Every set also repeats
  its own name in property id 255, which is used as the fallback when an FMTID is
  not in `FMT`.
- Mass, volume, density, and surface area live in Design Tracking as a cached
  snapshot. `Valid MassProps` (PID 62) says whether that snapshot still matches
  the model, so `mass_properties()` refuses to report the numbers when the flag
  is missing or zero.

Nothing here writes to a CAD file.
"""

from __future__ import annotations

import datetime
import struct
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import olefile

INVENTOR_EXTENSIONS = frozenset({".iam", ".idw", ".ipn", ".ipt"})

# FMTIDs seen in Inventor documents. The four standard OLE sets come first;
# Inventor keeps their canonical FMTID even under a scrambled stream name.
FMT = {
    # Standard OLE sets — present in some Inventor documents only.
    "F29F85E0-4FF9-1068-AB91-08002B27B3D9": "SummaryInformation (std)",
    "D5CDD502-2E9C-101B-9397-08002B2CF9AE": "DocumentSummaryInformation (std)",
    "D5CDD505-2E9C-101B-9397-08002B2CF9AE": "UserDefinedProperties (std)",
    # Inventor's own sets — these are what actually ship in .ipt/.iam/.idw.
    "3D38DE39-0588-4C14-BB37-18F4D5DD31C7": "Inventor Summary Information",
    "8CF58000-DA66-4AE6-8FF0-7B58406FB049": "Inventor Document Summary Information",
    "32853F0F-3444-11D1-9E93-0060B03C1CA6": "Design Tracking Properties",
    "9929ADB8-6407-413E-B3DC-CB9AD2F564B7": "Inventor User Defined Properties",
    "D861FB30-3136-11D1-9E92-0060B03C1CA6": "Design Tracking Control",
    "BB586990-AF3E-11D3-95A9-00A0C9B6E37A": "_Private Model Information",
    "02657684-6AD0-49EC-BBD2-9CC4E9293E60": "_PostAdaInternalDateMigration",
    "B9600981-DEE8-4547-8D7C-E525B3A1D0E1": "Inventor User Defined Properties (alt)",
}

SUMMARY_SET = ("Inventor Summary Information", "SummaryInformation (std)")
DOCUMENT_SET = ("Inventor Document Summary Information", "DocumentSummaryInformation (std)")
DESIGN_TRACKING_SET = ("Design Tracking Properties",)
USER_DEFINED_SETS = frozenset(
    {
        "Inventor User Defined Properties",
        "Inventor User Defined Properties (alt)",
        "UserDefinedProperties (std)",
    }
)

# Property-id maps. MS-OLEPS/MS-OSHARED define the standard sets; the Inventor
# SDK PropertySet documentation defines Design Tracking. The Design Tracking ids
# below were cross-checked against files in this workspace: Creation Time as a
# FILETIME at 4, Material at 20, Doc SubType Name 'Modeling' at 32, Designer at
# 41, Density at 61, and Last Updated With '2026.2 (Build ...)' at 67. Mass 58 /
# SurfaceArea 59 / Volume 60 / Density 61 were confirmed arithmetically: on every
# part carrying all three, Mass == Volume * Density exactly.
PID_SUMMARY = {
    2: "Title",
    3: "Subject",
    4: "Author",
    5: "Keywords",
    6: "Comments",
    7: "Template",
    8: "LastSavedBy",
    9: "RevisionNumber",
    10: "TotalEditingTime",
    11: "LastPrinted",
    12: "CreateTime",
    13: "LastSavedTime",
    14: "NumPages",
    15: "NumWords",
    16: "NumChars",
    17: "Thumbnail",
    18: "AppName",
    19: "Security",
}
PID_DESIGN_TRACKING = {
    4: "Creation Time",
    5: "Part Number",
    7: "Project",
    9: "Cost Center",
    10: "Checked By",
    11: "Date Checked",
    12: "Engr Approved By",
    13: "Engr Date Approved",
    17: "User Status",
    20: "Material",
    21: "Part Property Revision Id",
    23: "Catalog Web Link",
    28: "Part Icon",
    29: "Description",
    30: "Vendor",
    31: "Document SubType",
    32: "Document SubType Name",
    33: "Proxy Refresh Date",
    34: "Mfg Approved By",
    35: "Mfg Date Approved",
    36: "Cost",
    37: "Standard",
    40: "Design Status",
    41: "Designer",
    42: "Engineer",
    43: "Authority",
    48: "Manufacturer",
    49: "Standards Organization",
    50: "Language",
    52: "Size Designation",
    53: "Categories",
    55: "Stock Number",
    57: "Weld Material",
    58: "Mass",
    59: "SurfaceArea",
    60: "Volume",
    61: "Density",
    62: "Valid MassProps",
    67: "Last Updated With",
    71: "Material Identifier",
    72: "Appearance",
}

# (flattened field name, property-set names, property id)
FIELD_MAP: tuple[tuple[str, tuple[str, ...], int], ...] = (
    ("part_number", DESIGN_TRACKING_SET, 5),
    ("creation_time", DESIGN_TRACKING_SET, 4),
    ("project", DESIGN_TRACKING_SET, 7),
    ("checked_by", DESIGN_TRACKING_SET, 10),
    ("user_status", DESIGN_TRACKING_SET, 17),
    ("material", DESIGN_TRACKING_SET, 20),
    ("description", DESIGN_TRACKING_SET, 29),
    ("vendor", DESIGN_TRACKING_SET, 30),
    ("doc_subtype_name", DESIGN_TRACKING_SET, 32),
    ("cost", DESIGN_TRACKING_SET, 36),
    ("standard", DESIGN_TRACKING_SET, 37),
    ("design_status", DESIGN_TRACKING_SET, 40),
    ("designer", DESIGN_TRACKING_SET, 41),
    ("engineer", DESIGN_TRACKING_SET, 42),
    ("authority", DESIGN_TRACKING_SET, 43),
    ("manufacturer", DESIGN_TRACKING_SET, 48),
    ("stock_number", DESIGN_TRACKING_SET, 55),
    ("mass", DESIGN_TRACKING_SET, 58),
    ("surface_area", DESIGN_TRACKING_SET, 59),
    ("volume", DESIGN_TRACKING_SET, 60),
    ("density", DESIGN_TRACKING_SET, 61),
    ("valid_massprops", DESIGN_TRACKING_SET, 62),
    ("last_updated_with", DESIGN_TRACKING_SET, 67),
    ("appearance", DESIGN_TRACKING_SET, 72),
    ("title", SUMMARY_SET, 2),
    ("subject", SUMMARY_SET, 3),
    ("author", SUMMARY_SET, 4),
    ("keywords", SUMMARY_SET, 5),
    ("comments", SUMMARY_SET, 6),
    ("last_saved_by", SUMMARY_SET, 8),
    ("revision_number", SUMMARY_SET, 9),
    ("create_time", SUMMARY_SET, 12),
    ("last_saved_time", SUMMARY_SET, 13),
    ("app_name", SUMMARY_SET, 18),
    ("category", DOCUMENT_SET, 2),
    ("manager", DOCUMENT_SET, 14),
    ("company", DOCUMENT_SET, 15),
)

MASS_PROPERTY_FIELDS = ("mass", "volume", "density", "surface_area")

MEDIA_TYPES = {
    "png": "image/png",
    "bmp": "image/bmp",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
}

VT_NAMES = {
    0: "VT_EMPTY",
    1: "VT_NULL",
    2: "VT_I2",
    3: "VT_I4",
    4: "VT_R4",
    5: "VT_R8",
    6: "VT_CY",
    7: "VT_DATE",
    8: "VT_BSTR",
    10: "VT_ERROR",
    11: "VT_BOOL",
    16: "VT_I1",
    17: "VT_UI1",
    18: "VT_UI2",
    19: "VT_UI4",
    20: "VT_I8",
    21: "VT_UI8",
    22: "VT_INT",
    23: "VT_UINT",
    30: "VT_LPSTR",
    31: "VT_LPWSTR",
    64: "VT_FILETIME",
    65: "VT_BLOB",
    68: "VT_BLOB_OBJECT",
    71: "VT_CF",
    72: "VT_CLSID",
}

CODEPAGE_ALIAS = {
    932: "cp932",
    936: "gbk",
    949: "cp949",
    950: "cp950",
    1200: "utf-16-le",
    1251: "cp1251",
    1252: "cp1252",
    10000: "mac_roman",
    65001: "utf-8",
}

PROPERTY_SET_MAGIC = b"\xfe\xff\x00\x00"
SET_NAME_PID = 255


@dataclass(frozen=True)
class Preview:
    """An embedded preview image lifted straight out of the document."""

    data: bytes
    image_format: str

    @property
    def media_type(self) -> str:
        return MEDIA_TYPES.get(self.image_format, "application/octet-stream")


@dataclass(frozen=True)
class PropertySection:
    fmtid: str
    name: str
    stream: str
    codepage: int | None
    props: dict[int, object] = field(default_factory=dict)
    names: dict[int, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DocumentMeta:
    """Flattened iProperties plus the preview for one Inventor document."""

    path: str
    ok: bool
    error: str | None = None
    fields: dict[str, object] = field(default_factory=dict)
    user_defined: dict[str, object] = field(default_factory=dict)
    preview: Preview | None = None

    @property
    def part_number(self) -> str:
        value = self.fields.get("part_number")
        return str(value).strip() if isinstance(value, str) else ""

    def mass_properties(self) -> dict[str, float]:
        return mass_properties(self.fields)


def _guid(raw: bytes) -> str:
    return str(uuid.UUID(bytes_le=raw)).upper()


def _filetime(value: int) -> str | None:
    if value == 0:
        return None
    try:
        epoch = datetime.datetime(1601, 1, 1, tzinfo=datetime.timezone.utc)
        return (epoch + datetime.timedelta(microseconds=value // 10)).isoformat()
    except (OverflowError, OSError, ValueError):
        return None


def _decode_bytes(raw: bytes, codepage: int | None) -> str:
    raw = raw.split(b"\x00", 1)[0]
    preferred = CODEPAGE_ALIAS.get(codepage or 1252, "cp1252")
    for candidate in (preferred, "utf-8", "cp932", "cp1252", "latin-1"):
        try:
            return raw.decode(candidate)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("latin-1", "replace")


def _pad4(offset: int) -> int:
    return offset + ((4 - (offset % 4)) % 4)


def _read_scalar(buf: bytes, p: int, vt: int, codepage: int | None) -> tuple[object, int]:
    if vt in (0, 1):
        return None, p
    if vt == 2:
        return struct.unpack_from("<h", buf, p)[0], p + 4
    if vt in (3, 10, 22):
        return struct.unpack_from("<i", buf, p)[0], p + 4
    if vt in (17, 18, 19, 23):
        return struct.unpack_from("<I", buf, p)[0], p + 4
    if vt == 4:
        return struct.unpack_from("<f", buf, p)[0], p + 4
    if vt in (5, 7):
        return struct.unpack_from("<d", buf, p)[0], p + 8
    if vt in (6, 20, 21):
        return struct.unpack_from("<q", buf, p)[0], p + 8
    if vt == 11:
        return bool(struct.unpack_from("<h", buf, p)[0]), p + 4
    if vt == 64:
        return _filetime(struct.unpack_from("<Q", buf, p)[0]), p + 8
    if vt == 30:  # VT_LPSTR — length in bytes
        length = struct.unpack_from("<I", buf, p)[0]
        return _decode_bytes(buf[p + 4 : p + 4 + length], codepage), _pad4(p + 4 + length)
    if vt == 31:  # VT_LPWSTR — length in UTF-16 code units
        length = struct.unpack_from("<I", buf, p)[0]
        raw = buf[p + 4 : p + 4 + length * 2]
        text = raw.decode("utf-16-le", "replace").split("\x00", 1)[0]
        return text, _pad4(p + 4 + length * 2)
    if vt == 8:  # VT_BSTR — length in bytes
        length = struct.unpack_from("<I", buf, p)[0]
        return _decode_bytes(buf[p + 4 : p + 4 + length], codepage), _pad4(p + 4 + length)
    if vt in (65, 68, 71):  # VT_BLOB, VT_BLOB_OBJECT, VT_CF — the preview lives here
        length = struct.unpack_from("<I", buf, p)[0]
        return buf[p + 4 : p + 4 + length], _pad4(p + 4 + length)
    if vt == 72:
        return _guid(buf[p : p + 16]), p + 16
    return None, p + 4


def _read_value(buf: bytes, offset: int, codepage: int | None) -> object:
    vt = struct.unpack_from("<I", buf, offset)[0]
    base = vt & 0x0FFF
    p = offset + 4
    if vt & 0x1000:  # vector
        count = struct.unpack_from("<I", buf, p)[0]
        p += 4
        values = []
        for _ in range(min(count, 4096)):
            value, p = _read_scalar(buf, p, base, codepage)
            values.append(value)
        return values
    value, _ = _read_scalar(buf, p, base, codepage)
    return value


def _read_dictionary(section: bytes, offset: int, codepage: int | None) -> dict[int, str]:
    count = struct.unpack_from("<I", section, offset)[0]
    p = offset + 4
    names: dict[int, str] = {}
    for _ in range(min(count, 4096)):
        pid, length = struct.unpack_from("<II", section, p)
        p += 8
        if codepage == 1200:
            names[pid] = section[p : p + length * 2].decode("utf-16-le", "replace").split("\x00")[0]
            p = _pad4(p + length * 2)
        else:
            names[pid] = _decode_bytes(section[p : p + length], codepage)
            p += length
    return names


def parse_property_set(data: bytes, *, stream: str = "") -> list[PropertySection]:
    """Parse one MS-OLEPS property-set stream into its sections."""

    if data[:2] != b"\xfe\xff":
        raise ValueError("not a property set (bad byte-order mark)")
    section_count = struct.unpack_from("<I", data, 24)[0]
    headers = []
    offset = 28
    for _ in range(section_count):
        fmtid = _guid(data[offset : offset + 16])
        headers.append((fmtid, struct.unpack_from("<I", data, offset + 16)[0]))
        offset += 20

    sections: list[PropertySection] = []
    for fmtid, section_offset in headers:
        body = data[section_offset:]
        if len(body) < 8:
            continue
        _length, property_count = struct.unpack_from("<II", body, 0)
        index = [struct.unpack_from("<II", body, 8 + 8 * i) for i in range(property_count)]

        codepage = None
        for pid, value_offset in index:
            if pid == 1:
                try:
                    codepage = _read_value(body, value_offset, None)
                except (struct.error, ValueError, IndexError):
                    codepage = None
                if isinstance(codepage, int) and codepage < 0:
                    codepage += 65536

        props: dict[int, object] = {}
        names: dict[int, str] = {}
        for pid, value_offset in index:
            if pid == 0:  # user-defined property name dictionary
                try:
                    names = _read_dictionary(body, value_offset, codepage)
                except (struct.error, ValueError, IndexError, UnicodeDecodeError):
                    names = {}
                continue
            try:
                props[pid] = _read_value(body, value_offset, codepage)
            except (struct.error, ValueError, IndexError, UnicodeDecodeError):
                continue

        # The set repeats its own name in PID 255, which is the authoritative
        # fallback when the FMTID is one this table has never seen.
        self_name = props.get(SET_NAME_PID)
        fallback = self_name if isinstance(self_name, str) else None
        friendly = FMT.get(fmtid) or fallback or "UNKNOWN"
        sections.append(
            PropertySection(
                fmtid=fmtid,
                name=friendly,
                stream=stream,
                codepage=codepage if isinstance(codepage, int) else None,
                props=props,
                names=names,
            )
        )
    return sections


def _dib_to_bmp(dib: bytes) -> bytes:
    """Prepend a BITMAPFILEHEADER so a raw DIB becomes a loadable .bmp."""

    header_size = struct.unpack_from("<I", dib, 0)[0]
    bpp = struct.unpack_from("<H", dib, 14)[0] if header_size >= 40 else 24
    compression = struct.unpack_from("<I", dib, 16)[0] if header_size >= 40 else 0
    colors_used = struct.unpack_from("<I", dib, 32)[0] if header_size >= 40 else 0
    if bpp <= 8 and colors_used == 0:
        colors_used = 1 << bpp
    masks = 12 if compression == 3 else 0
    pixel_offset = 14 + header_size + masks + colors_used * 4
    return b"BM" + struct.pack("<IHHI", 14 + len(dib), 0, 0, pixel_offset) + dib


def _find_image(blob: bytes) -> tuple[str | None, int]:
    """Locate the real image payload inside a VT_CF / VT_BLOB wrapper.

    Inventor wraps the preview in a clipboard-format header
    (`FF FF FF FF | kind | width | height | image bytes`), so the payload starts
    16 bytes in. Rather than hard-code that offset, scan the first 64 bytes for a
    known image magic; that survives Inventor version changes. Older documents
    store a headerless DIB instead, hence the second pass.
    """

    for magic, image_format in (
        (b"\x89PNG\r\n\x1a\n", "png"),
        (b"\xff\xd8\xff", "jpeg"),
        (b"GIF89a", "gif"),
        (b"BM", "bmp"),
    ):
        found = blob.find(magic, 0, 64)
        if found != -1:
            return image_format, found
    for offset in (0, 4, 8, 12, 16, 20):
        if len(blob) > offset + 40:
            header_size = struct.unpack_from("<I", blob, offset)[0]
            if header_size in (12, 40, 52, 56, 108, 124):
                width = struct.unpack_from("<i", blob, offset + 4)[0]
                if 0 < width <= 4096:
                    return "dib", offset
    return None, 0


def extract_preview(sections: list[PropertySection]) -> Preview | None:
    """Return the largest embedded preview image across all property sections."""

    best: Preview | None = None
    for section in sections:
        for value in section.props.values():
            if not isinstance(value, (bytes, bytearray)) or len(value) < 64:
                continue
            blob = bytes(value)
            image_format, offset = _find_image(blob)
            if image_format is None:
                continue
            body = blob[offset:]
            if image_format == "dib":
                try:
                    candidate = Preview(data=_dib_to_bmp(body), image_format="bmp")
                except (struct.error, IndexError):
                    continue
            else:
                candidate = Preview(data=body, image_format=image_format)
            if best is None or len(candidate.data) > len(best.data):
                best = candidate
    return best


def _flatten_fields(sections: list[PropertySection]) -> dict[str, object]:
    by_name: dict[str, list[PropertySection]] = {}
    for section in sections:
        by_name.setdefault(section.name, []).append(section)
    fields: dict[str, object] = {}
    for name, set_names, pid in FIELD_MAP:
        for set_name in set_names:
            for section in by_name.get(set_name, ()):
                value = section.props.get(pid)
                if isinstance(value, str):
                    value = value.strip()
                if isinstance(value, (bytes, bytearray)):
                    continue
                if value not in (None, "", []) and name not in fields:
                    fields[name] = value
    return fields


def _user_defined(sections: list[PropertySection]) -> dict[str, object]:
    """Named iProperties the owner added by hand, from the section dictionary."""

    values: dict[str, object] = {}
    for section in sections:
        if section.name not in USER_DEFINED_SETS or not section.names:
            continue
        for pid, label in section.names.items():
            # 0 dictionary, 1 codepage, 255 set name, 0x80000000 locale.
            if pid in (0, 1, SET_NAME_PID) or pid >= 0x80000000:
                continue
            if label.startswith("{") and label.endswith("}"):
                continue
            value = section.props.get(pid)
            if isinstance(value, (bytes, bytearray)) or value in (None, ""):
                continue
            values[label] = value
    return values


def read_sections(path: Path | str) -> list[PropertySection]:
    """Parse every property-set stream in an OLE compound document."""

    target = str(path)
    if not olefile.isOleFile(target):
        raise ValueError("not an OLE compound document")
    sections: list[PropertySection] = []
    ole = olefile.OleFileIO(target)
    try:
        for entry in ole.listdir(streams=True, storages=False):
            if len(entry) != 1:
                continue
            name = entry[0]
            try:
                data = ole.openstream(name).read()
            except OSError:
                continue
            if data[:4] != PROPERTY_SET_MAGIC:
                continue
            try:
                sections.extend(parse_property_set(data, stream=name))
            except (ValueError, struct.error, IndexError):
                continue
    finally:
        ole.close()
    return sections


def read_document(path: Path | str) -> DocumentMeta:
    """Read iProperties and the preview from one Inventor document."""

    display = str(path)
    try:
        sections = read_sections(path)
    except ValueError as exc:
        return DocumentMeta(path=display, ok=False, error=str(exc))
    except (OSError, struct.error) as exc:
        return DocumentMeta(path=display, ok=False, error=f"{type(exc).__name__}: {exc}")
    return DocumentMeta(
        path=display,
        ok=True,
        fields=_flatten_fields(sections),
        user_defined=_user_defined(sections),
        preview=extract_preview(sections),
    )


def read_preview(path: Path | str) -> Preview | None:
    """Return only the embedded preview image, or None when there is none."""

    try:
        return extract_preview(read_sections(path))
    except (ValueError, OSError, struct.error):
        return None


def mass_properties(fields: dict[str, object]) -> dict[str, float]:
    """Return cached mass properties only when Inventor marked them valid.

    `Valid MassProps` (PID 62) is a bitmask that Inventor clears when the model
    changes without a mass-property update. This workspace only ever shows 1, 17,
    or 31, so the individual bits stay undocumented; a missing or zero flag is
    treated as "do not trust these numbers" and the caller gets nothing back.
    Values are also frequently absent even under a valid flag, so presence is
    checked per field.
    """

    flag = fields.get("valid_massprops")
    if not isinstance(flag, (int, float)) or isinstance(flag, bool) or not flag:
        return {}
    values: dict[str, float] = {}
    for name in MASS_PROPERTY_FIELDS:
        value = fields.get(name)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values[name] = float(value)
    return values
