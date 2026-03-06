"""
PDF读取工具模块，将PDF页面转换为图像
"""

import json
import base64
from pathlib import Path

# 尝试导入PyMuPDF (fitz)，用于PDF转图像
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False


def pdf_reader(pdf_path, page_number=1, dpi=200):
    """
    读取PDF文件，将指定页面转换为图像并返回Base64编码的图像数据
    
    参数:
        pdf_path: PDF文件路径
        page_number: 页码（从1开始，默认第1页）
        dpi: 图像分辨率（默认200）
    
    返回格式: {"type": "image", "data": "base64编码的图像数据", "format": "png"}
    """
    try:
        if not PYMUPDF_AVAILABLE:
            return json.dumps({
                "type": "error",
                "message": "❌ 缺少依赖库: 请安装 PyMuPDF (pip install PyMuPDF)"
            })
        
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            return json.dumps({
                "type": "error",
                "message": f"❌ PDF文件不存在: {pdf_path}"
            })
        
        # 验证文件扩展名
        if pdf_path.suffix.lower() != '.pdf':
            return json.dumps({
                "type": "error",
                "message": f"❌ 文件不是PDF格式: {pdf_path}"
            })
        
        # 使用PyMuPDF打开PDF
        doc = fitz.open(str(pdf_path))
        
        # 获取PDF总页数
        total_pages = len(doc)
        
        # 验证页码范围
        if page_number < 1 or page_number > total_pages:
            doc.close()
            return json.dumps({
                "type": "error",
                "message": f"❌ 页码超出范围: {page_number}（共{total_pages}页）"
            })
        
        # 获取指定页面（PyMuPDF使用0-based索引）
        page = doc[page_number - 1]
        
        # 计算缩放比例：72 DPI是PDF的默认分辨率，所以缩放因子 = dpi / 72
        zoom_factor = dpi / 72.0
        mat = fitz.Matrix(zoom_factor, zoom_factor)
        
        # 将页面渲染为图像
        pix = page.get_pixmap(matrix=mat)
        
        # 获取PNG格式的图像字节
        img_bytes = pix.tobytes("png")
        
        # 关闭文档
        doc.close()
        
        # 转换为Base64
        base64_data = base64.b64encode(img_bytes).decode('utf-8')
        
        return json.dumps({
            "type": "image",
            "data": base64_data,
            "format": "png",
            "current_page": page_number,
            "total_pages": total_pages,
            "message": f"✅ 成功读取PDF第{page_number}页（共{total_pages}页），分辨率{dpi} DPI"
        })
        
    except Exception as e:
        return json.dumps({
            "type": "error",
            "message": f"❌ PDF读取失败: {str(e)}"
        })
