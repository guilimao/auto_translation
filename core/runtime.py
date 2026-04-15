from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from core.conversation_log import ConversationLogger
from core.rate_control import GlobalRequestManager


StatusCallback = Callable[[dict[str, Any]], None]


@dataclass
class RuntimeContext:
    project_root: Path
    request_manager: GlobalRequestManager
    logger: ConversationLogger
    status_callback: StatusCallback
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    active_agent_names: set[str] = field(default_factory=set)

    @property
    def inputs_dir(self) -> Path:
        return self.project_root / 'inputs'

    @property
    def workspaces_dir(self) -> Path:
        return self.project_root / 'workspaces'

    @property
    def output_dir(self) -> Path:
        return self.project_root / 'output'

    def emit_status(self, payload: dict[str, Any]) -> None:
        self.status_callback(payload)

    def register_agent(self, agent_name: str) -> None:
        self.active_agent_names.add(agent_name)

    def unregister_agent(self, agent_name: str) -> None:
        self.active_agent_names.discard(agent_name)

    def has_active_agents(self) -> bool:
        return bool(self.active_agent_names)

    def interrupt_all(self) -> None:
        self.cancel_event.set()

    def reset_interrupt(self) -> None:
        if self.cancel_event.is_set():
            self.cancel_event.clear()
