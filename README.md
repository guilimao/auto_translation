# auto-translation

基于Agent的自动翻译工具

## 项目简介

借助多模态LLM和Typst排版工具，生成与原始文档观感相近的高质量翻译文件

## 安装步骤

### 安装uv

```powershell
# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

```bash
# Linux / macOS
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 同步依赖项

```bash
uv sync
```

### 将API KEY添加到环境变量

```bash
export OPENROUTER_API_KEY="sk-......"
```

## 使用方式

### 基本用法

```bash
uv run cli.py
```

在对话中告诉模型需要翻译的文件路径即可

输出文件保存在 output 文件夹下，退出对话时会清理中间文件，保留最后一个可用版本。

### 配置文件

```json
{
  "base_url": "在这里填写推理提供商的base_url",
  "api_key": "在这里填写对应的API KEY名称，并将实际的API KEY保存到系统环境变量",
  "model": "在这里填写模型名称"
}
```
