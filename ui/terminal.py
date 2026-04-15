from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any


@dataclass
class AgentLine:
    agent_name: str
    text: str


class TerminalUI:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rendered_status_lines = 0
        self._executor_order: list[str] = []
        self._executor_lines: dict[str, AgentLine] = {}
        self._stream_open = False
        self._stream_key: tuple[str, str, int] | None = None

    def _clear_status_block(self) -> None:
        if self._rendered_status_lines <= 0:
            return
        for _ in range(self._rendered_status_lines):
            print('\x1b[1A\x1b[2K', end='')
        self._rendered_status_lines = 0

    def _render_status_block(self) -> None:
        if not self._executor_order:
            return
        for agent_name in self._executor_order:
            line = self._executor_lines[agent_name].text
            print(line)
        self._rendered_status_lines = len(self._executor_order)

    def _prepare_for_log_output(self) -> None:
        self._clear_status_block()

    def _finish_stream_if_needed(self) -> None:
        if self._stream_open:
            print()
            self._stream_open = False
            self._stream_key = None

    def log(self, text: str = '', end: str = '\n') -> None:
        with self._lock:
            self._prepare_for_log_output()
            self._finish_stream_if_needed()
            print(text, end=end, flush=True)
            self._render_status_block()

    def stream(self, *, agent_name: str, round_no: int, channel: str, text: str) -> None:
        prefix = f'[{agent_name}][轮次 {round_no}][{"思考" if channel == "reasoning" else "输出"}] '
        key = (agent_name, channel, round_no)
        with self._lock:
            self._prepare_for_log_output()
            if self._stream_key != key:
                self._finish_stream_if_needed()
                print(prefix, end='', flush=True)
                self._stream_open = True
                self._stream_key = key
            style_prefix = '\x1b[90m' if channel == 'reasoning' else ''
            style_suffix = '\x1b[0m' if channel == 'reasoning' else ''
            print(f'{style_prefix}{text}{style_suffix}', end='', flush=True)
            self._render_status_block()

    def scheduler_tool_call(self, agent_name: str, round_no: int, detail: str) -> None:
        self.log(f'[{agent_name}][轮次 {round_no}][工具调用] {detail}')

    def update_executor(self, agent_name: str, round_no: int, state: str, detail: str | None = None) -> None:
        if agent_name not in self._executor_lines:
            self._executor_order.append(agent_name)
            self._executor_lines[agent_name] = AgentLine(agent_name=agent_name, text='')
        line = f'[{agent_name}][轮次 {round_no}] {state}'
        if detail:
            line += f' | {detail}'
        with self._lock:
            self._executor_lines[agent_name].text = line
            self._clear_status_block()
            self._render_status_block()

    def finish_executor(self, agent_name: str, round_no: int, final_state: str, detail: str | None = None) -> None:
        if agent_name not in self._executor_lines:
            self._executor_order.append(agent_name)
            self._executor_lines[agent_name] = AgentLine(agent_name=agent_name, text='')
        line = f'[{agent_name}][轮次 {round_no}] {final_state}'
        if detail:
            line += f' | {detail}'
        with self._lock:
            self._executor_lines[agent_name].text = line
            self._clear_status_block()
            self._render_status_block()
