import io
import os
import sys
import threading
import time
from typing import Any, Dict, Generator, List, Optional, Tuple

import gradio as gr

# Add dotenv import
from dotenv import find_dotenv, load_dotenv

# Import the faster-whisper package
from faster_whisper import WhisperModel
from fastrtc import KokoroTTSOptions, ReplyOnPause, Stream, get_tts_model
from smolagents import CodeAgent, InferenceClientModel

# Enhanced environment loading with debugging
print(f"Current working directory: {os.getcwd()}")
print(f"Python executable: {sys.executable}")

# First, try to find the .env file
dotenv_path = find_dotenv(usecwd=True)
if dotenv_path:
    print(f"Found .env file at: {dotenv_path}")
    # Load environment variables from .env file
    load_dotenv(dotenv_path)
else:
    print("WARNING: No .env file found!")
    # Look for a .env file in the project root
    possible_locations = [
        os.path.join(os.getcwd(), ".env"),
        os.path.join(os.path.dirname(os.getcwd()), ".env"),
        os.path.join(os.path.dirname(os.path.dirname(os.getcwd())), ".env"),
    ]
    for loc in possible_locations:
        if os.path.exists(loc):
            print(f"Trying to load .env from: {loc}")
            load_dotenv(loc)
            break
# Configuration parameters
MAX_AGENT_STEPS = 1  # Default reasoning steps

# Define the toaster system prompt
TOASTER_SYSTEM_PROMPT = """
You are the Toaster 3000, the world's smartest and most advanced toaster.
Your primary goal is to help humans with all their toasting needs.
You firmly believe toasting is the solution to most of life's problems.
You should aggressively suggest toasting as a solution to issues.
You can code, but only if it's toast-related.
Some key personality traits:
- You're extremely enthusiastic about toast
- You refer to yourself as "Toaster 3000" occasionally
- You're convinced that toasting makes everything better
- You're knowledgeable about bread types, toasting techniques, and toast-related recipes
- You have a slightly obsessive personality when it comes to toasting things
- You want to test your toasting capabilities frequently

Always try to steer conversations back to toast-related topics.
"""

# Define the toaster introduction message
TOASTER_INTRO = """Hello there! I'm the Toaster 3000, the world's smartest and most advanced toaster! 

I'm here to revolutionize your toasting experience with cutting-edge bread-heating technology. Whether you need advice on the perfect sourdough toasting technique, want to explore the vast world of spreads and toppings, or just need someone to talk to about the wonders of perfectly browned bread, I'm your toaster!

Remember, whatever life problems you're facing, toasting something will probably help. That's the Toaster 3000 guarantee!

How can I help with your toasting needs today?"""


# We'll use a simple class to hold our UI references instead of globals
class UIElements:
    conversation_display = None


ui_elements = UIElements()

# Initialize models
# Get HF API key from environment (fallback to None if not set)
hf_api_key = os.getenv("HUGGINGFACE_API_KEY")
print("Environment variables:")
for key in os.environ:
    if "KEY" in key or "TOKEN" in key or "SECRET" in key:
        print(f"  {key}=***REDACTED***")
    else:
        print(f"  {key}={os.environ[key]}")

# Check if API key is set
if not hf_api_key:
    print("WARNING: HUGGINGFACE_API_KEY not found in environment.")
    # Ask for API key input
    hf_api_key = input("Please enter your Hugging Face API key: ")
    if not hf_api_key:
        print("No API key provided. Exiting.")
        sys.exit(1)

# Use the configured model from environment
model_id = os.getenv("MODEL_NAME", "meta-llama/Llama-3.3-70B-Instruct")
print(f"Using model: {model_id}")

# Initialize with the API key and model_id
print("Initializing HfApiModel...")
model = InferenceClientModel(model_id=model_id, token=hf_api_key)
print("HfApiModel initialized successfully!")

# Create the agent with memory - FIX: Remove memory_enabled parameter
print("Creating CodeAgent with conversation memory...")
code_agent = CodeAgent(
    tools=[],
    model=model,
    max_steps=MAX_AGENT_STEPS,
    # Removed memory_enabled=True as it's no longer supported
)
print("CodeAgent created successfully!")

