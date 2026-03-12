"""
TeX文件编译器（带GUI文件对话框）
通过文件对话框选择TeX文件，调用Docker编译，将PDF输出保存到原文件夹
"""

import os
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from datetime import datetime


def select_tex_file() -> str | None:
    """
    打开文件对话框，让用户选择TeX文件
    
    返回:
        选中的文件路径，如果用户取消则返回None
    """
    # 创建主窗口（隐藏）
    root = tk.Tk()
    root.withdraw()
    
    # 打开文件对话框
    file_path = filedialog.askopenfilename(
        title="选择TeX文件",
        filetypes=[
            ("TeX文件", "*.tex"),
            ("所有文件", "*.*")
        ]
    )
    
    root.destroy()
    
    return file_path if file_path else None


def compile_tex_with_docker(tex_file_path: Path) -> tuple[bool, str]:
    """
    使用Docker编译TeX文件
    
    参数:
        tex_file_path: TeX文件的路径
        
    返回:
        (是否成功, 消息/错误信息)
    """
    # 获取文件所在目录和文件名
    tex_dir = tex_file_path.parent
    tex_filename = tex_file_path.name
    tex_stem = tex_file_path.stem  # 不带扩展名的文件名
    
    # 构建输出PDF的路径
    output_pdf = tex_dir / f"{tex_stem}.pdf"
    
    # Docker编译命令
    # 挂载tex文件所在目录到容器的/work目录
    docker_cmd = [
        "docker", "run", "--rm",
        "-v", f"{tex_dir}:/work",
        "-w", "/work",
        "texlive/texlive:latest-full",
        "xelatex",
        "-interaction=nonstopmode",
        "-halt-on-error",
        f"/work/{tex_filename}"
    ]
    
    try:
        print(f"开始编译: {tex_file_path}")
        print(f"执行命令: {' '.join(docker_cmd)}")
        print("-" * 50)
        
        # 执行编译命令，实时输出
        process = subprocess.Popen(
            docker_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        
        # 实时输出编译日志
        output_lines = []
        for line in process.stdout:
            print(line, end='')
            output_lines.append(line)
        
        process.wait()
        
        print("-" * 50)
        
        # 检查编译结果
        if process.returncode != 0:
            return False, f"编译失败，Docker返回码: {process.returncode}"
        
        # 检查PDF是否生成
        # Docker中生成的PDF可能在当前工作目录（即挂载的目录）
        generated_pdf = tex_dir / f"{tex_stem}.pdf"
        
        if not generated_pdf.exists():
            # 有时Docker生成的PDF文件名可能不同，查找最近的PDF文件
            pdf_files = list(tex_dir.glob("*.pdf"))
            if pdf_files:
                # 找到最近修改的PDF文件
                latest_pdf = max(pdf_files, key=lambda p: p.stat().st_mtime)
                # 重命名为期望的文件名
                latest_pdf.rename(generated_pdf)
            else:
                return False, "编译完成，但未找到生成的PDF文件"
        
        return True, str(generated_pdf)
        
    except subprocess.TimeoutExpired:
        return False, "编译超时（超过30分钟）"
    except FileNotFoundError:
        return False, "未找到Docker命令，请确保Docker已安装并添加到系统PATH"
    except Exception as e:
        return False, f"编译过程中发生错误: {str(e)}"


def compile_tex_multiple_passes(tex_file_path: Path, passes: int = 2) -> tuple[bool, str]:
    """
    多次编译TeX文件（用于处理交叉引用等问题）
    
    参数:
        tex_file_path: TeX文件的路径
        passes: 编译次数，默认2次
        
    返回:
        (是否成功, 消息/错误信息)
    """
    tex_dir = tex_file_path.parent
    tex_filename = tex_file_path.name
    
    for i in range(passes):
        print(f"\n>>> 第 {i + 1}/{passes} 次编译...")
        
        docker_cmd = [
            "docker", "run", "--rm",
            "-v", f"{tex_dir}:/work",
            "-w", "/work",
            "texlive/texlive:latest-full",
            "xelatex",
            "-interaction=nonstopmode",
            "-halt-on-error",
            f"/work/{tex_filename}"
        ]
        
        try:
            process = subprocess.Popen(
                docker_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='ignore'
            )
            
            output_lines = []
            for line in process.stdout:
                print(line, end='')
                output_lines.append(line)
            
            process.wait()
            
            if process.returncode != 0:
                return False, f"第{i + 1}次编译失败"
                
        except Exception as e:
            return False, f"编译过程中发生错误: {str(e)}"
    
    # 检查最终PDF
    tex_stem = tex_file_path.stem
    generated_pdf = tex_dir / f"{tex_stem}.pdf"
    
    if generated_pdf.exists():
        return True, str(generated_pdf)
    else:
        return False, "多次编译完成，但未找到生成的PDF文件"


def main():
    """主函数"""
    print("=" * 60)
    print("TeX文件编译器 (Docker + XeLaTeX)")
    print("=" * 60)
    print()
    
    # 选择文件
    print("请选择要编译的TeX文件...")
    file_path = select_tex_file()
    
    if not file_path:
        print("未选择文件，程序退出")
        return
    
    tex_file = Path(file_path)
    print(f"已选择文件: {tex_file}")
    print()
    
    # 确认编译
    result = messagebox.askyesno(
        "确认编译",
        f"是否编译以下文件?\n\n{tex_file}\n\n" +
        f"输出将保存到: {tex_file.parent}"
    )
    
    if not result:
        print("用户取消编译")
        return
    
    # 选择编译模式
    compile_mode = messagebox.askyesno(
        "编译模式",
        "是否需要多次编译（用于处理交叉引用、目录等）?\n\n" +
        "是 = 编译2次\n否 = 编译1次"
    )
    
    # 执行编译
    if compile_mode:
        success, message = compile_tex_multiple_passes(tex_file, passes=2)
    else:
        success, message = compile_tex_with_docker(tex_file)
    
    print()
    print("=" * 60)
    
    if success:
        output_path = Path(message)
        file_size = output_path.stat().st_size / 1024  # KB
        print(f"✓ 编译成功!")
        print(f"✓ PDF文件: {output_path}")
        print(f"✓ 文件大小: {file_size:.2f} KB")
        messagebox.showinfo(
            "编译成功",
            f"PDF文件已生成!\n\n" +
            f"路径: {output_path}\n" +
            f"大小: {file_size:.2f} KB"
        )
    else:
        print(f"✗ 编译失败!")
        print(f"✗ 错误信息: {message}")
        messagebox.showerror(
            "编译失败",
            f"编译过程中出现错误:\n\n{message}"
        )
    
    print("=" * 60)
    input("\n按回车键退出...")


if __name__ == "__main__":
    main()
