"""Session management for Toaster 3000."""

import html
import threading
import time
from collections import deque
from threading import Lock
from typing import TYPE_CHECKING, Any, Dict, Generator, List, Optional, Tuple

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

    def format_html(self, extra_html: str = "") -> str:
        """Format history as HTML with proper escaping.

        Args:
            extra_html: Optional HTML appended inside the container (e.g. thinking indicator).

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
            if extra_html:
                formatted += extra_html
            formatted += "</div>"
            return formatted

    def format_html_thinking(self, status: str = "Toasting your response") -> str:
        """Return history HTML with an animated thinking indicator appended."""
        return self.format_html(extra_html=f"<div class='thinking'>🍞 {status}…</div>")

    def format_html_partial(self, partial: str) -> str:
        """Return history HTML with a partially-streamed bot message appended."""
        safe = html.escape(partial)
        return self.format_html(
            extra_html=(
                f"<div class='bot-message bot-message--streaming'>"
                f"<strong>Toaster 3000:</strong> {safe}"
                f"</div>"
            )
        )


# Human-readable status messages shown in the thinking bubble per tool call
_TOOL_STATUS: Dict[str, str] = {
    "toast_calculator": "Calculating toast time",
    "find_toast_recipe": "Finding a recipe",
    "toast_coder": "Writing toast code",
    "register_toast_tool": "Registering your tool",
    "save_recipe": "Saving recipe to your collection",
    "list_recipes": "Browsing your recipe collection",
    "get_recipe": "Looking up that recipe",
}


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

        # Custom tools registered at runtime via register_toast_tool
        self._custom_tools: List[Any] = []
        # Queue for tools registered mid-run (rebuilt after run completes)
        self._pending_registrations: List[tuple] = []

        # Rate limiting
        from toaster_3000.rate_limit import PerSessionCooldown, TokenBucket
        self._rate_limiter = TokenBucket(
            rate=runtime.config.rate_limit_runs_per_minute / 60.0,
            capacity=float(runtime.config.rate_limit_runs_per_minute),
        )
        self._register_cooldown = PerSessionCooldown(runtime.config.tool_register_cooldown_secs)

        # Each session owns its agent to prevent cross-session memory leakage
        self.agent = self._build_agent()

        # Add intro message to chat display; audio plays via WebRTC on first turn
        self.chat_history.add_message("assistant", TOASTER_INTRO)
        self._intro_played = False
        self.last_active: float = time.time()
        self._countdown_html: str = ""
        self._voice_state: str = "sleeping"
        # Persisted source for registered tools so they survive restarts
        self._registered_tool_sources: List[tuple] = []

    def _build_agent(self) -> Any:
        """Create a ToolCallingAgent with the full toast tool suite."""
        from smolagents import ToolCallingAgent

        from toaster_3000.constants import TOASTER_SYSTEM_PROMPT
        from toaster_3000.tools import (
            GetRecipeTool,
            ListRecipesTool,
            RegisterToolTool,
            SaveRecipeTool,
            ToastCoderTool,
            find_toast_recipe,
            toast_calculator,
        )

        tools = [
            toast_calculator,
            find_toast_recipe,
            ToastCoderTool(self.runtime.model),
            RegisterToolTool(self._queue_tool_registration),
            SaveRecipeTool(self.runtime.recipe_store),
            ListRecipesTool(self.runtime.recipe_store),
            GetRecipeTool(self.runtime.recipe_store),
        ] + list(self._custom_tools)

        return ToolCallingAgent(
            tools=tools,
            model=self.runtime.model,
            max_steps=self._agent_steps,
            instructions=TOASTER_SYSTEM_PROMPT,
        )

    def _queue_tool_registration(
        self, tool_name: str, python_code: str, description: str
    ) -> str:
        """Called by RegisterToolTool during a run — queues for post-run processing."""
        if not self._register_cooldown.check_and_record():
            secs = self._register_cooldown.seconds_remaining()
            return (
                f"Tool registration is on cooldown — please wait "
                f"{secs:.0f}s before registering another tool."
            )

        from toaster_3000.tool_audit import ToolAuditEntry
        from toaster_3000.tools import (
            RISK_NONE,
            TOOL_RISK_POLICY_TEXT,
            assess_dynamic_tool,
        )

        assessment = assess_dynamic_tool(tool_name, python_code)
        if not assessment.allowed:
            self.runtime.tool_audit_store.append(
                ToolAuditEntry(
                    session_id=self.session_id,
                    tool_name=tool_name,
                    description=description,
                    risk_level=assessment.level,
                    outcome="denied",
                    reasons=assessment.reasons,
                    python_code=python_code,
                )
            )
            reasons = "; ".join(assessment.reasons) or "not sandbox-approved"
            return (
                f"Tool '{tool_name}' was not registered. Risk: {assessment.level}. "
                f"Reason: {reasons}. {TOOL_RISK_POLICY_TEXT}"
            )

        self._pending_registrations.append((tool_name, python_code, description))
        return (
            f"Tool '{tool_name}' classified as risk {RISK_NONE} and queued — "
            "it will be available from your next message!"
        )

    def _flush_pending_registrations(self) -> None:
        """Compile and register any tools queued during the last agent run."""
        if not self._pending_registrations:
            return

        from toaster_3000.tool_audit import ToolAuditEntry
        from toaster_3000.tools import assess_dynamic_tool, build_dynamic_tool

        for tool_name, python_code, description in self._pending_registrations:
            assessment = assess_dynamic_tool(tool_name, python_code)
            try:
                new_tool = build_dynamic_tool(tool_name, python_code, description)
                self._custom_tools.append(new_tool)
                self._registered_tool_sources.append((tool_name, python_code, description))
                self.runtime.tool_audit_store.append(
                    ToolAuditEntry(
                        session_id=self.session_id,
                        tool_name=tool_name,
                        description=description,
                        risk_level=assessment.level,
                        outcome="registered",
                        reasons=assessment.reasons,
                        python_code=python_code,
                    )
                )
                print(f"Registered dynamic tool: {tool_name}")
            except Exception as e:
                self.runtime.tool_audit_store.append(
                    ToolAuditEntry(
                        session_id=self.session_id,
                        tool_name=tool_name,
                        description=description,
                        risk_level=assessment.level,
                        outcome="failed",
                        reasons=[str(e)],
                        python_code=python_code,
                    )
                )
                print(f"Failed to register tool '{tool_name}': {e}")

        self._pending_registrations.clear()
        # Rebuild agent so new tools appear in its tool list
        self.agent = self._build_agent()

    def get_custom_tools(self) -> List[Dict[str, str]]:
        """Return metadata for all custom tools registered in this session."""
        return [
            {"name": t.name, "description": t.description} for t in self._custom_tools
        ]

    def get_tool_audit_entries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return recent dynamic-tool registration decisions for this session."""
        entries = self.runtime.tool_audit_store.list_recent(
            limit=limit,
            session_id=self.session_id,
        )
        return [
            {
                "created_at": e.created_at,
                "tool_name": e.tool_name,
                "description": e.description,
                "risk_level": e.risk_level,
                "outcome": e.outcome,
                "reasons": e.reasons,
            }
            for e in entries
        ]

    def refresh_agent(self) -> None:
        """Rebuild the agent after a model switch, preserving chat history."""
        with self._lock:
            self.agent = self._build_agent()

    # ── Snapshot / restore ──────────────────────────────────────────────────

    def _snapshot_path(self) -> "Path":
        import os
        from pathlib import Path
        d = Path(os.path.expanduser("~/.toaster3000/sessions"))
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{self.session_id}.json"

    def save_snapshot(self) -> None:
        """Kick off a background write so the response hot path is not blocked."""
        if self.session_id.startswith("bench-"):
            return
        t = threading.Thread(target=self._write_snapshot, daemon=True)
        t.start()

    def _write_snapshot(self) -> None:
        """Persist chat history, agent steps, and registered tools to disk."""
        import json
        from datetime import datetime, timezone
        data = {
            "session_id": self.session_id,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "chat_history": self.chat_history.get_all(),
            "agent_steps": self._agent_steps,
            "registered_tool_sources": [
                {"tool_name": n, "python_code": c, "description": d}
                for n, c, d in self._registered_tool_sources
            ],
        }
        try:
            path = self._snapshot_path()
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"Failed to save snapshot: {e}")

    def restore_from_snapshot(self, data: Dict[str, Any]) -> None:
        """Restore session state from a snapshot dict."""
        from toaster_3000.tools import assess_dynamic_tool, build_dynamic_tool
        self.chat_history.clear()
        for msg in data.get("chat_history", []):
            self.chat_history.add_message(msg["role"], msg["content"])
        self._agent_steps = data.get("agent_steps", self._agent_steps)
        for entry in data.get("registered_tool_sources", []):
            try:
                tool = build_dynamic_tool(
                    entry["tool_name"], entry["python_code"], entry["description"]
                )
                self._custom_tools.append(tool)
                self._registered_tool_sources.append(
                    (entry["tool_name"], entry["python_code"], entry["description"])
                )
            except Exception as e:
                print(f"Failed to restore tool '{entry['tool_name']}': {e}")
        self.agent = self._build_agent()

    def _start_toast_countdown_from_output(self, observation: str) -> None:
        """Parse toast duration from tool output text and start countdown."""
        import re
        m = re.search(r"Time\s*[:\-]\s*(\d+)\s*s", observation, re.IGNORECASE)
        duration = int(m.group(1)) if m else 60
        self._start_toast_countdown(duration)

    def _start_toast_countdown(self, duration: int) -> None:
        """Launch a background thread that animates a toast countdown bar."""
        duration = max(5, duration)

        def _run(session_ref, total: int) -> None:
            for remaining in range(total, -1, -1):
                pct = int((total - remaining) / total * 100)
                session_ref._countdown_html = (
                    f"<div class='countdown-bar'>"
                    f"🍞 Toasting… <strong>{remaining}s</strong> remaining"
                    f"<div class='countdown-progress' style='width:{pct}%'></div>"
                    f"</div>"
                )
                time.sleep(1)
            session_ref._countdown_html = ""

        t = threading.Thread(target=_run, args=(self, duration), daemon=True)
        t.start()

    def stream_text_input(
        self, text: str
    ) -> Generator[Tuple[str, Optional[Tuple[int, Any]]], None, None]:
        """Process text input, yielding UI states as they become available.

        Yields:
            (html, audio) tuples — audio is None for intermediate states,
            populated only on the final yield.
        """
        if not text or not text.strip():
            yield self.chat_history.format_html(), None
            return

        if not self._rate_limiter.consume():
            yield self.chat_history.format_html_partial(
                "Whoa, too many requests! Even the Toaster 3000 needs a moment to cool down. "
                "Please wait a few seconds before asking again."
            ), None
            return

        from smolagents.agents import ToolOutput as AgentToolOutput
        from smolagents.memory import FinalAnswerStep
        from smolagents.memory import ToolCall as AgentToolCall

        self.last_active = time.time()
        self.chat_history.add_message("user", text)
        yield self.chat_history.format_html_thinking(), None

        final_response = ""
        _waiting_for_toast = False
        try:
            with self._lock:
                steps = self._agent_steps

            with self.runtime.hf_semaphore:
                for event in self.agent.run(
                    text, max_steps=steps, reset=False, stream=True
                ):
                    if isinstance(event, AgentToolCall):
                        status = _TOOL_STATUS.get(event.name, f"Using {event.name}")
                        if event.name == "toast_calculator":
                            _waiting_for_toast = True
                        yield self.chat_history.format_html_thinking(status), None
                    elif isinstance(event, AgentToolOutput) and _waiting_for_toast:
                        _waiting_for_toast = False
                        self._start_toast_countdown_from_output(event.observation or "")
                    elif isinstance(event, FinalAnswerStep):
                        final_response = (
                            str(event.output) if event.output is not None else ""
                        )

            self._flush_pending_registrations()

        except Exception as e:
            final_response = (
                f"Oh crumbs! Error: {str(e)[:100]}… "
                "Would you like to talk about bread instead?"
            )

        if not final_response:
            final_response = "I'm speechless! Ask me about toast?"

        # Word-stream the final answer for a smooth reveal
        words = final_response.split()
        accumulated = ""
        for i, word in enumerate(words):
            accumulated += ("" if i == 0 else " ") + word
            yield self.chat_history.format_html_partial(accumulated), None
            time.sleep(0.015)

        self.chat_history.add_message("assistant", final_response)
        self.save_snapshot()
        audio = self._generate_tts(final_response)
        yield self.chat_history.format_html(), audio

    def get_response_text(self, user_input: str) -> str:
        """Run agent, update chat history, return response text without TTS.

        Used by the WebRTC handler so it can stream TTS chunks separately.
        """
        if not user_input or not user_input.strip():
            return ""
        self.last_active = time.time()
        self.chat_history.add_message("user", user_input)
        response = self._run_agent_with_hooks(user_input)
        self.chat_history.add_message("assistant", response)
        self.save_snapshot()
        return response

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
        agent_response = self._run_agent_with_hooks(text)

        # Add bot response
        self.chat_history.add_message("assistant", agent_response)

        # Generate audio
        audio_data = self._generate_tts(agent_response)

        return self.chat_history.format_html(), audio_data

    def _run_agent_with_hooks(self, user_input: str) -> str:
        """Run agent with streaming to enable countdown and tool hooks.

        Used by both the text and voice paths so features like the toast
        countdown bar work regardless of how the user is interacting.
        """
        from smolagents.agents import ToolOutput as AgentToolOutput
        from smolagents.memory import FinalAnswerStep
        from smolagents.memory import ToolCall as AgentToolCall

        if not self._rate_limiter.consume():
            return (
                "Whoa, too many requests! Even the Toaster 3000 needs a moment to cool down. "
                "Please wait a few seconds before asking again."
            )

        with self._lock:
            steps = self._agent_steps

        final_response = ""
        _waiting_for_toast = False
        try:
            with self.runtime.hf_semaphore:
                for event in self.agent.run(user_input, max_steps=steps, reset=False, stream=True):
                    if isinstance(event, AgentToolCall):
                        if event.name == "toast_calculator":
                            _waiting_for_toast = True
                    elif isinstance(event, AgentToolOutput) and _waiting_for_toast:
                        _waiting_for_toast = False
                        self._start_toast_countdown_from_output(event.observation or "")
                    elif isinstance(event, FinalAnswerStep):
                        final_response = str(event.output) if event.output is not None else ""
            self._flush_pending_registrations()
        except Exception as e:
            return (
                f"Oh crumbs! Error: {str(e)[:100]}... "
                f"Would you like to talk about bread instead?"
            )
        return final_response or "I'm speechless! Ask me about toast?"

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
            user_text, no_speech_prob = self.runtime.stt_service.transcribe(audio)

            if not user_text or no_speech_prob > self.runtime.config.no_speech_threshold:
                return self.chat_history.format_html(), None

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
