from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional

import httpx


@dataclass
class LLMResponse:
    text: str
    raw: Any | None = None


class LLMClient:
    def complete(self, *, system: str, user: str, temperature: float = 0.0) -> LLMResponse:
        raise NotImplementedError


class OpenAICompatClient(LLMClient):
    """Minimal OpenAI-compatible chat.completions client.

    Works with OpenAI or any compatible endpoint.

    Env vars:
      - OPENAI_API_KEY (required)
      - OPENAI_BASE_URL (optional; default https://api.openai.com/v1)
      - OPENAI_MODEL (optional; default gpt-4.1-mini)
    """

    def __init__(self, *, api_key: Optional[str] = None, base_url: Optional[str] = None, model: Optional[str] = None, timeout_s: float = 120.0):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.model = model or os.environ.get("OPENAI_MODEL") or "gpt-4.1-mini"
        self.timeout_s = timeout_s

    def complete(self, *, system: str, user: str, temperature: float = 0.0) -> LLMResponse:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self.timeout_s) as client:
            r = client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
        text = data["choices"][0]["message"]["content"]
        return LLMResponse(text=text, raw=data)


class NoLLMClient(LLMClient):
    """Deterministic fallback that returns an empty program stub.

    Useful for running the CLI without API keys.
    """

    def complete(self, *, system: str, user: str, temperature: float = 0.0) -> LLMResponse:
        stub = """# NoLLMClient active. Provide your own analyzer program in --program.
# Expected to set: FINAL (str) and optionally PHASES (list[dict])
FINAL = "No LLM configured. Re-run with OPENAI_API_KEY or pass --program."\
"""
        return LLMResponse(text=stub)
