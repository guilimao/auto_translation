import os
import base64
import mimetypes
import io
from typing import Union, Dict, List, Any
from PIL import Image


def read_image(image_path: str, max_size: int = 1920) -> Dict[str, Any]:
    """
    读取一个图像文件，将其编码为base64格式返回。如果图像尺寸超过指定大小，将自动缩放。
    
    Args:
        image_path: 图像文件的路径
        max_size: 图像长宽的最大像素值，默认为1920
        
    Returns:
        包含图像信息的字典，格式为OpenAI SDK兼容的消息内容格式:
        {
            "type": "image_content",
            "content": [
                {"type": "text", "text": "原始图像尺寸: 宽x高像素"},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
            ],
            "mime_type": "image/jpeg",
            "filename": "example.jpg"
        }
        如果读取失败，返回包含错误信息的字典:
        {
            "type": "error",
            "message": "错误信息"
        }
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(image_path):
            return {
                "type": "error",
                "message": f"图像文件不存在: {image_path}"
            }
        
        # 检查是否为文件
        if not os.path.isfile(image_path):
            return {
                "type": "error",
                "message": f"路径不是文件: {image_path}"
            }
        
        # 获取MIME类型
        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type:
            # 根据扩展名确定MIME类型
            ext = os.path.splitext(image_path)[1].lower()
            mime_map = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.bmp': 'image/bmp',
                '.webp': 'image/webp',
                '.tiff': 'image/tiff',
                '.svg': 'image/svg+xml'
            }
            mime_type = mime_map.get(ext, 'image/jpeg')
        
        # 检查是否为支持的图像类型
        if not mime_type.startswith('image/'):
            return {
                "type": "error",
                "message": f"不支持的文件类型: {mime_type}，请提供图像文件"
            }
        
        # 使用PIL打开图像以获取尺寸信息和进行缩放
        try:
            with Image.open(image_path) as img:
                original_width, original_height = img.size
                original_size_text = f"原始图像尺寸: {original_width}x{original_height}像素"
                
                # 检查是否需要缩放
                if original_width > max_size or original_height > max_size:
                    # 计算缩放比例，保持宽高比
                    ratio = min(max_size / original_width, max_size / original_height)
                    new_width = int(original_width * ratio)
                    new_height = int(original_height * ratio)
                    
                    # 缩放图像
                    img_resized = img.resize((new_width, new_height), Image.LANCZOS)
                    
                    # 将缩放后的图像保存到内存
                    buffer = io.BytesIO()
                    # 根据原始格式保存，如果原始格式是RGBA且目标是JPEG，需要转换
                    if img.mode in ('RGBA', 'LA', 'P') and mime_type == 'image/jpeg':
                        img_resized = img_resized.convert('RGB')
                    img_resized.save(buffer, format=img.format if img.format else 'PNG')
                    image_data = buffer.getvalue()
                else:
                    # 不需要缩放，直接读取原文件
                    with open(image_path, 'rb') as image_file:
                        image_data = image_file.read()
        except Exception as e:
            # 如果PIL处理失败，回退到直接读取文件
            with open(image_path, 'rb') as image_file:
                image_data = image_file.read()
            original_size_text = "无法获取原始图像尺寸"
        
        # 编码图像数据
        encoded_string = base64.b64encode(image_data).decode('utf-8')
        
        # 构建data URL
        data_url = f"data:{mime_type};base64,{encoded_string}"
        
        # 获取文件名
        filename = os.path.basename(image_path)
        
        # 返回OpenAI SDK格式的消息内容数组
        return {
            "type": "image_content",
            "content": [
                {
                    "type": "text",
                    "text": original_size_text
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": data_url
                    }
                }
            ],
            "mime_type": mime_type,
            "filename": filename
        }
        
    except Exception as e:
        return {
            "type": "error",
            "message": f"读取图像失败: {str(e)}"
        }


# 工具定义（供LLM识别）
TOOL_SCHEMA = {
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
            "required": ["image_path"]
        }
    }
}

