"""LLM client — OpenAI-compatible interface to DeepSeek."""

from __future__ import annotations

import logging
from typing import Optional

from openai import OpenAI

from final_agent.settings import Settings, load_settings

logger = logging.getLogger(__name__)


def _get_client(settings: Settings) -> OpenAI:
    """Create a fresh OpenAI client from settings (no caching — keys may change)."""
    return OpenAI(
        api_key=settings.models_llm.api_key,
        base_url=settings.models_llm.base_url,
    )


def generate(
    messages: list[dict[str, str]],
    settings: Settings | None = None,
    *,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    stream: bool = False,
) -> str:
    """Send a chat completion request to the LLM.

    Args:
        messages: List of {"role": "system"|"user", "content": "..."} dicts.
        settings: Application settings.
        model: Override model name.
        temperature: Override temperature.
        max_tokens: Override max_tokens.
        stream: If True, stream tokens to stdout.

    Returns:
        Full assistant response text.
    """
    if settings is None:
        settings = load_settings()
    client = _get_client(settings)

    kwargs = {
        "model": model or settings.models_llm.model,
        "messages": messages,
        "temperature": temperature if temperature is not None else settings.models_llm.temperature,
        "max_tokens": max_tokens or settings.models_llm.max_tokens,
    }

    if stream:
        response = client.chat.completions.create(**kwargs, stream=True)
        collected: list[str] = []
        for chunk in response:
            delta = chunk.choices[0].delta
            if delta.content:
                collected.append(delta.content)
                print(delta.content, end="", flush=True)
        print()
        return "".join(collected)
    else:
        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""


def generate_stream(
    messages: list[dict[str, str]],
    settings: Settings | None = None,
    **kwargs,
):
    """Generator yielding text chunks from a streaming LLM response."""
    if settings is None:
        settings = load_settings()
    client = _get_client(settings)

    params = {
        "model": settings.models_llm.model,
        "messages": messages,
        "temperature": settings.models_llm.temperature,
        "max_tokens": settings.models_llm.max_tokens,
        "stream": True,
    }
    params.update(kwargs)

    response = client.chat.completions.create(**params)
    for chunk in response:
        delta = chunk.choices[0].delta
        if delta.content:
            yield delta.content
