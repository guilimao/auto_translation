"""
文本替换工具模块
"""

import os


# 工具定义（供LLM识别）
TOOL_SCHEMA = {
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
}


def replace(file_path, replacements):
    """在文件中查找并替换文本内容"""
    try:
        if not os.path.exists(file_path):
            return f"❌ 文件不存在: {file_path}"
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        modified = False
        for repl in replacements:
            search = repl.get('search', '')
            replacement = repl.get('replacement', '')
            if search in content:
                content = content.replace(search, replacement)
                modified = True
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        if modified:
            return f"✅ 文件已成功更新: {file_path}"
        else:
            return f"⚠️ 文件未修改（未找到匹配内容）: {file_path}"
    except Exception as e:
        return f"❌ 替换失败: {str(e)}"
