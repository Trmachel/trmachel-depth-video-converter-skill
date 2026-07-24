"""Bootstrap and launch the bundled Depth Video Converter."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import venv
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = SKILL_DIR / "scripts"
APP_PATH = SCRIPTS_DIR / "app.py"
REQUIREMENTS_PATH = SCRIPTS_DIR / "requirements.txt"


def cache_root() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "convert-depth-video"


def runtime_python(runtime_dir: Path) -> Path:
    if sys.platform == "win32":
        return runtime_dir / "Scripts" / "python.exe"
    return runtime_dir / "bin" / "python"


def requirements_digest() -> str:
    payload = REQUIREMENTS_PATH.read_bytes()
    payload += f"\n{sys.version_info.major}.{sys.version_info.minor}".encode()
    return hashlib.sha256(payload).hexdigest()


def ensure_runtime(reinstall: bool = False) -> Path:
    runtime_dir = cache_root() / (
        f"runtime-py{sys.version_info.major}.{sys.version_info.minor}"
    )
    python_path = runtime_python(runtime_dir)
    marker = runtime_dir / ".requirements-sha256"
    expected_digest = requirements_digest()

    if not python_path.is_file():
        print(f"Creating isolated runtime: {runtime_dir}", flush=True)
        runtime_dir.parent.mkdir(parents=True, exist_ok=True)
        venv.EnvBuilder(with_pip=True, clear=False).create(runtime_dir)

    installed_digest = marker.read_text().strip() if marker.is_file() else ""
    if reinstall or installed_digest != expected_digest:
        print("Installing Depth Video Converter dependencies…", flush=True)
        subprocess.run(
            [str(python_path), "-m", "pip", "install", "--upgrade", "pip"],
            check=True,
        )
        subprocess.run(
            [
                str(python_path),
                "-m",
                "pip",
                "install",
                "-r",
                str(REQUIREMENTS_PATH),
            ],
            check=True,
        )
        marker.write_text(expected_digest + "\n")

    return python_path


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    setup_only = "--setup-only" in arguments
    reinstall = "--reinstall" in arguments
    forwarded = [
        argument
        for argument in arguments
        if argument not in {"--setup-only", "--reinstall"}
    ]

    if not (3, 10) <= sys.version_info[:2] <= (3, 14):
        print("Python 3.10 through 3.14 is required.", file=sys.stderr)
        return 2
    if not APP_PATH.is_file() or not REQUIREMENTS_PATH.is_file():
        print("The Skill bundle is incomplete.", file=sys.stderr)
        return 2

    python_path = ensure_runtime(reinstall=reinstall)
    if setup_only:
        print(f"Runtime ready: {python_path}")
        return 0

    command = [str(python_path), str(APP_PATH), *forwarded]
    print("Starting the local Depth Video Converter…", flush=True)
    try:
        return subprocess.call(command)
    except KeyboardInterrupt:
        print("\nDepth Video Converter stopped.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
