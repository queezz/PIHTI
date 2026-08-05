import os
import re
from pathlib import Path

import pihti_dedup.web as web
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

    html = client.get("/catalog").get_data(as_text=True)
    rail = html.split('<aside class="rail-side"', 1)[1]

    assert rail.index("<h2>Scan</h2>") < rail.index("<h2>Folders</h2>")
    assert "data-folder-tree" in html
    # The two BoronProbe subfolders collapse under one top-level node carrying both.
    assert 'data-tree-toggle="BoronProbe"' in html
    assert 'data-tree-children="BoronProbe"' in html
    assert 'data-tree-children="BoronProbe" hidden' in html
    assert 'aria-expanded="false"' in html
    assert "rail-navrow" not in html


def test_the_catalog_section_header_shows_the_folder_note_excerpt(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    (root / "BoronProbe" / "parts" / "README.md").write_text(
        "# parts\n\nPAEK bearing stack for the rotating head.\n", encoding="utf-8"
    )
    client = create_app(root).test_client()

    html = client.get("/catalog").get_data(as_text=True)

    assert "PAEK bearing stack for the rotating head." in html
    assert "No folder note yet." in html
    assert 'action="/folder/BoronProbe/parts/note"' in html


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

    catalog_html = client.get("/catalog").get_data(as_text=True)
    folder_html = client.get("/folder/BoronProbe/parts").get_data(as_text=True)

    for html in (catalog_html, folder_html):
        assert "This file was generated by scripts/generate_readmes.py" not in html
        assert "claims it as your folder note" not in html  # the comment block itself
        assert "## Purpose" in html  # the rest of the generated body is still editable
        assert (
            "Generated index — edit and save to make it your folder note; "
            "the generator will then leave this file alone." in html
        )


def test_a_manually_edited_readme_is_shown_as_is_with_no_generated_hint(tmp_path: Path) -> None:
    root = make_workspace(tmp_path)
    manual = "# parts\n\nHand-written prose about the bearing stack.\n"
    (root / "BoronProbe" / "parts" / "README.md").write_text(manual, encoding="utf-8")
    client = create_app(root).test_client()

    catalog_html = client.get("/catalog").get_data(as_text=True)
    folder_html = client.get("/folder/BoronProbe/parts").get_data(as_text=True)

    for html in (catalog_html, folder_html):
        assert "Hand-written prose about the bearing stack." in html
        assert "Generated index — edit and save to make it your folder note" not in html


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
    assert 'TREE_KEY = "pihti-catalog-tree"' in script
    assert "localStorage.setItem(TREE_KEY" in script
    assert "data-copy-text" in script
    assert "data-rename-settled" in script
    assert "data-rename-search" in script


def test_styles_indent_the_folder_tree_without_an_inner_scrollbar(tmp_path: Path) -> None:
    style = create_app(tmp_path).test_client().get("/static/dedup.css").get_data(as_text=True)

    assert ".folder-tree" in style
    assert "var(--tree-depth, 0)" in style  # depth indent, not a nested scroll container
    assert "overflow-y: auto" not in style
    assert "overflow-y: scroll" not in style
    # The owner rejected inner scrolling: nothing may be given a height ceiling.
    assert re.search(r"max-height:\s*\d", style) is None