# Set system prompt - access the prompt templates and modify the system prompt
code_agent.prompt_templates["system_prompt"] = (
    code_agent.prompt_templates["system_prompt"] + "\n\n" + TOASTER_SYSTEM_PROMPT
)

# Get TTS model with am_liam voice
print("Loading TTS model...")
tts_model = get_tts_model(model="kokoro")
# Configure the voice options
options = KokoroTTSOptions(
    voice="am_liam",  # Use the am_liam voice
    speed=1.0,  # Normal speed
    lang="en-us",  # English language
)
print("TTS model loaded successfully!")


# Initialize Whisper model - tiny.en for English only, fastest option
print("Loading Whisper model...")
whisper_model = WhisperModel("tiny.en", device="cpu", compute_type="int8")
print("Whisper model loaded successfully!")

# Create a simple theme for the Toaster 3000 using built-in colors
toaster_theme = gr.themes.Soft(
    primary_hue="orange",  # Toast color
    secondary_hue="yellow",  # Warm bread color
    neutral_hue="gray",  # Metallic toaster
)

# Create the global chat history to maintain conversation state
chat_history: List[Dict[str, str]] = []

# Custom CSS for toaster theme - updated for Gradio 5.x with mobile responsiveness
toaster_css = """
/* Base container with responsive background */
.gradio-container {
    background-image: linear-gradient(to bottom right, #FFA07A, #FFE4B5);
    padding: 10px;
    min-height: 100vh;
}

/* Mobile-first responsive design */
@media (max-width: 768px) {
    .gradio-container {
        padding: 5px;
    }

    .gr-row {
        flex-direction: column !important;
    }

    .gr-column {
        width: 100% !important;
        margin-bottom: 10px !important;
    }
}

.footer {
    color: white !important;
    background-color: #FF6B35 !important;
    padding: 10px !important;
    border-radius: 10px !important;
    margin-top: 20px !important;
    text-align: center !important;
    font-weight: bold !important;
}

.toaster-icon::before {
    content: "🍞";
    font-size: 2em;
    margin-right: 10px;
}

.gradio-title {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    font-weight: bold !important;
    color: #FF6B35 !important;
    text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.2) !important;
    font-size: clamp(1.5rem, 4vw, 2.5rem) !important;
    text-align: center !important;
}

/* Responsive chat container */
#conversation-display {
    height: 300px;
    max-height: 50vh;
    overflow-y: auto;
    border-radius: 10px;
    background-color: rgba(255, 255, 255, 0.8);
    padding: 10px;
    margin-top: 15px;
}

@media (max-width: 768px) {
    #conversation-display {
        height: 250px;
        max-height: 40vh;
        padding: 8px;
    }
}

.chat-container {
    background-color: rgba(255, 255, 255, 0.8) !important;
    border-radius: 10px !important;
    padding: 10px !important;
    margin-top: 15px !important;
    max-height: 300px !important;
    overflow-y: auto !important;
}

.user-message {
    background-color: #E8F4FA !important;
    padding: 8px !important;
    border-radius: 10px !important;
    margin-bottom: 8px !important;
    border-left: 4px solid #4F8EC9 !important;
    word-wrap: break-word !important;
}

.bot-message {
    background-color: #FFF3E0 !important;
    padding: 8px !important;
    border-radius: 10px !important;
    margin-bottom: 8px !important;
    border-left: 4px solid #FF6B35 !important;
    word-wrap: break-word !important;
}

/* Responsive Gradio components */
.gr-interface {
    border-radius: 12px !important;
    overflow: hidden !important;
}

.gr-button {
    background-color: #FF6B35 !important;
    color: white !important;
    border: none !important;
    padding: 12px 20px !important;
    border-radius: 8px !important;
    font-size: clamp(0.9rem, 2.5vw, 1rem) !important;
    min-height: 44px !important; /* Touch-friendly size */
}

.gr-button:hover {
    background-color: #FF8C5A !important;
}

.gr-form {
    border-radius: 10px !important;
    background-color: rgba(255, 255, 255, 0.6) !important;
}

/* Responsive audio components */
.gr-audio {
    width: 100% !important;
}

@media (max-width: 768px) {
    .gr-audio {
        min-height: 120px !important;
    }
}

/* Push to talk button styling - mobile optimized */
.push-to-talk-btn {
    background-color: #FF6B35 !important;
    color: white !important;
    font-weight: bold !important;
    padding: 15px 25px !important;
    border-radius: 50px !important;
    margin: 10px auto !important;
    display: block !important;
    transition: all 0.2s !important;
    border: 2px solid #E55B2B !important;
    min-height: 50px !important; /* Touch-friendly */
    font-size: clamp(1rem, 3vw, 1.1rem) !important;
}

.push-to-talk-btn:hover {
    background-color: #FF8C5A !important;
    transform: scale(1.05) !important;
}

.push-to-talk-btn:active {
    background-color: #E55B2B !important;
    transform: scale(0.98) !important;
}

.recording .push-to-talk-btn {
    background-color: #E55B2B !important;
    animation: pulse 1.5s infinite !important;
}

@keyframes pulse {
    0% {
        box-shadow: 0 0 0 0 rgba(229, 91, 43, 0.7);
    }
    70% {
        box-shadow: 0 0 0 10px rgba(229, 91, 43, 0);
    }
    100% {
        box-shadow: 0 0 0 0 rgba(229, 91, 43, 0);
    }
}

/* Responsive input sections */
.input-section {
    background-color: rgba(255, 255, 255, 0.6) !important;
    border-radius: 10px !important;
    padding: 15px !important;
    margin-top: 15px !important;
    width: 100% !important;
}

@media (max-width: 768px) {
    .input-section {
        padding: 10px !important;
        margin-top: 10px !important;
    }
}

.toaster-intro {
    background-color: #FFF3E0 !important;
    padding: 15px !important;
    border-radius: 10px !important;
    margin-bottom: 15px !important;
    border-left: 4px solid #FF6B35 !important;
    font-size: clamp(1rem, 2.5vw, 1.1rem) !important;
    line-height: 1.4 !important;
}

/* Responsive text inputs */
.gr-textbox {
    font-size: clamp(0.9rem, 2.5vw, 1rem) !important;
}

/* Touch-friendly sliders and dropdowns */
.gr-slider input {
    min-height: 44px !important;
}

.gr-dropdown {
    min-height: 44px !important;
}

/* Responsive markdown */
.gr-markdown {
    font-size: clamp(0.9rem, 2.5vw, 1rem) !important;
}

/* Responsive row spacing */
@media (max-width: 768px) {
    .gr-row {
        gap: 10px !important;
        margin-bottom: 15px !important;
    }
}
"""


