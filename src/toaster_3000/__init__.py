"""Toaster 3000 - AI voice agent with toaster personality."""

from toaster_3000.config import ToasterConfig
from toaster_3000.session import ChatHistoryManager, ToasterSession
from toaster_3000.session_manager import SessionManager

__version__ = "0.1.0"

__all__ = [
    "ToasterConfig",
    "ChatHistoryManager",
    "ToasterSession",
    "SessionManager",
]


def hello() -> str:
    """Return a greeting message."""
    return "Hello from toaster-3000!"
