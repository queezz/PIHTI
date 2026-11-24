"""Thin the vector stroke widths of an Inventor PDF export on chosen pages.

Inventor's PDF translator draws a JIS drawing with six fixed line widths, and
at A4 the heavier ones blot small holes and crowd centerlines. This module
rewrites only those width operators, on only the pages asked for, and refuses
anything it does not recognise instead of guessing:

- only classic cross-reference tables (what Inventor writes), no incremental
  updates and no cross-reference streams;
- only standalone width operators at the start of a content-stream line, and
  only widths in the mapping; every width operator on a target page must match;
- inline images and shared page content streams are always refused. Pages
  with separate image XObjects can be processed when explicitly requested.

Text, page boxes, fonts and every untouched page are copied byte for byte.
The output is written only after every check passed.
"""

from __future__ import annotations

import re
import zlib
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

# Inventor's exported widths (pt) mapped to the thinner set verified on the
# bellows shop set at A4 (.agents/log/2026-11-16-bellows-centerlines-and-pdf-weights.md).
DEFAULT_MAPPING: dict[float, float] = {
    0.36: 0.36,
    0.54: 0.39,
    0.72: 0.48,
    1.08: 0.63,
    1.44: 0.88,
    1.98: 1.16,
    3.42: 1.55,
}

_LINE_WIDTH = re.compile(rb"(?m)^(\d*\.?\d+) w(?=\s)")
_ANY_WIDTH = re.compile(rb"(?<![\w.])(\d*\.?\d+)\s+w\b")
_INLINE_IMAGE = re.compile(rb"(?<!\S)BI(?!\S)")
_REF = re.compile(rb"(\d+)\s+0\s+R")


class PdfStrokeError(ValueError):
    """The PDF is outside what the bounded rewrite accepts; nothing was written."""


