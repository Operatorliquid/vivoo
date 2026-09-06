#!/usr/bin/env python3
"""Build a platform-native, self-contained capture-agent runtime."""

from __future__ import annotations

import shutil
import subprocess
import sys
from importlib.util import find_spec
from pathlib import Path


DESKTOP_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = DESKTOP_ROOT.parents[1]
AGENT_ROOT = PROJECT_ROOT / "apps" / "capture-agent"
RUNTIME_ROOT = DESKTOP_ROOT / "runtime"


def main() -> None:
    if find_spec("PyInstaller") is None:
        raise SystemExit("PyInstaller no está instalado en el Python activo")
    output = RUNTIME_ROOT / "agent"
    work = DESKTOP_ROOT / ".build" / "pyinstaller"
    spec = DESKTOP_ROOT / ".build" / "spec"
    shutil.rmtree(output, ignore_errors=True)
    shutil.rmtree(work, ignore_errors=True)
    spec.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir",
            "--name", "courtvision-agent", "--distpath", str(output), "--workpath", str(work),
            "--specpath", str(spec), "--paths", str(AGENT_ROOT / "src"),
            "--collect-all", "ultralytics",
            str(AGENT_ROOT / "src" / "main.py"),
        ],
        check=True,
        cwd=PROJECT_ROOT,
    )


if __name__ == "__main__":
    main()
