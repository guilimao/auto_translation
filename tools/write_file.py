"""
写入文件工具模块
"""

import os


# 工具定义（供LLM识别）
TOOL_SCHEMA = {
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
}


def write_file(file_name, file_content):
    """创建新文件或更新现有文件内容"""
    try:
        # 确保目录存在
        dir_path = os.path.dirname(file_name)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path)
        
        with open(file_name, 'w', encoding='utf-8') as f:
            f.write(file_content)
        return f"✅ 文件已成功写入: {file_name}"
    except Exception as e:
        return f"❌ 写入文件失败: {str(e)}"
