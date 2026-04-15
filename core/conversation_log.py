from __future__ import annotations

import json
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class ConversationLogger:
    project_root: Path
    session_dir: Path = field(init=False)
    _counters: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.session_dir = self.project_root / 'logs' / timestamp
        (self.session_dir / 'scheduler').mkdir(parents=True, exist_ok=True)
        (self.session_dir / 'executors').mkdir(parents=True, exist_ok=True)

    def _next_path(self, group: str, agent_name: str) -> Path:
        with self._lock:
            key = f'{group}:{agent_name}'
            self._counters[key] += 1
            index = self._counters[key]
        if group == 'scheduler':
            directory = self.session_dir / 'scheduler'
        else:
            directory = self.session_dir / 'executors' / agent_name
            directory.mkdir(parents=True, exist_ok=True)
        return directory / f'request_{index:03d}.json'

    def save_messages(
        self,
        *,
        group: str,
        agent_name: str,
        messages: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        path = self._next_path(group, agent_name)
        payload = {
            'saved_at': datetime.now().isoformat(timespec='seconds'),
            'group': group,
            'agent_name': agent_name,
            'metadata': metadata or {},
            'messages': messages,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        return path
