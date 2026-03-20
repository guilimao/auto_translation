import json
import os
from chat import process_stream

# 加载配置
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)


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
            content, reasoning_content, tool_calls = process_stream(messages, output_to_cli=True)

            # 添加助手消息
            assistant_msg = {"role": "assistant"}
            if content:
                assistant_msg["content"] = content
            if reasoning_content:
                assistant_msg["reasoning_content"] = reasoning_content
            if tool_calls:
                from tools import process_tool_calls
                assistant_msg["tool_calls"] = [{"id": tc["id"], "type": tc["type"],
                                                 "function": tc["function"]} for tc in tool_calls]
            messages.append(assistant_msg)

            # 处理工具调用，如果没有工具调用则退出循环
            if not process_tool_calls(messages, tool_calls):
                break


if __name__ == "__main__":
    main()
