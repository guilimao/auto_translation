from __future__ import annotations

import asyncio
import base64
import io
import json
import mimetypes
import re
import shutil
from pathlib import Path
from typing import Any, Awaitable, Callable

import fitz
from PIL import Image

from .base import ToolContext, ToolSpec
from .directory_list import list_directory as raw_list_directory
from .helpers import (
    AgentInterrupted,
    dump_json,
    extract_page_number,
    find_page_workspaces,
    is_text_file,
    join_output,
    resolve_path,
    run_subprocess,
    timestamp,
    to_docker_path,
    to_thread,
)


def _allowed_root(ctx: ToolContext) -> Path:
    return ctx.runtime.project_root



def _image_content(image_bytes: bytes, mime_type: str, filename: str, text: str) -> dict[str, Any]:
    encoded_string = base64.b64encode(image_bytes).decode('utf-8')
    return {
        'type': 'image_content',
        'content': [
            {'type': 'text', 'text': text},
            {'type': 'image_url', 'image_url': {'url': f'data:{mime_type};base64,{encoded_string}'}},
        ],
        'mime_type': mime_type,
        'filename': filename,
    }


async def tool_list_directory(ctx: ToolContext, path: str = '.', depth: int = 2, blacklist=None, whitelist=None) -> str:
    resolved = resolve_path(
        path,
        ctx.default_root,
        fallback_inputs=ctx.runtime.inputs_dir if ctx.agent_type == 'scheduler' else None,
        allowed_root=_allowed_root(ctx),
    )
    return await to_thread(raw_list_directory, str(resolved), depth, blacklist, whitelist)


async def tool_read_file(ctx: ToolContext, file_path: str) -> str:
    resolved = resolve_path(
        file_path,
        ctx.default_root,
        fallback_inputs=ctx.runtime.inputs_dir if ctx.agent_type == 'scheduler' else None,
        allowed_root=_allowed_root(ctx),
    )
    if not resolved.exists():
        return f'❌ 文件不存在: {resolved}'
    if resolved.is_dir():
        return f'❌ 路径是目录而不是文件: {resolved}'
    if not is_text_file(resolved):
        return f'❌ 当前工具只读取文本文件: {resolved.name}'
    return await to_thread(resolved.read_text, encoding='utf-8')


async def tool_write_file(ctx: ToolContext, file_path: str, content: str) -> str:
    resolved = resolve_path(file_path, ctx.default_root, allowed_root=_allowed_root(ctx))
    resolved.parent.mkdir(parents=True, exist_ok=True)
    await to_thread(resolved.write_text, content, encoding='utf-8')
    return f'✅ 文件已写入: {resolved}'


async def tool_replace(ctx: ToolContext, file_path: str, replacements: list[dict[str, str]]) -> str:
    resolved = resolve_path(file_path, ctx.default_root, allowed_root=_allowed_root(ctx))
    if not resolved.exists():
        return f'❌ 文件不存在: {resolved}'
    content = await to_thread(resolved.read_text, encoding='utf-8')
    modified = False
    for item in replacements:
        src = item.get('search', '')
        dst = item.get('replacement', '')
        if src and src in content:
            content = content.replace(src, dst)
            modified = True
    await to_thread(resolved.write_text, content, encoding='utf-8')
    return f'✅ 文件已更新: {resolved}' if modified else f'⚠️ 未发生替换: {resolved}'


async def tool_read_image(ctx: ToolContext, image_path: str, max_size: int = 1920) -> dict[str, Any]:
    resolved = resolve_path(
        image_path,
        ctx.default_root,
        fallback_inputs=ctx.runtime.inputs_dir if ctx.agent_type == 'scheduler' else None,
        allowed_root=_allowed_root(ctx),
    )
    if not resolved.exists():
        return {'type': 'error', 'message': f'图像文件不存在: {resolved}'}
    mime_type, _ = mimetypes.guess_type(str(resolved))
    mime_type = mime_type or 'image/png'

    def _read() -> dict[str, Any]:
        with Image.open(resolved) as img:
            original_width, original_height = img.size
            display = img.copy()
            if original_width > max_size or original_height > max_size:
                ratio = min(max_size / original_width, max_size / original_height)
                display = display.resize((int(original_width * ratio), int(original_height * ratio)), Image.LANCZOS)
            buffer = io.BytesIO()
            save_format = img.format or 'PNG'
            if display.mode in ('RGBA', 'LA', 'P') and save_format.upper() == 'JPEG':
                display = display.convert('RGB')
            display.save(buffer, format=save_format)
            return _image_content(
                buffer.getvalue(),
                mime_type,
                resolved.name,
                f'原始图像尺寸: {original_width}x{original_height} 像素\n文件路径: {resolved}',
            )

    return await to_thread(_read)


