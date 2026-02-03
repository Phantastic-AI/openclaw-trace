from __future__ import annotations

import os
from typing import Optional

import httpx


def openai_embeddings(
    texts: list[str],
    *,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout_s: float = 120.0,
    batch_size: int = 128,
) -> list[list[float]]:
    api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    base_url = (base_url or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    model = model or os.environ.get("OPENAI_EMBED_MODEL") or "text-embedding-3-small"

    url = f"{base_url}/embeddings"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    if not texts:
        return []

    out: list[list[float]] = [None] * len(texts)  # type: ignore[list-item]

    with httpx.Client(timeout=timeout_s) as client:
        for start in range(0, len(texts), batch_size):
            chunk = texts[start : start + batch_size]
            payload = {"model": model, "input": chunk}
            r = client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
            for item in data.get("data", []):
                idx = item.get("index")
                if idx is None:
                    continue
                out[start + idx] = item.get("embedding")

    if any(v is None for v in out):
        raise RuntimeError("Embedding response missing vectors")

    return out  # type: ignore[return-value]
