"""
Isolated persistence for AI outputs (not part of canonical deterministic stores).
"""

from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class AiOutputStore(ABC):
    @abstractmethod
    def append(
        self,
        *,
        workflow_id: str,
        evaluation_run_id: str,
        ai_output: Dict[str, Any],
        stored_at: Optional[str] = None,
    ) -> str:
        """Returns record_id."""

    @abstractmethod
    def list_for_workflow(self, workflow_id: str) -> List[Dict[str, Any]]:
        raise NotImplementedError


class InMemoryAiOutputStore(AiOutputStore):
    def __init__(self) -> None:
        self._records: List[Dict[str, Any]] = []

    def append(
        self,
        *,
        workflow_id: str,
        evaluation_run_id: str,
        ai_output: Dict[str, Any],
        stored_at: Optional[str] = None,
    ) -> str:
        rid = f"rec_{uuid.uuid4().hex[:16]}"
        ts = stored_at or datetime.now(timezone.utc).isoformat()
        self._records.append(
            {
                "record_id": rid,
                "workflow_id": workflow_id,
                "evaluation_run_id": evaluation_run_id,
                "stored_at": ts,
                "ai_output": dict(ai_output),
            }
        )
        return rid

    def list_for_workflow(self, workflow_id: str) -> List[Dict[str, Any]]:
        return [r for r in self._records if r.get("workflow_id") == workflow_id]

    def clear(self) -> None:
        self._records.clear()


class AppendOnlyJsonlStore(AiOutputStore):
    """Append-only JSON lines file; suitable for auxiliary audit logs."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def append(
        self,
        *,
        workflow_id: str,
        evaluation_run_id: str,
        ai_output: Dict[str, Any],
        stored_at: Optional[str] = None,
    ) -> str:
        rid = f"rec_{uuid.uuid4().hex[:16]}"
        ts = stored_at or datetime.now(timezone.utc).isoformat()
        row = {
            "record_id": rid,
            "workflow_id": workflow_id,
            "evaluation_run_id": evaluation_run_id,
            "stored_at": ts,
            "ai_output": dict(ai_output),
        }
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, default=str) + "\n")
        return rid

    def list_for_workflow(self, workflow_id: str) -> List[Dict[str, Any]]:
        if not self._path.is_file():
            return []
        out: List[Dict[str, Any]] = []
        with open(self._path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                if row.get("workflow_id") == workflow_id:
                    out.append(row)
        return out
