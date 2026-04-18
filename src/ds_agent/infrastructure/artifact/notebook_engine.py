"""Notebook generation helpers."""

from __future__ import annotations

import json
from pathlib import Path


class NotebookEngine:
    """Build simple Jupyter notebook documents."""

    def build(
        self,
        *,
        markdown_blocks: list[str],
        code_blocks: list[str],
        output_blocks: list[str] | None = None,
    ) -> dict[str, object]:
        outputs = output_blocks or []
        cells: list[dict[str, object]] = []
        for block in markdown_blocks:
            cells.append(
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": [block],
                }
            )
        for index, block in enumerate(code_blocks):
            output_payload = []
            if index < len(outputs):
                output_payload.append(
                    {
                        "name": "stdout",
                        "output_type": "stream",
                        "text": outputs[index],
                    }
                )
            cells.append(
                {
                    "cell_type": "code",
                    "execution_count": index + 1,
                    "metadata": {},
                    "outputs": output_payload,
                    "source": [block],
                }
            )
        return {
            "cells": cells,
            "metadata": {
                "kernelspec": {
                    "display_name": "Python 3",
                    "language": "python",
                    "name": "python3",
                },
                "language_info": {"name": "python"},
            },
            "nbformat": 4,
            "nbformat_minor": 5,
        }

    def write(
        self,
        path: str,
        *,
        markdown_blocks: list[str],
        code_blocks: list[str],
        output_blocks: list[str] | None = None,
    ) -> dict[str, object]:
        notebook = self.build(
            markdown_blocks=markdown_blocks,
            code_blocks=code_blocks,
            output_blocks=output_blocks,
        )
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(notebook, indent=2), encoding="utf-8")
        return notebook