@dataclass
class StrokeResult:
    source: Path
    target: Path
    remapped: dict[int, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return sum(self.remapped.values())

    def to_dict(self) -> dict:
        return {
            "source": str(self.source),
            "target": str(self.target),
            "remapped": self.remapped,
            "total": self.total,
        }


class ClassicPdf:
    """Read-only view of a PDF with one classic cross-reference table."""

    def __init__(self, data: bytes):
        self.data = data
        match = re.search(rb"startxref\s+(\d+)\s+%%EOF\s*$", data)
        if match is None:
            raise PdfStrokeError("no startxref at the end of the file")
        xref_at = int(match.group(1))
        if data[xref_at:xref_at + 4] != b"xref":
            raise PdfStrokeError("cross-reference stream PDFs are not supported")
        self.offsets: dict[int, int] = {}
        pos = xref_at + 4
        header = re.compile(rb"\s*(\d+)\s+(\d+)[ \t]*\r?\n")
        match = header.match(data, pos)
        while match:
            first, count = int(match.group(1)), int(match.group(2))
            pos = match.end()
            for k in range(count):
                entry = data[pos:pos + 20]
                pos += 20
                if entry[17:18] == b"n":
                    self.offsets[first + k] = int(entry[:10])
            match = header.match(data, pos)
        trailer_at = data.rfind(b"trailer", xref_at)
        if trailer_at < 0:
            raise PdfStrokeError("no trailer after the cross-reference table")
        self.trailer = data[trailer_at:data.rindex(b"startxref")]
        if b"/Prev" in self.trailer:
            raise PdfStrokeError("incrementally updated PDFs are not supported")
        if b"/Encrypt" in self.trailer:
            raise PdfStrokeError("encrypted PDFs are not supported")
        root = re.search(rb"/Root\s+(\d+)\s+0\s+R", self.trailer)
        size = re.search(rb"/Size\s+(\d+)", self.trailer)
        if root is None or size is None:
            raise PdfStrokeError("trailer lacks /Root or /Size")
        self.root = int(root.group(1))
        self.size = int(size.group(1))

    def raw(self, num: int) -> bytes:
        if num not in self.offsets:
            raise PdfStrokeError(f"object {num} is not in the cross-reference table")
        start = self.offsets[num]
        end = self.data.index(b"endobj", start) + len(b"endobj")
        return self.data[start:end]

    def head(self, num: int) -> bytes:
        raw = self.raw(num)
        at = raw.find(b"stream")
        return raw[:at] if at >= 0 else raw

    def _resolve(self, value: bytes) -> bytes:
        ref = re.fullmatch(rb"\s*(\d+)\s+0\s+R\s*", value)
        return self.head(int(ref.group(1))) if ref else value

    def stream(self, num: int) -> tuple[bytes, int, bytes, bytes]:
        """Return (dictionary, body start within raw, encoded body, decoded body)."""

        raw = self.raw(num)
        head = raw[:raw.index(b"stream")]
        length = re.search(rb"/Length\s+(\d+)(\s+\d+\s+R)?", head)
        if length is None or length.group(2):
            raise PdfStrokeError(f"object {num}: stream length must be a direct number")
        start = raw.index(b"stream") + len(b"stream")
        start += 2 if raw[start:start + 2] == b"\r\n" else 1
        body = raw[start:start + int(length.group(1))]
        filters = re.findall(rb"/(\w+Decode)\b", head)
        if filters == [b"FlateDecode"]:
            decoded = zlib.decompress(body)
        elif not filters:
            decoded = body
        else:
            raise PdfStrokeError(f"object {num}: unsupported stream filter {filters}")
        return head, start, body, decoded

    def pages(self) -> list[int]:
        found: list[int] = []

        def walk(num: int, depth: int = 0) -> None:
            if depth > 32:
                raise PdfStrokeError("page tree is too deep")
            head = self.head(num)
            if re.search(rb"/Type\s*/Pages\b", head):
                kids = re.search(rb"/Kids\s*\[([^\]]*)\]", head)
                for kid in _REF.findall(kids.group(1) if kids else b""):
                    walk(int(kid), depth + 1)
            else:
                found.append(num)

        catalog = self.head(self.root)
        pages = re.search(rb"/Pages\s+(\d+)\s+0\s+R", catalog)
        if pages is None:
            raise PdfStrokeError("catalog has no page tree")
        walk(int(pages.group(1)))
        return found

    def contents(self, page: int) -> list[int]:
        match = re.search(rb"/Contents\s*(\[[^\]]*\]|\d+\s+0\s+R)", self.head(page))
        return [int(x) for x in _REF.findall(match.group(1))] if match else []

    def has_image(self, page: int) -> bool:
        head = self.head(page)
        resources = re.search(rb"/Resources\s+(\d+\s+0\s+R)", head)
        if resources:
            head = self._resolve(resources.group(1))
        xobjects = re.search(rb"/XObject\s*(<<.*?>>|\d+\s+0\s+R)", head, re.S)
        if xobjects is None:
            return False
        table = self._resolve(xobjects.group(1))
        return any(
            re.search(rb"/Subtype\s*/Image", self.head(int(ref))) for ref in _REF.findall(table)
        )


def page_widths(pdf: ClassicPdf, page: int) -> Counter:
    """Count the line-start width operators on one page, by width."""

    counts: Counter = Counter()
    for num in pdf.contents(page):
        counts.update(float(w) for w in _LINE_WIDTH.findall(pdf.stream(num)[3]))
    return counts


def parse_pages(spec: str, page_count: int) -> list[int]:
    """Parse '5-17' or '1,3,5-7' into sorted 1-based page numbers."""

    pages: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        match = re.fullmatch(r"(\d+)(?:-(\d+))?", part)
        if match is None:
            raise PdfStrokeError(f"bad page range {part!r}; use e.g. 5-17 or 1,3")
        first = int(match.group(1))
        last = int(match.group(2) or first)
        if first < 1 or last < first or last > page_count:
            raise PdfStrokeError(f"page range {part!r} is outside 1-{page_count}")
        pages.update(range(first, last + 1))
    if not pages:
        raise PdfStrokeError("no pages selected")
    return sorted(pages)


def _format_width(value: float) -> bytes:
    return f"{value:g}".encode("ascii")


def remap_strokes(
    source: Path,
    target: Path,
    pages: str,
    mapping: dict[float, float] | None = None,
    *,
    allow_image_xobjects: bool = False,
) -> StrokeResult:
    """Write `target`: `source` with the widths on `pages` remapped by `mapping`."""

    mapping = dict(DEFAULT_MAPPING if mapping is None else mapping)
    source, target = Path(source), Path(target)
    if source.resolve() == target.resolve():
        raise PdfStrokeError("write to a new file; the source stays as exported")
    pdf = ClassicPdf(source.read_bytes())
    all_pages = pdf.pages()
    selected = parse_pages(pages, len(all_pages))

    owners: dict[int, int] = {}
    for number in selected:
        page = all_pages[number - 1]
        if not allow_image_xobjects and pdf.has_image(page):
            raise PdfStrokeError(f"page {number} embeds an image; refusing to rewrite it")
        for num in pdf.contents(page):
            if num in owners:
                raise PdfStrokeError(f"pages {owners[num]} and {number} share content stream {num}")
            owners[num] = number
    for number, page in enumerate(all_pages, 1):
        if number not in selected and set(pdf.contents(page)) & owners.keys():
            raise PdfStrokeError(f"page {number} shares a content stream with a selected page")

    result = StrokeResult(source=source, target=target)
    replaced: dict[int, bytes] = {}
    for num, number in owners.items():
        head, start, body, decoded = pdf.stream(num)
        if _INLINE_IMAGE.search(decoded):
            raise PdfStrokeError(f"page {number} embeds an inline image in its content stream")
        every = [float(w) for w in _ANY_WIDTH.findall(decoded)]
        unknown = sorted({w for w in every if w not in mapping})
        if unknown:
            raise PdfStrokeError(f"page {number}: widths {unknown} are not in the mapping")
        hits = 0

        def swap(match: re.Match) -> bytes:
            nonlocal hits
            hits += 1
            return _format_width(mapping[float(match.group(1))]) + b" w"

        rewritten = _LINE_WIDTH.sub(swap, decoded)
        if hits != len(every):
            raise PdfStrokeError(
                f"page {number}: {len(every) - hits} width operators are not at a line start"
            )
        result.remapped[number] = result.remapped.get(number, 0) + hits
        encoded = zlib.compress(rewritten, 9) if b"/FlateDecode" in head else rewritten
        raw = pdf.raw(num)
        new_head = re.sub(rb"/Length\s+\d+", b"/Length %d" % len(encoded), raw[:start], count=1)
        replaced[num] = new_head + encoded + raw[start + len(body):]

    order = sorted(pdf.offsets, key=pdf.offsets.__getitem__)
    out = bytearray(pdf.data[:pdf.offsets[order[0]]])
    offsets: dict[int, int] = {}
    for num in order:
        offsets[num] = len(out)
        out += replaced.get(num, pdf.raw(num))
        out += b"\n"
    xref_at = len(out)
    out += b"xref\n0 %d\n" % pdf.size
    for num in range(pdf.size):
        if num in offsets:
            out += b"%010d 00000 n \n" % offsets[num]
        else:
            out += b"0000000000 65535 f \n"
    out += pdf.trailer.rstrip() + b"\nstartxref\n%d\n%%%%EOF\n" % xref_at

    check = ClassicPdf(bytes(out))
    if len(check.pages()) != len(all_pages):
        raise PdfStrokeError("rewritten PDF lost pages; nothing written")
    target.write_bytes(bytes(out))
    return result
