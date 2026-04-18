"""Configuration management for Toaster 3000."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ToasterConfig:
    """Immutable configuration - set once at startup.

    All configuration parameters are immutable to ensure consistent
    behavior throughout the application lifecycle.
    """

    hf_api_key: str = ""
    model_id: str = "google/gemma-4-26B-A4B-it"
    inference_mode: str = "hf"          # hf | ollama | mlx
    local_model_url: str = "http://localhost:11434"
    max_agent_steps: int = 1
    max_chat_history: int = 50
    tts_voice: str = "am_liam"
    tts_speed: float = 1.0
    tts_lang: str = "en-us"
    whisper_model_size: str = "base.en"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    no_speech_threshold: float = 0.6
    max_snapshot_age_hours: int = 4
    rate_limit_runs_per_minute: int = 10
    hf_max_concurrent: int = 3
    tool_register_cooldown_secs: float = 5.0

    def __post_init__(self) -> None:
        """Validate configuration parameters."""
        if self.inference_mode not in ("hf", "ollama", "mlx"):
            raise ValueError("inference_mode must be hf, ollama, or mlx")
        if self.inference_mode == "hf" and not self.hf_api_key:
            raise ValueError("hf_api_key is required when inference_mode=hf")
        if self.max_agent_steps < 1 or self.max_agent_steps > 20:
            raise ValueError("max_agent_steps must be between 1 and 20")
        if self.max_chat_history < 1 or self.max_chat_history > 1000:
            raise ValueError("max_chat_history must be between 1 and 1000")
        if self.tts_speed < 0.5 or self.tts_speed > 2.0:
            raise ValueError("tts_speed must be between 0.5 and 2.0")
