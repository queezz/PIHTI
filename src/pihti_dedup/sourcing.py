"""Sourcing notes: the parts a folder's design is built around, one note per option.

Some parts of a design are bought, not drawn: a bellows, a linear stage, a
flange. The design is then drawn around the part that was chosen, so the
choice belongs beside the CAD it shaped. A folder's sourcing options live in
its own `sourcing/` folder, one Markdown note per option:

```text
<folder>/sourcing/<slug>.md
<folder>/sourcing/attachments/<timestamp>-<name>.png|.jpg|.pdf|...
```

A note is YAML frontmatter followed by free prose, the same shape as a sidecar:

```text
---
title: Edge-welded bellows, 40 mm stroke
vendor: Example Vacuum
part_number: EWB-40
url: https://example.com/ewb-40
price: 38,000 JPY
status: quoted
for:
- bellows.iam
date: 2026-09-24
---

Why this one. ![catalogue page](attachments/20260924-101500-catalogue.png)
[Quote](attachments/20260924-101512-quote.pdf)
```

Frontmatter keys: `title` (required), `vendor`, `part_number`, `url` (http or
https, or empty), `price` (free text), `status` (one of `STATUS_VALUES`),
`for` (CAD filenames in the folder this option is for; may be empty), and
`date`. Unknown keys are kept as written.

Pictures and PDFs sit in `sourcing/attachments/` and are referenced from the
note with ordinary relative Markdown links, so the same note reads in GitHub,
MkDocs and Obsidian. Obsidian's own `![[attachments/name.png]]` embed is
accepted and rewritten to the standard form before rendering.

None of these files has a CAD extension, so the inventory, the folder tree and
the duplicate tooling never see them. Nothing here commits, and nothing here
deletes a note or an attachment.
"""

from __future__ import annotations

import datetime
import posixpath
import re
import secrets
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

import yaml

from pihti_dedup.sidecar import FENCE, SidecarError, split_frontmatter

SOURCING_DIR = "sourcing"
ATTACHMENTS_DIR = "attachments"
NOTE_SUFFIX = ".md"
STATUS_VALUES = ("candidate", "quoted", "ordered", "received", "rejected")
FIELDS = ("title", "vendor", "part_number", "url", "price", "status", "for", "date")
TEXT_FIELDS = ("vendor", "part_number", "url", "price")

#: The only files the attachment route will serve or the attach route accept.
ATTACHMENT_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".pdf": "application/pdf",
}
IMAGE_EXTENSIONS = frozenset(ext for ext, kind in ATTACHMENT_TYPES.items() if kind.startswith("image/"))
#: What a pasted or dropped file without a usable name is saved as.
MIME_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
    "application/pdf": ".pdf",
}
MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
# A note name: what `slugify` writes, or a hand-named note (no path, no leading dot).
_SLUG_SHAPE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,119}$")
# `![[target]]` and `![[target|caption]]`, as Obsidian writes an embed.
_OBSIDIAN_EMBED = re.compile(r"!\[\[([^\]\n|]+)(?:\|([^\]\n]*))?\]\]")


class SourcingError(ValueError):
    """A sourcing note or attachment this tool will not write or read."""


@dataclass(frozen=True)
class SourcingOption:
    """One parsed sourcing note."""

    folder: str
    slug: str
    frontmatter: dict = field(default_factory=dict)
    body: str = ""
    mtime_ns: int = 0

    def text(self, key: str) -> str:
        value = self.frontmatter.get(key)
        return "" if value is None else str(value).strip()

    @property
    def title(self) -> str:
        return self.text("title")

    @property
    def status(self) -> str:
        return self.text("status")

    @property
    def vendor(self) -> str:
        return self.text("vendor")

    @property
    def part_number(self) -> str:
        return self.text("part_number")

    @property
    def url(self) -> str:
        return self.text("url")

    @property
    def price(self) -> str:
        return self.text("price")

    @property
    def date(self) -> str:
        return self.text("date")

    @property
    def for_files(self) -> tuple[str, ...]:
        values = self.frontmatter.get("for") or ()
        return tuple(str(value).strip() for value in values if str(value).strip())

    @property
    def host(self) -> str:
        """The link's host, the words a card shows for it."""

        try:
            return urlsplit(self.url).hostname or self.url
        except ValueError:
            return self.url

    @property
    def relative_path(self) -> str:
        return f"{self.folder}/{SOURCING_DIR}/{self.slug}{NOTE_SUFFIX}"


