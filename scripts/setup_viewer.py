"""One-time Windows student setup; the environment always lives outside the checkout."""

from __future__ import annotations

import subprocess
import sys
import venv
from pathlib import Path


def main() -> int:
    if sys.platform != "win32" or sys.version_info < (3, 12):
        print("Use an installed Windows Python 3.12 or newer executable.")
        return 2
    executable = Path(sys.executable).resolve()
    if "windowsapps" in str(executable).casefold():
        print("Choose the installed Python executable, not the WindowsApps alias.")
        return 2
    root = Path(__file__).resolve().parent.parent
    environment = Path.home() / ".venvs" / "pihti-dedup"
    if environment.resolve().is_relative_to(root):
        print("The environment must live outside the repository.")
        return 2
    python = environment / "Scripts" / "python.exe"
    if not python.exists():
        if environment.exists():
            print("The existing pihti-dedup environment has no Python. Repair it before retrying.")
            return 2
        venv.EnvBuilder(with_pip=True).create(environment)
    subprocess.run(
        [str(python), "-c", "import sys; assert sys.version_info >= (3, 12), 'Python 3.12+ required'"],
        check=True,
    )
    subprocess.run(
        [str(python), "-m", "pip", "install", "-e", ".[dev,preview,step,inventor,simulation]"],
        cwd=root,
        check=True,
    )
    print("Setup complete. Double-click Start-PIHTI-Viewer.cmd.")
    print("After pulling tool updates, rerun Setup-PIHTI-Viewer.cmd to refresh dependencies.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"Setup failed: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
