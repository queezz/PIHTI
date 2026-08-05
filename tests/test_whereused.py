import os
from pathlib import Path

from pihti_dedup.whereused import (
    ReferenceCache,
    build_index,
    extract_filenames,
    filename_locations,
)


def blob(*stored_paths: str, offset: int = 0) -> bytes:
    """A synthetic document body: garbage with UTF-16LE paths embedded in it.

    `offset` shifts everything by one byte so the same paths land on the odd
    alignment a real OLE stream also produces.
    """

    payload = bytearray(b"\xff" * offset) + bytearray(b"\xde\xad" * 4)
    for stored in stored_paths:
        payload += b"\x00\x00" + stored.encode("utf-16-le") + b"\x00\x00"
    return bytes(payload)


def write_document(path: Path, *stored_paths: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(blob(*stored_paths))
    return path


def test_extraction_keeps_the_filename_and_drops_the_stored_directory() -> None:
    data = blob(
        "..\\parts\\bearing.ipt",
        "C:/Users/someone/Work/PIHTI/BoronProbe/probe.iam",
        "flange.idw",
    )

    assert extract_filenames(data) == frozenset({"bearing.ipt", "probe.iam", "flange.idw"})


def test_extraction_survives_both_byte_alignments() -> None:
    even = extract_filenames(blob("parts\\bearing.ipt", offset=0))
    odd = extract_filenames(blob("parts\\bearing.ipt", offset=1))

    assert even == odd == frozenset({"bearing.ipt"})


def test_extraction_matches_uppercase_extensions_and_non_ascii_names() -> None:
    data = blob("Plasma Vessel\\軸受.IPT", "parts\\図面\\B_probe_bearing.idw")

    assert extract_filenames(data) == frozenset({"軸受.IPT", "B_probe_bearing.idw"})


def test_a_bare_extension_with_no_stem_is_not_a_reference() -> None:
    assert extract_filenames(blob(".ipt", ".iam")) == frozenset()


def test_index_maps_filenames_to_referring_documents(tmp_path: Path) -> None:
    write_document(tmp_path / "BoronProbe" / "probe.iam", "parts\\bearing.ipt", "parts\\shaft.ipt")
    write_document(tmp_path / "図面" / "probe.idw", "..\\BoronProbe\\parts\\bearing.ipt")
    (tmp_path / "BoronProbe" / "parts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "BoronProbe" / "parts" / "bearing.ipt").write_bytes(b"geometry")

    index = build_index(tmp_path)

    assert index.documents == 2
    assert index.referring("bearing.ipt") == ("BoronProbe/probe.iam", "図面/probe.idw")
    assert index.referring("BEARING.IPT") == ("BoronProbe/probe.iam", "図面/probe.idw")
    assert index.referring("shaft.ipt") == ("BoronProbe/probe.iam",)
    assert index.referring("absent.ipt") == ()


def test_a_document_naming_itself_is_not_its_own_referrer(tmp_path: Path) -> None:
    write_document(tmp_path / "probe.iam", "C:\\old\\workspace\\probe.iam", "parts\\bearing.ipt")

    index = build_index(tmp_path)

    assert index.referring("probe.iam") == ()
    assert index.referring("bearing.ipt") == ("probe.iam",)


def test_only_referring_extensions_are_read_and_save_history_is_skipped(tmp_path: Path) -> None:
    write_document(tmp_path / "live.iam", "parts\\bearing.ipt")
    write_document(tmp_path / "OldVersions" / "live.iam", "parts\\bearing.ipt")
    # A part can embed a filename too, but a part never consumes another document.
    write_document(tmp_path / "part.ipt", "parts\\bearing.ipt")

    index = build_index(tmp_path)

    assert index.documents == 1
    assert index.referring("bearing.ipt") == ("live.iam",)


def test_reference_cache_re_reads_only_when_the_document_changes(tmp_path: Path) -> None:
    document = write_document(tmp_path / "probe.iam", "parts\\bearing.ipt")
    stamp = 1_750_458_966_208_000_000
    os.utime(document, ns=(stamp, stamp))
    cache = ReferenceCache()
    first = build_index(tmp_path, cache=cache)

    document.write_bytes(blob("parts\\shaft.ipt"))
    os.utime(document, ns=(stamp, stamp))
    stale = build_index(tmp_path, cache=cache)

    os.utime(document, ns=(stamp + 1_000_000_000, stamp + 1_000_000_000))
    fresh = build_index(tmp_path, cache=cache)

    assert first.referring("bearing.ipt") == ("probe.iam",)
    assert stale.referring("bearing.ipt") == ("probe.iam",)  # unchanged mtime, cached answer
    assert fresh.referring("shaft.ipt") == ("probe.iam",)
    assert fresh.referring("bearing.ipt") == ()


def test_filename_locations_reaches_save_history_because_inventor_does(tmp_path: Path) -> None:
    (tmp_path / "Live").mkdir()
    (tmp_path / "Live" / "bearing.ipt").write_bytes(b"a")
    (tmp_path / "OldVersions").mkdir()
    (tmp_path / "OldVersions" / "bearing.ipt").write_bytes(b"b")
    (tmp_path / "notes.md").write_text("not CAD", encoding="utf-8")

    locations = filename_locations(tmp_path)

    assert locations["bearing.ipt"] == ("Live/bearing.ipt", "OldVersions/bearing.ipt")
    assert "notes.md" not in locations
