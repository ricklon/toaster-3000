#!/usr/bin/env python3
"""Benchmark the full Toaster 3000 pipeline: STT → Agent → TTS.

Feeds pre-generated WAV files through each stage, measures latency,
and writes a report to benchmarks/results_<timestamp>.csv.

Usage:
    uv run python scripts/benchmark_pipeline.py
    uv run python scripts/benchmark_pipeline.py --category calculator
    uv run python scripts/benchmark_pipeline.py --no-tts --runs 3
"""

import argparse
import csv
import io
import json
import os
import sys
import time
import wave
from datetime import datetime
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).parent.parent
AUDIO_DIR = REPO_ROOT / "tests" / "audio"
PHRASES_FILE = REPO_ROOT / "tests" / "phrases.json"
CONVERSATIONS_FILE = REPO_ROOT / "tests" / "conversations.json"
BENCHMARKS_DIR = REPO_ROOT / "benchmarks"

sys.path.insert(0, str(REPO_ROOT / "src"))


def load_wav(path: Path):
    with wave.open(str(path), "r") as f:
        sample_rate = f.getframerate()
        frames = f.readframes(f.getnframes())
        audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32767.0
    return sample_rate, audio


def fmt(seconds: float) -> str:
    return f"{seconds:.2f}s" if seconds >= 0 else "  --  "