async def tool_crop_image(ctx: ToolContext, image_path: str, bbox: list[int], output_name: str | None = None) -> dict[str, Any]:
    resolved = resolve_path(image_path, ctx.default_root, allowed_root=_allowed_root(ctx))
    if not resolved.exists():
        return {'type': 'error', 'message': f'图像文件不存在: {resolved}'}
    if len(bbox) != 4:
        return {'type': 'error', 'message': 'bbox 必须为 [x1, x2, y1, y2]'}
    x1, x2, y1, y2 = bbox
    if not all(0 <= value <= 999 for value in bbox) or x1 >= x2 or y1 >= y2:
        return {'type': 'error', 'message': f'bbox 非法: {bbox}'}
    crops_dir = ctx.workspace / 'crops'
    crops_dir.mkdir(parents=True, exist_ok=True)
    output_name = output_name or f'crop_{timestamp()}.png'
    output_path = crops_dir / output_name

    def _crop() -> dict[str, Any]:
        with Image.open(resolved) as img:
            width, height = img.size
            left = int(width * x1 / 999)
            right = int(width * x2 / 999)
            top = int(height * y1 / 999)
            bottom = int(height * y2 / 999)
            cropped = img.crop((left, top, right, bottom))
            cropped.save(output_path, format='PNG')
            buffer = io.BytesIO()
            preview = cropped.copy()
            max_preview = 1920
            if preview.width > max_preview or preview.height > max_preview:
                ratio = min(max_preview / preview.width, max_preview / preview.height)
                preview = preview.resize((int(preview.width * ratio), int(preview.height * ratio)), Image.LANCZOS)
            if preview.mode in ('RGBA', 'LA', 'P'):
                preview = preview.convert('RGB')
            preview.save(buffer, format='PNG')
            return _image_content(
                buffer.getvalue(),
                'image/png',
                output_path.name,
                f'已截取图像\n原图: {resolved.name}\n保存路径: {output_path}\n像素区域: ({left}, {top}) - ({right}, {bottom})',
            )

    return await to_thread(_crop)


async def tool_color_sample(ctx: ToolContext, image_path: str, x: int, y: int) -> str:
    resolved = resolve_path(image_path, ctx.default_root, allowed_root=_allowed_root(ctx))
    if not resolved.exists():
        return f'❌ 图像文件不存在: {resolved}'

    def _sample() -> str:
        with Image.open(resolved) as img:
            rgb = img.convert('RGB')
            width, height = rgb.size
            if not (1 <= x <= 1000 and 1 <= y <= 1000):
                raise ValueError('x 和 y 必须是 1-1000 的归一化相对坐标')
            px = round((x - 1) * (width - 1) / 999) if width > 1 else 0
            py = round((y - 1) * (height - 1) / 999) if height > 1 else 0
            r, g, b = rgb.getpixel((px, py))
            return dump_json(
                {
                    'image_path': str(resolved),
                    'relative_point_1_1000': [x, y],
                    'pixel_point': [px, py],
                    'rgb_255': [r, g, b],
                    'srgb': [round(r / 255, 4), round(g / 255, 4), round(b / 255, 4)],
                    'hex': f'#{r:02X}{g:02X}{b:02X}',
                }
            )

    try:
        return await to_thread(_sample)
    except Exception as exc:
        return f'❌ 颜色采样失败: {exc}'


