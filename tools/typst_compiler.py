"""
Typst 编译工具模块 - 使用 Docker 编译 Typst 文件

输入参数:
- file_path: Typst 文件路径
- format: 输出格式 (pdf, png, svg)
- output_name: 输出文件名模板
  * PDF: 无限制
  * PNG/SVG: 必须包含 {p}(页码) 或 {0p}(补零页码), 可包含 {t}(总页数)

输出:
- 保存到项目根目录/outputs/文件名_时间戳/ 文件夹
- 返回编译输出流（最后2000字符）和输出文件夹路径
"""

import os
import re
import subprocess
from datetime import datetime
from pathlib import Path


# 工具定义（供LLM识别）
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "typst_compiler",
        "description": "使用 Docker 编译 Typst 文件，支持输出 PDF、PNG、SVG 格式。输出保存到项目根目录下的 outputs 文件夹中，每次调用会创建一个新的时间戳文件夹。",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "要编译的 Typst 文件路径"
                },
                "format": {
                    "type": "string",
                    "description": "输出格式: pdf、png 或 svg",
                    "enum": ["pdf", "png", "svg"]
                },
                "output_name": {
                    "type": "string",
                    "description": "输出文件名模板。PDF无限制；PNG和SVG必须包含{p}(页码)或{0p}(补零页码)，可包含{t}显示总页数。示例: output-{p}-of-{t}.png, page-{0p}.svg"
                }
            },
            "required": ["file_path", "format", "output_name"]
        }
    }
}


def typst_compiler(file_path: str, format: str, output_name: str) -> str:
    """
    使用 Docker 编译 Typst 文件
    
    参数:
        file_path: Typst 文件路径
        format: 输出格式 (pdf, png, svg)
        output_name: 输出文件名模板
    
    返回:
        JSON 格式的结果，包含输出信息和输出文件夹路径
    """
    # 验证参数
    valid_formats = ["pdf", "png", "svg"]
    format = format.lower().strip()
    if format not in valid_formats:
        return f"❌ 不支持的输出格式: {format}。支持的格式: {', '.join(valid_formats)}"
    
    # 验证输入文件
    if not os.path.exists(file_path):
        return f"❌ Typst 文件不存在: {file_path}"
    
    # 验证 PNG/SVG 文件名模板
    if format in ["png", "svg"]:
        if "{p}" not in output_name and "{0p}" not in output_name:
            return f"❌ PNG/SVG 输出文件名必须包含 {{p}}(页码) 或 {{0p}}(补零页码) 模板"
    
    # 获取项目根目录（当前文件的上两级目录）
    project_root = Path(__file__).parent.parent.absolute()
    
    # 创建输出目录: outputs/文件名_时间戳/
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    input_filename = Path(file_path).stem
    output_dir_name = f"{input_filename}_{timestamp}"
    output_dir = project_root / "outputs" / output_dir_name
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 准备挂载路径（Docker 需要 Unix 风格路径）
    fonts_dir = project_root / "fonts"
    
    # 检查 fonts 目录是否存在
    if not fonts_dir.exists():
        return f"❌ Fonts 目录不存在: {fonts_dir}"
    
    # 将 Windows 路径转换为 Docker 可用的路径格式
    def to_docker_path(path: Path) -> str:
        """将 Windows 路径转换为 Docker 挂载格式"""
        abs_path = str(path.absolute())
        # Windows 路径如 C:\path\to\dir 转换为 /c/path/to/dir
        if abs_path[1:2] == ":":
            drive = abs_path[0].lower()
            rest = abs_path[2:].replace("\\", "/")
            return f"/{drive}{rest}"
        return abs_path.replace("\\", "/")
    
    # 构建 Docker 命令
    docker_cmd = [
        "docker", "run", "--rm",
        "-v", f"{to_docker_path(fonts_dir)}:/fonts:ro",
        "-v", f"{to_docker_path(output_dir)}:/output",
        "-v", f"{to_docker_path(Path(file_path).parent)}:/workdir:ro",
        "ghcr.io/typst/typst:latest",
        "compile",
        "--font-path", "/fonts",
    ]
    
    # 添加格式参数
    docker_cmd.extend(["--format", format])
    
    # 构建输出文件路径
    output_file = f"/output/{output_name}"
    
    # 添加输入和输出文件
    input_filename_only = Path(file_path).name
    docker_cmd.extend([f"/workdir/{input_filename_only}", output_file])
    
    # 执行命令
    try:
        result = subprocess.run(
            docker_cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=300  # 5分钟超时
        )
        
        # 构建输出信息
        output_lines = []
        
        if result.stdout:
            output_lines.append("=== 标准输出 ===")
            output_lines.append(result.stdout)
        
        if result.stderr:
            output_lines.append("=== 错误输出 ===")
            output_lines.append(result.stderr)
        
        # 获取返回码信息
        if result.returncode != 0:
            output_lines.append(f"=== 编译失败 (返回码: {result.returncode}) ===")
        else:
            output_lines.append("=== 编译成功 ===")
            # 列出输出文件
            output_files = list(output_dir.iterdir())
            if output_files:
                output_lines.append("生成的文件:")
                for f in output_files:
                    size = f.stat().st_size
                    output_lines.append(f"  - {f.name} ({size:,} bytes)")
        
        full_output = "\n".join(output_lines)
        
        # 只保留最后2000个字符
        if len(full_output) > 2000:
            truncated_output = "... (前面内容已省略) ...\n" + full_output[-1900:]
        else:
            truncated_output = full_output
        
        # 构建返回结果
        result_dict = {
            "success": result.returncode == 0,
            "output": truncated_output,
            "output_dir": str(output_dir),
            "command": " ".join(docker_cmd)
        }
        
        import json
        return json.dumps(result_dict, ensure_ascii=False, indent=2)
        
    except subprocess.TimeoutExpired:
        return json.dumps({
            "success": False,
            "output": "❌ 编译超时 (超过5分钟)",
            "output_dir": str(output_dir),
            "command": " ".join(docker_cmd)
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({
            "success": False,
            "output": f"❌ 执行编译命令时出错: {str(e)}",
            "output_dir": str(output_dir),
            "command": " ".join(docker_cmd)
        }, ensure_ascii=False, indent=2)
