from __future__ import annotations

import json
import re
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


_DATA_URL_PREFIX = re.compile(r'^data:[^;]+;base64,', re.IGNORECASE)


@dataclass(slots=True, frozen=True)
class AgentLifecycleLog:
    lifecycle_id: str
    group: str
    agent_name: str
    path: Path


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

    def _safe_component(self, value: str) -> str:
        normalized = re.sub(r'[^a-zA-Z0-9_.-]+', '_', value.strip())
        return normalized.strip('_.') or 'agent'

    def _build_lifecycle_path(self, group: str, agent_name: str, lifecycle_id: str) -> Path:
        safe_agent = self._safe_component(agent_name)
        safe_lifecycle = self._safe_component(lifecycle_id)
        if group == 'scheduler':
            directory = self.session_dir / 'scheduler'
        else:
            directory = self.session_dir / 'executors' / safe_agent
            directory.mkdir(parents=True, exist_ok=True)
        return directory / f'{safe_lifecycle}.jsonl'

    def _next_lifecycle_id(self, group: str, agent_name: str) -> str:
        with self._lock:
            key = f'{group}:{agent_name}'
            self._counters[key] += 1
            index = self._counters[key]
        now = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f'{agent_name}_{now}_{index:03d}'

    def _serialize_message(self, value: Any) -> Any:
        if isinstance(value, str):
            return value if len(value) <= 10000 else (value[:9500] + '\n...[truncated]')
        if isinstance(value, list):
            return [self._serialize_message(item) for item in value]
        if isinstance(value, dict):
            result: dict[str, Any] = {}
            for key, item in value.items():
                if key == 'image_url' and isinstance(item, dict):
                    url = item.get('url')
                    if isinstance(url, str) and _DATA_URL_PREFIX.match(url):
                        result[key] = {'url': '<data_url_omitted>'}
                        continue
                result[key] = self._serialize_message(item)
            return result
        return value

    def append_event(self, handle: AgentLifecycleLog, event: str, payload: dict[str, Any] | None = None) -> None:
        row = {
            'time': datetime.now().isoformat(timespec='seconds'),
            'event': event,
        }
        if payload:
            row.update(payload)
        line = json.dumps(row, ensure_ascii=False)
        with self._lock:
            with handle.path.open('a', encoding='utf-8') as fh:
                fh.write(line + '\n')

    def start_agent_lifecycle(
        self,
        *,
        group: str,
        agent_name: str,
        metadata: dict[str, Any] | None = None,
    ) -> AgentLifecycleLog:
        lifecycle_id = self._next_lifecycle_id(group, agent_name)
        path = self._build_lifecycle_path(group, agent_name, lifecycle_id)
        handle = AgentLifecycleLog(
            lifecycle_id=lifecycle_id,
            group=group,
            agent_name=agent_name,
            path=path,
        )
        self.append_event(
            handle,
            'lifecycle_start',
            {
                'lifecycle_id': lifecycle_id,
                'group': group,
                'agent_name': agent_name,
                'metadata': metadata or {},
            },
        )
        return handle

    def append_messages(self, handle: AgentLifecycleLog, messages: list[dict[str, Any]], *, start_index: int = 0) -> None:
        for index, message in enumerate(messages[start_index:], start=start_index):
            self.append_event(
                handle,
                'message',
                {
                    'index': index,
                    'message': self._serialize_message(message),
                },
            )

    def end_agent_lifecycle(self, handle: AgentLifecycleLog, *, summary: dict[str, Any] | None = None) -> None:
        self.append_event(handle, 'lifecycle_end', {'summary': summary or {}})

    def save_messages(
        self,
        *,
        group: str,
        agent_name: str,
        messages: list[dict[str, Any]],
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        # Backward-compatible wrapper: keep writing to a single lifecycle file.
        handle = self.start_agent_lifecycle(group=group, agent_name=agent_name, metadata={'legacy_mode': True})
        self.append_event(handle, 'snapshot', {'metadata': metadata or {}, 'messages': self._serialize_message(messages)})
        self.end_agent_lifecycle(handle)
        return handle.path
