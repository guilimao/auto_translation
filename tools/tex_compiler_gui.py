"""
TeX编译器GUI版本，通过文件对话框选择TeX文件并编译为图像
"""

import os
import sys
import tempfile
import shutil
import subprocess
import base64
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path
from typing import Union, Optional
import threading
import queue


class TexCompilerGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("TeX 编译器")
        self.root.geometry("700x500")
        self.root.minsize(600, 400)
        
        # 设置样式
        self.style = ttk.Style()
        self.style.configure('TButton', padding=5)
        self.style.configure('TLabel', padding=5)
        
        # 当前选中的文件路径
        self.selected_file: Optional[Path] = None
        
        self._create_widgets()
        self._center_window()
    
    def _create_widgets(self):
        """创建GUI组件"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置grid权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        # 文件选择区域
        ttk.Label(main_frame, text="TeX 文件:").grid(row=0, column=0, sticky=tk.W)
        
        file_frame = ttk.Frame(main_frame)
        file_frame.grid(row=0, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        file_frame.columnconfigure(0, weight=1)
        
        self.file_path_var = tk.StringVar()
        self.file_entry = ttk.Entry(file_frame, textvariable=self.file_path_var, state='readonly')
        self.file_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        
        self.browse_btn = ttk.Button(file_frame, text="浏览...", command=self._browse_file)
        self.browse_btn.grid(row=0, column=1)
        
        # 输出路径显示
        ttk.Label(main_frame, text="输出位置:").grid(row=1, column=0, sticky=tk.W)
        self.output_path_var = tk.StringVar(value="（未选择文件）")
        ttk.Label(main_frame, textvariable=self.output_path_var, foreground="gray").grid(
            row=1, column=1, columnspan=2, sticky=tk.W
        )
        
        # 编译按钮
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=3, pady=10)
        
        self.compile_btn = ttk.Button(
            button_frame, 
            text="开始编译", 
            command=self._start_compile,
            width=20
        )
        self.compile_btn.pack(side=tk.LEFT, padx=5)
        
        self.clear_btn = ttk.Button(
            button_frame, 
            text="清除", 
            command=self._clear,
            width=15
        )
        self.clear_btn.pack(side=tk.LEFT, padx=5)
        
        # 日志输出区域
        ttk.Label(main_frame, text="编译日志:").grid(row=3, column=0, sticky=(tk.W, tk.N), pady=(5, 0))
        
        log_frame = ttk.Frame(main_frame)
        log_frame.grid(row=3, column=1, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame, 
            wrap=tk.WORD, 
            height=15,
            state='disabled',
            font=('Consolas', 10)
        )
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        self.status_bar = ttk.Label(
            main_frame, 
            textvariable=self.status_var, 
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(5, 2)
        )
        self.status_bar.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
    
    def _center_window(self):
        """将窗口居中显示"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
    
    def _browse_file(self):
        """打开文件选择对话框"""
        file_path = filedialog.askopenfilename(
            title="选择 TeX 文件",
            filetypes=[
                ("TeX 文件", "*.tex"),
                ("所有文件", "*.*")
            ]
        )
        
        if file_path:
            self.selected_file = Path(file_path)
            self.file_path_var.set(str(self.selected_file))
            
            # 显示输出路径
            output_path = self.selected_file.with_suffix('.png')
            self.output_path_var.set(str(output_path))
            
            self._log(f"已选择文件: {self.selected_file}")
            self._log(f"输出将保存至: {output_path}")
            self.status_var.set("文件已选择，准备编译")
    
    def _log(self, message: str):
        """向日志区域添加消息（线程安全）"""
        # 使用 after 方法确保在主线程中执行UI更新
        self.root.after(0, lambda: self._log_ui(message))
    
    def _log_ui(self, message: str):
        """实际执行UI日志更新（必须在主线程调用）"""
        self.log_text.configure(state='normal')
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state='disabled')
    
    def _clear(self):
        """清除所有内容"""
        self.selected_file = None
        self.file_path_var.set("")
        self.output_path_var.set("（未选择文件）")
        self.log_text.configure(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state='disabled')
        self.status_var.set("就绪")
    
    def _set_ui_enabled(self, enabled: bool):
        """设置UI控件启用/禁用状态"""
        state = 'normal' if enabled else 'disabled'
        self.browse_btn.configure(state=state)
        self.compile_btn.configure(state=state)
        self.clear_btn.configure(state=state)
    
    def _start_compile(self):
        """开始编译（在新线程中运行）"""
        if not self.selected_file:
            messagebox.showwarning("警告", "请先选择一个 TeX 文件！")
            return
        
        if not self.selected_file.exists():
            messagebox.showerror("错误", f"文件不存在: {self.selected_file}")
            return
        
        # 在新线程中运行编译，避免阻塞UI
        thread = threading.Thread(target=self._compile_worker, daemon=True)
        thread.start()
    
    def _compile_worker(self):
        """编译工作线程"""
        self._set_ui_enabled(False)
        self.status_var.set("正在编译...")
        
        try:
            success, message = self._compile_tex_to_image(self.selected_file)
            
            if success:
                self.root.after(0, lambda: self.status_var.set("编译成功"))
                self.root.after(0, lambda: messagebox.showinfo("成功", message))
            else:
                self.root.after(0, lambda: self.status_var.set("编译失败"))
                self.root.after(0, lambda: messagebox.showerror("错误", message))
        
        except Exception as e:
            self.root.after(0, lambda: self.status_var.set("发生错误"))
            self.root.after(0, lambda: messagebox.showerror("错误", f"处理过程中发生错误: {str(e)}"))
        
        finally:
            self.root.after(0, lambda: self._set_ui_enabled(True))
    
    def _compile_tex_to_image(self, tex_file_path: Path) -> tuple[bool, str]:
        """
        将TeX文件编译为图像（保持与原文件相同的编译和挂载指令）
        
        参数:
            tex_file_path: TeX文件的路径
            
        返回:
            (成功状态, 消息)
        """
        self._log(f"开始编译: {tex_file_path.name}")
        
        # 创建临时目录
        temp_dir = tempfile.mkdtemp(prefix="tex_compile_")
        temp_tex_path = Path(temp_dir) / "document.tex"
        pdf_file_path = Path(temp_dir) / "document.pdf"
        
        try:
            # 读取原始TeX文件内容
            tex_content = tex_file_path.read_text(encoding='utf-8')
            
            # 写入临时TeX文件
            temp_tex_path.write_text(tex_content, encoding='utf-8')
            self._log("已准备临时文件")
            
            # 获取项目根目录下的fonts目录绝对路径
            script_dir = Path(__file__).parent.parent
            fonts_dir = script_dir / "fonts"
            fonts_dir.mkdir(exist_ok=True)
            
            # 使用Docker运行TeX Live编译（与原文件完全相同的命令）
            docker_cmd = [
                "docker", "run", "--rm",
                "-v", f"{temp_dir}:/work",
                "-v", f"{fonts_dir}:/fonts:ro",
                "-e", "OSFONTDIR=/fonts",
                "-w", "/work",
                "texlive/texlive:latest-full",
                "sh", "-c",
                "luaotfload-tool --update --force && lualatex -interaction=nonstopmode -halt-on-error document.tex"
            ]
            
            self._log("正在执行 Docker 编译...")
            self._log(f"挂载临时目录: {temp_dir} -> /work")
            self._log(f"挂载字体目录: {fonts_dir} -> /fonts")
            self._log("--- 开始实时输出 ---")
            
            # 执行编译命令，实时捕获输出
            process = subprocess.Popen(
                docker_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # 合并 stderr 到 stdout
                text=True,
                bufsize=1,  # 行缓冲
                encoding='utf-8',
                errors='replace'
            )
            
            # 实时读取并显示输出
            full_output = []
            try:
                while True:
                    line = process.stdout.readline()
                    if not line:
                        break
                    line = line.rstrip('\n\r')
                    full_output.append(line)
                    self._log(line)
                
                # 等待进程完成
                process.wait(timeout=1800)
            except subprocess.TimeoutExpired:
                process.kill()
                return False, "TeX 编译超时（超过30分钟）"
            
            self._log("--- 实时输出结束 ---")
            
            # 检查编译是否成功
            if process.returncode != 0:
                return False, f"TeX 编译失败，返回码: {process.returncode}"
            
            if not pdf_file_path.exists():
                return False, "编译失败：未生成 PDF 文件"
            
            self._log("PDF 生成成功，正在转换为图像...")
            
            # 编译成功，将PDF转换为图像
            try:
                import fitz  # PyMuPDF
                
                doc = fitz.open(str(pdf_file_path))
                page = doc[0]
                
                # 设置缩放比例，提高清晰度
                mat = fitz.Matrix(2.0, 2.0)
                pix = page.get_pixmap(matrix=mat)
                
                # 输出到与TeX文件相同的路径，只是扩展名改为.png
                output_path = tex_file_path.with_suffix('.png')
                pix.save(str(output_path))
                
                img_bytes = pix.tobytes("png")
                doc.close()
                
                self._log(f"图像已保存: {output_path}")
                
                return True, f"编译成功！\n输出文件: {output_path}\n图像大小: {len(img_bytes):,} 字节"
                
            except ImportError:
                return False, "缺少 PyMuPDF 库，请安装: pip install PyMuPDF"
        
        except subprocess.TimeoutExpired:
            return False, "TeX 编译超时（超过30分钟）"
        
        except Exception as e:
            return False, f"处理过程中发生错误: {str(e)}"
        
        finally:
            # 清理临时目录
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
                self._log("已清理临时文件")
            except Exception as e:
                self._log(f"清理临时文件时出错: {e}")


def main():
    """主函数"""
    # 检查依赖
    try:
        import fitz
    except ImportError:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "缺少依赖",
            "缺少 PyMuPDF 库，请先安装:\n\npip install PyMuPDF"
        )
        sys.exit(1)
    
    # 创建主窗口
    root = tk.Tk()
    app = TexCompilerGUI(root)
    
    # 运行主循环
    root.mainloop()


if __name__ == "__main__":
    main()
