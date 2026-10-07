"""Reversible assembly deferrals; never permit an unsafe Inventor open."""

import json
import os
import tempfile
import threading
from pathlib import Path

STORE = Path(".agents/doctor-later.json")
LOCK = threading.RLock()


def read(root):
    try:
        value = json.loads((Path(root) / STORE).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if (
        not isinstance(value, dict)
        or value.get("version") != 1
        or not isinstance(value.get("assemblies"), dict)
    ):
        raise ValueError("Invalid Doctor later record")
    return value["assemblies"]


def active(root):
    result = {}
    for key, entry in read(root).items():
        path = (Path(root) / entry["path"]).resolve()
        if not path.is_relative_to(Path(root).resolve()):
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        if stat.st_mtime_ns == entry["mtime_ns"] and stat.st_size == entry["size"]:
            result[key] = entry
    return result


def set_later(root, relative, blocker=None):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or path.suffix.lower() != ".iam" or not path.is_file():
        raise ValueError("Choose a workspace assembly")
    relative = path.relative_to(root).as_posix()
    with LOCK:
        entries = read(root)
        if blocker is None:
            entries.pop(relative.casefold(), None)
        else:
            stat = path.stat()
            entries[relative.casefold()] = {
                "path": relative,
                "mtime_ns": stat.st_mtime_ns,
                "size": stat.st_size,
                "reference": blocker[0],
                "reason": blocker[1],
            }
        destination = root / STORE
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=destination.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump({"version": 1, "assemblies": entries}, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        try:
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
