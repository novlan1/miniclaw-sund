"""单元测试：rules 系统、todo_write 工具、ask_followup_question 工具。"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch

from miniclaw.rules import load_rules
from miniclaw.tools.todo_write import handle_todo_write
from miniclaw.skills import build_system_prompt


# ---------------------------------------------------------------------------
# Rules 系统测试
# ---------------------------------------------------------------------------

class TestRulesLoading(unittest.TestCase):
    """测试 rules 文件扫描与加载。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, relpath: str, content: str):
        path = os.path.join(self.tmp, relpath)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def test_no_rules_returns_none(self):
        self.assertIsNone(load_rules(self.tmp))

    def test_agents_md_only(self):
        self._write("AGENTS.md", "# Project Rules\nBe nice.")
        result = load_rules(self.tmp)
        self.assertIsNotNone(result)
        self.assertIn("# Project Rules", result)
        self.assertIn("Be nice.", result)

    def test_rules_dir_only(self):
        self._write(".miniclaw/rules/style.md", "Always use spaces.")
        self._write(".miniclaw/rules/security.md", "No eval().")
        result = load_rules(self.tmp)
        self.assertIsNotNone(result)
        self.assertIn("### style", result)
        self.assertIn("Always use spaces.", result)
        self.assertIn("### security", result)
        self.assertIn("No eval().", result)

    def test_agents_md_and_rules_combined(self):
        self._write("AGENTS.md", "# Project Rules\nUse type hints.")
        self._write(".miniclaw/rules/test.md", "Write tests.")
        result = load_rules(self.tmp)
        self.assertIsNotNone(result)
        self.assertIn("Use type hints.", result)
        self.assertIn("Write tests.", result)
        self.assertIn("---", result)  # separator

    def test_rules_sorted_by_name(self):
        self._write(".miniclaw/rules/c.md", "C")
        self._write(".miniclaw/rules/a.md", "A")
        self._write(".miniclaw/rules/b.md", "B")
        result = load_rules(self.tmp)
        idx_a = result.index("### a")
        idx_b = result.index("### b")
        idx_c = result.index("### c")
        self.assertLess(idx_a, idx_b)
        self.assertLess(idx_b, idx_c)

    def test_skips_non_md_files(self):
        self._write(".miniclaw/rules/config.json", "{}")
        self._write(".miniclaw/rules/.gitkeep", "")
        self._write(".miniclaw/rules/style.md", "Use spaces.")
        result = load_rules(self.tmp)
        self.assertIn("style", result)
        self.assertNotIn("config.json", result)

    def test_oversized_file_skipped(self):
        content = "x" * 33000
        self._write(".miniclaw/rules/big.md", content)
        result = load_rules(self.tmp)
        self.assertIsNone(result)

    def test_empty_file_skipped(self):
        self._write(".miniclaw/rules/empty.md", "\n\n")
        result = load_rules(self.tmp)
        self.assertIsNone(result)

    def test_system_prompt_includes_rules(self):
        prompt = build_system_prompt(
            [], workspace_root="/tmp",
            rules_block="## My Rules\nAlways lint.",
        )
        self.assertIn("项目规则", prompt)
        self.assertIn("Always lint.", prompt)

    def test_system_prompt_without_rules(self):
        prompt = build_system_prompt([], workspace_root="/tmp")
        self.assertNotIn("项目规则", prompt)


# ---------------------------------------------------------------------------
# todo_write 工具测试
# ---------------------------------------------------------------------------

