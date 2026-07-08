from __future__ import annotations

from pydantic import BaseModel


class EchoInput(BaseModel):
    text: str


def test_tool_registry_executes_allowed_tool():
    from final_agent.agent.models import ToolCall
    from final_agent.agent.roles import AgentRole
    from final_agent.agent.tool_registry import ToolRegistry, ToolSpec

    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="echo",
            input_model=EchoInput,
            operation=lambda payload: payload.text.upper(),
        )
    )

    result = registry.execute(AgentRole.RETRIEVAL, ToolCall(name="echo", arguments={"text": "ci"}), allowed_tools=["echo"])

    assert result.ok is True
    assert result.value == "CI"


def test_tool_registry_rejects_unauthorized_tool():
    from final_agent.agent.models import ToolCall
    from final_agent.agent.roles import AgentRole
    from final_agent.agent.tool_registry import ToolRegistry, ToolSpec

    registry = ToolRegistry()
    registry.register(ToolSpec(name="echo", input_model=EchoInput, operation=lambda payload: payload.text))

    result = registry.execute(AgentRole.SUPERVISOR, ToolCall(name="echo", arguments={"text": "ci"}), allowed_tools=[])

    assert result.ok is False
    assert "not allowed" in result.error


def test_tool_registry_rejects_invalid_arguments():
    from final_agent.agent.models import ToolCall
    from final_agent.agent.roles import AgentRole
    from final_agent.agent.tool_registry import ToolRegistry, ToolSpec

    registry = ToolRegistry()
    registry.register(ToolSpec(name="echo", input_model=EchoInput, operation=lambda payload: payload.text))

    result = registry.execute(AgentRole.RETRIEVAL, ToolCall(name="echo", arguments={}), allowed_tools=["echo"])

    assert result.ok is False
    assert "validation" in result.error.lower()