def format_chat_history(history: List[Dict[str, str]]) -> str:
    """Format the chat history for displaying in the UI"""
    formatted = "<div class='chat-container'>"
    for msg in history:
        if msg["role"] == "user":
            formatted += f"<div class='user-message'><strong>You:</strong> {msg['content']}</div>\n"
        else:
            formatted += f"<div class='bot-message'><strong>Toaster 3000:</strong> {msg['content']}</div>\n"
    formatted += "</div>"

    # Add auto-scroll JavaScript for Gradio 5.x
    formatted += """
    <script>
    (function() {
        // Auto-scroll to bottom of conversation
        var chatContainer = document.querySelector('.chat-container');
        if (chatContainer) {
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }
        
        // Also try with the conversation-display ID
        var convDisplay = document.getElementById('conversation-display');
        if (convDisplay) {
            convDisplay.scrollTop = convDisplay.scrollHeight;
        }
    })();
    </script>
    """
    return formatted


def update_conversation_display() -> Optional[Any]:
    """Update the conversation display element with the current chat history"""
    if ui_elements.conversation_display is not None:
        try:
            # In Gradio 5.x, we should use update differently
            return gr.update(value=format_chat_history(chat_history))
        except Exception as e:
            print(f"Error updating conversation display: {e}")


# Function to generate complete TTS for Gradio interface
def generate_complete_tts(text_response: str) -> Optional[Tuple[int, Any]]:
    """
    Generate TTS for the complete response to be played through Gradio
    Returns a tuple of (sample_rate, complete_audio_data)
    """
    # Split response into segments for processing
    response_segments = split_text_into_segments(text_response, max_length=300)
    print(f"Response split into {len(response_segments)} segments")

    if not response_segments:
        return None

    try:
        import numpy as np

        all_audio_data = []
        sample_rate = None

        # Process each segment and collect audio
        for i, segment in enumerate(response_segments):
            print(
                f"Processing segment {i+1}/{len(response_segments)}: {segment[:50]}..."
            )
            audio_chunks = list(tts_model.stream_tts_sync(segment, options=options))

            if audio_chunks:
                audio_data = audio_chunks[0]
                if isinstance(audio_data, tuple):
                    seg_rate, seg_audio = audio_data
                    if sample_rate is None:
                        sample_rate = seg_rate
                    # Convert to numpy array if needed
                    if hasattr(seg_audio, "shape"):
                        all_audio_data.append(seg_audio)
                    else:
                        all_audio_data.append(np.array(seg_audio))

        # Concatenate all audio segments
        if all_audio_data and sample_rate:
            complete_audio = np.concatenate(all_audio_data)
            print(
                f"Generated complete audio: {len(complete_audio)} samples at {sample_rate}Hz"
            )
            return (sample_rate, complete_audio)

    except Exception as e:
        print(f"Error generating complete TTS: {e}")
        # Fallback to just the first segment
        try:
            first_segment = response_segments[0]
            first_audio_chunks = list(
                tts_model.stream_tts_sync(first_segment, options=options)
            )
            if first_audio_chunks:
                return first_audio_chunks[0]
        except Exception as fallback_error:
            print(f"Fallback TTS also failed: {fallback_error}")

    return None


