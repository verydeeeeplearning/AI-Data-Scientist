#!/usr/bin/env python3
"""Build the Python backend with PyInstaller.

Usage:
    python scripts/build_backend.py [--clean]

Output:
    build/ds-agent-backend/   (directory with ds-agent-api executable)
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC_FILE = ROOT / "ds-agent-api.spec"
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
OUTPUT_DIR = ROOT / "build" / "ds-agent-backend"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build DS Agent backend")
    parser.add_argument("--clean", action="store_true", help="Clean build dirs first")
    args = parser.parse_args()

    if args.clean:
        print("[build] Cleaning build directories...")
        for d in [DIST_DIR / "ds-agent-backend", BUILD_DIR / "ds-agent-api"]:
            if d.exists():
                shutil.rmtree(d)

    if not SPEC_FILE.exists():
        print(f"[build] ERROR: Spec file not found: {SPEC_FILE}", file=sys.stderr)
        sys.exit(1)

    print("[build] Running PyInstaller...")
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(SPEC_FILE),
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(BUILD_DIR / "pyinstaller-work"),
        "--noconfirm",
    ]

    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        print("[build] ERROR: PyInstaller failed", file=sys.stderr)
        sys.exit(1)

    # Move output to build/ for electron-builder
    src = DIST_DIR / "ds-agent-backend"
    dest = OUTPUT_DIR
    if src.exists() and src != dest:
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(str(src), str(dest))
        print(f"[build] Backend copied to {dest}")

    # Verify
    exe_name = "ds-agent-api.exe" if sys.platform == "win32" else "ds-agent-api"
    exe_path = dest / exe_name
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"[build] SUCCESS: {exe_path} ({size_mb:.1f} MB)")
    else:
        print(f"[build] WARNING: Executable not found at {exe_path}")
        print(f"[build] Contents: {list(dest.iterdir()) if dest.exists() else 'N/A'}")


if __name__ == "__main__":
    main()
