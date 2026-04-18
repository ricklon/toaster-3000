"""Session management for Toaster 3000."""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Dict, Optional

from toaster_3000.session import ToasterSession

if TYPE_CHECKING:
    from toaster_3000.runtime import ToasterRuntime


class SessionManager:
    """Manages all active Toaster sessions.

    This class is responsible for creating, retrieving, and destroying
    user sessions. Each session is isolated from others.
    """

    def __init__(self, runtime: "ToasterRuntime"):
        """Initialize session manager.

        Args:
            runtime: Shared runtime instance with model references
        """
        self.runtime = runtime
        self._sessions: Dict[str, ToasterSession] = {}
        self._lock = Lock()

    def _find_recent_snapshot(self) -> Optional[dict]:
        """Return the most recent valid snapshot younger than max_snapshot_age_hours."""
        snap_dir = Path(os.path.expanduser("~/.toaster3000/sessions"))
        if not snap_dir.exists():
            return None
        max_age_secs = self.runtime.config.max_snapshot_age_hours * 3600
        best = None
        best_time = None
        for path in snap_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                saved_at = datetime.fromisoformat(data["saved_at"])
                age = (datetime.now(timezone.utc) - saved_at).total_seconds()
                if age <= max_age_secs:
                    if best_time is None or saved_at > best_time:
                        best = data
                        best_time = saved_at
            except Exception:
                continue
        return best

    def create_session(self) -> str:
        """Create a new session, restoring the most recent snapshot if available.

        Returns:
            Unique session identifier
        """
        snapshot = self._find_recent_snapshot()
        if snapshot:
            session_id = snapshot["session_id"]
            print(f"Restoring session from snapshot: {session_id}")
        else:
            session_id = str(uuid.uuid4())

        session = ToasterSession(session_id, self.runtime)

        if snapshot:
            try:
                session.restore_from_snapshot(snapshot)
                print(f"Session restored: {len(session.chat_history.get_all())} messages, "
                      f"{len(session._custom_tools)} tools")
            except Exception as e:
                print(f"Snapshot restore failed, starting fresh: {e}")

        with self._lock:
            self._sessions[session_id] = session

        return session_id

    def get_session(self, session_id: str) -> Optional[ToasterSession]:
        """Get existing session by ID.

        Args:
            session_id: Session identifier

        Returns:
            ToasterSession instance or None if not found
        """
        with self._lock:
            return self._sessions.get(session_id)

    def destroy_session(self, session_id: str) -> bool:
        """Clean up and remove a session.

        Args:
            session_id: Session identifier to destroy

        Returns:
            True if session was found and destroyed, False otherwise
        """
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    def get_session_count(self) -> int:
        """Get number of active sessions.

        Returns:
            Count of active sessions
        """
        with self._lock:
            return len(self._sessions)

    def list_sessions(self) -> list:
        """List all active session IDs.

        Returns:
            List of session ID strings
        """
        with self._lock:
            return list(self._sessions.keys())

    def refresh_all_agents(self) -> None:
        """Rebuild each session's agent after a model switch."""
        with self._lock:
            sessions = list(self._sessions.values())
        for session in sessions:
            session.refresh_agent()

    def clear_all_sessions(self) -> int:
        """Destroy all sessions.

        WARNING: Use with caution. This will disconnect all users.

        Returns:
            Number of sessions cleared
        """
        with self._lock:
            count = len(self._sessions)
            self._sessions.clear()
            return count