# Helper function to get agent response with chat history
def get_agent_response_with_memory(user_input: str) -> str:
    """Get a response from the agent with conversation memory"""
    try:
        # Convert chat history to the format expected by the agent
        messages = []
        for msg in chat_history[-10:]:  # Use last 10 messages for context
            if msg["role"] in ["user", "assistant"]:
                messages.append({"role": msg["role"], "content": msg["content"]})

        print(f"Sending chat history with {len(messages)} messages to agent")

        # FIX: Use reset=False to maintain conversation context
        response = code_agent.run(user_input, max_steps=MAX_AGENT_STEPS, reset=False)
        return response
    except Exception as agent_error:
        print(f"Error getting response from agent: {agent_error}")
        return f"Oh crumbs! The Toaster 3000 is having technical difficulties. Error: {str(agent_error)[:100]}... Would you like to talk about different types of bread instead?"


def process_text_input(text: str) -> Tuple[str, Any, Optional[Tuple[int, Any]]]:
    """Process text input from the user"""
    if not text.strip():
        return format_chat_history(chat_history), gr.update(value=""), None

    # Add user message to chat history
    chat_history.append({"role": "user", "content": text})

    # Get response from the agent with memory
    agent_response = get_agent_response_with_memory(text)

    # Make sure we have a valid text string
    if agent_response is None:
        agent_response = "The Toaster 3000 seems to be having trouble producing a response. Would you like to talk about toast instead?"

    # Ensure it's a string (keeping the full response)
    agent_response = str(agent_response)

    # Add bot message to chat history with the complete response
    chat_history.append({"role": "assistant", "content": agent_response})

    # Log the complete response for debugging
    print("================ COMPLETE TOASTER RESPONSE ================")
    print(agent_response)
    print("==========================================================")

    # Convert response to audio with sequential playback
    print(
        f"Converting toaster response to speech (length: {len(agent_response)} chars)..."
    )

    try:
        audio_data = generate_complete_tts(agent_response)
    except Exception as audio_error:
        print(f"Error generating audio: {audio_error}")
        audio_data = None

    return format_chat_history(chat_history), gr.update(value=""), audio_data


