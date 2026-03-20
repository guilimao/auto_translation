import json, base64, os
from openai import OpenAI
from tools import TOOLS, process_tool_calls

# 加载配置
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

# 从环境变量获取 API key（config 中的 api_key 是环境变量名）
api_key_name = config["api_key"]
api_key = os.getenv(api_key_name)
if not api_key:
    raise ValueError(f"环境变量 '{api_key_name}' 未设置，请在系统环境变量中配置 API key")

client = OpenAI(base_url=config["base_url"], api_key=api_key)
model = config["model"]

def encode_image(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def process_stream(messages, output_to_cli=False):
    """处理流式响应并返回完整消息
    
    参数:
        messages: 消息列表
        output_to_cli: 若为True，则向CLI输出内容，否则不向CLI输出内容
    
    返回:
        content: 完整内容
        reasoning_content: 思考内容
        tool_calls: 工具调用列表
    """
    stream = client.chat.completions.create(
        model=model, messages=messages, tools=TOOLS, tool_choice="auto", stream=True
    )
    
    content = ""
    reasoning_content = ""
    tool_calls = []
    finish_reason = None
    tool_call_chars_count = 0  # 跟踪工具调用参数字符数
    
    for chunk in stream:
        # 捕获结束原因
        if chunk.choices[0].finish_reason:
            finish_reason = chunk.choices[0].finish_reason
        delta = chunk.choices[0].delta
        
        # 捕获思考内容
        reasoning_text = getattr(delta, 'reasoning_content', None) or (delta.model_extra or {}).get('reasoning_content')
        if reasoning_text:
            if output_to_cli:
                print(f"\033[90m{reasoning_text}\033[0m", end="", flush=True)
            reasoning_content += reasoning_text
        
        if delta.content:
            if output_to_cli:
                print(delta.content, end="", flush=True)
            content += delta.content
        
        if delta.tool_calls:
            for tc in delta.tool_calls:
                if tc.index >= len(tool_calls):
                    tool_calls.append({"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                if tc.id:
                    tool_calls[tc.index]["id"] = tc.id
                if tc.function and tc.function.name:
                    tool_calls[tc.index]["function"]["name"] = tc.function.name
                    # 显示工具调用信息
                    if output_to_cli:
                        print(f"\n\033[94m[调用工具: {tc.function.name}]\033[0m", end="", flush=True)
                if tc.function and tc.function.arguments:
                    tool_calls[tc.index]["function"]["arguments"] += tc.function.arguments
                    # 每获取50个字符，输出一个黄色点
                    tool_call_chars_count += len(tc.function.arguments)
                    dots_to_print = tool_call_chars_count // 50
                    if dots_to_print > 0:
                        if output_to_cli:
                            print("\033[93m.\033[0m" * dots_to_print, end="", flush=True)
                        tool_call_chars_count %= 50
    
    if output_to_cli:
        print()
        # 打印处理状态
        if finish_reason:
            print(f"\033[93m[状态: {finish_reason}]\033[0m")
    return content, reasoning_content, tool_calls
