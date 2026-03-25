"""
PDF转图像工具 - 使用PyMuPDF将PDF文件转换为PNG图像
"""

import os
import fitz  # PyMuPDF
from datetime import datetime
from pathlib import Path
from typing import Union, Dict, List, Any


def get_project_root() -> Path:
    """获取项目根目录"""
    # 从当前文件向上查找，找到包含pyproject.toml的目录
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    # 如果没找到，返回当前文件所在目录的父目录（tools的父目录）
    return Path(__file__).resolve().parent.parent


def pdf_to_image(pdf_path: str) -> Union[str, Dict[str, Any]]:
    """
    将PDF文件转换为PNG图像
    
    Args:
        pdf_path: PDF文件的路径
        
    Returns:
        成功时返回输出文件夹的路径字符串
        失败时返回包含错误信息的字典:
        {
            "type": "error",
            "message": "错误信息"
        }
    """
    try:
        # 检查PDF文件是否存在
        if not os.path.exists(pdf_path):
            return {
                "type": "error",
                "message": f"PDF文件不存在: {pdf_path}"
            }
        
        # 检查是否为文件
        if not os.path.isfile(pdf_path):
            return {
                "type": "error",
                "message": f"路径不是文件: {pdf_path}"
            }
        
        # 检查文件扩展名
        if not pdf_path.lower().endswith('.pdf'):
            return {
                "type": "error",
                "message": f"文件不是PDF格式: {pdf_path}"
            }
        
        # 获取PDF文件名（不含扩展名）
        pdf_name = Path(pdf_path).stem
        
        # 生成时间戳
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 创建输出目录: workspaces/{pdf文件名}_{时间戳}/
        project_root = get_project_root()
        output_dir = project_root / "workspaces" / f"{pdf_name}_{timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 打开PDF文件
        pdf_document = fitz.open(pdf_path)
        
        # 获取总页数
        total_pages = len(pdf_document)
        
        if total_pages == 0:
            pdf_document.close()
            return {
                "type": "error",
                "message": f"PDF文件没有页面: {pdf_path}"
            }
        
        # 转换每一页为PNG图像
        for page_num in range(total_pages):
            # 获取页面
            page = pdf_document[page_num]
            
            # 将页面渲染为图像（使用默认DPI）
            pix = page.get_pixmap()
            
            # 生成输出文件名: {pdf文件名}_第{页数}页.png
            output_filename = f"{pdf_name}_第{page_num + 1}页.png"
            output_path = output_dir / output_filename
            
            # 保存图像
            pix.save(str(output_path))
            
            # 清理pixmap资源
            pix = None
        
        # 关闭PDF文档
        pdf_document.close()
        
        # 返回输出文件夹路径
        return str(output_dir)
        
    except Exception as e:
        return {
            "type": "error",
            "message": f"PDF转图像失败: {str(e)}"
        }


# 工具定义（供LLM识别）
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "pdf_to_image",
        "description": "将PDF文件转换为PNG图像。使用PyMuPDF将输入的PDF文件转换为原始尺寸的PNG图像，输出保存到项目根目录下的work文件夹中，每次调用会创建一个新的文件名+时间戳子文件夹。每张图像以文件名+所在页数的格式命名。",
        "parameters": {
            "type": "object",
            "properties": {
                "pdf_path": {
                    "type": "string",
                    "description": "要转换的PDF文件路径"
                }
            },
            "required": ["pdf_path"]
        }
    }
}

