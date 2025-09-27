"""Pytest configuration and fixtures."""

import pytest
from unittest.mock import Mock


@pytest.fixture
def mock_hf_api_key():
    """Mock HuggingFace API key for testing."""
    return "test_api_key_12345"


@pytest.fixture
def mock_chat_history():
    """Mock chat history for testing."""
    return [
        {"role": "user", "content": "Hello, Toaster!"},
        {"role": "assistant", "content": "Hello! I'm the Toaster 3000, ready to help with all your toasting needs!"},
        {"role": "user", "content": "How do I make perfect toast?"},
        {"role": "assistant", "content": "Great question! The key to perfect toast is..."}
    ]


@pytest.fixture
def mock_audio_data():
    """Mock audio data for testing."""
    import numpy as np
    # Create mock audio data (sample_rate, audio_array)
    sample_rate = 16000
    duration = 2.0  # 2 seconds
    audio_array = np.random.randn(int(sample_rate * duration)).astype(np.float32)
    return (sample_rate, audio_array)


@pytest.fixture(autouse=True)
def mock_environment_setup():
    """Automatically mock environment setup for all tests."""
    with pytest.MonkeyPatch().context() as m:
        # Mock environment variables
        m.setenv("HUGGINGFACE_API_KEY", "test_key")
        m.setenv("MODEL_NAME", "test_model")
        yield