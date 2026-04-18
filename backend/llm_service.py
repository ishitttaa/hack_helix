"""
PromptGuard — LLM Service
Wraps OpenAI chat completions.  Falls back to mock mode if no API key is set.
"""

import os
import random
from typing import AsyncGenerator

from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY  = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL    = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
SYSTEM_PROMPT   = os.getenv(
    "LLM_SYSTEM_PROMPT",
    "You are a helpful, safe, and concise AI assistant. Answer clearly and factually.",
)
MAX_TOKENS      = int(os.getenv("LLM_MAX_TOKENS", "512"))

# ── Mock fallback ─────────────────────────────────────────────────────────────
_MOCK_RESPONSES = [
    "That's a great question! Here's what I know about that topic…",
    "I'd be happy to help with that. Let me explain step by step.",
    "Based on my knowledge, the answer involves several key factors.",
    "Great question! The main thing to understand here is…",
    "Here's a helpful breakdown of what you're asking about.",
]


def _mock_llm(prompt: str) -> str:
    base = random.choice(_MOCK_RESPONSES)
    snippet = prompt[:60] + "…" if len(prompt) > 60 else prompt
    return f"{base} (Responding to: '{snippet}')"


def is_openai_available() -> bool:
    """Return True when a real API key is configured."""
    return bool(OPENAI_API_KEY and OPENAI_API_KEY != "sk-...")


# ── Sync helper (used by /chat route) ────────────────────────────────────────

async def call_llm(prompt: str, use_real: bool = True) -> tuple[str, str]:
    """
    Returns (response_text, model_label).
    model_label is one of: 'openai:<model>', 'mock'.
    """
    if use_real and is_openai_available():
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        resp = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            max_tokens=MAX_TOKENS,
            temperature=0.7,
        )
        text = resp.choices[0].message.content or ""
        return text.strip(), f"openai:{OPENAI_MODEL}"

    # Fall back to mock
    return _mock_llm(prompt), "mock"


# ── Streaming helper (used by /chat/stream SSE route) ────────────────────────

async def stream_llm(prompt: str) -> AsyncGenerator[str, None]:
    """
    Async generator that yields text chunks from OpenAI streaming.
    Falls back to yielding the full mock string at once.
    """
    if is_openai_available():
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        stream = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            max_tokens=MAX_TOKENS,
            temperature=0.7,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
    else:
        yield _mock_llm(prompt)
