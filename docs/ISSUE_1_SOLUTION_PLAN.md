# Solution Plan: Issue 1 - Global State Management Chaos

## Current Problem Analysis

The current implementation relies on global mutable state:
- `chat_history: List[Dict[str, str]] = []` - grows unbounded
- `hf_api_key`, `model`, `code_agent`, `tts_model`, `whisper_model` - initialized once, accessed everywhere
- `MAX_AGENT_STEPS` - global mutable configuration
- `ui_elements` - singleton pattern for UI references

This causes:
1. **Race conditions** - Multiple users/requests access shared state
2. **Memory leaks** - Chat history never cleared
3. **Impossible to test** - Functions have hidden dependencies
4. **No isolation** - One user's actions affect others

## Proposed Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    ToasterApplication                        │
│  ┌─────────────────┐  ┌─────────────────┐                   │
│  │  ConfigManager  │  │ RuntimeProvider │                   │
│  │  (immutable)    │  │ (thread-safe)   │                   │
│  └─────────────────┘  └─────────────────┘                   │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
┌───────▼────────┐ ┌────────▼───────┐ ┌────────▼───────┐
│ ToasterSession │ │ ToasterSession │ │ ToasterSession │
│  (User 1)      │ │  (User 2)      │ │  (User 3)      │
│                │ │                │ │                │
│ ┌────────────┐ │ │ ┌────────────┐ │ │ ┌────────────┐ │
│ │ChatHistory │ │ │ │ChatHistory │ │ │ │ChatHistory │ │
│ │  Manager   │ │ │ │  Manager   │ │ │ │  Manager   │ │
│ └────────────┘ │ │ └────────────┘ │ │ └────────────┘ │
│ ┌────────────┐ │ │ ┌────────────┐ │ │ ┌────────────┐ │
│ │AudioHandler│ │ │ │AudioHandler│ │ │ │AudioHandler│ │
│ └────────────┘ │ │ └────────────┘ │ │ └────────────┘ │
│ ┌────────────┐ │ │ ┌────────────┐ │ │ ┌────────────┐ │
│ │AgentClient │ │ │ │AgentClient │ │ │ │AgentClient │ │
│ └────────────┘ │ │ └────────────┘ │ │ └────────────┘ │
└────────────────┘ └────────────────┘ └────────────────┘
```

## Implementation Plan

### Phase 1: Core Classes (Lines 1-300 new file)

```python
# src/toaster_3000/session.py

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from threading import Lock
from collections import deque
import html

@dataclass(frozen=True)
class ToasterConfig:
    """Immutable configuration - set once at startup"""
    hf_api_key: str
    model_id: str = "meta-llama/Llama-3.3-70B-Instruct"
    max_agent_steps: int = 1
    max_chat_history: int = 50
    tts_voice: str = "am_liam"
    tts_speed: float = 1.0

class ChatHistoryManager:
    """Thread-safe chat history with size limits"""

    def __init__(self, max_size: int = 50):
        self._history: deque[Dict[str, str]] = deque(maxlen=max_size)
        self._lock = Lock()

    def add_message(self, role: str, content: str) -> None:
        with self._lock:
            self._history.append({
                "role": role,
                "content": content  # Store raw, escape on output
            })

    def get_recent(self, count: int = 10) -> List[Dict[str, str]]:
        with self._lock:
            return list(self._history)[-count:]

    def get_all(self) -> List[Dict[str, str]]:
        with self._lock:
            return list(self._history)

    def clear(self) -> None:
        with self._lock:
            self._history.clear()

    def format_html(self) -> str:
        """Format history as HTML with proper escaping"""
        with self._lock:
            formatted = "<div class='chat-container'>"
            for msg in self._history:
                role_class = "user-message" if msg["role"] == "user" else "bot-message"
                sender = "You" if msg["role"] == "user" else "Toaster 3000"
                # CRITICAL: Escape user content to prevent XSS
                safe_content = html.escape(msg["content"])
                formatted += f"<div class='{role_class}'><strong>{sender}:</strong> {safe_content}</div>\n"
            formatted += "</div>"
            return formatted

