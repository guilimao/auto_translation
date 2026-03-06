"""
Tools模块 - 提供各种工具函数的集合

包含以下工具：
- tex_compiler: 将TeX文件编译为PDF并转换为图像
- read_file: 读取文本文件内容
- write_file: 创建或更新文件内容
- replace: 在文件中查找并替换文本
- pdf_reader: 读取PDF文件并转换为图像

使用方式:
    from tools import TOOLS, execute_tool, process_tool_calls
    
    # 获取工具定义（用于API调用）
    tools = TOOLS
    
    # 执行单个工具
    result = execute_tool(tool_call)
    
    # 处理多个工具调用
    should_continue = process_tool_calls(messages, tool_calls)
"""

# 导出工具配置
from .config import TOOLS

# 导出各个工具函数（供直接使用）
from .tex_compiler import tex_compiler
from .read_file import read_file
from .write_file import write_file
from .replace import replace
from .pdf_reader import pdf_reader

# 导出执行器函数
from .executor import execute_tool, process_tool_calls, TOOL_FUNCTIONS

__all__ = [
    # 工具定义
    "TOOLS",
    # 工具函数映射
    "TOOL_FUNCTIONS",
    # 单个工具函数
    "tex_compiler",
    "read_file",
    "write_file",
    "replace",
    "pdf_reader",
    # 执行器函数
    "execute_tool",
    "process_tool_calls",
]
