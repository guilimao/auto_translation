"""
工具执行模块，处理工具调用的执行和消息处理
"""

import json

# 导入所有工具函数
from .tex_compiler import tex_compiler
from .read_file import read_file
from .write_file import write_file
from .replace import replace
from .pdf_reader import pdf_reader


# ========== 工具函数映射 ==========

TOOL_FUNCTIONS = {
    "tex_compiler": tex_compiler,
    "read_file": read_file,
    "write_file": write_file,
    "replace": replace,
    "pdf_reader": pdf_reader,
}


def execute_tool(tool_call):
    """执行单个工具调用，返回结果"""
    func_name = tool_call["function"]["name"]
    func_args = json.loads(tool_call["function"]["arguments"])
    
    if func_name not in TOOL_FUNCTIONS:
        error_msg = f"未知工具: {func_name}"
        print(f"\033[91m[工具错误: {error_msg}]\033[0m", flush=True)
        return error_msg
    
    try:
        return TOOL_FUNCTIONS[func_name](**func_args)
    except Exception as e:
        error_msg = f"工具 '{func_name}' 执行失败: {str(e)}"
        print(f"\033[91m[工具错误: {error_msg}]\033[0m", flush=True)
        return error_msg


def process_tool_calls(messages, tool_calls):
    """处理所有工具调用并添加结果到messages，返回是否需要继续获取响应"""
    if not tool_calls:
        return False
    
    for tc in tool_calls:
        result = execute_tool(tc)
        
        # 尝试解析结果是否为图像类型
        try:
            result_obj = json.loads(result)
            if result_obj.get("type") == "image":
                # 图像类型：使用官方推荐的 image_url 格式
                base64_data = result_obj.get("data", "")
                image_format = result_obj.get("format", "png")
                
                # 构造 data:image/{format};base64,{data} URL
                image_url = f"data:image/{image_format};base64,{base64_data}"
                
                # 按照官方文档格式构造消息内容
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url,
                            },
                        },
                        {
                            "type": "text",
                            "text": result_obj.get("message", "图像已生成"),
                        },
                    ]
                })
                continue
        except (json.JSONDecodeError, AttributeError):
            pass
        
        # 非图像类型：使用普通文本格式
        messages.append({
            "role": "tool",
            "tool_call_id": tc["id"],
            "content": str(result)
        })
    return True