def run_benchmark(args) -> None:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")

    hf_key = os.getenv("HUGGINGFACE_API_KEY", "")
    inference_mode = os.getenv("INFERENCE_MODE", "hf")
    if inference_mode == "hf" and not hf_key:
        print("ERROR: HUGGINGFACE_API_KEY not set in .env (required for INFERENCE_MODE=hf)")
        sys.exit(1)

    from toaster_3000.config import ToasterConfig
    from toaster_3000.runtime import ToasterRuntime

    mode_defaults = {
        "hf": "google/gemma-4-26B-A4B-it",
        "ollama": "gemma3:4b",
        "mlx": "mlx-community/gemma-4-e4b-it-4bit",
    }
    model_id = args.model or os.getenv("MODEL_NAME", mode_defaults.get(inference_mode, "google/gemma-4-26B-A4B-it"))
    config = ToasterConfig(
        hf_api_key=hf_key,
        model_id=model_id,
        inference_mode=inference_mode,
        local_model_url=os.getenv("LOCAL_MODEL_URL", "http://localhost:11434"),
        whisper_model_size=args.whisper,
        max_agent_steps=1,
    )

    print(f"Loading runtime (model={model_id}, whisper={args.whisper})...")
    runtime = ToasterRuntime(config)

    # Give warmup thread time to finish
    time.sleep(5)

    phrases = json.loads(PHRASES_FILE.read_text())
    categories = (
        {args.category: phrases[args.category]}
        if args.category and args.category in phrases
        else phrases
    )

    results = []
    col_w = [12, 44, 7, 8, 7, 8]
    header = f"{'Category':<{col_w[0]}} {'Phrase':<{col_w[1]}} {'STT':>{col_w[2]}} {'Agent':>{col_w[3]}} {'TTS':>{col_w[4]}} {'Total':>{col_w[5]}}"
    print("\n" + header)
    print("-" * sum(col_w + [5]))

    for category, phrase_list in categories.items():
        cat_dir = AUDIO_DIR / category

        for phrase in phrase_list:
            slug = phrase.lower().replace(" ", "_").replace("'", "")[:50]
            wav_path = cat_dir / f"{slug}.wav"

            if not wav_path.exists():
                print(f"  [missing] {wav_path} — run generate_test_audio.py first")
                continue

            stt_times, agent_times, tts_times = [], [], []

            for run in range(args.runs):
                sample_rate, audio_data = load_wav(wav_path)

                # Stage 1: STT
                t0 = time.perf_counter()
                user_text, no_speech_prob = runtime.stt_service.transcribe(
                    (sample_rate, audio_data)
                )
                stt_time = time.perf_counter() - t0
                stt_times.append(stt_time)

                if not user_text or no_speech_prob > config.no_speech_threshold:
                    user_text = phrase  # fall back to raw phrase for agent test

                # Stage 2: Agent (LLM)
                agent_time = -1.0
                agent_response = ""
                if not args.no_agent:
                    from smolagents import ToolCallingAgent
                    from toaster_3000.tools import (
                        find_toast_recipe,
                        toast_calculator,
                    )

                    agent = ToolCallingAgent(
                        tools=[toast_calculator, find_toast_recipe],
                        model=runtime.model,
                        max_steps=1,
                        verbosity_level=0,
                    )
                    t0 = time.perf_counter()
                    try:
                        agent_response = agent.run(user_text, reset=True)
                    except Exception as e:
                        agent_response = f"[error: {e}]"
                    agent_time = time.perf_counter() - t0
                    agent_times.append(agent_time)

                # Stage 3: TTS
                tts_time = -1.0
                if not args.no_tts and agent_response:
                    t0 = time.perf_counter()
                    runtime.tts_service.generate_audio(str(agent_response))
                    tts_time = time.perf_counter() - t0
                    tts_times.append(tts_time)

            stt_avg = sum(stt_times) / len(stt_times)
            agent_avg = sum(agent_times) / len(agent_times) if agent_times else -1.0
            tts_avg = sum(tts_times) / len(tts_times) if tts_times else -1.0
            total = stt_avg + max(agent_avg, 0) + max(tts_avg, 0)

            short_phrase = phrase if len(phrase) <= col_w[1] else phrase[:col_w[1]-1] + "…"
            print(
                f"{category:<{col_w[0]}} {short_phrase:<{col_w[1]}} "
                f"{fmt(stt_avg):>{col_w[2]}} {fmt(agent_avg):>{col_w[3]}} "
                f"{fmt(tts_avg):>{col_w[4]}} {fmt(total):>{col_w[5]}}"
            )

            results.append({
                "category": category,
                "phrase": phrase,
                "stt_transcribed": user_text,
                "stt_s": round(stt_avg, 3),
                "agent_s": round(agent_avg, 3),
                "tts_s": round(tts_avg, 3),
                "total_s": round(total, 3),
                "model": model_id,
                "whisper": args.whisper,
                "runs": args.runs,
                "timestamp": datetime.now().isoformat(),
            })

    # Summary
    if results:
        valid = [r for r in results if r["agent_s"] >= 0]
        print("\n--- Summary ---")
        print(f"Phrases benchmarked : {len(results)}")
        if valid:
            print(f"Avg total latency   : {sum(r['total_s'] for r in valid)/len(valid):.2f}s")
            print(f"Avg STT latency     : {sum(r['stt_s'] for r in valid)/len(valid):.2f}s")
            print(f"Avg agent latency   : {sum(r['agent_s'] for r in valid)/len(valid):.2f}s")
            print(f"Avg TTS latency     : {sum(r['tts_s'] for r in valid)/len(valid):.2f}s")

        # Write CSV
        BENCHMARKS_DIR.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = BENCHMARKS_DIR / f"results_{ts}.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
        print(f"\nResults saved to: {csv_path}")


