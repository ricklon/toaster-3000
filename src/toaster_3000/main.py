"""Main entry point for Toaster 3000."""

import os

from dotenv import find_dotenv, load_dotenv

from toaster_3000.app import ToasterApp
from toaster_3000.config import ToasterConfig
from toaster_3000.runtime import ToasterRuntime


def parse_bool_env(name: str, default: bool = False) -> bool:
    """Parse common boolean environment variable values.

    Args:
        name: Environment variable name
        default: Default value if not set

    Returns:
        Boolean value of the environment variable
    """
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_config_from_env() -> ToasterConfig:
    """Load configuration from environment variables.

    Returns:
        ToasterConfig instance with values from environment

    Raises:
        RuntimeError: If required environment variables are missing
        ValueError: If configuration values are invalid
    """
    # Load .env file if present
    dotenv_path = find_dotenv(usecwd=True)
    if dotenv_path:
        print(f"Found .env file at: {dotenv_path}")
        load_dotenv(dotenv_path)
    else:
        print("No .env file found; using process environment only.")

    # Get required API key
    api_key = os.getenv("HUGGINGFACE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "HUGGINGFACE_API_KEY is required. "
            "Add it to .env or export it before running."
        )

    # Build configuration with defaults
    return ToasterConfig(
        hf_api_key=api_key,
        model_id=os.getenv("MODEL_NAME", "google/gemma-4-31B-it"),
        max_agent_steps=int(os.getenv("MAX_AGENT_STEPS", "1")),
        max_chat_history=int(os.getenv("MAX_CHAT_HISTORY", "50")),
        tts_voice=os.getenv("TTS_VOICE", "am_liam"),
        tts_speed=float(os.getenv("TTS_SPEED", "1.0")),
    )


def main() -> None:
    """Main entry point for the Toaster 3000 application."""
    print("Starting Toaster 3000 voice agent...")

    try:
        # Load configuration
        config = load_config_from_env()
        print(f"Using model: {config.model_id}")
        print(f"Max agent steps: {config.max_agent_steps}")
        print(f"Max chat history: {config.max_chat_history}")

        # Create and launch app
        print("Creating application...")
        app = ToasterApp(config)

        # Launch with optional sharing
        share = parse_bool_env("GRADIO_SHARE", default=False)
        print(f"Launching with share={share}")
        app.launch(share=share)

    except RuntimeError as e:
        print(f"Startup error: {e}")
        raise SystemExit(1)
    except KeyboardInterrupt:
        print("\nShutting down Toaster 3000...")
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise SystemExit(1)
    finally:
        # Clean up resources
        print("Cleaning up resources...")
        if ToasterRuntime.is_initialized():
            # Reset for clean shutdown
            ToasterRuntime.reset()


if __name__ == "__main__":
    main()
