"""Theme and styling for Toaster 3000."""

import gradio as gr

# Create the theme for Toaster 3000 - dark mode optimized
toaster_theme = gr.themes.Soft(
    primary_hue="orange",  # Toast color
    secondary_hue="amber",  # Warm bread color
    neutral_hue="slate",  # Metallic toaster
).set(
    body_background_fill="#1a1a2e",
    body_background_fill_dark="#1a1a2e",
    block_background_fill="#16213e",
    block_background_fill_dark="#16213e",
    block_title_background_fill="#0f3460",
    block_title_background_fill_dark="#0f3460",
    block_label_background_fill="#e94560",
    block_label_background_fill_dark="#e94560",
    block_label_text_color="#ffffff",
    block_label_text_color_dark="#ffffff",
)

# Custom CSS for toaster dark theme - optimized for Gradio 5.x
toaster_css = """
/* Dark theme base container */
.gradio-container {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    padding: 10px;
    min-height: 100vh;
    color: #e0e0e0;
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
    background-color: rgba(22, 33, 62, 0.9);
    padding: 10px;
    margin-top: 15px;
    border: 1px solid #0f3460;
}

@media (max-width: 768px) {
    #conversation-display {
        height: 250px;
        max-height: 40vh;
        padding: 8px;
    }
}

.chat-container {
    background-color: rgba(22, 33, 62, 0.9) !important;
    border-radius: 10px !important;
    padding: 10px !important;
    margin-top: 15px !important;
    max-height: 300px !important;
    overflow-y: auto !important;
    color: #e0e0e0 !important;
}

.user-message {
    background-color: #1a3a5c !important;
    color: #e0e0e0 !important;
    padding: 8px !important;
    border-radius: 10px !important;
    margin-bottom: 8px !important;
    border-left: 4px solid #4F8EC9 !important;
    word-wrap: break-word !important;
}

.bot-message {
    background-color: #2a1a3e !important;
    color: #e0e0e0 !important;
    padding: 8px !important;
    border-radius: 10px !important;
    margin-bottom: 8px !important;
    border-left: 4px solid #e94560 !important;
    word-wrap: break-word !important;
}

.bot-message {
    background-color: #2a1a3e !important;
    color: #e0e0e0 !important;
    padding: 8px !important;
    border-radius: 10px !important;
    margin-bottom: 8px !important;
    border-left: 4px solid #e94560 !important;
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
    min-height: 44px !important; /* Touch-friendly size */
}

.gr-button:hover {
    background-color: #FF8C5A !important;
}

.gr-form {
    border-radius: 10px !important;
    background-color: rgba(22, 33, 62, 0.8) !important;
    color: #e0e0e0 !important;
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
    background-color: rgba(22, 33, 62, 0.8) !important;
    border-radius: 10px !important;
    padding: 15px !important;
    margin-top: 15px !important;
    width: 100% !important;
    color: #e0e0e0 !important;
}

@media (max-width: 768px) {
    .input-section {
        padding: 10px !important;
        margin-top: 10px !important;
    }
}

.toaster-intro {
    background-color: #16213e !important;
    color: #e0e0e0 !important;
    padding: 15px !important;
    border-radius: 10px !important;
    margin-bottom: 15px !important;
    border-left: 4px solid #e94560 !important;
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