def run_conversation_benchmark(args) -> None:
    """Run multi-turn conversation benchmarks using real ToasterSession."""
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")

    hf_key = os.getenv("HUGGINGFACE_API_KEY", "")
    inference_mode = os.getenv("INFERENCE_MODE", "hf")
    if inference_mode == "hf" and not hf_key:
        print("ERROR: HUGGINGFACE_API_KEY not set in .env (required for INFERENCE_MODE=hf)")
        sys.exit(1)

    from toaster_3000.config import ToasterConfig
    from toaster_3000.runtime import ToasterRuntime
    from toaster_3000.session import ToasterSession
    mode_defaults = {
        "hf": "google/gemma-4-26B-A4B-it",
        "ollama": "gemma3:4b",
        "mlx": "mlx-community/gemma-4-e4b-it-4bit",
    }
    model_id = args.model or os.getenv("MODEL_NAME", mode_defaults.get(inference_mode, "google/gemma-4-26B-A4B-it"))
    config = ToasterConfig(
        hf_api_key=hf_key,
        model_id=model_id,
        inference_mode=inference_mode,
        local_model_url=os.getenv("LOCAL_MODEL_URL", "http://localhost:11434"),
        whisper_model_size=args.whisper,
        max_agent_steps=1,
    )

    print(f"Loading runtime (model={model_id}, whisper={args.whisper})...")
    runtime = ToasterRuntime(config)
    time.sleep(5)  # wait for warmup

    conversations = json.loads(CONVERSATIONS_FILE.read_text())
    convs = (
        {args.conversation: conversations[args.conversation]}
        if args.conversation and args.conversation in conversations
        else conversations
    )

    results = []
    for conv_name, turns in convs.items():
        print(f"\n{'='*60}")
        print(f"Conversation: {conv_name}")
        print(f"{'='*60}")

        session = ToasterSession(f"bench-{conv_name}", runtime)
        conv_total = 0.0

        for i, phrase in enumerate(turns, 1):
            # Find the WAV — search all category dirs
            wav_path = None
            slug = phrase.lower().replace(" ", "_").replace("'", "")[:50]
            for cat_dir in AUDIO_DIR.iterdir():
                candidate = cat_dir / f"{slug}.wav"
                if candidate.exists():
                    wav_path = candidate
                    break

            if wav_path is None:
                print(f"  Turn {i}: [no audio for \"{phrase}\"] — using text path")
                t0 = time.perf_counter()
                try:
                    # Drain the generator
                    for _ in session.stream_text_input(phrase):
                        pass
                    elapsed = time.perf_counter() - t0
                except Exception as e:
                    elapsed = time.perf_counter() - t0
                    print(f"    ERROR: {e}")
            else:
                sample_rate, audio_data = load_wav(wav_path)
                t0 = time.perf_counter()
                try:
                    _html, _audio = session.process_audio_input((sample_rate, audio_data))
                    elapsed = time.perf_counter() - t0
                except Exception as e:
                    elapsed = time.perf_counter() - t0
                    print(f"    ERROR: {e}")

            conv_total += elapsed
            history = session.chat_history.get_all()
            last_response = history[-1]["content"] if history else ""
            short = last_response[:80] + "…" if len(last_response) > 80 else last_response

            print(f"  Turn {i} ({elapsed:.2f}s): \"{phrase}\"")
            print(f"    → {short}")

            results.append({
                "conversation": conv_name,
                "turn": i,
                "phrase": phrase,
                "elapsed_s": round(elapsed, 3),
                "response_preview": last_response[:120],
                "model": model_id,
                "whisper": args.whisper,
                "timestamp": datetime.now().isoformat(),
            })

        print(f"\n  Total conversation time: {conv_total:.2f}s")

    if results:
        BENCHMARKS_DIR.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = BENCHMARKS_DIR / f"conversations_{ts}.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
        print(f"\nResults saved to: {csv_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Toaster 3000 pipeline")
    parser.add_argument("--category", default=None, help="Only benchmark this category (single-phrase mode)")
    parser.add_argument("--conversation", default=None, help="Only benchmark this conversation (multi-turn mode)")
    parser.add_argument("--runs", type=int, default=1, help="Runs per phrase (averaged, single-phrase mode only)")
    parser.add_argument("--model", default=None, help="Override model ID")
    parser.add_argument("--whisper", default="base.en", help="Whisper model size")
    parser.add_argument("--no-agent", action="store_true", help="Skip agent stage (single-phrase mode)")
    parser.add_argument("--no-tts", action="store_true", help="Skip TTS stage (single-phrase mode)")
    parser.add_argument("--conv", action="store_true", help="Run multi-turn conversation benchmarks")
    args = parser.parse_args()

    if args.conv or args.conversation:
        run_conversation_benchmark(args)
    else:
        run_benchmark(args)


if __name__ == "__main__":
    main()
