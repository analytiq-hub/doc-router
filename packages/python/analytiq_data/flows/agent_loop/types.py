"""Types for the flow agent loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FlowAgentConfig:
    model: str
    system_message: str
    user_message: str
    max_tool_rounds: int = 10
    temperature: float = 0.2
    enable_streaming: bool = False


@dataclass
class ToolCallRecord:
    round: int
    tool: str
    arguments: dict[str, Any]
    result_preview: str
    duration_ms: int
    success: bool
    error: str | None = None


@dataclass
class FlowAgentResult:
    text: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    rounds_used: int = 0
    max_rounds_reached: bool = False
    error: str | None = None


@dataclass
class NormalizedToolCall:
    id: str
    name: str
    arguments: dict[str, Any]
