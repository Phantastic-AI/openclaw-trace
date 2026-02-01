# Voice Triage Web

Browser-based voice triage using Daily + Pipecat.

## Architecture

```
Browser (mic) → Daily WebRTC → Pipecat Bot → Grok (interpret) → OpenAI TTS → Daily → Browser (speaker)
```

## Requirements

Environment variables:
- `DAILY_API_KEY` - Daily.co API key (for rooms)
- `OPENAI_API_KEY` - OpenAI API key (for TTS)
- `XAI_API_KEY` - xAI API key (for Grok command interpretation)
- `DEEPGRAM_API_KEY` - Deepgram API key (optional, for STT)

## Setup

```bash
cd experiments/voice-triage-web
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python server.py
# Serves on http://localhost:8765
```

## Deploy

nginx config at `/etc/nginx/sites-available/voice-triage.phantastic.ai`:

```nginx
server {
    listen 80;
    server_name voice-triage.phantastic.ai;

    location / {
        proxy_pass http://127.0.0.1:8765;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Then:
```bash
sudo ln -s /etc/nginx/sites-available/voice-triage.phantastic.ai /etc/nginx/sites-enabled/
sudo certbot --nginx -d voice-triage.phantastic.ai
sudo systemctl reload nginx
```

## Systemd service

`/etc/systemd/system/voice-triage.service`:

```ini
[Unit]
Description=Voice Triage Web Server
After=network.target

[Service]
Type=simple
User=debian
WorkingDirectory=/home/debian/clawd/home/rlm-session-analyzer/experiments/voice-triage-web
ExecStart=/home/debian/clawd/home/rlm-session-analyzer/experiments/voice-triage-web/.venv/bin/python server.py
Restart=always
Environment=DAILY_API_KEY=...
Environment=OPENAI_API_KEY=...
Environment=XAI_API_KEY=...

[Install]
WantedBy=multi-user.target
```
