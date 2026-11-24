"""Add sourcing links AFTER Inventor export and pdf-strokes (requires pypdf).

Usage: python add-monotaro-pdf-links.py thin.pdf Bellows-Monotaro-A4-JIS-man.pdf
The adjacent manifest records native note bounds as fractions of the sheet.
Regenerate those bounds if the sourcing-page layout changes.
"""

import argparse
import json
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Link


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    args = parser.parse_args()
    if args.source.resolve() == args.target.resolve():
        parser.error("Use separate source and target paths")
    manifest = json.loads(Path(__file__).with_name("monotaro-pdf-links.json").read_text(encoding="utf8"))
    reader = PdfReader(args.source)
    if len(reader.pages) != 23:
        raise ValueError("Expected the reviewed 23-sheet drawing")
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    for item in manifest["links"]:
        index = item["page"] - 1
        page = reader.pages[index]
        if item["code"] not in page.extract_text():
            raise ValueError(f"Order code missing from expected sheet: {item['code']}")
        if page.get("/Annots"):
            raise ValueError("Source already has annotations; start from the unlinked thin PDF")
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        x0, y0, x1, y1 = item["rect_fraction"]
        rect = (x0 * width - 3, y0 * height - 3, x1 * width + 3, y1 * height + 3)
        writer.add_annotation(page_number=index, annotation=Link(rect=rect, url=item["url"]))
    writer.write(args.target)
    result = PdfReader(args.target)
    if [p.extract_text() for p in reader.pages] != [p.extract_text() for p in result.pages]:
        raise ValueError("PDF text changed unexpectedly")
    actual = [a.get_object()["/A"]["/URI"] for a in result.pages[22]["/Annots"]]
    if actual != [item["url"] for item in manifest["links"]]:
        raise ValueError("Saved link annotations do not match the manifest")
    print(f"Verified {len(actual)} MonotaRO links; all 23 pages retain identical text")


if __name__ == "__main__":
    main()
