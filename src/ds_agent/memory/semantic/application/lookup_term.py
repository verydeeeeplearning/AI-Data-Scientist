"""Use case for glossary lookup."""

from __future__ import annotations

from ds_agent.memory.semantic.application.dtos import LookupTermResultDTO
from ds_agent.memory.semantic.application.ports import GlossaryRepository


class LookupTermUseCase:
    """Lookup business glossary terms."""

    def __init__(self, glossary: GlossaryRepository) -> None:
        self._glossary = glossary

    def execute(self, query: str, *, limit: int = 5) -> LookupTermResultDTO:
        return LookupTermResultDTO(query=query, matches=self._glossary.lookup(query, limit=limit))

