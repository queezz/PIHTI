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
---

Why this part exists, what it mates with, what is still unverified.
```

Frontmatter schema — deliberately six keys, all optional:

- `part_number` — Inventor Part Number as seeded, kept so a later drift is visible
- `material` — Inventor Material as seeded
- `status` — one of `concept`, `draft`, `manufactured`, `obsolete`, or empty
- `tags` — list of short strings
- `supersedes` — workspace-relative path of the file this one replaces, or empty
- `seeded_from_iproperties` — date the sidecar was generated

Sidecars are written next to the CAD file and never committed automatically;
they surface as untracked or modified files for the owner's own Git flow.
"""

from __future__ import annotations

import datetime
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
)
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
    fields: dict[str, object], *, seeded_on: datetime.date | None = None
) -> dict[str, object]:
    """Build frontmatter from extracted iProperties, leaving judgement blank."""

    def text(name: str) -> str:
        value = fields.get(name)
        return str(value).strip() if isinstance(value, str) else ""

    return {
        "part_number": text("part_number"),
        "material": text("material"),
        "status": "",
        "tags": [],
        "supersedes": "",
        "seeded_from_iproperties": seeded_on or datetime.date.today(),
    }


def seed_text(fields: dict[str, object], *, seeded_on: datetime.date | None = None) -> str:
    """Seed text for a new sidecar: iProperties in frontmatter, empty prose."""

    return format_sidecar(seed_frontmatter(fields, seeded_on=seeded_on))


def read_sidecar(path: Path | str) -> Sidecar | None:
    """Read and parse a sidecar, or return None when it does not exist."""

    target = Path(path)
    if not target.is_file():
        return None
    return parse_sidecar(target.read_text(encoding="utf-8"))


def write_sidecar(path: Path | str, text: str) -> Sidecar:
    """Validate sidecar text, then write it. Invalid text never reaches disk."""

    parsed = parse_sidecar(text)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8", newline="\n")
    return parsed
