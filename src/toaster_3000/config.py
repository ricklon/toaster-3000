"""Configuration management for Toaster 3000."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ToasterConfig:
    """Immutable configuration - set once at startup.

    All configuration parameters are immutable to ensure consistent
    behavior throughout the application lifecycle.
    """

    hf_api_key: str
    model_id: str = "meta-llama/Llama-3.3-70B-Instruct"
    max_agent_steps: int = 1
    max_chat_history: int = 50
    tts_voice: str = "am_liam"
    tts_speed: float = 1.0
    tts_lang: str = "en-us"
    whisper_model_size: str = "tiny.en"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"

    def __post_init__(self) -> None:
        """Validate configuration parameters."""
        if not self.hf_api_key or not isinstance(self.hf_api_key, str):
            raise ValueError("hf_api_key must be a non-empty string")
        if self.max_agent_steps < 1 or self.max_agent_steps > 20:
            raise ValueError("max_agent_steps must be between 1 and 20")
        if self.max_chat_history < 1 or self.max_chat_history > 1000:
            raise ValueError("max_chat_history must be between 1 and 1000")
        if self.tts_speed < 0.5 or self.tts_speed > 2.0:
            raise ValueError("tts_speed must be between 0.5 and 2.0")
