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

DEFAULT_INFERENCE = {
    'temperature': 0.2,
    'max_output_tokens': 8192,
    'repetition_penalty': 1.05,
    'reasoning_enabled': True,
    'reasoning_effort': 'low',
    'reasoning_max_tokens': None,
    'reasoning_exclude': False,
}

_ALLOWED_REASONING_EFFORTS = {'minimal', 'low', 'medium', 'high', 'xhigh', 'none'}


@dataclass(slots=True)
class ConcurrencyConfig:
    max_parallel_agents: int = 4
    max_concurrent_requests: int = 4
    qps: float = 1.0
    qpm: int = 30


@dataclass(slots=True)
class InferenceConfig:
    temperature: float = 0.2
    max_output_tokens: int = 8192
    repetition_penalty: float = 1.05
    reasoning_enabled: bool = True
    reasoning_effort: str | None = 'low'
    reasoning_max_tokens: int | None = None
    reasoning_exclude: bool = False

    def to_request_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            'temperature': self.temperature,
            'max_tokens': self.max_output_tokens,
            'repetition_penalty': self.repetition_penalty,
        }
        reasoning: dict[str, Any] = {'enabled': self.reasoning_enabled}
        if self.reasoning_enabled and self.reasoning_effort:
            kwargs['reasoning_effort'] = self.reasoning_effort
        if self.reasoning_max_tokens is not None:
            reasoning['max_tokens'] = self.reasoning_max_tokens
        if self.reasoning_exclude:
            reasoning['exclude'] = True
        if reasoning:
            kwargs['reasoning'] = reasoning
        return kwargs


@dataclass(slots=True)
class AppConfig:
    base_url: str
    api_key_env: str
    model: str
    scheduler_model: str
    executor_model: str
    concurrency: ConcurrencyConfig
    inference: InferenceConfig

    @property
    def api_key(self) -> str:
        api_key = os.getenv(self.api_key_env)
        if not api_key:
            raise ValueError(f"环境变量 '{self.api_key_env}' 未设置，请先配置 API key。")
        return api_key



def _load_json(path: Path) -> dict[str, Any]:
    with path.open('r', encoding='utf-8') as fh:
        return json.load(fh)



def _load_inference_config(raw: dict[str, Any]) -> InferenceConfig:
    inference_raw = {**DEFAULT_INFERENCE, **raw.get('inference', {})}
    reasoning_effort = inference_raw.get('reasoning_effort')
    if reasoning_effort is not None:
        reasoning_effort = str(reasoning_effort).strip().lower() or None
        if reasoning_effort == 'none':
            reasoning_effort = None
        if reasoning_effort is not None and reasoning_effort not in _ALLOWED_REASONING_EFFORTS:
            raise ValueError(
                'config.json 中 inference.reasoning_effort 非法，'
                f'可选值: {sorted(_ALLOWED_REASONING_EFFORTS)}'
            )
    reasoning_max_tokens_raw = inference_raw.get('reasoning_max_tokens')
    reasoning_max_tokens = None if reasoning_max_tokens_raw in (None, '') else max(1, int(reasoning_max_tokens_raw))
    return InferenceConfig(
        temperature=min(2.0, max(0.0, float(inference_raw['temperature']))),
        max_output_tokens=max(1, int(inference_raw['max_output_tokens'])),
        repetition_penalty=min(2.0, max(0.0, float(inference_raw['repetition_penalty']))),
        reasoning_enabled=bool(inference_raw.get('reasoning_enabled', True)),
        reasoning_effort=reasoning_effort,
        reasoning_max_tokens=reasoning_max_tokens,
        reasoning_exclude=bool(inference_raw.get('reasoning_exclude', False)),
    )



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
        inference=_load_inference_config(raw),
    )
