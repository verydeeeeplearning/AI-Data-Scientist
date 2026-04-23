"""CLI helpers for web push subscription + VAPID key management.

Three subcommands::

    ds-agent web-push generate-vapid-keys
    ds-agent web-push print-public-key
    ds-agent web-push subscribers [--workspace-dir DIR]

The ``generate-vapid-keys`` subcommand uses :mod:`cryptography` directly
(no ``pywebpush`` dep) and emits two lines on stdout: PEM-encoded private
key followed by the base64url-encoded uncompressed public point. Pipe
the output to env vars when bootstrapping a new operator.
"""

from __future__ import annotations

import argparse
import base64
import os
import sys
from collections.abc import Sequence

from ds_agent.runtime.web_push_keys import ENV_PUBLIC_KEY


def run_web_push_command(
    argv: Sequence[str],
    *,
    workspace_dir: str = ".",
) -> int:
    """Entry point for ``ds-agent web-push`` subcommands."""

    parser = argparse.ArgumentParser(prog="ds-agent web-push")
    sub = parser.add_subparsers(dest="subcmd")

    sub.add_parser(
        "generate-vapid-keys",
        help="Print a fresh ECDSA P-256 VAPID key pair (private PEM + public b64url).",
    )
    sub.add_parser(
        "print-public-key",
        help="Echo the configured DS_AGENT_VAPID_PUBLIC_KEY.",
    )
    subscribers_cmd = sub.add_parser(
        "subscribers",
        help="List registered web push subscribers per operator.",
    )
    subscribers_cmd.add_argument(
        "--workspace-dir",
        default=workspace_dir,
        help="Workspace directory to read subscriptions from.",
    )

    args = parser.parse_args(argv)

    if args.subcmd == "generate-vapid-keys":
        return _generate_vapid_keys()
    if args.subcmd == "print-public-key":
        return _print_public_key()
    if args.subcmd == "subscribers":
        return _list_subscribers(args.workspace_dir)

    parser.print_help()
    return 0


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def _generate_vapid_keys() -> int:
    """Emit a private (PEM) + public (b64url uncompressed point) pair."""

    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec
    except ImportError:
        sys.stderr.write(
            "cryptography library is required for VAPID key generation.\n",
        )
        return 2

    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()

    pem_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    raw_public = public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    public_b64url = base64.urlsafe_b64encode(raw_public).rstrip(b"=").decode("ascii")

    # First line: private (PEM, base64url encoded so it is a single line).
    pem_b64url = base64.urlsafe_b64encode(pem_bytes).rstrip(b"=").decode("ascii")
    sys.stdout.write(pem_b64url + "\n")
    sys.stdout.write(public_b64url + "\n")
    sys.stdout.flush()
    return 0


def _print_public_key() -> int:
    value = os.environ.get(ENV_PUBLIC_KEY, "").strip()
    if not value:
        sys.stderr.write(f"{ENV_PUBLIC_KEY} is not set.\n")
        return 1
    sys.stdout.write(value + "\n")
    sys.stdout.flush()
    return 0


def _list_subscribers(workspace_dir: str) -> int:
    from ds_agent.infrastructure.persistence.web_push_subscription_store import (
        JsonWebPushSubscriptionStore,
    )

    store = JsonWebPushSubscriptionStore(workspace_dir)
    # The store is per-operator JSON; enumerate files directly so we can
    # show a per-operator breakdown without leaking internal types.
    base_dir = store._dir
    if not base_dir.exists():
        sys.stdout.write("(no subscribers registered)\n")
        return 0

    files = sorted(base_dir.glob("*.json"))
    if not files:
        sys.stdout.write("(no subscribers registered)\n")
        return 0

    import json

    total = 0
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        operator_id = payload.get("operator_id", path.stem)
        subs = payload.get("subscriptions", [])
        if not isinstance(subs, list):
            continue
        sys.stdout.write(f"{operator_id}: {len(subs)} subscription(s)\n")
        for sub in subs:
            if not isinstance(sub, dict):
                continue
            endpoint = sub.get("endpoint", "?")
            sys.stdout.write(f"  - {endpoint}\n")
            total += 1
    sys.stdout.write(f"total: {total}\n")
    sys.stdout.flush()
    return 0


__all__ = ["run_web_push_command"]
