import os
import re
import struct
from pathlib import Path

import pytest

import pihti_dedup.web as web
from pihti_dedup import geometry_preview
from pihti_dedup.cleanup import plan_member_cleanup
from pihti_dedup.git_filename_history import FilenameHistory, FilenameOccurrence
from pihti_dedup.git_history import PullRequestMerge
from pihti_dedup.inventor_meta import DocumentMeta, Preview
from pihti_dedup.inventory import scan_workspace
from pihti_dedup.renames import read_ledger
from pihti_dedup.sidecar import read_sidecar
from pihti_dedup.web import create_app


def make_workspace(root: Path) -> Path:
    for folder in ("BoronProbe", "Plasma Vessel"):
        path = root / folder / "parts" / "bearing.ipt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"same bearing")
    collision = root / "BoronProbe_2026" / "parts" / "bearing.ipt"
    collision.parent.mkdir(parents=True, exist_ok=True)
    collision.write_bytes(b"new bearing")
    vendor = root / "bellows" / "Design Data" / "vendor.ipt"
    vendor.parent.mkdir(parents=True, exist_ok=True)
    vendor.write_bytes(b"vendor")
    return root


def scrolling_selectors(style: str) -> list[str]:
    """Selectors of every top-level rule that gives an element a vertical scrollbar."""

    return [
        match.group(1).strip()
        for match in re.finditer(r"(?m)^([^@{}\n][^{}\n]*)\{[^{}]*overflow-y:\s*(?:auto|scroll)", style)
    ]


def test_shell_is_immediate_and_results_are_loaded_separately(tmp_path: Path) -> None:
    client = create_app(make_workspace(tmp_path)).test_client()

    landing = client.get("/")
    assert landing.status_code == 302
    assert landing.headers["Location"].endswith("/catalog")

    shell = client.get("/duplicates")
    html = shell.get_data(as_text=True)
    assert shell.status_code == 200
    assert 'id="dup-results"' in html
    assert 'data-src="/duplicates/results"' in html
    assert "bearing.ipt" not in html
    assert "page-heading" not in html
    assert 'type="image/svg+xml" href="/static/pihtiicon.svg"' in html
    assert 'class="brand" href="/catalog"' in html
    assert (
        html.index(">Catalog</a>")
        < html.index(">Duplicates</a>")
        < html.index(">Doctor</a>")
        < html.index(">Renames</a>")
    )

    favicon = client.get("/static/pihtiicon.svg")
    mkdocs_icon = Path(__file__).resolve().parents[1] / "docs" / "assets" / "pihtiicon.svg"
    assert favicon.status_code == 200
    assert favicon.mimetype == "image/svg+xml"
    assert favicon.data == mkdocs_icon.read_bytes()

    results = client.get("/duplicates/results")
    result_html = results.get_data(as_text=True)
    assert results.status_code == 200
    assert "bearing.ipt" in result_html
    assert "different bytes" in result_html
    assert "data-filter-search" in result_html
    assert "data-include-vendor" in result_html
    assert "Copy paths" not in result_html
    assert result_html.count('data-copy="') == 6
    expected = tmp_path / "BoronProbe_2026" / "parts" / "bearing.ipt"
    assert f'data-copy="{expected}"' in result_html
    assert f'data-copy="{expected.parent}"' in result_html
    assert 'data-copy-kind="file" title="Paste into Inventor\'s File name field"' in result_html
    assert 'data-copy-kind="folder" title="Paste into Inventor\'s address bar"' in result_html
    assert 'data-system-filter="boronprobe_2026"' in result_html
    assert '<time datetime="' in result_html
    assert 'title="Modified time"' in result_html


def test_inventory_cache_survives_restart_and_rehashes_only_changed_files(
    monkeypatch, tmp_path: Path
) -> None:
    root = make_workspace(tmp_path)
    first = web.InventoryCache(root, scan_workspace).get(include_vendor=False)

    assert all(record.sha256 for record in first.records)
    assert (root / ".pihti-dedup" / "inventory-default-v1.json").is_file()

    original = web.sha256_file
    hashed: list[str] = []

    def record_hash(path: Path) -> str:
        hashed.append(path.relative_to(root).as_posix())
        return original(path)

    monkeypatch.setattr(web, "sha256_file", record_hash)
    unchanged = web.InventoryCache(root, scan_workspace).get(include_vendor=False)

    assert unchanged.records == first.records
    assert hashed == []

    changed = root / "BoronProbe_2026" / "parts" / "bearing.ipt"
    changed.write_bytes(b"new bearing revision")
    refreshed = web.InventoryCache(root, scan_workspace).get(include_vendor=False)

    assert len(refreshed.records) == len(first.records)
    assert hashed == ["BoronProbe_2026/parts/bearing.ipt"]


