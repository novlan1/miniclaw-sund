"""todo_write tool: 创建/更新任务列表，支持 merge 模式追踪进度。"""
from __future__ import annotations

import json
import os

_TODOS_FILENAME = ".miniclaw/todos.json"


def _load_todos(workspace: str) -> list[dict]:
    """读取已存在的 todos.json。"""
    path = os.path.join(workspace, _TODOS_FILENAME)
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    if isinstance(data, list):
        return data
    return []


def _save_todos(workspace: str, todos: list[dict]) -> None:
    """写入 todos.json。"""
    path = os.path.join(workspace, _TODOS_FILENAME)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(todos, f, ensure_ascii=False, indent=2)


def _format_todos(todos: list[dict]) -> str:
    """将任务列表格式化为可读文本。"""
    if not todos:
        return "（暂无任务）"
    status_icons = {
        "pending": "○",
        "in_progress": "◐",
        "completed": "●",
        "cancelled": "✕",
    }
    lines = []
    for i, t in enumerate(todos):
        icon = status_icons.get(t.get("status", "pending"), "?")
        content = t.get("content", f"任务 {i + 1}")
        status = t.get("status", "pending")
        lines.append(f"{icon} [{status}] {content}")
    return "\n".join(lines)


def handle_todo_write(
    args: dict,
    workspace_root: str,
    tools_cfg=None,
) -> str:
    """创建/更新任务列表。

    args:
        todos: list of {content, status, id?}  — 任务列表
        merge: bool — 是否合并到现有任务（默认 false=替换）

    status 取值: pending, in_progress, completed, cancelled
    """
    todos_input = args.get("todos", [])
    merge = bool(args.get("merge", False))

    if not isinstance(todos_input, list):
        return json.dumps({"error": "todos 必须是数组"}, ensure_ascii=False)

    # 标准化输入
    normalized = []
    for t in todos_input:
        if not isinstance(t, dict):
            continue
        content = str(t.get("content", "")).strip()
        if not content:
            continue
        status = t.get("status", "pending")
        if status not in ("pending", "in_progress", "completed", "cancelled"):
            status = "pending"
        entry = {"content": content, "status": status}
        tid = t.get("id")
        if tid is not None:
            entry["id"] = tid
        normalized.append(entry)

    if merge:
        existing = _load_todos(workspace_root)
        # 按 id 合并：输入中有 id 的更新已有条目，无 id 的追加
        existing_by_id = {}
        for e in existing:
            tid = e.get("id")
            if tid is not None:
                existing_by_id[tid] = e

        merged = []
        seen_ids = set()
        for new_t in normalized:
            tid = new_t.get("id")
            if tid is not None and tid in existing_by_id:
                # 更新已有条目
                existing_by_id[tid].update(new_t)
                merged.append(existing_by_id[tid])
                seen_ids.add(tid)
            else:
                merged.append(new_t)
        # 保留未被更新的已有条目
        for e in existing:
            tid = e.get("id")
            if tid is not None and tid not in seen_ids:
                merged.append(e)
            elif tid is None:
                merged.append(e)

        _save_todos(workspace_root, merged)
        return f"任务列表已合并更新（共 {len(merged)} 条）：\n{_format_todos(merged)}"
    else:
        _save_todos(workspace_root, normalized)
        return f"任务列表已更新（共 {len(normalized)} 条）：\n{_format_todos(normalized)}"
