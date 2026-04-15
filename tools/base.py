from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable


ToolHandler = Callable[..., Awaitable[Any]]


@dataclass(slots=True)
class ToolSpec:
    name: str
    schema: dict[str, Any]
    handler: ToolHandler


@dataclass
class ToolContext:
    runtime: Any
    agent_name: str
    agent_type: str
    workspace: Path
    default_root: Path
    flags: dict[str, Any] = field(default_factory=dict)
