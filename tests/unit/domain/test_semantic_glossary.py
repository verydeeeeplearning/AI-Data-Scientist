from __future__ import annotations

from ds_agent.memory.semantic.domain.glossary import GlossaryTerm


def test_glossary_term_normalizes_variants() -> None:
    term = GlossaryTerm(
        term_id="term.mau",
        canonical_form="MAU",
        definition="월간 활성 유저",
        synonyms=[" 월간 활성 유저 ", "MAU", "mau"],
        abbreviations=[" MAU ", "mau"],
        translations={"en": " MAU ", "ko": " 월간 활성 유저 "},
        linked_metric_ids=["mau", "mau"],
        category="metric",
    )

    assert term.synonyms == ["월간 활성 유저", "MAU"]
    assert term.abbreviations == ["MAU"]
    assert term.translations == {"en": "MAU", "ko": "월간 활성 유저"}
    assert term.linked_metric_ids == ["mau"]

