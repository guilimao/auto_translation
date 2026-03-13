"""
TeX编译器模块，用于将TeX字符串编译为图像
"""

import os
import tempfile
import shutil
import subprocess
import base64
from pathlib import Path
from typing import Union, Tuple


def compile_tex_to_image(tex_file_path: Union[str, Path]) -> Union[Tuple[bytes, str], Tuple[None, str]]:
    """
    将TeX文件编译为图像
    
    参数:
        tex_file_path: TeX文件的路径（字符串或Path对象）
        
    返回:
        成功时返回 (图像字节数据, 成功消息)
        失败时返回 (None, 错误信息)
    """
    tex_file_path = Path(tex_file_path)
    
    # 检查文件是否存在
    if not tex_file_path.exists():
        return None, f"TeX文件不存在: {tex_file_path}"
    
    # 创建临时目录
    temp_dir = tempfile.mkdtemp(prefix="tex_compile_")
    temp_tex_path = Path(temp_dir) / "document.tex"
    pdf_file_path = Path(temp_dir) / "document.pdf"
    
    try:
        # 读取原始TeX文件内容
        tex_content = tex_file_path.read_text(encoding='utf-8')
        
        # 写入临时TeX文件
        temp_tex_path.write_text(tex_content, encoding='utf-8')
        
        # 获取项目根目录下的fonts目录绝对路径
        script_dir = Path(__file__).parent.parent
        fonts_dir = script_dir / "fonts"
        
        # 确保fonts目录存在
        fonts_dir.mkdir(exist_ok=True)
        
        # 使用Docker运行TeX Live编译
        # 挂载临时目录到容器的/work目录
        # 挂载fonts目录到容器的/fonts目录
        # 使用 lualatex 引擎并设置 OSFONTDIR 指向 fonts 目录
        docker_cmd = [
            "docker", "run", "--rm",
            "-v", f"{temp_dir}:/work",
            "-v", f"{fonts_dir}:/fonts:ro",
            "-e", "OSFONTDIR=/fonts",          # 添加字体搜索路径
            "-w", "/work",
            "texlive/texlive:latest-full",
            "sh", "-c",
            "luaotfload-tool --update --force && lualatex -interaction=nonstopmode -halt-on-error document.tex"
        ]
        # 执行编译命令，捕获输出
        result = subprocess.run(
            docker_cmd,
            capture_output=True,
            text=True,
            timeout=1800
        )
        
        # 检查编译是否成功
        if result.returncode != 0 or not pdf_file_path.exists():
            # 编译失败，返回错误信息
            error_msg = f"TeX编译失败:\n{result.stdout}\n{result.stderr}"
            return None, error_msg
        
        # 编译成功，将PDF转换为图像 
        try:
            import fitz  # PyMuPDF
            
            doc = fitz.open(str(pdf_file_path))
            page = doc[0]
            
            # 设置缩放比例，提高清晰度
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat)
            
            img_bytes = pix.tobytes("png")
            doc.close()
            
            return img_bytes, "编译成功"
            
        except ImportError:
            return None, "缺少PDF转图像的依赖库，请安装 pdf2image 或 PyMuPDF"
    
    except subprocess.TimeoutExpired:
        return None, "TeX编译超时"
    
    except Exception as e:
        return None, f"处理过程中发生错误: {str(e)}"
    
    finally:
        # 清理临时目录
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass


def compile_tex_to_image_base64(tex_file_path: Union[str, Path]) -> Union[Tuple[str, str], Tuple[None, str]]:
    """
    将TeX文件编译为Base64编码的图像
    
    参数:
        tex_file_path: TeX文件的路径（字符串或Path对象）
        
    返回:
        成功时返回 (base64图像数据, 成功消息)
        失败时返回 (None, 错误信息)
    """
    image_data, message = compile_tex_to_image(tex_file_path)
    
    if image_data is None:
        return None, message
    
    base64_data = base64.b64encode(image_data).decode('utf-8')
    return base64_data, message


def tex_compiler(tex_file_path: str) -> str:
    """
    将TeX文件编译为图像，返回JSON格式的结果
    
    参数:
        tex_file_path: TeX文件的路径
        
    返回格式:
        成功: {"type": "image", "data": "base64数据", "format": "png", "message": "编译成功"}
        失败: {"type": "error", "message": "错误信息"}
    """
    import json
    
    base64_data, message = compile_tex_to_image_base64(tex_file_path)
    
    if base64_data is None:
        return json.dumps({
            "type": "error",
            "message": message
        })
    
    return json.dumps({
        "type": "image",
        "data": base64_data,
        "format": "png",
        "message": message
    })