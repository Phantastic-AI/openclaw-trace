#!/usr/bin/env python3
"""
Voice Triage MVP for openclaw-trace signals.
Uses OpenAI for TTS/STT and Grok for command understanding.

Flow:
1. Load rollup.json
2. Read top signals via OpenAI TTS
3. Voice commands: "next", "create ticket", "skip", "mark resolved"
4. Loop until done

Requirements: pip install openai sounddevice soundfile numpy
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

from openai import OpenAI

# Audio deps are optional (for headless mode)
try:
    import sounddevice as sd
    import soundfile as sf
    import numpy as np
    AUDIO_AVAILABLE = True
except (ImportError, OSError) as e:
    AUDIO_AVAILABLE = False
    sd = sf = np = None
    print(f"Note: Audio disabled ({e}). Use --cli or --export mode.")

# Load API keys
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
XAI_API_KEY = os.environ.get("XAI_API_KEY")

env_file = Path.home() / ".env-voice-triage"
if env_file.exists():
    for line in env_file.read_text().strip().split("\n"):
        if line.startswith("XAI_API_KEY=") and not XAI_API_KEY:
            XAI_API_KEY = line.split("=", 1)[1]
        if line.startswith("OPENAI_API_KEY=") and not OPENAI_API_KEY:
            OPENAI_API_KEY = line.split("=", 1)[1]

if not OPENAI_API_KEY:
    print("Error: OPENAI_API_KEY not found (needed for TTS/STT)")
    sys.exit(1)

# Initialize clients
openai_client = OpenAI(api_key=OPENAI_API_KEY)
grok_client = OpenAI(api_key=XAI_API_KEY, base_url="https://api.x.ai/v1") if XAI_API_KEY else None

ROLLUP_PATH = Path(__file__).parent / "rollup.json"
SAMPLE_RATE = 24000


def load_signals():
    """Load signals from rollup.json, sorted by tier then score."""
    if not ROLLUP_PATH.exists():
        print(f"Error: {ROLLUP_PATH} not found")
        sys.exit(1)
    
    with open(ROLLUP_PATH) as f:
        data = json.load(f)
    
    rollups = data.get("rollups", [])
    # Sort: tier ascending, score descending
    rollups.sort(key=lambda x: (x.get("tier", 99), -x.get("score", 0)))
    return rollups


def text_to_speech(text: str) -> Optional[bytes]:
    """Convert text to speech using OpenAI TTS."""
    try:
        response = openai_client.audio.speech.create(
            model="tts-1",
            voice="onyx",  # Deep, authoritative voice
            input=text,
            response_format="wav"
        )
        return response.content
    except Exception as e:
        print(f"TTS Error: {e}")
        return None


def play_audio(audio_bytes: bytes):
    """Play audio bytes through speakers."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio_bytes)
        f.flush()
        try:
            data, samplerate = sf.read(f.name)
            sd.play(data, samplerate)
            sd.wait()
        finally:
            os.unlink(f.name)


def record_audio(duration: float = 3.0):
    """Record audio from microphone."""
    print(f"🎤 Listening for {duration}s...")
    recording = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype=np.float32
    )
    sd.wait()
    return recording


def speech_to_text(audio) -> Optional[str]:
    """Convert speech to text using OpenAI Whisper."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        sf.write(f.name, audio, SAMPLE_RATE)
        try:
            with open(f.name, "rb") as audio_file:
                response = openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file
                )
                return response.text.strip().lower()
        except Exception as e:
            print(f"STT Error: {e}")
            return None
        finally:
            os.unlink(f.name)


def smart_parse_command(text: str, signal: dict) -> str:
    """Use Grok to understand complex voice commands."""
    if not grok_client or not text:
        return parse_command(text)
    
    try:
        response = grok_client.chat.completions.create(
            model="grok-3-mini",
            messages=[
                {"role": "system", "content": """You are a voice command parser for a signal triage system.
Parse the user's voice command into one of these actions:
- next: move to next signal (includes "skip", "continue", "pass", "okay")
- ticket: create a ticket for this signal (includes "file bug", "report", "create issue")
- resolve: mark signal as resolved (includes "fixed", "done", "close", "ignore")
- repeat: repeat the current signal
- stop: end the session (includes "quit", "exit", "end")
- unknown: couldn't understand

