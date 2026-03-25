# auto-translation

Agent-based Automatic Translation Tool

[中文版本](README.md)

---

## Project Overview

Leveraging multimodal LLM and Typst typesetting tools to make high-quality translated documents with visual appearance similar to the original, supporting mixed text and image layouts.

---

## Installation

### 1. Install Docker

#### Windows

<a href="https://get.microsoft.com/installer/download/xp8cbj40xlbwkx?referrer=appbadge" target="_blank">
    <img src="https://get.microsoft.com/images/en-us%20dark.svg" width="200" alt="Get Docker from Microsoft Store"/>
</a>

Or download from [Docker Official Releases](https://docs.docker.com/desktop/release-notes/)

#### Linux

Visit [Docker Installation Guide](https://docs.docker.com/engine/install/)

---

### 2. Install uv

```powershell
# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

```bash
# Linux / macOS
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

### 3. Sync Dependencies

```bash
uv sync
```

---

### 4. Configure API Key

Add the API KEY to environment variables:

```bash
export OPENROUTER_API_KEY="sk-......"
```

---

## Usage

### Basic Usage

```bash
uv run cli.py
```

Simply tell the model the file path you need to translate during the conversation.

Output files are saved in the `outputs` folder. Intermediate files will be cleaned up when exiting the conversation, keeping only the last usable version.

---

### Configuration File

The `config.json` format is as follows:

```json
{
  "base_url": "Enter the inference provider's base_url here",
  "api_key": "Enter the corresponding API KEY name here, and save the actual API KEY to system environment variables",
  "model": "Enter the model name here"
}
```

---

### Custom Fonts

Create a `fonts` folder, download the required font files, extract them, and place them directly inside.

---
