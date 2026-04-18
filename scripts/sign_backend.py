#!/usr/bin/env python3
"""Sign the PyInstaller-built backend executable (P0-05).

The Electron installer is signed by electron-builder using CSC_LINK env
vars. The backend binary ships inside extraResources and is NOT auto-signed
by electron-builder, so we sign it directly before packaging.

Windows: signtool + RFC 3161 timestamp.
macOS:   codesign with hardened runtime + entitlements.
Linux:   no-op (distributed as unsigned AppImage + SHA256 checksum).

Usage:
    python scripts/sign_backend.py --platform win \
        --pfx cert.pfx --password $PW build/ds-agent-backend/ds-agent-api.exe
    python scripts/sign_backend.py --platform mac \
        --identity "Developer ID Application: Foo (TEAMID)" \
        --entitlements electron/resources/entitlements.mac.plist \
        build/ds-agent-backend/ds-agent-api
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

TIMESTAMP_SERVER = "http://timestamp.digicert.com"


def _run(cmd: list[str]) -> None:
    print("[sign]", " ".join(cmd))
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        sys.exit(f"[sign] FAILED: exit {result.returncode}")


def _locate_signtool() -> str:
    """Find signtool.exe in the installed Windows SDK."""
    import glob
    import os

    candidates = glob.glob(
        r"C:\Program Files (x86)\Windows Kits\10\bin\*\x64\signtool.exe"
    )
    if not candidates:
        candidates = glob.glob(
            r"C:\Program Files (x86)\Windows Kits\10\App Certification Kit\signtool.exe"
        )
    if not candidates:
        on_path = os.environ.get("SIGNTOOL") or "signtool.exe"
        return on_path
    return sorted(candidates)[-1]


def sign_windows(binary: Path, pfx: Path, password: str) -> None:
    signtool = _locate_signtool()
    _run(
        [
            signtool,
            "sign",
            "/f",
            str(pfx),
            "/p",
            password,
            "/tr",
            TIMESTAMP_SERVER,
            "/td",
            "sha256",
            "/fd",
            "sha256",
            str(binary),
        ]
    )
    _run([signtool, "verify", "/pa", "/v", str(binary)])


def sign_macos(binary: Path, identity: str, entitlements: Path | None) -> None:
    cmd = [
        "codesign",
        "--sign",
        identity,
        "--force",
        "--timestamp",
        "--options",
        "runtime",
    ]
    if entitlements:
        cmd.extend(["--entitlements", str(entitlements)])
    cmd.append(str(binary))
    _run(cmd)
    _run(["codesign", "--verify", "--strict", "--verbose=2", str(binary)])


def main() -> None:
    parser = argparse.ArgumentParser(description="Sign DS Agent backend binary")
    parser.add_argument(
        "--platform", choices=["win", "mac", "linux"], required=True
    )
    parser.add_argument("--pfx", type=Path, help="Windows: path to PFX")
    parser.add_argument("--password", help="Windows: PFX password")
    parser.add_argument("--identity", help="macOS: signing identity")
    parser.add_argument(
        "--entitlements", type=Path, help="macOS: entitlements plist"
    )
    parser.add_argument("binary", type=Path, help="Binary to sign")
    args = parser.parse_args()

    if not args.binary.exists():
        sys.exit(f"[sign] Binary not found: {args.binary}")

    if args.platform == "win":
        if not args.pfx or not args.password:
            sys.exit("[sign] --pfx and --password are required on Windows")
        sign_windows(args.binary, args.pfx, args.password)
    elif args.platform == "mac":
        if not args.identity:
            sys.exit("[sign] --identity is required on macOS")
        sign_macos(args.binary, args.identity, args.entitlements)
    else:
        print("[sign] Linux: no signing required (SHA256 checksum only)")


if __name__ == "__main__":
    main()
