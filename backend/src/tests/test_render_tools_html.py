import os
import sys
import tempfile
import unittest


def _load_renderer_module():
    """Load the tools markdown renderer module for testing."""

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    file_path = os.path.join(repo_root, "competition_submission", "render_tools_html.py")
    namespace = {"__file__": file_path, "__name__": "render_tools_html"}
    with open(file_path, "r", encoding="utf-8") as f:
        code = f.read()
    exec(compile(code, file_path, "exec"), namespace)
    return namespace


class TestRenderToolsHtml(unittest.TestCase):
    """Test cases for the markdown-to-HTML renderer used by competition submission tools doc."""

    def test_renders_table(self):
        """Renderer should convert markdown tables into HTML table tags."""

        renderer = _load_renderer_module()
        markdown_text = (
            "# T\n\n"
            "| A | B |\n"
            "|---|---|\n"
            "| 1 | 2 |\n"
        )
        html_text = renderer["render_markdown_to_html"](markdown_text)
        self.assertIn("<table>", html_text)
        self.assertIn("<th>A</th>", html_text)
        self.assertIn("<td>1</td>", html_text)

    def test_renders_tools_doc_sections(self):
        """Rendered HTML should include key content from 02_tools.md."""

        renderer = _load_renderer_module()
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
        md_path = os.path.join(repo_root, "competition_submission", "02_tools.md")
        with open(md_path, "r", encoding="utf-8") as f:
            markdown_text = f.read()
        html_text = renderer["render_markdown_to_html"](markdown_text)
        self.assertIn("Tool 实现能力清单", html_text)
        self.assertIn("<table>", html_text)
        self.assertIn("<code>adjust_plan_item</code>", html_text)

    def test_main_uses_script_dir_defaults(self):
        """main() should locate default input relative to script directory, not current working directory."""

        renderer = _load_renderer_module()
        original_argv = sys.argv[:]
        original_cwd = os.getcwd()
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                out_path = os.path.join(tmp_dir, "out.html")
                sys.argv = ["render_tools_html.py", "--output", out_path]
                try:
                    os.chdir(tmp_dir)
                    renderer["main"]()
                finally:
                    os.chdir(original_cwd)
                with open(out_path, "r", encoding="utf-8") as f:
                    html_text = f.read()
                self.assertIn("<!doctype html>", html_text)
                self.assertIn("<table>", html_text)
        finally:
            sys.argv = original_argv
            os.chdir(original_cwd)


if __name__ == "__main__":
    unittest.main()
