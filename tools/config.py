"""
工具配置模块，包含所有工具的Schema定义
"""

# ========== 工具定义 ==========

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "tex_compiler",
            "description": "将TeX文件编译为PDF并转换为图像，返回Base64编码的图像数据。用于可视化查看TeX渲染结果",
            "parameters": {
                "type": "object",
                "properties": {
                    "tex_file_path": {"type": "string", "description": "要编译的TeX文件路径"}
                },
                "required": ["tex_file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取文本文件的内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {"type": "string", "description": "要读取的文件路径"}
                },
                "required": ["file_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "创建新文件或更新现有文件内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {"type": "string", "description": "目标文件路径"},
                    "file_content": {"type": "string", "description": "文件内容"}
                },
                "required": ["file_name", "file_content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "replace",
            "description": "在文件中查找并替换文本内容，支持一次执行多个替换操作",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "文件路径"},
                    "replacements": {
                        "type": "array",
                        "description": "替换规则数组",
                        "items": {
                            "type": "object",
                            "properties": {
                                "search": {"type": "string", "description": "要查找的文本"},
                                "replacement": {"type": "string", "description": "要替换成的文本"}
                            },
                            "required": ["search", "replacement"]
                        }
                    }
                },
                "required": ["file_path", "replacements"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "pdf_reader",
            "description": "读取PDF文件，将指定页面转换为图像并返回Base64编码的图像数据，供模型查看PDF内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "pdf_path": {"type": "string", "description": "PDF文件的路径"},
                    "page_number": {"type": "integer", "description": "要转换的页码（从1开始，默认为第1页）"},
                    "dpi": {"type": "integer", "description": "图像分辨率（默认200，越高越清晰但文件越大）"}
                },
                "required": ["pdf_path"]
            }
        }
    },
]
