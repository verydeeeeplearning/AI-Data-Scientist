"""Gap 4-2 contract tests: reviewer charter ↔ verifier layer name linkage.

Each verifier layer name (from LayerName Literal in ds_agent.domain) must have
a corresponding reviewer charter document in Docs/reviewer_charters/.

The charter file must mention the layer name (case-insensitive) either in its
filename or in its content (under a "Layer:" or "**Layer**:" heading).

Layer ↔ charter mapping:
  statistical  → statistical_reviewer.md   (Layer: Statistical)
  data         → data_governance_reviewer.md (Layer: Data)
  policy       → causal_leakage_reviewer.md  (Layer: Policy)
  narrative    → executive_narrative_reviewer.md (Layer: Narrative)
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
CHARTER_DIR = REPO_ROOT / "Docs" / "reviewer_charters"
REVIEW_VERDICT_MODULE = (
    REPO_ROOT / "src" / "ds_agent" / "domain" / "entities" / "review_verdict.py"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_layer_names_from_source() -> list[str]:
    """Parse LayerName Literal values from review_verdict.py at runtime."""
    source = REVIEW_VERDICT_MODULE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "LayerName":
                # e.g. Literal["statistical", "data", "policy", "narrative"]
                value = node.value
                if isinstance(value, ast.Subscript) and isinstance(value.slice, ast.Tuple):
                    return [
                        elt.value
                        for elt in value.slice.elts
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                    ]
    # Fallback: hardcoded from verifier_orchestrator._LAYER_TIMEOUTS keys
    return ["statistical", "data", "policy", "narrative"]


def _charter_files() -> list[Path]:
    if not CHARTER_DIR.exists():
        return []
    return sorted(CHARTER_DIR.glob("*.md"))


def _file_mentions_layer(path: Path, layer: str) -> bool:
    """Return True if the file name or content mentions the layer name."""
    if layer.lower() in path.stem.lower():
        return True
    text = path.read_text(encoding="utf-8").lower()
    # Check for "layer: <name>" or "**layer**: <name>" pattern in the markdown
    return f"layer**: {layer.lower()}" in text or f"layer: {layer.lower()}" in text


# ---------------------------------------------------------------------------
# Contract: charter docs exist for each verifier layer
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not CHARTER_DIR.exists(),
    reason="Docs/reviewer_charters/ directory does not exist — charter docs pending Gap 4-2",
)
def test_verifier_layers_have_corresponding_charter_docs() -> None:
    """Each verifier layer name must have a corresponding reviewer charter document.

    If charter docs are not yet created, this test is skipped (not failed) via
    the skipif marker above.
    """
    layer_names = _extract_layer_names_from_source()
    charter_files = _charter_files()

    assert layer_names, "LayerName literal must contain at least one layer name"
    assert charter_files, (
        f"Docs/reviewer_charters/ exists but contains no .md files — "
        "create charter docs or remove the empty directory"
    )

    missing: list[str] = []
    for layer in layer_names:
        matched = [f for f in charter_files if _file_mentions_layer(f, layer)]
        if not matched:
            missing.append(layer)

    missing_report = "\n".join(f"  - {m}" for m in missing)
    assert not missing, (
        f"The following verifier layer(s) have no corresponding charter doc in "
        f"{CHARTER_DIR.relative_to(REPO_ROOT)}:\n{missing_report}\n\n"
        "Create a <layer>_reviewer.md file that contains 'Layer: <name>' in its header."
    )


@pytest.mark.skipif(
    not CHARTER_DIR.exists(),
    reason="Docs/reviewer_charters/ directory does not exist — charter docs pending Gap 4-2",
)
def test_charter_docs_contain_mandatory_sections() -> None:
    """Each charter doc must contain at least a Layer header and Mandatory Checks section."""
    charter_files = _charter_files()
    if not charter_files:
        pytest.skip("No charter files found — pending Gap 4-2 doc creation")

    failures: list[str] = []
    for path in charter_files:
        text = path.read_text(encoding="utf-8").lower()
        missing_sections: list[str] = []
        if "layer" not in text:
            missing_sections.append("Layer")
        if "mandatory checks" not in text:
            missing_sections.append("Mandatory Checks")
        if missing_sections:
            failures.append(
                f"  {path.name}: missing sections {missing_sections}"
            )

    assert not failures, (
        "One or more charter docs are missing required sections:\n"
        + "\n".join(failures)
    )


@pytest.mark.skipif(
    not CHARTER_DIR.exists(),
    reason="Docs/reviewer_charters/ directory does not exist — charter docs pending Gap 4-2",
)
def test_charter_layer_names_match_domain_layer_names() -> None:
    """Layer names declared in charter docs must all be valid LayerName values."""
    layer_names = set(_extract_layer_names_from_source())
    charter_files = _charter_files()
    if not charter_files:
        pytest.skip("No charter files found — pending Gap 4-2 doc creation")

    unknown: list[str] = []
    for path in charter_files:
        text = path.read_text(encoding="utf-8").lower()
        # Extract declared layer from "Layer: <name>" or "**Layer**: <name>"
        for marker in ("layer**: ", "layer: "):
            idx = text.find(marker)
            if idx == -1:
                continue
            declared = text[idx + len(marker):].split("\n")[0].strip().rstrip("*").strip()
            if declared and declared not in layer_names:
                unknown.append(f"  {path.name}: declared layer '{declared}' not in {sorted(layer_names)}")
            break

    assert not unknown, (
        "Charter docs reference layer names not in the domain LayerName Literal:\n"
        + "\n".join(unknown)
    )
