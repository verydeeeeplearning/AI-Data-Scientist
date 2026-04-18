"""Web search tool — documentation, papers, Kaggle.

Backends:
- arxiv: https://export.arxiv.org/api/query (no key required)
- general / docs / kaggle / stackoverflow: DuckDuckGo Instant Answer
  (https://api.duckduckgo.com) when no TAVILY_API_KEY is set; Tavily
  otherwise.

Set `WEB_SEARCH_DISABLED=1` to force the tool to return an explicit
disabled message (useful for sealed/offline environments).
"""

from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from ds_agent.tools.registry import tool

_USER_AGENT = "ds-agent-web-search/1.0"
_DEFAULT_TIMEOUT_SECONDS = 10


def _disabled_response(query: str, source: str, reason: str) -> str:
    return json.dumps(
        {
            "error": reason,
            "query": query,
            "source": source,
            "results": [],
        }
    )


def _http_get_json(url: str, timeout: int = _DEFAULT_TIMEOUT_SECONDS) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = resp.read().decode("utf-8", errors="replace")
    return json.loads(payload) if payload else {}


def _http_get_text(url: str, timeout: int = _DEFAULT_TIMEOUT_SECONDS) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        text: str = resp.read().decode("utf-8", errors="replace")
        return text


def _http_post_json(url: str, body: dict, timeout: int = _DEFAULT_TIMEOUT_SECONDS) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = resp.read().decode("utf-8", errors="replace")
    return json.loads(payload) if payload else {}


def _search_arxiv(query: str, max_results: int) -> list[dict]:
    params = urllib.parse.urlencode(
        {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": max_results,
        }
    )
    url = f"https://export.arxiv.org/api/query?{params}"
    xml_text = _http_get_text(url)
    root = ET.fromstring(xml_text)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    results: list[dict] = []
    for entry in root.findall("a:entry", ns):
        title_el = entry.find("a:title", ns)
        link_el = entry.find("a:id", ns)
        summary_el = entry.find("a:summary", ns)
        if title_el is None or link_el is None:
            continue
        results.append(
            {
                "title": (title_el.text or "").strip(),
                "url": (link_el.text or "").strip(),
                "snippet": (summary_el.text or "").strip() if summary_el is not None else "",
                "source": "arxiv",
            }
        )
    return results


def _search_tavily(query: str, max_results: int, api_key: str) -> list[dict]:
    url = "https://api.tavily.com/search"
    body = {
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
        "search_depth": "basic",
    }
    payload = _http_post_json(url, body)
    results: list[dict] = []
    for item in payload.get("results", [])[:max_results]:
        results.append(
            {
                "title": item.get("title") or "",
                "url": item.get("url") or "",
                "snippet": item.get("content") or "",
                "source": "tavily",
            }
        )
    return results


def _search_duckduckgo(query: str, max_results: int) -> list[dict]:
    params = urllib.parse.urlencode(
        {
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1",
        }
    )
    url = f"https://api.duckduckgo.com/?{params}"
    payload = _http_get_json(url)

    results: list[dict] = []
    abstract = payload.get("AbstractText")
    if abstract:
        results.append(
            {
                "title": payload.get("Heading") or query,
                "url": payload.get("AbstractURL") or "",
                "snippet": abstract,
                "source": "duckduckgo",
            }
        )

    for topic in payload.get("RelatedTopics", []):
        if len(results) >= max_results:
            break
        if "Text" not in topic:
            continue
        results.append(
            {
                "title": topic.get("Text", "").split(" - ")[0][:120],
                "url": topic.get("FirstURL") or "",
                "snippet": topic.get("Text", ""),
                "source": "duckduckgo",
            }
        )
    return results[:max_results]


def _run_search_sync(query: str, source: str, max_results: int) -> list[dict]:
    if source == "arxiv":
        return _search_arxiv(query, max_results)

    tavily_key = os.environ.get("TAVILY_API_KEY")
    if tavily_key:
        return _search_tavily(query, max_results, tavily_key)

    return _search_duckduckgo(query, max_results)


@tool(
    name="web_search",
    description=(
        "Search the web for documentation, research papers, Kaggle datasets, "
        "or Stack Overflow answers. Returns search results with titles, URLs, "
        "and snippets."
    ),
    category="utility",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query",
            },
            "source": {
                "type": "string",
                "enum": ["general", "arxiv", "kaggle", "stackoverflow", "docs"],
                "default": "general",
                "description": "Search source",
            },
            "max_results": {
                "type": "integer",
                "default": 5,
                "description": "Maximum number of results to return",
            },
        },
        "required": ["query"],
    },
    timeout=30,
    prompt=(
        "Searches the web for information.\n\n"
        "## Sources\n"
        "- general: DuckDuckGo Instant Answer (or Tavily if TAVILY_API_KEY set)\n"
        "- arxiv: research papers via arxiv.org public API\n"
        "- kaggle / stackoverflow / docs: routed through the general backend\n\n"
        "## Tips\n"
        "- Be specific: 'lightgbm early stopping classification' > 'model training'\n"
        "- Prefer `arxiv` for research; `general` for APIs/best practices\n"
        "- Set `TAVILY_API_KEY` for higher-quality general search"
    ),
)
async def web_search(query: str, source: str = "general", max_results: int = 5) -> str:
    if os.environ.get("WEB_SEARCH_DISABLED") == "1":
        return _disabled_response(
            query,
            source,
            "Web search explicitly disabled via WEB_SEARCH_DISABLED=1.",
        )

    try:
        results = await asyncio.to_thread(_run_search_sync, query, source, max_results)
    except urllib.error.URLError as e:
        return _disabled_response(query, source, f"Web search network error: {e.reason}")
    except (TimeoutError, OSError) as e:
        return _disabled_response(query, source, f"Web search I/O error: {e}")
    except ET.ParseError as e:
        return _disabled_response(query, source, f"arxiv response parse error: {e}")
    except json.JSONDecodeError as e:
        return _disabled_response(query, source, f"Web search response parse error: {e}")

    return json.dumps(
        {
            "query": query,
            "source": source,
            "count": len(results),
            "results": results,
        }
    )
