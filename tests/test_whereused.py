import os
import struct
from pathlib import Path

import pytest

from pihti_dedup.whereused import (
    ReferenceCache,
    WhereUsed,
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


def fragmented_ole(payload: bytes) -> bytes:
    """A real CFB v3 file with a 4096-byte stream in non-contiguous sectors."""

    free, end, fat_sector = 0xFFFFFFFF, 0xFFFFFFFE, 0xFFFFFFFD
    header = bytearray(512)
    header[:8] = bytes.fromhex("d0cf11e0a1b11ae1")
    struct.pack_into("<HHHHH", header, 24, 0x3E, 3, 0xFFFE, 9, 6)
    struct.pack_into("<9I", header, 40, 0, 1, 1, 0, 4096, end, 0, end, 0)
    struct.pack_into("<109I", header, 76, 0, *([free] * 108))
    chain = [2, 4, 3, 5, 6, 7, 8, 9]
    fat = [free] * 128
    fat[0], fat[1] = fat_sector, end
    for index, sector in enumerate(chain):
        fat[sector] = chain[index + 1] if index + 1 < len(chain) else end

    def entry(name, kind, child, start, size):
        result = bytearray(128)
        text = (name + "\0").encode("utf-16-le")
        result[:len(text)] = text
        struct.pack_into("<HBBIII", result, 64, len(text), kind, 1, free, free, child)
        struct.pack_into("<IQ", result, 116, start, size)
        return result

    directory = entry("Root Entry", 5, 1, end, 0)
    directory += entry("UFRxDoc", 2, free, chain[0], 4096)
    sectors = [struct.pack("<128I", *fat), bytes(directory).ljust(512, b"\0")]
    sectors += [b"\0" * 512 for _ in chain]
    payload = payload.ljust(4096, b"\0")
    assert len(payload) == 4096
    for index, sector in enumerate(chain):
        sectors[sector] = payload[index * 512:(index + 1) * 512]
    return bytes(header) + b"".join(sectors)


def test_reassembles_reference_names_across_noncontiguous_ole_sectors() -> None:
    name = "monotaro-telescope-sleeve-6.ipt"
    payload = b"\0" * 460 + blob("parts\\" + name)
    assert extract_filenames(fragmented_ole(payload)) == frozenset({name})


def test_ole_scan_ignores_unallocated_directory_bytes() -> None:
    data = bytearray(fragmented_ole(blob("parts\\actual-washer.ipt")))
    # Unused directory entry: raw scanning used to mistake this for a reference.
    fake = blob("English (United Statesg-washer.ipt")
    data[512 * 2 + 256:512 * 2 + 256 + len(fake)] = fake
    assert extract_filenames(bytes(data)) == frozenset({"actual-washer.ipt"})


def test_broken_ole_is_reported_instead_of_scanned_as_raw_bytes() -> None:
    with pytest.raises(OSError, match="OLE reference streams"):
        extract_filenames(bytes.fromhex("d0cf11e0a1b11ae1") + blob("unreliable.ipt"))


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


def test_index_maps_each_document_to_its_referenced_filenames(tmp_path: Path) -> None:
    write_document(
        tmp_path / "BoronProbe" / "probe.iam",
        "parts\\shaft.ipt",
        "parts\\Bearing.IPT",
        "drawings\\probe.idw",
    )

    index = build_index(tmp_path)

    assert index.document_names == {
        "BoronProbe/probe.iam": ("Bearing.IPT", "probe.idw", "shaft.ipt")
    }
    assert index.names_in("BoronProbe/probe.iam") == (
        "Bearing.IPT",
        "probe.idw",
        "shaft.ipt",
    )
    assert index.names_in(r"boronprobe\PROBE.IAM") == index.names_in(
        "BoronProbe/probe.iam"
    )
    assert index.names_in("absent.iam") == ()


def test_existing_whereused_constructors_default_to_no_forward_names(tmp_path: Path) -> None:
    index = WhereUsed(root=tmp_path, referrers={}, documents=0)

    assert index.document_names == {}
    assert index.names_in("probe.iam") == ()


def test_a_document_naming_itself_is_not_its_own_referrer(tmp_path: Path) -> None:
    write_document(tmp_path / "probe.iam", "C:\\old\\workspace\\probe.iam", "parts\\bearing.ipt")

    index = build_index(tmp_path)

    assert index.referring("probe.iam") == ()
    assert index.referring("bearing.ipt") == ("probe.iam",)
    assert index.names_in("probe.iam") == ("bearing.ipt",)


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
    assert first.names_in("probe.iam") == ("bearing.ipt",)
    assert stale.names_in("probe.iam") == ("bearing.ipt",)
    assert fresh.names_in("probe.iam") == ("shaft.ipt",)


def test_filename_locations_reaches_save_history_because_inventor_does(tmp_path: Path) -> None:
    (tmp_path / "Live").mkdir()
    (tmp_path / "Live" / "bearing.ipt").write_bytes(b"a")
    (tmp_path / "OldVersions").mkdir()
    (tmp_path / "OldVersions" / "bearing.ipt").write_bytes(b"b")
    (tmp_path / "notes.md").write_text("not CAD", encoding="utf-8")

    locations = filename_locations(tmp_path)

    assert locations["bearing.ipt"] == ("Live/bearing.ipt", "OldVersions/bearing.ipt")
    assert "notes.md" not in locations


def test_staging_cannot_create_doctor_referrers_but_remains_a_resolution_concern(
    tmp_path: Path,
) -> None:
    write_document(tmp_path / "live.iam", "parts\\bearing.ipt")
    write_document(tmp_path / "staging" / "import.iam", "parts\\missing-import.ipt")
    (tmp_path / "staging" / "bearing.ipt").write_bytes(b"imported geometry")

    index = build_index(tmp_path)

    assert index.documents == 1
    assert index.referring("missing-import.ipt") == ()
    assert index.names_in("staging/import.iam") == ()
    assert filename_locations(tmp_path)["bearing.ipt"] == ("staging/bearing.ipt",)
