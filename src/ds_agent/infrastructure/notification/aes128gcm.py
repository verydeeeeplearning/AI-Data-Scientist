"""RFC 8291 / RFC 8188 payload encryption for Web Push.

This module implements the ``aes128gcm`` HTTP encrypted content-coding
profile used by Web Push. The caller provides the user agent public key
(``p256dh``) and authentication secret from the PushSubscription. The
application server generates a fresh ephemeral P-256 key and random salt
per message, derives the CEK/nonce, then returns the binary body:

``salt || rs || idlen || keyid || ciphertext``

Notes
-----
* The transport MUST use a fresh ephemeral key per payload. Reusing the
  VAPID signing key here would be incorrect.
* ``vapid_private_key`` is kept as an optional *ephemeral-key override*
  for deterministic tests only. Production callers should leave it as
  ``None`` so a new key is generated for every payload.
"""

from __future__ import annotations

import base64
import os
from hmac import digest as hmac_digest

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_AUTH_SECRET_LENGTH = 16
_HEADER_SALT_LENGTH = 16
_RECORD_SIZE = 4096
_MAX_PLAINTEXT_LENGTH = 3993

_WEB_PUSH_INFO = b"WebPush: info\x00"
_CEK_INFO = b"Content-Encoding: aes128gcm\x00"
_NONCE_INFO = b"Content-Encoding: nonce\x00"


def encrypt(
    payload: bytes,
    *,
    p256dh_key: str,
    auth_key: str,
    vapid_private_key: ec.EllipticCurvePrivateKey | str | bytes | None = None,
) -> bytes:
    """Encrypt *payload* for one PushSubscription.

    Args:
        payload: UTF-8 JSON or other binary payload to encrypt.
        p256dh_key: Base64url-encoded receiver public key in uncompressed
            P-256 point form (65 bytes, leading ``0x04``).
        auth_key: Base64url-encoded 16-byte authentication secret.
        vapid_private_key: Optional deterministic override for the
            *ephemeral* application-server private key used in ECDH.
            Kept for testability despite the historical parameter name.
    """

    plaintext = bytes(payload)
    if len(plaintext) > _MAX_PLAINTEXT_LENGTH:
        raise ValueError(
            f"payload exceeds Web Push maximum plaintext length ({_MAX_PLAINTEXT_LENGTH} bytes)"
        )

    ua_public = _decode_public_key(p256dh_key)
    auth_secret = _decode_auth_secret(auth_key)
    as_private = _load_ephemeral_private_key(vapid_private_key)
    as_public = _public_key_bytes(as_private.public_key())
    salt = os.urandom(_HEADER_SALT_LENGTH)

    ecdh_secret = as_private.exchange(ec.ECDH(), ua_public)
    ikm = _hkdf_expand(
        _hkdf_extract(auth_secret, ecdh_secret),
        _WEB_PUSH_INFO + _public_key_bytes(ua_public) + as_public,
        32,
    )
    prk = _hkdf_extract(salt, ikm)
    cek = _hkdf_expand(prk, _CEK_INFO, 16)
    nonce = _hkdf_expand(prk, _NONCE_INFO, 12)

    record_plaintext = plaintext + b"\x02"
    ciphertext = AESGCM(cek).encrypt(nonce, record_plaintext, b"")
    return b"".join(
        (
            salt,
            _RECORD_SIZE.to_bytes(4, "big"),
            len(as_public).to_bytes(1, "big"),
            as_public,
            ciphertext,
        )
    )


def _decode_auth_secret(value: str) -> bytes:
    raw = _decode_base64url(value, field_name="auth_key")
    if len(raw) != _AUTH_SECRET_LENGTH:
        raise ValueError("auth_key must decode to exactly 16 bytes")
    return raw


def _decode_public_key(value: str) -> ec.EllipticCurvePublicKey:
    raw = _decode_base64url(value, field_name="p256dh_key")
    if len(raw) != 65 or raw[0] != 0x04:
        raise ValueError("p256dh_key must decode to an uncompressed 65-byte P-256 point")
    try:
        key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), raw)
    except ValueError as exc:
        raise ValueError("p256dh_key is not a valid P-256 public key") from exc
    return key


def _decode_base64url(value: str, *, field_name: str) -> bytes:
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    padding = "=" * ((4 - (len(text) % 4)) % 4)
    try:
        return base64.urlsafe_b64decode(text + padding)
    except Exception as exc:
        raise ValueError(f"{field_name} is not valid base64url") from exc


def _load_ephemeral_private_key(
    key: ec.EllipticCurvePrivateKey | str | bytes | None,
) -> ec.EllipticCurvePrivateKey:
    if key is None:
        return ec.generate_private_key(ec.SECP256R1())
    if isinstance(key, ec.EllipticCurvePrivateKey):
        return key
    if isinstance(key, bytes):
        return _load_ephemeral_private_key_from_bytes(key)
    return _load_ephemeral_private_key_from_text(key)


def _load_ephemeral_private_key_from_bytes(key: bytes) -> ec.EllipticCurvePrivateKey:
    try:
        loaded = serialization.load_pem_private_key(key, password=None)
    except ValueError:
        return _derive_private_key(_decode_base64url(key.decode("ascii"), field_name="private_key"))
    if not isinstance(loaded, ec.EllipticCurvePrivateKey):
        raise ValueError("private_key must be an EC P-256 private key")
    return loaded


def _load_ephemeral_private_key_from_text(key: str) -> ec.EllipticCurvePrivateKey:
    text = key.strip()
    if "BEGIN" in text:
        return _load_ephemeral_private_key_from_bytes(text.encode("utf-8"))
    return _derive_private_key(_decode_base64url(text, field_name="private_key"))


def _derive_private_key(raw: bytes) -> ec.EllipticCurvePrivateKey:
    if len(raw) != 32:
        raise ValueError("private_key must decode to 32 bytes")
    value = int.from_bytes(raw, "big")
    if value <= 0:
        raise ValueError("private_key must be in the valid P-256 scalar range")
    return ec.derive_private_key(value, ec.SECP256R1())


def _public_key_bytes(public_key: ec.EllipticCurvePublicKey) -> bytes:
    return public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )


def _hkdf_extract(salt: bytes, ikm: bytes) -> bytes:
    return hmac_digest(salt, ikm, "sha256")


def _hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    if length <= 0:
        raise ValueError("length must be positive")
    if length > hashes.SHA256().digest_size:
        raise ValueError("length exceeds single-block HKDF expansion for SHA-256")
    return hmac_digest(prk, info + b"\x01", "sha256")[:length]


__all__ = ["encrypt"]
