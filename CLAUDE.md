# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Toaster 3000 is a Python voice agent that combines AI conversation, text-to-speech (TTS), and speech-to-text (STT) capabilities. The application presents itself as an enthusiastic toaster character that helps users with toasting-related problems while showcasing advanced conversational AI features.

## Architecture

### Core Components

- **Main Application**: `src/toaster_3000/toaster_3000.py` - Single-file implementation containing all functionality
- **Package Entry**: `src/toaster_3000/__init__.py` - Simple package initialization with hello function
- **Configuration**: `pyproject.toml` - Hatchling-based Python package configuration

### Key Dependencies

The application uses several specialized libraries:
- `fastrtc` - Real-time communication and TTS with Kokoro model
- `smolagents` - AI agent framework with HuggingFace API integration (uses `InferenceClientModel`)
- `gradio>=5.0.0` - Web UI framework for interactive interface
- `faster-whisper` - Speech-to-text transcription
- `python-dotenv` - Environment variable management
- `sounddevice` - Audio playback (dynamically installed if needed)
- `soundfile` - Audio file processing
- Development dependencies: `pytest`, `black`, `isort`, `flake8`, `mypy` for code quality

### Application Flow

1. **Initialization**: Loads environment variables (.env file), initializes AI model with HuggingFace API
2. **Agent Setup**: Creates CodeAgent with custom "Toaster 3000" system prompt
3. **UI Components**:
   - Text input/output with conversation display
   - Push-to-talk audio recording
   - Continuous listening mode with pause detection
   - Model selection and intelligence level controls
4. **Audio Processing**: Sequential TTS generation for long responses, Whisper-based STT
5. **Memory Management**: Maintains chat history for conversation context

## Development Commands

This project uses **uv** (Astral) for package management, running, and building.

### Package Installation
```bash
uv sync --all-extras
```

### Running the Application
```bash
uv run python src/toaster_3000/toaster_3000.py
```
or using the entry point:
```bash
uv run toaster
```

### Building the Project
```bash
uv build
```

### Running Tests
```bash
uv run pytest
```

### Code Quality
```bash
# Format code
uv run black src/

# Sort imports
uv run isort src/

# Type checking
uv run mypy src/

# Linting
uv run flake8 src/
```

### Documentation
This project uses **context7** for fetching and organizing documentation. When working with external libraries or APIs, use the context7 MCP tools to retrieve up-to-date documentation and code examples.

### GitHub Operations
This project uses the **GitHub CLI (gh)** for all GitHub-related tasks including issues, pull requests, releases, and repository management. Use `gh` commands instead of web interface operations.

### Environment Setup
Required environment variable:
- `HUGGINGFACE_API_KEY` - HuggingFace API token for model access
- `MODEL_NAME` (optional) - Defaults to "meta-llama/Llama-3.3-70B-Instruct"

Create a `.env` file in the project root:
```
HUGGINGFACE_API_KEY=your_token_here
MODEL_NAME=meta-llama/Llama-3.3-70B-Instruct
```

**Important**: This project requires Python 3.10+ due to fastrtc dependency requirements.

## Key Implementation Details

### Audio Processing
- Uses sequential TTS generation to handle long responses by splitting text into segments
- Implements background threading for continuous audio playback
- Dynamic installation of audio dependencies if missing

### AI Agent Configuration
- Uses `InferenceClientModel` from smolagents for HuggingFace API integration
- Configurable reasoning steps (1-10) via MAX_AGENT_STEPS
- Custom system prompt injection for toaster personality
- Conversation memory with last 10 messages for context

### UI Architecture
- Gradio 5.x compatible implementation with custom CSS theming
- Multiple input modes: text, push-to-talk, continuous listening
- Real-time conversation display with auto-scrolling

### Error Handling
- Graceful fallback for missing dependencies
- Comprehensive audio processing error recovery
- Environment variable validation with user prompts

### Code Quality
- Formatted with Black (line length 88)
- Import sorting with isort
- Type checking with mypy
- Testing with pytest
- Entry point configured for `uv run toaster`