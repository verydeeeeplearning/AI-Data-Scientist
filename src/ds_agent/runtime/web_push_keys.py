"""VAPID key bootstrap for web push (Wave 4 PLAN_06b).

The composition root reads the operator-provided VAPID keypair from env
vars. If either var is missing the runtime returns a sentinel so the
caller can wire a no-op transport (no push) instead of crashing. The
subject is resolved from persisted config first, then environment, then
the default contact URI used by the transport fallback.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from ds_agent.runtime.web_push_subject_store import JsonWebPushSubjectStore

_LOG = logging.getLogger(__name__)

ENV_PRIVATE_KEY = "DS_AGENT_VAPID_PRIVATE_KEY"
ENV_PUBLIC_KEY = "DS_AGENT_VAPID_PUBLIC_KEY"
ENV_SUBJECT = "DS_AGENT_VAPID_SUBJECT"  # mailto:operator@example.com


@dataclass(frozen=True, slots=True)
class VapidKeys:
    """A loaded VAPID key pair plus contact subject."""

    private_key_pem: str
    public_key_b64url: str
    subject: str


@dataclass(frozen=True, slots=True)
class _VapidKeysMissing:
    """Sentinel returned when env vars are not set.

    The ``reason`` field is a short stable token logged at init and
    surfaced via the IPC ``webPush.getPublicKey`` channel so the mobile
    UI can render an actionable explanation rather than spin.
    """

    reason: str


def load_vapid_subject(workspace_dir: str | None = None) -> str | None:
    """Return the persisted or environment VAPID subject, if any."""

    if workspace_dir:
        subject = JsonWebPushSubjectStore(workspace_dir).load()
        if subject:
            return subject

    subject = os.environ.get(ENV_SUBJECT, "").strip()
    return subject or None


def load_vapid_keys(
    workspace_dir: str | None = None,
) -> VapidKeys | _VapidKeysMissing:
    """Read the VAPID keypair from process env.

    Logs at most once per process when keys are missing. Returns the
    sentinel on missing private key, missing public key, or missing
    subject. The subject falls back to a generic mailto URI when no
    persisted or environment value exists so operators can bootstrap
    push without a manual config write.
    """
    private_key = os.environ.get(ENV_PRIVATE_KEY, "").strip()
    public_key = os.environ.get(ENV_PUBLIC_KEY, "").strip()

    if not private_key:
        _log_once("vapid_private_key_missing")
        return _VapidKeysMissing(reason="vapid_private_key_missing")
    if not public_key:
        _log_once("vapid_public_key_missing")
        return _VapidKeysMissing(reason="vapid_public_key_missing")
    subject = load_vapid_subject(workspace_dir)
    if not subject:
        subject = "mailto:operator@ds-agent.local"
    return VapidKeys(
        private_key_pem=private_key,
        public_key_b64url=public_key,
        subject=subject,
    )


_LOGGED_REASONS: set[str] = set()


def _log_once(reason: str) -> None:
    if reason in _LOGGED_REASONS:
        return
    _LOGGED_REASONS.add(reason)
    _LOG.warning("web_push disabled: %s", reason)


__all__ = [
    "ENV_PRIVATE_KEY",
    "ENV_PUBLIC_KEY",
    "ENV_SUBJECT",
    "VapidKeys",
    "_VapidKeysMissing",
    "load_vapid_keys",
    "load_vapid_subject",
]
