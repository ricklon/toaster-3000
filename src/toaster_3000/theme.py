"""Theme and styling for Toaster 3000."""

import gradio as gr

# Create the theme for Toaster 3000 - warm toast colors
toaster_theme = gr.themes.Soft(
    primary_hue="orange",
    secondary_hue="amber",
    neutral_hue="stone",
).set(
    body_background_fill="#FFF8F0",
    body_background_fill_dark="#2a1f14",
    block_background_fill="#FFFFFF",
    block_background_fill_dark="#3a2f24",
    block_title_background_fill="#FFE4B5",
    block_title_background_fill_dark="#4a3f34",
    block_label_background_fill="#FFA07A",
    block_label_background_fill_dark="#e94560",
    body_text_color="#3a2f24",
    body_text_color_dark="#e0e0e0",
    block_title_text_color="#5a3a1a",
    block_title_text_color_dark="#ffffff",
    block_label_text_color="#ffffff",
    block_label_text_color_dark="#ffffff",
    block_info_text_color="#6a5a4a",
    block_info_text_color_dark="#c0c0c0",
    input_background_fill="#FFF3E0",
    input_background_fill_dark="#1a1a2e",
    button_primary_text_color="#ffffff",
    button_primary_text_color_dark="#ffffff",
    button_secondary_text_color="#5a3a1a",
    button_secondary_text_color_dark="#e0e0e0",
    checkbox_label_text_color="#3a2f24",
    checkbox_label_text_color_dark="#e0e0e0",
    slider_color="#FF6B35",
    color_accent="#FF6B35",
    color_accent_soft="#FFE4B5",
)

