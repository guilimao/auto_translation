"""
工具配置模块，包含所有工具的Schema定义
"""

# ========== 工具定义 ==========

TOOLS = [
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
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "列出目录的树状结构。当同一层级项目过多时，总输出量控制在2000字符内。如果目录中存在.gitignore文件，将自动跳过其中指定的文件和目录。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要列出的目录路径（默认为当前目录）",
                    },
                    "depth": {
                        "type": "integer",
                        "description": "展开目录的层数，默认值为0，代表全部展开，1代表只展开当前目录下一层，2代表展开两层，以此类推",
                    },
                    "blacklist": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "黑名单，用于排除文件名中含有特定字符的项，可以用来滤除结果中无关的干扰项，默认值为.git文件夹",
                    },
                    "whitelist": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "白名单，用于仅保留文件名中含有特定字符的项，可用于在目录下查找指定文件",
                    }
                },
                "required": [],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_image",
            "description": "读取一个图像文件，输入图像路径，将图像编码为base64格式返回，可用于分析图像内容。支持jpg、jpeg、png、gif、bmp、webp、tiff、svg等格式。",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "图像文件的路径"
                    }
                },
                "required": ["image_path"],
            },
        }
    },
]
