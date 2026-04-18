"""Gradio application for Toaster 3000."""

import html
from threading import Lock
from typing import Any, Dict, Generator, Optional, Tuple

import gradio as gr

from toaster_3000.config import ToasterConfig
from toaster_3000.constants import TOASTER_INTRO
from toaster_3000.runtime import ToasterRuntime
from toaster_3000.session_manager import SessionManager
from toaster_3000.theme import toaster_css, toaster_theme
from toaster_3000.tools import TOOL_RISK_POLICY_TEXT


def _render_voice_state(state: str) -> str:
    """Return HTML badge for the current wake-word voice state."""
    configs = {
        "sleeping": ("💤", "Sleeping — say <strong>Hey Toaster</strong> to wake me up", "#8a6a3a", "#FFF3E0"),
        "listening": ("👂", "Listening…", "#234b2c", "#E8F4EA"),
        "responding": ("🍞", "Responding…", "#5a3a1a", "#FFF3E0"),
    }
    icon, label, color, bg = configs.get(state, configs["sleeping"])
    return (
        f"<div class='voice-state-badge' style='"
        f"background:{bg};color:{color};border-left:4px solid {color};"
        f"padding:8px 14px;border-radius:10px;margin:6px auto;"
        f"max-width:520px;font-size:0.92rem;display:flex;align-items:center;gap:10px;'>"
        f"<span style='font-size:1.2em'>{icon}</span><span>{label}</span>"
        f"</div>"
    )


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
        # Cache for timer polling — skip DOM update when nothing changed
        self._last_talk_state: Dict[str, Any] = {}

    def _create_continuous_handler(self) -> Any:
        """Create a fastrtc ReplyOnStopWords handler with wake-word activation.

        Listens continuously via Moonshine STT. Activates the full
        Whisper → Agent → Kokoro TTS pipeline only after a wake phrase.
        """
        from fastrtc import AlgoOptions, ReplyOnStopWords, SileroVadOptions

        def continuous_audio_processor(
            audio: Tuple[int, Any],
            session_id: Optional[str] = None,
            *extra_args: Any,
        ) -> Generator[Tuple[int, Any], None, None]:
            """Process audio via STT → Agent → TTS pipeline.

            Args:
                audio: Tuple of (sample_rate, audio_data) — captured after wake word.
                session_id: Gradio session id shared with text/push-to-talk paths.
                *extra_args: FastRTC may pass additional component values.

            Yields:
                Audio chunks from TTS response.
            """
            from fastrtc import get_current_context

            session = None
            try:
                try:
                    webrtc_id = get_current_context().webrtc_id
                except RuntimeError:
                    webrtc_id = None

                with self._stream_sessions_lock:
                    sid = self._stream_sessions.get(webrtc_id or "")
                    if sid is None:
                        bound = set(self._stream_sessions.values())
                        unbound = [s for s in self.session_manager.list_sessions()
                                   if s not in bound]
                        if unbound:
                            sid = unbound[0]
                        else:
                            sid = self.session_manager.create_session()
                        if webrtc_id:
                            self._stream_sessions[webrtc_id] = sid

                session = self.session_manager.get_session(sid)
                if session is None:
                    with self._stream_sessions_lock:
                        sid = self.session_manager.create_session()
                        if webrtc_id:
                            self._stream_sessions[webrtc_id] = sid
                    session = self.session_manager.get_session(sid)

                session._voice_state = "listening"
                sample_rate, audio_data = audio
                user_text, no_speech_prob = self.runtime.stt_service.transcribe(
                    (sample_rate, audio_data)
                )

                if not user_text or no_speech_prob > self.runtime.config.no_speech_threshold:
                    return

                session._voice_state = "responding"
                response_text = session.get_response_text(user_text)
                if response_text:
                    yield from self.runtime.tts_service.stream_audio_chunks(response_text)

            except Exception as e:
                print(f"Continuous audio processor error: {e}")
                error_msg = (
                    f"Oh crumbs! Error: {str(e)[:80]}... "
                    f"Shall we talk about bread instead?"
                )
                error_audio = self.runtime.tts_service.generate_audio(error_msg)
                if error_audio:
                    yield error_audio
            finally:
                if session is not None:
                    session._voice_state = "sleeping"

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

        return ReplyOnStopWords(
            continuous_audio_processor,
            stop_words=["hey toaster", "hey toast"],
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

        def get_talk_tab_updates(session_id: str) -> Tuple[Any, str, str]:
            """Return (conversation_html, idle_warning_html, voice_state_html)."""
            import time as _time
            session = self.session_manager.get_session(session_id)
            if session is None:
                return "<div class='error'>Error: Session expired</div>", "", _render_voice_state("sleeping")
            idle = _time.time() - session.last_active
            if idle > 240:
                mins = int(idle // 60)
                warning = (
                    f"<div class='idle-warning'>"
                    f"⏰ You've been away for {mins} min — your session resets at 5 min of inactivity."
                    f"</div>"
                )
            else:
                warning = ""
            msg_count = len(session.chat_history.get_all())
            voice_state = session._voice_state
            countdown_active = bool(session._countdown_html)
            cache_key = (msg_count, voice_state, countdown_active)
            if self._last_talk_state.get(session_id) == cache_key and not warning:
                return gr.update(), gr.update(), gr.update()
            self._last_talk_state[session_id] = cache_key
            return (
                session.chat_history.format_html(extra_html=session._countdown_html),
                warning,
                _render_voice_state(voice_state),
            )

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
            """Risk policy text for the settings panel."""
            return f"#### Risk Policy\n\n{TOOL_RISK_POLICY_TEXT}"

        def get_tool_gallery(session_id: str) -> Tuple[str, list]:
            """Return (gallery_html, tool_name_choices) for the tool gallery."""
            if not session_id:
                return "<p><em>No active session.</em></p>", []
            session = self.session_manager.get_session(session_id)
            if session is None:
                return "<p><em>Session expired.</em></p>", []
            tools = session.get_custom_tools()
            if not tools:
                return (
                    "<p class='tool-gallery-empty'>No custom tools yet. "
                    "Ask the Toaster to write a toast calculator, then register it!</p>",
                    [],
                )
            cards = "<div class='tool-gallery'>"
            for t in tools:
                cards += (
                    f"<div class='tool-card'>"
                    f"<strong class='tool-card-name'>{html.escape(t['name'])}</strong>"
                    f"<p class='tool-card-desc'>{html.escape(t['description'])}</p>"
                    f"</div>"
                )
            cards += "</div>"
            return cards, [t["name"] for t in tools]

        def invoke_custom_tool(session_id: str, tool_name: str, args_json: str) -> str:
            """Invoke a registered custom tool by name with JSON args."""
            import json
            if not session_id or not tool_name:
                return "Select a tool first."
            session = self.session_manager.get_session(session_id)
            if session is None:
                return "Session expired."
            tool = next((t for t in session._custom_tools if t.name == tool_name), None)
            if tool is None:
                return f"Tool '{tool_name}' not found."
            try:
                kwargs = json.loads(args_json) if args_json.strip() else {}
            except json.JSONDecodeError as e:
                return f"Invalid JSON: {e}"
            try:
                result = tool(**kwargs)
                return str(result)
            except Exception as e:
                return f"Error: {e}"

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

                    voice_state_indicator = gr.HTML(
                        value=_render_voice_state("sleeping"),
                        elem_id="voice-state-indicator",
                        show_label=False,
                    )
                    conversation_display = gr.HTML(
                        value="<div class='chat-container'></div>",
                        elem_id="conversation-display",
                        show_label=False,
                    )
                    idle_warning = gr.HTML(value="", elem_id="idle-warning")

                    # Poll every 1s so voice turns appear quickly in the chat display.
                    voice_timer = gr.Timer(value=1)
                    voice_timer.tick(
                        get_talk_tab_updates,
                        inputs=[session_state],
                        outputs=[conversation_display, idle_warning, voice_state_indicator],
                    )

                    with gr.Row():
                        clear_button = gr.Button(
                            "Reset Conversation", size="sm", variant="secondary"
                        )
                        download_btn = gr.DownloadButton(
                            "⬇️ Download Chat", size="sm", variant="secondary"
                        )
                    clear_button.click(
                        clear_chat,
                        inputs=[session_state],
                        outputs=[conversation_display],
                    )

                    def generate_chat_export(session_id: str) -> Optional[str]:
                        import tempfile
                        from datetime import datetime
                        session = self.session_manager.get_session(session_id)
                        if session is None:
                            return None
                        msgs = session.chat_history.get_all()
                        lines = [
                            "# Toaster 3000 Conversation\n",
                            f"_Exported {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n\n---\n",
                        ]
                        for m in msgs:
                            sender = "You" if m["role"] == "user" else "Toaster 3000"
                            lines.append(f"**{sender}:** {m['content']}\n\n")
                        content = "\n".join(lines)
                        fd, path = tempfile.mkstemp(suffix=".md", prefix="toaster_chat_")
                        import os
                        with os.fdopen(fd, "w") as f:
                            f.write(content)
                        return path

                    download_btn.click(
                        generate_chat_export,
                        inputs=[session_state],
                        outputs=[download_btn],
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
                                "_Tools the Toaster writes and registers during your session._",
                                elem_classes=["gr-markdown"],
                            )
                            custom_tools_display = gr.Markdown(
                                get_tool_management_info(""),
                            )
                            tool_gallery = gr.HTML(
                                "<p class='tool-gallery-empty'>No custom tools yet.</p>",
                                label="Active Tools",
                                show_label=True,
                            )
                            tools_refresh_btn = gr.Button("🔄 Refresh Tools", size="sm")

                            gr.Markdown("##### Quick Invoke")
                            with gr.Row():
                                tool_invoke_select = gr.Dropdown(
                                    choices=[],
                                    label="Tool",
                                    scale=1,
                                    interactive=True,
                                )
                                tool_invoke_args = gr.Textbox(
                                    label="Arguments (JSON)",
                                    placeholder='{"param": "value"}',
                                    scale=2,
                                )
                            tool_invoke_btn = gr.Button("Run Tool", size="sm")
                            tool_invoke_output = gr.Markdown("")

                            def refresh_tools(session_id):
                                gallery_html, choices = get_tool_gallery(session_id)
                                return (
                                    get_tool_management_info(session_id),
                                    gallery_html,
                                    gr.update(choices=choices),
                                )

                            tools_refresh_btn.click(
                                refresh_tools,
                                inputs=[session_state],
                                outputs=[custom_tools_display, tool_gallery, tool_invoke_select],
                            )
                            tool_invoke_btn.click(
                                invoke_custom_tool,
                                inputs=[session_state, tool_invoke_select, tool_invoke_args],
                                outputs=[tool_invoke_output],
                            )

                            gr.Markdown("---")

                            gr.Markdown("#### Audio")
                            voice_dropdown = gr.Dropdown(
                                choices=[
                                    ("Liam (US Male)", "am_liam"),
                                    ("Heart (US Female)", "af_heart"),
                                    ("Emma (UK Female)", "bf_emma"),
                                    ("Nicole (US Female)", "af_nicole"),
                                    ("Michael (US Male)", "am_michael"),
                                    ("Bella (US Female)", "af_bella"),
                                ],
                                value=self.runtime.config.tts_voice,
                                label="TTS Voice",
                                info="Switch voice — takes effect on the next response",
                            )
                            voice_btn = gr.Button("Apply Voice", size="sm")
                            voice_status = gr.Textbox(
                                label="", show_label=False, interactive=False
                            )
                            voice_btn.click(
                                lambda v: self.runtime.switch_tts_voice(v),
                                inputs=[voice_dropdown],
                                outputs=[voice_status],
                            )
                            gr.Markdown("---")
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

                # ─── AUDIT TAB ───
                with gr.Tab("🔍 Audit"):
                    gr.Markdown("### Tool Registration Audit Log")
                    gr.Markdown(
                        "_Every dynamic tool request is logged here — approved, denied, or failed._"
                    )
                    audit_display = gr.Dataframe(
                        headers=["Time", "Tool", "Risk", "Outcome", "Reasons"],
                        datatype=["str", "str", "str", "str", "str"],
                        col_count=(5, "fixed"),
                        label=None,
                        show_label=False,
                        wrap=True,
                    )
                    audit_refresh_btn = gr.Button("🔄 Refresh", size="sm", variant="secondary")

                    def get_audit_table(session_id: str):
                        session = self.session_manager.get_session(session_id)
                        if session is None:
                            return []
                        entries = session.get_tool_audit_entries(limit=50)
                        return [
                            [
                                e["created_at"][:19],
                                e["tool_name"],
                                e["risk_level"],
                                e["outcome"],
                                "; ".join(e["reasons"]) if e["reasons"] else "—",
                            ]
                            for e in entries
                        ]

                    audit_refresh_btn.click(
                        get_audit_table,
                        inputs=[session_state],
                        outputs=[audit_display],
                    )
                    audit_timer = gr.Timer(value=10)
                    audit_timer.tick(
                        get_audit_table,
                        inputs=[session_state],
                        outputs=[audit_display],
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
                    get_talk_tab_updates(session_id)[0],
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
