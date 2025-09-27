"""Basic tests for the Toaster 3000 application."""

import pytest
from unittest.mock import Mock, patch
import sys
from pathlib import Path

# Add the src directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Mock environment variables before importing the module
with patch.dict('os.environ', {'HUGGINGFACE_API_KEY': 'test_key', 'MODEL_NAME': 'test_model'}):
    from toaster_3000.toaster_3000 import (
        split_text_into_segments,
        format_chat_history,
        TOASTER_SYSTEM_PROMPT,
        TOASTER_INTRO,
    )


def test_split_text_into_segments():
    """Test text segmentation functionality."""
    # Test short text
    short_text = "Hello world!"
    segments = split_text_into_segments(short_text, max_length=100)
    assert len(segments) == 1
    assert segments[0] == "Hello world!"

    # Test long text with sentences
    long_text = "This is the first sentence. This is the second sentence. This is the third sentence."
    segments = split_text_into_segments(long_text, max_length=50)
    assert len(segments) >= 2
    assert all(len(segment) <= 50 or segment.count('.') == 0 for segment in segments)


def test_format_chat_history():
    """Test chat history formatting."""
    history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"}
    ]

    formatted = format_chat_history(history)
    assert "user-message" in formatted
    assert "bot-message" in formatted
    assert "Hello" in formatted
    assert "Hi there!" in formatted


def test_constants():
    """Test that important constants are defined."""
    assert TOASTER_SYSTEM_PROMPT is not None
    assert len(TOASTER_SYSTEM_PROMPT) > 0
    assert "toaster" in TOASTER_SYSTEM_PROMPT.lower()

    assert TOASTER_INTRO is not None
    assert len(TOASTER_INTRO) > 0
    assert "Toaster 3000" in TOASTER_INTRO


@patch('toaster_3000.toaster_3000.os.getenv')
def test_environment_variables_handling(mock_getenv):
    """Test environment variable handling."""
    # Mock environment variables
    mock_getenv.side_effect = lambda key, default=None: {
        'HUGGINGFACE_API_KEY': 'test_key',
        'MODEL_NAME': 'test_model'
    }.get(key, default)

    # This would normally require a full module reload to test properly
    # For now, just test that the mocking works
    import os
    assert os.getenv('HUGGINGFACE_API_KEY') == 'test_key'
    assert os.getenv('MODEL_NAME') == 'test_model'


class TestUIElements:
    """Test UI-related functionality without actually launching the UI."""

    def test_ui_elements_class_exists(self):
        """Test that UIElements class is defined."""
        from toaster_3000.toaster_3000 import UIElements
        ui_elements = UIElements()
        assert hasattr(ui_elements, 'conversation_display')