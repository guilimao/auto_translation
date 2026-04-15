from __future__ import annotations

from core.app_config import AppConfig


class LLMClientFactory:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._client = None

    def get_client(self):
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except ModuleNotFoundError as exc:
                raise RuntimeError('缺少 openai 依赖，请先执行 `uv sync`。') from exc
            self._client = AsyncOpenAI(base_url=self.config.base_url, api_key=self.config.api_key)
        return self._client
