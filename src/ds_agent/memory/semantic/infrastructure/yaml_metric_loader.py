"""YAML loaders for semantic metric packs."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import yaml

from ds_agent.memory.semantic.application.ports import LoadedMetricPack
from ds_agent.memory.semantic.domain.glossary import GlossaryTerm
from ds_agent.memory.semantic.domain.metric import Metric
from ds_agent.memory.semantic.domain.trust import TableTrust
from ds_agent.memory.semantic.domain.verified_query import VerifiedQuery

# Re-export for backward compatibility.
__all__ = ["LoadedMetricPack", "YamlMetricLoader"]

_SUPPORTED_EXTENSIONS = (".yaml", ".yml")
_SUPPORTED_SQL_EXTENSIONS = (".sql",)
_SEMANTIC_SCHEMA_VERSION = 6


class YamlMetricLoader:
    """Load semantic metric definitions from a pack directory."""

    def __init__(self, *, required_schema_version: int = _SEMANTIC_SCHEMA_VERSION) -> None:
        self._required_schema_version = required_schema_version

    def load_pack(self, pack_dir: str | Path) -> LoadedMetricPack:
        resolved = Path(pack_dir).resolve()
        metadata = self._load_pack_metadata(resolved)
        metric_paths = self._discover_paths(
            resolved,
            directory="metrics",
            extensions=_SUPPORTED_EXTENSIONS,
        )
        glossary_paths = self._discover_paths(
            resolved,
            directory="glossary",
            extensions=_SUPPORTED_EXTENSIONS,
        )
        trust_paths = self._discover_paths(
            resolved,
            directory="trust",
            extensions=_SUPPORTED_EXTENSIONS,
        )
        verified_query_paths = self._discover_paths(
            resolved,
            directory="verified_queries",
            extensions=_SUPPORTED_SQL_EXTENSIONS,
        )
        artifact_paths = [*metric_paths, *glossary_paths, *trust_paths, *verified_query_paths]
        self._validate_checksum(resolved, metadata, artifact_paths)
        metrics = self.load_metrics(metric_paths)
        glossary_terms = self.load_glossary_terms(glossary_paths)
        table_trust = self.load_table_trust(trust_paths)
        verified_queries = self.load_verified_queries(verified_query_paths)
        return LoadedMetricPack(
            pack_dir=resolved,
            pack_metadata=metadata,
            metrics=metrics,
            glossary_terms=glossary_terms,
            table_trust=table_trust,
            verified_queries=verified_queries,
        )

    def compute_pack_checksum(self, pack_dir: str | Path) -> str:
        """Compute the canonical checksum for one semantic pack."""

        resolved = Path(pack_dir).resolve()
        metadata = self._load_pack_metadata(resolved)
        artifact_paths = [
            *self._discover_paths(resolved, directory="metrics", extensions=_SUPPORTED_EXTENSIONS),
            *self._discover_paths(resolved, directory="glossary", extensions=_SUPPORTED_EXTENSIONS),
            *self._discover_paths(resolved, directory="trust", extensions=_SUPPORTED_EXTENSIONS),
            *self._discover_paths(
                resolved,
                directory="verified_queries",
                extensions=_SUPPORTED_SQL_EXTENSIONS,
            ),
        ]
        return self._compute_pack_checksum(resolved, metadata, artifact_paths)

    def load_metrics(self, metric_paths: Sequence[str | Path]) -> list[Metric]:
        return self._load_unique_yaml_models(
            metric_paths,
            model_loader=lambda path: Metric.model_validate(self._read_yaml_mapping(path)),
            id_getter=lambda item: item.metric_id,
            label="metric_id",
        )

    def load_glossary_terms(self, glossary_paths: Sequence[str | Path]) -> list[GlossaryTerm]:
        return self._load_unique_yaml_models(
            glossary_paths,
            model_loader=lambda path: GlossaryTerm.model_validate(self._read_yaml_mapping(path)),
            id_getter=lambda item: item.term_id,
            label="term_id",
        )

    def load_table_trust(self, trust_paths: Sequence[str | Path]) -> list[TableTrust]:
        return self._load_unique_yaml_models(
            trust_paths,
            model_loader=lambda path: TableTrust.model_validate(self._read_yaml_mapping(path)),
            id_getter=lambda item: item.fqtn,
            label="fqtn",
        )

    def load_verified_queries(
        self,
        verified_query_paths: Sequence[str | Path],
    ) -> list[VerifiedQuery]:
        return self._load_unique_yaml_models(
            verified_query_paths,
            model_loader=self._load_verified_query,
            id_getter=lambda item: item.vq_id,
            label="vq_id",
        )

    def _load_pack_metadata(self, pack_dir: Path) -> dict[str, Any]:
        pack_yaml = pack_dir / "pack.yaml"
        if not pack_yaml.exists():
            return {}
        metadata = self._read_yaml_mapping(pack_yaml)
        schema_version = metadata.get("requires_semantic_layer_schema_version")
        if schema_version is not None and int(schema_version) != self._required_schema_version:
            raise ValueError(
                "semantic pack schema version mismatch: "
                f"expected {self._required_schema_version}, got {schema_version}"
            )
        return metadata

    def _validate_checksum(
        self,
        pack_dir: Path,
        metadata: dict[str, Any],
        metric_paths: Sequence[Path],
    ) -> None:
        expected = metadata.get("checksum")
        if expected is None:
            return
        if not isinstance(expected, str) or not expected.startswith("sha256:"):
            raise ValueError("semantic pack checksum must use the 'sha256:<digest>' format")

        actual = self._compute_pack_checksum(pack_dir, metadata, metric_paths)
        if actual != expected:
            raise ValueError(
                f"semantic pack checksum mismatch: expected {expected}, got {actual}"
            )

    @staticmethod
    def _compute_pack_checksum(
        pack_dir: Path,
        metadata: dict[str, Any],
        metric_paths: Sequence[Path],
    ) -> str:
        hasher = hashlib.sha256()
        checksum_metadata = dict(metadata)
        checksum_metadata.pop("checksum", None)
        metadata_payload = json.dumps(
            checksum_metadata,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        hasher.update(b"pack.yaml\0")
        hasher.update(metadata_payload)

        for path in sorted(metric_paths, key=lambda item: item.relative_to(pack_dir).as_posix()):
            hasher.update(path.relative_to(pack_dir).as_posix().encode("utf-8"))
            hasher.update(b"\0")
            hasher.update(path.read_bytes())

        return f"sha256:{hasher.hexdigest()}"

    @staticmethod
    def _discover_paths(
        pack_dir: Path,
        *,
        directory: str,
        extensions: Sequence[str],
    ) -> list[Path]:
        target_dir = pack_dir / directory
        if not target_dir.exists():
            return []
        return sorted(
            path
            for path in target_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in extensions
        )

    def _load_unique_yaml_models(
        self,
        paths: Sequence[str | Path],
        *,
        model_loader: Callable[[Path], Any],
        id_getter: Callable[[Any], str],
        label: str,
    ) -> list[Any]:
        items: list[Any] = []
        seen_ids: dict[str, Path] = {}
        for raw_path in paths:
            path = Path(raw_path).resolve()
            item = model_loader(path)
            item_id = id_getter(item)
            previous = seen_ids.get(item_id)
            if previous is not None:
                raise ValueError(f"duplicate {label} '{item_id}' in {path} and {previous}")
            seen_ids[item_id] = path
            items.append(item)
        return items

    @staticmethod
    def _read_yaml_mapping(path: Path) -> dict[str, Any]:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"expected a YAML mapping in {path}")
        return payload

    def _load_verified_query(self, path: Path) -> VerifiedQuery:
        metadata, sql_template = self._read_frontmatter_document(path)
        metadata["sql_template"] = sql_template
        return VerifiedQuery.model_validate(metadata)

    @staticmethod
    def _read_frontmatter_document(path: Path) -> tuple[dict[str, Any], str]:
        text = path.read_text(encoding="utf-8").strip()
        if not text.startswith("---"):
            raise ValueError(f"verified query file must start with YAML frontmatter: {path}")
        parts = text.split("---", 2)
        if len(parts) < 3:
            raise ValueError(f"invalid verified query frontmatter in {path}")
        metadata = yaml.safe_load(parts[1])
        if not isinstance(metadata, dict):
            raise ValueError(f"verified query frontmatter must be a mapping in {path}")
        sql_template = parts[2].strip()
        if not sql_template:
            raise ValueError(f"verified query SQL body is required in {path}")
        return metadata, sql_template
