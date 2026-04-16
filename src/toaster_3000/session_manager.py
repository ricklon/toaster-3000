"""Session management for Toaster 3000."""

import uuid
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

    def create_session(self) -> str:
        """Create new session and return session ID.

        Returns:
            Unique session identifier
        """
        session_id = str(uuid.uuid4())
        session = ToasterSession(session_id, self.runtime)

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
