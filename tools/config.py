"""
工具配置模块，从各个工具文件导入工具Schema定义
"""

# 从各个工具模块导入工具定义
from .read_file import TOOL_SCHEMA as READ_FILE_SCHEMA
from .write_file import TOOL_SCHEMA as WRITE_FILE_SCHEMA
from .replace import TOOL_SCHEMA as REPLACE_SCHEMA
from .typst_compiler import TOOL_SCHEMA as TYPST_COMPILER_SCHEMA
from .directory_list import TOOL_SCHEMA as LIST_DIRECTORY_SCHEMA
from .image_tools import TOOL_SCHEMA as READ_IMAGE_SCHEMA
from .pdf_to_image import TOOL_SCHEMA as PDF_TO_IMAGE_SCHEMA
from .font_list import TOOL_SCHEMA as FONT_LIST_SCHEMA
from .crop_image import TOOL_SCHEMA as CROP_IMAGE_SCHEMA

# 工具定义列表（供LLM识别）
TOOLS = [
    READ_FILE_SCHEMA,
    WRITE_FILE_SCHEMA,
    REPLACE_SCHEMA,
    TYPST_COMPILER_SCHEMA,
    LIST_DIRECTORY_SCHEMA,
    READ_IMAGE_SCHEMA,
    PDF_TO_IMAGE_SCHEMA,
    FONT_LIST_SCHEMA,
    CROP_IMAGE_SCHEMA,
]
