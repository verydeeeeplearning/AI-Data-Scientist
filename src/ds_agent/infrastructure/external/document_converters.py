"""Shared markdown conversion helpers for external collaboration systems."""

from __future__ import annotations

from html import escape
from typing import Any


def markdown_to_notion_blocks(markdown: str) -> list[dict[str, Any]]:
    """Convert simple markdown into a bounded Notion block list."""

    blocks: list[dict[str, Any]] = []
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        block_type = "paragraph"
        content = line
        if line.startswith("### "):
            block_type = "heading_3"
            content = line[4:]
        elif line.startswith("## "):
            block_type = "heading_2"
            content = line[3:]
        elif line.startswith("# "):
            block_type = "heading_1"
            content = line[2:]
        elif line.startswith("- "):
            block_type = "bulleted_list_item"
            content = line[2:]
        blocks.append(
            {
                "object": "block",
                "type": block_type,
                block_type: {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": content[:1800]},
                        }
                    ]
                },
            }
        )
        if len(blocks) >= 100:
            break
    return blocks or [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {"type": "text", "text": {"content": "No delivery content available."}}
                ]
            },
        }
    ]


def markdown_to_confluence_storage(markdown: str) -> str:
    """Convert simple markdown into Confluence storage-format HTML."""

    html_lines: list[str] = []
    in_list = False
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            continue
        if line.startswith("# "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h1>{escape(line[2:])}</h1>")
            continue
        if line.startswith("## "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h2>{escape(line[3:])}</h2>")
            continue
        if line.startswith("### "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h3>{escape(line[4:])}</h3>")
            continue
        if line.startswith("- "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{escape(line[2:])}</li>")
            continue
        if in_list:
            html_lines.append("</ul>")
            in_list = False
        html_lines.append(f"<p>{escape(line)}</p>")
    if in_list:
        html_lines.append("</ul>")
    return "".join(html_lines) or "<p>No delivery content available.</p>"