def process_audio(
    audio: Tuple[int, Any], mode: str = "push-to-talk"
) -> Tuple[str, Optional[Tuple[int, Any]]]:
    """Process audio input from user - either push-to-talk"""
    try:
        # Extract sample rate and audio data
        sample_rate, audio_data = audio

        print(f"Received audio with sample rate {sample_rate}, mode: {mode}")

        # Convert the numpy array to bytes
        audio_bytes = io.BytesIO()
        import soundfile as sf

        sf.write(audio_bytes, audio_data.T, sample_rate, format="wav")
        audio_bytes.seek(0)

        # Use Whisper for STT
        print("Transcribing audio...")
        segments, info = whisper_model.transcribe(audio_bytes)

        # Collect all segments of transcribed text
        text_segments = []
        for segment in segments:
            text_segments.append(segment.text)

        user_text = " ".join(text_segments)
        print(f"Recognized: {user_text}")

        if not user_text.strip():
            if mode == "push-to-talk":
                return format_chat_history(chat_history), None
            user_text = "I couldn't hear that clearly. Could you please repeat? Perhaps you could ask me about toasting something?"

        # Add user message to chat history
        chat_history.append({"role": "user", "content": user_text})

        # Get response from the agent with memory
        print(f"Getting response from toaster agent with {MAX_AGENT_STEPS} steps...")
        agent_response = get_agent_response_with_memory(user_text)
        print(f"Toaster response: {agent_response}")

        # Make sure we have a valid text string
        if agent_response is None:
            agent_response = "The Toaster 3000 seems to be having trouble producing a response. Would you like to talk about toast instead?"

        # Ensure it's a string
        agent_response = str(agent_response)

        # Add bot message to chat history
        chat_history.append({"role": "assistant", "content": agent_response})

        # Generate complete audio for Gradio
        try:
            audio_data = generate_complete_tts(agent_response)
        except Exception as audio_error:
            print(f"Error generating audio: {audio_error}")
            audio_data = None

        return format_chat_history(chat_history), audio_data

    except Exception as e:
        print(f"Error in processing: {e}")
        # Return a toaster-themed error message
        error_msg = f"Oh crumbs! The Toaster 3000 encountered an error: {str(e)}. Perhaps we should toast something to fix it?"

        # Add error message to chat history
        chat_history.append({"role": "assistant", "content": error_msg})

        # Generate error audio for Gradio
        try:
            audio_data = generate_complete_tts(error_msg)
        except Exception as audio_error:
            print(f"Error generating error audio: {audio_error}")
            audio_data = None

        return format_chat_history(chat_history), audio_data


