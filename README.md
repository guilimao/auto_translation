# Auto-Translator

基于多 Agent 的自动翻译工具。

[English Version](README_EN.md)

## 安装

### 1. 安装 Docker

- Windows: 使用 Docker Desktop
- Linux: 参考 Docker 官方安装指南

### 2. 安装 uv

```powershell
# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

```bash
# Linux / macOS
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 3. 安装依赖

```bash
uv sync
```

### 4. 配置 API Key

```bash
export OPENROUTER_API_KEY="sk-......"
```

## 启动

```bash
uv run cli.py
```

## 当前目录结构

- `core/`: Agent、运行时、限流、配置、日志、提示词
- `ui/`: CLI 会话与终端渲染
- `tools/`: 工具定义、目录扫描、工具工厂
- `inputs/`: 输入文件目录
- `workspaces/`: 页面级工作区目录
- `output/`: 最终产物目录
- `logs/`: 每次 CLI 启动后的会话日志目录
- `fonts/`: Typst 字体目录

## 说明

- 调度器会在 CLI 中显示思考内容、普通输出和工具调用。
- 执行器状态以固定行展示；运行完成后会显示“正常提交结果 / 未提交成果 / 传输报错 / 用户中断”。
- 执行器默认工作路径是自身 workspace，但允许在项目根目录范围内跨 workspace 查看其他页面。
- `read_image` / `crop_image` 会自动压缩上一张同类图像消息，节省 token。
- `color_sample` 的 `x/y` 使用 `1-1000` 的归一化相对坐标。

## 配置文件

`config.json` 示例：

```json
{
  "base_url": "https://openrouter.ai/api/v1",
  "api_key": "OPENROUTER_API_KEY",
  "model": "google/gemini-3.1-pro-preview",
  "scheduler_model": "google/gemini-3.1-pro-preview",
  "executor_model": "google/gemini-3.1-pro-preview",
  "concurrency": {
    "max_parallel_agents": 4,
    "max_concurrent_requests": 4,
    "qps": 1.0,
    "qpm": 30
  }
}
```