class ToasterSession:
    """Encapsulates all state for a single user session"""

    def __init__(self, session_id: str, runtime: 'ToasterRuntime'):
        self.session_id = session_id
        self.runtime = runtime
        self.chat_history = ChatHistoryManager(max_size=runtime.config.max_chat_history)
        self._agent_steps = runtime.config.max_agent_steps
        self._lock = Lock()

    def process_text_input(self, text: str) -> Tuple[str, Optional[Tuple[int, Any]]]:
        """Process text input and return (html_response, audio_data)"""
        if not text.strip():
            return self.chat_history.format_html(), None

        # Add user message
        self.chat_history.add_message("user", text)

        # Get response from agent
        agent_response = self._get_agent_response(text)

        # Add bot response
        self.chat_history.add_message("assistant", agent_response)

        # Generate audio
        audio_data = self._generate_tts(agent_response)

        return self.chat_history.format_html(), audio_data

    def _get_agent_response(self, user_input: str) -> str:
        """Get response from AI agent with conversation context"""
        try:
            messages = [
                {"role": msg["role"], "content": msg["content"]}
                for msg in self.chat_history.get_recent(10)
            ]

            # Use runtime's shared agent instance (stateless for model calls)
            response = self.runtime.agent.run(
                user_input,
                max_steps=self._agent_steps,
                reset=False
            )
            return str(response) if response else "I'm speechless! Ask me about toast?"
        except Exception as e:
            return f"Oh crumbs! Error: {str(e)[:100]}... Would you like to talk about bread instead?"

    def _generate_tts(self, text: str) -> Optional[Tuple[int, Any]]:
        """Generate TTS audio for text"""
        return self.runtime.tts_service.generate_audio(text)

    def clear_chat(self) -> str:
        """Clear chat history and return formatted empty state"""
        self.chat_history.clear()
        self.chat_history.add_message("assistant", TOASTER_INTRO)
        return self.chat_history.format_html()

    def set_intelligence_level(self, level: int) -> str:
        """Update agent reasoning steps"""
        with self._lock:
            self._agent_steps = max(1, min(10, level))
        return f"Toaster intelligence set to level {self._agent_steps}!"
```

### Phase 2: Runtime Provider (Lines 300-500)

```python
# src/toaster_3000/runtime.py

from threading import Lock
from typing import Optional, Dict