@dataclass(frozen=True)
class SourcingProblem:
    """A note in a `sourcing/` folder that does not parse."""

    folder: str
    slug: str
    detail: str

    @property
    def relative_path(self) -> str:
        return f"{self.folder}/{SOURCING_DIR}/{self.slug}{NOTE_SUFFIX}"


def sourcing_dir(folder: Path) -> Path:
    return folder / SOURCING_DIR


def attachments_dir(folder: Path) -> Path:
    return folder / SOURCING_DIR / ATTACHMENTS_DIR


def is_sourcing_path(relative: str) -> bool:
    """True when a workspace-relative folder is itself inside a `sourcing/` folder."""

    return any(part.casefold() == SOURCING_DIR for part in PurePosixPath(relative).parts)


def validate_option(frontmatter: dict) -> dict:
    """Check the note schema. Unknown keys are kept; wrong shapes are refused."""

    title = frontmatter.get("title")
    if not isinstance(title, (str, int, float)) or not str(title).strip():
        raise SourcingError("title is required")
    status = frontmatter.get("status")
    if status is None or str(status) not in STATUS_VALUES:
        raise SourcingError(f"status must be one of: {', '.join(STATUS_VALUES)}")
    for key in TEXT_FIELDS:
        value = frontmatter.get(key)
        if value is not None and not isinstance(value, (str, int, float)):
            raise SourcingError(f"{key} must be plain text")
    url = frontmatter.get("url")
    if url not in (None, ""):
        scheme = urlsplit(str(url).strip()).scheme.casefold()
        if scheme not in {"http", "https"}:
            raise SourcingError("url must start with http:// or https://")
    targets = frontmatter.get("for")
    if targets not in (None, ""):
        if not isinstance(targets, (list, tuple)):
            raise SourcingError("for must be a YAML list of CAD filenames")
        for target in targets:
            if not isinstance(target, str) or not target.strip():
                raise SourcingError("for must list CAD filenames as plain text")
            if "/" in target or "\\" in target:
                raise SourcingError("for names files in this folder, without a path")
    date = frontmatter.get("date")
    if date not in (None, "") and not isinstance(date, (str, datetime.date)):
        raise SourcingError("date must be a date such as 2026-09-24")
    return frontmatter


def parse_option(text: str) -> tuple[dict, str]:
    """Parse note text into (frontmatter, body), raising `SourcingError`."""

    try:
        frontmatter, body = split_frontmatter(text)
    except SidecarError as exc:
        raise SourcingError(str(exc)) from exc
    return validate_option(frontmatter), body


def format_option(frontmatter: dict, body: str = "") -> str:
    """Render frontmatter plus prose back to note text, known keys first."""

    ordered = {key: frontmatter[key] for key in FIELDS if key in frontmatter}
    ordered.update({key: value for key, value in frontmatter.items() if key not in ordered})
    dumped = yaml.safe_dump(
        ordered, allow_unicode=True, sort_keys=False, default_flow_style=False
    ).strip("\n")
    prose = body.replace("\r\n", "\n").strip("\n")
    return f"{FENCE}\n{dumped}\n{FENCE}\n\n{prose}\n" if prose else f"{FENCE}\n{dumped}\n{FENCE}\n"


def slugify(title: str) -> str:
    """A filename stem from a title: lowercase ASCII words joined by hyphens."""

    slug = _SLUG_RE.sub("-", title.casefold()).strip("-")[:60].strip("-")
    return slug or "option"


