"""Portable metadata sidecars for CAD files.

A sidecar is a plain Markdown file named after the whole CAD filename plus
`.md` — `B_probe_bearing.ipt` gets `B_probe_bearing.ipt.md` — so it sorts next to
its file, survives a copy, and never collides with the `.ipt`/`.idw` pair of the
same stem. It holds YAML frontmatter followed by free prose:

```text
---
part_number: B_probe_bearing
material: PAEK 樹脂
status: draft
tags: [boron-probe, bearing]
supersedes: BoronProbe/parts/B_probe_bearing.ipt
seeded_from_iproperties: 2026-08-05
hero: true
---

Why this part exists, what it mates with, what is still unverified.
```

Frontmatter schema — deliberately seven keys, all optional:

- `part_number` — Inventor Part Number as seeded, kept so a later drift is visible
- `material` — Inventor Material as seeded
- `status` — one of `concept`, `draft`, `manufactured`, `obsolete`, or empty
- `tags` — list of short strings
- `supersedes` — workspace-relative path of the file this one replaces, or empty
- `seeded_from_iproperties` — date the sidecar was generated
- `hero` — `true` when the owner designated this file a main assembly (or main
  file); absent otherwise

Sidecars are written next to the CAD file and never committed automatically;
they surface as untracked or modified files for the owner's own Git flow.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

FENCE = "---"
SIDECAR_SUFFIX = ".md"
FRONTMATTER_FIELDS = (
    "part_number",
    "material",
    "status",
    "tags",
    "supersedes",
    "seeded_from_iproperties",
    "hero",
)
HERO_KEY = "hero"
STATUS_VALUES = ("concept", "draft", "manufactured", "obsolete")


class SidecarError(ValueError):
    """The sidecar text is not something this tool is willing to write."""


@dataclass(frozen=True)
class Sidecar:
    frontmatter: dict = field(default_factory=dict)
    body: str = ""

    @property
    def status(self) -> str:
        return str(self.frontmatter.get("status") or "")

    @property
    def tags(self) -> tuple[str, ...]:
        values = self.frontmatter.get("tags") or ()
        if isinstance(values, (list, tuple)):
            return tuple(str(value) for value in values)
        return ()

    @property
    def hero(self) -> bool:
        return self.frontmatter.get(HERO_KEY) is True


def sidecar_path(cad_path: Path | str) -> Path:
    """Return the sidecar path for a CAD file: full filename plus `.md`."""

    path = Path(cad_path)
    return path.with_name(path.name + SIDECAR_SUFFIX)


def parse_sidecar(text: str) -> Sidecar:
    """Parse sidecar text, raising `SidecarError` on anything unwritable."""

    stripped = text.lstrip("﻿")
    if not stripped.startswith(FENCE):
        raise SidecarError("the file must start with a --- frontmatter fence")
    rest = stripped[len(FENCE) :].lstrip("\r")
    if not rest.startswith("\n"):
        raise SidecarError("the opening --- fence must be alone on the first line")
    lines = rest[1:].splitlines(keepends=True)
    closing = None
    for index, line in enumerate(lines):
        if line.strip() == FENCE:
            closing = index
            break
    if closing is None:
        raise SidecarError("the frontmatter block is not closed by a --- line")
    raw = "".join(lines[:closing])
    body = "".join(lines[closing + 1 :]).lstrip("\n")
    try:
        loaded = yaml.safe_load(raw) if raw.strip() else {}
    except yaml.YAMLError as exc:
        raise SidecarError(f"the frontmatter is not valid YAML: {exc}") from exc
    if loaded is None:
        loaded = {}
    if not isinstance(loaded, dict):
        raise SidecarError("the frontmatter must be a mapping of keys to values")
    return Sidecar(frontmatter=validate_frontmatter(loaded), body=body)


def validate_frontmatter(frontmatter: dict) -> dict:
    """Check the small schema. Unknown keys are kept; wrong shapes are refused."""

    status = frontmatter.get("status")
    if status not in (None, "") and str(status) not in STATUS_VALUES:
        allowed = ", ".join(STATUS_VALUES)
        raise SidecarError(f"status must be empty or one of: {allowed}")
    tags = frontmatter.get("tags")
    if tags not in (None, "") and not isinstance(tags, (list, tuple)):
        raise SidecarError("tags must be a YAML list")
    if isinstance(tags, (list, tuple)) and any(isinstance(tag, (list, dict)) for tag in tags):
        raise SidecarError("tags must be a flat list of short strings")
    supersedes = frontmatter.get("supersedes")
    if supersedes not in (None, "") and not isinstance(supersedes, str):
        raise SidecarError("supersedes must be a workspace-relative path")
    hero = frontmatter.get(HERO_KEY)
    if hero not in (None, "") and not isinstance(hero, bool):
        raise SidecarError("hero must be true or false")
    return frontmatter


def format_sidecar(frontmatter: dict, body: str = "") -> str:
    """Render frontmatter plus prose back to sidecar text."""

    ordered = {key: frontmatter[key] for key in FRONTMATTER_FIELDS if key in frontmatter}
    ordered.update({key: value for key, value in frontmatter.items() if key not in ordered})
    dumped = yaml.safe_dump(
        ordered, allow_unicode=True, sort_keys=False, default_flow_style=False
    ).strip("\n")
    prose = body.strip("\n")
    return f"{FENCE}\n{dumped}\n{FENCE}\n\n{prose}\n" if prose else f"{FENCE}\n{dumped}\n{FENCE}\n"


def seed_frontmatter(
    fields: dict[str, object],
    *,
    seeded_on: datetime.date | None = None,
    hero: bool = False,
) -> dict[str, object]:
    """Build frontmatter from extracted iProperties, leaving judgement blank."""

    def text(name: str) -> str:
        value = fields.get(name)
        return str(value).strip() if isinstance(value, str) else ""

    seeded: dict[str, object] = {
        "part_number": text("part_number"),
        "material": text("material"),
        "status": "",
        "tags": [],
        "supersedes": "",
        "seeded_from_iproperties": seeded_on or datetime.date.today(),
    }
    if hero:
        seeded[HERO_KEY] = True
    return seeded


def seed_text(
    fields: dict[str, object],
    *,
    seeded_on: datetime.date | None = None,
    hero: bool = False,
) -> str:
    """Seed text for a new sidecar: iProperties in frontmatter, empty prose."""

    return format_sidecar(seed_frontmatter(fields, seeded_on=seeded_on, hero=hero))


_HERO_LINE = re.compile(r"hero[ \t]*:")


def with_hero(text: str, hero: bool) -> str:
    """Return sidecar text with only the `hero` key set to true or removed.

    The text is parsed first, so frontmatter this tool cannot read is refused
    rather than rewritten. The edit is one frontmatter line: `hero: true` goes
    in before the closing fence, or an existing top-level `hero:` line (with
    any indented continuation) comes out. Every other byte is kept: the other
    keys and their formatting, the line endings, and the prose. Should that
    one-line edit ever not yield exactly the intended frontmatter, the
    frontmatter alone is re-serialised; the prose is still left untouched.
    """

    current = parse_sidecar(text)
    if current.hero == hero and (hero or HERO_KEY not in current.frontmatter):
        return text
    wanted = {key: value for key, value in current.frontmatter.items() if key != HERO_KEY}
    if hero:
        wanted[HERO_KEY] = True

    bom = "\ufeff" if text.startswith("\ufeff") else ""
    lines = text[len(bom) :].splitlines(keepends=True)
    newline = "\r\n" if lines[0].endswith("\r\n") else "\n"
    closing = next(index for index in range(1, len(lines)) if lines[index].strip() == FENCE)
    kept: list[str] = []
    skipping = False
    for line in lines[1:closing]:
        if skipping and line[:1] in (" ", "\t"):
            continue
        skipping = bool(_HERO_LINE.match(line))
        if not skipping:
            kept.append(line)
    if hero:
        kept.append(f"{HERO_KEY}: true{newline}")
    edited = bom + "".join([lines[0], *kept, *lines[closing:]])
    try:
        if parse_sidecar(edited).frontmatter == wanted:
            return edited
    except SidecarError:
        pass
    rest = "".join(lines[closing + 1 :])
    dumped = format_sidecar(wanted).rstrip("\n").replace("\n", newline)
    return f"{bom}{dumped}{newline}{rest}"


def read_sidecar(path: Path | str) -> Sidecar | None:
    """Read and parse a sidecar, or return None when it does not exist."""

    target = Path(path)
    if not target.is_file():
        return None
    return parse_sidecar(target.read_text(encoding="utf-8"))


def write_sidecar(path: Path | str, text: str, *, exact: bool = False) -> Sidecar:
    """Validate sidecar text, then write it. Invalid text never reaches disk.

    `exact=True` writes the text as given, without adding a final newline, so
    a one-key edit leaves every other byte of an existing sidecar alone.
    """

    parsed = parse_sidecar(text)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not exact and not text.endswith("\n"):
        text += "\n"
    target.write_text(text, encoding="utf-8", newline="")
    return parsed


def set_hero(
    path: Path | str,
    hero: bool,
    fields: dict[str, object],
    *,
    seeded_on: datetime.date | None = None,
) -> bool:
    """Set or clear `hero` in the sidecar at `path`; return whether it wrote.

    A missing sidecar is created only to set the flag, seeded from iProperties
    exactly as a new sidecar is. Clearing the flag of a file with no sidecar
    writes nothing. An existing sidecar that does not parse is refused.
    """

    target = Path(path)
    if not target.is_file():
        if not hero:
            return False
        write_sidecar(target, seed_text(fields, seeded_on=seeded_on, hero=True))
        return True
    with target.open(encoding="utf-8", newline="") as handle:
        original = handle.read()
    edited = with_hero(original, hero)
    if edited == original:
        return False
    write_sidecar(target, edited, exact=True)
    return True
