"""
图像裁剪工具，根据BBOX框截取图像的特定区域
"""

import os
import base64
import io
import re
from datetime import datetime
from typing import Union, Dict, List, Any, Tuple
from PIL import Image


def resize_to_max_size(img: Image.Image, max_size: int, allow_upscale: bool = True) -> Image.Image:
    """
    将图像缩放到指定最大尺寸。
    
    参数:
        img: PIL图像对象
        max_size: 最大尺寸（长或宽）
        allow_upscale: 是否允许放大（True时小于max_size会放大，False时保持原样）
    
    返回:
        缩放后的图像对象
    """
    width, height = img.size
    
    # 如果图像已经在限制范围内且不允许放大，直接返回
    if not allow_upscale and width <= max_size and height <= max_size:
        return img
    
    # 计算缩放比例，使长宽均不超过max_size
    ratio = min(max_size / width, max_size / height)
    
    # 只有当需要缩放时才执行（避免不必要的重采样）
    if ratio < 1.0 or (ratio > 1.0 and allow_upscale):
        new_width = int(width * ratio)
        new_height = int(height * ratio)
        return img.resize((new_width, new_height), Image.LANCZOS)
    
    return img


def crop_image(image_path: str, bbox: List[int]) -> Dict[str, Any]:
    """
    根据BBOX框截取图像的特定区域并保存。
    
    输入参数：
        image_path: 图片路径
        bbox: BBOX框，格式为[x1, x2, y1, y2]，数值取0-999之间，为相对坐标
              例如 [100, 500, 200, 800] 表示从(10%, 20%)到(50%, 80%)的区域
    
    返回值：
        包含截取图像信息和base64编码的字典，格式与read_image一致:
        {
            "type": "image_content",
            "content": [
                {"type": "text", "text": "原始图像尺寸: 宽x高像素"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
            ],
            "mime_type": "image/png",
            "filename": "cropped_image.png"
        }
        如果执行失败，返回包含错误信息的字典:
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
        
        # 验证bbox参数
        if not isinstance(bbox, list) or len(bbox) != 4:
            return {
                "type": "error",
                "message": f"bbox参数格式错误，应为包含4个整数的列表，当前: {bbox}"
            }
        
        x1, x2, y1, y2 = bbox
        
        # 验证坐标范围
        if not all(0 <= coord <= 999 for coord in [x1, x2, y1, y2]):
            return {
                "type": "error",
                "message": f"bbox坐标必须在0-999之间，当前: {bbox}"
            }
        
        # 确保坐标顺序正确（x1 < x2, y1 < y2）
        if x1 >= x2 or y1 >= y2:
            return {
                "type": "error",
                "message": f"bbox坐标顺序错误，需要满足x1 < x2且y1 < y2，当前: {bbox}"
            }
        
        max_size = 1920
        
        # 打开图像
        with Image.open(image_path) as img:
            input_width, input_height = img.size
            
            # 输入图像处理：大于1920则缩小，小于1920则放大到尽可能大但不超过1920
            processed_img = resize_to_max_size(img, max_size, allow_upscale=True)
            processed_width, processed_height = processed_img.size
            
            # 将相对坐标(0-999)转换为处理后的图像的像素坐标
            pixel_x1 = int(processed_width * x1 / 999)
            pixel_x2 = int(processed_width * x2 / 999)
            pixel_y1 = int(processed_height * y1 / 999)
            pixel_y2 = int(processed_height * y2 / 999)
            
            # 确保坐标不越界
            pixel_x1 = max(0, min(pixel_x1, processed_width))
            pixel_x2 = max(0, min(pixel_x2, processed_width))
            pixel_y1 = max(0, min(pixel_y1, processed_height))
            pixel_y2 = max(0, min(pixel_y2, processed_height))
            
            # 裁剪图像
            cropped_img = processed_img.crop((pixel_x1, pixel_y1, pixel_x2, pixel_y2))
            cropped_width, cropped_height = cropped_img.size
            
            # 构建输出文件名：图片路径（去除非法字符）+ 时间戳
            # 清理原文件名，只保留字母数字和下划线
            base_name = os.path.basename(image_path)
            name_without_ext = os.path.splitext(base_name)[0]
            safe_name = re.sub(r'[^\w\-]', '_', name_without_ext)
            
            # 生成时间戳
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 构建输出路径
            output_filename = f"{safe_name}_{timestamp}.png"
            work_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "work")
            os.makedirs(work_dir, exist_ok=True)
            output_path = os.path.join(work_dir, output_filename)
            
            # 保存原始裁剪图像（未缩放的版本）
            # 计算原始图像上的裁剪坐标
            orig_pixel_x1 = int(input_width * x1 / 999)
            orig_pixel_x2 = int(input_width * x2 / 999)
            orig_pixel_y1 = int(input_height * y1 / 999)
            orig_pixel_y2 = int(input_height * y2 / 999)
            
            # 确保坐标不越界
            orig_pixel_x1 = max(0, min(orig_pixel_x1, input_width))
            orig_pixel_x2 = max(0, min(orig_pixel_x2, input_width))
            orig_pixel_y1 = max(0, min(orig_pixel_y1, input_height))
            orig_pixel_y2 = max(0, min(orig_pixel_y2, input_height))
            
            # 从原始图像裁剪（保持原始尺寸）
            original_cropped = img.crop((orig_pixel_x1, orig_pixel_y1, orig_pixel_x2, orig_pixel_y2))
            original_cropped.save(output_path, format="PNG")
            original_cropped_width, original_cropped_height = original_cropped.size
            
            # 返回图像处理：大于1920则缩小，小于1920则保持不变
            display_img = resize_to_max_size(cropped_img, max_size, allow_upscale=False)
            display_width, display_height = display_img.size
            
            # 将图像转换为base64
            buffer = io.BytesIO()
            # 转换为RGB模式（如果必要）
            if display_img.mode in ('RGBA', 'LA', 'P'):
                display_img_rgb = display_img.convert('RGB')
            else:
                display_img_rgb = display_img
            display_img_rgb.save(buffer, format='PNG')
            image_data = buffer.getvalue()
            encoded_string = base64.b64encode(image_data).decode('utf-8')
            
            # 构建data URL
            data_url = f"data:image/png;base64,{encoded_string}"
            
            # 构建返回信息
            info_text = f"图像截取成功！\n" \
                       f"原始图像尺寸: {input_width}x{input_height}像素\n" \
                       f"处理后图像尺寸（用于裁剪）: {processed_width}x{processed_height}像素\n" \
                       f"截取区域（相对坐标）: [{x1}, {x2}, {y1}, {y2}]\n" \
                       f"截取区域（像素坐标）: ({pixel_x1}, {pixel_y1}) - ({pixel_x2}, {pixel_y2})\n" \
                       f"原始裁剪图像尺寸: {original_cropped_width}x{original_cropped_height}像素\n" \
                       f"返回图像尺寸: {display_width}x{display_height}像素\n" \
                       f"保存路径: {output_path}"
            
            return {
                "type": "image_content",
                "content": [
                    {
                        "type": "text",
                        "text": info_text
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": data_url
                        }
                    }
                ],
                "mime_type": "image/png",
                "filename": output_filename
            }
            
    except Exception as e:
        return {
            "type": "error",
            "message": f"裁剪图像失败: {str(e)}"
        }


# 工具定义（供LLM识别）
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "crop_image",
        "description": "根据BBOX框截取图像的特定区域，将框内的部分截取下来，以PNG图像的形式保存到项目根目录下的work文件夹。输入的bbox是相对坐标（0-999），返回值包含截取图像的原始长宽信息和缩放后的图像。",
        "parameters": {
            "type": "object",
            "properties": {
                "image_path": {
                    "type": "string",
                    "description": "图片路径"
                },
                "bbox": {
                    "type": "array",
                    "description": "BBOX框，格式为[x1, x2, y1, y2]，数值取0-999之间，为相对坐标。例如[100, 500, 200, 800]表示从(10%, 20%)到(50%, 80%)的区域",
                    "items": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 999
                    },
                    "minItems": 4,
                    "maxItems": 4
                }
            },
            "required": ["image_path", "bbox"]
        }
    }
}

