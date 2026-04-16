from __future__ import annotations

import inspect
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.app_config import InferenceConfig
from core.llm_client import LLMClientFactory
from core.runtime import RuntimeContext
from tools import ToolContext, ToolSpec
from tools.helpers import AgentInterrupted


STATE_STARTED = 'started'
STATE_WAITING_RESPONSE = 'waiting_response'
STATE_REASONING = 'reasoning'
STATE_OUTPUT = 'output'
STATE_TOOL_CALLING = 'tool_calling'
STATE_FINISHED = 'finished'
STATE_INTERRUPTED = 'interrupted'
STATE_ERROR = 'error'
STATE_OUTPUT_TOO_LONG = 'output_too_long'

EXECUTOR_OUTPUT_WORD_LIMIT = 3000
_WORD_RE = re.compile(r'\S+', re.UNICODE)


@dataclass
class StreamResult:
    content: str
    reasoning_content: str
    reasoning_details: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str | None = None
    output_too_long: bool = False


class Agent:
    def __init__(
        self,
        *,
        name: str,
        agent_type: str,
        system_prompt: str,
        tools: list[ToolSpec],
        model: str,
        inference: InferenceConfig,
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
        self.inference = inference
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
        self._chat_create_param_names: set[str] | None = None
        self._log_handle = None
        self._logged_message_count = 0

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
        if self._log_handle is not None:
            self.runtime.logger.append_event(
                self._log_handle,
                'status',
                {
                    'round': round_no,
                    'state': state,
                    'detail': detail,
                },
            )

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
                'state': STATE_TOOL_CALLING,
                'detail': detail,
                'tool_name': func_name,
            }
        )
        if self._log_handle is not None:
            self.runtime.logger.append_event(
                self._log_handle,
                'tool_call',
                {
                    'round': round_no,
                    'tool_name': func_name,
                    'arguments': raw_arguments,
                },
            )

    def _prepare_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = [dict(message) for message in messages]
        if not result or result[0].get('role') != 'system':
            result.insert(0, {'role': 'system', 'content': self.system_prompt})
        return result

    def _get_chat_create_param_names(self, client: Any) -> set[str] | None:
        if self._chat_create_param_names is not None:
            return self._chat_create_param_names
        create_method = getattr(getattr(getattr(client, 'chat', None), 'completions', None), 'create', None)
        if create_method is None:
            return None
        try:
            self._chat_create_param_names = set(inspect.signature(create_method).parameters.keys())
        except (TypeError, ValueError):
            self._chat_create_param_names = None
        return self._chat_create_param_names

    def _adapt_inference_kwargs(self, client: Any, inference_kwargs: dict[str, Any]) -> dict[str, Any]:
        supported = self._get_chat_create_param_names(client)
        if not supported:
            adapted = dict(inference_kwargs)
            extra_body = dict(adapted.pop('extra_body', {}) or {})
            for key in ('repetition_penalty', 'reasoning'):
                if key in adapted:
                    extra_body[key] = adapted.pop(key)
            if extra_body:
                adapted['extra_body'] = extra_body
            return adapted
        adapted: dict[str, Any] = {}
        extra_body = dict(inference_kwargs.get('extra_body') or {})
        for key, value in inference_kwargs.items():
            if key == 'extra_body':
                continue
            if key in supported:
                adapted[key] = value
                continue
            extra_body[key] = value
        if extra_body:
            adapted['extra_body'] = extra_body
        return adapted

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

    def _count_words(self, text: str) -> int:
        return len(_WORD_RE.findall(text))

    def _extract_reasoning_details(self, delta: Any) -> list[dict[str, Any]]:
        model_extra = getattr(delta, 'model_extra', None) or {}
        details = getattr(delta, 'reasoning_details', None) or model_extra.get('reasoning_details')
        if not details:
            return []
        result: list[dict[str, Any]] = []
        for item in details:
            if hasattr(item, 'model_dump'):
                result.append(item.model_dump(exclude_none=True))
                continue
            if isinstance(item, dict):
                result.append(dict(item))
                continue
            raw = {
                key: value
                for key, value in vars(item).items()
                if not key.startswith('_') and value is not None
            }
            if raw:
                result.append(raw)
        return result

    def _flatten_reasoning_details(self, reasoning_details: list[dict[str, Any]]) -> str:
        parts: list[str] = []
        for item in reasoning_details:
            reasoning_type = item.get('type')
            if reasoning_type == 'reasoning.text' and item.get('text'):
                parts.append(str(item['text']))
                continue
            if reasoning_type == 'reasoning.summary':
                summary = item.get('summary')
                if isinstance(summary, list):
                    parts.extend(str(part) for part in summary if part)
                elif summary:
                    parts.append(str(summary))
        return ''.join(parts)

    def _extract_reasoning_text(self, delta: Any) -> str:
        model_extra = getattr(delta, 'model_extra', None) or {}
        direct = (
            getattr(delta, 'reasoning', None)
            or getattr(delta, 'reasoning_content', None)
            or model_extra.get('reasoning')
            or model_extra.get('reasoning_content')
        )
        if direct:
            return str(direct)
        reasoning_details = self._extract_reasoning_details(delta)
        return self._flatten_reasoning_details(reasoning_details)

    def _stage_log(self, *, round_no: int, stage: str, detail: str | None = None, interrupted: bool = False) -> None:
        if self._log_handle is None:
            return
        payload: dict[str, Any] = {
            'round': round_no,
            'stage': stage,
            'interrupted': interrupted,
            'tool_flags': dict(self.tool_context.flags),
        }
        if detail:
            payload['detail'] = detail
        self.runtime.logger.append_event(self._log_handle, 'stage', payload)

    def _log_new_messages(self, messages: list[dict[str, Any]]) -> None:
        if self._log_handle is None:
            return
        if self._logged_message_count >= len(messages):
            return
        self.runtime.logger.append_messages(
            self._log_handle,
            messages,
            start_index=self._logged_message_count,
        )
        self._logged_message_count = len(messages)

    def _start_lifecycle_log(self, prepared_messages: list[dict[str, Any]]) -> None:
        self._log_handle = self.runtime.logger.start_agent_lifecycle(
            group='scheduler' if self.agent_type == 'scheduler' else 'executor',
            agent_name=self.name,
            metadata={
                'workspace': str(self.workspace),
                'model': self.model,
                'agent_type': self.agent_type,
            },
        )
        self._logged_message_count = 0
        self._log_new_messages(prepared_messages)

    def _close_lifecycle_log(self, *, summary: dict[str, Any]) -> None:
        if self._log_handle is None:
            return
        self.runtime.logger.end_agent_lifecycle(self._log_handle, summary=summary)
        self._log_handle = None

    async def _process_stream(self, messages: list[dict[str, Any]], round_no: int) -> StreamResult:
        if self.runtime.cancel_event.is_set():
            raise AgentInterrupted('用户中断')
        self._emit_state(STATE_WAITING_RESPONSE, round_no)
        await self.runtime.request_manager.acquire()
        stream = None
        try:
            client = self.client_factory.get_client()
            request_kwargs: dict[str, Any] = {
                'model': self.model,
                'messages': messages,
                'tools': self.tool_schemas,
                'tool_choice': 'auto',
                'stream': True,
            }
            request_kwargs.update(
                self._adapt_inference_kwargs(client, self.inference.to_request_kwargs())
            )
            stream = await client.chat.completions.create(**request_kwargs)
            content = ''
            reasoning_content = ''
            reasoning_details: list[dict[str, Any]] = []
            tool_calls: list[dict[str, Any]] = []
            finish_reason = None
            emitted_thinking = False
            emitted_output = False
            emitted_tool_call = False
            async for chunk in stream:
                if self.runtime.cancel_event.is_set():
                    await self._safe_close_stream(stream)
                    raise AgentInterrupted('用户中断')
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                if choice.finish_reason:
                    finish_reason = choice.finish_reason
                delta = choice.delta
                delta_reasoning_details = self._extract_reasoning_details(delta)
                reasoning_text = self._extract_reasoning_text(delta)
                if delta_reasoning_details:
                    reasoning_details.extend(delta_reasoning_details)
                if reasoning_text:
                    if not emitted_thinking:
                        self._emit_state(STATE_REASONING, round_no)
                        emitted_thinking = True
                    reasoning_content += reasoning_text
                    self._emit_stream(round_no, 'reasoning', reasoning_text)
                if delta.tool_calls:
                    if not emitted_tool_call:
                        self._emit_state(STATE_TOOL_CALLING, round_no)
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
                if delta.content:
                    if not emitted_output:
                        self._emit_state(STATE_OUTPUT, round_no)
                        emitted_output = True
                    content += delta.content
                    self._emit_stream(round_no, 'output', delta.content)
                    if self.agent_type == 'executor' and not emitted_tool_call and self._count_words(content) > EXECUTOR_OUTPUT_WORD_LIMIT:
                        await self._safe_close_stream(stream)
                        return StreamResult(
                            content='输出过长',
                            reasoning_content=reasoning_content,
                            reasoning_details=reasoning_details,
                            tool_calls=[],
                            finish_reason=STATE_OUTPUT_TOO_LONG,
                            output_too_long=True,
                        )
            return StreamResult(
                content=content,
                reasoning_content=reasoning_content,
                reasoning_details=reasoning_details,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
            )
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
            self._log_new_messages(messages)
            if self.tool_context.flags.get('terminate_after_tool'):
                return False
        return True

    async def run(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        prepared_messages = self._prepare_messages(messages)
        round_no = 0
        interrupted = False
        self.runtime.register_agent(self.name)
        self._start_lifecycle_log(prepared_messages)
        self._emit_state(STATE_STARTED, 0)
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
                    assistant_message['reasoning'] = stream_result.reasoning_content
                    assistant_message['reasoning_content'] = stream_result.reasoning_content
                if stream_result.reasoning_details:
                    assistant_message['reasoning_details'] = stream_result.reasoning_details
                if stream_result.tool_calls:
                    assistant_message['tool_calls'] = [
                        {'id': item['id'], 'type': item['type'], 'function': item['function']}
                        for item in stream_result.tool_calls
                    ]
                prepared_messages.append(assistant_message)
                self._log_new_messages(prepared_messages)
                self._stage_log(
                    round_no=round_no,
                    stage='assistant_message',
                    interrupted=interrupted,
                    detail=stream_result.finish_reason,
                )
                if stream_result.output_too_long:
                    self._emit_state(STATE_OUTPUT_TOO_LONG, round_no, f'单轮普通输出超过 {EXECUTOR_OUTPUT_WORD_LIMIT} 词')
                    break
                should_continue = await self._process_tool_calls(prepared_messages, stream_result.tool_calls, round_no)
                self._stage_log(
                    round_no=round_no,
                    stage='round_complete',
                    interrupted=interrupted,
                    detail=stream_result.finish_reason,
                )
                if not should_continue:
                    break
            final_detail = None
            if self.agent_type == 'executor' and self.tool_context.flags.get('submitted'):
                final_detail = 'submitted'
            self._emit_state(STATE_FINISHED, round_no, final_detail)
            return prepared_messages
        except AgentInterrupted as exc:
            interrupted = True
            detail = str(exc)
            self._emit_state(STATE_INTERRUPTED, round_no, detail)
            self._stage_log(round_no=round_no, stage='interrupted', interrupted=interrupted, detail=detail)
            return prepared_messages
        except Exception as exc:
            detail = str(exc)
            self._emit_state(STATE_ERROR, round_no, detail)
            prepared_messages.append({'role': 'assistant', 'content': f'Agent 运行失败: {detail}'})
            self._log_new_messages(prepared_messages)
            self._stage_log(round_no=round_no, stage='error', interrupted=interrupted, detail=detail)
            return prepared_messages
        finally:
            self.last_run_flags = dict(self.tool_context.flags)
            self._close_lifecycle_log(
                summary={
                    'rounds': round_no,
                    'interrupted': interrupted,
                    'tool_flags': dict(self.tool_context.flags),
                }
            )
            self.runtime.unregister_agent(self.name)
