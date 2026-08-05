from pathlib import Path

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

    results = client.get("/duplicates/results")
    result_html = results.get_data(as_text=True)
    assert results.status_code == 200
    assert "bearing.ipt" in result_html
    assert "different bytes" in result_html
    assert "data-filter-search" in result_html
    assert "data-include-vendor" in result_html


def test_json_endpoint_and_vendor_toggle_share_the_inventory_contract(tmp_path: Path) -> None:
    client = create_app(make_workspace(tmp_path)).test_client()

    default = client.get("/duplicates/data").get_json()
    vendor = client.get("/duplicates/data?include_vendor=1").get_json()

    assert default["summary"]["files"] == 3
    assert default["summary"]["collision_groups"] == 1
    assert vendor["summary"]["files"] == 4
    assert vendor["scope"]["include_vendor"] is True


def test_health_names_read_only_service(tmp_path: Path) -> None:
    payload = create_app(tmp_path).test_client().get("/health").get_json()

    assert payload["status"] == "ok"
    assert payload["service"] == "pihti-dedup"
    assert payload["read_only"] is True


def test_packaged_script_contains_filter_and_rescan_behaviour(tmp_path: Path) -> None:
    client = create_app(tmp_path).test_client()
    script = client.get("/static/dedup.js").get_data(as_text=True)

    assert "applyFilters" in script
    assert "include_vendor" in script
    assert "navigator.clipboard.writeText" in script
