import json
from pathlib import Path

from pihti_dedup.cli import main
from pihti_dedup.legacy import main as legacy_main


def test_scan_command_writes_portable_json(tmp_path: Path, capsys) -> None:
    (tmp_path / "one").mkdir()
    (tmp_path / "two").mkdir()
    (tmp_path / "one" / "part.ipt").write_bytes(b"same")
    (tmp_path / "two" / "part.ipt").write_bytes(b"same")
    output = tmp_path / "inventory.json"

    assert main(["scan", str(tmp_path), "--json", str(output)]) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["root"] == "."
    assert payload["summary"]["exact_groups"] == 1
    assert "same-name/exact-copy groups: 1" in capsys.readouterr().out


def test_legacy_cli_retains_old_summary_and_group_keys(tmp_path: Path, capsys) -> None:
    (tmp_path / "one").mkdir()
    (tmp_path / "two").mkdir()
    (tmp_path / "one" / "part.ipt").write_bytes(b"same")
    (tmp_path / "two" / "part.ipt").write_bytes(b"same")
    output = tmp_path / "legacy.json"

    assert legacy_main([str(tmp_path), "--extensions", ".ipt", "--json", str(output)]) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["root"] == str(tmp_path.resolve())
    assert set(payload["files"][0]) == {"path", "name", "suffix", "size", "mtime_ns", "sha256"}
    assert "hash_duplicates" in payload["groups"]
    assert "same_name_same_size" in payload["groups"]
    assert "hash duplicate groups: 1" in capsys.readouterr().out
