import datetime
import re
from pathlib import Path

import pytest

from pihti_dedup import sourcing
from pihti_dedup.markdown_view import render
from pihti_dedup.notes_check import SOURCING, check_notes
from pihti_dedup.sourcing import (
    SourcingError,
    format_option,
    parse_option,
    read_folder_options,
    rewrite_obsidian_embeds,
    save_attachment,
)
from pihti_dedup.web import attachment_version, create_app

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
PDF = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="4" height="4"><rect width="4" height="4"/></svg>'


def make_workspace(root: Path) -> Path:
    for relative in ("bellows/bellows.iam", "bellows/flange.ipt", "PALP/clamp.ipt"):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(relative.encode())
    return root


def write_note(root: Path, folder: str, slug: str, text: str) -> Path:
    path = root / folder / "sourcing" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def note_text(title: str, status: str, *targets: str, date: str = "2026-09-24", body: str = "") -> str:
    lines = ["---", f"title: {title}", f"status: {status}"]
    lines += ["for:"] + [f"- {target}" for target in targets] if targets else ["for: []"]
    lines += [f"date: {date}", "---", "", body]
    return "\n".join(lines) + "\n"


def attach(root: Path, folder: str, name: str, data: bytes) -> Path:
    path = root / folder / "sourcing" / "attachments" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


# ---- the note format -------------------------------------------------------


def test_frontmatter_round_trips_and_keeps_unknown_keys() -> None:
    frontmatter = {
        "title": "Edge-welded bellows, 40 mm",
        "vendor": "Example Vacuum",
        "part_number": "0012",
        "url": "https://example.com/ewb-40",
        "price": "38,000 JPY",
        "status": "quoted",
        "for": ["bellows.iam", "flange.ipt"],
        "date": datetime.date(2026, 9, 24),
        "currency_note": "incl. tax",
    }
    text = format_option(frontmatter, "Why this one.\n")

    assert text.startswith("---\ntitle: Edge-welded bellows, 40 mm\nvendor: Example Vacuum\n")
    assert "part_number: '0012'\n" in text  # stays text, not the number 12
    assert "for:\n- bellows.iam\n- flange.ipt\n" in text
    assert "date: 2026-09-24\n" in text
    assert text.endswith("---\n\nWhy this one.\n")
    assert parse_option(text) == (frontmatter, "Why this one.\n")


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"status": "maybe"}, "status must be one of: candidate, quoted, ordered, received, rejected"),
        ({"status": None}, "status must be one of"),
        ({"title": "  "}, "title is required"),
        ({"url": "javascript:alert(1)"}, "url must start with http:// or https://"),
        ({"for": "bellows.iam"}, "for must be a YAML list"),
        ({"for": ["../PALP/clamp.ipt"]}, "without a path"),
    ],
)
def test_the_schema_refuses_a_bad_status_and_bad_shapes(change: dict, message: str) -> None:
    frontmatter = {"title": "Stage", "status": "candidate", "for": [], **change}
    text = "---\n" + "".join(
        f"{key}: {value!r}\n" if isinstance(value, str) else f"{key}: {value}\n"
        for key, value in frontmatter.items()
        if value is not None
    ) + "---\n"
    with pytest.raises(SourcingError, match=re.escape(message)):
        parse_option(text)


def test_obsidian_embeds_become_standard_markdown_before_rendering() -> None:
    text = "Front ![[attachments/front view.png|Front view]]\n\n![[quote.pdf]]\n\n![[side.jpg]]"

    rewritten = rewrite_obsidian_embeds(text)

    assert "![Front view](<attachments/front view.png>)" in rewritten
    assert "[quote.pdf](attachments/quote.pdf)" in rewritten
    assert "![side](attachments/side.jpg)" in rewritten
    html = str(render(rewritten, resolve=lambda value: "/served/" + value))
    assert '<img alt="Front view" src="/served/attachments/front view.png"' in html
    assert '<a href="/served/attachments/quote.pdf">quote.pdf</a>' in html


def test_the_resolver_sees_only_relative_targets() -> None:
    seen: list[str] = []

    def resolve(value: str):
        seen.append(value)
        return None

    render("[a](attachments/a.pdf) [b](https://example.com) [c](/abs) [d](#x) [e](javascript:x)", resolve)

    assert seen == ["attachments/a.pdf"]


