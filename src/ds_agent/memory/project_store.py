"""Project store — per-project artifact management."""

from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path

import structlog

logger = structlog.get_logger()


class ProjectStore:
    """File-based project workspace management."""

    def __init__(self, data_dir: str = "data/projects") -> None:
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        # 4.7 fix: protect per-project read-modify-write from concurrent access
        self._lock = threading.Lock()

    def create_project(
        self,
        name: str,
        description: str = "",
        task_type: str | None = None,
    ) -> str:
        """Create a new project workspace. Returns project ID."""
        project_id = str(uuid.uuid4())[:8]
        project_dir = self._dir / project_id

        # Create directory structure
        (project_dir / "artifacts").mkdir(parents=True, exist_ok=True)
        (project_dir / "plots").mkdir(parents=True, exist_ok=True)
        (project_dir / "models").mkdir(parents=True, exist_ok=True)

        # Save metadata
        meta: dict[str, object] = {
            "id": project_id,
            "name": name,
            "description": description,
            "task_type": task_type,
            "artifacts": [],
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        (project_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return project_id

    def get_project(self, project_id: str) -> dict | None:
        """Get project metadata."""
        meta_file = self._dir / project_id / "meta.json"
        if not meta_file.exists():
            return None
        try:
            return dict(json.loads(meta_file.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("project_meta_load_failed", project_id=project_id, error=str(e))
            return None

    def list_projects(self) -> list[dict]:
        """List all projects."""
        projects = []
        for d in sorted(self._dir.iterdir()):
            if d.is_dir() and (d / "meta.json").exists():
                try:
                    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError) as e:
                    logger.warning("project_meta_load_failed", project_id=d.name, error=str(e))
                    continue
                projects.append(meta)
        return projects

    def register_artifact(
        self,
        project_id: str,
        artifact_type: str,
        file_path: str,
        description: str = "",
    ) -> None:
        """Register an artifact for a project."""
        meta_file = self._dir / project_id / "meta.json"
        if not meta_file.exists():
            return

        # 4.7 fix: lock the full read-modify-write to prevent concurrent data loss
        with self._lock:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            meta["artifacts"].append(
                {
                    "type": artifact_type,
                    "path": file_path,
                    "description": description,
                    "timestamp": time.time(),
                }
            )
            meta["updated_at"] = time.time()
            meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    def get_project_dir(self, project_id: str) -> Path:
        """Get the project workspace directory path."""
        return self._dir / project_id
