"""Gradio application for Toaster 3000."""

from threading import Lock
from typing import Any, Dict, Generator, Optional, Tuple

import gradio as gr

from toaster_3000.config import ToasterConfig
from toaster_3000.constants import TOASTER_INTRO
from toaster_3000.runtime import ToasterRuntime
from toaster_3000.session_manager import SessionManager
from toaster_3000.theme import toaster_css, toaster_theme
from toaster_3000.tools import TOOL_RISK_POLICY_TEXT


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
        # Maps webrtc_id → session_id so each WebRTC connection owns its session
        self._stream_sessions: Dict[str, str] = {}
        self._stream_sessions_lock = Lock()

    def _create_continuous_handler(self) -> Any:
        """Create a fastrtc ReplyOnPause handler for continuous listening.

        Returns:
            A callable that processes audio and yields TTS chunks.
        """
        from fastrtc import AlgoOptions, ReplyOnPause, SileroVadOptions

        def continuous_audio_processor(
            audio: Tuple[int, Any],
            session_id: Optional[str] = None,
            *extra_args: Any,
        ) -> Generator[Tuple[int, Any], None, None]:
            """Process audio via STT → Agent → TTS pipeline.

            Args:
                audio: Tuple of (sample_rate, audio_data)
                session_id: Gradio session id shared with text/push-to-talk paths.
                *extra_args: FastRTC may pass additional component values.

            Yields:
                Audio chunks from TTS response.
            """
            from fastrtc import get_current_context

            try:
                # Resolve the per-connection session via the WebRTC connection ID.
                # Each browser tab gets a unique webrtc_id, so sessions never mix.
                try:
                    webrtc_id = get_current_context().webrtc_id
                except RuntimeError:
                    webrtc_id = None

                # fastrtc passes its own webrtc_id as the session_id argument
                # rather than the Gradio component value. Resolve the real session
                # via _stream_sessions, binding on first call.
                with self._stream_sessions_lock:
                    sid = self._stream_sessions.get(webrtc_id or "")
                    if sid is None:
                        # Adopt the existing page-load session so the timer and
                        # voice handler share the same chat history.
                        bound = set(self._stream_sessions.values())
                        unbound = [s for s in self.session_manager.list_sessions()
                                   if s not in bound]
                        if unbound:
                            sid = unbound[0]
                        else:
                            sid = self.session_manager.create_session()
                        if webrtc_id:
                            self._stream_sessions[webrtc_id] = sid
                        print(f"[VOICE] bound webrtc {webrtc_id!r} → session {sid!r}")

                session = self.session_manager.get_session(sid)
                if session is None:
                    with self._stream_sessions_lock:
                        sid = self.session_manager.create_session()
                        if webrtc_id:
                            self._stream_sessions[webrtc_id] = sid
                    session = self.session_manager.get_session(sid)

                sample_rate, audio_data = audio
                user_text = self.runtime.stt_service.transcribe(
                    (sample_rate, audio_data)
                )

                if not user_text.strip():
                    user_text = (
                        "I couldn't hear that clearly. "
                        "Could you please repeat? "
                        "Perhaps ask me about toasting?"
                    )

                if session is not None:
                    response_text = session.get_response_text(user_text)
                    if response_text:
                        yield from self.runtime.tts_service.stream_audio_chunks(
                            response_text
                        )

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
        """Create immersive two-tab interface.

        Tab 1 "Talk": Full-screen conversation with continuous streaming.
        Tab 2 "Settings": Model config, intelligence, diagnostics.

        Returns:
            Gradio Blocks application
        """

        def process_text(
            session_id: str, text: str
        ) -> Generator[Tuple[str, Any, Optional[Tuple[int, Any]]], None, None]:
            """Process text input, streaming intermediate UI states."""
            if not session_id:
                yield (
                    "<div class='error'>Error: No active session</div>",
                    gr.update(value=text),
                    None,
                )
                return

            session = self.session_manager.get_session(session_id)
            if session is None:
                session_id = self.session_manager.create_session()
                session = self.session_manager.get_session(session_id)
                if session is None:
                    yield (
                        "<div class='error'>Error: Could not create session</div>",
                        gr.update(value=text),
                        None,
                    )
                    return

            first = True
            for html_response, audio in session.stream_text_input(text):
                if first:
                    # Clear the input box on the first yield
                    yield html_response, gr.update(value=""), audio
                    first = False
                else:
                    yield html_response, gr.update(), audio

        def process_audio(
            session_id: str, audio: Tuple[int, Any]
        ) -> Tuple[str, Optional[Tuple[int, Any]]]:
            """Process audio input for specific session."""
            if not session_id:
                return "<div class='error'>Error: No active session</div>", None

            session = self.session_manager.get_session(session_id)
            if session is None:
                return "<div class='error'>Error: Session expired</div>", None

            return session.process_audio_input(audio)

        def clear_chat(session_id: str) -> str:
            """Clear chat for specific session."""
            if not session_id:
                return ""

            session = self.session_manager.get_session(session_id)
            if session is None:
                return ""

            return session.clear_chat()

        def update_model(session_id: str, model_id: str) -> str:
            """Update the AI model at runtime."""
            try:
                result = self.runtime.switch_model(model_id)
                self.session_manager.refresh_all_agents()
                return result
            except Exception as e:
                return f"Error: {str(e)}"

        def update_intelligence(session_id: str, level: int) -> str:
            """Update intelligence level for session."""
            if not session_id:
                return "Error: No active session"

            session = self.session_manager.get_session(session_id)
            if session is None:
                return "Error: Session expired"

            return session.set_intelligence_level(level)

        def generate_intro_audio() -> Optional[Tuple[int, Any]]:
            """Generate introduction audio."""
            return self.runtime.tts_service.generate_audio(TOASTER_INTRO)

        def get_conversation_display(session_id: str) -> str:
            """Return the current conversation display for a session."""
            session = self.session_manager.get_session(session_id)
            if session is None:
                return "<div class='error'>Error: Session expired</div>"
            return session.chat_history.format_html()

        def get_session_info(session_id: str) -> str:
            """Get session diagnostics."""
            if not session_id:
                return "No active session"
            session = self.session_manager.get_session(session_id)
            if session is None:
                return f"Session `{session_id}` expired"
            history = session.chat_history.get_all()
            return (
                f"**Session**: `{session_id}`\n\n"
                f"**Messages**: {len(history)}\n\n"
                f"**Model**: `{self.runtime.config.model_id}`\n\n"
                f"**Intelligence**: {session.get_intelligence_level()}/10"
            )

        def get_recipes_display() -> str:
            """Format all saved recipes as markdown."""
            recipes = self.runtime.recipe_store.list_recipes()
            if not recipes:
                return "_No recipes saved yet. Ask the Toaster to make you one!_"
            parts = []
            for r in recipes:
                steps = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(r.steps))
                parts.append(
                    f"### {r.name}\n"
                    f"**Bread**: {r.bread_type}  \n"
                    f"**Ingredients**: {', '.join(r.ingredients)}\n\n"
                    f"{steps}\n\n"
                    f"_Saved: {r.created_at[:10]}_"
                )
            return "\n\n---\n\n".join(parts)

        def delete_recipe(name: str) -> Tuple[str, str]:
            """Delete a recipe by name, return (status, updated display)."""
            name = name.strip()
            if not name:
                return "Enter a recipe name to delete.", get_recipes_display()
            success = self.runtime.recipe_store.delete_recipe(name)
            msg = f"Deleted '{name}'." if success else f"Recipe '{name}' not found."
            return msg, get_recipes_display()

        def get_tool_management_info(session_id: str) -> str:
            """List custom tools and recent registration decisions."""
            if not session_id:
                return "No active session."
            session = self.session_manager.get_session(session_id)
            if session is None:
                return "Session expired."

            parts = [
                "#### Risk Policy",
                TOOL_RISK_POLICY_TEXT,
                "#### Active Custom Tools",
            ]
            tools = session.get_custom_tools()
            if not tools:
                parts.append(
                    "_No custom tools yet._ Ask the Toaster to write a pure "
                    "toast calculator, then register it as a tool."
                )
            else:
                parts.extend(f"- **{t['name']}** — {t['description']}" for t in tools)

            parts.append("\n#### Recent Tool Requests")
            audit_entries = session.get_tool_audit_entries(limit=10)
            if not audit_entries:
                parts.append("_No tool registration requests logged yet._")
            else:
                for entry in audit_entries:
                    reason = "; ".join(entry["reasons"]) or "sandbox-approved"
                    parts.append(
                        f"- **{entry['tool_name']}** — risk `{entry['risk_level']}`, "
                        f"outcome `{entry['outcome']}`. {reason}"
                    )

            return "\n\n".join(parts)

        # Build the UI
        with gr.Blocks(theme=toaster_theme, css=toaster_css) as app:
            session_state = gr.State(value=None)
            stream_session_state = gr.Textbox(
                visible=False,
                show_label=False,
                render=False,
            )

            # Two top-level tabs
            with gr.Tabs():
                # ─── TALK TAB ───
                with gr.Tab("🍞 Talk"):
                    gr.HTML(
                        """
                        <section class="voice-hero">
                            <div class="voice-orb" aria-hidden="true"></div>
                            <div>
                                <p class="voice-kicker">Start here</p>
                                <h1 class="gradio-title">
                                    <span class="toaster-icon"></span>Toaster 3000
                                </h1>
                                <p class="voice-subtitle">
                                    Allow microphone access, then click
                                    <strong>Record</strong> — Toaster 3000 will
                                    introduce itself and start listening.
                                </p>
                            </div>
                        </section>
                        """
                    )

                    # Hidden audio component — used only for the load event output
                    # so the outputs list stays consistent. Actual intro plays
                    # through the WebRTC stream on the first voice turn.
                    talk_intro_audio = gr.Audio(
                        autoplay=False,
                        type="numpy",
                        elem_classes=["intro-audio-hidden"],
                        show_label=False,
                    )

                    # Stream is the primary CTA — lives at the top, right after the hero.
                    handler = self._create_continuous_handler()
                    from fastrtc import Stream

                    stream = Stream(
                        handler,
                        modality="audio",
                        mode="send-receive",
                        additional_inputs=[stream_session_state],
                        ui_args={
                            "full_screen": False,
                            "hide_title": True,
                        },
                    )
                    stream.ui.render()

                    conversation_display = gr.HTML(
                        value="<div class='chat-container'></div>",
                        elem_id="conversation-display",
                        show_label=False,
                    )

                    # Poll every 2 s so voice turns appear in the chat display.
                    voice_timer = gr.Timer(value=2)
                    voice_timer.tick(
                        get_conversation_display,
                        inputs=[session_state],
                        outputs=[conversation_display],
                    )

                    clear_button = gr.Button(
                        "Reset Conversation", size="sm", variant="secondary"
                    )
                    clear_button.click(
                        clear_chat,
                        inputs=[session_state],
                        outputs=[conversation_display],
                    )

                # ─── RECIPES TAB ───
                with gr.Tab("📋 Recipes"):
                    gr.Markdown("### Your Toast Recipe Collection")
                    gr.Markdown(
                        "_The Toaster saves recipes automatically as you chat. "
                        "Browse, refresh, or delete them here._"
                    )
                    recipes_display = gr.Markdown(
                        "_Loading recipes…_", elem_id="recipes-display"
                    )
                    with gr.Row():
                        recipes_refresh_btn = gr.Button(
                            "🔄 Refresh", size="sm", variant="secondary"
                        )
                        recipes_refresh_btn.click(
                            get_recipes_display, outputs=[recipes_display]
                        )
                    gr.Markdown("#### Delete a Recipe")
                    with gr.Row():
                        delete_name_input = gr.Textbox(
                            placeholder="Recipe name…",
                            label="",
                            scale=4,
                            show_label=False,
                        )
                        delete_btn = gr.Button(
                            "🗑️ Delete", size="sm", variant="stop", scale=1
                        )
                    delete_status = gr.Markdown("")
                    delete_btn.click(
                        delete_recipe,
                        inputs=[delete_name_input],
                        outputs=[delete_status, recipes_display],
                    )

                # ─── SETTINGS TAB ───
                with gr.Tab("⚙️ Settings"):
                    gr.Markdown("### Configuration & Diagnostics")

                    with gr.Row():
                        with gr.Column():
                            gr.Markdown("#### Model")
                            model_dropdown = gr.Dropdown(
                                choices=[
                                    "google/gemma-4-31B-it",
                                    "google/gemma-4-26B-A4B-it",
                                    "Qwen/Qwen3-Coder-Next",
                                    "Qwen/Qwen3-14B",
                                    "mistralai/Mistral-Small-4-119B-2603",
                                    "mistralai/Devstral-Small-2-24B-Instruct-2512",
                                    "meta-llama/Llama-3.3-70B-Instruct",
                                ],
                                value=self.config.model_id,
                                label="Select Model",
                                info="Switches live — no restart needed",
                                allow_custom_value=True,
                            )
                            model_button = gr.Button("Switch Model")
                            model_output = gr.Textbox(label="Status")
                            model_button.click(
                                update_model,
                                inputs=[session_state, model_dropdown],
                                outputs=model_output,
                            )

                            gr.Markdown("---")

                            gr.Markdown("#### Intelligence")
                            step_slider = gr.Slider(
                                minimum=1,
                                maximum=10,
                                value=self.config.max_agent_steps,
                                step=1,
                                label="Reasoning Steps",
                                info="Higher = deeper thinking",
                            )
                            step_button = gr.Button("Set")
                            step_output = gr.Textbox(label="Status")
                            step_button.click(
                                update_intelligence,
                                inputs=[session_state, step_slider],
                                outputs=step_output,
                            )

                            gr.Markdown("---")

                            with gr.Accordion("Testing Inputs", open=False):
                                gr.Markdown(
                                    "These are fallback and test paths. The Talk tab "
                                    "is designed for continuous voice interaction.",
                                    elem_classes=["gr-markdown"],
                                )
                                text_input = gr.Textbox(
                                    placeholder="Type a test prompt for Toaster 3000...",
                                    label="Text test input",
                                    lines=2,
                                )
                                text_submit = gr.Button("Send Text Test")
                                text_audio = gr.Audio(
                                    label="Text Test Response",
                                    autoplay=True,
                                    type="numpy",
                                    visible=True,
                                )
                                text_submit.click(
                                    process_text,
                                    inputs=[session_state, text_input],
                                    outputs=[
                                        conversation_display,
                                        text_input,
                                        text_audio,
                                    ],
                                )
                                text_input.submit(
                                    process_text,
                                    inputs=[session_state, text_input],
                                    outputs=[
                                        conversation_display,
                                        text_input,
                                        text_audio,
                                    ],
                                )

                                push_to_talk = gr.Audio(
                                    sources=["microphone"],
                                    type="numpy",
                                    label="Push-to-talk test recording",
                                    streaming=False,
                                )
                                ptt_audio = gr.Audio(
                                    label="Push-to-talk Test Response",
                                    autoplay=True,
                                    type="numpy",
                                    visible=True,
                                )
                                push_to_talk.change(
                                    process_audio,
                                    inputs=[session_state, push_to_talk],
                                    outputs=[conversation_display, ptt_audio],
                                )

                                gr.Markdown("#### Test Prompts")
                                STARTERS = [
                                    (
                                        "👋 Introduce yourself",
                                        "Tell me about yourself, Toaster 3000! What can you do?",
                                    ),
                                    (
                                        "🍞 Best toast advice",
                                        "What's the single most important tip for perfect toast?",
                                    ),
                                    (
                                        "🧮 Calculate toast time",
                                        "How long should I toast a 20mm slice of sourdough to get it dark?",
                                    ),
                                    (
                                        "🥑 Recipe from ingredients",
                                        "I have sourdough, avocado, eggs, and lemon — what toast can I make?",
                                    ),
                                    (
                                        "💻 Write toast code",
                                        "Write me a Python function that calculates optimal toasting time "
                                        "given bread type, thickness, and desired darkness level.",
                                    ),
                                    (
                                        "🔧 Build a tool",
                                        "Build a crispiness rating calculator — takes moisture percentage "
                                        "and heat setting, returns a crispiness score from 1 to 10 — "
                                        "then register it as a tool I can use later.",
                                    ),
                                ]
                                for i in range(0, len(STARTERS), 2):
                                    with gr.Row():
                                        for label, text in STARTERS[i : i + 2]:
                                            btn = gr.Button(
                                                label,
                                                size="sm",
                                                variant="secondary",
                                            )

                                            def make_starter(t: str) -> Any:
                                                def handler(
                                                    sid: str,
                                                ) -> Generator[
                                                    Tuple[
                                                        str,
                                                        Any,
                                                        Optional[Tuple[int, Any]],
                                                    ],
                                                    None,
                                                    None,
                                                ]:
                                                    yield from process_text(sid, t)

                                                return handler

                                            btn.click(
                                                fn=make_starter(text),
                                                inputs=[session_state],
                                                outputs=[
                                                    conversation_display,
                                                    text_input,
                                                    text_audio,
                                                ],
                                            )

                        with gr.Column():
                            gr.Markdown("#### Session Info")
                            session_info = gr.Markdown("No active session")
                            refresh_btn = gr.Button("Refresh", size="sm")
                            refresh_btn.click(
                                get_session_info,
                                inputs=[session_state],
                                outputs=[session_info],
                            )

                            gr.Markdown("---")

                            gr.Markdown("#### Tool Management")
                            gr.Markdown(
                                "_Transparent record of custom tools the Toaster tries to register._",
                                elem_classes=["gr-markdown"],
                            )
                            custom_tools_display = gr.Markdown(
                                f"#### Risk Policy\n\n{TOOL_RISK_POLICY_TEXT}\n\n"
                                "#### Active Custom Tools\n\n"
                                "_No custom tools yet._\n\n"
                                "#### Recent Tool Requests\n\n"
                                "_No tool registration requests logged yet._"
                            )
                            tools_refresh_btn = gr.Button("Refresh Tools", size="sm")
                            tools_refresh_btn.click(
                                get_tool_management_info,
                                inputs=[session_state],
                                outputs=[custom_tools_display],
                            )

                            gr.Markdown("---")

                            gr.Markdown("#### Audio")
                            intro_btn = gr.Button("🔊 Play Intro", size="sm")
                            intro_audio = gr.Audio(
                                label=None,
                                autoplay=False,
                                type="numpy",
                                show_label=False,
                            )
                            intro_btn.click(
                                lambda: gr.update(value=generate_intro_audio()),
                                outputs=[intro_audio],
                            )

            def init_and_get_info(
                request: gr.Request,
            ) -> Tuple[str, str, str, str, str, str, Any]:
                """Initialize session and return initial info in one load event."""
                session_id = self.session_manager.create_session()
                print(f"Created session: {session_id}")
                return (
                    session_id,
                    session_id,
                    get_conversation_display(session_id),
                    get_session_info(session_id),
                    get_recipes_display(),
                    get_tool_management_info(session_id),
                    generate_intro_audio(),
                )

            # Single load event prevents the race where session_info fires
            # before session_state is populated
            app.load(
                init_and_get_info,
                outputs=[
                    session_state,
                    stream_session_state,
                    conversation_display,
                    session_info,
                    recipes_display,
                    custom_tools_display,
                    talk_intro_audio,
                ],
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