class TestTodoWrite(unittest.TestCase):
    """测试 todo_write 工具。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_create_todos_replace(self):
        todos = [
            {"content": "Add login", "status": "pending"},
            {"content": "Add dashboard", "status": "in_progress"},
        ]
        result = handle_todo_write({"todos": todos, "merge": False}, self.tmp)
        self.assertIn("2 条", result)
        self.assertIn("Add login", result)
        self.assertIn("in_progress", result)

    def test_create_todos_cancelled_item(self):
        todos = [
            {"content": "Won't do", "status": "cancelled"},
        ]
        result = handle_todo_write({"todos": todos, "merge": False}, self.tmp)
        self.assertIn("cancelled", result)

    def test_merge_updates_existing_by_id(self):
        # 先创建
        initial = [
            {"content": "Task A", "status": "pending", "id": "a"},
            {"content": "Task B", "status": "pending", "id": "b"},
        ]
        handle_todo_write({"todos": initial, "merge": False}, self.tmp)

        # 合并更新
        updates = [
            {"content": "Task A", "status": "completed", "id": "a"},
        ]
        result = handle_todo_write({"todos": updates, "merge": True}, self.tmp)
        # Task A 应变为 completed，Task B 保留
        lines = result.split("\n")
        self.assertTrue(any("Task A" in l and "completed" in l for l in lines),
                        f"Task A should be completed in:\n{result}")
        self.assertTrue(any("Task B" in l and "pending" in l for l in lines),
                        f"Task B should remain pending in:\n{result}")

    def test_merge_adds_new_without_id(self):
        initial = [
            {"content": "Task A", "status": "pending", "id": "a"},
        ]
        handle_todo_write({"todos": initial, "merge": False}, self.tmp)

        updates = [
            {"content": "Task B", "status": "pending"},
        ]
        result = handle_todo_write({"todos": updates, "merge": True}, self.tmp)
        self.assertIn("Task A", result)
        self.assertIn("Task B", result)

    def test_empty_todos(self):
        result = handle_todo_write({"todos": [], "merge": False}, self.tmp)
        self.assertIn("（暂无任务）", result)

    def test_invalid_status_defaults_to_pending(self):
        todos = [
            {"content": "Bad status", "status": "invalid_status"},
        ]
        result = handle_todo_write({"todos": todos, "merge": False}, self.tmp)
        self.assertIn("pending", result)

    def test_missing_content_skipped(self):
        todos = [
            {"content": "Valid", "status": "pending"},
            {"content": "", "status": "pending"},
            {"content": "   ", "status": "pending"},
        ]
        result = handle_todo_write({"todos": todos, "merge": False}, self.tmp)
        self.assertIn("1 条", result)
        self.assertIn("Valid", result)

    def test_error_on_non_list_todos(self):
        result = handle_todo_write({"todos": "not_a_list", "merge": False}, self.tmp)
        data = json.loads(result)
        self.assertIn("error", data)

    def test_persists_to_file(self):
        todos = [
            {"content": "Write tests", "status": "completed"},
        ]
        handle_todo_write({"todos": todos, "merge": False}, self.tmp)
        path = os.path.join(self.tmp, ".miniclaw", "todos.json")
        self.assertTrue(os.path.isfile(path))
        with open(path, "r") as f:
            saved = json.load(f)
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["content"], "Write tests")


# ---------------------------------------------------------------------------
# ask_followup_question 工具测试
# ---------------------------------------------------------------------------

class TestAskFollowup(unittest.TestCase):
    """测试 ask_followup_question 工具。"""

    def test_requires_question(self):
        from miniclaw.tools.ask import handle_ask
        result = handle_ask({"question": ""}, "/tmp")
        data = json.loads(result)
        self.assertIn("error", data)

    def test_returns_answer_json(self):
        from miniclaw.tools.ask import handle_ask
        with patch("miniclaw.tools.ask.prompt", return_value="my answer"):
            result = handle_ask({"question": "What framework?"}, "/tmp")
        data = json.loads(result)
        self.assertEqual(data["answer"], "my answer")
        self.assertIn("question", data)

    def test_with_options_and_header(self):
        from miniclaw.tools.ask import handle_ask
        with patch("miniclaw.tools.ask.prompt", return_value="2"):
            result = handle_ask({
                "question": "Pick one",
                "header": "Choice",
                "options": ["React", "Vue", "Svelte"],
            }, "/tmp")
        data = json.loads(result)
        self.assertEqual(data["answer"], "2")
        self.assertEqual(data["question"], "Pick one")

    def test_with_dict_options(self):
        from miniclaw.tools.ask import handle_ask
        with patch("miniclaw.tools.ask.prompt", return_value="1"):
            result = handle_ask({
                "question": "Which one?",
                "options": [
                    {"label": "React", "description": "Fast"},
                    {"label": "Vue", "description": "Simple"},
                ],
            }, "/tmp")
        data = json.loads(result)
        self.assertEqual(data["answer"], "1")

    def test_multi_select(self):
        from miniclaw.tools.ask import handle_ask
        with patch("miniclaw.tools.ask.prompt", return_value="1,3"):
            result = handle_ask({
                "question": "Select",
                "options": ["A", "B", "C"],
                "multi_select": True,
            }, "/tmp")
        data = json.loads(result)
        self.assertEqual(data["answer"], "1,3")

    def test_rejects_non_list_options(self):
        from miniclaw.tools.ask import handle_ask
        result = handle_ask({
            "question": "Q",
            "options": "not_a_list",
        }, "/tmp")
        data = json.loads(result)
        self.assertIn("error", data)

    def test_renders_question_and_options(self):
        """问题与选项必须真正输出到终端，否则用户看不到选项框。"""
        from miniclaw.tools.ask import handle_ask
        with patch("miniclaw.tools.ask.prompt", return_value="1"), \
                patch("miniclaw.tools.ask.console") as mock_console:
            handle_ask({
                "question": "Pick one",
                "header": "Choice",
                "options": ["React", {"label": "Vue", "description": "Simple"}],
            }, "/tmp")
        self.assertTrue(mock_console.print.called)
        rendered = "".join(
            str(getattr(call.args[0], "renderable", call.args[0]) if call.args else "")
            for call in mock_console.print.call_args_list
        )
        self.assertIn("Pick one", rendered)
        self.assertIn("React", rendered)
        self.assertIn("Vue", rendered)
        self.assertIn("Simple", rendered)

    def test_renders_without_options(self):
        from miniclaw.tools.ask import handle_ask
        with patch("miniclaw.tools.ask.prompt", return_value="free text"), \
                patch("miniclaw.tools.ask.console") as mock_console:
            handle_ask({"question": "Anything?"}, "/tmp")
        self.assertTrue(mock_console.print.called)

    def test_maps_index_to_label(self):
        from miniclaw.tools.ask import handle_ask
        with patch("miniclaw.tools.ask.prompt", return_value="2"), \
                patch("miniclaw.tools.ask.console"):
            result = handle_ask({
                "question": "Pick one",
                "options": ["React", {"label": "Vue"}, "Svelte"],
            }, "/tmp")
        data = json.loads(result)
        self.assertEqual(data["answer"], "2")
        self.assertEqual(data["selected"], ["Vue"])

    def test_maps_multi_select_indexes(self):
        from miniclaw.tools.ask import handle_ask
        with patch("miniclaw.tools.ask.prompt", return_value="1, 3"), \
                patch("miniclaw.tools.ask.console"):
            result = handle_ask({
                "question": "Select",
                "options": ["A", "B", "C"],
                "multi_select": True,
            }, "/tmp")
        data = json.loads(result)
        self.assertEqual(data["selected"], ["A", "C"])

    def test_free_text_answer_has_no_selected(self):
        from miniclaw.tools.ask import handle_ask
        for raw in ("Svelte", "0", "9", ""):
            with self.subTest(raw=raw):
                with patch("miniclaw.tools.ask.prompt", return_value=raw), \
                        patch("miniclaw.tools.ask.console"):
                    result = handle_ask({
                        "question": "Pick one",
                        "options": ["A", "B"],
                    }, "/tmp")
                data = json.loads(result)
                self.assertNotIn("selected", data)
                self.assertEqual(data["answer"], raw.strip())

    def test_cancelled_input_returns_error(self):
        from miniclaw.tools.ask import handle_ask
        for exc in (EOFError, KeyboardInterrupt):
            with self.subTest(exc=exc.__name__):
                with patch("miniclaw.tools.ask.prompt", side_effect=exc), \
                        patch("miniclaw.tools.ask.console"):
                    result = handle_ask({"question": "Q"}, "/tmp")
                data = json.loads(result)
                self.assertIn("error", data)


if __name__ == "__main__":
    unittest.main()
