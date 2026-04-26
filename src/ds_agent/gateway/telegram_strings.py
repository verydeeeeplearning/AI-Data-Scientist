"""Localized Telegram bot reply strings."""

from __future__ import annotations

TELEGRAM_STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "pairing.success": "Connected. Type /menu to start.",
        "pairing.invalid_code": "Pairing code is invalid or expired.",
    },
    "ko": {
        "pairing.success": "연결 완료. /menu 로 시작하세요.",
        "pairing.invalid_code": "페어링 코드가 잘못되었거나 만료되었습니다.",
    },
    "ja": {
        "pairing.success": "接続完了。/menu で開始してください。",
        "pairing.invalid_code": "ペアリングコードが無効または期限切れです。",
    },
}


def telegram_string(language: str | None, key: str) -> str:
    """Return a localized Telegram string with English fallback."""

    catalog = TELEGRAM_STRINGS.get(language or "", TELEGRAM_STRINGS["en"])
    return catalog.get(key) or TELEGRAM_STRINGS["en"][key]