def is_slug(value: str) -> bool:
    return bool(_SLUG_SHAPE.fullmatch(value or ""))


def unique_slug(folder: Path, title: str) -> str:
    base = slugify(title)
    directory = sourcing_dir(folder)
    candidate = base
    number = 2
    while (directory / f"{candidate}{NOTE_SUFFIX}").exists():
        candidate = f"{base}-{number}"
        number += 1
    return candidate


def note_path(folder: Path, slug: str) -> Path:
    if not is_slug(slug):
        raise SourcingError("not a sourcing note name")
    return sourcing_dir(folder) / f"{slug}{NOTE_SUFFIX}"


def read_folder_options(
    folder: Path, relative: str
) -> tuple[list[SourcingOption], list[SourcingProblem]]:
    """Every note in `folder/sourcing/`, newest first, and the ones that do not parse."""

    directory = sourcing_dir(folder)
    options: list[SourcingOption] = []
    problems: list[SourcingProblem] = []
    try:
        entries = sorted(directory.iterdir(), key=lambda item: item.name.casefold())
    except OSError:
        return options, problems
    for entry in entries:
        if entry.suffix.casefold() != NOTE_SUFFIX or not entry.is_file():
            continue
        slug = entry.stem
        try:
            text = entry.read_text(encoding="utf-8")
            frontmatter, body = parse_option(text)
            mtime_ns = entry.stat().st_mtime_ns
        except (SourcingError, OSError, UnicodeDecodeError) as exc:
            detail = str(exc).splitlines()[0] if str(exc) else exc.__class__.__name__
            problems.append(SourcingProblem(relative, slug, detail))
            continue
        options.append(SourcingOption(relative, slug, frontmatter, body, mtime_ns))
    return newest_first(options), problems


def newest_first(options: list[SourcingOption]) -> list[SourcingOption]:
    ordered = sorted(options, key=lambda option: option.title.casefold())
    return sorted(ordered, key=lambda option: (option.date, option.mtime_ns), reverse=True)


