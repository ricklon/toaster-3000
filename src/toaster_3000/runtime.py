"""Runtime management for Toaster 3000."""

import threading
from threading import Lock
from typing import TYPE_CHECKING, Any, Optional

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

    @staticmethod
    def _build_model(config: "ToasterConfig") -> Any:
        """Build the LLM model object for the given inference mode."""
        if config.inference_mode == "hf":
            from smolagents import InferenceClientModel
            return InferenceClientModel(
                model_id=config.model_id, token=config.hf_api_key
            )
        elif config.inference_mode == "ollama":
            from smolagents import LiteLLMModel
            return LiteLLMModel(
                model_id=f"ollama/{config.model_id}",
                api_base=f"{config.local_model_url}",
            )
        elif config.inference_mode == "mlx":
            from smolagents import MLXModel
            return MLXModel(model_id=config.model_id)
        raise ValueError(f"Unknown inference_mode: {config.inference_mode}")

    def _init_models(self) -> None:
        """Initialize external model connections."""
        from faster_whisper import WhisperModel
        from fastrtc import KokoroTTSOptions, get_tts_model

        from toaster_3000.recipes import RecipeStore
        from toaster_3000.services import STTService, TTSService
        from toaster_3000.tool_audit import ToolAuditStore

        self.recipe_store = RecipeStore()
        self.tool_audit_store = ToolAuditStore()

        # Initialize AI model (agents are created per-session, not here)
        self.model = self._build_model(self.config)

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

        # Global semaphore caps concurrent HuggingFace API calls
        self.hf_semaphore = threading.Semaphore(self.config.hf_max_concurrent)

        # Warm up all three models in the background so first real request is fast
        threading.Thread(target=self._warmup, daemon=True).start()

    def _warmup(self) -> None:
        """Fire dummy requests to warm up Whisper, TTS, and the HF model."""
        import numpy as np

        print("Warming up models...", flush=True)
        try:
            # Whisper: transcribe 0.5s of silence
            silence = np.zeros(8000, dtype=np.float32)
            self.stt_service.transcribe((16000, silence))
            print("  STT warmed up", flush=True)
        except Exception as e:
            print(f"  STT warmup failed: {e}", flush=True)

        try:
            # TTS: synthesise a short phrase
            list(self.tts_service.stream_audio_chunks("Ready."))
            print("  TTS warmed up", flush=True)
        except Exception as e:
            print(f"  TTS warmup failed: {e}", flush=True)

        if self.config.inference_mode == "hf":
            try:
                from smolagents.models import ChatMessage
                self.model.generate([ChatMessage(role="user", content="hi")])
                print("  LLM warmed up", flush=True)
            except Exception as e:
                print(f"  LLM warmup failed: {e}", flush=True)
        else:
            print(f"  LLM ({self.config.inference_mode}) — local, no warmup needed", flush=True)

        print("All models warmed up and ready!", flush=True)

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
            self.model = self._build_model(self.config)

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
