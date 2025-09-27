import io
import os
import sys
import threading
import time

import gradio as gr
import numpy as np

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

# Use a freely available model instead of the Qwen model
# Options include: gpt2, facebook/opt-125m, EleutherAI/pythia-70m
model_id = os.getenv(
    "MODEL_NAME", "Qwen/Qwen2.5-Coder-1.5B-Instruct"
)  # Default to gpt2 if not specified
model_id = os.getenv(
    "MODEL_NAME", "meta-llama/Llama-3.3-70B-Instruct"
)  # Default to gpt2 if not specified
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
chat_history = []

# Custom CSS for toaster theme - updated for Gradio 5.x
toaster_css = """
.gradio-container {
    background-image: linear-gradient(to bottom right, #FFA07A, #FFE4B5);
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
}
/* Updated chat container for Gradio 5.x */
#conversation-display {
    height: 300px;
    overflow-y: auto;
    border-radius: 10px;
    background-color: rgba(255, 255, 255, 0.8);
    padding: 10px;
    margin-top: 15px;
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
}
.bot-message {
    background-color: #FFF3E0 !important;
    padding: 8px !important;
    border-radius: 10px !important;
    margin-bottom: 8px !important;
    border-left: 4px solid #FF6B35 !important;
}
/* Gradio 5.x specific styles */
.gr-interface {
    border-radius: 12px !important;
    overflow: hidden !important;
}
.gr-button {
    background-color: #FF6B35 !important;
    color: white !important;
    border: none !important;
}
.gr-button:hover {
    background-color: #FF8C5A !important;
}
.gr-form {
    border-radius: 10px !important;
    background-color: rgba(255, 255, 255, 0.6) !important;
}
/* Push to talk button styling */
.push-to-talk-btn {
    background-color: #FF6B35 !important;
    color: white !important;
    font-weight: bold !important;
    padding: 12px 24px !important;
    border-radius: 50px !important;
    margin: 10px auto !important;
    display: block !important;
    transition: all 0.2s !important;
    border: 2px solid #E55B2B !important;
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
.input-section {
    background-color: rgba(255, 255, 255, 0.6) !important;
    border-radius: 10px !important;
    padding: 10px !important;
    margin-top: 15px !important;
}
.toaster-intro {
    background-color: #FFF3E0 !important;
    padding: 15px !important;
    border-radius: 10px !important;
    margin-bottom: 15px !important;
    border-left: 4px solid #FF6B35 !important;
    font-size: 1.1em !important;
    line-height: 1.4 !important;
}
"""


def format_chat_history(history):
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


def update_conversation_display():
    """Update the conversation display element with the current chat history"""
    if ui_elements.conversation_display is not None:
        try:
            # In Gradio 5.x, we should use update differently
            return gr.update(value=format_chat_history(chat_history))
        except Exception as e:
            print(f"Error updating conversation display: {e}")


# Add this new function for sequential TTS generation
def generate_sequential_tts(text_response):
    """
    Generate TTS for longer responses by playing segments sequentially
    Returns a tuple of (sample_rate, audio_data) with the first segment,
    and triggers sequential playback of the rest
    """
    try:
        import sounddevice as sd
    except ImportError:
        print("Warning: sounddevice module not found. Installing...")
        try:
            # Try to install sounddevice
            import subprocess

            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "sounddevice"]
            )
            import sounddevice as sd

            print("Successfully installed sounddevice")
        except Exception as e:
            print(f"Error installing sounddevice: {e}")
            print("Will continue without sequential playback")

    # Split response into segments
    response_segments = split_text_into_segments(text_response, max_length=300)
    print(f"Response split into {len(response_segments)} segments")

    if not response_segments:
        return None

    # Get audio for the first segment to return immediately
    first_segment = response_segments[0]
    print(f"Processing first segment: {first_segment[:50]}...")
    first_audio_chunks = list(tts_model.stream_tts_sync(first_segment, options=options))

    if not first_audio_chunks:
        return None

    first_audio = first_audio_chunks[0]

    # If there are more segments, start a background thread to play them sequentially
    if len(response_segments) > 1:

        def play_remaining_segments():
            try:
                import sounddevice as sd

                # Wait for the first segment to finish playing
                # Calculate duration of first segment and add a small buffer
                if isinstance(first_audio, tuple):
                    sample_rate, audio_data = first_audio
                    duration = len(audio_data) / sample_rate + 0.5  # Add 0.5s buffer
                else:
                    # Estimate duration if we don't know the exact format
                    duration = (
                        len(first_segment) * 0.1
                    )  # Rough estimate: 0.1s per character

                # Wait before playing the next segment
                time.sleep(duration)

                # Play each subsequent segment
                for i, segment in enumerate(response_segments[1:], 1):
                    print(
                        f"Playing segment {i+1}/{len(response_segments)}: {segment[:50]}..."
                    )

                    try:
                        audio_chunks = list(
                            tts_model.stream_tts_sync(segment, options=options)
                        )
                        if audio_chunks:
                            audio_data = audio_chunks[0]

                            if isinstance(audio_data, tuple):
                                segment_rate, segment_audio = audio_data
                                sd.play(segment_audio, segment_rate)
                                # Wait for audio to finish
                                segment_duration = (
                                    len(segment_audio) / segment_rate + 0.5
                                )
                                time.sleep(segment_duration)
                            else:
                                # If we don't understand the format, just wait based on text length
                                print(
                                    f"Unknown audio format for segment {i+1}, skipping playback"
                                )
                                time.sleep(len(segment) * 0.1)
                    except Exception as e:
                        print(f"Error playing segment {i+1}: {e}")
                        time.sleep(1)  # Wait a bit before continuing

            except Exception as e:
                print(f"Error in sequential TTS playback: {e}")

        # Start the background thread for sequential playback
        threading.Thread(target=play_remaining_segments, daemon=True).start()

    # Return the first segment's audio immediately
    return first_audio


