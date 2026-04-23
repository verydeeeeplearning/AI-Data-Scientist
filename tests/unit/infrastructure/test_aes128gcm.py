from __future__ import annotations

import base64

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ds_agent.infrastructure.notification.aes128gcm import encrypt

_AUTH_SECRET_B64U = "BTBZMqHH6r4Tts7J_aSIgg"
_UA_PRIVATE_B64U = "q1dXpw3UpT5VOmu_cf_v6ih07Aems3njxI-JWgLcM94"
_UA_PUBLIC_B64U = (
    "BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4"
)
_AS_PRIVATE_B64U = "yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw"
_SALT_B64U = "DGv6ra1nlYgDCS1FRnbzlw"
_RFC_BODY_B64U = (
    "DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27ml"
    "mlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A_yl95bQpu6cVPT"
    "pK4Mqgkf1CXztLVBSt2Ks3oZwbuwXPXLWyouBWLVWGNWQexSgSxsj_Qulcy4a-fN"
)


def _b64u_decode(value: str) -> bytes:
    padding = "=" * ((4 - (len(value) % 4)) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _private_key_from_b64u(value: str) -> ec.EllipticCurvePrivateKey:
    raw = _b64u_decode(value)
    return ec.derive_private_key(int.from_bytes(raw, "big"), ec.SECP256R1())


def _public_key_bytes(public_key: ec.EllipticCurvePublicKey) -> bytes:
    return public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )


def _hkdf_extract(salt: bytes, ikm: bytes) -> bytes:
    import hmac

    return hmac.digest(salt, ikm, "sha256")


def _hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    import hmac

    return hmac.digest(prk, info + b"\x01", "sha256")[:length]


def _decrypt_web_push_body(
    body: bytes,
    *,
    ua_private_key_b64u: str,
    auth_secret_b64u: str,
) -> bytes:
    salt = body[:16]
    record_size = int.from_bytes(body[16:20], "big")
    assert record_size == 4096
    key_id_len = body[20]
    as_public = body[21 : 21 + key_id_len]
    ciphertext = body[21 + key_id_len :]

    ua_private = _private_key_from_b64u(ua_private_key_b64u)
    ua_public = _public_key_bytes(ua_private.public_key())
    auth_secret = _b64u_decode(auth_secret_b64u)
    sender_public = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), as_public)

    ecdh_secret = ua_private.exchange(ec.ECDH(), sender_public)
    ikm = _hkdf_expand(
        _hkdf_extract(auth_secret, ecdh_secret),
        b"WebPush: info\x00" + ua_public + as_public,
        32,
    )
    prk = _hkdf_extract(salt, ikm)
    cek = _hkdf_expand(prk, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf_expand(prk, b"Content-Encoding: nonce\x00", 12)

    decrypted = AESGCM(cek).decrypt(nonce, ciphertext, b"")
    assert decrypted.endswith(b"\x02")
    return decrypted[:-1]


def test_encrypt_matches_rfc_8291_example(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ds_agent.infrastructure.notification.aes128gcm.os.urandom",
        lambda size: _b64u_decode(_SALT_B64U),
    )

    body = encrypt(
        b"When I grow up, I want to be a watermelon",
        p256dh_key=_UA_PUBLIC_B64U,
        auth_key=_AUTH_SECRET_B64U,
        vapid_private_key=_AS_PRIVATE_B64U,
    )

    assert body == _b64u_decode(_RFC_BODY_B64U)


def test_encrypt_rejects_invalid_p256dh_key() -> None:
    with pytest.raises(ValueError, match="p256dh_key"):
        encrypt(b"hello", p256dh_key="abc", auth_key=_AUTH_SECRET_B64U)


def test_encrypt_rejects_invalid_auth_secret_length() -> None:
    with pytest.raises(ValueError, match="auth_key"):
        encrypt(b"hello", p256dh_key=_UA_PUBLIC_B64U, auth_key="AQI")


def test_encrypt_handles_empty_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ds_agent.infrastructure.notification.aes128gcm.os.urandom",
        lambda size: b"\x01" * size,
    )

    body = encrypt(
        b"",
        p256dh_key=_UA_PUBLIC_B64U,
        auth_key=_AUTH_SECRET_B64U,
        vapid_private_key=_AS_PRIVATE_B64U,
    )

    assert _decrypt_web_push_body(
        body,
        ua_private_key_b64u=_UA_PRIVATE_B64U,
        auth_secret_b64u=_AUTH_SECRET_B64U,
    ) == b""


def test_encrypt_handles_large_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ds_agent.infrastructure.notification.aes128gcm.os.urandom",
        lambda size: b"\x02" * size,
    )
    payload = b"x" * 3500

    body = encrypt(
        payload,
        p256dh_key=_UA_PUBLIC_B64U,
        auth_key=_AUTH_SECRET_B64U,
        vapid_private_key=_AS_PRIVATE_B64U,
    )

    assert _decrypt_web_push_body(
        body,
        ua_private_key_b64u=_UA_PRIVATE_B64U,
        auth_secret_b64u=_AUTH_SECRET_B64U,
    ) == payload


def test_encrypt_is_deterministic_when_ephemeral_key_and_salt_are_fixed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "ds_agent.infrastructure.notification.aes128gcm.os.urandom",
        lambda size: b"\x03" * size,
    )

    first = encrypt(
        b"fixed",
        p256dh_key=_UA_PUBLIC_B64U,
        auth_key=_AUTH_SECRET_B64U,
        vapid_private_key=_AS_PRIVATE_B64U,
    )
    second = encrypt(
        b"fixed",
        p256dh_key=_UA_PUBLIC_B64U,
        auth_key=_AUTH_SECRET_B64U,
        vapid_private_key=_AS_PRIVATE_B64U,
    )

    assert first == second


def test_encrypt_rejects_payloads_over_web_push_limit() -> None:
    with pytest.raises(ValueError, match="maximum plaintext length"):
        encrypt(
            b"x" * 3994,
            p256dh_key=_UA_PUBLIC_B64U,
            auth_key=_AUTH_SECRET_B64U,
        )
