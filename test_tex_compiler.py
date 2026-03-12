"""
tex_compiler.py 模块的测试脚本
使用 hanja_translation.tex 和 fonts\NotoSansCJK-VF.otf.ttc 进行编译测试
"""

import sys
from pathlib import Path

# 将 tools 目录添加到路径
sys.path.insert(0, str(Path(__file__).parent / "tools"))

from tex_compiler import (
    compile_tex_to_image,
    compile_tex_to_image_base64,
    tex_compiler,
    get_font_path
)


def test_get_font_path():
    """测试获取字体路径功能"""
    print("=" * 60)
    print("测试 1: get_font_path()")
    print("=" * 60)
    
    font_path = get_font_path("NotoSansCJK-VF.otf.ttc")
    print(f"字体路径: {font_path}")
    assert font_path == "/usr/share/fonts/custom/NotoSansCJK-VF.otf.ttc"
    print("✓ 测试通过\n")


def test_compile_tex_to_image():
    """测试将TeX文件编译为图像字节数据"""
    print("=" * 60)
    print("测试 2: compile_tex_to_image()")
    print("=" * 60)
    
    tex_file = "hanja_translation.tex"
    print(f"编译文件: {tex_file}")
    print("正在编译，请稍候... (可能需要1-3分钟)")
    
    image_data, message = compile_tex_to_image(tex_file)
    
    if image_data is None:
        print(f"✗ 编译失败: {message}")
        return False
    
    print(f"编译结果: {message}")
    print(f"图像大小: {len(image_data)} 字节")
    print(f"图像前20字节 (十六进制): {image_data[:20].hex()}")
    
    # 保存图像文件用于查看
    output_file = "test_output_compile.png"
    with open(output_file, "wb") as f:
        f.write(image_data)
    print(f"✓ 图像已保存到: {output_file}\n")
    return True


def test_compile_tex_to_image_base64():
    """测试将TeX文件编译为Base64编码的图像"""
    print("=" * 60)
    print("测试 3: compile_tex_to_image_base64()")
    print("=" * 60)
    
    tex_file = "hanja_translation.tex"
    print(f"编译文件: {tex_file}")
    print("正在编译，请稍候...")
    
    base64_data, message = compile_tex_to_image_base64(tex_file)
    
    if base64_data is None:
        print(f"✗ 编译失败: {message}")
        return False
    
    print(f"编译结果: {message}")
    print(f"Base64 编码长度: {len(base64_data)} 字符")
    print(f"Base64 前100字符: {base64_data[:100]}...")
    print("✓ 测试通过\n")
    return True


def test_tex_compiler_json():
    """测试返回JSON格式的编译结果"""
    print("=" * 60)
    print("测试 4: tex_compiler() - JSON 格式输出")
    print("=" * 60)
    
    tex_file = "hanja_translation.tex"
    print(f"编译文件: {tex_file}")
    print("正在编译，请稍候...")
    
    result = tex_compiler(tex_file)
    
    import json
    data = json.loads(result)
    
    if data["type"] == "error":
        print(f"✗ 编译失败: {data['message']}")
        return False
    
    print(f"结果类型: {data['type']}")
    print(f"图像格式: {data['format']}")
    print(f"消息: {data['message']}")
    print(f"Base64 数据长度: {len(data['data'])} 字符")
    print(f"Base64 前100字符: {data['data'][:100]}...")
    print("✓ 测试通过\n")
    return True


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("TeX Compiler 测试套件")
    print("=" * 60 + "\n")
    
    # 测试 1: get_font_path
    test_get_font_path()
    
    # 测试 2: compile_tex_to_image
    test_compile_tex_to_image()
    
    # 测试 3: compile_tex_to_image_base64
    test_compile_tex_to_image_base64()
    
    # 测试 4: tex_compiler (JSON格式)
    test_tex_compiler_json()
    
    print("=" * 60)
    print("所有测试执行完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
