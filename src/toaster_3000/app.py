"""Gradio application for Toaster 3000."""

from typing import Any, Optional, Tuple

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

    def create_ui(self) -> gr.Blocks:
        """Create Gradio interface with session management.

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
                # Session expired, create new one
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

            # Header
            with gr.Row():
                gr.HTML(
                    '<h1 class="gradio-title">'
                    '<span class="toaster-icon"></span>Toaster 3000'
                    "</h1>"
                )

            # Model info
            with gr.Row():
                gr.Markdown(f"**Model**: {self.config.model_id}")

            # Initialize session on load
            app.load(init_session, outputs=[session_state])

            # Introduction section
            with gr.Row():
                with gr.Column():
                    gr.HTML(
                        f"<div class='toaster-intro'>"
                        f"{TOASTER_INTRO.replace(chr(10), '<br/>')}"
                        f"</div>",
                        label="Welcome Message",
                    )
                    gr.Audio(
                        label="Introduction",
                        autoplay=True,
                        type="numpy",
                        visible=True,
                        value=generate_intro_audio(),
                    )

            # Model selection
            with gr.Row():
                model_dropdown = gr.Dropdown(
                    choices=[
                        "gpt2",
                        "facebook/opt-125m",
                        "EleutherAI/pythia-70m",
                        "meta-llama/Llama-3.3-70B-Instruct",
                        "Qwen/Qwen2.5-Coder-1.5B-Instruct",
                    ],
                    value=self.config.model_id,
                    label="Select Model",
                    info="Choose a different model (requires restart to apply)",
                    allow_custom_value=True,
                )
                model_button = gr.Button("Change Model")
                model_output = gr.Textbox(label="Model Status")
                model_button.click(
                    update_model,
                    inputs=[session_state, model_dropdown],
                    outputs=model_output,
                )

            # Intelligence level
            with gr.Row():
                step_slider = gr.Slider(
                    minimum=1,
                    maximum=10,
                    value=self.config.max_agent_steps,
                    step=1,
                    label="Toaster Intelligence Level (Reasoning Steps)",
                    info="Higher values make the toaster think more deeply",
                )
                step_button = gr.Button("Set Toaster Intelligence")
                step_output = gr.Textbox(label="Status")
                step_button.click(
                    update_intelligence,
                    inputs=[session_state, step_slider],
                    outputs=step_output,
                )

            # Conversation display
            with gr.Row():
                # Initialize with intro
                conversation_display = gr.HTML(
                    value="<div class='chat-container'></div>",
                    label="Conversation",
                    elem_id="conversation-display",
                )

                clear_button = gr.Button("Clear Chat")
                clear_button.click(
                    clear_chat,
                    inputs=[session_state],
                    outputs=[conversation_display],
                )

            # Text input section
            with gr.Row():
                with gr.Column(elem_classes="input-section"):
                    gr.Markdown("### Type your question:")

                    text_input = gr.Textbox(
                        placeholder="Ask Toaster 3000 something...",
                        label="Text Input",
                        lines=2,
                    )

                    text_submit = gr.Button("Send Message")

                    text_audio_output = gr.Audio(
                        label="Audio Response",
                        autoplay=True,
                        visible=True,
                        type="numpy",
                    )

                    text_submit.click(
                        process_text,
                        inputs=[session_state, text_input],
                        outputs=[conversation_display, text_input, text_audio_output],
                    )

                    text_input.submit(
                        process_text,
                        inputs=[session_state, text_input],
                        outputs=[conversation_display, text_input, text_audio_output],
                    )

            # Push-to-talk section
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

                    ptt_audio_output = gr.Audio(
                        label="Audio Response",
                        autoplay=True,
                        visible=True,
                        type="numpy",
                    )

                    push_to_talk.change(
                        process_audio,
                        inputs=[session_state, push_to_talk],
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
