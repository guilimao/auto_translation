from __future__ import annotations

import asyncio
import json
import signal
from pathlib import Path
from typing import Any

from core import (
    Agent,
    ConversationLogger,
    EXECUTOR_PROMPT,
    GlobalRequestManager,
    LLMClientFactory,
    RuntimeContext,
    SCHEDULER_PROMPT,
    SPEC_TEXT,
    load_config,
)
from core.agent import (
    STATE_ERROR,
    STATE_FINISHED,
    STATE_INTERRUPTED,
    STATE_OUTPUT_TOO_LONG,
    STATE_STARTED,
)
from tools import create_executor_tools, create_scheduler_tools
from tools.helpers import clean_workspaces, ensure_directories, truncate_text
from ui.terminal import TerminalUI


class CLISession:
    _FONT_EXTENSIONS = {'.ttf', '.otf', '.ttc', '.otc', '.woff', '.woff2'}

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.config = load_config(project_root)
        ensure_directories(project_root)
        clean_workspaces(project_root)
        self._write_spec_file()
        self.logger = ConversationLogger(project_root)
        self.ui = TerminalUI()
        self.runtime = RuntimeContext(
            project_root=project_root,
            request_manager=GlobalRequestManager(
                max_concurrent_requests=self.config.concurrency.max_concurrent_requests,
                qps=self.config.concurrency.qps,
                qpm=self.config.concurrency.qpm,
            ),
            logger=self.logger,
            status_callback=self._on_status,
        )
        self.client_factory = LLMClientFactory(self.config)
        self.scheduler_messages: list[dict[str, Any]] = []
        self._current_interrupt_handler = None
        self._executor_finals: dict[str, tuple[int, str, str | None]] = {}

    def _write_spec_file(self) -> None:
        spec_path = self.project_root / 'ARCHITECTURE.md'
        spec_path.write_text(SPEC_TEXT + '\n', encoding='utf-8')

    def _install_interrupt_handler(self) -> None:
        previous = signal.getsignal(signal.SIGINT)

        def handler(signum, frame):
            if self.runtime.has_active_agents():
                self.ui.log('[收到 Ctrl+C，正在中断所有 Agent 并收集已完成结果...]')
                self.runtime.interrupt_all()
            else:
                raise KeyboardInterrupt

        signal.signal(signal.SIGINT, handler)
        self._current_interrupt_handler = previous

    def _restore_interrupt_handler(self) -> None:
        if self._current_interrupt_handler is not None:
            signal.signal(signal.SIGINT, self._current_interrupt_handler)
            self._current_interrupt_handler = None

    def _format_executor_prompt(self, workspace: Path, task_description: str) -> str:
        meta = json.loads((workspace / 'workspace_meta.json').read_text(encoding='utf-8'))
        return (
            f"请处理第 {meta['page_number']} 页。\n"
            f'任务描述：{task_description}\n'
            f'当前 workspace：{workspace}\n'
            '目录中已有页面图像 source.png，可先读取分析。\n'
            '完成后必须调用 submit_result 提交最终 Typst 文件。'
        )

    def _scan_project_font_names(self) -> list[str]:
        fonts_dir = self.project_root / 'fonts'
        if not fonts_dir.exists():
            return []
        font_names = {
            path.stem
            for path in fonts_dir.rglob('*')
            if path.is_file() and path.suffix.lower() in self._FONT_EXTENSIONS
        }
        return sorted(font_names, key=str.lower)

    def _build_executor_system_prompt(self) -> str:
        font_names = self._scan_project_font_names()
        fonts_text = '\n'.join(f'- {name}' for name in font_names) if font_names else '- (none found)'
        font_section = (
            'Available fonts from project `fonts/` (recursive scan, including subfolders):\n'
            f'{fonts_text}'
        )
        return f'{EXECUTOR_PROMPT}\n\n{font_section}'

    def _last_message_text(self, messages: list[dict[str, Any]]) -> str:
        for message in reversed(messages):
            content = message.get('content')
            if isinstance(content, str) and content.strip():
                return content.strip()
            if isinstance(content, list):
                parts = [item.get('text', '') for item in content if isinstance(item, dict) and item.get('type') == 'text']
                joined = '\n'.join([part for part in parts if part]).strip()
                if joined:
                    return joined
        return '无可用消息'

    def _record_executor_final(self, agent_name: str, round_no: int, state: str, detail: str | None) -> bool:
        previous = self._executor_finals.get(agent_name)
        if previous and previous[1] in {'submitted', 'interrupted', 'error', 'output_too_long'}:
            return False
        self._executor_finals[agent_name] = (round_no, state, detail)
        return True

    def _on_status(self, payload: dict[str, Any]) -> None:
        kind = payload.get('kind', 'state')
        agent_name = payload['agent_name']
        agent_type = payload['agent_type']
        round_no = payload.get('round', 0)
        state = payload.get('state', '')
        detail = payload.get('detail')

        if kind == 'stream':
            if agent_type == 'scheduler':
                self.ui.stream_scheduler(round_no=round_no, channel=payload['channel'], text=payload['text'])
            return

        if kind == 'tool_call':
            if agent_type == 'scheduler':
                self.ui.scheduler_tool_call(round_no, detail or '')
            return

        if agent_type == 'scheduler':
            if state == STATE_STARTED:
                self.ui.scheduler_started()
            elif state == STATE_FINISHED:
                self.ui.scheduler_finished(detail)
            elif state == STATE_INTERRUPTED:
                self.ui.scheduler_interrupted(detail)
            elif state == STATE_ERROR:
                self.ui.scheduler_error(detail)
            return

        if state == STATE_STARTED:
            self.ui.executor_started(agent_name, round_no)
            return

        if state == STATE_FINISHED:
            final_state = 'submitted' if detail == 'submitted' else 'no_submission'
            final_detail = None if detail == 'submitted' else detail
            if self._record_executor_final(agent_name, round_no, final_state, final_detail):
                self.ui.executor_finished(agent_name, round_no, final_state, final_detail)
            return

        if state == STATE_ERROR:
            if self._record_executor_final(agent_name, round_no, 'error', detail):
                self.ui.executor_finished(agent_name, round_no, 'error', detail)
            return

        if state == STATE_INTERRUPTED:
            if self._record_executor_final(agent_name, round_no, 'interrupted', detail):
                self.ui.executor_finished(agent_name, round_no, 'interrupted', detail)
            return

        if state == STATE_OUTPUT_TOO_LONG:
            if self._record_executor_final(agent_name, round_no, 'output_too_long', detail):
                self.ui.executor_finished(agent_name, round_no, 'output_too_long', detail)

    async def spawn_executor(self, workspace: Path, task_description: str) -> dict[str, Any]:
        meta = json.loads((workspace / 'workspace_meta.json').read_text(encoding='utf-8'))
        page_number = int(meta['page_number'])
        agent_name = f'executor_page_{page_number:03d}'
        self._executor_finals.pop(agent_name, None)
        agent = Agent(
            name=agent_name,
            agent_type='executor',
            system_prompt=self._build_executor_system_prompt(),
            tools=create_executor_tools(),
            model=self.config.executor_model,
            inference=self.config.inference,
            runtime=self.runtime,
            client_factory=self.client_factory,
            workspace=workspace,
            default_root=workspace,
            output_to_cli=False,
        )
        messages = [{'role': 'user', 'content': self._format_executor_prompt(workspace, task_description)}]
        result_messages = await agent.run(messages)
        flags = agent.last_run_flags
        final = self._executor_finals.get(agent_name)

        if flags.get('submitted'):
            return {'page': page_number, 'status': '运行成功', 'workspace': str(workspace)}

        if final is not None and final[1] in {'error', 'interrupted', 'output_too_long'}:
            status_map = {
                'error': '执行失败',
                'interrupted': '用户中断',
                'output_too_long': '输出过长',
            }
            final_status = status_map[final[1]]
            final_detail = final[2] or final_status
            return {'page': page_number, 'status': final_status, 'detail': final_detail, 'workspace': str(workspace)}

        detail = truncate_text(self._last_message_text(result_messages), 500)
        self._record_executor_final(agent_name, 0, 'no_submission', detail)
        return {'page': page_number, 'status': detail, 'detail': detail, 'workspace': str(workspace)}

    async def handle_user_input(self, user_input: str) -> None:
        self.runtime.reset_interrupt()
        self._executor_finals.clear()
        self.scheduler_messages.append({'role': 'user', 'content': user_input})
        scheduler = Agent(
            name='scheduler',
            agent_type='scheduler',
            system_prompt=SCHEDULER_PROMPT,
            tools=create_scheduler_tools(
                spawn_executor=self.spawn_executor,
                max_parallel_agents=self.config.concurrency.max_parallel_agents,
            ),
            model=self.config.scheduler_model,
            inference=self.config.inference,
            runtime=self.runtime,
            client_factory=self.client_factory,
            workspace=self.project_root,
            default_root=self.project_root,
            output_to_cli=True,
        )
        self._install_interrupt_handler()
        try:
            self.scheduler_messages = await scheduler.run(self.scheduler_messages)
        finally:
            self._restore_interrupt_handler()
            self.ui.log()

    def print_banner(self) -> None:
        self.ui.log('自动翻译 CLI 已启动。')
        self.ui.log(f'输入目录: {self.project_root / "inputs"}')
        self.ui.log(f'工作区目录: {self.project_root / "workspaces"}')
        self.ui.log(f'输出目录: {self.project_root / "output"}')
        self.ui.log(f'日志目录: {self.logger.session_dir}')
        self.ui.log(
            '并发设置: '
            f'max_parallel_agents={self.config.concurrency.max_parallel_agents}, '
            f'max_concurrent_requests={self.config.concurrency.max_concurrent_requests}, '
            f'qps={self.config.concurrency.qps}, qpm={self.config.concurrency.qpm}'
        )
        self.ui.log('请把待处理文件放入 inputs 后，再输入你的任务。')


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    session = CLISession(project_root)
    session.print_banner()
    try:
        while True:
            try:
                user_input = input('\n你: ').strip()
            except EOFError:
                print()
                break
            except KeyboardInterrupt:
                print('\n\n[退出]')
                break
            if not user_input:
                continue
            asyncio.run(session.handle_user_input(user_input))
    finally:
        print('[再见]')
