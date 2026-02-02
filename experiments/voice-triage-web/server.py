#!/usr/bin/env python3
import time
"""
Voice Triage Web Server - Daily + Pipecat

Creates Daily rooms and spawns Pipecat bots for voice triage sessions.
"""

import os
import json
import asyncio
import aiohttp
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from bot import run_bot

DAILY_API_KEY = os.environ.get("DAILY_API_KEY")
DAILY_API_URL = "https://api.daily.co/v1"

# Load rollup data
ROLLUP_PATH = Path(__file__).parent.parent.parent / "rollup.json"


def load_rollup():
    """Load signal clusters from rollup.json."""
    if not ROLLUP_PATH.exists():
        return []
    with open(ROLLUP_PATH) as f:
        data = json.load(f)
    return data.get("rollups", data.get("clusters", []))


async def create_daily_room() -> dict:
    """Create a temporary Daily room."""
    if not DAILY_API_KEY:
        raise HTTPException(status_code=500, detail="DAILY_API_KEY not set")
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{DAILY_API_URL}/rooms",
            headers={"Authorization": f"Bearer {DAILY_API_KEY}"},
            json={
                "properties": {
                    "exp": int(int(time.time())) + 3600,  # 1 hour
                    "enable_chat": False,
                    "enable_knocking": False,
                    "start_video_off": True,
                    "start_audio_off": False,
                }
            }
        ) as resp:
            if resp.status != 200:
                error = await resp.text()
                raise HTTPException(status_code=resp.status, detail=f"Daily API error: {error}")
            return await resp.json()


async def get_bot_token(room_name: str) -> str:
    """Get an owner token for the bot."""
    if not DAILY_API_KEY:
        raise HTTPException(status_code=500, detail="DAILY_API_KEY not set")
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{DAILY_API_URL}/meeting-tokens",
            headers={"Authorization": f"Bearer {DAILY_API_KEY}"},
            json={
                "properties": {
                    "room_name": room_name,
                    "is_owner": True,
                    "exp": int(time.time()) + 3600,
                }
            }
        ) as resp:
            if resp.status != 200:
                error = await resp.text()
                raise HTTPException(status_code=resp.status, detail=f"Daily API error: {error}")
            data = await resp.json()
            return data["token"]


async def get_daily_token(room_name: str) -> str:
    """Get a meeting token for the room."""
    if not DAILY_API_KEY:
        raise HTTPException(status_code=500, detail="DAILY_API_KEY not set")
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{DAILY_API_URL}/meeting-tokens",
            headers={"Authorization": f"Bearer {DAILY_API_KEY}"},
            json={
                "properties": {
                    "room_name": room_name,
                    "is_owner": False,
                    "exp": int(int(time.time())) + 3600,
                }
            }
        ) as resp:
            if resp.status != 200:
                error = await resp.text()
                raise HTTPException(status_code=resp.status, detail=f"Daily API error: {error}")
            data = await resp.json()
            return data["token"]


# Store active bot tasks
bot_tasks: dict[str, asyncio.Task] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown."""
    print("Voice Triage server starting...")
    yield
    # Cancel all bot tasks on shutdown
    for task in bot_tasks.values():
        task.cancel()
    print("Voice Triage server stopped.")


app = FastAPI(title="Voice Triage", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main page."""
    clusters = load_rollup()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "cluster_count": len(clusters),
    })


@app.post("/api/start-session")
async def start_session():
    """Create a room and start the bot."""
    # Create Daily room
    room = await create_daily_room()
    room_url = room["url"]
    room_name = room["name"]
    
    # Get token for user
    user_token = await get_daily_token(room_name)
    
    # Load clusters
    clusters = load_rollup()
    
    # Get bot token (owner)
    bot_token = await get_bot_token(room_name)
    
    # Start bot in background
    task = asyncio.create_task(run_bot(room_url, bot_token, clusters))
    bot_tasks[room_name] = task
    
    return JSONResponse({
        "room_url": room_url,
        "token": user_token,
        "cluster_count": len(clusters),
    })


@app.get("/api/clusters")
async def get_clusters():
    """Get current clusters."""
    clusters = load_rollup()
    return JSONResponse({
        "count": len(clusters),
        "clusters": clusters[:20],  # Limit for preview
    })


@app.get("/health")
async def health():
    return {"status": "ok", "daily_configured": bool(DAILY_API_KEY)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)