def test_vendor_scope_reuses_default_hashes(monkeypatch, tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    cache = web.InventoryCache(root, scan_workspace)
    cache.get(include_vendor=False)
    original = web.sha256_file
    hashed: list[str] = []

    def record_hash(path: Path) -> str:
        hashed.append(path.relative_to(root).as_posix())
        return original(path)

    monkeypatch.setattr(web, "sha256_file", record_hash)
    vendor = cache.get(include_vendor=True)

    assert len(vendor.records) == 4
    assert hashed == ["bellows/Design Data/vendor.ipt"]


def test_results_offer_recent_pr_merge_as_a_real_filter(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    canonical = root / "ContentCenter" / "parts" / "bearing.ipt"
    canonical.parent.mkdir(parents=True)
    canonical.write_bytes(b"new bearing")
    merge = PullRequestMerge(
        sha="a" * 40,
        number=3,
        branch="queezz/BoronProbe-update",
        paths=frozenset(
            {
                "BoronProbe_2026/parts/bearing.ipt",
                "ContentCenter/parts/bearing.ipt",
            }
        ),
        folders=("BoronProbe_2026", "ContentCenter"),
        added_paths=frozenset({"BoronProbe_2026/parts/bearing.ipt"}),
    )
    client = create_app(root, merge_reader=lambda _root: (merge,)).test_client()

    result_html = client.get("/duplicates/results").get_data(as_text=True)

    assert "PR folder #1, #3" in result_html
    assert "No PR filter" in result_html
    assert "BoronProbe-update" in result_html
    assert 'data-merge-filter="3"' in result_html
    assert 'class="member is-pr-member"' in result_html
    assert "Edited PR #3" in result_html
    assert 'data-merges="3"' in result_html
    assert 'class="rail-side rail-primary"' in result_html
    assert 'class="rail-side rail-secondary"' in result_html
    canonical_href = 'href="/part/ContentCenter/parts/bearing.ipt"'
    canonical_index = result_html.index(canonical_href)
    member_marker = '          <div\n            class="member'
    canonical_start = result_html.rfind(member_marker, 0, canonical_index)
    canonical_end = result_html.find(member_marker, canonical_index)
    canonical_row = result_html[canonical_start:canonical_end]
    assert "pr-badge" not in canonical_row
    assert "pr-touch-badge" in canonical_row
    assert "Edited PR #3" in canonical_row


def test_zero_result_folders_and_merges_remain_visible(tmp_path: Path) -> None:
    merge = PullRequestMerge(
        sha="b" * 40,
        number=2,
        branch="student/new-fixture",
        paths=frozenset({"Unrelated/new-fixture.ipt"}),
        folders=("Unrelated",),
    )
    root = make_workspace(tmp_path)
    extra = root / "NoDuplicates" / "unique.ipt"
    extra.parent.mkdir()
    extra.write_bytes(b"unique")
    client = create_app(root, merge_reader=lambda _root: (merge,)).test_client()

    result_html = client.get("/duplicates/results").get_data(as_text=True)

    assert 'data-system-filter="noduplicates"' in result_html
    assert "NoDuplicates" in result_html
    assert 'data-merge-filter="2"' in result_html
    assert "PR #2" in result_html


def test_json_endpoint_and_vendor_toggle_share_the_inventory_contract(tmp_path: Path) -> None:
    client = create_app(make_workspace(tmp_path)).test_client()

    default = client.get("/duplicates/data").get_json()
    vendor = client.get("/duplicates/data?include_vendor=1").get_json()

    assert default["summary"]["files"] == 3
    assert default["summary"]["collision_groups"] == 1
    assert vendor["summary"]["files"] == 4
    assert vendor["scope"]["include_vendor"] is True


def test_health_names_guarded_quarantine_service(tmp_path: Path) -> None:
    payload = create_app(tmp_path).test_client().get("/health").get_json()

    assert payload["status"] == "ok"
    assert payload["service"] == "pihti-dedup"
    assert payload["read_only"] is False
    assert payload["cleanup_mode"] == "recoverable-quarantine"


def test_packaged_script_contains_filter_and_rescan_behaviour(tmp_path: Path) -> None:
    client = create_app(tmp_path).test_client()
    script = client.get("/static/dedup.js").get_data(as_text=True)

    assert "applyFilters" in script
    assert "include_vendor" in script
    assert "navigator.clipboard.writeText" in script
    assert "data-kind-filter" in script
    assert "data-system-filter" in script
    assert "data-merge-filter" in script
    assert "references_checked" in script
    assert "Apply to quarantine" in script
    assert "data-member-delete" in script
    assert "Move only this file to recoverable quarantine?" in script
    assert "new AbortController()" in script
    assert "operationPending" in script
    assert "new AbortController()" in script
    assert "operationPending" in script
    assert 'FILTER_KEY = "pihti-dedup-filter"' in script
    assert "localStorage.setItem(FILTER_KEY" in script
    assert "captureViewportAnchor" in script
    assert "restoreViewportAnchor" in script
    assert "preserveView: true" in script
    assert "showToast" in script
    assert "updateCardAfterMemberRemoval" in script
    assert "if (hideWholeCard) removeCard(card);" in script


def test_styles_keep_desktop_rail_at_its_initial_top_offset(tmp_path: Path) -> None:
    client = create_app(tmp_path).test_client()
    style = client.get("/static/dedup.css").get_data(as_text=True)

    assert "top: calc(var(--bar-height) + var(--content-pad));" in style
    assert ".summary-strip" not in style
    assert "grid-template-columns: minmax(0, 1fr) 17rem 17rem" in style
    # Only the catalog folder tree may scroll inside its pinned rail card.
    assert scrolling_selectors(style) == [".inspector-facts", ".tree-card .folder-tree"]
    assert ".operation-toast" in style
    assert "#dup-results.is-refreshing { pointer-events: none; }" in style
    assert "opacity: 0.56" not in style
    assert ".operation-notice" not in style
    assert ".note-rendered" in style and "max-width: 82ch" in style
    assert ".markdown-body h1 { font-size: 1.24rem" in style


def test_web_cleanup_previews_then_quarantines_with_local_guard(tmp_path: Path) -> None:
    canonical = tmp_path / "Canonical" / "part.ipt"
    candidate = tmp_path / "Submission" / "part.ipt"
    canonical.parent.mkdir()
    candidate.parent.mkdir()
    canonical.write_bytes(b"same")
    candidate.write_bytes(b"same")
    merge = PullRequestMerge(
        sha="e" * 40,
        number=3,
        branch="student/update",
        paths=frozenset({"Submission/part.ipt"}),
        folders=("Submission",),
        added_paths=frozenset({"Submission/part.ipt"}),
    )
    app = create_app(tmp_path, merge_reader=lambda _root: (merge,))
    client = app.test_client()

    plan_response = client.get("/duplicates/merge-plan/3")
    plan = plan_response.get_json()
    assert plan_response.status_code == 200
    assert plan["dry_run"] is True
    assert plan["summary"]["candidates"] == 1
    assert candidate.exists()

    blocked = client.post(
        "/duplicates/merge-plan/3/apply",
        json={"signature": plan["signature"], "references_checked": True},
        headers={"X-PIHTI-Token": app.config["FORM_TOKEN"]},
        environ_base={"REMOTE_ADDR": "192.0.2.10"},
    )
    assert blocked.status_code == 403
    assert candidate.exists()

    applied = client.post(
        "/duplicates/merge-plan/3/apply",
        json={"signature": plan["signature"], "references_checked": True},
        headers={"X-PIHTI-Token": app.config["FORM_TOKEN"]},
    )

    assert applied.status_code == 200
    payload = applied.get_json()
    assert payload["execution"]["moved"] == ["Submission/part.ipt"]
    assert not candidate.exists()
    assert canonical.exists()
    assert Path(payload["execution"]["manifest"]).exists()

    # The count lives only in the Removed page's History rail, not in the top bar.
    catalog = client.get("/catalog").get_data(as_text=True)
    topbar = catalog.split('<header class="topbar">', 1)[1].split("</header>", 1)[0]
    assert "recoverable" not in topbar and "quarantine empty" not in topbar
    assert "local-tool" not in catalog
    assert '<span class="version">v' in topbar
    removed = client.get("/removed").get_data(as_text=True)
    history = removed.split("<h2>History</h2>", 1)[1].split("</section>", 1)[0]
    assert "<dt>Paths</dt><dd>1</dd>" in history


def test_reviewed_collision_consolidates_to_one_logged_restorable_survivor(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path)
    app = create_app(root)
    client = app.test_client()
    group = next(
        item for item in scan_workspace(root).filename_groups if item.title == "bearing.ipt"
    )
    keep = "BoronProbe_2026/parts/bearing.ipt"

    page = client.get("/duplicates/results").get_data(as_text=True)
    assert page.count("Keep only this") == 3
    assert page.count(">Quarantine this</button>") == 3
    assert "data-consolidate-keep" in page

    applied = client.post(
        f"/duplicates/member/{group.id}/consolidate",
        json={"keep_path": keep, "reviewed": True},
        headers={"X-PIHTI-Token": app.config["FORM_TOKEN"]},
    )

    assert applied.status_code == 200
    assert (root / keep).exists()
    assert not (root / "BoronProbe" / "parts" / "bearing.ipt").exists()
    assert not (root / "Plasma Vessel" / "parts" / "bearing.ipt").exists()
    history = client.get("/removed").get_data(as_text=True)
    assert "Manual Consolidation" in history
    assert "BoronProbe_2026\\parts\\bearing.ipt" in history
    assert "Restore this event" in history
    assert "data-removed-filter" in history
    assert "data-removed-expand" in history
    old_page = client.get("/part/BoronProbe/parts/bearing.ipt")
    assert old_page.status_code == 410
    assert "This file was deliberately consolidated" in old_page.get_data(as_text=True)

    repeated = client.post(
        f"/duplicates/member/{group.id}/consolidate",
        json={"keep_path": keep, "reviewed": True},
        headers={"X-PIHTI-Token": app.config["FORM_TOKEN"]},
    )
    assert repeated.status_code == 200
    assert repeated.get_json()["already_applied"] is True

    manifest = applied.get_json()["execution"]["manifest"]
    restored = client.post(
        "/removed/restore",
        data={"token": app.config["FORM_TOKEN"], "manifest": manifest},
    )
    assert restored.status_code == 302
    assert (root / "BoronProbe" / "parts" / "bearing.ipt").exists()
    assert (root / "Plasma Vessel" / "parts" / "bearing.ipt").exists()


def test_collision_consolidation_requires_local_review_confirmation(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    app = create_app(root)
    client = app.test_client()
    group = next(
        item for item in scan_workspace(root).filename_groups if item.title == "bearing.ipt"
    )
    url = f"/duplicates/member/{group.id}/consolidate"
    headers = {"X-PIHTI-Token": app.config["FORM_TOKEN"]}

    unreviewed = client.post(url, json={"keep_path": group.records[0].path}, headers=headers)
    remote = client.post(
        url,
        json={"keep_path": group.records[0].path, "reviewed": True},
        headers=headers,
        environ_base={"REMOTE_ADDR": "192.0.2.1"},
    )

    assert unreviewed.status_code == 400
    assert remote.status_code == 403
    assert all((root / item.path).exists() for item in group.records)


def test_removed_events_group_into_time_bounded_sessions() -> None:
    events = (
        {"source": "manual-consolidation", "created_at": "2026-08-06T13:24:00+00:00", "files": [{}]},
        {"source": "manual-consolidation", "created_at": "2026-08-06T13:18:00+00:00", "files": [{}, {}]},
        {"source": "manual-consolidation", "created_at": "2026-08-06T12:50:00+00:00", "files": [{}]},
        {"source": "manual-consolidation", "created_at": "2026-08-06T12:49:00+00:00", "restored_at": "2026-08-06T13:00:00+00:00", "files": [{}]},
    )

    batches = web._removed_batches(events)

    assert [len(batch["events"]) for batch in batches] == [2, 1, 1]
    assert batches[0]["files"] == 3
    assert [batch["status"] for batch in batches] == ["recoverable", "recoverable", "restored"]


def test_reviewed_collision_can_quarantine_only_one_revision(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    app = create_app(root)
    client = app.test_client()
    group = next(
        item for item in scan_workspace(root).filename_groups if item.title == "bearing.ipt"
    )
    removed_path = "Plasma Vessel/parts/bearing.ipt"
    plan = plan_member_cleanup(
        scan_workspace(root),
        group_id=group.id,
        path=removed_path,
        allow_collision=True,
    )
    url = f"/duplicates/member/{group.id}/delete"
    payload = {
        "path": removed_path,
        "signature": plan.signature,
        "references_checked": True,
    }
    headers = {"X-PIHTI-Token": app.config["FORM_TOKEN"]}

    unreviewed = client.post(url, json=payload, headers=headers)
    assert unreviewed.status_code == 400

    applied = client.post(url, json={**payload, "reviewed": True}, headers=headers)

    assert applied.status_code == 200
    assert not (root / removed_path).exists()
    assert (root / "BoronProbe/parts/bearing.ipt").exists()
    assert (root / "BoronProbe_2026/parts/bearing.ipt").exists()
    history = client.get("/removed").get_data(as_text=True)
    assert "Plasma Vessel\\parts\\bearing.ipt" in history
    assert "BoronProbe\\parts\\bearing.ipt" in history
    assert "BoronProbe_2026\\parts\\bearing.ipt" in history

    repeated = client.post(url, json={**payload, "reviewed": True}, headers=headers)
    assert repeated.status_code == 200
    assert repeated.get_json()["already_applied"] is True


def test_member_cleanup_reuses_inventory_hashes_and_defers_rescan(
    monkeypatch, tmp_path: Path
) -> None:
    root = make_workspace(tmp_path)
    app = create_app(root)
    client = app.test_client()
    client.get("/duplicates/results")  # Prime the disk-aware inventory cache.
    inventory = scan_workspace(root)
    group = next(item for item in inventory.filename_groups if item.title == "bearing.ipt")
    removed_path = "Plasma Vessel/parts/bearing.ipt"
    plan = plan_member_cleanup(
        inventory,
        group_id=group.id,
        path=removed_path,
        allow_collision=True,
    )
    hashed: list[Path] = []
    original_sha256 = web.sha256_file

    def tracked_sha256(path: Path) -> str:
        hashed.append(path)
        return original_sha256(path)

    monkeypatch.setattr(web, "sha256_file", tracked_sha256)
    response = client.post(
        f"/duplicates/member/{group.id}/delete",
        json={
            "path": removed_path,
            "signature": plan.signature,
            "references_checked": True,
            "reviewed": True,
        },
        headers={"X-PIHTI-Token": app.config["FORM_TOKEN"]},
    )

    assert response.status_code == 200
    assert response.get_json()["rescan_pending"] is True
    assert hashed == []


def test_newver_pair_is_characterized_and_offers_confirmed_member_delete(
    tmp_path: Path,
) -> None:
    base = tmp_path / "Parts" / "Part5.ipt"
    artifact = tmp_path / "Parts" / "Part5.newVer.ipt"
    base.parent.mkdir()
    base.write_bytes(b"same")
    artifact.write_bytes(b"same")
    stamp = 1_750_458_966_208_000_000
    os.utime(base, ns=(stamp, stamp))
    os.utime(artifact, ns=(stamp, stamp))
    inventory = scan_workspace(tmp_path)
    group = inventory.renamed_groups[0]
    plan = plan_member_cleanup(inventory, group_id=group.id, path="Parts/Part5.newVer.ipt")
    app = create_app(tmp_path)
    client = app.test_client()

    result_html = client.get("/duplicates/results").get_data(as_text=True)
    assert "newVer pair — identical bytes" in result_html
    assert "same bytes and modified time; origin unproven" in result_html
    assert result_html.count("data-member-delete") == 2
    assert 'data-display-path="Parts\\Part5.newVer.ipt"' in result_html

    unconfirmed = client.post(
        f"/duplicates/member/{group.id}/delete",
        json={"path": plan.candidate.path, "signature": plan.signature},
        headers={"X-PIHTI-Token": app.config["FORM_TOKEN"]},
    )
    assert unconfirmed.status_code == 400
    assert artifact.exists()

    applied = client.post(
        f"/duplicates/member/{group.id}/delete",
        json={
            "path": plan.candidate.path,
            "signature": plan.signature,
            "references_checked": True,
        },
        headers={"X-PIHTI-Token": app.config["FORM_TOKEN"]},
    )

    assert applied.status_code == 200
    assert not artifact.exists()
    assert base.exists()
    payload = applied.get_json()
    assert payload["execution"]["moved"] == ["Parts/Part5.newVer.ipt"]
    assert Path(payload["execution"]["manifest"]).exists()


def make_document(**fields) -> DocumentMeta:
    return DocumentMeta(path="stub", ok=True, fields=fields)


def test_duplicate_rows_show_a_preview_and_link_to_the_part_page(tmp_path: Path) -> None:
    client = create_app(make_workspace(tmp_path)).test_client()

    result_html = client.get("/duplicates/results").get_data(as_text=True)

    assert result_html.count('class="member-thumb"') == 3
    assert 'src="/preview/BoronProbe_2026/parts/bearing.ipt?v=' in result_html
    assert 'href="/part/BoronProbe_2026/parts/bearing.ipt"' in result_html
    assert 'loading="lazy"' in result_html


def test_preview_serves_the_embedded_image_with_a_content_type_from_magic(
    tmp_path: Path, monkeypatch
) -> None:
    png = b"\x89PNG\r\n\x1a\n" + b"body bytes"
    monkeypatch.setattr(web, "read_preview", lambda _path: Preview(data=png, image_format="png"))
    client = create_app(make_workspace(tmp_path)).test_client()

    response = client.get("/preview/BoronProbe/parts/bearing.ipt")

    assert response.status_code == 200
    assert response.mimetype == "image/png"
    assert response.get_data() == png


def test_preview_falls_back_to_a_neutral_placeholder(tmp_path: Path) -> None:
    client = create_app(make_workspace(tmp_path)).test_client()

    response = client.get("/preview/BoronProbe/parts/bearing.ipt")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert response.mimetype == "image/svg+xml"
    assert "No embedded preview" in body
    assert ">IPT<" in body


def test_preview_and_part_reject_traversal_and_unknown_paths(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-secret.ipt"
    outside.write_bytes(b"not in the workspace")
    client = create_app(make_workspace(tmp_path)).test_client()

    assert client.get("/preview/BoronProbe/parts/absent.ipt").status_code == 404
    assert client.get("/preview/..%2Foutside-secret.ipt").status_code == 404
    assert client.get("/preview/..%2F..%2FWindows%2Fwin.ini").status_code == 404
    assert client.get("/preview/C:%5CWindows%5Cwin.ini").status_code == 404
    assert client.get("/part/..%2Foutside-secret.ipt").status_code == 404


def binary_stl(path: Path, triangles) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(b"\0" * 80)
        handle.write(struct.pack("<I", len(triangles)))
        for triangle in triangles:
            handle.write(struct.pack("<3f", 0, 0, 1))
            for vertex in triangle:
                handle.write(struct.pack("<3f", *vertex))
            handle.write(b"\0\0")
    return path


def make_export_workspace(root: Path) -> Path:
    """One STL export beside one Inventor part, in the same folder."""

    binary_stl(
        root / "BoronProbe" / "exports" / "head.stl",
        [
            [(0, 0, 0), (10, 0, 0), (0, 10, 0)],
            [(0, 0, 0), (10, 0, 0), (0, 0, 10)],
            [(0, 0, 0), (0, 10, 0), (0, 0, 10)],
            [(10, 0, 0), (0, 10, 0), (0, 0, 10)],
        ],
    )
    (root / "BoronProbe" / "exports" / "head.ipt").write_bytes(b"not really an ipt")
    return root


def test_an_stl_export_is_rendered_and_served_as_png(tmp_path: Path) -> None:
    if ".stl" not in geometry_preview.available_extensions():
        pytest.skip("the 'preview' extra is not installed")
    root = make_export_workspace(tmp_path)
    client = create_app(root).test_client()

    response = client.get("/preview/BoronProbe/exports/head.stl")

    assert response.status_code == 200
    assert response.mimetype == "image/png"
    assert response.get_data()[:8] == b"\x89PNG\r\n\x1a\n"
    # The render landed in the gitignored on-disk cache, sharded.
    stored = list((root / ".pihti-dedup" / "previews").rglob("*.png"))
    assert len(stored) == 1
    assert stored[0].read_bytes() == response.get_data()


def test_the_part_page_and_catalog_show_the_rendered_export(tmp_path: Path) -> None:
    root = make_export_workspace(tmp_path)
    client = create_app(root).test_client()

    part = client.get("/part/BoronProbe/exports/head.stl").get_data(as_text=True)
    catalog = client.get("/catalog/BoronProbe/exports").get_data(as_text=True)

    assert 'src="/preview/BoronProbe/exports/head.stl?v=' in part
    assert "rendered from the geometry" in part
    assert 'src="/preview/BoronProbe/exports/head.stl?v=' in catalog
    assert "head.stl" in catalog


def test_a_missing_preview_extra_falls_back_to_the_placeholder(monkeypatch, tmp_path: Path) -> None:
    root = make_export_workspace(tmp_path)
    monkeypatch.setattr(geometry_preview, "available_extensions", frozenset)
    client = create_app(root).test_client()

    response = client.get("/preview/BoronProbe/exports/head.stl")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert response.mimetype == "image/svg+xml"
    assert ">STL<" in body
    assert not (root / ".pihti-dedup").exists()


def test_previews_are_exempt_from_no_store_and_revalidate_by_etag(tmp_path: Path) -> None:
    root = make_export_workspace(tmp_path)
    client = create_app(root).test_client()

    page = client.get("/duplicates")
    first = client.get("/preview/BoronProbe/exports/head.stl")
    again = client.get(
        "/preview/BoronProbe/exports/head.stl", headers={"If-None-Match": first.headers["ETag"]}
    )

    assert page.headers["Cache-Control"] == "no-store"
    assert "no-store" not in first.headers["Cache-Control"]
    assert "no-cache" in first.headers["Cache-Control"]
    assert first.headers["ETag"] and first.headers["Last-Modified"]
    assert again.status_code == 304
    assert again.get_data() == b""


def test_a_resaved_file_gets_a_new_validator_so_the_browser_refetches(tmp_path: Path) -> None:
    root = make_export_workspace(tmp_path)
    target = root / "BoronProbe" / "exports" / "head.stl"
    client = create_app(root).test_client()
    before = client.get("/preview/BoronProbe/exports/head.stl").headers["ETag"]

    stamp = target.stat().st_mtime_ns + 2_000_000_000
    os.utime(target, ns=(stamp, stamp))

    assert client.get("/preview/BoronProbe/exports/head.stl").headers["ETag"] != before


def test_a_versioned_preview_url_is_immutable_only_while_it_names_the_current_file(
    tmp_path: Path, monkeypatch
) -> None:
    png = b"\x89PNG\r\n\x1a\n" + b"body bytes"
    monkeypatch.setattr(web, "read_preview", lambda _path: Preview(data=png, image_format="png"))
    root = make_workspace(tmp_path)
    target = root / "BoronProbe" / "parts" / "bearing.ipt"
    client = create_app(root).test_client()
    stat = target.stat()
    current = web.preview_version(stat.st_mtime_ns, stat.st_size)
    url = "/preview/BoronProbe/parts/bearing.ipt"

    right = client.get(f"{url}?v={current}")
    wrong = client.get(f"{url}?v=0-0-r0")
    bare = client.get(url)

    assert right.status_code == 200 and right.get_data() == png
    assert right.headers["Cache-Control"] == "private, max-age=31536000, immutable"
    assert right.headers["ETag"] and right.headers["Last-Modified"]
    for response in (wrong, bare):
        assert "immutable" not in response.headers["Cache-Control"]
        assert "no-cache" in response.headers["Cache-Control"]

    # A resave changes the key: the old URL degrades to revalidation, and the
    # page renders the new key.
    stamp = stat.st_mtime_ns + 2_000_000_000
    os.utime(target, ns=(stamp, stamp))
    stale = client.get(f"{url}?v={current}")
    assert "no-cache" in stale.headers["Cache-Control"]
    html = client.get("/catalog/BoronProbe/parts").get_data(as_text=True)
    assert f'src="{url}?v={web.preview_version(stamp, stat.st_size)}"' in html


def test_a_placeholder_is_never_promised_immutable(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    stat = (root / "BoronProbe" / "parts" / "bearing.ipt").stat()
    key = web.preview_version(stat.st_mtime_ns, stat.st_size)
    client = create_app(root).test_client()

    response = client.get(f"/preview/BoronProbe/parts/bearing.ipt?v={key}")

    assert response.mimetype == "image/svg+xml"
    assert "immutable" not in response.headers["Cache-Control"]
    assert "no-cache" in response.headers["Cache-Control"]


def test_every_rendered_preview_src_carries_a_version_key(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    assembly = root / "Assembly" / "Fixture.iam"
    assembly.parent.mkdir()
    assembly.write_bytes(assembly_bytes("bearing.ipt"))
    client = create_app(root).test_client()

    pages = [
        client.get(url).get_data(as_text=True)
        for url in (
            "/catalog",
            "/catalog/BoronProbe",
            "/catalog/BoronProbe/parts",
            "/catalog?q=bearing",
            "/part/BoronProbe/parts/bearing.ipt",
            "/duplicates/results",
            "/doctor",
            "/doctor/name/bearing.ipt",
            "/doctor/assembly/Assembly/Fixture.iam",
        )
    ]

    sources = [src for html in pages for src in re.findall(r'src="(/preview/[^"]*)"', html)]
    assert sources
    assert all(re.search(r"\?v=[0-9a-f]+-[0-9a-f]+-r\d+$", src) for src in sources), sources


def test_plain_catalog_pages_are_briefly_cacheable_for_hover_prefetch(tmp_path: Path) -> None:
    client = create_app(make_workspace(tmp_path)).test_client()

    assert client.get("/catalog").headers["Cache-Control"] == "private, max-age=5"
    assert client.get("/catalog/BoronProbe/parts").headers["Cache-Control"] == "private, max-age=5"
    assert client.get("/catalog?q=bearing").headers["Cache-Control"] == "no-store"
    assert client.get("/catalog/BoronProbe/parts?saved=1").headers["Cache-Control"] == "no-store"
    assert client.get("/catalog/not-there").headers["Cache-Control"] == "no-store"
    assert client.get("/part/BoronProbe/parts/bearing.ipt").headers["Cache-Control"] == "no-store"
    assert client.get("/doctor").headers["Cache-Control"] == "no-store"

    script = client.get("/static/dedup.js").get_data(as_text=True)
    assert 'credentials: "same-origin"' in script
    assert ".folder-tree a.tree-name, .breadcrumbs a, a.folder-card" in script
    assert "var DELAY = 100;" in script


def test_duplicate_rows_offer_rename_only_for_the_four_inventor_extensions(tmp_path: Path) -> None:
    root = tmp_path
    binary_stl(root / "A" / "head.stl", [[(0, 0, 0), (1, 0, 0), (0, 1, 0)]])
    binary_stl(root / "B" / "head.stl", [[(0, 0, 0), (1, 0, 0), (0, 1, 0)]])
    (root / "A" / "head.ipt").write_bytes(b"same")
    (root / "B" / "head.ipt").write_bytes(b"same")
    client = create_app(root).test_client()

    html = client.get("/duplicates/results").get_data(as_text=True)

    # Every member row carries a preview, including the two STL exports...
    assert html.count('class="member-thumb"') == 4
    assert 'src="/preview/A/head.stl?v=' in html
    # ...but only the Inventor documents can be renamed through the ledger flow.
    assert html.count(">Rename<") == 2
    assert "/part/A/head.stl#rename" not in html


def test_catalog_browses_one_folder_level_at_a_time(tmp_path: Path) -> None:
    client = create_app(make_workspace(tmp_path)).test_client()

    landing = client.get("/catalog").get_data(as_text=True)
    system = client.get("/catalog/BoronProbe").get_data(as_text=True)
    folder = client.get("/catalog/BoronProbe/parts").get_data(as_text=True)

    assert 'href="/catalog/BoronProbe"' in landing
    assert 'href="/catalog/Plasma%20Vessel"' in landing
    # Deeper files appear only as a folder card's thumbnail strip, never as tiles.
    assert 'href="/part/BoronProbe/parts/bearing.ipt"' not in landing
    assert landing.count('class="thumb-tile"') == 0
    assert 'href="/catalog/BoronProbe/parts"' in system
    assert 'href="/part/BoronProbe/parts/bearing.ipt"' not in system
    assert system.count('class="thumb-tile"') == 0
    assert 'href="/part/BoronProbe/parts/bearing.ipt"' in folder
    assert 'src="/preview/BoronProbe/parts/bearing.ipt?v=' in folder
    assert folder.count('class="thumb-tile"') == 1
    assert "Design Data" not in landing
    assert 'class="work-grid catalog-grid"' in landing
    assert client.get("/catalog/not-there").status_code == 404
    assert client.get("/catalog/..%2Foutside").status_code == 404

    vendor = client.get("/catalog/bellows/Design%20Data?include_vendor=1").get_data(as_text=True)
    assert 'href="/catalog/bellows?include_vendor=1"' in vendor
    assert 'href="/part/bellows/Design%20Data/vendor.ipt"' in vendor


def test_catalog_search_and_large_folders_reveal_bounded_batches(tmp_path: Path) -> None:
    bulk = tmp_path / "3D-printing"
    bulk.mkdir()
    for index in range(55):
        (bulk / f"fixture-{index:02}.stl").write_bytes(str(index).encode())
    client = create_app(tmp_path).test_client()

    first = client.get("/catalog/3D-printing").get_data(as_text=True)
    more = client.get("/catalog/3D-printing?show=96").get_data(as_text=True)
    search = client.get("/catalog?q=fixture-0").get_data(as_text=True)

    assert first.count('class="thumb-tile"') == 48
    assert "7 still hidden" in first
    assert "Show 48 more" in first
    assert more.count('class="thumb-tile"') == 55
    assert "still hidden" not in more
    assert search.count('class="thumb-tile"') == 10
    assert "Global results" in search


def test_catalog_promotes_sidecar_prose_status_material_and_tags(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    companion = root / "BoronProbe" / "parts" / "bearing.ipt.md"
    companion.write_text(
        "---\n"
        "part_number: BRG-17\n"
        "material: PAEK resin\n"
        "status: manufactured\n"
        "tags: [probe, bearing]\n"
        "supersedes: ''\n"
        "seeded_from_iproperties: 2026-08-06\n"
        "---\n\n"
        "Carries the rotating probe through the vacuum boundary.\n",
        encoding="utf-8",
    )
    client = create_app(root).test_client()

    html = client.get("/catalog/BoronProbe/parts").get_data(as_text=True)

    assert 'class="thumb-tile has-metadata has-story"' in html
    assert "Carries the rotating probe through the vacuum boundary." in html
    assert 'class="metadata-chip status-manufactured">manufactured</b>' in html
    assert 'class="metadata-chip">PAEK resin</span>' in html
    assert 'class="metadata-chip">PN BRG-17</span>' in html
    assert "#probe" in html and "#bearing" in html
    assert 'class="metadata-source">documented</span>' in html


def test_catalog_uses_useful_iproperties_when_no_sidecar_exists(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        web,
        "read_inventor_document",
        lambda _path: make_document(
            part_number="BRG-17",
            description="Radial bearing carrier for the probe head.",
            material="Stainless Steel",
        ),
    )
    client = create_app(make_workspace(tmp_path)).test_client()

    html = client.get("/catalog/BoronProbe/parts").get_data(as_text=True)

    assert 'class="thumb-tile has-metadata has-story"' in html
    assert "Radial bearing carrier for the probe head." in html
    assert "Stainless Steel" in html
    assert "PN BRG-17" in html
    assert "documented" not in html


def test_catalog_iproperties_are_cached_until_the_cad_file_changes(
    tmp_path: Path, monkeypatch
) -> None:
    calls: list[str] = []

    def metadata(path: Path) -> DocumentMeta:
        calls.append(path.name)
        return make_document(description="Cached catalog description.")

    monkeypatch.setattr(web, "read_inventor_document", metadata)
    root = make_workspace(tmp_path)
    app = create_app(root)
    client = app.test_client()

    client.get("/catalog/BoronProbe/parts")
    client.get("/catalog/BoronProbe/parts")
    assert calls == ["bearing.ipt"]

    target = root / "BoronProbe" / "parts" / "bearing.ipt"
    target.write_bytes(b"changed bearing metadata source")
    client.get("/catalog/BoronProbe/parts")

    assert calls == ["bearing.ipt", "bearing.ipt"]


def test_catalog_root_and_folder_cards_promote_readme_summaries(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    (root / "README.md").write_text(
        "# Archive\n\nCurated plasma hardware from concept through fabrication\noutputs.\n",
        encoding="utf-8",
    )
    (root / "Plasma Vessel" / "README.md").write_text(
        "# Plasma Vessel\n\nHolds the plasma box inside the full vacuum vessel assembly.\n",
        encoding="utf-8",
    )
    client = create_app(root).test_client()

    landing = client.get("/catalog").get_data(as_text=True)
    folder = client.get("/catalog/Plasma%20Vessel").get_data(as_text=True)

    assert '<p class="catalog-description">Curated plasma hardware from concept through fabrication outputs.</p>' in landing
    assert 'class="folder-card has-summary" href="/catalog/Plasma%20Vessel"' in landing
    assert 'class="folder-summary">Holds the plasma box inside the full vacuum vessel assembly.</small>' in landing
    rail_note = folder.split('<div class="note-rail-body markdown-body" data-note-rail-body>', 1)[1]
    assert rail_note.startswith("<p>Holds the plasma box inside the full vacuum vessel assembly.</p>")


def test_part_page_shows_iproperties_and_flags_a_part_number_mismatch(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        web,
        "read_inventor_document",
        lambda _path: make_document(
            part_number="UFC-152",
            description="Rotating feedthrough body",
            material="Stainless Steel",
            designer="zetsu",
            mass=32.07,
            volume=4.008,
            density=8.0,
            valid_massprops=17,
        ),
    )
    client = create_app(make_workspace(tmp_path)).test_client()

    html = client.get("/part/BoronProbe/parts/bearing.ipt").get_data(as_text=True)

    assert "Part Number differs from the filename" in html
    assert "UFC-152" in html
    assert "Rotating feedthrough body" in html
    assert "Stainless Steel" in html
    assert "32.0700 g" in html
    assert "8.0000 g/cm" in html
    assert "BoronProbe\\parts\\bearing.ipt" in html
    assert "Create metadata" in html


def test_part_page_withholds_mass_when_inventor_did_not_flag_it_valid(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        web,
        "read_inventor_document",
        lambda _path: make_document(part_number="bearing", mass=32.07, valid_massprops=0),
    )
    client = create_app(make_workspace(tmp_path)).test_client()

    html = client.get("/part/BoronProbe/parts/bearing.ipt").get_data(as_text=True)

    assert "Mass properties are withheld" in html
    assert "32.07" not in html
    assert "Part Number differs" not in html


def test_metadata_sidecar_is_seeded_then_edited_through_the_part_page(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        web,
        "read_inventor_document",
        lambda _path: make_document(part_number="bearing", material="PAEK resin"),
    )
    app = create_app(make_workspace(tmp_path))
    client = app.test_client()
    companion = tmp_path / "BoronProbe" / "parts" / "bearing.ipt.md"

    created = client.post(
        "/part/BoronProbe/parts/bearing.ipt/metadata",
        data={"action": "create", "token": app.config["FORM_TOKEN"]},
    )

    assert created.status_code == 302
    assert companion.exists()
    seeded = read_sidecar(companion)
    assert seeded is not None
    assert seeded.frontmatter["part_number"] == "bearing"
    assert seeded.frontmatter["material"] == "PAEK resin"
    assert seeded.body == ""

    page = client.get("/part/BoronProbe/parts/bearing.ipt?saved=1").get_data(as_text=True)
    assert "Sidecar saved." in page
    assert "bearing.ipt.md" in page
    assert "Create metadata" not in page

    edited = companion.read_text(encoding="utf-8").replace("status: ''", "status: draft")
    saved = client.post(
        "/part/BoronProbe/parts/bearing.ipt/metadata",
        data={"action": "save", "token": app.config["FORM_TOKEN"], "text": edited + "\nWhy.\n"},
    )

    assert saved.status_code == 302
    reread = read_sidecar(companion)
    assert reread is not None
    assert reread.status == "draft"
    assert reread.body.strip() == "Why."


def test_invalid_sidecar_text_is_refused_and_the_file_is_untouched(tmp_path: Path) -> None:
    app = create_app(make_workspace(tmp_path))
    client = app.test_client()
    companion = tmp_path / "BoronProbe" / "parts" / "bearing.ipt.md"
    companion.write_text("---\nstatus: draft\n---\n\nKeep me.\n", encoding="utf-8")

    rejected = client.post(
        "/part/BoronProbe/parts/bearing.ipt/metadata",
        data={
            "action": "save",
            "token": app.config["FORM_TOKEN"],
            "text": "---\nstatus: shipped\n---\n",
        },
    )

    assert rejected.status_code == 400
    assert "status must be empty or one of" in rejected.get_data(as_text=True)
    assert companion.read_text(encoding="utf-8") == "---\nstatus: draft\n---\n\nKeep me.\n"


def test_metadata_writes_keep_the_localhost_and_token_guard(tmp_path: Path) -> None:
    app = create_app(make_workspace(tmp_path))
    client = app.test_client()
    companion = tmp_path / "BoronProbe" / "parts" / "bearing.ipt.md"

    remote = client.post(
        "/part/BoronProbe/parts/bearing.ipt/metadata",
        data={"action": "create", "token": app.config["FORM_TOKEN"]},
        environ_base={"REMOTE_ADDR": "192.0.2.10"},
    )
    untokened = client.post(
        "/part/BoronProbe/parts/bearing.ipt/metadata",
        data={"action": "create", "token": "guessed"},
    )

    assert remote.status_code == 403
    assert untokened.status_code == 403
    assert not companion.exists()


def test_catalog_search_is_a_server_route_not_a_full_page_client_filter(tmp_path: Path) -> None:
    client = create_app(make_workspace(tmp_path)).test_client()
    page = client.get("/catalog?q=Plasma").get_data(as_text=True)
    script = client.get("/static/dedup.js").get_data(as_text=True)

    assert 'action="/catalog"' in page
    assert 'name="q" value="Plasma"' in page
    assert 'href="/part/Plasma%20Vessel/parts/bearing.ipt"' in page
    assert 'href="/part/BoronProbe/parts/bearing.ipt"' not in page
    assert "filterCatalog" not in script
    assert "data-catalog-item" not in script


def assembly_bytes(*stored_paths: str) -> bytes:
    payload = bytearray(b"\xde\xad" * 4)
    for stored in stored_paths:
        payload += b"\x00\x00" + stored.encode("utf-16-le") + b"\x00\x00"
    return bytes(payload)


def make_rename_workspace(root: Path) -> Path:
    """One uniquely named part, one assembly that refers to it by filename."""

    parts = root / "BoronProbe" / "parts"
    parts.mkdir(parents=True)
    (parts / "spacer.ipt").write_bytes(b"geometry")
    (root / "BoronProbe" / "probe.iam").write_bytes(assembly_bytes("parts\\spacer.ipt"))
    return root


def test_catalog_right_rail_holds_only_the_collapsible_folder_tree(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    (root / "BoronProbe" / "drawings").mkdir()
    (root / "BoronProbe" / "drawings" / "bearing.idw").write_bytes(b"drawing")
    client = create_app(root).test_client()

    landing = client.get("/catalog").get_data(as_text=True)
    current = client.get("/catalog/BoronProbe/parts").get_data(as_text=True)
    context = landing.split('<aside class="rail-side rail-context"', 1)[1].split("</aside>", 1)[0]
    tree_rail = landing.split('<aside class="rail-side rail-tree"', 1)[1].split("</aside>", 1)[0]

    # The workspace counts moved out of the tree rail into the context rail.
    assert tree_rail.count('class="rail-card') == 1
    assert ">Folders</h2>" in tree_rail and "data-folder-tree" in tree_rail
    assert "<h2>Catalog</h2>" not in landing
    assert "<dt>CAD files</dt><dd>4</dd>" in context
    assert "<dt>Folders</dt>" in context
    assert "data-folder-tree" in landing
    # The two BoronProbe subfolders collapse under one top-level node carrying both.
    assert 'data-tree-toggle="BoronProbe" aria-expanded="false"' in landing
    assert 'data-tree-children="BoronProbe" hidden' in landing
    # Navigating opens only the current ancestry and marks the leaf.
    assert 'data-tree-toggle="BoronProbe" aria-expanded="true"' in current
    assert 'data-tree-children="BoronProbe">' in current
    assert 'href="/catalog/BoronProbe/parts" title="BoronProbe\\parts" aria-current="page"' in current
    assert "rail-navrow" not in landing


def test_folder_cards_carry_a_thumbnail_strip_from_the_subtree_inventor_first(
    tmp_path: Path,
) -> None:
    root = tmp_path
    exports = root / "Box" / "a-exports"
    exports.mkdir(parents=True)
    for index in range(3):
        (exports / f"early-{index}.stl").write_bytes(b"mesh %d" % index)
    deep = root / "Box" / "z-deep" / "inner"
    deep.mkdir(parents=True)
    for index in range(8):
        (deep / f"part-{index}.ipt").write_bytes(b"part %d" % index)
    (root / "Box" / "direct.ipt").write_bytes(b"direct")
    client = create_app(root).test_client()

    html = client.get("/catalog").get_data(as_text=True)
    card = html.split('class="folder-card" href="/catalog/Box"', 1)[1].split("</a>", 1)[0]
    strip = re.findall(r'src="/preview/([^"?]+)\?v=', card)

    # Six images from the whole subtree, Inventor documents only: each round
    # takes one from each subfolder that has one, then one direct file; the
    # three earlier meshes would only top up a short strip.
    assert strip == ["Box/z-deep/inner/part-0.ipt", "Box/direct.ipt"] + [
        f"Box/z-deep/inner/part-{index}.ipt" for index in range(1, 5)
    ]
    assert ">Box</strong>" in card
    assert "<b>12</b> files" in card
    assert 'class="folder-strip-empty"' not in card

    inner = client.get("/catalog/Box").get_data(as_text=True)
    exports_card = inner.split('href="/catalog/Box/a-exports"', 1)[1].split("</a>", 1)[0]
    assert re.findall(r'src="/preview/([^"?]+)\?v=', exports_card) == [
        f"Box/a-exports/early-{index}.stl" for index in range(3)
    ]
    assert exports_card.count('class="folder-strip-empty"') == 3
    # Folder cards lead in a grid of their own; files follow in a separate grid
    # under their own compact count line, so one never reflows the other.
    folders = inner.split('<div class="folder-grid">', 1)[1].split('<div class="file-block">', 1)[0]
    file_block = inner.split('<div class="file-block">', 1)[1]
    assert folders.count('<a class="folder-card') == 2 and "thumb-tile" not in folders
    assert '<a class="folder-card' not in file_block.split("</section>", 1)[0]
    assert '<p class="grid-label"><strong>Files</strong> · <span data-filter-count data-total="1">1</span></p>' in file_block
    assert file_block.count('class="thumb-tile"') == 1
    assert "folder-glyph" not in inner
    # A leaf folder has no folder grid, a folder with only subfolders no file grid.
    leaf = client.get("/catalog/Box/a-exports").get_data(as_text=True)
    assert 'class="folder-grid"' not in leaf and 'class="file-block"' in leaf
    only_folders = client.get("/catalog/Box/z-deep").get_data(as_text=True)
    assert 'class="folder-grid"' in only_folders and 'class="file-block"' not in only_folders


def test_tiles_carry_hidden_details_only_when_there_is_something_to_add(
    tmp_path: Path, monkeypatch
) -> None:
    def metadata(path: Path) -> DocumentMeta:
        if path.name == "spacer.ipt":
            return make_document(
                description="Keeps the probe head off the flange.",
                material="Generic",
                mass=12.5,
                valid_massprops=17,
            )
        return make_document()

    monkeypatch.setattr(web, "read_inventor_document", metadata)
    root = make_rename_workspace(tmp_path)
    (root / "BoronProbe" / "parts" / "washer.ipt").write_bytes(b"plain")
    client = create_app(root).test_client()

    html = client.get("/catalog/BoronProbe/parts").get_data(as_text=True)
    spacer = html.split('href="/part/BoronProbe/parts/spacer.ipt"', 1)[1].split("</a>", 1)[0]
    washer = html.split('href="/part/BoronProbe/parts/washer.ipt"', 1)[1].split("</a>", 1)[0]
    details = spacer.split('<dl class="thumb-details" hidden>', 1)[1].split("</dl>", 1)[0]

    assert "<dt>Description</dt><dd>Keeps the probe head off the flange.</dd>" in details
    assert "<dt>Mass</dt><dd>12.5 g</dd>" in details
    assert "<dt>Modified</dt>" in details
    assert "<dt>Material</dt>" not in details  # "Generic" says nothing
    assert "<dt>Used in</dt>" in details
    assert '<li title="BoronProbe\\probe.iam">probe.iam</li>' in details
    assert "thumb-details" not in washer

    script = client.get("/static/dedup.js").get_data(as_text=True)
    assert 'querySelector(".thumb-details")' in script
    assert 'image.style.maxWidth = natural ? natural / ratio + "px"' in script  # never upscaled


def test_tiles_signal_copies_and_names_by_colour_with_a_legend(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    older = root / "BoronProbe" / "parts" / "bearing.ipt"
    newer = root / "BoronProbe_2026" / "parts" / "bearing.ipt"
    os.utime(older, ns=(1_700_000_000_000_000_000, 1_700_000_000_000_000_000))
    os.utime(newer, ns=(1_800_000_000_000_000_000, 1_800_000_000_000_000_000))
    (root / "BoronProbe" / "parts" / "Part1.ipt").write_bytes(b"generic geometry")
    (root / "BoronProbe" / "parts" / "clean.ipt").write_bytes(b"clean geometry")
    client = create_app(root).test_client()
    client.get("/duplicates/results")  # hash once, as the live viewer's snapshot has

    old_html = client.get("/catalog/BoronProbe/parts").get_data(as_text=True)
    new_html = client.get("/catalog/BoronProbe_2026/parts").get_data(as_text=True)

    def tile(html: str, path: str) -> str:
        start = html.rindex('<a class="thumb-tile', 0, html.index(f'href="/part/{path}"'))
        return html[start : html.index("</a>", start)]

    old_tile = tile(old_html, "BoronProbe/parts/bearing.ipt")
    new_tile = tile(new_html, "BoronProbe_2026/parts/bearing.ipt")
    generic = tile(old_html, "BoronProbe/parts/Part1.ipt")
    clean = tile(old_html, "BoronProbe/parts/clean.ipt")

    # Collision: both members get the collision dot; only the older one the
    # "newer file exists" dot after it, which names the folder and never says
    # superseded. Every signal is a dot; no tile carries a coloured edge.
    assert '<i class="signal-dot signal-collision"></i><i class="signal-dot signal-newer"></i>' in old_tile
    assert '<i class="signal-dot signal-collision"></i>' in new_tile
    assert "data-edge" not in old_html + new_html
    assert "signal-newer" not in new_tile
    assert "A newer file with this name exists at BoronProbe_2026\\parts" in old_tile
    assert "superseded" not in old_html.casefold()
    assert '<i class="signal-dot signal-generic"></i>' in generic
    assert "Generic name" in generic
    assert "signal-" not in clean and "thumb-details" not in clean
    # No words on the tile face: meanings live in the title and the details card.
    face = old_tile.split('<dl class="thumb-details"', 1)[0]
    assert "Same filename, different bytes" in face.split(">", 1)[0]  # the title attribute
    assert "Same filename, different bytes" not in face.split(">", 1)[1]
    legend = old_html.split('<section class="rail-card signal-legend">', 1)[1].split("</section>", 1)[0]
    assert "Same name, different bytes" in legend
    assert "Generic name" in legend and "Newer file with this name exists" in legend
    assert "Identical copy elsewhere" not in legend  # only signals present on this page


def test_signal_lookup_is_built_once_per_inventory(monkeypatch, tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    app = create_app(root, refresh_seconds=5)
    client = app.test_client()
    built: list[int] = []
    original = web.file_signals

    def counting(inventory):
        built.append(id(inventory))
        return original(inventory)

    monkeypatch.setattr(web, "file_signals", counting)
    try:
        client.get("/catalog/BoronProbe/parts")
        client.get("/catalog/Plasma%20Vessel/parts")
        assert len(built) == 1
    finally:
        app.extensions["pihti_ticker"].stop()


def test_the_header_field_filters_the_page_and_enter_still_searches_the_archive(
    tmp_path: Path,
) -> None:
    client = create_app(make_workspace(tmp_path)).test_client()

    folder = client.get("/catalog/BoronProbe/parts").get_data(as_text=True)
    results = client.get("/catalog?q=bearing").get_data(as_text=True)
    part = client.get("/part/BoronProbe/parts/bearing.ipt").get_data(as_text=True)
    script = client.get("/static/dedup.js").get_data(as_text=True)

    bar = folder.split('<header class="catalog-bar">', 1)[1].split("</header>", 1)[0]
    assert 'action="/catalog"' in bar and 'method="get"' in bar
    assert 'name="q" value="" placeholder="Filter this folder" autocomplete="off" data-filter-search>' in bar
    assert 'data-search-archive>Search whole archive</button>' in bar
    assert '<span data-filter-count data-total="1">1</span>' in folder
    assert 'placeholder="Filter results"' in results and "data-filter-search" in results
    assert results.count('class="thumb-tile"') == 3  # the server search itself is unchanged
    assert "data-filter-search" not in part and 'placeholder="Search whole archive"' in part
    assert 'document.querySelector("input[data-filter-search]")' in script
    assert "window.requestAnimationFrame(applyFilter)" in script
    assert "localStorage" not in script.split('input[data-filter-search]', 1)[1]  # persists nothing


def test_the_left_rail_inspector_is_present_only_where_there_are_files(tmp_path: Path) -> None:
    client = create_app(make_workspace(tmp_path)).test_client()

    folder = client.get("/catalog/BoronProbe/parts").get_data(as_text=True)
    only_folders = client.get("/catalog/BoronProbe").get_data(as_text=True)
    search = client.get("/catalog?q=bearing").get_data(as_text=True)

    context = folder.split('<aside class="rail-side rail-context"', 1)[1].split("</aside>", 1)[0]
    assert '<section class="rail-card inspector" data-inspector' in context
    assert "<p class=\"inspector-empty\" data-inspector-empty>Hover or arrow onto a file</p>" in context
    assert context.index("data-note-rail") < context.index("data-inspector")
    assert "data-inspector" in search
    assert "data-inspector" not in only_folders


def test_folder_cards_keep_their_approved_size(tmp_path: Path) -> None:
    style = create_app(tmp_path).test_client().get("/static/dedup.css").get_data(as_text=True)

    # Three to four cards per row on a 1920 screen, never six: a minimum card
    # width sized to a 3 x 2 strip of ~110-120px thumbnails, not a column count.
    assert (
        ".folder-grid { display: grid; grid-template-columns: "
        "repeat(auto-fill, minmax(min(100%, 22.5rem), 1fr));"
    ) in style
    assert ".folder-strip { display: grid; grid-template-columns: repeat(3, minmax(110px, 1fr)); gap: 3px; }" in style
    name_rule = style.split(".folder-card-head strong {", 1)[1].split("}", 1)[0]
    assert "ellipsis" not in name_rule and "nowrap" not in name_rule  # names wrap
    assert ".thumb-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(148px, 1fr));" in style
    assert "folder-glyph" not in style


def test_part_page_shares_the_catalog_shell_and_packs_its_facts(
    tmp_path: Path, monkeypatch
) -> None:
    png = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + (256).to_bytes(4, "big") + (192).to_bytes(4, "big")
    monkeypatch.setattr(web, "read_preview", lambda _path: Preview(data=png, image_format="png"))
    monkeypatch.setattr(
        web,
        "read_inventor_document",
        lambda _path: make_document(
            description="Carrier", material="PAEK", mass=3.5, density=1.3, valid_massprops=1
        ),
    )
    client = create_app(make_workspace(tmp_path)).test_client()

    part = client.get("/part/BoronProbe/parts/bearing.ipt").get_data(as_text=True)
    folder = client.get("/catalog/BoronProbe/parts").get_data(as_text=True)

    for html in (part, folder):
        assert '<div class="work-grid catalog-grid">' in html
        assert '<aside class="rail-side rail-context"' in html
        assert '<aside class="rail-side rail-tree" aria-label="Folder tree">' in html
        assert '<header class="catalog-bar">' in html
    assert 'href="/catalog/BoronProbe/parts" title="BoronProbe\\parts" aria-current="location"' in part
    assert '<strong aria-current="page">bearing.ipt</strong>' in part
    context = part.split('<aside class="rail-side rail-context"', 1)[1].split("</aside>", 1)[0]
    assert ">Back to folder</a>" in context and ">Folder note</a>" in context
    assert f'data-copy-text="{tmp_path / "BoronProbe" / "parts" / "bearing.ipt"}"' in context
    # Collision signal from the shared lookup, explained in the rail.
    assert "signal-legend" in context
    # Dense sheet: preview at its own pixel size, iProperties and mass in one grid.
    assert 'width="256" height="192"' in part
    sheet = part.split('<section class="part-sheet">', 1)[1].split("</section>", 1)[0]
    assert "<dt>Material</dt><dd>PAEK</dd>" in sheet
    assert "<dt>Mass</dt><dd>3.5000 g</dd>" in sheet
    # Two compact cards side by side; empty states are one line.
    pair = part.split('<div class="part-pair">', 1)[1]
    assert pair.index("Where used") < pair.index("Metadata sidecar")
    assert "No document names this file." in pair
    assert "No sidecar yet" in pair and ">Create metadata</button>" in pair
    # Rename is a disclosure carrying the old boundary sentence; no Boundary card.
    assert '<details class="part-card rename-editor" id="rename" data-rename-disclosure>' in part
    assert "never edits geometry, rewrites an Inventor reference, or commits anything" in part
    assert ">Boundary</h2>" not in part


def test_root_project_file_stands_in_the_rail_not_the_file_grid(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    (root / "PIHTI.ipj").write_bytes(b"<project/>")
    (root / "loose.stl").write_bytes(b"solid loose")
    client = create_app(root).test_client()

    html = client.get("/catalog").get_data(as_text=True)
    context = html.split('<aside class="rail-side rail-context"', 1)[1].split("</aside>", 1)[0]
    browse = html.split('<section class="catalog-browse"', 1)[1].split("</section>", 1)[0]

    assert 'href="/part/PIHTI.ipj"' not in html
    assert "PIHTI.ipj" not in browse
    assert '<p class="micro-heading">Project file</p>' in context
    assert '>PIHTI.ipj</strong>' in context
    assert f'data-copy-text="{root / "PIHTI.ipj"}"' in context
    assert "10 B" in context
    # Any other loose root file is still a tile, counted on its own line.
    assert browse.count('class="thumb-tile"') == 1
    assert 'href="/part/loose.stl"' in browse
    assert '<p class="grid-label"><strong>Files</strong> · <span data-filter-count data-total="1">1</span></p>' in browse
    # Search still finds the project file as an ordinary match.
    search = client.get("/catalog?q=PIHTI").get_data(as_text=True)
    assert 'href="/part/PIHTI.ipj"' in search


def test_folder_strips_are_one_pass_and_bounded() -> None:
    record = web.FileRecord
    records = [
        record(path, path.rsplit("/", 1)[-1], path.casefold(), "." + path.rsplit(".", 1)[-1], 1, 1, None, "A")
        for path in (
            "A/x.stl",
            "A/B/one.ipt",
            "A/B/C/two.iam",
            "A/B/mesh.step",
            "A/D/three.ipt",
            "AB/elsewhere.ipt",
            "A/direct.ipt",
        )
    ]

    strips = web.folder_strips(records, "A", limit=2)

    # Round-robin: a subfolder's first Inventor document, then a direct file.
    assert {key: [item.path for item in value] for key, value in strips.items()} == {
        "A/B": ["A/B/C/two.iam", "A/B/one.ipt"],
        "A/D": ["A/D/three.ipt"],
    }
    # At the root the A/B subtree offers its assembly before its part, and the
    # meshes (no cached render asked for) only top the strip up.
    top = web.folder_strips(records, ".")
    assert [item.path for item in top["A"]] == [
        "A/B/C/two.iam", "A/D/three.ipt", "A/direct.ipt", "A/B/one.ipt", "A/x.stl", "A/B/mesh.step"
    ]
    assert [item.path for item in top["AB"]] == ["AB/elsewhere.ipt"]


def test_catalog_header_is_one_compact_line_and_the_note_sits_behind_a_toggle(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path)
    (root / "BoronProbe" / "parts" / "README.md").write_text(
        "# parts\n\nPAEK bearing stack for the rotating head.\n", encoding="utf-8"
    )
    client = create_app(root).test_client()

    html = client.get("/catalog/BoronProbe/parts").get_data(as_text=True)
    main = html.split('<div class="work-main catalog-main">', 1)[1].split("<aside", 1)[0]
    bar = main.split('<header class="catalog-bar">', 1)[1].split("</header>", 1)[0]
    context = html.split('<aside class="rail-side rail-context"', 1)[1].split("</aside>", 1)[0]

    # One line above the thumbnails: breadcrumb and the global search, nothing else.
    assert main.index('<header class="catalog-bar">') < main.index("data-thumb-grid")
    assert 'aria-label="Breadcrumb"' in bar and 'name="q"' in bar
    assert 'href="/catalog/BoronProbe"' in bar
    assert '<strong aria-current="page">parts</strong>' in bar
    assert "catalog-heading" not in html
    assert "catalog-note-launch" not in html
    assert "Folder note</strong>" not in html
    assert ">Folder</p>" not in html
    assert "catalog-section" not in html
    # Folder facts, the copyable path, and the Note toggle live in the left rail.
    assert "<dt>Files here</dt><dd>1</dd>" in context
    assert "<dt>Below here</dt><dd>1</dd>" in context
    assert f'data-copy-text="{root / "BoronProbe" / "parts"}"' in context
    assert (
        '<button class="button note-rail-open" type="button" data-dialog-open="folder-note-dialog"'
        ' data-note-view="reader"' in context
    )
    assert '<p>PAEK bearing stack for the rotating head.</p>' in context
    # The whole note is inside the modal: its reader, the preview, the raw editor.
    assert main.count("PAEK bearing stack for the rotating head.") == 3
    assert main.index('id="folder-note-dialog"') > main.index("data-thumb-grid")

    landing = client.get("/catalog").get_data(as_text=True)
    assert 'data-dialog-open="folder-note-dialog"' not in landing  # the root README is not a folder note
    search = client.get("/catalog?q=bearing").get_data(as_text=True)
    assert "Clear search" in search and "<dt>Matches</dt><dd>3</dd>" in search


def test_catalog_styles_place_context_left_and_tree_right_on_one_sticky_offset(
    tmp_path: Path,
) -> None:
    client = create_app(tmp_path).test_client()
    style = client.get("/static/dedup.css").get_data(as_text=True)
    script = client.get("/static/dedup.js").get_data(as_text=True)

    # A wide left rail for the inspector, the standard tree rail right (the
    # same 17rem as the outer Duplicates rail, so it does not move across tabs).
    assert (
        ".work-grid.catalog-grid { grid-template-columns: 25.5rem minmax(0, 1fr) 17rem; "
        "align-items: stretch; }"
    ) in style
    assert "grid-template-columns: minmax(0, 1fr) 17rem 17rem" in style
    assert ".catalog-grid > .rail-context { grid-column: 1; grid-row: 1; }" in style
    assert ".catalog-grid > .rail-tree { grid-column: 3; grid-row: 1; }" in style
    # Both rails and the header line share the one sticky offset of every tab.
    rail_rule = style.split(".rail-side {", 1)[1].split("}", 1)[0]
    bar_rule = style.split(".catalog-bar {", 1)[1].split("}", 1)[0]
    for rule in (rail_rule, bar_rule):
        assert "top: calc(var(--bar-height) + var(--content-pad));" in rule
    # One fold: below 1200px both rails move into one right column, no inspector.
    fold = style.split("@media (max-width: 1200px)", 1)[1]
    assert ".work-grid.catalog-grid { grid-template-columns: minmax(0, 1fr) 17rem;" in fold
    assert ".inspector { display: none !important; }" in fold
    assert ".catalog-grid" not in style.split("@media (max-width: 1100px)", 1)[1].split("@media", 1)[0]
    assert "thumb-peek" not in style and "thumb-peek" not in script  # nothing floats
    # The inspector and keyboard walking are progressive enhancement.
    assert "var HOVER_DELAY = 150;" in script
    assert 'key === "ArrowDown"' in script and 'event.key === "Escape"' in script
    assert "data-thumb-grid" in script and "[data-inspector]" in script


def test_the_catalog_section_header_shows_the_folder_note_excerpt(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    (root / "BoronProbe" / "parts" / "README.md").write_text(
        "# parts\n\nPAEK bearing stack for the rotating head.\n", encoding="utf-8"
    )
    client = create_app(root).test_client()

    html = client.get("/catalog/BoronProbe").get_data(as_text=True)

    assert "PAEK bearing stack for the rotating head." in html


def test_live_folder_note_preview_renders_without_writing_a_readme(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    client = create_app(root).test_client()

    preview = client.post("/markdown/preview", data={"text": "# Draft\n\nA **live** note."})

    assert preview.status_code == 200
    assert "<strong>live</strong>" in preview.get_json()["html"]
    assert not (root / "BoronProbe" / "parts" / "README.md").exists()


def test_catalog_note_dialog_has_live_preview_and_sticky_actions(tmp_path: Path) -> None:
    app = create_app(make_workspace(tmp_path))
    client = app.test_client()

    html = client.get("/catalog/BoronProbe/parts").get_data(as_text=True)
    style = client.get("/static/dedup.css").get_data(as_text=True)
    script = client.get("/static/dedup.js").get_data(as_text=True)

    assert "data-live-note-form" in html
    assert "data-live-note-input" in html
    assert "data-note-preview-body" in html
    assert "data-live-note-status" in html
    assert "resize: both" in style
    assert ".note-dialog-actions { position: sticky" in style
    assert 'fetch("/markdown/preview"' in script


def test_folder_note_editor_explains_that_the_summary_feeds_catalog_cards(tmp_path: Path) -> None:
    client = create_app(make_workspace(tmp_path)).test_client()

    catalog = client.get("/catalog/BoronProbe/parts").get_data(as_text=True)
    full_page = client.get("/folder/BoronProbe/parts").get_data(as_text=True)

    for html in (catalog, full_page):
        assert "Start with a one-sentence summary directly below the title." in html
        assert "It appears on this folder's Catalog card." in html
        assert "One sentence: what this folder contains" in html


def test_folder_note_full_page_has_obvious_routes_back_to_browsing(tmp_path: Path) -> None:
    client = create_app(make_workspace(tmp_path)).test_client()

    html = client.get("/folder/BoronProbe/parts").get_data(as_text=True)

    assert 'aria-label="Leave the folder-note editor"' in html
    assert 'class="rail-action primary" href="/catalog/BoronProbe/parts"' in html
    assert "Back to this folder" in html
    assert 'class="rail-action" href="/catalog/BoronProbe"' in html
    assert "Parent folder" in html
    assert 'class="rail-action" href="/catalog"' in html
    assert "Catalog home" in html
    assert "Catalog</a><span" in html
    assert "Folder note</strong>" in html
    assert 'href="/catalog/BoronProbe/parts"' in html


def test_a_folder_note_is_written_to_that_folders_own_readme(tmp_path: Path) -> None:
    app = create_app(make_workspace(tmp_path))
    client = app.test_client()
    readme = tmp_path / "BoronProbe" / "parts" / "README.md"

    saved = client.post(
        "/folder/BoronProbe/parts/note",
        data={"token": app.config["FORM_TOKEN"], "text": "# parts\n\nThe bearing stack.\n"},
    )

    assert saved.status_code == 302
    assert readme.read_text(encoding="utf-8") == "# parts\n\nThe bearing stack.\n"

    page = client.get("/folder/BoronProbe/parts?saved=1").get_data(as_text=True)
    assert "Folder note saved." in page
    assert "The bearing stack." in page
    assert "bearing.ipt" in page


def test_generated_readme_editors_hide_the_leading_comment_but_keep_the_body(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path)
    generated = (
        "<!-- This file was generated by scripts/generate_readmes.py -->\n"
        "<!-- Editing this file (by hand or via the folder-note editor) claims it as "
        "your folder note; the generator will then leave it alone. -->\n\n"
        "# parts\n\n## Purpose\n"
    )
    (root / "BoronProbe" / "parts" / "README.md").write_text(generated, encoding="utf-8")
    client = create_app(root).test_client()

    catalog_html = client.get("/catalog/BoronProbe/parts").get_data(as_text=True)
    folder_html = client.get("/folder/BoronProbe/parts").get_data(as_text=True)

    for html in (catalog_html, folder_html):
        assert "This file was generated by scripts/generate_readmes.py" not in html
        assert "claims it as your folder note" not in html  # the comment block itself
    assert "Generated inventory" in catalog_html
    assert "<h2>Purpose</h2>" in catalog_html  # preview is directly inside the dialog
    assert "## Purpose" in catalog_html  # raw editing is directly inside the dialog too
    assert "## Purpose" in folder_html
    assert (
        "Generated index — edit and save to make it your folder note; "
        "the generator will then leave this file alone." in folder_html
    )


def test_a_manually_edited_readme_is_shown_as_is_with_no_generated_hint(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    manual = "# parts\n\nHand-written prose about the bearing stack.\n"
    (root / "BoronProbe" / "parts" / "README.md").write_text(manual, encoding="utf-8")
    client = create_app(root).test_client()

    catalog_html = client.get("/catalog/BoronProbe/parts").get_data(as_text=True)
    folder_html = client.get("/folder/BoronProbe/parts").get_data(as_text=True)

    for html in (catalog_html, folder_html):
        assert "Hand-written prose about the bearing stack." in html
        assert "Generated index — edit and save to make it your folder note" not in html


def test_sidecar_prose_is_rendered_and_the_raw_text_hides_behind_an_edit_toggle(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path)
    companion = root / "BoronProbe" / "parts" / "bearing.ipt.md"
    companion.write_text(
        "---\nstatus: draft\n---\n\nA **bold** claim.\n\n| a | b |\n|---|---|\n| 1 | 2 |\n",
        encoding="utf-8",
    )
    client = create_app(root).test_client()

    html = client.get("/part/BoronProbe/parts/bearing.ipt").get_data(as_text=True)

    assert "<strong>bold</strong>" in html
    assert "**bold**" not in html.split('<textarea id="sidecar-text"', 1)[0]
    assert "<th>a</th>" in html  # the tables extension is live on the page too
    assert 'class="raw-editor"' in html
    assert ">Edit raw text</summary>" in html
    # The editor still carries the exact file text, so a round-trip cannot lose it.
    assert "A **bold** claim." in html.split('<textarea id="sidecar-text"', 1)[1]


def test_a_rendered_note_round_trips_the_raw_text_through_save_untouched(tmp_path: Path) -> None:
    app = create_app(make_workspace(tmp_path))
    client = app.test_client()
    readme = tmp_path / "BoronProbe" / "parts" / "README.md"
    source = "# parts\n\nA **bold** claim.\n\n- one\n- two\n"

    saved = client.post(
        "/folder/BoronProbe/parts/note", data={"token": app.config["FORM_TOKEN"], "text": source}
    )
    html = client.get("/folder/BoronProbe/parts").get_data(as_text=True)
    editor = html.split('<textarea id="folder-note-text"', 1)[1]

    assert saved.status_code == 302
    assert readme.read_text(encoding="utf-8") == source
    assert "<strong>bold</strong>" in html
    assert "<li>one</li>" in html
    assert "A **bold** claim." in editor  # the textarea is still the raw file


def test_an_empty_folder_note_editor_teaches_valid_markdown_structure(tmp_path: Path) -> None:
    client = create_app(make_workspace(tmp_path)).test_client()

    html = client.get("/folder/BoronProbe").get_data(as_text=True)

    assert "Markdown needs explicit structure" in html
    assert "# BoronProbe&#10;&#10;One sentence: what this folder contains" in html
    assert "- **Owner:**" in html


def test_the_catalog_renders_a_folder_note_and_strips_markdown_from_the_excerpt(
    tmp_path: Path,
) -> None:
    root = make_workspace(tmp_path)
    (root / "BoronProbe" / "parts" / "README.md").write_text(
        "# parts\n\nThe **PAEK** bearing stack.\n", encoding="utf-8"
    )
    client = create_app(root).test_client()

    html = client.get("/catalog/BoronProbe/parts").get_data(as_text=True)

    assert "<strong>PAEK</strong>" in html
    rail = html.split("data-note-rail-body>", 1)[1].split("</div>", 1)[0]
    assert rail == "<p>The <strong>PAEK</strong> bearing stack.</p>"  # rendered in the rail
    assert 'data-dialog-open="folder-note-dialog"' in html
    assert 'id="folder-note-dialog"' in html
    assert 'id="catalog-folder-note-text"' in html
    assert 'name="origin" value="catalog"' in html
    assert 'aria-label="Close folder note"' in html
    assert ">Close</button>" in html
    assert "Open or edit folder note" not in html
    assert 'class="catalog-note"' not in html


def test_marker_stripping_composes_with_rendering_for_a_generated_readme(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    generated = (
        "<!-- This file was generated by scripts/generate_readmes.py -->\n"
        "<!-- Editing this file (by hand or via the folder-note editor) claims it as "
        "your folder note; the generator will then leave it alone. -->\n\n"
        "# parts\n\n## Purpose\n\nSeeded **index** body.\n"
    )
    (root / "BoronProbe" / "parts" / "README.md").write_text(generated, encoding="utf-8")
    client = create_app(root).test_client()

    catalog_html = client.get("/catalog/BoronProbe/parts").get_data(as_text=True)
    folder_html = client.get("/folder/BoronProbe/parts").get_data(as_text=True)

    for html in (catalog_html, folder_html):
        # The stripped marker is neither rendered as markup nor leaked as escaped text.
        assert "generate_readmes.py" not in html
        assert "&lt;!--" not in html

    assert "<h2>Purpose</h2>" in folder_html  # the rest of the body renders
    assert "<strong>index</strong>" in folder_html
    # The current note's preview and editor live together in the Catalog dialog.
    assert "<h2>Purpose</h2>" in catalog_html
    assert "## Purpose" in catalog_html
    assert "Generated inventory" in catalog_html


def test_catalog_folder_note_save_returns_to_the_same_open_dialog(tmp_path: Path) -> None:
    app = create_app(make_workspace(tmp_path))
    client = app.test_client()
    source = "# parts\n\nUpdated from the Catalog dialog.\n"

    response = client.post(
        "/folder/BoronProbe/parts/note",
        data={
            "token": app.config["FORM_TOKEN"],
            "origin": "catalog",
            "text": source,
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/catalog/BoronProbe/parts?saved=1")
    page = client.get(response.headers["Location"]).get_data(as_text=True)
    assert "Folder note saved." in page
    assert 'id="folder-note-dialog" aria-labelledby="folder-note-title" data-auto-open' in page
    assert "Updated from the Catalog dialog." in page


def test_invalid_catalog_folder_note_stays_in_the_open_dialog(tmp_path: Path) -> None:
    app = create_app(make_workspace(tmp_path))
    client = app.test_client()

    response = client.post(
        "/folder/BoronProbe/parts/note",
        data={
            "token": app.config["FORM_TOKEN"],
            "origin": "catalog",
            "text": "  \n",
        },
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 400
    assert "an empty note would erase" in html
    assert 'id="folder-note-dialog" aria-labelledby="folder-note-title" data-auto-open' in html


def test_folder_note_writes_keep_the_localhost_token_and_containment_guards(
    tmp_path: Path,
) -> None:
    app = create_app(make_workspace(tmp_path))
    client = app.test_client()
    readme = tmp_path / "BoronProbe" / "parts" / "README.md"
    note = {"token": app.config["FORM_TOKEN"], "text": "# parts\n\nProse.\n"}

    remote = client.post(
        "/folder/BoronProbe/parts/note", data=note, environ_base={"REMOTE_ADDR": "192.0.2.10"}
    )
    untokened = client.post("/folder/BoronProbe/parts/note", data={**note, "token": "guessed"})
    escaped = client.post("/folder/..%2Foutside/note", data=note)
    empty = client.post(
        "/folder/BoronProbe/parts/note", data={"token": app.config["FORM_TOKEN"], "text": "  \n"}
    )

    assert remote.status_code == 403
    assert untokened.status_code == 403
    assert escaped.status_code == 404
    assert empty.status_code == 400
    assert "would erase" in empty.get_data(as_text=True)
    assert not readme.exists()
    assert client.get("/folder/BoronProbe/parts/bearing.ipt").status_code == 404


def test_rename_moves_the_file_its_sidecar_and_writes_the_ledger(tmp_path: Path) -> None:
    root = make_rename_workspace(tmp_path)
    companion = root / "BoronProbe" / "parts" / "spacer.ipt.md"
    companion.write_text("---\nstatus: draft\n---\n\nWhy.\n", encoding="utf-8")
    app = create_app(root)
    client = app.test_client()

    page = client.get("/part/BoronProbe/parts/spacer.ipt").get_data(as_text=True)
    assert "Rename in place" in page
    assert "BoronProbe\\probe.iam" in page  # where-used, read out of the assembly bytes

    renamed = client.post(
        "/part/BoronProbe/parts/spacer.ipt/rename",
        data={"token": app.config["FORM_TOKEN"], "new_name": "rear_spacer"},
    )

    assert renamed.status_code == 302
    assert renamed.headers["Location"].endswith("/part/BoronProbe/parts/rear_spacer.ipt?renamed=1")
    assert not (root / "BoronProbe" / "parts" / "spacer.ipt").exists()
    assert (root / "BoronProbe" / "parts" / "rear_spacer.ipt").exists()
    assert not companion.exists()
    assert (root / "BoronProbe" / "parts" / "rear_spacer.ipt.md").is_file()

    entries = read_ledger(root)
    assert len(entries) == 1
    assert entries[0].where_used == ("BoronProbe/probe.iam",)
    assert entries[0].will_prompt is True


def test_rename_refuses_a_name_that_already_exists_in_the_workspace(tmp_path: Path) -> None:
    root = make_rename_workspace(tmp_path)
    taken = root / "Plasma Vessel"
    taken.mkdir()
    (taken / "rear_spacer.ipt").write_bytes(b"someone else")
    app = create_app(root)
    client = app.test_client()

    refused = client.post(
        "/part/BoronProbe/parts/spacer.ipt/rename",
        data={"token": app.config["FORM_TOKEN"], "new_name": "rear_spacer"},
    )

    assert refused.status_code == 400
    assert "already exists in the workspace" in refused.get_data(as_text=True)
    assert (root / "BoronProbe" / "parts" / "spacer.ipt").exists()
    assert read_ledger(root) == ()


def test_rename_warns_about_a_silent_rebind_before_it_will_proceed(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)  # three files all named bearing.ipt
    (root / "BoronProbe" / "probe.iam").write_bytes(assembly_bytes("parts\\bearing.ipt"))
    app = create_app(root)
    client = app.test_client()
    form = {"token": app.config["FORM_TOKEN"], "new_name": "probe_bearing"}

    warned = client.post("/part/BoronProbe/parts/bearing.ipt/rename", data=form)
    body = warned.get_data(as_text=True)

    assert warned.status_code == 409
    assert "Inventor will not warn you about this one." in body
    assert "Plasma Vessel\\parts\\bearing.ipt" in body
    assert "BoronProbe\\probe.iam" in body
    assert 'name="confirm_collision" value="1"' in body
    assert (root / "BoronProbe" / "parts" / "bearing.ipt").exists()
    assert read_ledger(root) == ()

    confirmed = client.post(
        "/part/BoronProbe/parts/bearing.ipt/rename", data={**form, "confirm_collision": "1"}
    )

    assert confirmed.status_code == 302
    assert (root / "BoronProbe" / "parts" / "probe_bearing.ipt").exists()
    entry = read_ledger(root)[0]
    assert entry.will_prompt is False
    assert entry.where_used == ("BoronProbe/probe.iam",)


def test_rename_keeps_the_localhost_token_and_containment_guards(tmp_path: Path) -> None:
    app = create_app(make_rename_workspace(tmp_path))
    client = app.test_client()
    form = {"token": app.config["FORM_TOKEN"], "new_name": "rear_spacer"}

    remote = client.post(
        "/part/BoronProbe/parts/spacer.ipt/rename", data=form, environ_base={"REMOTE_ADDR": "1.1.1.1"}
    )
    untokened = client.post(
        "/part/BoronProbe/parts/spacer.ipt/rename", data={**form, "token": "guessed"}
    )
    escaped = client.post("/part/..%2Foutside-secret.ipt/rename", data=form)

    assert remote.status_code == 403
    assert untokened.status_code == 403
    assert escaped.status_code == 404
    assert (tmp_path / "BoronProbe" / "parts" / "spacer.ipt").exists()


def test_renames_page_separates_the_two_flavours_and_marks_an_entry_settled(
    tmp_path: Path,
) -> None:
    root = make_rename_workspace(tmp_path)
    app = create_app(root)
    client = app.test_client()

    assert "No renames recorded yet." in client.get("/renames").get_data(as_text=True)

    client.post(
        "/part/BoronProbe/parts/spacer.ipt/rename",
        data={"token": app.config["FORM_TOKEN"], "new_name": "rear_spacer"},
    )
    entry = read_ledger(root)[0]

    page = client.get("/renames").get_data(as_text=True)

    assert "Inventor will ask now." in page
    assert "Inventor will NOT ask." not in page
    assert "rear_spacer.ipt" in page
    assert f'data-copy-text="{root / "BoronProbe" / "parts" / "rear_spacer.ipt"}"' in page
    assert f'data-copy-text="{root / "BoronProbe" / "parts"}"' in page
    assert f'data-referrer-check="{entry.id}::BoronProbe/probe.iam"' in page
    assert f'data-rename-settled="{entry.id}"' in page
    assert 'href="/renames"' in page

    toggled = client.post(
        f"/renames/{entry.id}/settled",
        json={"settled": True},
        headers={"X-PIHTI-Token": app.config["FORM_TOKEN"]},
    )

    assert toggled.status_code == 200
    assert toggled.get_json() == {"id": entry.id, "settled": True}
    assert read_ledger(root)[0].settled is True

    blocked = client.post(
        f"/renames/{entry.id}/settled",
        json={"settled": False},
        headers={"X-PIHTI-Token": app.config["FORM_TOKEN"]},
        environ_base={"REMOTE_ADDR": "192.0.2.10"},
    )
    untokened = client.post(f"/renames/{entry.id}/settled", json={"settled": False})
    unknown = client.post(
        "/renames/0000000000000000/settled",
        json={"settled": True},
        headers={"X-PIHTI-Token": app.config["FORM_TOKEN"]},
    )

    assert blocked.status_code == 403
    assert untokened.status_code == 403
    assert unknown.status_code == 404
    assert read_ledger(root)[0].settled is True


def test_duplicate_rows_link_to_the_guarded_rename_action(tmp_path: Path) -> None:
    client = create_app(make_workspace(tmp_path)).test_client()

    result_html = client.get("/duplicates/results").get_data(as_text=True)

    assert result_html.count('href="/part/BoronProbe/parts/bearing.ipt#rename"') == 1
    assert result_html.count(">Rename<") == 3


def test_doctor_keeps_a_name_session_open_until_the_last_original_is_renamed(
    tmp_path: Path,
) -> None:
    root = tmp_path
    first = root / "A" / "Wide Din Clip.ipt"
    second = root / "B" / "Wide Din Clip.ipt"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    app = create_app(root)
    client = app.test_client()
    token = app.config["FORM_TOKEN"]
    url = "/doctor/name/Wide%20Din%20Clip.ipt"

    page = client.get(url).get_data(as_text=True)
    assert page.count('name="relative_path"') == 2
    assert page.count('class="doctor-file-preview"') == 2
    assert "Will not ask" in page

    warned = client.post(
        url,
        data={
            "token": token,
            "relative_path": "A/Wide Din Clip.ipt",
            "new_name": "Wide Din Clip v1",
        },
    )
    assert warned.status_code == 409
    assert "Rename this member and stay in session" in warned.get_data(as_text=True)

    renamed_first = client.post(
        url,
        data={
            "token": token,
            "relative_path": "A/Wide Din Clip.ipt",
            "new_name": "Wide Din Clip v1",
            "confirm_collision": "1",
        },
    )
    assert renamed_first.status_code == 302
    page = client.get(url + "?renamed=1").get_data(as_text=True)
    assert "This session remains open so the last original cannot disappear" in page
    assert "B\\Wide Din Clip.ipt" in page
    assert "A\\Wide Din Clip v1.ipt" in page
    assert 'class="doctor-history-preview"' in page

    renamed_second = client.post(
        url,
        data={
            "token": token,
            "relative_path": "B/Wide Din Clip.ipt",
            "new_name": "Wide Din Clip v2",
        },
    )
    assert renamed_second.status_code == 302
    page = client.get(url).get_data(as_text=True)
    assert "No original remains." in page
    assert "Will ask" in page


def test_rename_ledger_reports_current_resolution_not_only_rename_time(
    tmp_path: Path,
) -> None:
    root = tmp_path
    first = root / "A" / "Body.ipt"
    second = root / "B" / "Body.ipt"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    app = create_app(root)
    client = app.test_client()
    token = app.config["FORM_TOKEN"]

    client.post(
        "/part/A/Body.ipt/rename",
        data={"token": token, "new_name": "Connector Body", "confirm_collision": "1"},
    )
    before = client.get("/renames").get_data(as_text=True)
    assert "Inventor will NOT ask now." in before

    client.post(
        "/part/B/Body.ipt/rename",
        data={"token": token, "new_name": "Relay Body"},
    )
    after = client.get("/renames").get_data(as_text=True)
    assert after.count("Inventor will ask now.") == 2
    assert "At rename time another copy still existed" in after


def test_doctor_lists_collision_and_generic_name_queues(tmp_path: Path) -> None:
    root = tmp_path
    for relative, content in (
        ("A/Body.ipt", b"first"),
        ("B/Body.ipt", b"second"),
        ("C/Part001.ipt", b"single generic"),
    ):
        target = root / relative
        target.parent.mkdir()
        target.write_bytes(content)
    html = create_app(root).test_client().get("/doctor").get_data(as_text=True)

    assert "Collision doctor" in html
    assert "Name doctor" in html
    assert 'href="/doctor/name/Body.ipt"' in html
    assert 'href="/doctor/name/Part001.ipt"' in html
    assert html.count('class="doctor-preview-stack"') == 3
    assert "including singletons that never appear under Duplicates" in html


def test_doctor_previews_referring_assemblies(tmp_path: Path) -> None:
    part = tmp_path / "A" / "Body.ipt"
    assembly = tmp_path / "Assembly" / "Fixture.iam"
    part.parent.mkdir()
    assembly.parent.mkdir()
    part.write_bytes(b"geometry")
    assembly.write_bytes(b"\xde\xad" * 4 + b"\x00\x00" + "Body.ipt".encode("utf-16-le") + b"\x00\x00")

    html = create_app(tmp_path).test_client().get("/doctor/name/Body.ipt").get_data(as_text=True)

    assert 'class="doctor-referrer-preview"' in html
    assert '/preview/Assembly/Fixture.iam' in html


def test_doctor_starts_from_assembly_and_lists_direct_name_problems(
    monkeypatch, tmp_path: Path
) -> None:
    assembly = tmp_path / "Assembly" / "Fixture.iam"
    assembly.parent.mkdir()
    payload = bytearray(b"\xde\xad" * 4)
    for name in ("Body.ipt", "Missing.ipt", "Unique.ipt"):
        payload += b"\x00\x00" + name.encode("utf-16-le") + b"\x00\x00"
    assembly.write_bytes(payload)
    for relative, content in (
        ("A/Body.ipt", b"first body"),
        ("B/Body.ipt", b"second body"),
        ("Assembly/Unique.ipt", b"unique"),
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    monkeypatch.setattr(
        web,
        "query_filename_history",
        lambda root, name: FilenameHistory(name, ()),
    )
    client = create_app(tmp_path).test_client()

    queue = client.get("/doctor").get_data(as_text=True)
    assert "Assembly workbenches" in queue
    assert 'href="/doctor/assembly/Assembly/Fixture.iam"' in queue
    detail = client.get("/doctor/assembly/Assembly/Fixture.iam")
    html = detail.get_data(as_text=True)

    assert detail.status_code == 200
    assert "One assembly at a time" in html
    assert "Body.ipt" in html
    assert "2 possible silent targets" in html
    assert "Missing.ipt" in html
    assert "Never tracked in reachable Git history" in html
    assert "Unique.ipt" not in html
    assert html.count("Preview of A\\Body.ipt") == 1
    assert html.count("Preview of B\\Body.ipt") == 1
    assert "/doctor/name/Body.ipt?assembly=Assembly/Fixture.iam" in html


def test_assembly_doctor_surfaces_git_rename_and_historical_preview(
    monkeypatch, tmp_path: Path
) -> None:
    assembly = tmp_path / "Assembly" / "Fixture.iam"
    assembly.parent.mkdir()
    assembly.write_bytes(
        b"\xde\xad" * 4
        + b"\x00\x00"
        + "Old flange.ipt".encode("utf-16-le")
        + b"\x00\x00"
    )
    destination = tmp_path / "Library" / "New flange.ipt"
    destination.parent.mkdir()
    destination.write_bytes(b"current")
    occurrence = FilenameOccurrence(
        commit="a" * 40,
        committed_at="2026-08-01T10:00:00+09:00",
        subject="Rename flange",
        status="R100",
        path="Legacy/Old flange.ipt",
        rename_destination="Library/New flange.ipt",
    )
    monkeypatch.setattr(
        web,
        "query_filename_history",
        lambda root, name: FilenameHistory(name, (occurrence,)),
    )
    monkeypatch.setattr(web, "materialize_historical_blob", lambda *args: b"old bytes")
    client = create_app(tmp_path).test_client()

    html = client.get("/doctor/assembly/Assembly/Fixture.iam").get_data(as_text=True)
    preview = client.get(
        "/doctor/history-preview/" + "a" * 40 + "/Library/New%20flange.ipt"
    )

    assert "Git filename history" in html
    assert "Renamed to" in html
    assert "Library\\New flange.ipt" in html
    assert "current file" in html
    assert "/doctor/history-preview/" + "a" * 40 in html
    assert preview.status_code == 200
    assert preview.mimetype == "image/svg+xml"


def test_assembly_doctor_rejects_non_assemblies_and_traversal(tmp_path: Path) -> None:
    part = tmp_path / "part.ipt"
    part.write_bytes(b"part")
    client = create_app(tmp_path).test_client()

    assert client.get("/doctor/assembly/part.ipt").status_code == 404
    assert client.get("/doctor/assembly/..%2Foutside.iam").status_code == 404


def test_packaged_script_drives_the_folder_tree_and_the_rename_ledger(tmp_path: Path) -> None:
    script = create_app(tmp_path).test_client().get("/static/dedup.js").get_data(as_text=True)

    assert "data-folder-tree" in script
    assert "data-tree-toggle" in script
    assert "setOpen" in script
    assert 'TREE_KEY = "pihti-catalog-tree"' not in script
    assert "localStorage.setItem(TREE_KEY" not in script
    assert "data-dialog-open" in script
    assert "dialog.showModal()" in script
    assert "event.target === dialog" in script
    assert "dialog.close()" in script
    assert "data-copy-text" in script
    assert "data-rename-settled" in script
    assert "data-rename-search" in script


def test_styles_indent_the_folder_tree_and_scroll_only_the_tree_inside_its_pinned_card(
    tmp_path: Path,
) -> None:
    style = create_app(tmp_path).test_client().get("/static/dedup.css").get_data(as_text=True)

    assert ".folder-tree" in style
    assert "var(--tree-depth, 0)" in style  # depth indent, not a nested scroll container
    assert ".note-dialog::backdrop" in style
    assert ".dialog-close-x" in style
    assert ".thumb-tile.has-metadata" in style
    assert ".thumb-tile.has-story" in style
    assert "grid-column: span 2" in style
    assert ".folder-card.has-summary" in style
    assert ".note-rail { height: clamp(5rem, calc(100vh - 42rem), 11rem);" in style
    assert "grid-template-columns: minmax(0, 1.08fr) minmax(0, 0.92fr)" in style
    # The owner once rejected inner scrolling; on 2026-09-24 he ruled a pinned
    # rail the priority ("not nailed, hate it"). So each catalog rail stops
    # between the sticky offset and the page foot (so the end of the scroll
    # cannot push it up either), and only the tree, or the inspector's fact
    # list, scrolls inside it. Nothing gets a fixed pixel ceiling.
    assert scrolling_selectors(style) == [".inspector-facts", ".tree-card .folder-tree"]
    # The 1px absorbs sub-pixel document heights that scrollHeight rounds away.
    ceiling = "calc(100vh - var(--bar-height) - var(--content-pad) - var(--page-foot) - 1px)"
    assert (
        f".tree-card {{ display: flex; flex-direction: column; max-height: {ceiling}; }}"
    ) in style
    assert f".rail-context {{ max-height: {ceiling}; }}" in style
    assert "padding: var(--content-pad) 0 var(--page-foot);" in style
    assert re.search(r"max-height:\s*\d", style) is None
    assert style.count("max-height: calc(") == 2


def counting_scanner(calls: list[bool]):
    def scanner(root: Path, **kwargs):
        calls.append(kwargs.get("include_vendor", False))
        return scan_workspace(root, **kwargs)

    return scanner


def test_snapshot_cache_serves_persisted_inventory_without_walking(
    monkeypatch, tmp_path: Path
) -> None:
    root = make_workspace(tmp_path)
    persisted = web.InventoryCache(root, scan_workspace).get(include_vendor=False)
    calls: list[bool] = []
    cache = web.InventoryCache(root, counting_scanner(calls), max_age=5)

    adopted = cache.get(include_vendor=False)
    assert adopted.records == persisted.records
    assert calls == []

    fresh = root / "BoronProbe" / "parts" / "fresh.ipt"
    fresh.write_bytes(b"fresh part")
    assert cache.get(include_vendor=False) is adopted
    assert cache.get(include_vendor=False, hash_files=False) is adopted
    assert calls == []

    assert cache.refresh(include_vendor=False) is True
    assert calls == [False]
    refreshed = cache.get(include_vendor=False)
    by_path = {record.path: record for record in refreshed.records}
    assert by_path["BoronProbe/parts/fresh.ipt"].sha256
    assert calls == [False]
    assert cache.refresh(include_vendor=True) is False  # never loaded, never walked
    assert calls == [False]

    later = root / "BoronProbe" / "parts" / "later.ipt"
    later.write_bytes(b"later part")
    cache.clear()
    cleared = cache.get(include_vendor=False)
    assert "BoronProbe/parts/later.ipt" in {record.path for record in cleared.records}
    assert calls == [False, False]
    assert cache.get(include_vendor=False) is cleared
    assert calls == [False, False]

    cache.get(include_vendor=False, force=True)
    cache.get(include_vendor=False, force=True)
    assert calls == [False, False, False, False]


def test_snapshot_cache_validates_synchronously_on_a_true_first_run(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    calls: list[bool] = []
    cache = web.InventoryCache(root, counting_scanner(calls), max_age=5)

    first = cache.get(include_vendor=False, hash_files=False)
    assert calls == [False]
    assert len(first.records) == 3
    assert cache.get(include_vendor=False, hash_files=False) is first
    assert calls == [False]

    # A hashed view of an unhashed snapshot must hash rather than hand back None digests.
    hashed = cache.get(include_vendor=False)
    assert all(record.sha256 for record in hashed.records)
    assert calls == [False, False]


def test_snapshot_cache_refresh_due_follows_requests_and_idle_age(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    now = [100.0]
    calls: list[bool] = []
    cache = web.InventoryCache(
        root, counting_scanner(calls), max_age=5, idle_interval=60, clock=lambda: now[0]
    )
    cache.refresh_due()
    assert calls == []  # nothing loaded, nothing to refresh

    cache.get(include_vendor=False)
    assert calls == [False]
    now[0] = 104
    cache.refresh_due()
    assert calls == [False]

    cache.get(include_vendor=False)  # requested since the last validation
    now[0] = 105
    cache.refresh_due()
    assert calls == [False, False]

    now[0] = 164
    cache.refresh_due()  # idle but not yet stale
    assert calls == [False, False]
    now[0] = 165
    cache.refresh_due()
    assert calls == [False, False, False]


def test_snapshot_app_serves_catalog_from_memory_until_refreshed(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    app = create_app(root, refresh_seconds=5)
    assert "pihti_ticker" not in app.extensions  # building an app spawns no thread
    client = app.test_client()

    before = client.get("/catalog/BoronProbe/parts").get_data(as_text=True)
    assert 'href="/part/BoronProbe/parts/bearing.ipt"' in before
    ticker = app.extensions["pihti_ticker"]
    try:
        assert ticker.running
        (root / "BoronProbe" / "parts" / "fresh.ipt").write_bytes(b"fresh part")

        stale = client.get("/catalog/BoronProbe/parts").get_data(as_text=True)
        assert 'href="/part/BoronProbe/parts/fresh.ipt"' not in stale

        assert app.extensions["pihti_inventory_cache"].refresh(include_vendor=False) is True
        current = client.get("/catalog/BoronProbe/parts").get_data(as_text=True)
        assert 'href="/part/BoronProbe/parts/fresh.ipt"' in current
    finally:
        ticker.stop()
    assert not ticker.running


def test_snapshot_app_clear_invalidates_derived_snapshots(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    app = create_app(root, refresh_seconds=5)
    client = app.test_client()
    try:
        assert client.get("/doctor").status_code == 200
        locations = app.extensions["pihti_snapshots"]["locations"]
        assert "fresh.ipt" not in locations.peek()

        (root / "BoronProbe" / "parts" / "fresh.ipt").write_bytes(b"fresh part")
        assert "fresh.ipt" not in locations.get()

        app.extensions["pihti_inventory_cache"].clear()
        assert locations.get()["fresh.ipt"] == ("BoronProbe/parts/fresh.ipt",)
    finally:
        app.extensions["pihti_ticker"].stop()


def test_catalog_folder_index_is_rebuilt_only_for_a_new_inventory(
    monkeypatch, tmp_path: Path
) -> None:
    root = make_workspace(tmp_path)
    app = create_app(root, refresh_seconds=5)
    client = app.test_client()
    built: list[int] = []
    original = web.folder_tree

    def counting_tree(index, **kwargs):
        built.append(id(index))
        return original(index, **kwargs)

    monkeypatch.setattr(web, "folder_tree", counting_tree)
    try:
        client.get("/catalog")
        client.get("/catalog/BoronProbe")
        assert len(built) == 2 and built[0] == built[1]  # same memoized index object

        (root / "BoronProbe" / "parts" / "fresh.ipt").write_bytes(b"fresh part")
        app.extensions["pihti_inventory_cache"].refresh(include_vendor=False)
        client.get("/catalog")
        assert built[2] != built[0]
    finally:
        app.extensions["pihti_ticker"].stop()


def make_hero_workspace(root: Path) -> Path:
    for relative in (
        "Vessel/vessel-main.iam",
        "Vessel/flange.ipt",
        "Vessel/vessel-main.idw",
        "Vessel/parts/bolt-ring.ipt",
        "Vessel/parts/spacer.ipt",
        "Vessel/Probe/probe-head.iam",
        "Vessel/Probe/tip.ipt",
        "Desk/desk.ipt",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(relative.encode())
    return root


def post_hero(app, client, path: str, hero: bool, origin: str, **extra):
    data = {"token": app.config["FORM_TOKEN"], "hero": "1" if hero else "0", "origin": origin}
    data.update(extra)
    return client.post(f"/part/{path}/hero", data=data)


def test_hero_toggle_keeps_the_localhost_and_token_guard(tmp_path: Path) -> None:
    app = create_app(make_hero_workspace(tmp_path))
    client = app.test_client()
    companion = tmp_path / "Vessel" / "vessel-main.iam.md"

    untokened = client.post(
        "/part/Vessel/vessel-main.iam/hero", data={"hero": "1", "origin": "Vessel", "token": "guessed"}
    )
    remote = client.post(
        "/part/Vessel/vessel-main.iam/hero",
        data={"hero": "1", "origin": "Vessel", "token": app.config["FORM_TOKEN"]},
        environ_base={"REMOTE_ADDR": "192.0.2.10"},
    )
    escaped = post_hero(app, client, "../outside.iam", True, "Vessel")

    assert untokened.status_code == 403 and remote.status_code == 403
    assert escaped.status_code == 404
    assert not companion.exists()


def test_hero_toggle_seeds_a_sidecar_and_returns_to_the_tile(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        web,
        "read_inventor_document",
        lambda _path: make_document(part_number="vessel-main", material="SUS304"),
    )
    app = create_app(make_hero_workspace(tmp_path))
    client = app.test_client()
    companion = tmp_path / "Vessel" / "vessel-main.iam.md"

    response = post_hero(app, client, "Vessel/vessel-main.iam", True, "Vessel")

    assert response.status_code == 302
    location = response.headers["Location"]
    assert location.startswith("/catalog/Vessel?hero=set&file=Vessel/vessel-main.iam#file-")
    assert location.endswith(web.tile_anchor("Vessel/vessel-main.iam"))
    sidecar = read_sidecar(companion)
    assert sidecar is not None and sidecar.hero is True
    assert sidecar.frontmatter["part_number"] == "vessel-main"
    assert sidecar.frontmatter["material"] == "SUS304"
    assert sidecar.body == ""

    page = client.get(location.split("#", 1)[0])
    html = page.get_data(as_text=True)
    assert page.headers["Cache-Control"] == "no-store"  # the page after a toggle stays live
    assert '<div class="operation-toast" role="status" data-operation-toast data-hero-toast>Hero set: vessel-main.iam</div>' in html
    assert f'id="{web.tile_anchor("Vessel/vessel-main.iam")}"' in html

    cleared = post_hero(app, client, "Vessel/vessel-main.iam", False, "Vessel")
    assert cleared.headers["Location"].startswith("/catalog/Vessel?hero=cleared&")
    assert read_sidecar(companion).hero is False
    assert "Hero cleared: vessel-main.iam" in client.get(cleared.headers["Location"]).get_data(as_text=True)
    assert "hero-block" not in client.get("/catalog/Vessel").get_data(as_text=True)


def test_a_folder_leads_with_its_heroes_and_never_repeats_them(tmp_path: Path) -> None:
    root = make_hero_workspace(tmp_path)
    app = create_app(root)
    client = app.test_client()
    post_hero(app, client, "Vessel/vessel-main.iam", True, "Vessel")
    post_hero(app, client, "Vessel/flange.ipt", True, "Vessel")

    html = client.get("/catalog/Vessel").get_data(as_text=True)
    browse = html.split("data-thumb-grid", 1)[1].split("</section>", 1)[0]
    heroes = browse.split('<div class="hero-block">', 1)[1].split('<div class="folder-grid">', 1)[0]
    files = browse.split('<div class="file-block">', 1)[1]

    # Main assemblies first, above the folder cards and the files, in path order.
    assert browse.index("hero-block") < browse.index("folder-grid") < browse.index("file-block")
    assert '<p class="grid-label"><strong>Main assemblies</strong> · 2</p>' in heroes
    assert re.findall(r'href="/part/([^"]+)"', heroes) == ["Vessel/flange.ipt", "Vessel/vessel-main.iam"]
    assert heroes.count('<div class="hero-card">') == 2
    assert heroes.count('<a class="thumb-tile hero-tile"') == 2
    # A folder's own heroes need no location line and no Open folder: you are there.
    assert "hero-folder" not in heroes and "Open folder" not in heroes
    # The file tile's preview size, not a large one.
    assert heroes.count('width="160" height="120"') == 2 and "max-width" not in heroes
    # The files grid holds the rest, and counts only the rest.
    assert "Vessel/vessel-main.iam" not in files and "Vessel/flange.ipt" not in files
    assert '<span data-filter-count data-total="1">1</span>' in files
    assert 'href="/part/Vessel/vessel-main.idw"' in files
    # The hero mark: its own shape in the legend, and "Main assembly" as the
    # first fact the inspector copies.
    tile = heroes.split('href="/part/Vessel/vessel-main.iam"', 1)[1].split("</a>", 1)[0]
    details = tile.split('<dl class="thumb-details" hidden>', 1)[1]
    first = details.split("</div>", 1)[0]
    assert '<i class="signal-mark signal-hero"></i>' in first and "<dd>Main assembly</dd>" in first
    assert '<span class="tile-signals" aria-hidden="true"><i class="signal-dot signal-hero"></i></span>' in tile
    assert 'data-hero="1"' in heroes
    legend = html.split('<section class="rail-card signal-legend">', 1)[1].split("</section>", 1)[0]
    assert '<li><i class="signal-mark signal-hero"></i>Hero: a main assembly or file you designated</li>' in legend


def test_a_folder_holding_only_heroes_still_has_its_inspector(tmp_path: Path) -> None:
    root = make_hero_workspace(tmp_path)
    app = create_app(root)
    client = app.test_client()
    post_hero(app, client, "Desk/desk.ipt", True, "Desk")

    html = client.get("/catalog/Desk").get_data(as_text=True)

    assert 'class="file-block"' not in html and "No CAD files in this folder." not in html
    assert "hero-block" in html and "data-inspector" in html


def test_the_root_lists_every_hero_with_its_folder_and_omits_the_row_when_none(
    tmp_path: Path,
) -> None:
    root = make_hero_workspace(tmp_path)
    app = create_app(root)
    client = app.test_client()

    before = client.get("/catalog").get_data(as_text=True)
    assert "hero-block" not in before and "Main assemblies" not in before

    post_hero(app, client, "Vessel/Probe/probe-head.iam", True, ".")
    post_hero(app, client, "Desk/desk.ipt", True, ".")
    after = client.get("/catalog").get_data(as_text=True)
    browse = after.split("data-thumb-grid", 1)[1].split("</section>", 1)[0]
    heroes = browse.split('<div class="hero-block">', 1)[1].split('<div class="folder-grid">', 1)[0]

    assert browse.index("hero-block") < browse.index("folder-grid")
    assert re.findall(r'href="/part/([^"]+)"', heroes) == ["Desk/desk.ipt", "Vessel/Probe/probe-head.iam"]
    # The folder line is a real link to the folder page, beside an Open folder
    # action; both sit outside the part link, which keeps preview and name.
    assert (
        '<a class="hero-folder" href="/catalog/Vessel/Probe" title="Open the folder Vessel\\Probe">'
        "Vessel\\Probe</a>"
    ) in heroes
    assert '<a class="hero-open-folder" href="/catalog/Vessel/Probe">Open folder</a>' in heroes
    assert '<a class="hero-folder" href="/catalog/Desk"' in heroes
    part_link = heroes.split('href="/part/Desk/desk.ipt"', 1)[1].split("</a>", 1)[0]
    assert '<span class="hero-name">desk.ipt</span>' in part_link and "<img" in part_link
    assert "/catalog/" not in part_link
    assert client.get("/catalog/Vessel/Probe").status_code == 200
    assert "data-inspector" in after


def test_a_folder_strip_opens_with_the_heroes_below_it(tmp_path: Path) -> None:
    root = make_hero_workspace(tmp_path)
    app = create_app(root)
    client = app.test_client()
    post_hero(app, client, "Vessel/Probe/tip.ipt", True, "Vessel/Probe")

    html = client.get("/catalog").get_data(as_text=True)
    card = html.split('class="folder-card" href="/catalog/Vessel"', 1)[1].split("</a>", 1)[0]
    strip = re.findall(r'src="/preview/([^"?]+)\?v=', card)

    assert strip[0] == "Vessel/Probe/tip.ipt"
    assert strip.count("Vessel/Probe/tip.ipt") == 1


def test_folder_strips_put_leading_records_first_without_repeating_them() -> None:
    record = web.FileRecord
    records = [
        record(path, path.rsplit("/", 1)[-1], path.casefold(), "." + path.rsplit(".", 1)[-1], 1, 1, None, "A")
        for path in ("A/B/one.ipt", "A/B/two.ipt", "A/B/C/main.iam", "A/D/three.ipt")
    ]
    hero = records[2]

    strips = web.folder_strips(records, "A", limit=2, leading=(hero,))

    assert [item.path for item in strips["A/B"]] == ["A/B/C/main.iam", "A/B/one.ipt"]
    assert [item.path for item in strips["A/D"]] == ["A/D/three.ipt"]


def test_part_page_sets_and_clears_hero_next_to_the_sidecar(tmp_path: Path) -> None:
    root = make_hero_workspace(tmp_path)
    app = create_app(root)
    client = app.test_client()
    companion = root / "Vessel" / "flange.ipt.md"
    companion.write_text(
        "---\nstatus: draft\n---\n\nThe flange the whole vessel hangs from.\n", encoding="utf-8"
    )

    page = client.get("/part/Vessel/flange.ipt").get_data(as_text=True)
    card = page.split('<section class="part-card metadata-card">', 1)[1]
    assert card.index('class="hero-toggle"') < card.index('class="featured-toggle"') < card.index("Edit raw text")
    assert '<input type="hidden" name="hero" value="1">' in card
    assert "Main assembly <b>off</b></button>" in card
    assert "data-flag-confirm" not in card  # setting needs no confirmation

    response = post_hero(app, client, "Vessel/flange.ipt", True, "part")
    assert response.headers["Location"] == "/part/Vessel/flange.ipt?hero=set&file=Vessel/flange.ipt"
    assert companion.read_text(encoding="utf-8") == (
        "---\nstatus: draft\nhero: true\n---\n\nThe flange the whole vessel hangs from.\n"
    )
    marked = client.get(response.headers["Location"]).get_data(as_text=True)
    assert "Hero set: flange.ipt" in marked
    assert "Main assembly <b>on</b></button>" in marked and 'aria-pressed="true"' in marked
    hero_form = marked.split('<form class="hero-toggle"', 1)[1].split("</form>", 1)[0]
    assert (
        'data-flag-confirm="Clear hero on flange.ipt? It stays in its folder; '
        'only the Main assemblies placement goes."'
    ) in hero_form
    assert '<i class="signal-mark signal-hero"></i>Main assembly' in marked

    post_hero(app, client, "Vessel/flange.ipt", False, "part")
    assert companion.read_text(encoding="utf-8") == (
        "---\nstatus: draft\n---\n\nThe flange the whole vessel hangs from.\n"
    )


def test_hero_toggle_refuses_a_sidecar_it_cannot_parse(tmp_path: Path) -> None:
    root = make_hero_workspace(tmp_path)
    app = create_app(root)
    client = app.test_client()
    companion = root / "Vessel" / "flange.ipt.md"
    companion.write_bytes(b"---\nstatus: shipped\n---\n\nKeep me.\n")

    response = post_hero(app, client, "Vessel/flange.ipt", True, "Vessel")

    assert response.status_code == 400
    assert "the sidecar was not changed" in response.get_data(as_text=True)
    assert companion.read_bytes() == b"---\nstatus: shipped\n---\n\nKeep me.\n"


def test_hero_lookup_stats_sidecars_and_reads_one_only_when_it_changed(
    tmp_path: Path, monkeypatch
) -> None:
    root = make_hero_workspace(tmp_path)
    companion = root / "Desk" / "desk.ipt.md"
    companion.write_text("---\nhero: true\n---\n", encoding="utf-8")
    app = create_app(root)
    client = app.test_client()
    reads: list[str] = []
    original = web.read_sidecar

    def counting(path):
        reads.append(Path(path).name)
        return original(path)

    monkeypatch.setattr(web, "read_sidecar", counting)

    first = client.get("/catalog/Vessel/parts").get_data(as_text=True)
    second = client.get("/catalog/Vessel/parts").get_data(as_text=True)
    assert reads.count("desk.ipt.md") == 1  # read once, then known by its stat
    assert "Main assemblies" not in first + second  # Desk's hero belongs to Desk

    # An edit outside the viewer is seen at the next disk validation.
    companion.write_text("---\nstatus: draft\n---\n\nNo longer the main one.\n", encoding="utf-8")
    assert "hero-block" not in client.get("/catalog").get_data(as_text=True)
    assert reads.count("desk.ipt.md") == 2


def test_hero_styles_pin_the_file_tile_width_and_every_mark_is_a_dot(tmp_path: Path) -> None:
    style = create_app(tmp_path).test_client().get("/static/dedup.css").get_data(as_text=True)
    script = create_app(tmp_path).test_client().get("/static/dedup.js").get_data(as_text=True)
    rules = re.findall(r"([^{}]+)\{([^{}]*)\}", style)

    # Main assemblies share the file grid's column: nothing widens a hero card
    # or its grid, and its preview uses the file tile's 4:3 rule.
    assert ".thumb-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(148px, 1fr));" in style
    for selector, body in rules:
        if "hero" in selector:
            assert "grid-column" not in body and "grid-template-columns" not in body, selector
    assert ".hero-tile img" not in style
    assert ".thumb-tile img { display: block; width: 100%; height: auto; aspect-ratio: 4 / 3;" in style
    name_rule = style.split(".hero-name {", 1)[1].split("}", 1)[0]
    assert "ellipsis" not in name_rule and "nowrap" not in name_rule  # names wrap
    folder_rule = style.split(".hero-folder {", 1)[1].split("}", 1)[0]
    assert "text-decoration: underline" in folder_rule and "var(--accent)" in folder_rule

    # No tile or card rule draws a coloured edge or bar as a mark: every
    # signal is a dot in the corner.
    card_classes = (".thumb-tile", ".hero-card", ".hero-tile", ".folder-card")
    for selector, body in rules:
        if not any(name in selector for name in card_classes):
            continue
        assert "border-left" not in body and "border-top" not in body, selector
        assert "inset 0 3px" not in body and "inset 3px" not in body, selector
        assert "::before" not in selector, selector
    assert "data-edge" not in style and "is-bar" not in style and "is-edge" not in style

    hues = {
        name: style.split(f"--{name}:", 1)[1].split(";", 1)[0].strip()
        for name in ("hero", "featured", "collision", "exact", "renamed", "accent")
    }
    assert len(set(hues.values())) == len(hues)
    assert "#d79b4b" not in (hues["hero"], hues["featured"])  # the "newer file" dot
    assert ".signal-hero { background: var(--hero); }" in style
    assert ".signal-featured { background: var(--featured); }" in style
    # The inspector has no hero button; the part page's clear asks first.
    assert "heroForm" not in script and "data-inspector-hero" not in script
    assert "window.confirm(form.dataset.flagConfirm)" in script
    assert 'window.location.hash.indexOf("#file-") === 0' in script
    # The hero card's folder links prefetch like every other folder link.
    assert "a.hero-folder, a.hero-open-folder" in script

def test_the_folder_note_rail_renders_the_authored_part_in_a_fixed_budget(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    (root / "BoronProbe" / "parts" / "README.md").write_text(
        "# parts\n\nThe **PAEK** bearing stack.\n\n## Servicing\n\n- clean the ceramics\n\n"
        "## Main Assembly\n\n- **`bearing.iam`** — selected from the assemblies below\n\n"
        "## Assemblies (`.iam`)\n\n- `bearing.iam`\n\n"
        "> Generated CAD inventory — 2026-08-06. To document purpose or status, edit this file.\n\n"
        "## Parts (`.ipt`)\n\n- `bearing.ipt`\n",
        encoding="utf-8",
    )
    (root / "Plasma Vessel" / "parts" / "README.md").write_text(
        "<!-- This file was generated by scripts/generate_readmes.py -->\n\n# parts\n\n"
        "> Generated CAD inventory — 2026-08-06.\n\n## Parts (`.ipt`)\n\n- `bearing.ipt`\n",
        encoding="utf-8",
    )
    client = create_app(root).test_client()

    authored = client.get("/catalog/BoronProbe/parts").get_data(as_text=True)
    generated = client.get("/catalog/Plasma%20Vessel/parts").get_data(as_text=True)
    missing = client.get("/catalog/BoronProbe_2026/parts").get_data(as_text=True)

    rail = authored.split("data-note-rail-body>", 1)[1].split("</div>", 1)[0]
    assert rail.startswith("<p>The <strong>PAEK</strong> bearing stack.</p>")
    assert "<h2>Servicing</h2>" in rail and "clean the ceramics" in rail
    assert "Main Assembly" not in rail and "Generated CAD inventory" not in rail
    assert "<h1>" not in rail  # the rail already names the folder
    for page in (generated, missing):
        note = page.split('<div class="note-rail" data-note-rail>', 1)[1].split("</div>", 1)[0]
        assert '<p class="note-rail-empty">No note yet</p>' in note
        assert 'data-note-view="editor"' in note and ">Write one</button>" in note

    # One fixed budget: the Note card never grows, so the inspector below it
    # sits at the same place whatever the note's length.
    style = client.get("/static/dedup.css").get_data(as_text=True)
    budget = style.split(".note-rail {", 1)[1].split("}", 1)[0]
    # 11rem on any desktop window taller than ~850px; one budget for every folder.
    assert "height: clamp(5rem, calc(100vh - 42rem), 11rem);" in budget
    assert "max-height" not in budget
    body_rule = style.split(".note-rail-body {", 1)[1].split("}", 1)[0]
    assert "overflow: hidden;" in body_rule and "min-height: 0;" in body_rule

    def skeleton(html: str) -> list[str]:
        context = html.split('<aside class="rail-side rail-context"', 1)[1].split("</aside>", 1)[0]
        context = re.sub(r"<div class=\"note-rail\" data-note-rail>.*?</button>\s*</div>", "NOTE", context, flags=re.S)
        return re.findall(r'class="([^"]+)"', context)

    assert skeleton(authored) == skeleton(generated) == skeleton(missing)


def test_the_folder_note_modal_opens_as_a_reader_with_the_editor_behind_edit(
    tmp_path: Path,
) -> None:
    app = create_app(make_workspace(tmp_path))
    client = app.test_client()
    (tmp_path / "BoronProbe" / "parts" / "README.md").write_text(
        "# parts\n\nPAEK bearing stack.\n", encoding="utf-8"
    )

    html = client.get("/catalog/BoronProbe/parts").get_data(as_text=True)
    dialog = html.split('<dialog class="note-dialog"', 1)[1].split("</dialog>", 1)[0]
    script = client.get("/static/dedup.js").get_data(as_text=True)

    assert 'data-note-view="reader"' in dialog.split(">", 1)[0]
    reader = dialog.split('<section class="note-reader"', 1)[1].split("</section>", 1)[0]
    assert "data-note-reader>" in reader and "<p>PAEK bearing stack.</p>" in reader
    assert '<div class="note-dialog-grid" data-note-editor hidden>' in dialog
    assert 'id="catalog-folder-note-text"' in dialog  # present, only hidden
    tools = dialog.split('<div class="note-dialog-tools">', 1)[1].split("</div>", 1)[0]
    assert tools.index("data-note-edit") < tools.index("dialog-close-x")
    assert 'aria-pressed="false">Edit</button>' in tools
    assert "setView(dialog, opener.dataset.noteView)" in script

    saved = client.post(
        "/folder/BoronProbe/parts/note",
        data={"token": app.config["FORM_TOKEN"], "origin": "catalog", "text": "# parts\n\nSaved.\n"},
    )
    reopened = client.get(saved.headers["Location"]).get_data(as_text=True)
    assert 'data-auto-open data-note-view="reader"' in reopened  # lands in the reader
    refused = client.post(
        "/folder/BoronProbe/parts/note",
        data={"token": app.config["FORM_TOKEN"], "origin": "catalog", "text": "  \n"},
    ).get_data(as_text=True)
    assert 'data-auto-open data-note-view="editor"' in refused  # an error stays in the editor
    assert '<div class="note-dialog-grid" data-note-editor>' in refused


def test_the_inspector_states_main_assembly_and_carries_no_hero_form(tmp_path: Path) -> None:
    root = make_hero_workspace(tmp_path)
    app = create_app(root)
    client = app.test_client()
    post_hero(app, client, "Vessel/vessel-main.iam", True, "part")

    for address in ("/catalog", "/catalog/Vessel"):
        html = client.get(address).get_data(as_text=True)
        inspector = html.split('<section class="rail-card inspector"', 1)[1].split("</section>", 1)[0]
        assert "<h2>Inspector</h2>" in inspector
        assert "<form" not in inspector and "<button" not in inspector
        assert "hero" not in inspector.casefold()
        # The fact the inspector copies is in the tile's hidden details.
        assert "<dd>Main assembly</dd>" in html


def test_featured_leads_folder_cards_without_a_main_assemblies_place(tmp_path: Path) -> None:
    root = make_hero_workspace(tmp_path)
    app = create_app(root)
    client = app.test_client()
    companion = root / "Vessel" / "parts" / "spacer.ipt.md"

    response = client.post(
        "/part/Vessel/parts/spacer.ipt/featured",
        data={"token": app.config["FORM_TOKEN"], "featured": "1", "origin": "part"},
    )
    assert response.headers["Location"] == (
        "/part/Vessel/parts/spacer.ipt?featured=set&file=Vessel/parts/spacer.ipt"
    )
    assert read_sidecar(companion).featured is True and read_sidecar(companion).hero is False

    page = client.get(response.headers["Location"]).get_data(as_text=True)
    assert "Featured set: spacer.ipt" in page
    assert "Feature on folder card <b>on</b></button>" in page
    assert "Main assembly <b>off</b></button>" in page
    featured_form = page.split('<form class="featured-toggle"', 1)[1].split("</form>", 1)[0]
    assert 'data-flag-confirm="Clear featured on spacer.ipt?' in featured_form
    assert '<i class="signal-mark signal-featured"></i>Featured' in page

    top = client.get("/catalog").get_data(as_text=True)
    assert "hero-block" not in top  # featured is not a main assembly
    card = top.split('class="folder-card" href="/catalog/Vessel"', 1)[1].split("</a>", 1)[0]
    assert re.findall(r'src="/preview/([^"?]+)\?v=', card)[0] == "Vessel/parts/spacer.ipt"

    folder = client.get("/catalog/Vessel/parts").get_data(as_text=True)
    tile = folder.split('href="/part/Vessel/parts/spacer.ipt"', 1)[1].split("</a>", 1)[0]
    assert '<i class="signal-dot signal-featured"></i>' in tile
    assert '<i class="signal-mark signal-featured"></i></dt><dd>Featured</dd>' in tile
    legend = folder.split('<section class="rail-card signal-legend">', 1)[1].split("</section>", 1)[0]
    assert "<li><i class=\"signal-mark signal-featured\"></i>Featured: leads its folder&#39;s card</li>" in legend

    cleared = client.post(
        "/part/Vessel/parts/spacer.ipt/featured",
        data={"token": app.config["FORM_TOKEN"], "featured": "0", "origin": "part"},
    )
    assert "featured=cleared" in cleared.headers["Location"]
    assert "featured" not in read_sidecar(companion).frontmatter


def test_signal_dots_and_legend_share_one_order_with_hero_then_featured_last(tmp_path: Path) -> None:
    root = make_hero_workspace(tmp_path)
    other = root / "Desk" / "flange.ipt"
    other.write_bytes(b"another flange")  # a filename collision, the older member
    os.utime(other, ns=(1_700_000_000_000_000_000, 1_700_000_000_000_000_000))
    app = create_app(root)
    client = app.test_client()
    client.get("/duplicates/results")
    for flag in ("hero", "featured"):
        client.post(
            f"/part/Vessel/flange.ipt/{flag}",
            data={"token": app.config["FORM_TOKEN"], flag: "1", "origin": "part"},
        )

    html = client.get("/catalog/Vessel").get_data(as_text=True)
    tile = html.split('href="/part/Vessel/flange.ipt"', 1)[1].split("</a>", 1)[0]
    dots = re.findall(r'<i class="signal-dot signal-([a-z]+)"></i>', tile)
    facts = re.findall(r'<i class="signal-mark signal-([a-z]+)"></i>', tile)
    legend = html.split('<section class="rail-card signal-legend">', 1)[1].split("</section>", 1)[0]
    kinds = re.findall(r'<i class="signal-mark signal-([a-z]+)"></i>', legend)

    assert dots == facts == ["collision", "hero", "featured"]
    assert kinds == ["collision", "hero", "featured"]
    assert [kind for kind, _text in web.SIGNAL_LEGEND] == [
        "collision", "exact", "renamed", "unverified", "generic", "newer", "hero", "featured"
    ]


def test_folder_card_strips_lead_with_heroes_then_featured_in_every_ancestor(tmp_path: Path) -> None:
    for relative in (
        "PV/Cathode/a-part.ipt",
        "PV/Cathode/z-main.iam",
        "PV/Flange/b-part.ipt",
        "PV/Flange/y-feature.ipt",
        "PV/Pump/c-part.ipt",
        "PV/Pump/d-part.ipt",
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    app = create_app(tmp_path)
    client = app.test_client()
    token = app.config["FORM_TOKEN"]
    client.post("/part/PV/Cathode/z-main.iam/hero", data={"token": token, "hero": "1", "origin": "part"})
    client.post(
        "/part/PV/Flange/y-feature.ipt/featured",
        data={"token": token, "featured": "1", "origin": "part"},
    )

    def strip(address: str, folder: str) -> list[str]:
        html = client.get(address).get_data(as_text=True)
        card = html.split(f'class="folder-card" href="/catalog/{folder}"', 1)[1].split("</a>", 1)[0]
        return re.findall(r'src="/preview/([^"?]+)\?v=', card)

    # The root's PV card: hero, featured, then one pick per subfolder that has
    # not led yet, then the second round.
    assert strip("/catalog", "PV") == [
        "PV/Cathode/z-main.iam",
        "PV/Flange/y-feature.ipt",
        "PV/Pump/c-part.ipt",
        "PV/Cathode/a-part.ipt",
        "PV/Flange/b-part.ipt",
        "PV/Pump/d-part.ipt",
    ]
    # One level down, each subfolder's own card leads the same way.
    assert strip("/catalog/PV", "PV/Cathode")[0] == "PV/Cathode/z-main.iam"
    assert strip("/catalog/PV", "PV/Flange")[0] == "PV/Flange/y-feature.ipt"
    assert strip("/catalog/PV", "PV/Pump") == ["PV/Pump/c-part.ipt", "PV/Pump/d-part.ipt"]


def make_strip_records(paths, sizes=None):
    sizes = sizes or {}
    return [
        web.FileRecord(
            path, path.rsplit("/", 1)[-1], path.casefold(), "." + path.rsplit(".", 1)[-1],
            sizes.get(path, 1), 1, None, "A",
        )
        for path in paths
    ]


def test_folder_strip_defaults_take_one_from_each_subfolder_before_a_second() -> None:
    paths = [f"Box/{drawer}/{index}.ipt" for drawer in ("a", "b", "c") for index in range(5)]
    records = make_strip_records(paths)

    plain = web.folder_strips(records, ".")
    assert [item.path for item in plain["Box"]] == [
        "Box/a/0.ipt", "Box/b/0.ipt", "Box/c/0.ipt", "Box/a/1.ipt", "Box/b/1.ipt", "Box/c/1.ipt"
    ]
    # A hero still comes first, and its drawer sits out the round it covered.
    hero = next(record for record in records if record.path == "Box/c/4.ipt")
    led = web.folder_strips(records, ".", leading=(hero,))
    assert [item.path for item in led["Box"]] == [
        "Box/c/4.ipt", "Box/a/0.ipt", "Box/b/0.ipt", "Box/a/1.ipt", "Box/b/1.ipt", "Box/c/0.ipt"
    ]


def test_folder_strip_representatives_are_ranked_assembly_first() -> None:
    holder = ["Box/holder/main.iam"] + [f"Box/holder/tiny-{index:02d}.ipt" for index in range(10)]
    drawer = ["Box/drawer/bolt.ipt", "Box/drawer/washer.ipt"]
    exports = ["Box/exports/cached.stl", "Box/exports/fresh.step"]
    nested = ["Box/nested/sub.iam", "Box/nested/top.iam"]
    sizes = {path: 50 for path in holder[1:]}
    sizes.update({"Box/holder/main.iam": 5, "Box/drawer/washer.ipt": 9, "Box/drawer/bolt.ipt": 3})
    sizes.update({"Box/nested/sub.iam": 99, "Box/nested/top.iam": 1})
    records = make_strip_records(holder + drawer + exports + nested, sizes)

    def top_level(record) -> bool:
        return record.path != "Box/nested/sub.iam"  # top.iam references sub.iam

    def rendered(record) -> bool:
        return record.path == "Box/exports/cached.stl"

    strips = web.folder_strips(records, ".", top_level=top_level, rendered=rendered)
    picks = [item.path for item in strips["Box"]]

    # Round one, subfolders in name order: the drawer's largest part, the
    # export whose render is cached, the holder's assembly (not one of its
    # larger tiny parts), and the top-level assembly over a larger sub-assembly.
    assert picks[:4] == [
        "Box/drawer/washer.ipt",
        "Box/exports/cached.stl",
        "Box/holder/main.iam",
        "Box/nested/top.iam",
    ]
    assert picks[4:] == ["Box/drawer/bolt.ipt", "Box/holder/tiny-00.ipt"]
    assert "Box/exports/fresh.step" not in picks  # an uncached export only tops up

    hero = next(record for record in records if record.path == "Box/holder/tiny-09.ipt")
    led = web.folder_strips(records, ".", leading=(hero,), top_level=top_level, rendered=rendered)
    assert [item.path for item in led["Box"]][:2] == ["Box/holder/tiny-09.ipt", "Box/drawer/washer.ipt"]
