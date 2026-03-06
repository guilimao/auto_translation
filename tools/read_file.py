"""
读取文件工具模块
"""

import os


def read_file(file_name):
    """读取文本文件内容"""
    try:
        if not os.path.exists(file_name):
            return f"❌ 文件不存在: {file_name}"
        
        with open(file_name, 'r', encoding='utf-8') as f:
            content = f.read()
        return content
    except Exception as e:
        return f"❌ 读取文件失败: {str(e)}"
