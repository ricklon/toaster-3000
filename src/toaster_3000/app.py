"""Gradio application for Toaster 3000."""

from typing import Any, Generator, Optional, Tuple

import gradio as gr

from toaster_3000.config import ToasterConfig
from toaster_3000.constants import TOASTER_INTRO
from toaster_3000.runtime import ToasterRuntime
from toaster_3000.session_manager import SessionManager
from toaster_3000.theme import toaster_css, toaster_theme


class ToasterApp:
    """Gradio app with session-based state management."""

    def __init__(self, config: ToasterConfig):
        """Initialize the Toaster application.

        Args:
            config: Application configuration
        """
        self.config = config
        self.runtime = ToasterRuntime(config)
        self.session_manager = SessionManager(self.runtime)
        self._stream_session_id: Optional[str] = None

    def _create_continuous_handler(self) -> Any:
        """Create a fastrtc ReplyOnPause handler for continuous listening.

        Returns:
            A callable that processes audio and yields TTS chunks.
        """
        from fastrtc import AlgoOptions, ReplyOnPause, SileroVadOptions

        def continuous_audio_processor(
            audio: Tuple[int, Any],
        ) -> Generator[Tuple[int, Any], None, None]:
            """Process audio via STT → Agent → TTS pipeline.

            Args:
                audio: Tuple of (sample_rate, audio_data)

            Yields:
                Audio chunks from TTS response.
            """
            import io

            import soundfile as sf

            try:
                sample_rate, audio_data = audio

                # Convert numpy array to WAV bytes
                audio_bytes = io.BytesIO()
                sf.write(audio_bytes, audio_data.T, sample_rate, format="wav")
                audio_bytes.seek(0)

                # STT via Whisper
                user_text = self.runtime.stt_service.transcribe(
                    (sample_rate, audio_data)
                )

                if not user_text.strip():
                    user_text = (
                        "I couldn't hear that clearly. "
                        "Could you please repeat? "
                        "Perhaps ask me about toasting?"
                    )

                # Get agent response using the shared session
                # so conversation memory is preserved
                sid = self._stream_session_id or self.session_manager.create_session()
                session = self.session_manager.get_session(sid)
                if session is None:
                    sid = self.session_manager.create_session()
                    session = self.session_manager.get_session(sid)

                if session is not None:
                    _, tts_audio = session.process_text_input(user_text)
                    if tts_audio is not None:
                        yield tts_audio

            except Exception as e:
                print(f"Continuous audio processor error: {e}")
                error_msg = (
                    f"Oh crumbs! Error: {str(e)[:80]}... "
                    f"Shall we talk about bread instead?"
                )
                error_audio = self.runtime.tts_service.generate_audio(error_msg)
                if error_audio:
                    yield error_audio

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

        return ReplyOnPause(
            continuous_audio_processor,
            algo_options=algo_options,
            model_options=model_options,
        )

    def create_ui(self) -> gr.Blocks:
        """Create compact Gradio interface with session management.

        Returns:
            Gradio Blocks application
        """

        def init_session(request: gr.Request) -> str:
            """Initialize session for each user.

            Args:
                request: Gradio request object

            Returns:
                Session ID
            """
            session_id = self.session_manager.create_session()
            print(f"Created session: {session_id}")
            return session_id

        def process_text(
            session_id: str, text: str
        ) -> Tuple[str, Any, Optional[Tuple[int, Any]]]:
            """Process text input for specific session.

            Args:
                session_id: User's session ID
                text: Input text

            Returns:
                Tuple of (html_response, textbox_update, audio_data)
            """
            if not session_id:
                return (
                    "<div class='error'>Error: No active session</div>",
                    gr.update(value=text),
                    None,
                )

            session = self.session_manager.get_session(session_id)
            if session is None:
                session_id = self.session_manager.create_session()
                session = self.session_manager.get_session(session_id)
                if session is None:
                    return (
                        "<div class='error'>Error: Could not create session</div>",
                        gr.update(value=text),
                        None,
                    )

            html_response, audio = session.process_text_input(text)
            return html_response, gr.update(value=""), audio

        def process_audio(
            session_id: str, audio: Tuple[int, Any]
        ) -> Tuple[str, Optional[Tuple[int, Any]]]:
            """Process audio input for specific session.

            Args:
                session_id: User's session ID
                audio: Audio data tuple

            Returns:
                Tuple of (html_response, audio_response)
            """
            if not session_id:
                return "<div class='error'>Error: No active session</div>", None

            session = self.session_manager.get_session(session_id)
            if session is None:
                return "<div class='error'>Error: Session expired</div>", None

            return session.process_audio_input(audio)

        def clear_chat(session_id: str) -> str:
            """Clear chat for specific session.

            Args:
                session_id: User's session ID

            Returns:
                HTML formatted cleared chat
            """
            if not session_id:
                return ""

            session = self.session_manager.get_session(session_id)
            if session is None:
                return ""

            return session.clear_chat()

        def update_model(session_id: str, model_id: str) -> str:
            """Update the AI model at runtime.

            Args:
                session_id: User's session ID
                model_id: New model ID

            Returns:
                Status message
            """
            try:
                return self.runtime.switch_model(model_id)
            except Exception as e:
                return f"Error: {str(e)}"

        def update_intelligence(session_id: str, level: int) -> str:
            """Update intelligence level for session.

            Args:
                session_id: User's session ID
                level: New intelligence level

            Returns:
                Status message
            """
            if not session_id:
                return "Error: No active session"

            session = self.session_manager.get_session(session_id)
            if session is None:
                return "Error: Session expired"

            return session.set_intelligence_level(level)

        def generate_intro_audio() -> Optional[Tuple[int, Any]]:
            """Generate introduction audio.

            Returns:
                Audio data tuple
            """
            return self.runtime.tts_service.generate_audio(TOASTER_INTRO)

        # Build the UI
        with gr.Blocks(theme=toaster_theme, css=toaster_css) as app:
            # Session state stored per-user
            session_state = gr.State(value=None)

            # Header row: title + compact intro + play button
            with gr.Row():
                with gr.Column(scale=3):
                    gr.HTML(
                        '<h1 class="gradio-title">'
                        '<span class="toaster-icon"></span>Toaster 3000'
                        "</h1>"
                    )
                with gr.Column(scale=1, min_width=150):
                    intro_audio_player = gr.Audio(
                        label=None,
                        autoplay=False,
                        type="numpy",
                        visible=True,
                        value=generate_intro_audio(),
                        show_label=False,
                    )
                    gr.Button(
                        "🔊 Play Intro",
                        variant="secondary",
                        size="sm",
                    ).click(
                        lambda: gr.update(value=generate_intro_audio()),
                        outputs=[intro_audio_player],
                    )

            # Model info (compact)
            gr.Markdown(f"**Model**: `{self.config.model_id}`")

            # Initialize session on load
            app.load(init_session, outputs=[session_state])

            # Two-column layout: left sidebar (config) + main content
            with gr.Row():
                # Left sidebar: Configuration
                with gr.Column(scale=1, min_width=280):
                    gr.Markdown("### ⚙️ Configuration")

                    model_dropdown = gr.Dropdown(
                        choices=[
                            "Qwen/Qwen3-Coder-Next",
                            "Qwen/Qwen3-14B",
                            "google/gemma-4-31B-it",
                            "google/gemma-4-26B-A4B-it",
                            "mistralai/Mistral-Small-4-119B-2603",
                            "mistralai/Devstral-Small-2-24B-Instruct-2512",
                            "meta-llama/Llama-3.3-70B-Instruct",
                        ],
                        value=self.config.model_id,
                        label="Model",
                        info=("Tool-capable models — " "switches live, no restart"),
                        allow_custom_value=True,
                    )
                    model_button = gr.Button("Switch Model", size="sm")
                    model_output = gr.Textbox(label="Status", lines=1, max_lines=2)
                    model_button.click(
                        update_model,
                        inputs=[session_state, model_dropdown],
                        outputs=model_output,
                    )

                    gr.Markdown("---")

                    step_slider = gr.Slider(
                        minimum=1,
                        maximum=10,
                        value=self.config.max_agent_steps,
                        step=1,
                        label="Intelligence Level",
                        info="Higher = deeper thinking",
                    )
                    step_button = gr.Button("Set", size="sm")
                    step_output = gr.Textbox(label="Status", lines=1, max_lines=2)
                    step_button.click(
                        update_intelligence,
                        inputs=[session_state, step_slider],
                        outputs=step_output,
                    )

                # Main content area
                with gr.Column(scale=3):
                    # Conversation display
                    conversation_display = gr.HTML(
                        value="<div class='chat-container'></div>",
                        label="Conversation",
                        elem_id="conversation-display",
                    )

                    with gr.Row():
                        clear_button = gr.Button("Clear Chat", size="sm")
                        clear_button.click(
                            clear_chat,
                            inputs=[session_state],
                            outputs=[conversation_display],
                        )

                    # Tabbed input methods
                    with gr.Tabs():
                        with gr.Tab("💬 Text"):
                            text_input = gr.Textbox(
                                placeholder="Ask Toaster 3000...",
                                label="Text Input",
                                lines=2,
                            )
                            text_submit = gr.Button("Send Message")

                        with gr.Tab("🎤 Push to Talk"):
                            push_to_talk = gr.Audio(
                                sources=["microphone"],
                                type="numpy",
                                label="Record your question",
                                streaming=False,
                            )

                        with gr.Tab("👂 Continuous"):
                            gr.Markdown(
                                "Speak naturally — Toaster responds " "when you pause."
                            )
                            # Stream must be created during UI build phase
                            # because it registers Gradio event handlers
                            handler = self._create_continuous_handler()
                            from fastrtc import Stream

                            stream = Stream(
                                handler,
                                modality="audio",
                                mode="send-receive",
                            )
                            with gr.Column(visible=False) as stream_container:
                                stream.ui.render()
                            start_stream_btn = gr.Button(
                                "🎙️ Start Listening",
                                variant="primary",
                            )
                            stop_stream_btn = gr.Button(
                                "⏹️ Stop Listening",
                                variant="stop",
                                visible=False,
                            )

                            def _toggle_stream(start: bool) -> Any:
                                """Show or hide the stream UI."""
                                return gr.update(visible=start)

                            start_stream_btn.click(
                                lambda: (
                                    _toggle_stream(True),
                                    gr.update(visible=False),
                                    gr.update(visible=True),
                                ),
                                outputs=[
                                    stream_container,
                                    start_stream_btn,
                                    stop_stream_btn,
                                ],
                            )
                            stop_stream_btn.click(
                                lambda: (
                                    _toggle_stream(False),
                                    gr.update(visible=True),
                                    gr.update(visible=False),
                                ),
                                outputs=[
                                    stream_container,
                                    start_stream_btn,
                                    stop_stream_btn,
                                ],
                            )
                    # Wire up push-to-talk → unified audio
                    with gr.Accordion("🔊 Audio Response", open=False):
                        unified_audio = gr.Audio(
                            label="Response",
                            autoplay=True,
                            visible=True,
                            type="numpy",
                        )

            # Wire up text input → unified audio
            text_submit.click(
                process_text,
                inputs=[session_state, text_input],
                outputs=[conversation_display, text_input, unified_audio],
            )
            text_input.submit(
                process_text,
                inputs=[session_state, text_input],
                outputs=[conversation_display, text_input, unified_audio],
            )

            # Wire up push-to-talk → unified audio
            push_to_talk.change(
                process_audio,
                inputs=[session_state, push_to_talk],
                outputs=[conversation_display, unified_audio],
            )

            # Footer
            with gr.Row():
                gr.HTML(
                    """
                    <div class="footer">
                        <span class="toaster-icon"></span>
                        <span>Toaster 3000 - Making the world a better place,
                        one slice at a time!</span>
                    </div>
                    """
                )

        return app  # type: ignore[no-any-return]

    def launch(self, **kwargs: Any) -> None:
        """Launch the application.

        Args:
            **kwargs: Arguments passed to Gradio's launch()
        """
        app = self.create_ui()
        app.launch(**kwargs)
