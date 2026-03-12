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

def process_stream(messages):
    """处理流式响应并返回完整消息"""
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
            print(f"\033[90m{reasoning_text}\033[0m", end="", flush=True)
            reasoning_content += reasoning_text
        
        if delta.content:
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
                    print(f"\n\033[94m[调用工具: {tc.function.name}]\033[0m", end="", flush=True)
                if tc.function and tc.function.arguments:
                    tool_calls[tc.index]["function"]["arguments"] += tc.function.arguments
                    # 每获取50个字符，输出一个黄色点
                    tool_call_chars_count += len(tc.function.arguments)
                    dots_to_print = tool_call_chars_count // 50
                    if dots_to_print > 0:
                        print("\033[93m.\033[0m" * dots_to_print, end="", flush=True)
                        tool_call_chars_count %= 50
    
    print()
    # 打印流式传输结束原因
    if finish_reason:
        print(f"\033[93m[流式传输结束原因: {finish_reason}]\033[0m")
    return content, reasoning_content, tool_calls

# 加载系统提示词
def load_system_prompt():
    """从文件加载系统提示词"""
    try:
        with open("system_prompt.txt", "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        print("\033[93m[警告: system_prompt.txt 不存在，将不使用系统提示词]\033[0m")
        return None

def main():
    # 加载系统提示词
    system_prompt = load_system_prompt()
    messages = []
    
    # 如果系统提示词存在，添加到消息列表
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
        print("\033[92m[系统提示词已加载]\033[0m")
    print("开始对话 (输入 'quit' 退出)")
    
    while True:
        user_input = input("\n你: ").strip()
        
        if user_input.lower() == 'quit':
            break
        
        if not user_input:
            continue
        
        messages.append({"role": "user", "content": user_input})
        
        # 使用循环支持多轮工具调用
        while True:
            print("AI: ", end="", flush=True)
            content, reasoning_content, tool_calls = process_stream(messages)
            
            # 添加助手消息
            assistant_msg = {"role": "assistant"}
            if content:
                assistant_msg["content"] = content
            if reasoning_content:
                assistant_msg["reasoning_content"] = reasoning_content
            if tool_calls:
                assistant_msg["tool_calls"] = [{"id": tc["id"], "type": tc["type"], 
                                                 "function": tc["function"]} for tc in tool_calls]
            messages.append(assistant_msg)
            
            # 处理工具调用，如果没有工具调用则退出循环
            if not process_tool_calls(messages, tool_calls):
                break

if __name__ == "__main__":
    main()
