from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.llm_client import LLMClientFactory
from core.runtime import RuntimeContext
from tools import ToolContext, ToolSpec
from tools.helpers import AgentInterrupted


@dataclass
class StreamResult:
    content: str
    reasoning_content: str
    tool_calls: list[dict[str, Any]]
    finish_reason: str | None


class Agent:
    def __init__(
        self,
        *,
        name: str,
        agent_type: str,
        system_prompt: str,
        tools: list[ToolSpec],
        model: str,
        runtime: RuntimeContext,
        client_factory: LLMClientFactory,
        workspace: Path,
        default_root: Path,
        output_to_cli: bool,
    ) -> None:
        self.name = name
        self.agent_type = agent_type
        self.system_prompt = system_prompt.strip()
        self.tools = tools
        self.model = model
        self.runtime = runtime
        self.client_factory = client_factory
        self.workspace = workspace
        self.default_root = default_root
        self.output_to_cli = output_to_cli
        self.tool_map = {tool.name: tool for tool in tools}
        self.tool_schemas = [tool.schema for tool in tools]
        self.tool_context = ToolContext(
            runtime=runtime,
            agent_name=name,
            agent_type=agent_type,
            workspace=workspace,
            default_root=default_root,
        )
        self.last_run_flags: dict[str, Any] = {}

    def _emit_state(self, state: str, round_no: int, detail: str | None = None) -> None:
        payload = {
            'kind': 'state',
            'agent_name': self.name,
            'agent_type': self.agent_type,
            'state': state,
            'round': round_no,
        }
        if detail:
            payload['detail'] = detail
        self.runtime.emit_status(payload)

    def _emit_stream(self, round_no: int, channel: str, text: str) -> None:
        if not self.output_to_cli or not text:
            return
        self.runtime.emit_status(
            {
                'kind': 'stream',
                'agent_name': self.name,
                'agent_type': self.agent_type,
                'round': round_no,
                'channel': channel,
                'text': text,
            }
        )

    def _emit_tool_call(self, round_no: int, func_name: str, raw_arguments: str | None = None) -> None:
        detail = func_name
        if raw_arguments:
            detail += f' {raw_arguments}'
        self.runtime.emit_status(
            {
                'kind': 'tool_call',
                'agent_name': self.name,
                'agent_type': self.agent_type,
                'round': round_no,
                'state': '工具调用',
                'detail': detail,
                'tool_name': func_name,
            }
        )

    def _prepare_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = [dict(message) for message in messages]
        if not result or result[0].get('role') != 'system':
            result.insert(0, {'role': 'system', 'content': self.system_prompt})
        return result

    async def _safe_close_stream(self, stream: Any) -> None:
        close = getattr(stream, 'close', None)
        if callable(close):
            maybe = close()
            if hasattr(maybe, '__await__'):
                await maybe
            return
        aclose = getattr(stream, 'aclose', None)
        if callable(aclose):
            await aclose()

    def _compact_previous_tool_image(self, messages: list[dict[str, Any]], tool_name: str) -> None:
        for message in reversed(messages):
            if message.get('role') != 'tool' or message.get('_tool_name') != tool_name:
                continue
            content = message.get('content')
            if not isinstance(content, list):
                return
            has_image = any(isinstance(item, dict) and item.get('type') == 'image_url' for item in content)
            if not has_image:
                return
            new_content: list[dict[str, Any]] = []
            text_index: int | None = None
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get('type') == 'image_url':
                    continue
                if item.get('type') == 'text':
                    copied = dict(item)
                    if text_index is None:
                        text_index = len(new_content)
                    new_content.append(copied)
                    continue
                new_content.append(item)
            note = '图像已省略'
            if text_index is None:
                new_content.insert(0, {'type': 'text', 'text': note})
            else:
                existing = new_content[text_index].get('text', '')
                if note not in existing:
                    suffix = '\n\n' if existing.strip() else ''
                    new_content[text_index]['text'] = existing + suffix + note
            message['content'] = new_content
            return

    async def _process_stream(self, messages: list[dict[str, Any]], round_no: int) -> StreamResult:
        if self.runtime.cancel_event.is_set():
            raise AgentInterrupted('用户中断')
        self._emit_state('等待回应', round_no)
        await self.runtime.request_manager.acquire()
        stream = None
        try:
            client = self.client_factory.get_client()
            stream = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.tool_schemas,
                tool_choice='auto',
                stream=True,
            )
            content = ''
            reasoning_content = ''
            tool_calls: list[dict[str, Any]] = []
            finish_reason = None
            emitted_thinking = False
            emitted_output = False
            emitted_tool_call = False
            async for chunk in stream:
                if self.runtime.cancel_event.is_set():
                    await self._safe_close_stream(stream)
                    raise AgentInterrupted('用户中断')
                choice = chunk.choices[0]
                if choice.finish_reason:
                    finish_reason = choice.finish_reason
                delta = choice.delta
                reasoning_text = getattr(delta, 'reasoning_content', None) or (delta.model_extra or {}).get('reasoning_content')
                if reasoning_text:
                    if not emitted_thinking:
                        self._emit_state('思考', round_no)
                        emitted_thinking = True
                    reasoning_content += reasoning_text
                    self._emit_stream(round_no, 'reasoning', reasoning_text)
                if delta.content:
                    if not emitted_output:
                        self._emit_state('普通输出', round_no)
                        emitted_output = True
                    content += delta.content
                    self._emit_stream(round_no, 'output', delta.content)
                if delta.tool_calls:
                    if not emitted_tool_call:
                        self._emit_state('工具调用', round_no)
                        emitted_tool_call = True
                    for tc in delta.tool_calls:
                        if tc.index >= len(tool_calls):
                            tool_calls.append({'id': '', 'type': 'function', 'function': {'name': '', 'arguments': ''}})
                        if tc.id:
                            tool_calls[tc.index]['id'] = tc.id
                        if tc.function and tc.function.name:
                            tool_calls[tc.index]['function']['name'] = tc.function.name
                        if tc.function and tc.function.arguments:
                            tool_calls[tc.index]['function']['arguments'] += tc.function.arguments
            return StreamResult(content=content, reasoning_content=reasoning_content, tool_calls=tool_calls, finish_reason=finish_reason)
        finally:
            if stream is not None:
                try:
                    await self._safe_close_stream(stream)
                except Exception:
                    pass
            self.runtime.request_manager.release()

    async def _execute_tool(self, tool_call: dict[str, Any], round_no: int) -> dict[str, Any]:
        func_name = tool_call['function']['name']
        raw_arguments = tool_call['function'].get('arguments') or '{}'
        self._emit_tool_call(round_no, func_name, raw_arguments if self.agent_type == 'scheduler' else None)
        if func_name not in self.tool_map:
            return {'role': 'tool', 'tool_call_id': tool_call['id'], 'content': f'未知工具: {func_name}', '_tool_name': func_name}
        try:
            arguments = json.loads(raw_arguments)
        except json.JSONDecodeError as exc:
            return {'role': 'tool', 'tool_call_id': tool_call['id'], 'content': f'工具参数解析失败: {exc}', '_tool_name': func_name}
        try:
            result = await self.tool_map[func_name].handler(self.tool_context, **arguments)
        except AgentInterrupted:
            raise
        except Exception as exc:
            result = f"工具 '{func_name}' 执行失败: {exc}"
        if isinstance(result, dict) and result.get('type') == 'image_content':
            return {
                'role': 'tool',
                'tool_call_id': tool_call['id'],
                'content': result.get('content', []),
                '_tool_name': func_name,
            }
        if isinstance(result, dict) and result.get('type') == 'error':
            return {'role': 'tool', 'tool_call_id': tool_call['id'], 'content': result.get('message', '未知错误'), '_tool_name': func_name}
        return {'role': 'tool', 'tool_call_id': tool_call['id'], 'content': str(result), '_tool_name': func_name}

    async def _process_tool_calls(self, messages: list[dict[str, Any]], tool_calls: list[dict[str, Any]], round_no: int) -> bool:
        if not tool_calls:
            return False
        for tool_call in tool_calls:
            if self.runtime.cancel_event.is_set():
                raise AgentInterrupted('用户中断')
            tool_name = tool_call['function']['name']
            if tool_name in {'read_image', 'crop_image'}:
                self._compact_previous_tool_image(messages, tool_name)
            tool_message = await self._execute_tool(tool_call, round_no)
            messages.append(tool_message)
            if self.tool_context.flags.get('terminate_after_tool'):
                return False
        return True

    async def run(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        prepared_messages = self._prepare_messages(messages)
        round_no = 0
        interrupted = False
        self.runtime.register_agent(self.name)
        self._emit_state('启动', 0)
        try:
            while True:
                if self.runtime.cancel_event.is_set():
                    interrupted = True
                    raise AgentInterrupted('用户中断')
                round_no += 1
                stream_result = await self._process_stream(prepared_messages, round_no)
                assistant_message: dict[str, Any] = {'role': 'assistant'}
                if stream_result.content:
                    assistant_message['content'] = stream_result.content
                if stream_result.reasoning_content:
                    assistant_message['reasoning_content'] = stream_result.reasoning_content
                if stream_result.tool_calls:
                    assistant_message['tool_calls'] = [
                        {'id': item['id'], 'type': item['type'], 'function': item['function']}
                        for item in stream_result.tool_calls
                    ]
                prepared_messages.append(assistant_message)
                should_continue = await self._process_tool_calls(prepared_messages, stream_result.tool_calls, round_no)
                if not should_continue:
                    break
            self._emit_state('结束', round_no)
            return prepared_messages
        except AgentInterrupted as exc:
            interrupted = True
            self._emit_state('中断', round_no, str(exc))
            return prepared_messages
        except Exception as exc:
            self._emit_state('错误', round_no, str(exc))
            prepared_messages.append({'role': 'assistant', 'content': f'Agent 运行失败: {exc}'})
            return prepared_messages
        finally:
            self.last_run_flags = dict(self.tool_context.flags)
            self.runtime.logger.save_messages(
                group='scheduler' if self.agent_type == 'scheduler' else 'executor',
                agent_name=self.name,
                messages=prepared_messages,
                metadata={
                    'workspace': str(self.workspace),
                    'rounds': round_no,
                    'interrupted': interrupted,
                    'tool_flags': dict(self.tool_context.flags),
                },
            )
            self.runtime.unregister_agent(self.name)