Respond with ONLY the action word, nothing else."""},
                {"role": "user", "content": f"Command: {text}"}
            ],
            max_tokens=10
        )
        action = response.choices[0].message.content.strip().lower()
        if action in ["next", "ticket", "resolve", "repeat", "stop"]:
            return action
        return "unknown"
    except Exception as e:
        print(f"Grok parse error: {e}")
        return parse_command(text)  # Fall back to simple parsing


def format_signal_for_speech(signal: dict) -> str:
    """Format a signal for TTS readout."""
    tier = signal.get("tier", "?")
    summary = signal.get("canonical_summary", "No summary")
    severity = signal.get("max_severity", "unknown")
    kind = list(signal.get("kind_v2_counts", {}).keys())
    kind_str = kind[0] if kind else "unknown"
    
    return f"Tier {tier} {kind_str}. Severity: {severity}. {summary}"


def parse_command(text: Optional[str]) -> str:
    """Parse voice command into action."""
    if not text:
        return "unknown"
    
    text = text.lower().strip()
    
    if any(w in text for w in ["next", "skip", "continue", "pass"]):
        return "next"
    if any(w in text for w in ["ticket", "create", "file", "report"]):
        return "ticket"
    if any(w in text for w in ["resolve", "done", "fixed", "close"]):
        return "resolve"
    if any(w in text for w in ["stop", "quit", "exit", "end"]):
        return "stop"
    if any(w in text for w in ["repeat", "again", "what"]):
        return "repeat"
    
    return "unknown"


def speak(text: str):
    """Speak text aloud."""
    print(f"🔊 {text}")
    audio = text_to_speech(text)
    if audio:
        play_audio(audio)
    else:
        print("(TTS unavailable - text only)")


def main():
    """Main voice triage loop."""
    if not AUDIO_AVAILABLE:
        print("Audio not available. Use --cli or --export mode.")
        sys.exit(1)
    
    print("=" * 60)
    print("Voice Triage for openclaw-trace")
    print("Commands: next | ticket | resolve | repeat | stop")
    print("=" * 60)
    
    signals = load_signals()
    print(f"Loaded {len(signals)} signals from {ROLLUP_PATH}")
    
    if not signals:
        print("No signals to review.")
        return
    
    # Stats
    reviewed = 0
    tickets_created = 0
    resolved = 0
    
    for i, signal in enumerate(signals):
        sig_id = signal.get("signature_id", "unknown")[:20]
        print(f"\n--- Signal {i+1}/{len(signals)} [{sig_id}...] ---")
        
        speech_text = format_signal_for_speech(signal)
        speak(speech_text)
        
        while True:
            # Get command (voice or keyboard fallback)
            try:
                audio = record_audio(3.0)
                command_text = speech_to_text(audio)
                print(f"Heard: '{command_text}'")
            except Exception as e:
                print(f"Audio input error: {e}")
                command_text = input("Command (next/ticket/resolve/repeat/stop): ").strip()
            
            command = smart_parse_command(command_text, signal) if grok_client else parse_command(command_text)
            
            if command == "next":
                speak("Moving to next signal.")
                reviewed += 1
                break
            
            elif command == "ticket":
                speak("Creating ticket. This would call Phorge API.")
                # TODO: Actually create Phorge ticket
                print(f"  [Would create ticket for: {signal.get('canonical_summary', 'N/A')}]")
                tickets_created += 1
                reviewed += 1
                break
            
            elif command == "resolve":
                speak("Marked as resolved.")
                resolved += 1
                reviewed += 1
                break
            
            elif command == "repeat":
                speak(speech_text)
            
            elif command == "stop":
                speak("Stopping triage session.")
                print(f"\n--- Session Summary ---")
                print(f"Reviewed: {reviewed}")
                print(f"Tickets: {tickets_created}")
                print(f"Resolved: {resolved}")
                return
            
            else:
                speak("Unknown command. Say next, ticket, resolve, repeat, or stop.")
    
    speak("All signals reviewed.")
    print(f"\n--- Session Summary ---")
    print(f"Reviewed: {reviewed}")
    print(f"Tickets: {tickets_created}")
    print(f"Resolved: {resolved}")


def cli_mode():
    """CLI-only mode without audio (for headless servers)."""
    print("=" * 60)
    print("Voice Triage CLI Mode (no audio)")
    print("Commands: n=next | t=ticket | r=resolve | p=repeat | q=stop")
    print("=" * 60)
    
    signals = load_signals()
    print(f"Loaded {len(signals)} signals")
    
    reviewed = 0
    tickets_created = 0
    resolved = 0
    
    for i, signal in enumerate(signals):
        print(f"\n--- Signal {i+1}/{len(signals)} ---")
        speech_text = format_signal_for_speech(signal)
        print(f"📢 {speech_text}")
        
        while True:
            cmd = input("\n> ").strip().lower()
            
            if cmd in ["n", "next", "skip"]:
                reviewed += 1
                break
            elif cmd in ["t", "ticket", "create"]:
                print(f"  [TICKET] {signal.get('canonical_summary', 'N/A')}")
                tickets_created += 1
                reviewed += 1
                break
            elif cmd in ["r", "resolve", "done"]:
                resolved += 1
                reviewed += 1
                break
            elif cmd in ["p", "repeat"]:
                print(f"📢 {speech_text}")
            elif cmd in ["q", "quit", "stop"]:
                print(f"\n--- Summary: {reviewed} reviewed, {tickets_created} tickets, {resolved} resolved ---")
                return
            else:
                print("Unknown. Use: n(ext), t(icket), r(esolve), p(repeat), q(uit)")
    
    print(f"\n--- Summary: {reviewed} reviewed, {tickets_created} tickets, {resolved} resolved ---")


def export_audio():
    """Export all signals as audio files for later playback."""
    signals = load_signals()
    output_dir = Path(__file__).parent / "triage_audio"
    output_dir.mkdir(exist_ok=True)
    
    print(f"Exporting {len(signals)} signals to {output_dir}")
    
    for i, signal in enumerate(signals):
        speech_text = format_signal_for_speech(signal)
        print(f"  [{i+1}/{len(signals)}] {speech_text[:50]}...")
        
        audio = text_to_speech(speech_text)
        if audio:
            outfile = output_dir / f"signal_{i+1:02d}_tier{signal.get('tier', 0)}.wav"
            with open(outfile, "wb") as f:
                f.write(audio)
    
    print(f"✓ Exported to {output_dir}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Voice triage for openclaw-trace signals")
    parser.add_argument("--cli", action="store_true", help="CLI mode (no audio)")
    parser.add_argument("--export", action="store_true", help="Export signals as audio files")
    args = parser.parse_args()
    
    if args.cli:
        cli_mode()
    elif args.export:
        export_audio()
    else:
        main()