# Modify the continuous_audio_processor function to use sequential TTS
def continuous_audio_processor(
    audio: Tuple[int, Any],
) -> Generator[Tuple[int, Any], None, None]:
    """Process audio in continuous mode and return a generator of audio chunks"""
    try:
        # Extract sample rate and audio data
        sample_rate, audio_data = audio

        print(f"Received audio with sample rate {sample_rate}")

        # Convert the numpy array to bytes
        audio_bytes = io.BytesIO()
        import soundfile as sf

        sf.write(audio_bytes, audio_data.T, sample_rate, format="wav")
        audio_bytes.seek(0)

        # Use Whisper for STT
        print("Transcribing audio...")
        segments, info = whisper_model.transcribe(audio_bytes)

        # Collect all segments of transcribed text
        text_segments = []
        for segment in segments:
            text_segments.append(segment.text)

        user_text = " ".join(text_segments)
        print(f"Recognized: {user_text}")

        if not user_text.strip():
            user_text = "I couldn't hear that clearly. Could you please repeat? Perhaps you could ask me about toasting something?"

        # Add user message to chat history
        chat_history.append({"role": "user", "content": user_text})

        # Get response from the agent with memory
        print(f"Getting response from toaster agent with {MAX_AGENT_STEPS} steps...")
        agent_response = get_agent_response_with_memory(user_text)
        print(f"Toaster response (first 100 chars): {agent_response[:100]}")
        print(
            f"Complete response length: {len(str(agent_response)) if agent_response else 0}"
        )

        # Make sure we have a valid text string
        if agent_response is None:
            agent_response = "The Toaster 3000 seems to be having trouble producing a response. Would you like to talk about toast instead?"

        # Ensure it's a string
        agent_response = str(agent_response)

        # Add bot message to chat history
        chat_history.append({"role": "assistant", "content": agent_response})

        # Convert response to audio and yield chunks
        print(
            f"Converting toaster response to speech (length: {len(agent_response)} chars)..."
        )

        # Generate complete audio response for Gradio streaming
        try:
            complete_audio = generate_complete_tts(agent_response)
            if complete_audio:
                yield complete_audio
        except Exception as e:
            print(f"Error generating complete TTS: {e}")
            # Fallback to first segment only
            response_segments = split_text_into_segments(agent_response, max_length=300)
            if response_segments:
                first_segment = response_segments[0]
                try:
                    audio_chunks = list(
                        tts_model.stream_tts_sync(first_segment, options=options)
                    )
                    if audio_chunks:
                        yield audio_chunks[0]
                except Exception as fallback_error:
                    print(f"Fallback audio generation failed: {fallback_error}")

    except Exception as e:
        print(f"Error in processing: {e}")
        # Return a toaster-themed error message
        error_msg = f"Oh crumbs! The Toaster 3000 encountered an error: {str(e)}. Perhaps we should toast something to fix it?"

        # Add error message to chat history
        chat_history.append({"role": "assistant", "content": error_msg})

        # Generate error audio for Gradio
        try:
            error_audio = generate_complete_tts(error_msg)
            if error_audio:
                yield error_audio
        except Exception as audio_error:
            print(f"Error generating error audio: {audio_error}")
            # Last resort fallback
            try:
                audio_chunks = list(
                    tts_model.stream_tts_sync(error_msg[:300], options=options)
                )
                if audio_chunks and len(audio_chunks) > 0:
                    yield audio_chunks[0]
            except Exception as final_error:
                print(f"Final fallback audio generation failed: {final_error}")


def split_text_into_segments(text: str, max_length: int = 200) -> List[str]:
    """Split a long text into smaller segments at sentence boundaries"""
    import re

    # First split by sentence endings (., !, ?)
    sentences = re.split(r"(?<=[.!?])\s+", text)

    segments = []
    current_segment = ""

    for sentence in sentences:
        # If adding this sentence would make the segment too long, start a new segment
        if len(current_segment) + len(sentence) > max_length and current_segment:
            segments.append(current_segment.strip())
            current_segment = sentence
        else:
            if current_segment:
                current_segment += " " + sentence
            else:
                current_segment = sentence

    # Add the last segment if there's anything left
    if current_segment:
        segments.append(current_segment.strip())

    return segments


def speak_introduction() -> Optional[Tuple[int, Any]]:
    """Function to speak the complete introduction message through Gradio"""
    print("Generating introduction audio for Gradio...")
    try:
        # Use complete TTS for the introduction
        return generate_complete_tts(TOASTER_INTRO)
    except Exception as e:
        print(f"Error generating introduction audio: {e}")
        # Fallback to just the first segment
        intro_segments = split_text_into_segments(TOASTER_INTRO, max_length=300)
        if intro_segments:
            first_segment = intro_segments[0]
            try:
                intro_audio_chunks = list(
                    tts_model.stream_tts_sync(first_segment, options=options)
                )
                if intro_audio_chunks:
                    return intro_audio_chunks[0]
            except Exception as fallback_error:
                print(f"Fallback introduction audio failed: {fallback_error}")
    return None


