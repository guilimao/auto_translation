import json
import os
import shutil
from chat import process_stream
from tools import process_tool_calls

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


def cleanup_work_folder(work_dir="work"):
    """清空 work 文件夹的所有内容"""
    if not os.path.exists(work_dir):
        return
    
    for item in os.listdir(work_dir):
        item_path = os.path.join(work_dir, item)
        try:
            if os.path.isfile(item_path):
                os.remove(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
        except Exception as e:
            print(f"\033[91m[清理 work 文件夹时出错: {e}]\033[0m")


def cleanup_outputs_folder(outputs_dir="outputs", keep_last=1):
    """清理 outputs 文件夹，只保留最新的 keep_last 个项目"""
    if not os.path.exists(outputs_dir):
        return
    
    # 获取所有项目并提取时间戳
    items = []
    for item in os.listdir(outputs_dir):
        item_path = os.path.join(outputs_dir, item)
        try:
            # 获取修改时间
            mtime = os.path.getmtime(item_path)
            items.append((mtime, item, item_path))
        except Exception as e:
            print(f"\033[91m[获取文件信息时出错: {e}]\033[0m")
    
    if len(items) <= keep_last:
        return
    
    # 按时间排序（新的在前）
    items.sort(reverse=True, key=lambda x: x[0])
    
    # 删除旧的项目
    for _, item, item_path in items[keep_last:]:
        try:
            if os.path.isfile(item_path):
                os.remove(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
        except Exception as e:
            print(f"\033[91m[清理 outputs 文件夹时出错: {e}]\033[0m")


def perform_cleanup():
    """执行清理操作"""
    print("\033[94m[正在清理临时文件...]\033[0m")
    cleanup_work_folder()
    cleanup_outputs_folder()
    print("\033[92m[清理完成]\033[0m")


def main():
    # 加载系统提示词
    system_prompt = load_system_prompt()
    messages = []

    # 如果系统提示词存在，添加到消息列表
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
        print("\033[92m[系统提示词已加载]\033[0m")

    try:
        while True:
            try:
                user_input = input("\n你: ").strip()
            except EOFError:
                # 处理 Ctrl+D (EOF)
                print()
                break

            if not user_input:
                break

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
                    assistant_msg["tool_calls"] = [{"id": tc["id"], "type": tc["type"],"function": tc["function"]} for tc in tool_calls]
                messages.append(assistant_msg)

                # 处理工具调用，如果没有工具调用则退出循环
                if not process_tool_calls(messages, tool_calls):
                    break
    except KeyboardInterrupt:
        print("\n\n\033[93m[退出]\033[0m")
    finally:
        perform_cleanup()
        print("\033[92m[再见！]\033[0m")


if __name__ == "__main__":
    main()