def test_attachments_get_sanitised_timestamped_names_and_never_overwrite(tmp_path: Path) -> None:
    moment = datetime.datetime(2026, 9, 24, 10, 15, 0)

    first = save_attachment(tmp_path, "my photo (1)!.PNG", PNG, now=moment)
    second = save_attachment(tmp_path, "my photo (1)!.PNG", PNG + b"x", now=moment)
    pasted = save_attachment(tmp_path, "", PDF, mimetype="application/pdf", now=moment)

    assert first == (
        "20260924-101500-my-photo-1.png",
        "![my-photo-1](attachments/20260924-101500-my-photo-1.png)",
    )
    assert second[0] != first[0] and second[0].startswith("20260924-101500-my-photo-1-")
    assert pasted == ("20260924-101500-pasted.pdf", "[20260924-101500-pasted.pdf](attachments/20260924-101500-pasted.pdf)")
    folder = tmp_path / "sourcing" / "attachments"
    assert (folder / first[0]).read_bytes() == PNG
    assert (folder / second[0]).read_bytes() == PNG + b"x"
    with pytest.raises(SourcingError, match="only PNG"):
        save_attachment(tmp_path, "setup.exe", b"MZ" + b"\x00" * 10)
    with pytest.raises(SourcingError, match="not a PNG file"):
        save_attachment(tmp_path, "renamed.png", b"MZ" + b"\x00" * 10)
    with pytest.raises(SourcingError, match="25 MB"):
        save_attachment(tmp_path, "big.png", PNG + b"\x00" * sourcing.MAX_ATTACHMENT_BYTES)


# ---- serving attachments ---------------------------------------------------


def test_the_attachment_route_serves_only_sourcing_attachments(tmp_path: Path) -> None:
    root = make_workspace(tmp_path / "ws")
    image = attach(root, "bellows", "a.png", PNG)
    attach(root, "bellows", "notes.txt", b"text")
    (root / "bellows" / "sourcing" / "loose.png").write_bytes(PNG)
    (root / "bellows" / "attachments").mkdir()
    (root / "bellows" / "attachments" / "b.png").write_bytes(PNG)
    (tmp_path / "outside.png").write_bytes(PNG)
    client = create_app(root).test_client()

    stat = image.stat()
    good = client.get(
        f"/sourcing-file/bellows/sourcing/attachments/a.png?v={attachment_version(stat.st_mtime_ns, stat.st_size)}"
    )
    assert good.status_code == 200
    assert good.mimetype == "image/png" and good.data == PNG
    assert good.headers["Cache-Control"] == "private, max-age=31536000, immutable"
    assert good.headers["X-Content-Type-Options"] == "nosniff"
    stale = client.get("/sourcing-file/bellows/sourcing/attachments/a.png?v=0-0")
    assert stale.headers["Cache-Control"] == "private, no-cache"

    for refused in (
        "/sourcing-file/bellows/bellows.iam",  # a CAD file
        "/sourcing-file/bellows/sourcing/attachments/notes.txt",  # not an allowed type
        "/sourcing-file/bellows/sourcing/loose.png",  # not in attachments/
        "/sourcing-file/bellows/attachments/b.png",  # not under sourcing/
        "/sourcing-file/bellows/sourcing/attachments/../../../outside.png",  # traversal
        "/sourcing-file/bellows/sourcing/attachments/missing.png",
    ):
        assert client.get(refused).status_code == 404, refused


