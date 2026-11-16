import zlib

import pytest

import pihti_dedup.cli as cli
from pihti_dedup.pdf_strokes import (
    ClassicPdf,
    PdfStrokeError,
    page_widths,
    parse_pages,
    remap_strokes,
)

# Shaped like Inventor's sheets: a standalone width at the start of a line,
# sometimes followed by other operators, and text that must survive untouched.
SHEET = (
    b"q\n0.54 w\n0 0 m 100 0 l S\n1.98 w 1 J\n10 10 m 20 20 l S\n"
    b"3.42 w\nBT /F1 12 Tf (Hole 5 THRU) Tj ET\nQ\n"
)


def build_pdf(contents, *, image_page=None, compress=True, trailer_extra=b"", share=False):
    objects = {}
    kids = []
    image_num = 3 + 2 * len(contents) if image_page else None
    for index, body in enumerate(contents):
        page_num, content_num = 3 + 2 * index, 4 + 2 * index
        kids.append(page_num)
        resources = b"/Resources << >>"
        if image_page == index + 1:
            resources = b"/Resources << /XObject << /Im1 %d 0 R >> >>" % image_num
        contents_ref = 4 if share and index == 1 else content_num
        objects[page_num] = (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 842 595] %s /Contents %d 0 R >>"
            % (resources, contents_ref)
        )
        data = zlib.compress(body) if compress else body
        flt = b" /Filter /FlateDecode" if compress else b""
        objects[content_num] = b"<< /Length %d%s >>\nstream\n%s\nendstream" % (len(data), flt, data)
    if image_num:
        objects[image_num] = (
            b"<< /Type /XObject /Subtype /Image /Width 1 /Height 1 /ColorSpace /DeviceGray"
            b" /BitsPerComponent 8 /Length 1 >>\nstream\n\x00\nendstream"
        )
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[2] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (
        b" ".join(b"%d 0 R" % kid for kid in kids),
        len(kids),
    )
    out = bytearray(b"%PDF-1.6\n%\xe2\xe3\xcf\xd3\n")
    offsets = {}
    for num in sorted(objects):
        offsets[num] = len(out)
        out += b"%d 0 obj\n%s\nendobj\n" % (num, objects[num])
    size = max(objects) + 1
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % size
    for num in range(1, size):
        out += b"%010d 00000 n \n" % offsets[num]
    out += b"trailer\n<< /Size %d /Root 1 0 R%s >>\nstartxref\n%d\n%%%%EOF\n" % (
        size,
        trailer_extra,
        xref,
    )
    return bytes(out)


def write(tmp_path, data, name="sheet.pdf"):
    path = tmp_path / name
    path.write_bytes(data)
    return path


def test_thins_only_the_selected_pages(tmp_path):
    source = write(tmp_path, build_pdf([SHEET, SHEET, SHEET]))
    target = tmp_path / "thin.pdf"

    result = remap_strokes(source, target, "2-3")

    assert result.remapped == {2: 3, 3: 3}
    assert result.total == 6
    before, after = ClassicPdf(source.read_bytes()), ClassicPdf(target.read_bytes())
    pages = after.pages()
    assert page_widths(after, pages[0]) == {0.54: 1, 1.98: 1, 3.42: 1}
    assert page_widths(after, pages[1]) == {0.39: 1, 1.16: 1, 1.55: 1}
    assert page_widths(after, pages[2]) == {0.39: 1, 1.16: 1, 1.55: 1}
    first = before.contents(before.pages()[0])[0]
    assert after.raw(first) == before.raw(first)
    decoded = after.stream(after.contents(pages[1])[0])[3]
    assert b"(Hole 5 THRU) Tj" in decoded
    assert b"1.16 w 1 J" in decoded


def test_keeps_uncompressed_streams_uncompressed(tmp_path):
    source = write(tmp_path, build_pdf([SHEET], compress=False))
    target = tmp_path / "thin.pdf"

    remap_strokes(source, target, "1")

    pdf = ClassicPdf(target.read_bytes())
    head, _, body, decoded = pdf.stream(pdf.contents(pdf.pages()[0])[0])
    assert b"/Filter" not in head
    assert body == decoded
    assert b"0.39 w" in decoded


@pytest.mark.parametrize(
    "build, pages, message",
    [
        (lambda: build_pdf([b"0.6 w\n0 0 m 1 1 l S\n"]), "1", "not in the mapping"),
        (lambda: build_pdf([b"q 0.54 w\n0 0 m 1 1 l S\n"]), "1", "not at a line start"),
        (lambda: build_pdf([SHEET], image_page=1), "1", "embeds an image"),
        (lambda: build_pdf([SHEET], trailer_extra=b" /Prev 9"), "1", "incrementally"),
        (lambda: build_pdf([SHEET, SHEET], share=True), "1", "shares a content stream"),
        (lambda: build_pdf([SHEET]), "2", "outside 1-1"),
    ],
)
def test_refuses_and_writes_nothing(tmp_path, build, pages, message):
    source = write(tmp_path, build())
    target = tmp_path / "thin.pdf"

    with pytest.raises(PdfStrokeError, match=message):
        remap_strokes(source, target, pages)

    assert not target.exists()


def test_refuses_to_overwrite_its_source(tmp_path):
    source = write(tmp_path, build_pdf([SHEET]))

    with pytest.raises(PdfStrokeError, match="new file"):
        remap_strokes(source, source, "1")


def test_parse_pages():
    assert parse_pages("5-17", 17) == list(range(5, 18))
    assert parse_pages("1, 3,5-6", 6) == [1, 3, 5, 6]
    for bad in ("0", "18", "x", "4-2", ""):
        with pytest.raises(PdfStrokeError):
            parse_pages(bad, 17)


def test_cli_thins_and_reports(tmp_path, capsys):
    source = write(tmp_path, build_pdf([SHEET, SHEET]))
    target = tmp_path / "thin.pdf"

    assert cli.main(["pdf-strokes", str(source), str(target), "--pages", "2"]) == 0

    out = capsys.readouterr().out
    assert "page 2: 3 line widths thinned" in out
    assert target.exists()


def test_cli_reports_refusal(tmp_path, capsys):
    source = write(tmp_path, build_pdf([b"0.6 w\n"]))
    target = tmp_path / "thin.pdf"

    assert cli.main(["pdf-strokes", str(source), str(target), "--pages", "1"]) == 2

    assert "nothing written" in capsys.readouterr().err
    assert not target.exists()