def write_option(path: Path, frontmatter: dict, body: str, *, create: bool) -> str:
    """Write a note; the text must parse back to exactly `frontmatter`.

    `create=True` refuses to replace an existing file. The `sourcing/` folder
    is created when needed; nothing is ever committed.
    """

    text = format_option(frontmatter, body)
    parsed, _ = parse_option(text)
    if parsed != frontmatter:
        raise SourcingError("the note would not read back as written; nothing was saved")
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "x" if create else "w"
    try:
        with path.open(mode, encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    except FileExistsError as exc:
        raise SourcingError("a sourcing note with that name already exists") from exc
    return text


def rewrite_obsidian_embeds(text: str) -> str:
    """`![[attachments/a.png|caption]]` becomes `![caption](attachments/a.png)`.

    A bare `![[a.png]]` is taken to mean the note's own attachments folder, as
    Obsidian resolves it by name. A PDF becomes a link rather than an image.
    """

    def standard(match: re.Match[str]) -> str:
        target = match.group(1).strip()
        label = (match.group(2) or "").strip()
        if "/" not in target:
            target = f"{ATTACHMENTS_DIR}/{target}"
        name = target.rsplit("/", 1)[-1]
        wrapped = f"<{target}>" if any(char.isspace() for char in target) else target
        if Path(name).suffix.casefold() in IMAGE_EXTENSIONS:
            return f"![{label or Path(name).stem}]({wrapped})"
        return f"[{label or name}]({wrapped})"

    return _OBSIDIAN_EMBED.sub(standard, text)


def attachment_target(value: str) -> str | None:
    """The attachment filename a relative note link names, or None.

    Only `attachments/<name>` (optionally `./attachments/<name>`) directly in
    the note's own attachments folder counts; anything that normalises
    elsewhere is left alone.
    """

    path = value.split("#", 1)[0].split("?", 1)[0].strip()
    normal = posixpath.normpath(path)
    parts = normal.split("/")
    if len(parts) != 2 or parts[0] != ATTACHMENTS_DIR or parts[1] in {"", ".", ".."}:
        return None
    return parts[1]


def sanitized_stem(filename: str) -> str:
    stem = Path(filename.replace("\\", "/").rsplit("/", 1)[-1]).stem
    return _NAME_RE.sub("-", stem).strip("-._")[:40].strip("-._") or "pasted"


def attachment_extension(filename: str, mimetype: str = "") -> str:
    """The allowed extension for an upload, from its name or else its type."""

    suffix = Path(filename or "").suffix.casefold()
    if suffix:
        if suffix not in ATTACHMENT_TYPES:
            raise SourcingError(
                "only PNG, JPEG, WebP, GIF, SVG, and PDF files can be attached"
            )
        return suffix
    guessed = MIME_EXTENSIONS.get((mimetype or "").split(";", 1)[0].strip().casefold())
    if guessed is None:
        raise SourcingError("only PNG, JPEG, WebP, GIF, SVG, and PDF files can be attached")
    return guessed


def content_matches(extension: str, data: bytes) -> bool:
    """The bytes are the kind of file the extension says."""

    head = data[:4096]
    if extension == ".png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if extension in {".jpg", ".jpeg"}:
        return head.startswith(b"\xff\xd8\xff")
    if extension == ".gif":
        return head.startswith((b"GIF87a", b"GIF89a"))
    if extension == ".webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    if extension == ".pdf":
        return head.lstrip()[:5] == b"%PDF-"
    if extension == ".svg":
        return b"<svg" in head.lower()
    return False


def save_attachment(
    folder: Path,
    filename: str,
    data: bytes,
    *,
    mimetype: str = "",
    now: datetime.datetime | None = None,
) -> tuple[str, str]:
    """Save an upload under `folder/sourcing/attachments/`; return (name, embed).

    The name is `YYYYmmdd-HHMMSS-<sanitised original stem><ext>`; a clash adds
    a short random suffix. A file is never overwritten, and only the allowed
    types, of at most `MAX_ATTACHMENT_BYTES`, whose bytes match their
    extension, are written.
    """

    extension = attachment_extension(filename, mimetype)
    if not data:
        raise SourcingError("the file is empty")
    if len(data) > MAX_ATTACHMENT_BYTES:
        raise SourcingError("attachments are limited to 25 MB")
    if not content_matches(extension, data):
        raise SourcingError(f"the file's contents are not a {extension[1:].upper()} file")
    stem = sanitized_stem(filename)
    moment = (now or datetime.datetime.now()).strftime("%Y%m%d-%H%M%S")
    directory = attachments_dir(folder)
    directory.mkdir(parents=True, exist_ok=True)
    name = f"{moment}-{stem}{extension}"
    for _ in range(8):
        try:
            with (directory / name).open("xb") as handle:
                handle.write(data)
            break
        except FileExistsError:
            name = f"{moment}-{stem}-{secrets.token_hex(3)}{extension}"
    else:
        raise SourcingError("could not find a free attachment name")
    return name, embed_for(name, stem)


def embed_for(name: str, label: str) -> str:
    target = f"{ATTACHMENTS_DIR}/{name}"
    if Path(name).suffix.casefold() in IMAGE_EXTENSIONS:
        return f"![{label}]({target})"
    return f"[{name}]({target})"


def status_counts(options) -> dict[str, int]:
    counts = dict.fromkeys(STATUS_VALUES, 0)
    for option in options:
        if option.status in counts:
            counts[option.status] += 1
    return counts


def summary_line(options, problems=()) -> str:
    """`3 options · 1 quoted · 1 ordered`: the total, then each later stage present."""

    total = len(options)
    parts = [f"{total} option{'s' if total != 1 else ''}"] if total else []
    counts = status_counts(options)
    parts += [f"{counts[status]} {status}" for status in STATUS_VALUES[1:] if counts[status]]
    if problems:
        parts.append(f"{len(problems)} does not parse" if len(problems) == 1 else f"{len(problems)} do not parse")
    return " · ".join(parts)
