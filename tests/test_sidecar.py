import datetime
from pathlib import Path

import pytest

from pihti_dedup.sidecar import (
    SidecarError,
    parse_sidecar,
    read_sidecar,
    seed_text,
    set_flag,
    set_hero,
    sidecar_path,
    with_flag,
    with_hero,
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
        ("---\nhero: sure\n---\n", "hero must be true or false"),
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


def test_hero_round_trips_through_seed_and_parse(tmp_path: Path) -> None:
    seeded = seed_text(FIELDS, seeded_on=datetime.date(2026, 9, 24), hero=True)
    companion = tmp_path / "vessel.iam.md"
    write_sidecar(companion, seeded)

    parsed = read_sidecar(companion)

    assert parsed is not None and parsed.hero is True
    assert seeded.splitlines()[-2:] == ["hero: true", "---"]  # the last key, readable
    assert parse_sidecar(seed_text(FIELDS)).hero is False
    assert "hero" not in seed_text(FIELDS)  # an ordinary seed says nothing about it


def test_setting_hero_changes_one_line_and_keeps_prose_and_keys_byte_for_byte() -> None:
    original = (
        "---\r\n"
        "part_number: UFC-152\r\n"
        "tags: [flange, cf150]   # flow style stays flow style\r\n"
        "reviewer: queezz\r\n"
        "---\r\n"
        "\r\n"
        "# Why\r\n"
        "\r\n"
        "The **main** assembly of the vessel.\r\n"
        "hero: this line is prose, not a key\r\n"
    )

    marked = with_hero(original, True)
    cleared = with_hero(marked, False)

    assert marked == original.replace("reviewer: queezz\r\n", "reviewer: queezz\r\nhero: true\r\n")
    assert parse_sidecar(marked).hero is True
    assert parse_sidecar(marked).frontmatter["tags"] == ["flange", "cf150"]
    assert cleared == original  # clearing removes the key and nothing else
    assert "hero" not in parse_sidecar(cleared).frontmatter
    assert with_hero(marked, True) == marked  # setting twice is a no-op


def test_clearing_removes_a_hand_typed_hero_key_wherever_it_sits() -> None:
    original = "---\nhero: yes\nstatus: draft\n---\n\nKeep me.\n"

    cleared = with_hero(original, False)

    assert cleared == "---\nstatus: draft\n---\n\nKeep me.\n"


def test_set_hero_creates_a_seeded_sidecar_only_to_set_it(tmp_path: Path) -> None:
    companion = tmp_path / "vessel.iam.md"

    assert set_hero(companion, False, FIELDS) is False
    assert not companion.exists()  # clearing a flag that was never set writes nothing
    assert set_hero(companion, True, FIELDS, seeded_on=datetime.date(2026, 9, 24)) is True

    assert companion.read_text(encoding="utf-8") == (
        "---\n"
        "part_number: B_probe_bearing\n"
        "material: PAEK 樹脂\n"
        "status: ''\n"
        "tags: []\n"
        "supersedes: ''\n"
        "seeded_from_iproperties: 2026-09-24\n"
        "hero: true\n"
        "---\n"
    )
    assert set_hero(companion, False, FIELDS) is True
    assert read_sidecar(companion).hero is False


def test_set_hero_refuses_a_sidecar_it_cannot_parse(tmp_path: Path) -> None:
    companion = tmp_path / "vessel.iam.md"
    companion.write_bytes(b"---\nstatus: shipped\n---\n\nKeep me.\n")

    with pytest.raises(SidecarError):
        set_hero(companion, True, FIELDS)

    assert companion.read_bytes() == b"---\nstatus: shipped\n---\n\nKeep me.\n"


def test_featured_round_trips_beside_hero_and_changes_one_line(tmp_path: Path) -> None:
    seeded = seed_text(FIELDS, seeded_on=datetime.date(2026, 9, 24), featured=True)
    assert parse_sidecar(seeded).featured is True and parse_sidecar(seeded).hero is False
    assert parse_sidecar(seed_text(FIELDS)).featured is False
    with pytest.raises(SidecarError, match="featured must be true or false"):
        parse_sidecar("---\nfeatured: maybe\n---\n")

    original = "---\r\nstatus: draft\r\ntags: [a, b]\r\nhero: true\r\n---\r\n\r\nKeep me.\r\n"
    marked = with_flag(original, "featured", True)
    assert marked == original.replace("hero: true\r\n", "hero: true\r\nfeatured: true\r\n")
    both = parse_sidecar(marked)
    assert both.hero is True and both.featured is True
    assert with_flag(marked, "featured", False) == original  # the hero line stays
    assert with_flag(marked, "featured", True) == marked
    with pytest.raises(ValueError):
        with_flag(original, "status", True)

    companion = tmp_path / "flange.ipt.md"
    assert set_flag(companion, "featured", False, FIELDS) is False and not companion.exists()
    assert set_flag(companion, "featured", True, FIELDS, seeded_on=datetime.date(2026, 9, 24)) is True
    written = read_sidecar(companion)
    assert written.featured is True and written.hero is False
    assert written.frontmatter["part_number"] == "B_probe_bearing"
    assert set_flag(companion, "featured", False, FIELDS) is True
    assert "featured" not in read_sidecar(companion).frontmatter
