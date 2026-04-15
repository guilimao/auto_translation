from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_CONCURRENCY = {
    'max_parallel_agents': 4,
    'max_concurrent_requests': 4,
    'qps': 1.0,
    'qpm': 30,
}


@dataclass(slots=True)
class ConcurrencyConfig:
    max_parallel_agents: int = 4
    max_concurrent_requests: int = 4
    qps: float = 1.0
    qpm: int = 30


@dataclass(slots=True)
class AppConfig:
    base_url: str
    api_key_env: str
    model: str
    scheduler_model: str
    executor_model: str
    concurrency: ConcurrencyConfig

    @property
    def api_key(self) -> str:
        api_key = os.getenv(self.api_key_env)
        if not api_key:
            raise ValueError(f"环境变量 '{self.api_key_env}' 未设置，请先配置 API key。")
        return api_key



def _load_json(path: Path) -> dict[str, Any]:
    with path.open('r', encoding='utf-8') as fh:
        return json.load(fh)



def load_config(project_root: Path | None = None) -> AppConfig:
    project_root = project_root or Path(__file__).resolve().parent.parent
    raw = _load_json(project_root / 'config.json')
    concurrency_raw = {**DEFAULT_CONCURRENCY, **raw.get('concurrency', {})}
    concurrency = ConcurrencyConfig(
        max_parallel_agents=max(1, int(concurrency_raw['max_parallel_agents'])),
        max_concurrent_requests=max(1, int(concurrency_raw['max_concurrent_requests'])),
        qps=max(0.01, float(concurrency_raw['qps'])),
        qpm=max(1, int(concurrency_raw['qpm'])),
    )
    model = raw['model']
    return AppConfig(
        base_url=raw['base_url'],
        api_key_env=raw['api_key'],
        model=model,
        scheduler_model=raw.get('scheduler_model') or model,
        executor_model=raw.get('executor_model') or model,
        concurrency=concurrency,
    )