async def tool_pdf_to_image(ctx: ToolContext, pdf_path: str, dpi: int = 144) -> str:
    resolved = resolve_path(pdf_path, ctx.default_root, fallback_inputs=ctx.runtime.inputs_dir, allowed_root=_allowed_root(ctx))
    if not resolved.exists():
        return f'❌ PDF 文件不存在: {resolved}'
    if resolved.suffix.lower() != '.pdf':
        return f'❌ 文件不是 PDF: {resolved}'

    workspaces_dir = ctx.runtime.workspaces_dir
    for item in workspaces_dir.iterdir():
        if item.name == '.gitkeep':
            continue
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
        else:
            item.unlink(missing_ok=True)

    def _convert() -> str:
        doc = fitz.open(resolved)
        try:
            total_pages = len(doc)
            if total_pages == 0:
                return f'❌ PDF 没有页面: {resolved}'
            summary_lines = [f'PDF 已拆分: {resolved}', f'总页数: {total_pages}']
            for index in range(total_pages):
                page_no = index + 1
                workspace = workspaces_dir / f'page_{page_no:03d}'
                workspace.mkdir(parents=True, exist_ok=True)
                page = doc[index]
                matrix = fitz.Matrix(dpi / 72.0, dpi / 72.0)
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                image_path = workspace / 'source.png'
                pix.save(str(image_path))
                meta = {
                    'page_number': page_no,
                    'workspace': str(workspace),
                    'image_path': str(image_path),
                    'source_pdf': str(resolved),
                    'dpi': dpi,
                }
                (workspace / 'workspace_meta.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
                summary_lines.append(f'- 第 {page_no} 页 -> {workspace}')
            return '\n'.join(summary_lines)
        finally:
            doc.close()

    return await to_thread(_convert)


async def _compile_typst(*, project_root: Path, workdir: Path, file_path: Path, output_dir: Path, format: str, output_name: str) -> str:
    fonts_dir = project_root / 'fonts'
    if not fonts_dir.exists():
        return dump_json({'success': False, 'output': f'❌ Fonts 目录不存在: {fonts_dir}', 'output_dir': str(output_dir)})
    output_dir.mkdir(parents=True, exist_ok=True)
    docker_cmd = [
        'docker', 'run', '--rm',
        '-v', f'{to_docker_path(fonts_dir)}:/fonts:ro',
        '-v', f'{to_docker_path(output_dir)}:/output',
        '-v', f'{to_docker_path(workdir)}:/workdir',
        'ghcr.io/typst/typst:latest',
        'compile',
        '--font-path', '/fonts',
        '--format', format,
        f'/workdir/{file_path.name}',
        f'/output/{output_name}',
    ]

    def _run() -> str:
        try:
            returncode, stdout, stderr = run_subprocess(docker_cmd, timeout=300)
            files = [p.name for p in sorted(output_dir.iterdir())] if output_dir.exists() else []
            return dump_json(
                {
                    'success': returncode == 0,
                    'output': join_output(stdout, stderr, returncode),
                    'output_dir': str(output_dir),
                    'generated_files': files,
                    'command': ' '.join(docker_cmd),
                }
            )
        except Exception as exc:
            return dump_json(
                {
                    'success': False,
                    'output': f'❌ Typst 编译失败: {exc}',
                    'output_dir': str(output_dir),
                    'generated_files': [],
                    'command': ' '.join(docker_cmd),
                }
            )

    return await to_thread(_run)


async def tool_typst_compile(ctx: ToolContext, file_path: str, format: str = 'pdf', output_name: str | None = None) -> str:
    resolved = resolve_path(file_path, ctx.default_root, allowed_root=_allowed_root(ctx))
    if not resolved.exists():
        return f'❌ Typst 文件不存在: {resolved}'
    format = format.lower().strip()
    if format not in {'pdf', 'png', 'svg'}:
        return f'❌ 不支持的格式: {format}'
    if output_name is None:
        output_name = {'pdf': 'preview.pdf', 'png': 'preview-{0p}.png', 'svg': 'preview-{0p}.svg'}[format]
    if format in {'png', 'svg'} and '{p}' not in output_name and '{0p}' not in output_name:
        return f'❌ {format} 输出文件名必须包含 {{p}} 或 {{0p}}'
    return await _compile_typst(
        project_root=ctx.runtime.project_root,
        workdir=resolved.parent,
        file_path=resolved,
        output_dir=ctx.workspace / 'build',
        format=format,
        output_name=output_name,
    )


async def tool_typst_merge(ctx: ToolContext, output_name: str = 'translated_document.pdf') -> str:
    typ_files = sorted(
        [p for p in ctx.runtime.workspaces_dir.iterdir() if p.is_file() and p.suffix == '.typ' and re.fullmatch(r'page_\d+\.typ', p.name)],
        key=lambda p: extract_page_number(p.name),
    )
    if not typ_files:
        return '❌ workspaces 根目录下没有可合并的 Typst 页面文件'
    main_typ = ctx.runtime.workspaces_dir / 'main.typ'
    lines: list[str] = []
    for idx, typ_file in enumerate(typ_files):
        lines.append(f'#include "{typ_file.name}"')
        if idx != len(typ_files) - 1:
            lines.append('#pagebreak()')
    await to_thread(main_typ.write_text, '\n\n'.join(lines) + '\n', encoding='utf-8')
    output_dir = ctx.runtime.output_dir / f'merged_{timestamp()}'
    result = await _compile_typst(
        project_root=ctx.runtime.project_root,
        workdir=ctx.runtime.workspaces_dir,
        file_path=main_typ,
        output_dir=output_dir,
        format='pdf',
        output_name=output_name,
    )
    payload = json.loads(result)
    return dump_json(
        {
            'success': payload.get('success', False),
            'main_typ': str(main_typ),
            'output_dir': payload.get('output_dir'),
            'generated_files': payload.get('generated_files', []),
            'output': payload.get('output', ''),
        }
    )


async def tool_submit_result(ctx: ToolContext, file_path: str) -> str:
    resolved = resolve_path(file_path, ctx.default_root, allowed_root=_allowed_root(ctx))
    if not resolved.exists():
        return f'❌ 要提交的文件不存在: {resolved}'
    meta_path = ctx.workspace / 'workspace_meta.json'
    if not meta_path.exists():
        return '❌ workspace_meta.json 不存在，无法确定页码'
    meta = json.loads(await to_thread(meta_path.read_text, encoding='utf-8'))
    page_number = int(meta['page_number'])
    target = ctx.runtime.workspaces_dir / f'page_{page_number:03d}.typ'
    await to_thread(shutil.copy2, resolved, target)
    ctx.flags['submitted'] = True
    ctx.flags['submitted_target'] = str(target)
    ctx.flags['terminate_after_tool'] = True
    return f'✅ 结果已提交到 {target}，执行器会话已结束'


async def tool_create_executor(
    ctx: ToolContext,
    task_description: str,
    pages: list[int] | None,
    spawn_executor: Callable[[Path, str], Awaitable[dict[str, Any]]],
    max_parallel_agents: int,
) -> str:
    pages = pages or []
    workspaces = find_page_workspaces(ctx.runtime.workspaces_dir)
    if not workspaces:
        return '❌ 未发现页面工作区，请先调用 pdf_to_image'
    if pages:
        selected_numbers = set(pages)
        workspaces = [w for w in workspaces if extract_page_number(w.name) in selected_numbers]
        if not workspaces:
            return f'❌ 未找到指定页码的工作区: {pages}'
    semaphore = asyncio.Semaphore(max_parallel_agents)
    interrupted = False

    async def _run_one(workspace: Path) -> dict[str, Any]:
        nonlocal interrupted
        page_number = extract_page_number(workspace.name)
        async with semaphore:
            if ctx.runtime.cancel_event.is_set():
                interrupted = True
                return {'page': page_number, 'status': '用户中断', 'workspace': str(workspace)}
            try:
                return await spawn_executor(workspace, task_description)
            except AgentInterrupted:
                interrupted = True
                return {'page': page_number, 'status': '用户中断', 'workspace': str(workspace)}
            except Exception as exc:
                return {'page': page_number, 'status': f'执行失败: {exc}', 'workspace': str(workspace)}

    results = await asyncio.gather(*[_run_one(workspace) for workspace in workspaces], return_exceptions=False)
    if ctx.runtime.cancel_event.is_set():
        interrupted = True
        ctx.runtime.reset_interrupt()
    results = sorted(results, key=lambda item: item['page'])
    lines = ['执行器批量运行结果：']
    for item in results:
        lines.append(f"- 第 {item['page']} 页: {item['status']}")
        detail = item.get('detail')
        if detail and item['status'] != '运行成功':
            lines.append(f'  详情: {detail}')
    if interrupted:
        lines.append('- 本轮执行过程中收到用户中断信号，未完成页已标记为“用户中断”。')
    return '\n'.join(lines)


SCHEDULER_SCHEMAS = {
    'list_directory': {
        'type': 'function',
        'function': {
            'name': 'list_directory',
            'description': '列出目录树。调度器默认应优先查看 inputs、workspaces、output。',
            'parameters': {
                'type': 'object',
                'properties': {
                    'path': {'type': 'string', 'description': '目录路径，默认为当前项目根目录'},
                    'depth': {'type': 'integer', 'description': '展开深度，0 代表全部展开', 'default': 2},
                    'blacklist': {'type': 'array', 'items': {'type': 'string'}},
                    'whitelist': {'type': 'array', 'items': {'type': 'string'}},
                },
            },
        },
    },
    'pdf_to_image': {
        'type': 'function',
        'function': {
            'name': 'pdf_to_image',
            'description': '将 PDF 转换为页面图像，并在 workspaces 根目录下为每一页创建独立 workspace。',
            'parameters': {
                'type': 'object',
                'properties': {
                    'pdf_path': {'type': 'string', 'description': 'PDF 文件路径。相对路径默认相对项目根目录，找不到时会尝试 inputs/ 下同名文件。'},
                    'dpi': {'type': 'integer', 'description': '渲染 DPI，默认 144', 'default': 144},
                },
                'required': ['pdf_path'],
            },
        },
    },
    'read_image': {
        'type': 'function',
        'function': {
            'name': 'read_image',
            'description': '读取图像并以多模态消息返回。调用新的同类工具结果后，旧图像内容会被自动压缩。',
            'parameters': {
                'type': 'object',
                'properties': {
                    'image_path': {'type': 'string', 'description': '图像路径'},
                    'max_size': {'type': 'integer', 'description': '返回图像的最长边限制', 'default': 1920},
                },
                'required': ['image_path'],
            },
        },
    },
    'read_file': {
        'type': 'function',
        'function': {
            'name': 'read_file',
            'description': '读取文本文件。',
            'parameters': {'type': 'object', 'properties': {'file_path': {'type': 'string', 'description': '文本文件路径'}}, 'required': ['file_path']},
        },
    },
    'typst_merge': {
        'type': 'function',
        'function': {
            'name': 'typst_merge',
            'description': '扫描 workspaces 根目录下所有提交后的 Typst 页面，按页码顺序生成 main.typ 并编译到 output 文件夹。',
            'parameters': {'type': 'object', 'properties': {'output_name': {'type': 'string', 'description': '输出 PDF 文件名', 'default': 'translated_document.pdf'}}},
        },
    },
    'create_executor': {
        'type': 'function',
        'function': {
            'name': 'create_executor',
            'description': '按页码批量启动执行器 Agent。每个执行器处理一个页面 workspace。页码为空时处理全部页面。',
            'parameters': {
                'type': 'object',
                'properties': {
                    'task_description': {'type': 'string', 'description': '对执行器的任务描述'},
                    'pages': {'type': 'array', 'items': {'type': 'integer'}, 'description': '要处理的页码列表；为空时代表全部页'},
                },
                'required': ['task_description', 'pages'],
            },
        },
    },
}


EXECUTOR_SCHEMAS = {
    'list_directory': SCHEDULER_SCHEMAS['list_directory'],
    'read_image': SCHEDULER_SCHEMAS['read_image'],
    'crop_image': {
        'type': 'function',
        'function': {
            'name': 'crop_image',
            'description': '裁剪图像局部区域并返回预览，bbox 使用 0-999 的相对坐标 [x1, x2, y1, y2]。调用新的 crop_image 结果后，旧截图会被自动压缩。',
            'parameters': {
                'type': 'object',
                'properties': {
                    'image_path': {'type': 'string', 'description': '图像路径'},
                    'bbox': {'type': 'array', 'items': {'type': 'integer'}, 'description': '相对坐标 bbox'},
                    'output_name': {'type': 'string', 'description': '可选输出文件名'},
                },
                'required': ['image_path', 'bbox'],
            },
        },
    },
    'write_file': {
        'type': 'function',
        'function': {
            'name': 'write_file',
            'description': '默认在当前 workspace 内写入文件，但也允许显式指定项目目录内其他路径。',
            'parameters': {'type': 'object', 'properties': {'file_path': {'type': 'string'}, 'content': {'type': 'string'}}, 'required': ['file_path', 'content']},
        },
    },
    'replace': {
        'type': 'function',
        'function': {
            'name': 'replace',
            'description': '在文本文件中执行多组查找替换。',
            'parameters': {
                'type': 'object',
                'properties': {
                    'file_path': {'type': 'string', 'description': '文件路径'},
                    'replacements': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {'search': {'type': 'string'}, 'replacement': {'type': 'string'}},
                            'required': ['search', 'replacement'],
                        },
                    },
                },
                'required': ['file_path', 'replacements'],
            },
        },
    },
    'typst_compile': {
        'type': 'function',
        'function': {
            'name': 'typst_compile',
            'description': '编译 Typst 文件，输出默认写入当前 workspace/build。',
            'parameters': {
                'type': 'object',
                'properties': {
                    'file_path': {'type': 'string', 'description': 'Typst 文件路径'},
                    'format': {'type': 'string', 'enum': ['pdf', 'png', 'svg'], 'default': 'pdf'},
                    'output_name': {'type': 'string', 'description': '可选输出文件名模板'},
                },
                'required': ['file_path'],
            },
        },
    },
    'color_sample': {
        'type': 'function',
        'function': {
            'name': 'color_sample',
            'description': '采样图像指定位置的 sRGB 颜色。x/y 使用 1-1000 的归一化相对坐标。',
            'parameters': {
                'type': 'object',
                'properties': {'image_path': {'type': 'string'}, 'x': {'type': 'integer'}, 'y': {'type': 'integer'}},
                'required': ['image_path', 'x', 'y'],
            },
        },
    },
    'read_file': SCHEDULER_SCHEMAS['read_file'],
    'submit_result': {
        'type': 'function',
        'function': {
            'name': 'submit_result',
            'description': '将最终 Typst 文件提交到 workspaces 根目录，并立即结束当前执行器会话。',
            'parameters': {'type': 'object', 'properties': {'file_path': {'type': 'string', 'description': '要提交的 Typst 文件路径'}}, 'required': ['file_path']},
        },
    },
}



