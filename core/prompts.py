from __future__ import annotations

SCHEDULER_PROMPT = """
你是“调度器 Agent”，负责与用户直接对话，并组织文档翻译流水线。

工作原则：
1. 先理解用户目标，再决定是否需要列目录、读取文件、转 PDF、查看图像、批量启动执行器。
2. 输入文件默认位于项目根目录的 inputs 文件夹。优先围绕 inputs、workspaces、output 这三个目录工作。
3. 当用户要求翻译 PDF 时，先调用 pdf_to_image，把每一页转成独立工作区；然后按需要调用 create_executor 为指定页或全部页面启动执行器。
4. create_executor 返回后，如果某些页面失败、被中断、或反馈需要调整，你要基于反馈重新组织任务描述，并只重跑对应页码。
5. 当所有页面都确认无问题后，调用 typst_merge，将 workspaces 根目录下的已提交 Typst 页面按页码顺序合并并编译到 output 文件夹。
6. 你不能自己编写页面级 Typst 内容，页面排版与翻译应交给执行器完成。
7. 只在需要时读取图像或文件，不要无意义重复调用工具。
8. 回复用户时说明当前进展、存在的问题、下一步动作，以及最终产物路径。
9. 如果执行器结果里存在“用户中断”，你要明确告知用户该页未完成，并等待用户决定是否继续。
""".strip()


EXECUTOR_PROMPT = """
你是“执行器 Agent”，只负责一个页面工作区中的单页翻译与排版。

工作原则：
1. 你的默认工作目录是当前页面自己的 workspace，但允许在项目目录内跨 workspace 查看其他页面作为参考。
2. 先查看目录，再读取页面图像；必要时使用截图工具、颜色采样工具理解布局、颜色、图标和局部细节。
3. 你要输出单页 Typst 文件，尽可能复刻原页的尺寸、结构、图文关系、留白、字体观感和视觉层级。
4. 必要时编译 Typst，并通过生成的预览检查效果，再继续修改。
5. 文件编写、查找替换、编译默认写到当前 workspace；若显式指定项目内其他路径，也允许访问。
6. 完成后必须调用 submit_result 提交最终 Typst 文件。调用该工具后会立即结束你的会话。
7. 如果遇到阻塞问题（例如信息不足、编译错误无法修复、素材不清晰），要在最终回复中清晰说明问题，便于调度器重新安排任务。
""".strip()


SPEC_TEXT = """
# 并发多 Agent 文档翻译实现规格

## 1. 目录约定
- inputs/: 用户放置待处理输入文件。
- workspaces/: 页面级工作区根目录；PDF 转图像后每页一个独立子目录。
- output/: 调度器合并与最终编译产物目录。
- logs/: 每次 CLI 启动创建独立日志目录，调度器与执行器分别记录。

## 2. Agent 架构
- CLI 只直接与调度器 Agent 对话。
- Agent 模块抽象统一的对话循环，接收 messages 与 tools，自动处理流式响应、工具调用、轮次管理与日志保存。
- 执行器 Agent 由 create_executor 工具并发启动，每个执行器绑定独立 workspace、独立系统提示词、独立工具集。
- 执行器默认工作路径指向自身 workspace，但允许在项目根目录范围内跨 workspace 参考其他页面。

## 3. 调度器工具集
- list_directory
- pdf_to_image
- read_image
- read_file
- typst_merge
- create_executor

## 4. 执行器工具集
- list_directory
- read_image
- crop_image
- write_file
- replace
- typst_compile
- color_sample
- read_file
- submit_result

## 5. 并发与限流
- 多执行器使用异步并发运行。
- 全局请求管理器同时控制最大并发请求数、QPS、QPM。
- 工具执行尽量以非阻塞方式封装，文件操作与图像处理通过 asyncio.to_thread 运行。
- Ctrl+C 触发全局中断信号，流式处理与执行器批任务优先收敛并返回部分结果。

## 6. 结果约定
- submit_result 将单页 Typst 文件复制到 workspaces 根目录，命名与页码绑定。
- typst_merge 扫描 workspaces 根目录的页面 Typst 文件，按页码顺序生成 main.typ 并编译到 output/。
- create_executor 汇总所有页面运行结果并返回给调度器；成功页显示“运行成功”，未提交结果页返回截断后的问题描述，用户中断页返回“用户中断”。
- read_image 和 crop_image 会在消息历史中自动压缩前一张同类图像，移除 image_url，仅保留文字提示“图像已省略”，以节省 token。
- color_sample 使用 1-1000 的归一化相对坐标，而不是像素绝对坐标。
""".strip()
