import os
import re
import struct
from pathlib import Path

import pytest

import pihti_dedup.web as web
from pihti_dedup import geometry_preview
from pihti_dedup.cleanup import plan_member_cleanup
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
    assert html.index(">Catalog</a>") < html.index(">Duplicates</a>") < html.index(">Renames</a>")

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
    assert result_html.count('data-copy="') == 3
    assert 'data-copy="BoronProbe_2026\\parts\\bearing.ipt"' in result_html
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
    merge = PullRequestMerge(
        sha="a" * 40,
        number=3,
        branch="queezz/BoronProbe-update",
        paths=frozenset({"BoronProbe_2026/parts/bearing.ipt"}),
        folders=("BoronProbe_2026",),
        added_paths=frozenset({"BoronProbe_2026/parts/bearing.ipt"}),
    )
    client = create_app(make_workspace(tmp_path), merge_reader=lambda _root: (merge,)).test_client()

    result_html = client.get("/duplicates/results").get_data(as_text=True)

    assert "PR #3" in result_html
    assert "BoronProbe-update" in result_html
    assert 'data-merge-filter="3"' in result_html
    assert 'data-merges="3"' in result_html
    assert 'class="rail-side rail-primary"' in result_html
    assert 'class="rail-side rail-secondary"' in result_html


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
    assert "Delete this file from the Inventor workspace?" in script
    assert 'FILTER_KEY = "pihti-dedup-filter"' in script
    assert "localStorage.setItem(FILTER_KEY" in script
    assert "captureViewportAnchor" in script
    assert "restoreViewportAnchor" in script
    assert "preserveView: true" in script
    assert "showToast" in script


def test_styles_keep_desktop_rail_at_its_initial_top_offset(tmp_path: Path) -> None:
    client = create_app(tmp_path).test_client()
    style = client.get("/static/dedup.css").get_data(as_text=True)

    assert "top: calc(var(--bar-height) + var(--content-pad));" in style
    assert ".summary-strip" not in style
    assert "grid-template-columns: minmax(0, 1fr) 17rem 17rem" in style
    assert "overflow-y: auto" not in style
    assert ".operation-toast" in style
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
    assert (tmp_path / payload["execution"]["manifest"]).exists()


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
    assert (tmp_path / payload["execution"]["manifest"]).exists()


def make_document(**fields) -> DocumentMeta:
    return DocumentMeta(path="stub", ok=True, fields=fields)


def test_duplicate_rows_show_a_preview_and_link_to_the_part_page(tmp_path: Path) -> None:
    client = create_app(make_workspace(tmp_path)).test_client()

    result_html = client.get("/duplicates/results").get_data(as_text=True)

    assert result_html.count('class="member-thumb"') == 3
    assert 'src="/preview/BoronProbe_2026/parts/bearing.ipt"' in result_html
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

    assert 'src="/preview/BoronProbe/exports/head.stl"' in part
    assert "rendered from the geometry" in part
    assert 'src="/preview/BoronProbe/exports/head.stl"' in catalog
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

    page = client.get("/catalog")
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
    assert 'src="/preview/A/head.stl"' in html
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
    assert 'src="/preview/BoronProbe/parts/bearing.ipt"' not in landing
    assert 'href="/catalog/BoronProbe/parts"' in system
    assert 'src="/preview/BoronProbe/parts/bearing.ipt"' not in system
    assert 'href="/part/BoronProbe/parts/bearing.ipt"' in folder
    assert 'src="/preview/BoronProbe/parts/bearing.ipt"' in folder
    assert folder.count('class="thumb-tile"') == 1
    assert "Design Data" not in landing
    assert 'class="work-grid one-rail"' in landing
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
    assert '<p class="catalog-description">Holds the plasma box inside the full vacuum vessel assembly.</p>' in folder


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


def test_catalog_rail_pins_the_scan_card_above_a_collapsible_folder_tree(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    (root / "BoronProbe" / "drawings").mkdir()
    (root / "BoronProbe" / "drawings" / "bearing.idw").write_bytes(b"drawing")
    client = create_app(root).test_client()

    landing = client.get("/catalog").get_data(as_text=True)
    current = client.get("/catalog/BoronProbe/parts").get_data(as_text=True)
    rail = landing.split('<aside class="rail-side"', 1)[1]

    assert rail.index("<h2>Catalog</h2>") < rail.index("<h2>Folders</h2>")
    assert "data-folder-tree" in landing
    # The two BoronProbe subfolders collapse under one top-level node carrying both.
    assert 'data-tree-toggle="BoronProbe" aria-expanded="false"' in landing
    assert 'data-tree-children="BoronProbe" hidden' in landing
    # Navigating opens only the current ancestry and marks the leaf.
    assert 'data-tree-toggle="BoronProbe" aria-expanded="true"' in current
    assert 'data-tree-children="BoronProbe">' in current
    assert 'href="/catalog/BoronProbe/parts" title="BoronProbe\\parts" aria-current="page"' in current
    assert "rail-navrow" not in landing


def test_the_catalog_section_header_shows_the_folder_note_excerpt(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    (root / "BoronProbe" / "parts" / "README.md").write_text(
        "# parts\n\nPAEK bearing stack for the rotating head.\n", encoding="utf-8"
    )
    client = create_app(root).test_client()

    html = client.get("/catalog/BoronProbe").get_data(as_text=True)

    assert "PAEK bearing stack for the rotating head." in html


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
    assert "The PAEK bearing stack." in html  # launch excerpt is plain text
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

    assert "Inventor will ask." in page
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


def test_styles_indent_the_folder_tree_without_an_inner_scrollbar(tmp_path: Path) -> None:
    style = create_app(tmp_path).test_client().get("/static/dedup.css").get_data(as_text=True)

    assert ".folder-tree" in style
    assert "var(--tree-depth, 0)" in style  # depth indent, not a nested scroll container
    assert ".note-dialog::backdrop" in style
    assert ".dialog-close-x" in style
    assert ".thumb-tile.has-metadata" in style
    assert ".thumb-tile.has-story" in style
    assert "grid-column: span 2" in style
    assert ".folder-card.has-summary" in style
    assert "-webkit-line-clamp: 2" in style
    assert "grid-template-columns: minmax(0, 1.08fr) minmax(0, 0.92fr)" in style
    assert "overflow-y: auto" not in style
    assert "overflow-y: scroll" not in style
    # The owner rejected inner scrolling: nothing may be given a height ceiling.
    assert re.search(r"max-height:\s*\d", style) is None