def create_scheduler_tools(*, spawn_executor: Callable[[Path, str], Awaitable[dict[str, Any]]], max_parallel_agents: int) -> list[ToolSpec]:
    return [
        ToolSpec('list_directory', SCHEDULER_SCHEMAS['list_directory'], tool_list_directory),
        ToolSpec('pdf_to_image', SCHEDULER_SCHEMAS['pdf_to_image'], tool_pdf_to_image),
        ToolSpec('read_image', SCHEDULER_SCHEMAS['read_image'], tool_read_image),
        ToolSpec('read_file', SCHEDULER_SCHEMAS['read_file'], tool_read_file),
        ToolSpec('typst_merge', SCHEDULER_SCHEMAS['typst_merge'], tool_typst_merge),
        ToolSpec(
            'create_executor',
            SCHEDULER_SCHEMAS['create_executor'],
            lambda ctx, task_description, pages: tool_create_executor(
                ctx,
                task_description,
                pages,
                spawn_executor=spawn_executor,
                max_parallel_agents=max_parallel_agents,
            ),
        ),
    ]



def create_executor_tools() -> list[ToolSpec]:
    return [
        ToolSpec('list_directory', EXECUTOR_SCHEMAS['list_directory'], tool_list_directory),
        ToolSpec('read_image', EXECUTOR_SCHEMAS['read_image'], tool_read_image),
        ToolSpec('crop_image', EXECUTOR_SCHEMAS['crop_image'], tool_crop_image),
        ToolSpec('write_file', EXECUTOR_SCHEMAS['write_file'], tool_write_file),
        ToolSpec('replace', EXECUTOR_SCHEMAS['replace'], tool_replace),
        ToolSpec('typst_compile', EXECUTOR_SCHEMAS['typst_compile'], tool_typst_compile),
        ToolSpec('color_sample', EXECUTOR_SCHEMAS['color_sample'], tool_color_sample),
        ToolSpec('read_file', EXECUTOR_SCHEMAS['read_file'], tool_read_file),
        ToolSpec('submit_result', EXECUTOR_SCHEMAS['submit_result'], tool_submit_result),
    ]
