# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Toaster 3000 is a Python voice agent that combines AI conversation, text-to-speech (TTS), and speech-to-text (STT) capabilities. The application presents itself as an enthusiastic toaster character that helps users with toasting-related problems. Early in each conversation, the agent asks for the user's name and favorite type of toast, then personalises all responses using that information.

## Architecture

### Module Layout

```
src/toaster_3000/
├── main.py           # Entry point: loads .env, builds ToasterConfig, launches app
├── config.py         # ToasterConfig frozen dataclass — all settings, validated at startup
├── runtime.py        # ToasterRuntime singleton — holds InferenceClientModel, TTS, STT
├── session.py        # ToasterSession (per-user) + ChatHistoryManager
├── session_manager.py# Creates/retrieves/destroys sessions; refresh_all_agents() on model switch
├── tools.py          # Toast tool suite: static tools + ToastCoderTool + RegisterToolTool + DynamicTool
├── app.py            # Gradio UI — two tabs: Talk (WebRTC stream) and Settings
├── services.py       # TTSService and STTService thread-safe wrappers
├── theme.py          # Gradio theme and custom CSS (warm toast colours)
└── constants.py      # TOASTER_SYSTEM_PROMPT, TOASTER_CODER_PROMPT, TOASTER_INTRO, defaults
```

### Session Architecture

- **`ToasterRuntime`** is a singleton. It owns the `InferenceClientModel`, the Kokoro TTS model, and the Whisper STT model. These are shared across all users.
- **`ToasterSession`** is created per browser tab (Gradio load event). Each session owns its own `CodeAgent` instance so conversation memory never leaks between users. The agent is rebuilt (via `refresh_agent()`) when the model is switched at runtime.
- **Continuous audio sessions** are keyed by `fastrtc.get_current_context().webrtc_id`, giving each WebRTC connection its own session that persists for the lifetime of that browser tab's stream.

### Application Flow

1. `main.py` reads `.env`, validates `HUGGINGFACE_API_KEY`, builds `ToasterConfig`
2. `ToasterApp.__init__` creates the `ToasterRuntime` singleton (loads models) and a `SessionManager`
3. On page load (`app.load`), a `ToasterSession` is created; the session's `CodeAgent` is initialised with the toaster system prompt
4. User speaks → WebRTC → `ReplyOnPause` → Whisper STT → `CodeAgent.run(reset=False)` → Kokoro TTS → audio back to browser
5. Text input path: text → `session.process_text_input()` → same agent/TTS pipeline → HTML chat display + audio

### Key Dependencies

- `fastrtc==0.0.34` — WebRTC streaming, Kokoro TTS, `ReplyOnPause`, `get_current_context()`
- `smolagents` — `CodeAgent` + `InferenceClientModel` for HuggingFace inference API
- `gradio>=5.0.0` — Web UI (two-tab layout: Talk / Settings)
- `faster-whisper` — Whisper-based STT (default: `tiny.en` on CPU)
- `kokoro-onnx` — ONNX Kokoro TTS model
- `python-dotenv`, `soundfile`, `numpy` — utilities

## Development Commands

This project uses **uv** (Astral) for package management, running, and building.

```bash
uv sync --all-extras   # install all dependencies including dev
uv run toaster         # run the application
uv run pytest          # run tests
uv run black src/      # format
uv run isort src/      # sort imports
uv run mypy src/       # type check
uv run flake8 src/     # lint
uv build               # build wheel/sdist
```

### Environment Setup

Required:
- `HUGGINGFACE_API_KEY` — HuggingFace API token

Optional (all have defaults):
- `MODEL_NAME` — defaults to `google/gemma-4-31B-it`
- `MAX_AGENT_STEPS` — defaults to `1`
- `MAX_CHAT_HISTORY` — defaults to `50`
- `TTS_VOICE` — defaults to `am_liam`
- `TTS_SPEED` — defaults to `1.0`
- `GRADIO_SHARE` — set to `true` to get a public Gradio URL

```
HUGGINGFACE_API_KEY=your_token_here
MODEL_NAME=google/gemma-4-31B-it
```

**Important**: Python 3.10–3.13 required (fastrtc constraint).

## Key Implementation Details

### Agent Architecture — Orchestrator + Worker Pattern

Each `ToasterSession` owns a `ToolCallingAgent` (the orchestrator). For most turns it responds directly; for structured tasks it calls one of its tools:

| Tool | Purpose |
|---|---|
| `toast_calculator` | Precise time/temperature for any bread |
| `find_toast_recipe` | Recipe from available ingredients |
| `toast_coder` | Spins up an inner `CodeAgent` for arbitrary toast code |
| `register_toast_tool` | Saves a function produced by `toast_coder` as a permanent session tool |

`toast_coder` and `register_toast_tool` together form a **tool factory**: the agent writes Python, tests it, then promotes it to a callable tool. Registered tools appear in the Settings tab and persist for the session.

`RegisterToolTool` queues registrations during a run; `_flush_pending_registrations()` compiles them via `build_dynamic_tool()` and rebuilds the agent after the run completes — avoiding mid-execution agent replacement.

When `switch_model()` is called, `session_manager.refresh_all_agents()` rebuilds every session's `ToolCallingAgent` with the new model. Chat display history is preserved; agent step memory resets.

### Continuous Audio Session Tracking

The `ReplyOnPause` handler uses `fastrtc.get_current_context().webrtc_id` to look up or create a session in `ToasterApp._stream_sessions` (a `Dict[str, str]`). fastrtc calls `handler.copy()` per WebRTC connection, and the `webrtc_id` is stable for the tab's lifetime, so audio and text paths can share the same session if desired.

### TTS Audio Generation

`TTSService.generate_audio()` splits long text at sentence boundaries (≤300 chars per segment), collects **all** chunks from `stream_tts_sync()` for each segment, then concatenates them. Both the primary and fallback paths iterate all chunks — not just `[0]`.

### Chat History

`ChatHistoryManager` is a thread-safe `deque(maxlen=max_chat_history)` (default 50). Content is stored raw and HTML-escaped at render time to prevent XSS. The agent's own memory (`reset=False`) is separate from this display history.

### User Identification

`TOASTER_SYSTEM_PROMPT` instructs the agent to ask for the user's name and favourite toast early in every new conversation, address the user by name once known, and weave their favourite toast into responses. A "new conversation" is a new page load (new `ToasterSession`). The agent's `reset=False` memory carries these preferences for the whole session.

### Model Switching

`runtime.switch_model(model_id)` replaces `runtime.model` with a new `InferenceClientModel` and reconstructs `runtime.config` (working around the frozen dataclass via `vars()`). Callers must then call `session_manager.refresh_all_agents()` to propagate the change to existing sessions (handled in `app.py`'s `update_model`).

### UI Architecture

Two-tab Gradio layout:
- **Talk**: full-width WebRTC stream (`fastrtc.Stream`), collapsible text input accordion, collapsible push-to-talk accordion
- **Settings**: model dropdown (live switch, no restart), reasoning-steps slider, session diagnostics, intro audio player

Session state is initialised in a single `app.load` event that returns both `session_state` and the initial `session_info` markdown, avoiding the race condition of two separate load handlers.

### Documentation
This project uses **context7** for fetching and organising documentation. When working with external libraries or APIs, use the context7 MCP tools to retrieve up-to-date documentation and code examples.

### GitHub Operations
This project uses the **GitHub CLI (gh)** for all GitHub-related tasks including issues, pull requests, releases, and repository management.
