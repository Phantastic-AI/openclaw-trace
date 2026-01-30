from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


# NOTE: This module is intentionally conservative. False-positives are acceptable;
# false-negatives (PII leaking into mined idea reports) are not.


@dataclass(frozen=True)
class RedactionConfig:
    max_snippet_chars: int = 800


# --- PII / secret patterns ---

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)

# Very rough phone matcher (international + local). Intentionally broad.
_PHONE_RE = re.compile(r"(?:(?<=\D)|^)(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}(?:(?=\D)|$)")

# OpenAI-ish and generic API key prefixes.
_SK_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9]{10,}\b")
_API_KEY_RE = re.compile(r"\bapi-[A-Za-z0-9]{10,}\b", re.I)

# JWTs.
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\b")

# Authorization bearer tokens / long opaque tokens.
_BEARER_RE = re.compile(r"\bBearer\s+[A-Za-z0-9_\-\.]{20,}\b", re.I)

# File paths under /home/<user>/...
_HOME_PATH_RE = re.compile(r"/home/[^\s\n\r\t\0]+")

# URLs with query params: keep scheme+host+path, redact the query.
_URL_WITH_QUERY_RE = re.compile(r"\bhttps?://[^\s\]\)\>\"']+\?[^\s\]\)\>\"']+", re.I)

# Also redact common cloud console signed URLs by heuristic: any URL containing X-Amz or Signature.
_URL_SIGNATURE_RE = re.compile(r"\bhttps?://[^\s\]\)\>\"']*(?:X-Amz-|Signature=|sig=|token=)[^\s\]\)\>\"']*", re.I)


PII_PATTERNS: list[re.Pattern[str]] = [
    _EMAIL_RE,
    _PHONE_RE,
    _SK_KEY_RE,
    _API_KEY_RE,
    _JWT_RE,
    _BEARER_RE,
    _HOME_PATH_RE,
    _URL_WITH_QUERY_RE,
    _URL_SIGNATURE_RE,
]


def _redact_url_query(m: re.Match[str]) -> str:
    s = m.group(0)
    # naive split at first '?'
    pre = s.split("?", 1)[0]
    return pre + "[REDACTED_QUERY]"


def redact_pii(text: str) -> str:
    """Redact PII/secrets from text.

    This function must be run *before* any external LLM call.
    """
    if not text:
        return text

    # Order matters: redact URLs w/ queries first to avoid later partial matches.
    text = _URL_WITH_QUERY_RE.sub(_redact_url_query, text)
    text = _URL_SIGNATURE_RE.sub("[REDACTED_URL]", text)

    text = _EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    text = _PHONE_RE.sub("[REDACTED_PHONE]", text)
    text = _SK_KEY_RE.sub("[REDACTED_API_KEY]", text)
    text = _API_KEY_RE.sub("[REDACTED_API_KEY]", text)
    text = _JWT_RE.sub("[REDACTED_TOKEN]", text)
    text = _BEARER_RE.sub("Bearer [REDACTED_TOKEN]", text)
    text = _HOME_PATH_RE.sub("[REDACTED_HOME_PATH]", text)

    return text


def truncate_snippet(text: str, *, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 20)] + "…[TRUNCATED]"


def contains_pii(text: str) -> bool:
    if not text:
        return False
    return any(p.search(text) for p in PII_PATTERNS)


def drop_pii_lines(markdown: str) -> tuple[str, int]:
    """Drop lines that still match PII patterns. Returns (cleaned, dropped_count)."""
    out_lines: list[str] = []
    dropped = 0
    for line in markdown.splitlines():
        if contains_pii(line):
            dropped += 1
            continue
        out_lines.append(line)
    return "\n".join(out_lines) + ("\n" if markdown.endswith("\n") else ""), dropped


def self_check_redaction() -> None:
    samples: Iterable[tuple[str, str]] = [
        ("email", "contact me at alice@example.com"),
        ("phone", "call +1 (415) 555-1234 tomorrow"),
        ("sk", "OPENAI sk-abcDEF1234567890TOKEN"),
        ("jwt", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.aaaa.bbbb"),
        ("home", "see /home/bob/projects/secret.txt"),
        ("urlq", "visit https://example.com/path?a=1&token=abc"),
        ("bearer", "Authorization: Bearer abcdefghijklmnopqrstuvwxyz0123456789"),
    ]
    for name, s in samples:
        red = redact_pii(s)
        if contains_pii(red):
            raise AssertionError(f"redaction self-check failed for {name}: {red!r}")


if __name__ == "__main__":
    self_check_redaction()
    print("redaction self-check: OK")
