"""
Architecture Validation Tests for Issue 1 Solution

These tests validate that the new architecture properly addresses
the global state management issues BEFORE implementation.

Run these tests to verify the design is sound, then implement
the classes to make them pass.
"""

import sys
import threading
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestChatHistoryManagerDesign:
    """Validate ChatHistoryManager requirements"""

    def test_history_has_size_limit(self) -> None:
        """Chat history must be bounded to prevent memory leaks"""
        # This test will fail until we implement ChatHistoryManager
        from toaster_3000.session import ChatHistoryManager

        manager = ChatHistoryManager(max_size=5)

        # Add more messages than the limit
        for i in range(10):
            manager.add_message("user", f"Message {i}")

        history = manager.get_all()
        assert len(history) <= 5, "Chat history must enforce size limit"
        assert history[-1]["content"] == "Message 9", "Should keep most recent messages"
        assert history[0]["content"] == "Message 5", "Should discard oldest messages"

    def test_history_thread_safe(self) -> None:
        """Chat history must be thread-safe for concurrent access"""
        from toaster_3000.session import ChatHistoryManager

        manager = ChatHistoryManager(max_size=100)
        errors = []

        def add_messages(thread_id: int) -> None:
            try:
                for i in range(50):
                    manager.add_message("user", f"Thread {thread_id} msg {i}")
            except Exception as e:
                errors.append(e)

        # Start multiple threads
        threads = [threading.Thread(target=add_messages, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread safety errors: {errors}"
        assert len(manager.get_all()) == 100, "Should have max_size messages"

    def test_history_escapes_html(self) -> None:
        """Chat history must escape HTML to prevent XSS"""
        from toaster_3000.session import ChatHistoryManager

        manager = ChatHistoryManager()
        manager.add_message("user", "<script>alert('xss')</script>")

        html = manager.format_html()
        assert "<script>" not in html, "XSS vulnerability: script tag not escaped"
        assert "&lt;script&gt;" in html, "HTML should be properly escaped"


class TestToasterSessionDesign:
    """Validate ToasterSession requirements"""

    def test_session_isolated_state(self) -> None:
        """Each session must have isolated state"""
        from toaster_3000.runtime import ToasterRuntime
        from toaster_3000.session import ToasterSession

        config = Mock()
        config.max_chat_history = 50

        runtime = Mock(spec=ToasterRuntime)
        runtime.config = config

        session1 = ToasterSession("session-1", runtime)
        session2 = ToasterSession("session-2", runtime)

        # Add message to session1 only (session2 already has intro)
        session1.chat_history.add_message("user", "Message from session 1")

        # Session2 should not see session1's messages (only has intro)
        session2_history = session2.chat_history.get_all()
        session1_history = session1.chat_history.get_all()

        # Both have intro, but only session1 has the user message
        assert len(session1_history) == 2, "Session1 should have intro + user message"
        assert len(session2_history) == 1, "Session2 should only have intro"
        assert session1_history[-1]["content"] == "Message from session 1"
        assert (
            session2_history[-1]["role"] == "assistant"
        ), "Session2 should only have intro"

    def test_session_processes_input(self) -> None:
        """Session must process text input and return response"""
        from toaster_3000.session import ToasterSession

        config = Mock()
        config.max_agent_steps = 1
        config.max_chat_history = 50

        mock_runtime = Mock()
        mock_runtime.config = config

        session = ToasterSession("test-session", mock_runtime)

        # Mock the agent response
        mock_agent = Mock()
        mock_agent.run.return_value = "Toasty response!"
        mock_runtime.agent = mock_agent

        # Mock TTS service
        mock_tts = Mock()
        mock_tts.generate_audio.return_value = (16000, [0.0, 0.1, 0.2])
        mock_runtime.tts_service = mock_tts

        html, audio = session.process_text_input("Hello toaster!")

        assert "Hello toaster!" in html, "User message should appear in HTML"
        assert "Toasty response!" in html, "Bot response should appear in HTML"
        assert audio is not None, "Audio data should be returned"

    def test_session_clears_chat(self) -> None:
        """Session must clear chat history"""
        from toaster_3000.session import ToasterSession

        config = Mock()
        config.max_chat_history = 50

        mock_runtime = Mock()
        mock_runtime.config = config

        session = ToasterSession("test-session", mock_runtime)
        # Session starts with intro message
        assert len(session.chat_history.get_all()) == 1

        session.chat_history.add_message("user", "Test message")
        assert len(session.chat_history.get_all()) == 2

        session.clear_chat()

        # Should have intro message after clear
        history = session.chat_history.get_all()
        assert len(history) == 1, "Should have intro message after clear"
        assert history[0]["role"] == "assistant", "Intro should be from assistant"


class TestToasterRuntimeDesign:
    """Validate ToasterRuntime singleton requirements"""

    def test_runtime_is_singleton(self) -> None:
        """ToasterRuntime must be singleton"""
        from toaster_3000.runtime import ToasterRuntime

        # Reset singleton for testing
        ToasterRuntime.reset()

        config1 = Mock()
        config1.model_id = "model-1"
        config1.hf_api_key = "key-1"
        config1.max_agent_steps = 1
        config1.whisper_model_size = "tiny.en"
        config1.whisper_device = "cpu"
        config1.whisper_compute_type = "int8"
        config1.tts_voice = "am_liam"
        config1.tts_speed = 1.0
        config1.tts_lang = "en-us"

        # Patch model initialization to avoid actual loading
        with patch.object(ToasterRuntime, "_init_models"):
            runtime1 = ToasterRuntime(config1)

            config2 = Mock()
            config2.model_id = "model-2"

            # Second call should return same instance
            runtime2 = ToasterRuntime(config2)

            assert runtime1 is runtime2, "ToasterRuntime must be singleton"
            assert (
                runtime1.config.model_id == "model-1"
            ), "Config should not change after first init"

    def test_runtime_requires_config_on_first_init(self) -> None:
        """ToasterRuntime must require config on first initialization"""
        from toaster_3000.runtime import ToasterRuntime

        ToasterRuntime.reset()

        with pytest.raises(RuntimeError, match="ToasterRuntime must be initialized"):
            ToasterRuntime()  # No config provided

    def test_runtime_thread_safe_initialization(self) -> None:
        """ToasterRuntime initialization must be thread-safe"""
        from toaster_3000.runtime import ToasterRuntime

        ToasterRuntime.reset()

        config = Mock()
        config.model_id = "test-model"
        config.hf_api_key = "test-key"
        config.max_agent_steps = 1
        config.whisper_model_size = "tiny.en"
        config.whisper_device = "cpu"
        config.whisper_compute_type = "int8"
        config.tts_voice = "am_liam"
        config.tts_speed = 1.0
        config.tts_lang = "en-us"

        instances = []
        errors = []

        def create_runtime() -> None:
            try:
                with patch.object(ToasterRuntime, "_init_models"):
                    instance = ToasterRuntime(config)
                    instances.append(instance)
            except Exception as e:
                errors.append(e)

        # Try to create multiple instances simultaneously
        threads = [threading.Thread(target=create_runtime) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread safety errors: {errors}"
        # All threads should get the same instance
        assert (
            len(set(id(i) for i in instances)) == 1
        ), "All threads must get same instance"


class TestSessionManagerDesign:
    """Validate SessionManager requirements"""

    def _create_mock_runtime(self) -> Any:
        """Helper to create a properly mocked runtime"""
        mock_runtime = Mock()
        mock_config = Mock()
        mock_config.max_chat_history = 50
        mock_config.max_agent_steps = 1
        mock_runtime.config = mock_config
        return mock_runtime

    def test_session_manager_creates_unique_sessions(self) -> None:
        """SessionManager must create unique sessions"""
        from toaster_3000.session_manager import SessionManager

        mock_runtime = self._create_mock_runtime()
        manager = SessionManager(mock_runtime)

        session_id1 = manager.create_session()
        session_id2 = manager.create_session()

        assert session_id1 != session_id2, "Session IDs must be unique"
        assert manager.get_session_count() == 2

    def test_session_manager_retrieves_sessions(self) -> None:
        """SessionManager must retrieve sessions by ID"""
        from toaster_3000.session_manager import SessionManager

        mock_runtime = self._create_mock_runtime()
        manager = SessionManager(mock_runtime)

        session_id = manager.create_session()
        session = manager.get_session(session_id)

        assert session is not None, "Should retrieve existing session"
        assert session.session_id == session_id

    def test_session_manager_returns_none_for_invalid_session(self) -> None:
        """SessionManager must return None for invalid session IDs"""
        from toaster_3000.session_manager import SessionManager

        mock_runtime = self._create_mock_runtime()
        manager = SessionManager(mock_runtime)

        session = manager.get_session("non-existent-id")
        assert session is None, "Should return None for invalid session"

    def test_session_manager_destroys_sessions(self) -> None:
        """SessionManager must properly clean up sessions"""
        from toaster_3000.session_manager import SessionManager

        mock_runtime = self._create_mock_runtime()
        manager = SessionManager(mock_runtime)

        session_id = manager.create_session()
        assert manager.get_session_count() == 1

        manager.destroy_session(session_id)
        assert manager.get_session_count() == 0
        assert manager.get_session(session_id) is None


class TestDependencyInjectionDesign:
    """Validate dependency injection requirements"""

    def test_no_global_state_access(self) -> None:
        """Functions must not access global state"""
        import ast

        # Read the new implementation file
        new_file = Path(__file__).parent.parent / "src" / "toaster_3000" / "session.py"

        if not new_file.exists():
            pytest.skip("New implementation not created yet")

        with open(new_file) as f:
            tree = ast.parse(f.read())

        # Check for global keyword usage
        global_usage = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Global):
                global_usage.append(node.names)

        assert len(global_usage) == 0, f"Found global keyword usage: {global_usage}"

    def test_explicit_dependencies(self) -> None:
        """Classes must declare dependencies explicitly"""
        import inspect

        from toaster_3000.session import ToasterSession

        sig = inspect.signature(ToasterSession.__init__)
        params = list(sig.parameters.keys())

        assert "session_id" in params, "Session ID must be explicit parameter"
        assert "runtime" in params, "Runtime dependency must be explicit parameter"


class TestNoGlobalVariables:
    """Ensure no global variables exist in new implementation"""

    def test_no_module_level_mutable_state(self) -> None:
        """New implementation must not have module-level mutable state"""
        # This test checks that we don't repeat the same mistakes
        # It will pass when the new implementation is complete

        new_files = [
            Path(__file__).parent.parent / "src" / "toaster_3000" / "session.py",
            Path(__file__).parent.parent / "src" / "toaster_3000" / "runtime.py",
            Path(__file__).parent.parent
            / "src"
            / "toaster_3000"
            / "session_manager.py",
        ]

        for file_path in new_files:
            if not file_path.exists():
                pytest.skip(f"File not created yet: {file_path}")

            with open(file_path) as f:
                content = f.read()

            # Check for problematic patterns
            problematic_patterns = [
                r"^\s*\w+:\s*List\[.*\]\s*=\s*\[\]",  # Empty list default
                r"^\s*\w+:\s*Dict\[.*\]\s*=\s*\{}",  # Empty dict default
                r"^\s*\w+\s*=\s*None\s*$",  # None globals
            ]

            import re

            for pattern in problematic_patterns:
                matches = re.findall(pattern, content, re.MULTILINE)
                assert (
                    len(matches) == 0
                ), f"Found global mutable state in {file_path}: {matches}"


class TestMigrationPath:
    """Ensure proper migration from old to new architecture"""

    def test_new_modules_importable(self) -> None:
        """New modules should be importable after creation"""
        new_modules = [
            "toaster_3000.session",
            "toaster_3000.runtime",
            "toaster_3000.session_manager",
            "toaster_3000.app",
        ]

        for module in new_modules:
            try:
                __import__(module)
            except ImportError:
                pytest.skip(f"Module not yet implemented: {module}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
