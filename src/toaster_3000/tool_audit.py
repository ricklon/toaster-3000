"""Audit log for dynamic tool registration attempts."""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

DEFAULT_TOOL_AUDIT_PATH = Path.home() / ".toaster3000" / "tool_audit.jsonl"


@dataclass
class ToolAuditEntry:
    """One dynamic-tool registration decision."""

    session_id: str
    tool_name: str
    description: str
    risk_level: str
    outcome: str
    reasons: List[str]
    python_code: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class ToolAuditStore:
    """Thread-safe JSONL audit store for dynamic tool attempts."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = path or DEFAULT_TOOL_AUDIT_PATH
        self._lock = Lock()

    def append(self, entry: ToolAuditEntry) -> None:
        """Append an entry to the audit log."""
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "a") as f:
                f.write(json.dumps(asdict(entry), sort_keys=True) + "\n")

    def list_recent(
        self,
        limit: int = 20,
        session_id: Optional[str] = None,
    ) -> List[ToolAuditEntry]:
        """Return recent entries, newest first."""
        with self._lock:
            if not self._path.exists():
                return []
            lines = self._path.read_text().splitlines()

        entries: List[ToolAuditEntry] = []
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                data: Dict[str, Any] = json.loads(line)
                entry = ToolAuditEntry(**data)
            except Exception:
                continue
            if session_id is not None and entry.session_id != session_id:
                continue
            entries.append(entry)
            if len(entries) >= limit:
                break
        return entries
