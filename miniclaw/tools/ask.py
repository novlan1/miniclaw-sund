"""ask_followup_question tool: 模型向用户提问澄清需求。"""
from __future__ import annotations

import json

from prompt_toolkit import prompt
from prompt_toolkit.formatted_text import HTML


def _format_option(opt: dict | str, idx: int) -> str:
    """格式化单个选项。"""
    if isinstance(opt, dict):
        label = opt.get("label", f"选项 {idx + 1}")
        desc = opt.get("description", "")
        if desc:
            return f"  {idx + 1}. {label} — {desc}"
        return f"  {idx + 1}. {label}"
    return f"  {idx + 1}. {str(opt)}"


def handle_ask(
    args: dict,
    workspace_root: str,
    tools_cfg=None,
) -> str:
    """向用户展示问题并收集回答。

    args:
        question: str — 问题文本（必填）
        header: str — 可选标题
        options: list — 可选选项列表（每项可以是 string 或 {label, description}）
        multi_select: bool — 是否允许多选（默认 false）
    """
    question = str(args.get("question", "")).strip()
    if not question:
        return json.dumps({"error": "ask_followup_question 需要 question 参数"}, ensure_ascii=False)

    header = str(args.get("header", "")).strip()
    options = args.get("options")
    if options is not None and not isinstance(options, list):
        return json.dumps({"error": "options 必须是数组"}, ensure_ascii=False)
    multi_select = bool(args.get("multi_select", False))

    # 构建显示文本
    lines = []
    if header:
        lines.append(HTML(f"<style fg='ansiyellow'><b>{header}</b></style>"))
    lines.append(HTML(f"<style fg='ansicyan'>{question}</style>"))

    if options and len(options) > 0:
        for i, opt in enumerate(options):
            lines.append(_format_option(opt, i))

        if multi_select:
            lines.append(HTML("\n<style fg='ansigreen'>输入序号（逗号分隔，如 1,3）</style>"))
            user_input = prompt(
                HTML(" <style fg='ansigreen'>❯</style> "),
                multiline=False,
            )
        else:
            lines.append(HTML("\n<style fg='ansigreen'>输入序号</style>"))
            user_input = prompt(
                HTML(" <style fg='ansigreen'>❯</style> "),
                multiline=False,
            )

        # 格式化回答
        return json.dumps(
            {"answer": user_input.strip(), "question": question},
            ensure_ascii=False,
        )
    else:
        # 无选项时自由输入
        user_input = prompt(
            HTML(" <style fg='ansigreen'>❯</style> "),
            multiline=False,
        )
        return json.dumps(
            {"answer": user_input.strip(), "question": question},
            ensure_ascii=False,
        )
