#!/usr/bin/env python3
"""Generate WAV test audio files from phrases.json using Kokoro TTS.

Usage:
    uv run python scripts/generate_test_audio.py
    uv run python scripts/generate_test_audio.py --voice af_heart --speed 0.9
"""

import argparse
import json
import sys
import wave
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).parent.parent
PHRASES_FILE = REPO_ROOT / "tests" / "phrases.json"
AUDIO_DIR = REPO_ROOT / "tests" / "audio"


def write_wav(path: Path, sample_rate: int, audio: np.ndarray) -> None:
    with wave.open(str(path), "w") as f:
        f.setnchannels(1)
        f.setsampwidth(2)  # int16
        f.setframerate(sample_rate)
        f.writeframes(audio.tobytes())


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate test audio from phrases")
    parser.add_argument("--voice", default="am_liam", help="Kokoro voice ID")
    parser.add_argument("--speed", type=float, default=1.0, help="TTS speed")
    parser.add_argument("--lang", default="en-us", help="TTS language")
    parser.add_argument(
        "--category", default=None, help="Only generate for this category"
    )
    args = parser.parse_args()

    phrases = json.loads(PHRASES_FILE.read_text())
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    try:
        from fastrtc import KokoroTTSOptions, get_tts_model
    except ImportError:
        print("ERROR: fastrtc not installed. Run: uv sync --all-extras")
        sys.exit(1)

    print(f"Loading Kokoro TTS model (voice={args.voice})...")
    tts_model = get_tts_model(model="kokoro")
    options = KokoroTTSOptions(voice=args.voice, speed=args.speed, lang=args.lang)

    categories = (
        {args.category: phrases[args.category]}
        if args.category and args.category in phrases
        else phrases
    )

    total = sum(len(v) for v in categories.values())
    done = 0

    for category, phrase_list in categories.items():
        cat_dir = AUDIO_DIR / category
        cat_dir.mkdir(exist_ok=True)

        for phrase in phrase_list:
            slug = phrase.lower().replace(" ", "_").replace("'", "")[:50]
            out_path = cat_dir / f"{slug}.wav"

            if out_path.exists():
                print(f"  [skip] {category}/{slug}.wav")
                done += 1
                continue

            print(f"  [{done+1}/{total}] {category}: \"{phrase}\"")

            try:
                chunks = list(tts_model.stream_tts_sync(phrase, options=options))
                all_audio = []
                sample_rate = None
                for chunk in chunks:
                    if isinstance(chunk, tuple):
                        rate, audio = chunk
                        if sample_rate is None:
                            sample_rate = rate
                        arr = audio if hasattr(audio, "shape") else np.array(audio)
                        all_audio.append(arr)

                if all_audio and sample_rate:
                    combined = np.concatenate(all_audio)
                    combined = (combined * 32767).clip(-32768, 32767).astype(np.int16)
                    write_wav(out_path, sample_rate, combined)
                    print(f"    -> {out_path.name} ({len(combined)/sample_rate:.2f}s)")
                else:
                    print(f"    WARNING: no audio generated for \"{phrase}\"")

            except Exception as e:
                print(f"    ERROR: {e}")

            done += 1

    print(f"\nDone. {done} files in {AUDIO_DIR}")


if __name__ == "__main__":
    main()
