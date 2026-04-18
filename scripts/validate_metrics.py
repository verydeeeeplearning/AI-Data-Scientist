"""Validate semantic metric pack YAML files."""

from __future__ import annotations

import argparse
from pathlib import Path

from ds_agent.memory.semantic.infrastructure.yaml_metric_loader import YamlMetricLoader


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate semantic metric YAML definitions in a pack directory.",
    )
    parser.add_argument("pack_dir", help="Path to the semantic pack root directory")
    args = parser.parse_args()

    pack_dir = Path(args.pack_dir).resolve()
    loader = YamlMetricLoader()
    loaded = loader.load_pack(pack_dir)
    schema_version = loaded.pack_metadata.get(
        "requires_semantic_layer_schema_version",
        "n/a",
    )
    checksum = loaded.pack_metadata.get("checksum") or loader.compute_pack_checksum(pack_dir)
    print(
        "[validate_metrics] ok "
        f"pack={pack_dir} "
        f"metrics={len(loaded.metrics)} "
        f"glossary={len(loaded.glossary_terms)} "
        f"trust={len(loaded.table_trust)} "
        f"verified_queries={len(loaded.verified_queries)} "
        f"schema_version={schema_version} checksum={checksum}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
