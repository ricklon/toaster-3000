"""Service classes for TTS and STT operations."""

import io
from threading import Lock
from typing import Any, List, Optional, Tuple

import numpy as np


class TTSService:
    """Thread-safe wrapper for TTS (Text-to-Speech) operations."""

    def __init__(self, model: Any, options: Any):
        """Initialize TTS service.

        Args:
            model: TTS model instance (e.g., Kokoro)
            options: TTS options/config
        """
        self._model = model
        self._options = options
        self._lock = Lock()

    def generate_audio(self, text: str) -> Optional[Tuple[int, Any]]:
        """Generate complete audio for text (thread-safe).

        Args:
            text: Text to convert to speech

        Returns:
            Tuple of (sample_rate, audio_array) or None if failed
        """
        if not text or not text.strip():
            return None

        with self._lock:
            try:
                segments = self._split_text_into_segments(text, max_length=300)
                all_audio_data = []
                sample_rate = None

                for segment in segments:
                    audio_chunks = list(
                        self._model.stream_tts_sync(segment, options=self._options)
                    )

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
                    return (sample_rate, complete_audio)

            except Exception as e:
                print(f"Error generating TTS: {e}")
                # Fallback: try all segments individually
                try:
                    fallback_segments = self._split_text_into_segments(
                        text, max_length=300
                    )
                    fallback_audio = []
                    fallback_rate = None

                    for seg in fallback_segments:
                        chunks = list(
                            self._model.stream_tts_sync(seg, options=self._options)
                        )
                        if chunks:
                            chunk_data = chunks[0]
                            if isinstance(chunk_data, tuple):
                                rate, audio = chunk_data
                                if fallback_rate is None:
                                    fallback_rate = rate
                                fallback_audio.append(
                                    audio
                                    if hasattr(audio, "shape")
                                    else np.array(audio)
                                )

                    if fallback_audio and fallback_rate:
                        return (fallback_rate, np.concatenate(fallback_audio))
                except Exception as fallback_error:
                    print(f"Fallback TTS also failed: {fallback_error}")

        return None

    @staticmethod
    def _split_text_into_segments(text: str, max_length: int = 200) -> List[str]:
        """Split a long text into smaller segments at sentence boundaries.

        Args:
            text: Text to split
            max_length: Maximum segment length

        Returns:
            List of text segments
        """
        import re

        # First split by sentence endings (., !, ?)
        sentences = re.split(r"(?<=[.!?])\s+", text)

        segments = []
        current_segment = ""

        for sentence in sentences:
            # If adding this sentence would make the segment too long,
            # start a new segment
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


class STTService:
    """Thread-safe wrapper for STT (Speech-to-Text) operations."""

    def __init__(self, model: Any):
        """Initialize STT service.

        Args:
            model: Whisper model instance
        """
        self._model = model
        self._lock = Lock()

    def transcribe(self, audio: Tuple[int, Any]) -> str:
        """Transcribe audio to text (thread-safe).

        Args:
            audio: Tuple of (sample_rate, audio_data) or audio bytes

        Returns:
            Transcribed text
        """
        with self._lock:
            try:
                # Handle different audio input formats
                if isinstance(audio, tuple):
                    sample_rate, audio_data = audio
                    # Convert to bytes
                    audio_bytes = io.BytesIO()
                    import soundfile as sf

                    sf.write(audio_bytes, audio_data.T, sample_rate, format="wav")
                    audio_bytes.seek(0)
                else:
                    audio_bytes = audio

                # Transcribe
                segments, info = self._model.transcribe(audio_bytes)

                # Collect all segments
                text_segments = []
                for segment in segments:
                    text_segments.append(segment.text)

                return " ".join(text_segments)

            except Exception as e:
                print(f"Error transcribing audio: {e}")
                return ""
