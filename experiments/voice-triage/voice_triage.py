#!/usr/bin/env python3
"""
Voice triage for openclaw-trace signals.

Uses:
- Grok (xAI) for understanding and conversation
- OpenAI for TTS/STT (xAI doesn't have audio endpoints yet)
"""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from openai import OpenAI


def get_grok_client():
    """Get xAI/Grok client."""
    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        print("Warning: XAI_API_KEY not set, using OpenAI for everything")
        return None
    
    return OpenAI(
        api_key=api_key,
        base_url="https://api.x.ai/v1"
    )


def get_openai_client():
    """Get OpenAI client for TTS/STT."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def load_rollup(path: str) -> list:
    """Load rollup.json and return clusters."""
    with open(path) as f:
        data = json.load(f)
    
    # Handle both formats
    return data.get("rollups", data.get("clusters", []))


def speak(client: OpenAI, text: str, voice: str = "nova"):
    """Speak text using OpenAI TTS."""
    if not client:
        print(f"🔊 {text}")
        return
    
    try:
        # Try audio
        import sounddevice as sd
        import soundfile as sf
        
        response = client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text
        )
        
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(response.content)
            temp_path = f.name
        
        data, samplerate = sf.read(temp_path)
        sd.play(data, samplerate)
        sd.wait()
        os.unlink(temp_path)
        
    except ImportError:
        print(f"🔊 {text}")
    except Exception as e:
        print(f"🔊 {text}")
        print(f"   (audio error: {e})")


def listen(client: OpenAI, duration: float = 5.0) -> str:
    """Listen using OpenAI Whisper."""
    if not client:
        return input("🎤 > ")
    
    try:
        import sounddevice as sd
        import soundfile as sf
        
        print("🎤 Listening...")
        samplerate = 16000
        recording = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, dtype='float32')
        sd.wait()
        
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            sf.write(f.name, recording, samplerate)
            temp_path = f.name
        
        with open(temp_path, "rb") as f:
            transcript = client.audio.transcriptions.create(model="whisper-1", file=f)
        
        os.unlink(temp_path)
        result = transcript.text.strip().lower()
        print(f"   heard: {result}")
        return result
        
    except ImportError:
        return input("🎤 > ")
    except Exception as e:
        print(f"   (listen error: {e})")
        return input("🎤 > ")


def interpret_command(grok: OpenAI, user_input: str) -> str:
    """Use Grok to interpret fuzzy voice commands."""
    if not grok:
        # Simple keyword matching fallback
        user_input = user_input.lower()
        if any(w in user_input for w in ["quit", "done", "exit", "stop"]):
            return "quit"
        if any(w in user_input for w in ["ticket", "create", "file", "bug"]):
            return "ticket"
        if any(w in user_input for w in ["detail", "more", "explain", "what"]):
            return "details"
        if any(w in user_input for w in ["skip", "next", "pass", ""]):
            return "next"
        return "unknown"
    
    response = grok.chat.completions.create(
        model="grok-3-mini",
        messages=[
            {"role": "system", "content": """You are a command interpreter for a voice triage system.
Given user speech, classify it into exactly one of these commands:
- "next" (skip, move on, pass, continue)
- "ticket" (create ticket, file bug, log it, track it)
- "details" (tell me more, explain, what happened, examples)
- "quit" (done, stop, exit, finished)
- "unknown" (unclear command)

