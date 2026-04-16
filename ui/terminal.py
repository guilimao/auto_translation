from __future__ import annotations

import threading


RESET = '\x1b[0m'
BOLD = '\x1b[1m'

COLORS = {
    'info': '\x1b[96m',
    'ok': '\x1b[92m',
    'warn': '\x1b[93m',
    'error': '\x1b[91m',
    'muted': '\x1b[90m',
}


class TerminalUI:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stream_open = False
        self._stream_key: tuple[str, int] | None = None
        self._show_scheduler_reasoning = False
        self._executor_started: set[str] = set()
        self._executor_finals: dict[str, str] = {}

    def _color(self, text: str, color: str | None, *, bold: bool = False) -> str:
        if not color:
            return text
        prefix = color + (BOLD if bold else '')
        return f'{prefix}{text}{RESET}'

    def _compact_detail(self, detail: str | None, *, limit: int = 180) -> str | None:
        if not detail:
            return None
        text = ' '.join(detail.split())
        if len(text) <= limit:
            return text
        return text[: max(0, limit - 12)].rstrip() + ' ...[已截断]'

    def _finish_stream_if_needed(self) -> None:
        if self._stream_open:
            print()
            self._stream_open = False
            self._stream_key = None

    def log(self, text: str = '', end: str = '\n') -> None:
        with self._lock:
            self._finish_stream_if_needed()
            print(text, end=end, flush=True)

    def scheduler_started(self) -> None:
        self.log(self._color('[scheduler] 启动', COLORS['info'], bold=True))

    def scheduler_finished(self, detail: str | None = None) -> None:
        suffix = f' | {self._compact_detail(detail)}' if detail else ''
        self.log(self._color(f'[scheduler] 结束{suffix}', COLORS['ok'], bold=True))

    def scheduler_interrupted(self, detail: str | None = None) -> None:
        suffix = f' | {self._compact_detail(detail)}' if detail else ''
        self.log(self._color(f'[scheduler] 中断{suffix}', COLORS['warn'], bold=True))

    def scheduler_error(self, detail: str | None = None) -> None:
        suffix = f' | {self._compact_detail(detail)}' if detail else ''
        self.log(self._color(f'[scheduler] 错误{suffix}', COLORS['error'], bold=True))

    def scheduler_tool_call(self, round_no: int, detail: str) -> None:
        text = self._compact_detail(detail, limit=220) or ''
        self.log(self._color(f'[scheduler][轮次 {round_no}][工具] {text}', COLORS['warn']))

    def stream_scheduler(self, *, round_no: int, channel: str, text: str) -> None:
        if channel == 'reasoning' and not self._show_scheduler_reasoning:
            return
        key = (channel, round_no)
        channel_label = '思考' if channel == 'reasoning' else '输出'
        channel_color = COLORS['muted'] if channel == 'reasoning' else COLORS['ok']
        prefix = self._color(f'[scheduler][轮次 {round_no}][{channel_label}] ', channel_color, bold=True)
        with self._lock:
            if self._stream_key != key:
                self._finish_stream_if_needed()
                print(prefix, end='', flush=True)
                self._stream_open = True
                self._stream_key = key
            clean_text = text.replace('\r', '')
            print(self._color(clean_text, channel_color), end='', flush=True)

    def _render_executor_summary(self) -> None:
        total = len(self._executor_started)
        done = len(self._executor_finals)
        ok = sum(1 for status in self._executor_finals.values() if status == 'submitted')
        interrupted = sum(1 for status in self._executor_finals.values() if status == 'interrupted')
        failed = done - ok - interrupted
        self.log(
            self._color(
                f'[executors] 进度 {done}/{total} | 成功 {ok} | 失败 {failed} | 中断 {interrupted}',
                COLORS['muted'],
            )
        )

    def executor_started(self, agent_name: str, round_no: int) -> None:
        if agent_name in self._executor_started:
            return
        self._executor_started.add(agent_name)
        self.log(self._color(f'[{agent_name}][轮次 {round_no}] 启动', COLORS['info']))
        self._render_executor_summary()

    def executor_finished(self, agent_name: str, round_no: int, final_state: str, detail: str | None = None) -> None:
        if agent_name in self._executor_finals and self._executor_finals[agent_name] == final_state:
            return
        self._executor_finals[agent_name] = final_state
        state_map = {
            'submitted': ('正常提交结果', COLORS['ok']),
            'no_submission': ('未提交成果', COLORS['warn']),
            'output_too_long': ('输出过长', COLORS['error']),
            'interrupted': ('用户中断', COLORS['warn']),
            'error': ('执行失败', COLORS['error']),
        }
        label, color = state_map.get(final_state, (final_state, COLORS['warn']))
        compact_detail = self._compact_detail(detail)
        suffix = f' | {compact_detail}' if compact_detail and compact_detail != label else ''
        self.log(self._color(f'[{agent_name}][轮次 {round_no}] {label}{suffix}', color, bold=True))
        self._render_executor_summary()
