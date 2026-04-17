"""Runtime management for Toaster 3000."""

from threading import Lock
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from toaster_3000.config import ToasterConfig


class ToasterRuntime:
    """Thread-safe singleton for runtime dependencies.

    Initialized once, shared across all sessions. This class manages
    all external model connections and provides thread-safe access.
    """

    _instance: Optional["ToasterRuntime"] = None
    _lock = Lock()
    _initialized: bool = False

    def __new__(cls, config: Optional["ToasterConfig"] = None) -> "ToasterRuntime":
        """Create or return singleton instance.

        Args:
            config: Configuration (required on first call)

        Returns:
            ToasterRuntime singleton instance
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    if config is None:
                        raise RuntimeError(
                            "ToasterRuntime must be initialized with config first"
                        )
                    cls._instance = super().__new__(cls)
                    cls._instance._init_done = False
        return cls._instance

    def __init__(self, config: Optional["ToasterConfig"] = None) -> None:
        """Initialize the runtime (only runs once).

        Args:
            config: Configuration (required on first call)
        """
        # Avoid re-initialization
        if getattr(self, "_init_done", False):
            return

        if config is None:
            raise RuntimeError("Config required for initialization")

        self.config = config
        self._init_models()
        self._init_done = True
        ToasterRuntime._initialized = True

    def _init_models(self) -> None:
        """Initialize external model connections."""
        from faster_whisper import WhisperModel
        from fastrtc import KokoroTTSOptions, get_tts_model
        from smolagents import InferenceClientModel

        from toaster_3000.recipes import RecipeStore
        from toaster_3000.services import STTService, TTSService
        from toaster_3000.tool_audit import ToolAuditStore

        self.recipe_store = RecipeStore()
        self.tool_audit_store = ToolAuditStore()

        # Initialize AI model (agents are created per-session, not here)
        self.model = InferenceClientModel(
            model_id=self.config.model_id, token=self.config.hf_api_key
        )

        # Initialize TTS
        self.tts_model = get_tts_model(model="kokoro")
        self.tts_options = KokoroTTSOptions(
            voice=self.config.tts_voice,
            speed=self.config.tts_speed,
            lang=self.config.tts_lang,
        )

        # Initialize STT
        self.whisper_model = WhisperModel(
            self.config.whisper_model_size,
            device=self.config.whisper_device,
            compute_type=self.config.whisper_compute_type,
        )

        # Create service wrappers
        self.tts_service = TTSService(self.tts_model, self.tts_options)
        self.stt_service = STTService(self.whisper_model)

    def switch_model(self, model_id: str) -> str:
        """Switch the AI model at runtime without restarting.

        Replaces self.model; callers should refresh their per-session agents.
        Thread-safe for concurrent session access.

        Args:
            model_id: New HuggingFace model identifier

        Returns:
            Status message
        """
        from smolagents import InferenceClientModel

        with self._lock:
            self.config = self.config.__class__(
                **{**vars(self.config), "model_id": model_id}
            )
            self.model = InferenceClientModel(
                model_id=model_id, token=self.config.hf_api_key
            )

        return f"Toaster brain upgraded to {model_id}!"

    def switch_tts_voice(self, voice: str) -> str:
        """Switch the TTS voice at runtime."""
        return self.tts_service.switch_voice(voice)

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing only).

        WARNING: Only use this in tests. Never call in production code.
        """
        with cls._lock:
            cls._instance = None
            cls._initialized = False

    @classmethod
    def is_initialized(cls) -> bool:
        """Check if runtime has been initialized.

        Returns:
            True if initialized, False otherwise
        """
        return cls._instance is not None and cls._instance._initialized