Respond with just the command word, nothing else."""},
            {"role": "user", "content": user_input}
        ],
        temperature=0
    )
    
    return response.choices[0].message.content.strip().lower()


def format_signal(cluster: dict) -> str:
    """Format cluster for speaking."""
    # Handle different rollup formats
    sig_text = cluster.get("signature_text", "")
    parts = sig_text.split("|") if sig_text else []
    
    kind = parts[0] if parts else cluster.get("kind", "issue")
    title = parts[1][:60] if len(parts) > 1 else cluster.get("title", "Unknown")
    title = title.replace("_", " ").replace("|", ", ")
    
    count = cluster.get("count_items", cluster.get("count", 1))
    tier = cluster.get("tier", cluster.get("priority", "?"))
    
    return f"Tier {tier} {kind}: {title}. {count} occurrences."


def format_details(cluster: dict) -> str:
    """Get more details about a cluster."""
    tags = cluster.get("tags_top", [])[:5]
    tag_str = ", ".join(t[0] for t in tags if isinstance(t, list))
    
    severity = cluster.get("max_severity", "unknown")
    reasons = cluster.get("tier_reasons", [])
    
    return f"Severity: {severity}. Tags: {tag_str}. Tier reasons: {', '.join(reasons) if reasons else 'none'}."


def create_ticket(cluster: dict) -> str:
    """Create Phorge ticket."""
    sig_text = cluster.get("signature_text", "Unknown signal")
    fingerprint = cluster.get("signature_id", "")[:20]
    
    ticket = {
        "title": f"[openclaw-trace] {sig_text[:60]}",
        "description": f"**Auto-triaged via voice**\n\nSignature: `{fingerprint}`\n\nTier: {cluster.get('tier')}\nCount: {cluster.get('count_items', 1)}",
        "priority": 80 if cluster.get("tier") == 1 else 50
    }
    
    try:
        import subprocess
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(ticket, f)
            temp_path = f.name
        
        result = subprocess.run(
            ["sudo", "/srv/phorge/phorge/bin/conduit", "call", "--local",
             "--method", "maniphest.createtask", "--as", "admin", "--input", temp_path],
            capture_output=True, text=True
        )
        os.unlink(temp_path)
        
        if result.returncode == 0:
            resp = json.loads(result.stdout)
            task_id = resp.get("result", {}).get("id")
            return f"Created T{task_id}"
        return f"Failed: {result.stderr[:50]}"
        
    except Exception as e:
        return f"Error: {e}"


def run_triage(rollup_path: str, text_only: bool = False):
    """Main triage loop."""
    grok = get_grok_client()
    openai_client = get_openai_client() if not text_only else None
    
    clusters = load_rollup(rollup_path)
    if not clusters:
        print("No clusters found.")
        return
    
    print(f"\n📋 Loaded {len(clusters)} signals from {rollup_path}\n")
    speak(openai_client, f"Starting triage. {len(clusters)} issues to review.")
    
    i = 0
    created = 0
    while i < len(clusters):
        cluster = clusters[i]
        print(f"\n[{i+1}/{len(clusters)}] ", end="")
        
        # Speak the signal
        signal_text = format_signal(cluster)
        speak(openai_client, signal_text)
        
        # Get command
        if text_only:
            user_input = input("\n[next/ticket/details/quit] > ")
        else:
            user_input = listen(openai_client)
        
        cmd = interpret_command(grok, user_input)
        print(f"   → {cmd}")
        
        if cmd == "quit":
            break
        elif cmd == "ticket":
            result = create_ticket(cluster)
            speak(openai_client, result)
            created += 1
            i += 1
        elif cmd == "details":
            details = format_details(cluster)
            speak(openai_client, details)
        elif cmd == "next":
            i += 1
        else:
            speak(openai_client, "Say: next, ticket, details, or quit.")
    
    summary = f"Done. Reviewed {i} of {len(clusters)}. Created {created} tickets."
    print(f"\n{summary}")
    speak(openai_client, summary)


def main():
    parser = argparse.ArgumentParser(description="Voice triage for openclaw-trace")
    parser.add_argument("--rollup", "-r", required=True, help="Path to rollup.json")
    parser.add_argument("--text-only", "-t", action="store_true", help="Text mode (no audio)")
    args = parser.parse_args()
    
    if not Path(args.rollup).exists():
        print(f"Error: {args.rollup} not found")
        sys.exit(1)
    
    run_triage(args.rollup, text_only=args.text_only)


if __name__ == "__main__":
    main()
