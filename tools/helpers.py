from __future__ import annotations

import asyncio
import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path


TEXT_EXTENSIONS = {
    '.txt', '.md', '.typ', '.json', '.yaml', '.yml', '.csv', '.toml', '.log', '.html', '.css', '.js', '.py', '.svg'
}


class AgentInterrupted(Exception):
    pass



def ensure_directories(project_root: Path) -> None:
    for folder in ['inputs', 'workspaces', 'output', 'logs']:
        directory = project_root / folder
        directory.mkdir(parents=True, exist_ok=True)
        gitkeep = directory / '.gitkeep'
        if not gitkeep.exists():
            gitkeep.write_text('', encoding='utf-8')



def clean_workspaces(project_root: Path) -> None:
    workspaces = project_root / 'workspaces'
    workspaces.mkdir(parents=True, exist_ok=True)
    for item in workspaces.iterdir():
        if item.name == '.gitkeep':
            continue
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
        else:
            item.unlink(missing_ok=True)



def resolve_path(
    path_str: str,
    default_root: Path,
    *,
    fallback_inputs: Path | None = None,
    allowed_root: Path | None = None,
) -> Path:
    raw = Path(path_str)
    if raw.is_absolute():
        resolved = raw.resolve()
    else:
        candidate = (default_root / raw).resolve()
        if candidate.exists() or fallback_inputs is None:
            resolved = candidate
        else:
            alternative = (fallback_inputs / raw).resolve()
            resolved = alternative if alternative.exists() else candidate
    if allowed_root is not None:
        root_resolved = allowed_root.resolve()
        try:
            resolved.relative_to(root_resolved)
        except ValueError as exc:
            raise ValueError(f'路径超出允许范围: {resolved}') from exc
    return resolved



def is_text_file(path: Path) -> bool:
    return path.suffix.lower() in TEXT_EXTENSIONS


async def to_thread(func, /, *args, **kwargs):
    return await asyncio.to_thread(func, *args, **kwargs)



def to_docker_path(path: Path) -> str:
    abs_path = str(path.absolute())
    if len(abs_path) > 1 and abs_path[1:2] == ':':
        drive = abs_path[0].lower()
        rest = abs_path[2:].replace('\\', '/')
        return f'/{drive}{rest}'
    return abs_path.replace('\\', '/')



def extract_page_number(value: str) -> int:
    match = re.search(r'(\d+)', value)
    return int(match.group(1)) if match else 10**9



def dump_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)



def run_subprocess(cmd: list[str], *, timeout: int = 300) -> tuple[int, str, str]:
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
        timeout=timeout,
    )
    return result.returncode, result.stdout, result.stderr



def timestamp() -> str:
    return datetime.now().strftime('%Y%m%d_%H%M%S')



def join_output(stdout: str, stderr: str, returncode: int) -> str:
    parts: list[str] = []
    if stdout:
        parts.append('=== 标准输出 ===\n' + stdout)
    if stderr:
        parts.append('=== 错误输出 ===\n' + stderr)
    parts.append('=== 返回码 ===\n' + str(returncode))
    text = '\n'.join(parts).strip()
    if len(text) > 4000:
        return '... (前面内容已省略) ...\n' + text[-3800:]
    return text



def find_page_workspaces(workspaces_dir: Path) -> list[Path]:
    if not workspaces_dir.exists():
        return []
    candidates = [p for p in workspaces_dir.iterdir() if p.is_dir() and (p / 'workspace_meta.json').exists()]
    return sorted(candidates, key=lambda p: extract_page_number(p.name))



def truncate_text(text: str, limit: int = 500) -> str:
    text = (text or '').strip()
    if len(text) <= limit:
        return text or '无可用消息'
    return text[: max(0, limit - 12)].rstrip() + ' ...[已截断]'
