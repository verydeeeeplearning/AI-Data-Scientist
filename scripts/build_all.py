#!/usr/bin/env python3
"""Unified build script for distribution packaging.

Steps:
  1. Run backend baseline gate
  2. Run Python tests
  3. Build the backend with PyInstaller
  4. Build the Electron frontend
  5. Package with electron-builder

Usage:
    python scripts/build_all.py [--skip-tests] [--skip-backend] [--platform win|mac|linux]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ELECTRON_DIR = ROOT / "electron"


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> int:
    """Run a command, print it, and return the exit code."""

    print(f"\n{'=' * 60}")
    print(f"  {' '.join(cmd)}")
    print(f"  cwd: {cwd or ROOT}")
    print(f"{'=' * 60}\n")
    result = subprocess.run(cmd, cwd=str(cwd or ROOT))
    if check and result.returncode != 0:
        print(f"\nERROR: Command failed with code {result.returncode}", file=sys.stderr)
        sys.exit(result.returncode)
    return result.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="Build DS Agent for distribution")
    parser.add_argument("--skip-tests", action="store_true", help="Skip Python tests")
    parser.add_argument("--skip-backend", action="store_true", help="Skip PyInstaller build")
    parser.add_argument("--platform", choices=["win", "mac", "linux"], help="Target platform")
    args = parser.parse_args()

    py = sys.executable

    if not args.skip_tests:
        print("\n[1/5] Running backend baseline gate...")
        run([py, "scripts/check_backend_quality_gate.py"])
        print("\n[2/5] Running Python tests...")
        run([py, "-m", "pytest", "tests/", "-q", "--tb=short"])
    else:
        print("\n[1/5] Skipping backend baseline gate")
        print("\n[2/5] Skipping tests")

    if not args.skip_backend:
        print("\n[3/5] Building Python backend with PyInstaller...")
        run([py, "scripts/build_backend.py", "--clean"])
    else:
        print("\n[3/5] Skipping backend build")

    print("\n[4/5] Building Electron frontend...")
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    run([npm, "run", "build"], cwd=ELECTRON_DIR)

    print("\n[5/5] Packaging with electron-builder...")
    dist_cmd = [npm, "run"]
    if args.platform:
        dist_cmd.append(f"dist:{args.platform}")
    else:
        dist_cmd.append("dist")
    run(dist_cmd, cwd=ELECTRON_DIR)

    release_dir = ELECTRON_DIR / "release"
    if release_dir.exists():
        print("\n" + "=" * 60)
        print("  BUILD COMPLETE")
        print("=" * 60)
        print(f"\nOutput: {release_dir}")
        for path in sorted(release_dir.iterdir()):
            if path.is_file():
                size_mb = path.stat().st_size / (1024 * 1024)
                print(f"  {path.name}  ({size_mb:.1f} MB)")
    else:
        print("\n[!] Release directory not found; check electron-builder output")


if __name__ == "__main__":
    main()