# Helper function to get agent response with chat history
def get_agent_response_with_memory(user_input):
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


def process_text_input(text):
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
        audio_data = generate_sequential_tts(agent_response)
    except Exception as audio_error:
        print(f"Error generating audio: {audio_error}")
        audio_data = None

    return format_chat_history(chat_history), gr.update(value=""), audio_data


def process_audio(audio, mode="push-to-talk"):
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

        # Generate and play audio sequentially
        try:
            audio_data = generate_sequential_tts(agent_response)
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

        # Generate error audio with sequential playback
        try:
            audio_data = generate_sequential_tts(error_msg)
        except Exception as audio_error:
            print(f"Error generating error audio: {audio_error}")
            audio_data = None

        return format_chat_history(chat_history), audio_data


# Modify the continuous_audio_processor function to use sequential TTS
def continuous_audio_processor(audio):
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

        # For continuous mode, just yield the first segment audio chunks
        # (additional segments will be played by the sequential TTS in the background)
        response_segments = split_text_into_segments(agent_response, max_length=300)

        if response_segments:
            first_segment = response_segments[0]
            print(f"Processing first segment: {first_segment[:50]}...")
            try:
                audio_chunks = list(
                    tts_model.stream_tts_sync(first_segment, options=options)
                )
                if audio_chunks:
                    # Start a background thread to play the rest of the segments
                    if len(response_segments) > 1:

                        def play_remaining_segments():
                            try:
                                import sounddevice as sd

                                # Wait before playing the next segment
                                time.sleep(
                                    2
                                )  # Give some buffer time for the first segment

                                # Play each subsequent segment
                                for i, segment in enumerate(response_segments[1:], 1):
                                    try:
                                        audio_chunks = list(
                                            tts_model.stream_tts_sync(
                                                segment, options=options
                                            )
                                        )
                                        if audio_chunks:
                                            audio_data = audio_chunks[0]

                                            if isinstance(audio_data, tuple):
                                                segment_rate, segment_audio = audio_data
                                                sd.play(segment_audio, segment_rate)
                                                # Wait for audio to finish
                                                segment_duration = (
                                                    len(segment_audio) / segment_rate
                                                    + 0.5
                                                )
                                                time.sleep(segment_duration)
                                    except Exception as e:
                                        print(f"Error playing segment {i+1}: {e}")
                            except Exception as e:
                                print(f"Error in sequential playback: {e}")

                        # Start the background thread
                        threading.Thread(
                            target=play_remaining_segments, daemon=True
                        ).start()

                    # Yield the first chunk for the continuous mode
                    yield audio_chunks[0]

            except Exception as e:
                print(f"Error processing segment: {e}")

    except Exception as e:
        print(f"Error in processing: {e}")
        # Return a toaster-themed error message
        error_msg = f"Oh crumbs! The Toaster 3000 encountered an error: {str(e)}. Perhaps we should toast something to fix it?"

        # Add error message to chat history
        chat_history.append({"role": "assistant", "content": error_msg})

        # Yield error audio chunks - just use one chunk to avoid issues
        try:
            audio_chunks = list(
                tts_model.stream_tts_sync(error_msg[:300], options=options)
            )
            if audio_chunks and len(audio_chunks) > 0:
                yield audio_chunks[0]
        except Exception as audio_error:
            print(f"Error generating error audio: {audio_error}")


def split_text_into_segments(text, max_length=200):
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


def speak_introduction():
    """Function to speak the complete introduction message"""
    print("Speaking introduction...")
    try:
        # Use sequential TTS for the introduction
        return generate_sequential_tts(TOASTER_INTRO)
    except Exception as e:
        print(f"Error generating introduction audio: {e}")
        # Fallback to just the first segment
        intro_segments = split_text_into_segments(TOASTER_INTRO, max_length=300)
        if intro_segments:
            first_segment = intro_segments[0]
            intro_audio_chunks = list(
                tts_model.stream_tts_sync(first_segment, options=options)
            )
            if intro_audio_chunks:
                return intro_audio_chunks[0]
    return None


# Run the application
def main():
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

                def update_model(value):
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

                def update_steps(value):
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

                def clear_and_reset():
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
                        sources=["microphone"],  # Updated from 'source' to 'sources'
                        type="numpy",
                        label="Push to Talk",
                        streaming=False,  # Not streaming for push-to-talk
                        elem_classes="push-to-talk-input",
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
                        # Initialize the pause detector with the FIXED continuous processor
                        pause_detector = ReplyOnPause(continuous_audio_processor)
                        pause_detector.pause_threshold = 1.5

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