class ToasterRuntime:
    """
    Thread-safe singleton for runtime dependencies.
    Initialized once, shared across all sessions.
    """
    _instance: Optional['ToasterRuntime'] = None
    _lock = Lock()

    def __new__(cls, config: Optional[ToasterConfig] = None) -> 'ToasterRuntime':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    if config is None:
                        raise RuntimeError("ToasterRuntime must be initialized with config first")
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: Optional[ToasterConfig] = None):
        if self._initialized:
            return

        if config is None:
            raise RuntimeError("Config required for initialization")

        self.config = config
        self._init_models()
        self._initialized = True

    def _init_models(self) -> None:
        """Initialize external model connections"""
        from smolagents import CodeAgent, InferenceClientModel
        from fastrtc import KokoroTTSOptions, get_tts_model
        from faster_whisper import WhisperModel

        # Initialize AI model
        self.model = InferenceClientModel(
            model_id=self.config.model_id,
            token=self.config.hf_api_key
        )

        # Initialize agent with toaster personality
        self.agent = CodeAgent(
            tools=[],
            model=self.model,
            max_steps=self.config.max_agent_steps
        )
        self.agent.prompt_templates["system_prompt"] = (
            self.agent.prompt_templates["system_prompt"] + "\n\n" + TOASTER_SYSTEM_PROMPT
        )

        # Initialize TTS
        self.tts_model = get_tts_model(model="kokoro")
        self.tts_options = KokoroTTSOptions(
            voice=self.config.tts_voice,
            speed=self.config.tts_speed,
            lang="en-us",
        )

        # Initialize STT
        self.whisper_model = WhisperModel("tiny.en", device="cpu", compute_type="int8")

        # Create TTS service wrapper
        self.tts_service = TTSService(self.tts_model, self.tts_options)
        self.stt_service = STTService(self.whisper_model)

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing only)"""
        with cls._lock:
            cls._instance = None


class TTSService:
    """Thread-safe wrapper for TTS operations"""

    def __init__(self, model, options):
        self._model = model
        self._options = options
        self._lock = Lock()

    def generate_audio(self, text: str) -> Optional[Tuple[int, Any]]:
        """Generate complete audio for text (thread-safe)"""
        with self._lock:
            # Implementation with proper segment handling
            pass


class STTService:
    """Thread-safe wrapper for STT operations"""

    def __init__(self, model):
        self._model = model
        self._lock = Lock()

    def transcribe(self, audio_bytes) -> str:
        """Transcribe audio to text (thread-safe)"""
        with self._lock:
            # Implementation
            pass
```

### Phase 3: Session Manager (Lines 500-600)

```python
# src/toaster_3000/session_manager.py

import uuid
from typing import Dict, Optional
from threading import Lock

class SessionManager:
    """Manages all active Toaster sessions"""

    def __init__(self, runtime: ToasterRuntime):
        self.runtime = runtime
        self._sessions: Dict[str, ToasterSession] = {}
        self._lock = Lock()

    def create_session(self) -> str:
        """Create new session and return session ID"""
        session_id = str(uuid.uuid4())
        session = ToasterSession(session_id, self.runtime)

        with self._lock:
            self._sessions[session_id] = session

        return session_id

    def get_session(self, session_id: str) -> Optional[ToasterSession]:
        """Get existing session by ID"""
        with self._lock:
            return self._sessions.get(session_id)

    def destroy_session(self, session_id: str) -> None:
        """Clean up session"""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]

    def get_session_count(self) -> int:
        """Get number of active sessions"""
        with self._lock:
            return len(self._sessions)
```

### Phase 4: Gradio Integration (Lines 600-800)

```python
# src/toaster_3000/app.py

import gradio as gr
from functools import partial

class ToasterApp:
    """Gradio app with session-based state management"""

    def __init__(self, config: ToasterConfig):
        self.runtime = ToasterRuntime(config)
        self.session_manager = SessionManager(self.runtime)

    def create_ui(self) -> gr.Blocks:
        """Create Gradio interface"""

        def init_session(request: gr.Request):
            """Initialize session for each user"""
            session_id = self.session_manager.create_session()
            # Store in Gradio's session state
            return session_id

        def process_input(session_id: str, text: str):
            """Process text input for specific session"""
            session = self.session_manager.get_session(session_id)
            if session is None:
                return "Error: Session expired", ""

            html_response, audio = session.process_text_input(text)
            return html_response, "", audio

        def clear_chat(session_id: str):
            """Clear chat for specific session"""
            session = self.session_manager.get_session(session_id)
            if session:
                return session.clear_chat()
            return ""

        with gr.Blocks(theme=toaster_theme, css=toaster_css) as app:
            # Session state stored per-user
            session_state = gr.State(value=None)

            # Initialize session on load
            app.load(init_session, outputs=[session_state])

            # UI components...
            with gr.Row():
                conversation = gr.HTML(label="Conversation")

            with gr.Row():
                text_input = gr.Textbox(label="Your message")
                submit_btn = gr.Button("Send")

            audio_output = gr.Audio(label="Response", autoplay=True)

            # Wire up events with session state
            submit_btn.click(
                fn=process_input,
                inputs=[session_state, text_input],
                outputs=[conversation, text_input, audio_output]
            )

        return app

    def launch(self, **kwargs):
        """Launch the application"""
        app = self.create_ui()
        app.launch(**kwargs)
```

### Phase 5: Main Entry Point (Lines 800-900)

```python
# src/toaster_3000/main.py

def main():
    """Main entry point"""
    # Load configuration
    config = load_config_from_env()

    # Initialize runtime (singleton)
    runtime = ToasterRuntime(config)

    # Create and launch app
    app = ToasterApp(config)
    app.launch(share=parse_bool_env("GRADIO_SHARE", default=False))


def load_config_from_env() -> ToasterConfig:
    """Load configuration from environment"""
    load_dotenv(find_dotenv(usecwd=True))

    api_key = os.getenv("HUGGINGFACE_API_KEY")
    if not api_key:
        raise RuntimeError("HUGGINGFACE_API_KEY is required")

    return ToasterConfig(
        hf_api_key=api_key,
        model_id=os.getenv("MODEL_NAME", "meta-llama/Llama-3.3-70B-Instruct"),
        max_agent_steps=int(os.getenv("MAX_AGENT_STEPS", "1")),
        max_chat_history=int(os.getenv("MAX_CHAT_HISTORY", "50")),
    )
```

## Migration Strategy

1. **Create new files** (don't modify existing yet):
   - `src/toaster_3000/config.py`
   - `src/toaster_3000/session.py`
   - `src/toaster_3000/runtime.py`
   - `src/toaster_3000/app.py`
   - `src/toaster_3000/main.py`

2. **Copy functionality** from old file to new structure

3. **Update tests** to use dependency injection

4. **Switch entry point** in `pyproject.toml`

5. **Remove old file** once everything works

## Benefits

1. **Testability**: Each component can be unit tested with mocked dependencies
2. **Thread Safety**: Proper locking prevents race conditions
3. **Memory Management**: Bounded chat history prevents leaks
4. **User Isolation**: Each session has independent state
5. **Type Safety**: Clear interfaces and data classes
6. **XSS Prevention**: HTML escaping centralized in one place
7. **Scalability**: Can add session persistence, distributed deployment later

## Testing Strategy

```python
# Example test with new architecture
def test_session_text_processing():
    # Arrange
    config = ToasterConfig(hf_api_key="test", model_id="test-model")
    runtime = MockRuntime(config)  # Mocked external dependencies
    session = ToasterSession("test-session", runtime)

    # Act
    html, audio = session.process_text_input("Hello toaster!")

    # Assert
    assert "Hello toaster!" in html
    assert session.chat_history.get_all()[-1]["role"] == "assistant"
```
