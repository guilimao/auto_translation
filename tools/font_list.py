"""
字体列表工具模块 - 使用 Docker 列出 Typst 可用字体

输出:
- 返回 JSON 格式的字体列表（包含所有可用字体）
"""

import subprocess
import json
from pathlib import Path


# 工具定义（供LLM识别）
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "font_list",
        "description": "列出 Typst 所有可用的字体列表。",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
}


def to_docker_path(path: Path) -> str:
    """将 Windows 路径转换为 Docker 挂载格式"""
    abs_path = str(path.absolute())
    # Windows 路径如 C:\path\to\dir 转换为 /c/path/to/dir
    if abs_path[1:2] == ":":
        drive = abs_path[0].lower()
        rest = abs_path[2:].replace("\\", "/")
        return f"/{drive}{rest}"
    return abs_path.replace("\\", "/")


def font_list() -> str:
    """
    使用 Docker 列出 Typst 可用字体

    返回:
        JSON 格式的结果，包含所有可用字体列表
    """
    # 获取项目根目录（当前文件的上两级目录）
    project_root = Path(__file__).parent.parent.absolute()

    # 准备挂载路径（Docker 需要 Unix 风格路径）
    fonts_dir = project_root / "fonts"

    # 检查 fonts 目录是否存在
    if not fonts_dir.exists():
        return json.dumps({
            "success": False,
            "error": f"Fonts 目录不存在: {fonts_dir}",
            "fonts": []
        }, ensure_ascii=False, indent=2)

    # 构建 Docker 命令
    docker_cmd = [
        "docker", "run", "--rm",
        "-v", f"{to_docker_path(fonts_dir)}:/fonts:ro",
        "ghcr.io/typst/typst:latest",
        "fonts",
        "--font-path", "/fonts",
    ]

    # 执行命令
    try:
        result = subprocess.run(
            docker_cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=60  # 1分钟超时
        )

        if result.returncode != 0:
            return json.dumps({
                "success": False,
                "error": result.stderr or "未知错误",
                "fonts": [],
                "command": " ".join(docker_cmd)
            }, ensure_ascii=False, indent=2)

        # 解析字体列表
        fonts = []
        for line in result.stdout.strip().split('\n'):
            line = line.strip()
            if line:
                fonts.append(line)

        return json.dumps({
            "success": True,
            "count": len(fonts),
            "fonts": fonts,
            "command": " ".join(docker_cmd)
        }, ensure_ascii=False, indent=2)

    except subprocess.TimeoutExpired:
        return json.dumps({
            "success": False,
            "error": "❌ 获取字体列表超时 (超过1分钟)",
            "fonts": [],
            "command": " ".join(docker_cmd)
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"❌ 执行字体列表命令时出错: {str(e)}",
            "fonts": [],
            "command": " ".join(docker_cmd)
        }, ensure_ascii=False, indent=2)