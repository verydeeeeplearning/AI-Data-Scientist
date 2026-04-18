"""Regex-based PII detection and masking helpers."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from ds_agent.domain.entities.approval_policy import DataSensitivity

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"\b(?:\+?\d{1,2}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_ADDRESS_RE = re.compile(
    r"\b\d{1,5}\s+[A-Za-z0-9.\- ]+\s(?:Street|St|Road|Rd|Avenue|Ave|Lane|Ln|Boulevard|Blvd)\b",
    re.IGNORECASE,
)
_DATE_RE = re.compile(r"\b(?:19|20)\d{2}[-/]\d{1,2}[-/]\d{1,2}\b")

_KEYWORD_TO_TYPE: dict[str, str] = {
    "email": "email",
    "phone": "phone",
    "mobile": "phone",
    "ssn": "ssn",
    "social_security": "ssn",
    "address": "address",
    "street": "address",
    "name": "name",
    "full_name": "name",
    "birthday": "birthday",
    "birth_date": "birthday",
    "dob": "birthday",
    "ip": "ip_address",
    "ip_address": "ip_address",
}


@dataclass(frozen=True, slots=True)
class PIIMatch:
    """One detected PII item."""

    pii_type: str
    location: str
    sample: str


class PIIDetector:
    """PII detector based on column-name heuristics and regexes."""

    def detect(self, value: Any, *, location: str = "root") -> list[PIIMatch]:
        matches: list[PIIMatch] = []
        matches.extend(self._detect_keywords(value, location=location))
        matches.extend(self._detect_values(value, location=location))
        return self._dedupe(matches)

    def classify_sensitivity(self, value: Any) -> DataSensitivity:
        matches = self.detect(value)
        if any(match.pii_type in {"ssn", "address"} for match in matches):
            return DataSensitivity.RESTRICTED
        if matches:
            return DataSensitivity.PII
        return DataSensitivity.INTERNAL

    def redact(self, value: Any) -> Any:
        if isinstance(value, str):
            redacted = value
            redacted = _EMAIL_RE.sub(lambda m: self._hashed_token("email", m.group(0)), redacted)
            redacted = _PHONE_RE.sub(lambda m: self._hashed_token("phone", m.group(0)), redacted)
            redacted = _SSN_RE.sub(lambda m: self._hashed_token("ssn", m.group(0)), redacted)
            redacted = _IP_RE.sub(lambda m: self._hashed_token("ip", m.group(0)), redacted)
            redacted = _ADDRESS_RE.sub(
                lambda m: self._hashed_token("address", m.group(0)),
                redacted,
            )
            return redacted

        if isinstance(value, dict):
            output: dict[str, Any] = {}
            for key, item in value.items():
                pii_type = self._keyword_type(str(key))
                if pii_type is not None and isinstance(item, str):
                    output[str(key)] = self._hashed_token(pii_type, item)
                else:
                    output[str(key)] = self.redact(item)
            return output

        if isinstance(value, list):
            return [self.redact(item) for item in value]

        return value

    def _detect_keywords(self, value: Any, *, location: str) -> list[PIIMatch]:
        if not isinstance(value, dict):
            return []

        matches: list[PIIMatch] = []
        for key, item in value.items():
            pii_type = self._keyword_type(str(key))
            child_location = f"{location}.{key}"
            if pii_type is not None:
                matches.append(
                    PIIMatch(
                        pii_type=pii_type,
                        location=child_location,
                        sample=str(item)[:80],
                    )
                )
            matches.extend(self._detect_keywords(item, location=child_location))
            if isinstance(item, list):
                for index, child in enumerate(item):
                    matches.extend(
                        self._detect_keywords(child, location=f"{child_location}[{index}]")
                    )
        return matches

    def _detect_values(self, value: Any, *, location: str) -> list[PIIMatch]:
        if isinstance(value, dict):
            matches: list[PIIMatch] = []
            for key, item in value.items():
                matches.extend(self._detect_values(item, location=f"{location}.{key}"))
            return matches

        if isinstance(value, list):
            list_matches: list[PIIMatch] = []
            for index, item in enumerate(value):
                list_matches.extend(self._detect_values(item, location=f"{location}[{index}]"))
            return list_matches

        if not isinstance(value, str):
            return []

        patterns = [
            ("email", _EMAIL_RE),
            ("phone", _PHONE_RE),
            ("ssn", _SSN_RE),
            ("ip_address", _IP_RE),
            ("address", _ADDRESS_RE),
            ("birthday", _DATE_RE),
        ]
        matches = []
        for pii_type, pattern in patterns:
            for found in pattern.finditer(value):
                matches.append(
                    PIIMatch(
                        pii_type=pii_type,
                        location=location,
                        sample=found.group(0)[:80],
                    )
                )
        return matches

    @staticmethod
    def _keyword_type(key: str) -> str | None:
        return _KEYWORD_TO_TYPE.get(key.lower().strip())

    @staticmethod
    def _hashed_token(pii_type: str, value: str) -> str:
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
        return f"[REDACTED_{pii_type.upper()}:{digest}]"

    @staticmethod
    def _dedupe(matches: list[PIIMatch]) -> list[PIIMatch]:
        seen: set[tuple[str, str, str]] = set()
        deduped: list[PIIMatch] = []
        for match in matches:
            key = (match.pii_type, match.location, match.sample)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(match)
        return deduped
