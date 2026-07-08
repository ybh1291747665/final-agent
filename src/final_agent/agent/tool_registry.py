from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from pydantic import BaseModel, ValidationError

from final_agent.agent.models import ToolCall, ToolResult
from final_agent.agent.roles import AgentRole


@dataclass(frozen=True)
class ToolSpec:
    name: str
    input_model: type[BaseModel]
    operation: Callable[[Any], Any]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def execute(self, role: AgentRole, call: ToolCall, *, allowed_tools: list[str]) -> ToolResult:
        started = perf_counter()
        if call.name not in allowed_tools:
            return ToolResult(
                ok=False,
                error=f"Tool '{call.name}' is not allowed for role '{role.value}'",
                elapsed_ms=int((perf_counter() - started) * 1000),
            )
        spec = self._tools.get(call.name)
        if spec is None:
            return ToolResult(
                ok=False,
                error=f"Unknown tool '{call.name}'",
                elapsed_ms=int((perf_counter() - started) * 1000),
            )
        try:
            payload = spec.input_model.model_validate(call.arguments)
            value = spec.operation(payload)
            return ToolResult(ok=True, value=value, elapsed_ms=int((perf_counter() - started) * 1000))
        except ValidationError as exc:
            return ToolResult(
                ok=False,
                error=f"Validation error: {exc}",
                elapsed_ms=int((perf_counter() - started) * 1000),
            )
        except (RuntimeError, ValueError, TimeoutError) as exc:
            return ToolResult(ok=False, error=str(exc), elapsed_ms=int((perf_counter() - started) * 1000))
