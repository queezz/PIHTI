import os
from pathlib import Path

import pihti_dedup.web as web
from pihti_dedup.cleanup import plan_member_cleanup
from pihti_dedup.git_history import PullRequestMerge
from pihti_dedup.inventor_meta import DocumentMeta, Preview
from pihti_dedup.inventory import scan_workspace
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

    shell = client.get("/duplicates")
    html = shell.get_data(as_text=True)
    assert shell.status_code == 200
    assert 'id="dup-results"' in html
    assert 'data-src="/duplicates/results"' in html
    assert "bearing.ipt" not in html
    assert "page-heading" not in html
    assert 'href="/static/favicon.ico"' in html

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


def test_catalog_lists_every_folder_as_a_thumbnail_grid(tmp_path: Path) -> None:
    client = create_app(make_workspace(tmp_path)).test_client()

    html = client.get("/catalog").get_data(as_text=True)

    assert 'class="thumb-grid"' in html
    assert "BoronProbe\\parts" in html
    assert 'href="/part/Plasma%20Vessel/parts/bearing.ipt"' in html
    assert 'src="/preview/Plasma%20Vessel/parts/bearing.ipt"' in html
    assert "Design Data" not in html
    assert html.count("data-catalog-item") == 3
    assert 'class="work-grid one-rail"' in html


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


def test_packaged_script_filters_the_catalog_without_a_rescan(tmp_path: Path) -> None:
    script = create_app(tmp_path).test_client().get("/static/dedup.js").get_data(as_text=True)

    assert "data-catalog-search" in script
    assert "data-catalog-item" in script
    assert "filterCatalog" in script
