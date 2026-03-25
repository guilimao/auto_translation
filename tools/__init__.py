"""
Tools模块 - 提供各种工具函数的集合

包含以下工具：
- read_file: 读取文本文件内容
- write_file: 创建或更新文件内容
- replace: 在文件中查找并替换文本
- typst_compiler: 使用Docker编译Typst文件
- list_directory: 列出目录的树状结构
- read_image: 读取图像文件并编码为base64
- pdf_to_image: 将PDF文件转换为PNG图像
- font_list: 列出Typst可用的字体列表
- crop_image: 根据BBOX框截取图像的特定区域

使用方式:
    from tools import TOOLS, execute_tool, process_tool_calls
    
    # 获取工具定义（用于API调用）
    tools = TOOLS
    
    # 执行单个工具
    result = execute_tool(tool_call)
    
    # 处理多个工具调用
    should_continue = process_tool_calls(messages, tool_calls)
"""

# 导出工具定义
from .config import TOOLS

# 导出各个工具函数（供直接使用）
from .read_file import read_file
from .write_file import write_file
from .replace import replace
from .typst_compiler import typst_compiler
from .directory_list import list_directory
from .image_tools import read_image
from .pdf_to_image import pdf_to_image
from .font_list import font_list
from .crop_image import crop_image

# 导出执行器函数
from .executor import execute_tool, process_tool_calls, TOOL_FUNCTIONS

__all__ = [
    # 工具定义
    "TOOLS",
    # 工具函数映射
    "TOOL_FUNCTIONS",
    # 单个工具函数
    "read_file",
    "write_file",
    "replace",
    "typst_compiler",
    "list_directory",
    "read_image",
    "pdf_to_image",
    "font_list",
    "crop_image",
    # 执行器函数
    "execute_tool",
    "process_tool_calls",
]