def test_a_pdf_is_served_inline_and_an_svg_sandboxed(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    attach(root, "bellows", "quote.pdf", PDF)
    attach(root, "bellows", "sketch.svg", SVG)
    client = create_app(root).test_client()

    pdf = client.get("/sourcing-file/bellows/sourcing/attachments/quote.pdf")
    svg = client.get("/sourcing-file/bellows/sourcing/attachments/sketch.svg")

    assert pdf.status_code == 200 and pdf.mimetype == "application/pdf"
    assert pdf.headers["Content-Disposition"].startswith("inline")
    assert "Content-Security-Policy" not in pdf.headers
    assert svg.mimetype == "image/svg+xml"
    assert "sandbox" in svg.headers["Content-Security-Policy"]
    assert "default-src 'none'" in svg.headers["Content-Security-Policy"]


# ---- attaching -------------------------------------------------------------


def test_attach_needs_the_token_and_saves_a_sanitised_name(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    app = create_app(root)
    client = app.test_client()
    token = app.config["FORM_TOKEN"]

    def post(name: str, data: bytes, headers=None, folder="bellows"):
        from io import BytesIO

        return client.post(
            f"/sourcing/{folder}/attach",
            data={"file": (BytesIO(data), name)},
            headers=headers if headers is not None else {"X-PIHTI-Token": token},
            content_type="multipart/form-data",
        )

    assert post("a.png", PNG, headers={}).status_code == 403
    assert post("a.png", PNG, headers={"X-PIHTI-Token": "guessed"}).status_code == 403
    assert not (root / "bellows" / "sourcing").exists()

    saved = post("Front view!.png", PNG)
    assert saved.status_code == 201
    result = saved.get_json()
    assert re.fullmatch(r"\d{8}-\d{6}-Front-view\.png", result["name"])
    assert result["embed"] == f"![Front-view](attachments/{result['name']})"
    assert result["url"].startswith(f"/sourcing-file/bellows/sourcing/attachments/{result['name']}?v=")
    assert (root / "bellows" / "sourcing" / "attachments" / result["name"]).read_bytes() == PNG

    pdf = post("Quote 2026.pdf", PDF).get_json()
    assert pdf["embed"] == f"[{pdf['name']}](attachments/{pdf['name']})"

    exe = post("setup.exe", b"MZ" + b"\x00" * 64)
    assert exe.status_code == 400 and "only PNG" in exe.get_json()["error"]
    big = post("huge.png", PNG + b"\x00" * (26 * 1024 * 1024))
    assert big.status_code == 413
    assert post("a.png", PNG, folder="..%2Foutside").status_code == 404
    assert post("a.png", PNG, folder="bellows/sourcing").status_code == 404
    names = sorted(item.name for item in (root / "bellows" / "sourcing" / "attachments").iterdir())
    assert names == sorted([result["name"], pdf["name"]])


# ---- writing a note --------------------------------------------------------


def test_new_then_edit_round_trips_through_the_form(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    app = create_app(root)
    client = app.test_client()
    token = app.config["FORM_TOKEN"]

    form = client.get("/sourcing/bellows/new").get_data(as_text=True)
    assert 'name="for" value="bellows.iam">' in form and 'name="for" value="flange.ipt">' in form
    assert f'value="{datetime.date.today().isoformat()}"' in form
    assert 'data-attach-url="/sourcing/bellows/attach"' in form
    assert '<option value="candidate" selected>' in form

    fields = {
        "token": token,
        "title": "Edge-welded bellows, 40 mm",
        "status": "quoted",
        "vendor": "Example Vacuum",
        "part_number": "EWB-40",
        "url": "https://example.com/ewb-40",
        "price": "38,000 JPY",
        "date": "2026-09-24",
        "for": ["bellows.iam"],
        "body": "Stroke fits.\r\n\r\n![front](attachments/front.png)\r\n",
    }
    assert client.post("/sourcing/bellows/new", data={**fields, "token": "guessed"}).status_code == 403
    created = client.post("/sourcing/bellows/new", data=fields)
    assert created.status_code == 302
    assert created.headers["Location"].endswith(
        "/sourcing/bellows/edge-welded-bellows-40-mm/edit?saved=1"
    )
    path = root / "bellows" / "sourcing" / "edge-welded-bellows-40-mm.md"
    assert path.read_text(encoding="utf-8") == (
        "---\n"
        "title: Edge-welded bellows, 40 mm\n"
        "vendor: Example Vacuum\n"
        "part_number: EWB-40\n"
        "url: https://example.com/ewb-40\n"
        "price: 38,000 JPY\n"
        "status: quoted\n"
        "for:\n"
        "- bellows.iam\n"
        "date: 2026-09-24\n"
        "---\n"
        "\n"
        "Stroke fits.\n"
        "\n"
        "![front](attachments/front.png)\n"
    )
    page = client.get("/catalog/bellows?option=edge-welded-bellows-40-mm").get_data(as_text=True)
    assert "Saved: Edge-welded bellows, 40 mm" in page
    assert 'id="option-edge-welded-bellows-40-mm" href="/sourcing/bellows/edge-welded-bellows-40-mm/edit"' in page
    assert 'data-status="quoted"' in page and 'data-url="https://example.com/ewb-40"' in page
    assert '<b class="badge badge-sourcing-quoted" title="Status: quoted">quoted</b>' in page

    # A second option with the same title gets its own file.
    client.post("/sourcing/bellows/new", data={**fields, "status": "candidate"})
    assert (root / "bellows" / "sourcing" / "edge-welded-bellows-40-mm-2.md").is_file()

    # Edit keeps a key written by hand and refuses a stale form.
    path.write_text(path.read_text(encoding="utf-8").replace("date:", "lead_time: 6 weeks\ndate:"), encoding="utf-8")
    edit = client.get("/sourcing/bellows/edge-welded-bellows-40-mm/edit").get_data(as_text=True)
    assert 'value="Edge-welded bellows, 40 mm"' in edit and '<option value="quoted" selected>' in edit
    assert 'name="for" value="bellows.iam" checked>' in edit
    revision = re.search(r'name="revision" value="([0-9a-f]+)"', edit).group(1)
    stale = client.post(
        "/sourcing/bellows/edge-welded-bellows-40-mm/edit",
        data={**fields, "revision": "0" * 16, "status": "ordered"},
    )
    assert stale.status_code == 409 and "changed on disk" in stale.get_data(as_text=True)
    assert 'data-save-error="true"' in stale.get_data(as_text=True)
    saved = client.post(
        "/sourcing/bellows/edge-welded-bellows-40-mm/edit",
        data={**fields, "revision": revision, "status": "ordered", "for": ["bellows.iam", "flange.ipt"]},
    )
    assert saved.status_code == 302
    text = path.read_text(encoding="utf-8")
    assert "status: ordered\n" in text and "- flange.ipt\n" in text
    assert "lead_time: 6 weeks\n" in text
    assert parse_option(text)[0]["status"] == "ordered"
    assert client.get("/sourcing/bellows/missing/edit").status_code == 404
    assert client.get("/sourcing/bellows/..%2F..%2Fx/edit").status_code == 404


def test_a_note_that_does_not_parse_is_shown_not_overwritten(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    broken = write_note(root, "bellows", "broken", "---\ntitle: Stage\nstatus: maybe\n---\n")
    app = create_app(root)
    client = app.test_client()

    page = client.get("/catalog/bellows").get_data(as_text=True)
    edit = client.get("/sourcing/bellows/broken/edit").get_data(as_text=True)
    post = client.post(
        "/sourcing/bellows/broken/edit",
        data={"token": app.config["FORM_TOKEN"], "title": "X", "status": "quoted"},
    )

    broken_line = page.split('<ul class="sourcing-broken">', 1)[1].split("</ul>", 1)[0]
    assert "does not parse" in broken_line and "status must be one of" in broken_line
    assert "This note does not parse" in edit and "<form" not in edit.split("sourcing-editor", 1)[1].split("</section>", 1)[0]
    assert post.status_code == 409
    assert broken.read_text(encoding="utf-8") == "---\ntitle: Stage\nstatus: maybe\n---\n"


# ---- where sourcing shows up ------------------------------------------------


def test_folder_sourcing_actions_open_the_workspace_and_board(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    write_note(root, "bellows", "a", note_text("Bellows A", "quoted", "bellows.iam"))
    client = create_app(root).test_client()
    for folder in ("bellows", "PALP"):
        html = client.get(f"/catalog/{folder}").get_data(as_text=True)
        rail = html.split('data-sourcing-rail>', 1)[1].split('data-note-rail>', 1)[0]
        assert f'href="/sourcing/{folder}"><span>Sourcing <small>' in rail
        assert f'href="/sourcing/{folder}/board">Brainstorm board</a>' in rail
        assert rail.index('Sourcing <small>') < rail.index('Brainstorm board')
    assert "Sourcing <small>· 1</small>" in client.get("/catalog/bellows").get_data(as_text=True)
    assert "Sourcing <small>· 0</small>" in client.get("/catalog/PALP").get_data(as_text=True)
    assert "data-sourcing-rail" not in client.get("/catalog").get_data(as_text=True)


def test_a_file_named_in_for_gets_a_sourced_badge_and_an_inspector_fact(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    write_note(root, "bellows", "a", note_text("Bellows A", "quoted", "bellows.iam"))
    write_note(root, "bellows", "b", note_text("Bellows B", "rejected", "BELLOWS.iam"))
    client = create_app(root).test_client()

    html = client.get("/catalog/bellows").get_data(as_text=True)
    part = client.get("/part/bellows/bellows.iam").get_data(as_text=True)

    def tile(name: str) -> str:
        start = html.rindex('<a class="thumb-tile', 0, html.index(f'href="/part/bellows/{name}"'))
        return html[start : html.index("</a>", start)]

    sourced = tile("bellows.iam")
    assert '<b class="badge badge-sourced" title="Named in a sourcing option">sourced</b>' in sourced
    assert "<div><dt>Sourced</dt><dd>Bellows A; Bellows B</dd></div>" in sourced
    assert "badge-sourced" not in tile("flange.ipt")
    legend = html.split('aria-label="Legend">', 1)[1].split("</section>", 1)[0]
    assert '<b class="badge badge-sourced" title="Named in a sourcing option">sourced</b>' in legend
    assert "<span>2 sourcing options</span>" in part


def test_the_archive_page_groups_compact_options_by_design_folder(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    write_note(root, "bellows", "a", note_text("Bellows A", "ordered", date="2026-09-20"))
    write_note(root, "bellows", "b", note_text("Bellows B", "candidate"))
    write_note(root, "PALP", "c", note_text("Clamp C", "ordered", date="2026-09-22"))
    client = create_app(root).test_client()

    html = client.get("/sourcing").get_data(as_text=True)

    assert html.index("Bellows A") < html.index("Bellows B") < html.index("Clamp C")
    assert '<a class="sourcing-folder" href="/sourcing/PALP"' in html
    assert html.count('class="sourcing-overview-row"') == 3
    assert 'class="markdown-body sourcing-prose"' not in html
    assert 'data-status-filter="ordered" aria-pressed="false"' in html
    assert 'data-status-filter="quoted"' not in html  # no row for an empty status
    assert '>Sourcing</a>' in html.split('<nav class="topnav"', 1)[1].split("</nav>", 1)[0]
    assert 'class="is-current" aria-current="page">Sourcing</a>' in html
    empty = create_app(make_workspace(tmp_path / "empty")).test_client().get("/sourcing")
    assert "No sourcing options yet." in empty.get_data(as_text=True)


def test_the_live_preview_resolves_a_sourcing_folders_attachments(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    attach(root, "bellows", "front.png", PNG)
    client = create_app(root).test_client()

    plain = client.post("/markdown/preview", data={"text": "![f](attachments/front.png)"}).get_json()
    scoped = client.post(
        "/markdown/preview", data={"text": "![[attachments/front.png]]", "sourcing": "bellows"}
    ).get_json()

    assert 'src="attachments/front.png"' in plain["html"]
    assert 'src="/sourcing-file/bellows/sourcing/attachments/front.png?v=' in scoped["html"]


def test_notes_check_reports_a_sourcing_note_with_a_bad_status(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    write_note(root, "bellows", "good", note_text("Good", "received"))
    write_note(root, "bellows", "bad", note_text("Bad", "bought"))
    write_note(root, "bellows", "unfenced", "title: nothing\n")

    findings = check_notes(root).in_category(SOURCING)

    assert [(finding.path, finding.detail.split(":", 1)[0]) for finding in findings] == [
        ("bellows/sourcing/bad.md", "status must be one of"),
        ("bellows/sourcing/unfenced.md", "the file must start with a --- frontmatter fence"),
    ]


def test_the_scanner_never_sees_sourcing_files(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    write_note(root, "bellows", "a", note_text("A", "quoted"))
    attach(root, "bellows", "a.png", PNG)
    attach(root, "bellows", "a.pdf", PDF)
    client = create_app(root).test_client()

    records = client.get("/duplicates/data").get_json()["files"]

    assert sorted(record["path"] for record in records) == [
        "PALP/clamp.ipt",
        "bellows/bellows.iam",
        "bellows/flange.ipt",
    ]


# ---- sourcing in place (0.28.0) -----------------------------------------------


def section(html: str) -> str:
    return html.split('<div class="sourcing-block" id="sourcing">', 1)[1].split('<p class="filter-empty"', 1)[0]


def tile_ids(html: str) -> list[str]:
    return re.findall(r'<a class="thumb-tile sourcing-tile" id="option-([^"]+)"', html)


def test_the_folder_section_shows_the_folders_own_options_as_tiles(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    attach(root, "bellows", "front.png", PNG)
    attach(root, "bellows", "quote.pdf", PDF)
    body = "[quote](attachments/quote.pdf)\n\n![[front.png]]\n\n![missing](attachments/gone.png)"
    write_note(root, "bellows", "a", note_text("Rails A", "quoted", "bellows.iam", body=body))
    write_note(root, "bellows", "b", note_text("Rails B", "candidate", "bellows.iam", "flange.ipt"))
    write_note(root, "PALP", "c", note_text("Clamp", "ordered", "clamp.ipt"))
    client = create_app(root).test_client()

    html = client.get("/catalog/bellows").get_data(as_text=True)
    part = section(html)

    browse = html.split("data-thumb-grid", 1)[1].split("</section>", 1)[0]
    assert browse.index('class="file-block"') < browse.index('id="sourcing"')  # under the files
    assert '<strong>Sourcing</strong> · 2<a class="copy-path" href="/sourcing/bellows/new">Add option</a>' in part
    assert tile_ids(part) == ["a", "b"]  # only this folder's notes
    a = part.split('id="option-a"', 1)[1].split("</a>", 1)[0]
    b = part.split('id="option-b"', 1)[1].split("</a>", 1)[0]
    # The first picture the note links, not its PDF; a note without one gets the placeholder.
    assert '<img src="/sourcing-file/bellows/sourcing/attachments/front.png?v=' in a
    assert '<img src="data:image/svg+xml,' in b
    assert 'href="/sourcing/bellows/a/edit"' in part and 'href="/sourcing/bellows/b/edit"' in part
    assert '<span class="thumb-name">Rails A</span>' in a
    assert '<b class="badge badge-sourcing-quoted" title="Status: quoted">quoted</b>' in a
    assert (
        '<span class="tile-badges sourcing-for"><span class="metadata-chip">bellows.iam</span>'
        '<span class="metadata-chip">flange.ipt</span></span>'
    ) in b
    # The inspector is there to show them; the root page has no section.
    assert "data-inspector" in html
    palp = client.get("/catalog/PALP").get_data(as_text=True)
    assert tile_ids(section(palp)) == ["c"]
    assert 'id="sourcing"' not in client.get("/catalog").get_data(as_text=True)


def test_option_tiles_carry_what_the_inspector_shows(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    text = note_text("Rails A", "quoted", "bellows.iam", "gone.ipt").replace(
        "status:",
        "vendor: Misumi\npart_number: SSEB16\nprice: 6,000 JPY\nurl: https://example.com/rails?a=1&b='2'\nstatus:",
    )
    write_note(root, "bellows", "a", text)
    client = create_app(root).test_client()

    html = client.get("/catalog/bellows").get_data(as_text=True)
    tile = section(html).split('<a class="thumb-tile sourcing-tile"', 1)[1].split(">", 1)[0]
    script = client.get("/static/dedup.js").get_data(as_text=True)

    assert 'data-inspect="sourcing"' in tile and 'data-status="quoted"' in tile
    assert 'data-vendor="Misumi"' in tile and 'data-part-number="SSEB16"' in tile
    assert 'data-price="6,000 JPY"' in tile and 'data-date="2026-09-24"' in tile
    assert 'data-url="https://example.com/rails?a=1&amp;b=&#39;2&#39;"' in tile
    # `for` as JSON in a single-quoted attribute: a file here links to its part
    # page; a name no file carries has no link.
    assert (
        "data-for='[{\"name\": \"bellows.iam\", \"url\": \"/part/bellows/bellows.iam\"}, "
        "{\"name\": \"gone.ipt\", \"url\": \"\"}]'"
    ) in tile
    # The inspector builds the facts from those attributes, the link clickable,
    # and swaps the placement flags for the editor link.
    assert 'tile.dataset.inspect === "sourcing"' in script
    for label in ("Vendor", "Part number", "Price", "Status", "Link", "For"):
        assert f'row("{label}"' in script
    assert 'link.rel = "noopener noreferrer"' in script
    assert "[data-inspector-edit]" in script
    assert "a.thumb-tile:not(.sourcing-tile)" in script  # the file count counts files only
    assert '<a class="copy-path inspector-flag" data-inspector-edit hidden>Edit option</a>' in html


def test_cards_sort_by_status_and_rejected_ones_fold_into_one_row(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    notes = [
        ("cand-old", "candidate", "2026-09-01"),
        ("rej-old", "rejected", "2026-09-02"),
        ("recv", "received", "2026-08-01"),
        ("cand-new", "candidate", "2026-09-20"),
        ("quoted", "quoted", "2026-09-10"),
        ("ordered", "ordered", "2026-09-05"),
        ("rej-new", "rejected", "2026-09-21"),
    ]
    for slug, status, date in notes:
        write_note(root, "bellows", slug, note_text(slug.title(), status, date=date))
    client = create_app(root).test_client()

    part = section(client.get("/catalog/bellows").get_data(as_text=True))
    shown, folded = part.split('<details class="sourcing-rejected" data-sourcing-rejected>', 1)

    assert tile_ids(shown) == ["recv", "ordered", "quoted", "cand-new", "cand-old"]
    assert "<summary>2 rejected</summary>" in folded
    assert tile_ids(folded) == ["rej-new", "rej-old"]
    assert "<details" not in shown
    # No rejected option, no fold.
    fresh = make_workspace(tmp_path / "fresh")
    write_note(fresh, "bellows", "a", note_text("A", "quoted"))
    fresh_page = create_app(fresh).test_client().get("/catalog/bellows").get_data(as_text=True)
    assert "sourcing-rejected" not in fresh_page
    # The walk skips a folded row, and a link to a folded tile opens it.
    script = client.get("/static/dedup.js").get_data(as_text=True)
    assert 'tile.closest("details:not([open])")' in script
    assert 'hash.indexOf("#option-") === 0' in script and "fold.open = true" in script


def test_the_part_page_lists_the_files_options_and_adds_for_it(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    app = create_app(root)
    write_note(root, "bellows", "old", note_text("Old rails", "rejected", "bellows.iam", date="2026-09-01"))
    newer = note_text("New rails", "quoted", "bellows.iam", date="2026-09-20")
    write_note(root, "bellows", "new", newer.replace("status:", "price: 6000\nstatus:"))
    # An option in another folder, for a file that folder does not have.
    write_note(root, "PALP", "far", note_text("Far rails", "ordered", "bellows.iam", date="2026-09-10"))
    write_note(root, "PALP", "near", note_text("Clamp", "candidate", "clamp.ipt"))
    client = app.test_client()

    page = client.get("/part/bellows/bellows.iam").get_data(as_text=True)
    rows = page.split('<ul class="sourcing-rows"', 1)[1].split("</ul>", 1)[0]

    assert re.findall(r'<span class="sourcing-row-title">([^<]+)</span>', rows) == [
        "New rails",
        "Far rails",
        "Old rails",
    ]
    assert (
        '<a href="/sourcing/bellows/new/edit?back=bellows/bellows.iam" title="bellows\\sourcing\\new.md">'
        '<b class="badge badge-sourcing-quoted" title="Status: quoted">quoted</b>'
        '<span class="sourcing-row-title">New rails</span><small>6000</small></a>'
    ) in rows
    assert 'href="/sourcing/PALP/far/edit?back=bellows/bellows.iam"' in rows
    assert "<span>3 sourcing options</span>" in page  # the sourced signal stays
    add = '<a class="copy-path" href="/sourcing/bellows/new?back=bellows/bellows.iam&amp;for=bellows.iam">'
    assert add + "Add option</a>" in page
    # The other folder's note is listed on the file, but not in this folder's section.
    assert tile_ids(section(client.get("/catalog/bellows").get_data(as_text=True))) == ["new", "old"]
    assert tile_ids(section(client.get("/catalog/PALP").get_data(as_text=True))) == ["far", "near"]
    flange = client.get("/part/bellows/flange.ipt").get_data(as_text=True)
    assert "sourcing-rows" not in flange and "for=flange.ipt" in flange

    # Add pre-fills `for`; Save and Cancel go back to the part page.
    form = client.get("/sourcing/bellows/new?back=bellows/bellows.iam&for=bellows.iam").get_data(as_text=True)
    assert 'name="for" value="bellows.iam" checked>' in form
    assert 'name="for" value="flange.ipt">' in form
    assert '<input type="hidden" name="back" value="bellows/bellows.iam">' in form
    assert '<a class="button" data-sourcing-exit href="/part/bellows/bellows.iam">Back to bellows.iam</a>' in form
    assert "Back to bellows.iam" in form
    saved = client.post(
        "/sourcing/bellows/new",
        data={
            "token": app.config["FORM_TOKEN"],
            "title": "Third rails",
            "status": "candidate",
            "for": ["bellows.iam"],
            "back": "bellows/bellows.iam",
        },
    )
    assert saved.status_code == 302
    assert saved.headers["Location"].endswith("/sourcing/bellows/third-rails/edit?saved=1&back=bellows/bellows.iam")
    assert "Saved: Third rails" in client.get(saved.headers["Location"]).get_data(as_text=True)
    # A back path outside the workspace is ignored: the folder's section instead.
    stray = client.get("/sourcing/bellows/new?back=../outside.txt").get_data(as_text=True)
    assert 'name="back"' not in stray
    assert '<a class="button" data-sourcing-exit href="/catalog/bellows#sourcing">Back to catalog</a>' in stray


def test_the_folder_page_opens_its_selected_option_or_new_form(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    write_note(root, "bellows", "a", note_text("A", "quoted"))
    client = create_app(root).test_client()

    plain = client.get("/sourcing/bellows")
    saved = client.get("/sourcing/bellows?saved=a")

    assert plain.status_code == 302 and plain.headers["Location"].endswith("/sourcing/bellows/a/edit")
    assert saved.headers["Location"].endswith("/sourcing/bellows/a/edit")
    assert client.get("/sourcing/PALP").headers["Location"].endswith("/sourcing/PALP/new")
    assert client.get("/sourcing?folder=PALP").headers["Location"].endswith("/sourcing/PALP/new")
    assert client.get("/sourcing/nowhere").status_code == 404
    assert client.get("/sourcing/bellows/sourcing").status_code == 404
    # The editor and the archive-wide list stay.
    assert client.get("/sourcing/bellows/a/edit").status_code == 200
    assert client.get("/sourcing/bellows/new").status_code == 200
    assert client.get("/sourcing").status_code == 200


def test_option_navigation_stays_in_its_folder_and_preserves_part_context(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    write_note(root, "bellows", "a", note_text("First rails", "quoted"))
    write_note(root, "bellows", "b", note_text("Second rails", "candidate"))
    write_note(root, "PALP", "c", note_text("Unrelated clamp", "ordered"))
    client = create_app(root).test_client()
    html = client.get("/sourcing/bellows/a/edit?back=bellows/bellows.iam").get_data(as_text=True)
    nav = html.split('<nav class="sourcing-option-list"', 1)[1].split("</nav>", 1)[0]
    assert "First rails" in nav and "Second rails" in nav and "Unrelated clamp" not in nav
    assert 'href="/sourcing/bellows/b/edit?back=bellows/bellows.iam"' in nav
    assert 'data-sourcing-option aria-current="page"' in nav
    assert 'form="sourcing-form"' in html
    assert 'data-creating="false"' in html
    assert 'data-sourcing-image-dialog' in html


def test_folder_workspace_keeps_broken_notes_reachable_without_replacing_them(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    path = write_note(root, "bellows", "broken", "not frontmatter\n")
    client = create_app(root).test_client()
    response = client.get("/sourcing/bellows", follow_redirects=True)
    assert response.status_code == 200 and "This note does not parse" in response.get_data(as_text=True)
    assert path.read_text(encoding="utf-8") == "not frontmatter\n"
    assert 'form="sourcing-form"' not in response.get_data(as_text=True)


def test_brainstorm_board_is_plain_markdown_and_protects_conflicting_edits(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    app = create_app(root)
    client = app.test_client()
    route = "/sourcing/bellows/board"
    html = client.get(route).get_data(as_text=True)
    revision = re.search(r'name="revision" value="([^"]+)"', html).group(1)
    data = {"token": app.config["FORM_TOKEN"], "revision": revision,
            "body": "# Ideas\n\n[Rail](<https://example.com/a(b)>)\n"}
    assert client.post(route, data={**data, "token": "wrong"}).status_code == 403
    assert client.post(route, data=data, environ_base={"REMOTE_ADDR": "192.0.2.1"}).status_code == 403
    assert client.post(route, data=data).status_code == 302
    board = root / "bellows" / "sourcing" / "_brainstorm.md"
    assert board.read_text(encoding="utf-8") == data["body"]
    assert read_folder_options(root / "bellows", "bellows") == ([], [])
    assert not check_notes(root).in_category(SOURCING)
    assert client.get("/sourcing/bellows").location.endswith("/sourcing/bellows/board")
    saved = client.get(route).get_data(as_text=True)
    assert 'href="https://example.com/a(b)"' in saved
    board.write_text("Changed externally", encoding="utf-8")
    conflict = client.post(route, data=data)
    assert conflict.status_code == 409
    assert "nothing was saved" in conflict.get_data(as_text=True)
    assert board.read_text(encoding="utf-8") == "Changed externally"
    assert client.get("/sourcing").get_data(as_text=True).count('href="/sourcing/bellows/board"') >= 1
    for bad in ("/sourcing/missing/board", "/sourcing/bellows/sourcing/board"):
        assert client.get(bad).status_code == 404


def test_brainstorm_board_renders_local_attachments_without_option_frontmatter(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    attach(root, "bellows", "idea.png", PNG)
    (root / "bellows" / "sourcing" / "_brainstorm.md").write_text(
        "![Idea](attachments/idea.png)\n\n<script>alert(1)</script>", encoding="utf-8")
    client = create_app(root).test_client()
    html = client.get("/sourcing/bellows/board").get_data(as_text=True)
    assert 'src="/sourcing-file/bellows/sourcing/attachments/idea.png?v=' in html
    assert "<script>alert(1)</script>" not in html
    assert read_folder_options(root / "bellows", "bellows") == ([], [])
