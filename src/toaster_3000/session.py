"""Session management for Toaster 3000."""

import html
from collections import deque
from threading import Lock
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from toaster_3000.constants import TOASTER_INTRO

if TYPE_CHECKING:
    from toaster_3000.runtime import ToasterRuntime


class ChatHistoryManager:
    """Thread-safe chat history with size limits.

    This class manages conversation history for a single session,
    ensuring thread safety and preventing memory leaks through
    bounded storage.
    """

    def __init__(self, max_size: int = 50):
        """Initialize chat history manager.

        Args:
            max_size: Maximum number of messages to retain (default: 50)
        """
        self._max_size = max_size
        self._history: deque[Dict[str, str]] = deque(maxlen=max_size)
        self._lock = Lock()

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the chat history.

        Args:
            role: Message role ("user" or "assistant")
            content: Message content (stored raw, escaped on output)
        """
        with self._lock:
            self._history.append({"role": role, "content": content})

    def get_recent(self, count: int = 10) -> List[Dict[str, str]]:
        """Get the most recent messages.

        Args:
            count: Number of recent messages to return

        Returns:
            List of message dictionaries
        """
        with self._lock:
            return list(self._history)[-count:]

    def get_all(self) -> List[Dict[str, str]]:
        """Get all messages in the chat history.

        Returns:
            List of all message dictionaries
        """
        with self._lock:
            return list(self._history)

    def clear(self) -> None:
        """Clear all chat history."""
        with self._lock:
            self._history.clear()

    def format_html(self) -> str:
        """Format history as HTML with proper escaping.

        Returns:
            HTML string with conversation formatted for display
        """
        with self._lock:
            formatted = "<div class='chat-container'>"
            for msg in self._history:
                role_class = "user-message" if msg["role"] == "user" else "bot-message"
                sender = "You" if msg["role"] == "user" else "Toaster 3000"
                # CRITICAL: Escape user content to prevent XSS
                safe_content = html.escape(msg["content"])
                formatted += (
                    f"<div class='{role_class}'>"
                    f"<strong>{sender}:</strong> {safe_content}"
                    f"</div>\n"
                )
            formatted += "</div>"
            return formatted


class ToasterSession:
    """Encapsulates all state for a single user session.

    Each user gets their own ToasterSession instance, ensuring
    complete isolation between users.
    """

    def __init__(self, session_id: str, runtime: "ToasterRuntime"):
        """Initialize a new toaster session.

        Args:
            session_id: Unique identifier for this session
            runtime: Shared runtime instance with model references
        """
        self.session_id = session_id
        self.runtime = runtime
        self.chat_history = ChatHistoryManager(max_size=runtime.config.max_chat_history)
        self._agent_steps = runtime.config.max_agent_steps
        self._lock = Lock()

        # Add intro message
        self.chat_history.add_message("assistant", TOASTER_INTRO)

    def process_text_input(self, text: str) -> Tuple[str, Optional[Tuple[int, Any]]]:
        """Process text input and return response.

        Args:
            text: User input text

        Returns:
            Tuple of (html_response, audio_data)
        """
        if not text or not text.strip():
            return self.chat_history.format_html(), None

        # Add user message
        self.chat_history.add_message("user", text)

        # Get response from agent
        agent_response = self._get_agent_response(text)

        # Add bot response
        self.chat_history.add_message("assistant", agent_response)

        # Generate audio
        audio_data = self._generate_tts(agent_response)

        return self.chat_history.format_html(), audio_data

    def _get_agent_response(self, user_input: str) -> str:
        """Get response from AI agent with conversation context.

        Args:
            user_input: User's input text

        Returns:
            Agent's response text
        """
        try:
            # Use runtime's shared agent instance
            with self._lock:
                steps = self._agent_steps

            response = self.runtime.agent.run(user_input, max_steps=steps, reset=False)
            return str(response) if response else "I'm speechless! Ask me about toast?"
        except Exception as e:
            return (
                f"Oh crumbs! Error: {str(e)[:100]}... "
                f"Would you like to talk about bread instead?"
            )

    def _generate_tts(self, text: str) -> Optional[Tuple[int, Any]]:
        """Generate TTS audio for text.

        Args:
            text: Text to convert to speech

        Returns:
            Audio data tuple (sample_rate, audio_array) or None
        """
        return self.runtime.tts_service.generate_audio(text)

    def process_audio_input(
        self, audio: Tuple[int, Any]
    ) -> Tuple[str, Optional[Tuple[int, Any]]]:
        """Process audio input and return response.

        Args:
            audio: Tuple of (sample_rate, audio_data)

        Returns:
            Tuple of (html_response, audio_response_data)
        """
        try:
            # Transcribe audio to text
            user_text = self.runtime.stt_service.transcribe(audio)

            if not user_text.strip():
                user_text = (
                    "I couldn't hear that clearly. Could you please repeat? "
                    "Perhaps you could ask me about toasting something?"
                )

            # Process as text input
            return self.process_text_input(user_text)

        except Exception as e:
            error_msg = (
                f"Oh crumbs! The Toaster 3000 encountered an error: {str(e)}. "
                f"Perhaps we should toast something to fix it?"
            )
            self.chat_history.add_message("assistant", error_msg)
            audio_data = self._generate_tts(error_msg)
            return self.chat_history.format_html(), audio_data

    def clear_chat(self) -> str:
        """Clear chat history and return formatted empty state.

        Returns:
            HTML formatted intro message
        """
        self.chat_history.clear()
        self.chat_history.add_message("assistant", TOASTER_INTRO)
        return self.chat_history.format_html()

    def set_intelligence_level(self, level: int) -> str:
        """Update agent reasoning steps.

        Args:
            level: New intelligence level (1-10)

        Returns:
            Status message
        """
        with self._lock:
            self._agent_steps = max(1, min(10, level))
            return f"Toaster intelligence set to level {self._agent_steps}!"

    def get_intelligence_level(self) -> int:
        """Get current intelligence level.

        Returns:
            Current agent steps setting
        """
        with self._lock:
            return self._agent_steps
