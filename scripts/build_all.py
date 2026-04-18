#!/usr/bin/env python3
"""Unified build script — builds everything for distribution.

Steps:
  1. Run Python tests
  2. PyInstaller → build/ds-agent-backend/
  3. npm build (renderer + main)
  4. electron-builder → electron/release/

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
    """Run a command, print it, return exit code."""
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

    # Step 1: Tests
    if not args.skip_tests:
        print("\n[1/4] Running Python tests...")
        run([py, "-m", "pytest", "tests/", "-q", "--tb=short"])
    else:
        print("\n[1/4] Skipping tests")

    # Step 2: PyInstaller backend
    if not args.skip_backend:
        print("\n[2/4] Building Python backend with PyInstaller...")
        run([py, "scripts/build_backend.py", "--clean"])
    else:
        print("\n[2/4] Skipping backend build")

    # Step 3: Electron frontend build
    print("\n[3/4] Building Electron frontend...")
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    run([npm, "run", "build"], cwd=ELECTRON_DIR)

    # Step 4: electron-builder
    print("\n[4/4] Packaging with electron-builder...")
    dist_cmd = [npm, "run"]
    if args.platform:
        dist_cmd.append(f"dist:{args.platform}")
    else:
        dist_cmd.append("dist")
    run(dist_cmd, cwd=ELECTRON_DIR)

    # Summary
    release_dir = ELECTRON_DIR / "release"
    if release_dir.exists():
        print("\n" + "=" * 60)
        print("  BUILD COMPLETE")
        print("=" * 60)
        print(f"\nOutput: {release_dir}")
        for f in sorted(release_dir.iterdir()):
            if f.is_file():
                size_mb = f.stat().st_size / (1024 * 1024)
                print(f"  {f.name}  ({size_mb:.1f} MB)")
    else:
        print("\n[!] Release directory not found — check electron-builder output")


if __name__ == "__main__":
    main()