# Custom CSS for toaster theme - warm toast colors
toaster_css = """
/* Warm toast background */
.gradio-container {
    background: linear-gradient(135deg, #FFF8F0 0%, #FFE4B5 50%, #FFDAB9 100%);
    padding: 10px;
    min-height: 100vh;
    color: #3a2f24;
}

/* Force text to be readable */
.gr-markdown,
.gr-markdown p,
.gr-markdown span,
.gr-markdown strong,
.gr-markdown code,
textarea,
input[type="text"],
input[type="password"],
.form-group label,
.block label,
details summary,
details summary span,
.tab-nav button,
.tab-nav button span {
    color: #3a2f24 !important;
}

/* Tab buttons */
.tab-nav button,
.tab-nav button span {
    color: #3a2f24 !important;
    cursor: pointer !important;
    pointer-events: auto !important;
    z-index: 9999 !important;
    position: relative !important;
}
.tab-nav button.selected {
    color: #FF6B35 !important;
    border-bottom-color: #FF6B35 !important;
}
.tab-nav {
    z-index: 9999 !important;
    position: relative !important;
    pointer-events: auto !important;
}
.tab-nav button.selected {
    color: #FF6B35 !important;
    border-bottom-color: #FF6B35 !important;
}
.tab-nav {
    z-index: 9999 !important;
    position: relative !important;
    pointer-events: auto !important;
}

/* Dropdown options */
select option {
    background: #FFF8F0;
    color: #3a2f24;
}

/* Status indicator */
.status-indicator {
    color: #4CAF50 !important;
    font-weight: bold;
    text-align: center;
    padding: 8px;
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
    height: 30vh;
    max-height: 30vh;
    overflow-y: auto;
    border-radius: 10px;
    background-color: rgba(255, 255, 255, 0.95);
    padding: 15px;
    margin-top: 10px;
    border: 1px solid #FFE4B5;
}

@media (max-width: 768px) {
    #conversation-display {
        height: 28vh;
        max-height: 28vh;
        padding: 8px;
    }
}

.chat-container {
    background-color: transparent !important;
    border-radius: 10px !important;
    padding: 0 !important;
    max-height: 100% !important;
    overflow-y: auto !important;
    color: #3a2f24 !important;
}

.thinking {
    background-color: #FFF3E0 !important;
    color: #8a6a3a !important;
    padding: 12px !important;
    border-radius: 10px !important;
    margin-bottom: 10px !important;
    border-left: 4px solid #FFB347 !important;
    font-style: italic !important;
    animation: pulse-bg 1.2s ease-in-out infinite !important;
}

@keyframes pulse-bg {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.5; }
}

.bot-message--streaming {
    border-left-color: #FFB347 !important;
    opacity: 0.9 !important;
}

.user-message {
    background-color: #E8F4FA !important;
    color: #3a2f24 !important;
    padding: 12px !important;
    border-radius: 10px !important;
    margin-bottom: 10px !important;
    border-left: 4px solid #4F8EC9 !important;
    word-wrap: break-word !important;
}

.bot-message {
    background-color: #FFF3E0 !important;
    color: #3a2f24 !important;
    padding: 12px !important;
    border-radius: 10px !important;
    margin-bottom: 10px !important;
    border-left: 4px solid #FF6B35 !important;
    word-wrap: break-word !important;
}

/* Error message styling */
.error {
    color: #D32F2F !important;
    background-color: #FFEBEE !important;
    padding: 10px !important;
    border-radius: 5px !important;
    border-left: 4px solid #D32F2F !important;
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
    min-height: 44px !important;
}

.gr-button:hover {
    background-color: #FF8C5A !important;
}

.gr-form {
    border-radius: 10px !important;
    background-color: rgba(255, 255, 255, 0.6) !important;
    color: #3a2f24 !important;
}

/* Responsive audio components */
.gr-audio {
    width: 100% !important;
}

.voice-hero {
    display: flex;
    align-items: center;
    gap: 24px;
    max-width: 920px;
    margin: 8px auto 18px auto;
    padding: clamp(18px, 4vw, 34px);
    border-radius: 28px;
    background:
        radial-gradient(circle at 18% 30%, rgba(255, 183, 77, 0.46), transparent 32%),
        linear-gradient(135deg, rgba(255, 243, 224, 0.96), rgba(255, 255, 255, 0.82));
    border: 1px solid rgba(255, 107, 53, 0.22);
    box-shadow: 0 18px 50px rgba(130, 70, 20, 0.13);
}

.voice-orb {
    width: clamp(84px, 16vw, 150px);
    height: clamp(84px, 16vw, 150px);
    flex: 0 0 auto;
    border-radius: 999px;
    background:
        radial-gradient(circle at 35% 30%, #fff7d6 0 16%, transparent 17%),
        radial-gradient(circle, #ffb347 0 38%, #ff6b35 39% 68%, #7a3d1d 69% 100%);
    box-shadow:
        0 0 0 12px rgba(255, 179, 71, 0.16),
        0 0 46px rgba(255, 107, 53, 0.42);
    animation: voice-pulse 2.4s ease-in-out infinite;
}

@keyframes voice-pulse {
    0%, 100% {
        transform: scale(1);
        box-shadow:
            0 0 0 10px rgba(255, 179, 71, 0.15),
            0 0 42px rgba(255, 107, 53, 0.36);
    }
    50% {
        transform: scale(1.035);
        box-shadow:
            0 0 0 18px rgba(255, 179, 71, 0.08),
            0 0 64px rgba(255, 107, 53, 0.5);
    }
}

.voice-kicker {
    margin: 0 0 6px 0;
    color: #9a4c1f;
    font-size: 0.88rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}

.voice-subtitle {
    max-width: 660px;
    margin: 8px 0 0 0;
    color: #5f422a;
    font-size: clamp(1rem, 2.3vw, 1.22rem);
    line-height: 1.45;
}

.voice-ready-card {
    display: flex;
    align-items: center;
    gap: 14px;
    max-width: 920px;
    margin: 0 auto 14px auto;
    padding: 10px 16px;
    border-radius: 12px;
    background: rgba(232, 244, 234, 0.95);
    border: 1px solid rgba(54, 139, 72, 0.24);
    color: #234b2c;
    box-shadow: 0 6px 16px rgba(35, 75, 44, 0.07);
    font-size: 0.95rem;
    line-height: 1.4;
}

.voice-ready-card em {
    color: #8a4318;
    font-style: normal;
    font-weight: 800;
}

.ready-dot {
    width: 14px;
    height: 14px;
    flex: 0 0 auto;
    margin-top: 4px;
    border-radius: 999px;
    background: #2faa48;
    box-shadow: 0 0 0 8px rgba(47, 170, 72, 0.14);
    animation: ready-pulse 1.8s ease-in-out infinite;
}

@keyframes ready-pulse {
    0%, 100% {
        box-shadow: 0 0 0 6px rgba(47, 170, 72, 0.12);
    }
    50% {
        box-shadow: 0 0 0 13px rgba(47, 170, 72, 0.05);
    }
}

/* Intro audio plays automatically — hide the widget but keep the element live. */
.intro-audio-hidden {
    height: 0 !important;
    overflow: hidden !important;
    margin: 0 !important;
    padding: 0 !important;
    border: none !important;
    opacity: 0 !important;
    pointer-events: none !important;
}

/* Make the FastRTC microphone permission card look like the primary action. */
.audio-container {
    max-width: 520px !important;
    margin: 0 auto 12px auto !important;
    border-radius: 24px !important;
    border: 2px solid rgba(255, 107, 53, 0.45) !important;
    background: linear-gradient(135deg, #fff7e8, #ffe0bd) !important;
    box-shadow:
        0 16px 36px rgba(150, 78, 25, 0.16),
        inset 0 0 0 1px rgba(255, 255, 255, 0.72) !important;
}

.audio-container button,
.audio-container [role="button"] {
    cursor: pointer !important;
}

/* FastRTC renders two audio cards in send-receive mode; the second is a
   confusing duplicate permission card for this voice-first layout. */
.tabitem > .column > .row:has(.audio-container) + .row:has(.audio-container) {
    display: none !important;
}

.voice-state-guide {
    max-width: 720px;
    margin: 2px auto 12px auto;
    padding: 14px 18px;
    border-radius: 18px;
    background: rgba(255, 248, 240, 0.92);
    border: 1px solid rgba(255, 179, 71, 0.35);
    color: #4e321d;
}

.voice-state-guide strong {
    display: block;
    margin-bottom: 6px;
    color: #8a4318;
    letter-spacing: 0.02em;
}

.voice-state-guide ul {
    margin: 0;
    padding-left: 20px;
}

.voice-state-guide li {
    margin: 3px 0;
    line-height: 1.35;
}

@media (max-width: 768px) {
    .voice-hero {
        align-items: flex-start;
        flex-direction: column;
        gap: 14px;
    }
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
    min-height: 50px !important;
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
    color: #3a2f24 !important;
}

@media (max-width: 768px) {
    .input-section {
        padding: 10px !important;
        margin-top: 10px !important;
    }
}

.toaster-intro {
    background-color: #FFF3E0 !important;
    color: #3a2f24 !important;
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
