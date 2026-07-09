"""LLM client — OpenAI-compatible interface to DeepSeek."""

from __future__ import annotations

import logging
from time import perf_counter

from openai import OpenAI

from final_agent.runtime_monitoring import get_runtime_monitor
from final_agent.settings import Settings, load_settings

logger = logging.getLogger(__name__)


def _get_client(settings: Settings) -> OpenAI:
    """Create a fresh OpenAI client from settings (no caching — keys may change)."""
    return OpenAI(
        api_key=settings.models_llm.api_key,
        base_url=settings.models_llm.base_url,
    )


def _usage_value(usage: object, name: str) -> int:
    if usage is None:
        return 0
    value = getattr(usage, name, 0)
    return int(value or 0)


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

    started_at = perf_counter()
    if stream:
        response = client.chat.completions.create(**kwargs, stream=True)
        collected: list[str] = []
        for chunk in response:
            delta = chunk.choices[0].delta
            if delta.content:
                collected.append(delta.content)
                print(delta.content, end="", flush=True)
        print()
        get_runtime_monitor().record_model_call(
            provider=settings.models_llm.provider,
            model=kwargs["model"],
            latency_ms=(perf_counter() - started_at) * 1000,
        )
        return "".join(collected)
    else:
        response = client.chat.completions.create(**kwargs)
        usage = getattr(response, "usage", None)
        get_runtime_monitor().record_model_call(
            provider=settings.models_llm.provider,
            model=kwargs["model"],
            latency_ms=(perf_counter() - started_at) * 1000,
            prompt_tokens=_usage_value(usage, "prompt_tokens"),
            completion_tokens=_usage_value(usage, "completion_tokens"),
        )
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
    started_at = perf_counter()

    params = {
        "model": settings.models_llm.model,
        "messages": messages,
        "temperature": settings.models_llm.temperature,
        "max_tokens": settings.models_llm.max_tokens,
        "stream": True,
    }
    params.update(kwargs)

    response = client.chat.completions.create(**params)
    try:
        for chunk in response:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content
    finally:
        get_runtime_monitor().record_model_call(
            provider=settings.models_llm.provider,
            model=params["model"],
            latency_ms=(perf_counter() - started_at) * 1000,
        )
