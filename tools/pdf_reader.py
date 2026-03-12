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
        
        # 获取页面原始尺寸（以点为单位的矩形，1点 = 1/72英寸）
        rect = page.rect
        original_width = rect.width  # 宽度（点）
        original_height = rect.height  # 高度（点）
        
        # 转换为英寸和毫米（72点 = 1英寸）
        width_inch = original_width / 72.0
        height_inch = original_height / 72.0
        width_mm = width_inch * 25.4
        height_mm = height_inch * 25.4
        
        # 计算横竖比例（宽高比）
        aspect_ratio = original_width / original_height
        
        # 判断横竖方向
        if aspect_ratio > 1:
            orientation = "横向"
        elif aspect_ratio < 1:
            orientation = "纵向"
        else:
            orientation = "正方形"
        
        # 计算缩放比例：72 DPI是PDF的默认分辨率，所以缩放因子 = dpi / 72
        zoom_factor = dpi / 72.0
        mat = fitz.Matrix(zoom_factor, zoom_factor)
        
        # 将页面渲染为图像
        pix = page.get_pixmap(matrix=mat)
        
        # 获取渲染后的图像分辨率（像素）
        rendered_width = pix.width
        rendered_height = pix.height
        
        # 获取PNG格式的图像字节
        img_bytes = pix.tobytes("png")
        
        # 关闭文档
        doc.close()
        
        # 转换为Base64
        base64_data = base64.b64encode(img_bytes).decode('utf-8')
        
        # 构建页面尺寸信息文本（用于OpenAI SDK的text字段）
        size_info_text = (
            f"PDF第{page_number}页（共{total_pages}页）的页面尺寸信息：\n"
            f"- 原始分辨率（PDF点数）: {original_width:.1f} × {original_height:.1f} pt\n"
            f"- 物理尺寸: {width_inch:.2f}英寸 × {height_inch:.2f}英寸 ({width_mm:.1f} × {height_mm:.1f} mm)\n"
            f"- 宽高比例: {aspect_ratio:.3f}（{orientation}）\n"
            f"- 渲染后像素: {rendered_width} × {rendered_height} px @ {dpi} DPI"
        )
        
        return json.dumps({
            "type": "image",
            "data": base64_data,
            "format": "png",
            "current_page": page_number,
            "total_pages": total_pages,
            "text": size_info_text
        })
        
    except Exception as e:
        return json.dumps({
            "type": "error",
            "message": f"❌ PDF读取失败: {str(e)}"
        })
