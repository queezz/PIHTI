import tomllib
from pathlib import Path

from pihti_dedup import __version__


def test_version_matches_pyproject() -> None:
    document = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert document["project"]["version"] == __version__
