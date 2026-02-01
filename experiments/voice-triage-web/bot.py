#!/usr/bin/env python3
"""
Pipecat bot for voice triage.

Joins a Daily room and conducts voice-based signal triage.
"""

import os
import json
import asyncio
import tempfile
import subprocess
from typing import Optional

from pipecat.frames.frames import (
    Frame,
    TextFrame,
    EndFrame,
    LLMMessagesFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.processors.aggregators.llm_response import LLMAssistantResponseAggregator, LLMUserResponseAggregator
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.services.openai.tts import OpenAITTSService
from pipecat.services.openai.stt import OpenAISTTService
from pipecat.transports.daily.transport import DailyTransport, DailyParams
from pipecat.audio.vad.silero import SileroVADAnalyzer

# xAI/Grok for understanding (OpenAI-compatible)
from openai import OpenAI as OpenAIClient


class TriageState:
    """Track triage session state."""
    def __init__(self, clusters: list):
        self.clusters = clusters
        self.current_idx = 0
        self.tickets_created = 0
        self.done = False
    
    @property
    def current(self) -> Optional[dict]:
        if self.current_idx < len(self.clusters):
            return self.clusters[self.current_idx]
        return None
    
    def next(self):
        self.current_idx += 1
        if self.current_idx >= len(self.clusters):
            self.done = True
    
    def format_current(self) -> str:
        c = self.current
        if not c:
            return "No more signals to review."
        
        sig_text = c.get("signature_text", "")
        parts = sig_text.split("|") if sig_text else []
        kind = parts[0] if parts else c.get("kind", "issue")
        title = parts[1][:50] if len(parts) > 1 else c.get("title", "Unknown")
        title = title.replace("_", " ")
        count = c.get("count_items", 1)
        tier = c.get("tier", "?")
        
        return f"Signal {self.current_idx + 1} of {len(self.clusters)}. Tier {tier} {kind}: {title}. {count} occurrences."
    
    def format_details(self) -> str:
        c = self.current
        if not c:
            return "No signal selected."
        
        tags = c.get("tags_top", [])[:5]
        tag_str = ", ".join(t[0] for t in tags if isinstance(t, list))
        severity = c.get("max_severity", "unknown")
        return f"Severity: {severity}. Tags: {tag_str}."


def create_ticket(cluster: dict) -> str:
    """Create a Phorge ticket."""
    sig_text = cluster.get("signature_text", "Unknown signal")
    fingerprint = cluster.get("signature_id", "")[:20]
    
    ticket = {
        "title": f"[voice-triage] {sig_text[:60]}",
        "description": f"**Created via voice triage**\n\nSignature: `{fingerprint}`\nTier: {cluster.get('tier')}",
        "priority": 80 if cluster.get("tier") == 1 else 50
    }
    
    try:
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
            return f"T{task_id}"
        return None
    except Exception as e:
        print(f"Ticket error: {e}")
        return None


class TriageProcessor(FrameProcessor):
    """Process user input and manage triage flow."""
    
    def __init__(self, state: TriageState):
        super().__init__()
        self.state = state
        self.grok = OpenAIClient(
            api_key=os.environ.get("XAI_API_KEY"),
            base_url="https://api.x.ai/v1"
        ) if os.environ.get("XAI_API_KEY") else None
    
    def interpret_command(self, text: str) -> str:
        """Use Grok to interpret command."""
        text = text.lower().strip()
        
        if not self.grok:
            # Keyword fallback
            if any(w in text for w in ["quit", "done", "exit", "stop", "finish"]):
                return "quit"
            if any(w in text for w in ["ticket", "create", "file", "bug", "track"]):
                return "ticket"
            if any(w in text for w in ["detail", "more", "explain", "what"]):
                return "details"
            if any(w in text for w in ["skip", "next", "pass", "continue"]):
                return "next"
            return "unknown"
        
        try:
            response = self.grok.chat.completions.create(
                model="grok-3-mini",
                messages=[
                    {"role": "system", "content": """Classify into: next, ticket, details, quit, or unknown.
Just respond with the command word."""},
                    {"role": "user", "content": text}
                ],
                temperature=0,
                max_tokens=10
            )
            return response.choices[0].message.content.strip().lower()
        except:
            return "unknown"
    
    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        
        if isinstance(frame, TextFrame) and direction == FrameDirection.UPSTREAM:
            # User said something
            user_text = frame.text
            cmd = self.interpret_command(user_text)
            
            if cmd == "quit":
                self.state.done = True
                response = f"Ending session. Reviewed {self.state.current_idx} signals, created {self.state.tickets_created} tickets. Goodbye!"
                await self.push_frame(TextFrame(text=response))
                await self.push_frame(EndFrame())
            
            elif cmd == "ticket":
                if self.state.current:
                    task_id = create_ticket(self.state.current)
                    if task_id:
                        self.state.tickets_created += 1
                        response = f"Created ticket {task_id}. "
                    else:
                        response = "Failed to create ticket. "
                    self.state.next()
                    if not self.state.done:
                        response += self.state.format_current()
                    else:
                        response += f"That was the last signal. Created {self.state.tickets_created} tickets total."
                    await self.push_frame(TextFrame(text=response))
            
            elif cmd == "details":
                response = self.state.format_details()
                await self.push_frame(TextFrame(text=response))
            
            elif cmd == "next":
                self.state.next()
                if not self.state.done:
                    response = self.state.format_current()
                else:
                    response = f"No more signals. Created {self.state.tickets_created} tickets. Say quit to end."
                await self.push_frame(TextFrame(text=response))
            
            else:
                await self.push_frame(TextFrame(text="Say next, ticket, details, or quit."))
        
        else:
            await self.push_frame(frame, direction)


async def run_bot(room_url: str, clusters: list):
    """Run the Pipecat bot in a Daily room."""
    
    state = TriageState(clusters)
    
    # Daily transport
    transport = DailyTransport(
        room_url,
        None,  # No token needed for bot
        "Triage Bot",
        DailyParams(
            audio_out_enabled=True,
            audio_in_enabled=True,
            vad_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
        )
    )
    
    # STT (OpenAI Whisper)
    stt = OpenAISTTService(
        api_key=os.environ.get("OPENAI_API_KEY"),
    )
    
    # TTS (OpenAI)
    tts = OpenAITTSService(
        api_key=os.environ.get("OPENAI_API_KEY"),
        voice="nova"
    )
    
    # Our triage processor
    triage = TriageProcessor(state)
    
    # Build pipeline
    pipeline = Pipeline([
        transport.input(),
        stt,
        triage,
        tts,
        transport.output(),
    ])
    
    task = PipelineTask(pipeline, PipelineParams(allow_interruptions=True))
    
    @transport.event_handler("on_first_participant_joined")
    async def on_first_participant(transport, participant):
        # Greet and start
        greeting = f"Welcome to voice triage. You have {len(clusters)} signals to review. " + state.format_current()
        await task.queue_frame(TextFrame(text=greeting))
    
    @transport.event_handler("on_participant_left")
    async def on_participant_left(transport, participant, reason):
        await task.queue_frame(EndFrame())
    
    runner = PipelineRunner()
    await runner.run(task)
