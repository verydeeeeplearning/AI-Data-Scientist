"""Port: ``NotebookEnginePort`` — abstraction for notebook document construction.

The application layer depends only on this Protocol. Concrete notebook
builders live in ``ds_agent.infrastructure`` and are wired at the
composition root.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class NotebookEnginePort(Protocol):
    """Contract any notebook builder must honour."""

    def build(
        self,
        *,
        markdown_blocks: list[str],
        code_blocks: list[str],
        output_blocks: list[str] | None = None,
    ) -> dict[str, object]:
        """Assemble a Jupyter notebook document from the supplied blocks."""
