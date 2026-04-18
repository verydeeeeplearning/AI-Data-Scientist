"""Extract claims from reports and link them to supporting evidence markers."""

from __future__ import annotations

import re
from dataclasses import dataclass

_CLAIM_RE = re.compile(
    r"(?:(?:increase|decrease|improve|reduce|grow|recommend|should)\w*|%|\b\d+(?:\.\d+)?\b)",
    re.IGNORECASE,
)
_EVIDENCE_RE = re.compile(
    r"(Figure\s+\d+|Table\s+\d+|\[EVIDENCE:[^\]]+\]|Source:|Dataset:|SQL:)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ClaimCheck:
    """One claim and its evidence status."""

    claim: str
    evidence: list[str]
    supported: bool


class ClaimEvidenceLinker:
    """Analyze report text for unsupported claims."""

    def analyze(self, text: str) -> list[ClaimCheck]:
        sentences = [
            segment.strip() for segment in re.split(r"(?<=[.!?])\s+", text) if segment.strip()
        ]
        checks: list[ClaimCheck] = []
        for index, sentence in enumerate(sentences):
            if not _CLAIM_RE.search(sentence):
                continue
            evidence = _EVIDENCE_RE.findall(sentence)
            if not evidence and index + 1 < len(sentences):
                evidence = _EVIDENCE_RE.findall(sentences[index + 1])
            checks.append(
                ClaimCheck(
                    claim=sentence,
                    evidence=evidence,
                    supported=bool(evidence),
                )
            )
        return checks

    def score(self, text: str) -> dict[str, object]:
        checks = self.analyze(text)
        supported = [check for check in checks if check.supported]
        unsupported = [check for check in checks if not check.supported]
        coverage = 1.0 if not checks else round(len(supported) / len(checks), 2)
        return {
            "claims": len(checks),
            "supported": len(supported),
            "unsupported": [check.claim for check in unsupported],
            "coverage": coverage,
        }
