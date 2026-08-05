import datetime
from pathlib import Path

import pytest

from pihti_dedup.sidecar import (
    SidecarError,
    parse_sidecar,
    read_sidecar,
    seed_text,
    sidecar_path,
    write_sidecar,
)

FIELDS = {"part_number": "B_probe_bearing", "material": "PAEK 樹脂", "designer": "zetsu"}


def test_sidecar_is_named_after_the_whole_cad_filename() -> None:
    assert sidecar_path(Path("BoronProbe_2026/parts/B_probe_bearing.ipt")).name == (
        "B_probe_bearing.ipt.md"
    )
    assert sidecar_path("parts/B_probe_bearing.idw").name == "B_probe_bearing.idw.md"


def test_seed_then_edit_then_save_round_trips(tmp_path: Path) -> None:
    target = tmp_path / "B_probe_bearing.ipt"
    target.write_bytes(b"cad")
    companion = sidecar_path(target)

    seeded = seed_text(FIELDS, seeded_on=datetime.date(2026, 8, 5))
    write_sidecar(companion, seeded)

    parsed = read_sidecar(companion)
    assert parsed is not None
    assert parsed.frontmatter["part_number"] == "B_probe_bearing"
    assert parsed.frontmatter["material"] == "PAEK 樹脂"
    assert parsed.frontmatter["seeded_from_iproperties"] == datetime.date(2026, 8, 5)
    assert parsed.status == ""
    assert parsed.tags == ()
    assert parsed.body == ""

    edited = companion.read_text(encoding="utf-8").replace("status: ''", "status: manufactured")
    edited = edited.replace("tags: []", "tags:\n- bearing\n- boron-probe")
    edited += "\nSupports the rotating probe; PAEK because of the bakeout temperature.\n"
    write_sidecar(companion, edited)

    saved = read_sidecar(companion)
    assert saved is not None
    assert saved.status == "manufactured"
    assert saved.tags == ("bearing", "boron-probe")
    assert "bakeout temperature" in saved.body
    assert saved.frontmatter["part_number"] == "B_probe_bearing"


def test_missing_sidecar_reads_as_none(tmp_path: Path) -> None:
    assert read_sidecar(tmp_path / "absent.ipt.md") is None


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("no frontmatter at all\n", "frontmatter fence"),
        ("---\npart_number: a\n\nprose\n", "not closed"),
        ("---\npart_number: [unclosed\n---\n", "not valid YAML"),
        ("---\n- just\n- a list\n---\n", "must be a mapping"),
        ("---\nstatus: shipped\n---\n", "status must be empty or one of"),
        ("---\ntags: bearing\n---\n", "tags must be a YAML list"),
        ("---\nsupersedes: 42\n---\n", "supersedes must be"),
    ],
)
def test_invalid_sidecars_are_refused_before_anything_is_written(
    tmp_path: Path, text: str, message: str
) -> None:
    companion = tmp_path / "part.ipt.md"

    with pytest.raises(SidecarError) as error:
        write_sidecar(companion, text)

    assert message in str(error.value)
    assert not companion.exists()


def test_unknown_keys_and_prose_survive_a_parse(tmp_path: Path) -> None:
    text = "---\npart_number: UFC-152\nreviewer: queezz\n---\n\n# Notes\n\nStill unverified.\n"

    parsed = parse_sidecar(text)

    assert parsed.frontmatter["reviewer"] == "queezz"
    assert parsed.body.startswith("# Notes")
