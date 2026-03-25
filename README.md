# auto-translation

基于 Agent 的自动翻译工具

[English Version](README_EN.md)

---

## 项目简介

借助多模态 LLM 和 Typst 排版工具，生成与原始文档观感相近的高质量翻译文件，支持图文混排。

---

## 安装步骤

### 1. 安装 Docker

#### Windows

<a href="https://get.microsoft.com/installer/download/xp8cbj40xlbwkx?referrer=appbadge" target="_blank">
    <img src="https://get.microsoft.com/images/en-us%20dark.svg" width="200" alt="Get Docker from Microsoft Store"/>
</a>

或从 [Docker 官方发布页](https://docs.docker.com/desktop/release-notes/) 下载安装

#### Linux

访问 [Docker 安装指南](https://docs.docker.com/engine/install/)

---

### 2. 安装 uv

```powershell
# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

```bash
# Linux / macOS
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

### 3. 同步依赖项

```bash
uv sync
```

---

### 4. 配置 API Key

将 API KEY 添加到环境变量：

```bash
export OPENROUTER_API_KEY="sk-......"
```

---

## 使用方式

### 基本用法

```bash
uv run cli.py
```

在对话中告诉模型需要翻译的文件路径即可。

输出文件保存在 `outputs` 文件夹下，退出对话时会清理中间文件，保留最后一个可用版本。

---

### 配置文件

`config.json` 格式如下：

```json
{
  "base_url": "在这里填写推理提供商的 base_url",
  "api_key": "在这里填写对应的 API KEY 名称，并将实际的 API KEY 保存到系统环境变量",
  "model": "在这里填写模型名称"
}
```

---

### 自定义字体

下载需要的字体文件，解压后直接放置到 `fonts` 文件夹中即可。

例如，你可以在[Source Han Sans 字体发布页](https://github.com/adobe-fonts/source-han-sans/releases)下载[All Static Region Specific Subset OTFs](https://github.com/adobe-fonts/source-han-sans/releases/download/2.005R/05_SourceHanSansSubsetOTF.zip)，解压后放置到项目根目录下的fonts文件夹中。工具可以识别嵌套文件夹下的字体文件，并将正确的字体名称告知模型。


---
