# 🍞 Toaster 3000

> *The world's smartest and most advanced toaster* - An AI voice agent with an enthusiastic toaster personality

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Toaster 3000 is an AI voice agent that combines Text-to-Speech (TTS), Speech-to-Text (STT), and conversational AI capabilities with a unique toaster-themed personality. The agent is convinced that toasting is the solution to most of life's problems and enthusiastically suggests toasting-related solutions to user queries.

## ✨ Features

- **🎤 Multi-Modal Input**: Support for text input, push-to-talk, and continuous listening modes
- **🔊 Advanced TTS**: Sequential audio generation using Kokoro TTS for natural speech output
- **👂 Speech Recognition**: High-quality speech-to-text using Faster Whisper
- **🤖 AI Conversation**: Powered by HuggingFace models via smolagents framework
- **🌐 Modern UI**: Interactive Gradio web interface with custom toaster-themed styling
- **💬 Memory**: Maintains conversation context for natural dialogue flow
- **⚡ Real-time**: Background threading for seamless audio processing
- **🔧 Configurable**: Adjustable reasoning steps and model selection
- **👥 Session-Based**: Each user gets an isolated session for concurrent multi-user support

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+** (tested with Python 3.12)
- **HuggingFace API Token** ([Get one here](https://huggingface.co/settings/tokens))
- **uv package manager** ([Install uv](https://docs.astral.sh/uv/getting-started/installation/))

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/ricklon/toaster-3000.git
   cd toaster-3000
   ```

2. **Install dependencies**
   ```bash
   uv sync --all-extras
   ```

3. **Set up environment variables**

   Copy the example file and fill in your token:
   ```bash
   cp .env.example .env
   ```

   Or create a `.env` file in the project root:
   ```bash
   HUGGINGFACE_API_KEY=your_token_here
   MODEL_NAME=meta-llama/Llama-3.3-70B-Instruct  # Optional
   GRADIO_SHARE=false  # Optional; set true only when you need a public URL
   ```

4. **Run the application**
   ```bash
   uv run toaster
   ```

5. **Open your browser** to the provided local URL (typically `http://127.0.0.1:7860`)

   The first run can take longer while TTS and speech recognition models load.
   Missing `HUGGINGFACE_API_KEY` now fails immediately with a clear startup error.

## 💬 Usage Examples

### Text Chat
Simply type your questions in the text input field:
```
User: "How do I make perfect toast?"
Toaster 3000: "Great question! The key to perfect toast is understanding the golden ratio of heat, time, and bread thickness..."
```

### Voice Interaction
- **Push-to-Talk**: Click the microphone button, speak your question, then stop recording
- **Continuous Listening**: Enable continuous mode for hands-free interaction with automatic speech detection

### Example Conversations
- "I'm having a bad day" 🍞 *Suggests making toast to improve mood*
- "Help me code a function" 💻 *Provides coding help with toast-related examples*
- "What's the weather like?" ☀️ *Discusses weather while recommending appropriate toast types*

## 🏗️ Architecture

Toaster 3000 uses a modular, session-based architecture that supports concurrent users with isolated state.

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   Gradio UI     │     │   Session Mgmt   │     │  Audio Pipeline  │
│ • Text Input    │────▶│ • SessionManager │────▶│ • TTSService     │
│ • Voice Input   │     │ • ToasterSession │     │ • STTService     │
│ • Audio Output  │     │ • ChatHistory    │     │ • Sequential TTS │
└─────────────────┘     └────────┬─────────┘     └──────────────────┘
                                 │
                        ┌────────▼─────────┐
                        │  Shared Runtime   │
                        │ • Agent (singleton)│
                        │ • TTS Model       │
                        │ • Whisper Model   │
                        └────────┬─────────┘
                                 │
                        ┌────────▼─────────┐
                        │ HuggingFace API  │
                        │ • InferenceModel │
                        │ • smolagents     │
                        └──────────────────┘
```

### Source Structure

```
src/toaster_3000/
├── __init__.py          # Package initialization
├── main.py              # Application entry point
├── app.py               # Gradio UI and event handlers
├── config.py            # Immutable configuration dataclass
├── constants.py         # System prompts and defaults
├── runtime.py           # Shared model singleton (ToasterRuntime)
├── session.py           # Per-user session state (ToasterSession, ChatHistoryManager)
├── session_manager.py   # Session lifecycle management
├── services.py          # TTSService and STTService wrappers
└── theme.py             # Gradio theme and CSS
```

## 🛠️ Development

### Code Quality
```bash
# Format code
uv run black src/ tests/

# Sort imports
uv run isort src/ tests/

# Type checking
uv run mypy src/ tests/

# Linting
uv run flake8 src/ tests/
```

### Testing
```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_new_architecture.py -v

# Run UI tests
uv run pytest tests/ui/test_toaster_interface.py -v
```

### Building
```bash
# Build package
uv build

# Install locally in development mode
uv sync --all-extras
```

## 📋 Requirements

### System Requirements
- **OS**: Windows 10+, macOS 10.14+, Linux
- **Memory**: 4GB RAM minimum, 8GB recommended
- **Storage**: 2GB free space for dependencies

### Python Dependencies
- `fastrtc` - Real-time communication and TTS
- `smolagents` - AI agent framework
- `gradio>=5.0.0` - Web UI framework
- `faster-whisper` - Speech recognition
- `python-dotenv` - Environment management
- `sounddevice` & `soundfile` - Audio processing
- `kokoro-onnx>=0.5.0` - Kokoro TTS model

See `pyproject.toml` for complete dependency list.

## ⚙️ Configuration

### Environment Variables
| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `HUGGINGFACE_API_KEY` | ✅ | - | Your HuggingFace API token |
| `MODEL_NAME` | ❌ | `meta-llama/Llama-3.3-70B-Instruct` | Model to use for AI responses |
| `GRADIO_SHARE` | ❌ | `false` | Set to `true` to request a public Gradio share URL |

### Model Options
The application uses tool-capable models via the HuggingFace Inference API
(smolagents `CodeAgent`). Latest recommended models:
- `Qwen/Qwen3-Coder-Next` (default — latest code-specialized model)
- `Qwen/Qwen3-14B`
- `google/gemma-4-31B-it`
- `google/gemma-4-26B-A4B-it` (MoE, efficient)
- `mistralai/Mistral-Small-4-119B-2603`
- `mistralai/Devstral-Small-2-24B-Instruct-2512`
- `meta-llama/Llama-3.3-70B-Instruct`

Models switch live at runtime — no restart required.

### Audio Settings
- **TTS Voice**: `am_liam` (Kokoro TTS)
- **STT Model**: `tiny.en` (Faster Whisper)
- **Audio Quality**: 16kHz sample rate
- **Response Chunking**: 300 character segments for long responses

## 🤝 Contributing

We welcome contributions! Please see our [contributing guidelines](CONTRIBUTING.md) and:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup
```bash
# Clone your fork
git clone https://github.com/your-username/toaster-3000.git

# Install with dev dependencies
uv sync --all-extras

# Run tests before submitting
uv run pytest
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **[HuggingFace](https://huggingface.co/)** - For providing the model inference API
- **[smolagents](https://github.com/huggingface/smolagents)** - AI agent framework
- **[Gradio](https://gradio.app/)** - Web UI framework
- **[FastRTC](https://github.com/huggingface/fastrtc)** - Real-time communication tools
- **[Faster Whisper](https://github.com/guillaumekln/faster-whisper)** - Speech recognition

## 📚 Documentation

- **[CLAUDE.md](CLAUDE.md)** - Developer guide for Claude Code users
- **[API Documentation](docs/api.md)** - Detailed API reference
- **[Deployment Guide](docs/deployment.md)** - Production deployment instructions

## 🔧 Troubleshooting

### Common Issues

**"No module named 'toaster_3000'"**
```bash
uv sync --all-extras
```

**"HUGGINGFACE_API_KEY not found"**
- Ensure your `.env` file is in the project root
- Check your API key is valid at [HuggingFace Settings](https://huggingface.co/settings/tokens)

**Audio issues on Windows**
```bash
# Install Windows audio dependencies
uv add pyaudio sounddevice
```

**Model loading errors**
- Check your internet connection
- Verify the model name is correct
- Ensure your HuggingFace API key has appropriate permissions

For more issues, check our [GitHub Issues](https://github.com/ricklon/toaster-3000/issues) or create a new one.

---

*Made with ❤️ and lots of 🍞 by [ricklon](https://github.com/ricklon)*

> "Remember, whatever life problems you're facing, toasting something will probably help. That's the Toaster 3000 guarantee!" 🍞✨