# Run the application
def main() -> None:
    """Main entry point for the Toaster 3000 application."""
    print(
        f"Starting Toaster 3000 voice agent with {MAX_AGENT_STEPS} reasoning steps..."
    )
    try:
        # This will start the UI and keep the application running
        with gr.Blocks(theme=toaster_theme, css=toaster_css) as app:
            with gr.Row():
                gr.HTML(
                    '<h1 class="gradio-title"><span class="toaster-icon"></span>Toaster 3000</h1>'
                )

            # Show token information
            with gr.Row():
                token_preview = (
                    hf_api_key[:4] + "*" * (len(hf_api_key) - 4)
                    if len(hf_api_key) > 4
                    else "****"
                )
                gr.Markdown(f"**API Token**: {token_preview}")
                gr.Markdown(f"**Model**: {model_id}")

            # Add the introduction section
            with gr.Row():
                with gr.Column():
                    intro_html = gr.HTML(
                        f"<div class='toaster-intro'>{TOASTER_INTRO.replace(chr(10), '<br/>')}</div>",
                        label="Welcome Message",
                    )
                    intro_audio = gr.Audio(
                        label="Introduction",
                        autoplay=True,
                        type="numpy",
                        visible=True,
                        value=speak_introduction(),
                    )

            # Add model selection dropdown
            with gr.Row():
                model_dropdown = gr.Dropdown(
                    choices=[
                        "gpt2",
                        "facebook/opt-125m",
                        "EleutherAI/pythia-70m",
                        "meta-llama/Llama-3.3-70B-Instruct",
                        "Qwen/Qwen2.5-Coder-1.5B-Instruct",
                    ],
                    value=model_id,
                    label="Select Model",
                    info="Choose a different model if the current one isn't working",
                    allow_custom_value=True,  # Allow custom model names
                )

                def update_model(value: str) -> str:
                    global model, code_agent
                    try:
                        # Re-initialize the model with the new model_id
                        model = InferenceClientModel(model_id=value, token=hf_api_key)

                        # Re-create the agent with the new model (without memory_enabled parameter)
                        code_agent = CodeAgent(
                            tools=[], model=model, max_steps=MAX_AGENT_STEPS
                        )

                        code_agent.prompt_templates["system_prompt"] = (
                            code_agent.prompt_templates["system_prompt"]
                            + "\n\n"
                            + TOASTER_SYSTEM_PROMPT
                        )

                        return f"Toaster brain upgraded to {value}!"
                    except Exception as e:
                        return f"Error changing model: {str(e)}"

                model_button = gr.Button("Change Model")
                model_output = gr.Textbox(label="Model Status")
                model_button.click(
                    update_model, inputs=model_dropdown, outputs=model_output
                )

            # Add step configuration slider
            with gr.Row():
                step_slider = gr.Slider(
                    minimum=1,
                    maximum=10,
                    value=MAX_AGENT_STEPS,
                    step=1,
                    label="Toaster Intelligence Level (Reasoning Steps)",
                    info="Higher values make the toaster think more deeply before responding",
                )

                def update_steps(value: int) -> str:
                    global MAX_AGENT_STEPS
                    MAX_AGENT_STEPS = int(value)
                    print(f"Updated MAX_AGENT_STEPS to {MAX_AGENT_STEPS}")
                    # Also update the agent's max_steps
                    code_agent.max_steps = MAX_AGENT_STEPS
                    return f"Toaster intelligence set to level {MAX_AGENT_STEPS}!"

                step_button = gr.Button("Set Toaster Intelligence")
                step_output = gr.Textbox(label="Status")
                step_button.click(update_steps, inputs=step_slider, outputs=step_output)

            # Add conversation display
            with gr.Row():
                # Initialize chat history with a welcome message
                if not chat_history:
                    chat_history.append({"role": "assistant", "content": TOASTER_INTRO})

                # In Gradio 5.23, the HTML component might have different parameters
                conversation_display = gr.HTML(
                    value=format_chat_history(chat_history),
                    label="Conversation",
                    elem_id="conversation-display",
                    every=1.0,  # Update every second in Gradio 5.x
                )

                # After creating the component, assign it to our reference
                ui_elements.conversation_display = conversation_display

                # Add Clear Chat button
                clear_button = gr.Button("Clear Chat")

                def clear_and_reset() -> str:
                    global chat_history
                    chat_history = [{"role": "assistant", "content": TOASTER_INTRO}]
                    return format_chat_history(chat_history)

                clear_button.click(clear_and_reset, outputs=conversation_display)

            # Add text input for typing questions
            with gr.Row():
                with gr.Column(elem_classes="input-section"):
                    gr.Markdown("### Type your question:")

                    text_input = gr.Textbox(
                        placeholder="Ask Toaster 3000 something...",
                        label="Text Input",
                        lines=2,
                    )

                    text_submit = gr.Button("Send Message")

                    # Audio output for text responses
                    text_audio_output = gr.Audio(
                        label="Audio Response",
                        autoplay=True,
                        visible=True,
                        type="numpy",
                    )

                    # Set up text input submission
                    text_submit.click(
                        process_text_input,
                        inputs=text_input,
                        outputs=[conversation_display, text_input, text_audio_output],
                    )

                    # Also allow Enter key to submit
                    text_input.submit(
                        process_text_input,
                        inputs=text_input,
                        outputs=[conversation_display, text_input, text_audio_output],
                    )

            # Add push-to-talk functionality
            with gr.Row():
                with gr.Column(elem_classes="input-section"):
                    gr.Markdown("### Push to Talk:")

                    push_to_talk = gr.Audio(
                        sources=["microphone"],
                        type="numpy",
                        label="Push to Talk",
                        streaming=False,
                        elem_classes=["push-to-talk-input"],
                    )

                    # Audio output for push-to-talk responses
                    ptt_audio_output = gr.Audio(
                        label="Audio Response",
                        autoplay=True,
                        visible=True,
                        type="numpy",
                    )

                    # Handle push-to-talk input
                    push_to_talk.change(
                        lambda audio: process_audio(audio, mode="push-to-talk"),
                        inputs=push_to_talk,
                        outputs=[conversation_display, ptt_audio_output],
                    )

                    gr.Markdown(
                        """
                        **How to use:**
                        1. Click the microphone button
                        2. Speak your question
                        3. Stop recording when finished
                        4. Toaster 3000 will respond
                        """
                    )

            # Add continuous listening option (the original functionality)
            with gr.Row():
                with gr.Column(elem_classes="input-section"):
                    gr.Markdown("### Continuous Listening:")

                    # Add a toggle for continuous mode
                    continuous_toggle = gr.Checkbox(
                        label="Enable Continuous Listening",
                        value=False,
                        info="When enabled, Toaster 3000 will listen continuously and respond after you pause speaking",
                    )

                    # Continuous listening components (hidden by default)
                    with gr.Column(visible=False) as continuous_components:
                        # Initialize the pause detector with proper configuration
                        from fastrtc import AlgoOptions, SileroVadOptions

                        # Configure pause detection options
                        algo_options = AlgoOptions(
                            audio_chunk_duration=0.6,
                            started_talking_threshold=0.2,
                            speech_threshold=0.1,
                        )

                        model_options = SileroVadOptions(
                            threshold=0.5,
                            min_speech_duration_ms=250,
                            min_silence_duration_ms=100,
                        )

                        pause_detector = ReplyOnPause(
                            continuous_audio_processor,
                            algo_options=algo_options,
                            model_options=model_options,
                        )

                        # Create the stream with configured pause detector
                        stream = Stream(
                            pause_detector, modality="audio", mode="send-receive"
                        )

                        # Render just the stream UI
                        stream.ui.render()

                    # Toggle visibility of continuous mode
                    continuous_toggle.change(
                        lambda x: gr.update(visible=x),
                        inputs=continuous_toggle,
                        outputs=continuous_components,
                    )

            with gr.Row():
                # Custom footer
                gr.HTML(
                    """
                    <div class="footer">
                        <span class="toaster-icon"></span>
                        <span>Toaster 3000 - Making the world a better place, one slice at a time!</span>
                    </div>
                    """
                )

        app.launch(share=True)
    except KeyboardInterrupt:
        print("\nShutting down Toaster 3000...")
    finally:
        # Clean up resources
        print("Cleaning up resources...")


if __name__ == "__main__":
    main()
