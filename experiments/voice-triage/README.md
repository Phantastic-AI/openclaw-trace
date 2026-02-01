# Voice Triage for openclaw-trace

Voice-driven review of mined signals using Grok speech-to-speech.

## Setup

```bash
cd experiments/voice-triage
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment

```bash
export XAI_API_KEY="your-xai-key"
```

## Usage

```bash
# Run voice triage on latest rollup
python voice_triage.py --rollup ../../rollup.json

# Or point to a specific daily run
python voice_triage.py --rollup /home/debian/clawd/home/tmp/daily_20260201_123456/rollup.json
```

## Commands (voice)

- "next" / "skip" — move to next signal
- "ticket" / "create ticket" — create Phorge ticket for current signal
- "details" — hear more about the current signal
- "done" / "quit" — exit

## Architecture

```
rollup.json → voice_triage.py → Grok S2S API
                    ↓
              [speak signal]
                    ↓
              [listen command]
                    ↓
              [action: next/ticket/etc]
```
