"""Server-side Markdown rendering for sidecar prose and folder notes.

The notes this viewer edits are ordinary Markdown files that MkDocs and GitHub
already render: a folder note *is* the folder's `README.md`, and a sidecar's
prose sits under YAML frontmatter. Showing them as raw text in the viewer was
the odd one out. `python-markdown` is the same engine family the documentation
site uses, so a heading, a table, or a fenced block looks here the way it will
look there.

Two deliberate narrowings of the engine, because this renders files that arrive
through student pull requests into a page that carries the viewer's own form
token:

- **Raw HTML never survives.** `html_block` and the inline `html` pattern are
  deregistered, so `<script>` renders as visible text instead of executing.
  HTML comments are dropped first, so a comment stays invisible rather than
  becoming literal escaped text on the page.
- **Only safe link schemes survive.** A `javascript:` href is stripped from the
  rendered anchor; the link text stays.

Nothing here writes to a file.
"""

from __future__ import annotations

import re
import threading
from html.parser import HTMLParser
from urllib.parse import urlsplit

import markdown
from markdown.treeprocessors import Treeprocessor
from markupsafe import Markup

#: Same three the MkDocs site relies on: pipe tables, ``` fences, and list
#: parsing that does not treat an indented sibling as a nested list.
MARKDOWN_EXTENSIONS = ("tables", "fenced_code", "sane_lists")

#: Schemes a rendered link or image may keep. The empty string covers relative
#: and fragment targets, which is how a note points at a sibling file.
SAFE_SCHEMES = frozenset({"", "http", "https", "mailto"})

_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_LOCAL = threading.local()


class _SafeLinks(Treeprocessor):
    """Drop `href`/`src` values whose scheme is not in `SAFE_SCHEMES`."""

    def run(self, root):
        for element in root.iter():
            attribute = "href" if element.tag == "a" else "src" if element.tag == "img" else None
            if attribute is None:
                continue
            value = element.get(attribute)
            if value is not None and not is_safe_url(value):
                del element.attrib[attribute]
        return None


def is_safe_url(value: str) -> bool:
    """True when a URL's scheme is one a rendered note is allowed to keep.

    Control characters and surrounding whitespace are removed first: a browser
    ignores them inside a scheme, so `java\\nscript:` must not read as safe.
    """

    cleaned = "".join(char for char in value if char.isprintable() and not char.isspace())
    try:
        scheme = urlsplit(cleaned).scheme
    except ValueError:
        return False
    return scheme.casefold() in SAFE_SCHEMES


def _engine() -> markdown.Markdown:
    """One configured renderer per thread; `Markdown` instances carry state."""

    engine = getattr(_LOCAL, "engine", None)
    if engine is None:
        engine = markdown.Markdown(extensions=list(MARKDOWN_EXTENSIONS), output_format="html")
        engine.preprocessors.deregister("html_block")
        engine.inlinePatterns.deregister("html")
        engine.treeprocessors.register(_SafeLinks(engine), "pihti_safe_links", 1)
        _LOCAL.engine = engine
    engine.reset()
    return engine


def render(text: str | None) -> Markup:
    """Render note text to HTML, marked safe because the engine escaped it."""

    if not text or not text.strip():
        return Markup("")
    return Markup(_engine().convert(_COMMENT_RE.sub("", text)))


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def plain_text(text: str | None) -> str:
    """Markdown reduced to a single line of prose, for a catalog excerpt.

    The catalog already inlines a note editor per folder and is heavy enough;
    an excerpt renders to plain text rather than to HTML so `**bold**` reads as
    `bold` in a section header without adding markup to 99 sections.
    """

    if not text or not text.strip():
        return ""
    extractor = _TextExtractor()
    extractor.feed(str(render(text)))
    extractor.close()
    return " ".join("".join(extractor.parts).split())
