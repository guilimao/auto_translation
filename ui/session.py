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
from tools import create_executor_tools, create_scheduler_tools
from tools.helpers import clean_workspaces, ensure_directories, truncate_text
from ui.terminal import TerminalUI


class CLISession:
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
                self.ui.log('[收到 Ctrl+C，正在中断所有 Agent，并汇总当前结果...]')
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

    def _record_executor_final(self, agent_name: str, round_no: int, state: str, detail: str | None) -> None:
        self._executor_finals[agent_name] = (round_no, state, detail)

    def _on_status(self, payload: dict[str, Any]) -> None:
        kind = payload.get('kind', 'state')
        agent_name = payload['agent_name']
        agent_type = payload['agent_type']
        round_no = payload.get('round', 0)
        state = payload.get('state', '')
        detail = payload.get('detail')
        if kind == 'stream':
            self.ui.stream(agent_name=agent_name, round_no=round_no, channel=payload['channel'], text=payload['text'])
            return
        if kind == 'tool_call' and agent_type == 'scheduler':
            self.ui.scheduler_tool_call(agent_name, round_no, detail or '')
            return
        if agent_type == 'scheduler':
            if kind == 'state' and state in {'启动', '等待回应', '工具调用'}:
                self.ui.log(f'[{agent_name}][轮次 {round_no}][{state}]' + (f' {detail}' if detail else ''))
            elif kind == 'state' and state in {'结束', '中断', '错误'}:
                suffix = f' {detail}' if detail else ''
                self.ui.log(f'[{agent_name}][轮次 {round_no}][{state}]' + suffix)
            return
        display_state = state
        if state == '结束':
            final_state = '正常提交结果' if detail == '正常提交结果' else '未提交成果'
            self._record_executor_final(agent_name, round_no, final_state, detail if detail and detail != final_state else None)
            self.ui.finish_executor(agent_name, round_no, final_state, None if detail == final_state else detail)
            return
        if state == '错误':
            self._record_executor_final(agent_name, round_no, '传输报错', detail)
            self.ui.finish_executor(agent_name, round_no, '传输报错', detail)
            return
        if state == '中断':
            self._record_executor_final(agent_name, round_no, '用户中断', detail)
            self.ui.finish_executor(agent_name, round_no, '用户中断', detail)
            return
        self.ui.update_executor(agent_name, round_no, display_state, detail)

    async def spawn_executor(self, workspace: Path, task_description: str) -> dict[str, Any]:
        meta = json.loads((workspace / 'workspace_meta.json').read_text(encoding='utf-8'))
        page_number = int(meta['page_number'])
        agent_name = f'executor_page_{page_number:03d}'
        self._executor_finals.pop(agent_name, None)
        agent = Agent(
            name=agent_name,
            agent_type='executor',
            system_prompt=EXECUTOR_PROMPT,
            tools=create_executor_tools(),
            model=self.config.executor_model,
            runtime=self.runtime,
            client_factory=self.client_factory,
            workspace=workspace,
            default_root=workspace,
            output_to_cli=False,
        )
        messages = [{'role': 'user', 'content': self._format_executor_prompt(workspace, task_description)}]
        result_messages = await agent.run(messages)
        flags = agent.last_run_flags
        if flags.get('submitted'):
            self._on_status({'kind': 'state', 'agent_name': agent_name, 'agent_type': 'executor', 'state': '结束', 'round': 0, 'detail': '正常提交结果'})
            return {'page': page_number, 'status': '运行成功', 'workspace': str(workspace)}
        if self.runtime.cancel_event.is_set():
            detail = '用户中断'
            self._on_status({'kind': 'state', 'agent_name': agent_name, 'agent_type': 'executor', 'state': '中断', 'round': 0, 'detail': detail})
            return {'page': page_number, 'status': detail, 'detail': detail, 'workspace': str(workspace)}
        detail = truncate_text(self._last_message_text(result_messages), 500)
        final = self._executor_finals.get(agent_name)
        if final is None or final[1] not in {'传输报错', '用户中断'}:
            self._on_status({'kind': 'state', 'agent_name': agent_name, 'agent_type': 'executor', 'state': '结束', 'round': 0, 'detail': detail})
        return {'page': page_number, 'status': detail, 'detail': detail, 'workspace': str(workspace)}

    async def handle_user_input(self, user_input: str) -> None:
        self.runtime.reset_interrupt()
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
        self.ui.log('请将待处理文件放入 inputs 文件夹后，再告诉调度器要翻译哪个文件。')



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
