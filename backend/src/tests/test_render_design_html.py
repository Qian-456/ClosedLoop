import os
import unittest


def _load_renderer_module():
    """Load the docs competition submission renderer module for testing."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    file_path = os.path.join(
        repo_root, "docs", "competition_submission", "render_design_html.py"
    )
    namespace = {}
    with open(file_path, "r", encoding="utf-8") as f:
        code = f.read()
    exec(compile(code, file_path, "exec"), namespace)
    return namespace


class TestRenderDesignHtml(unittest.TestCase):
    """Test cases for the markdown-to-HTML renderer used by competition submission docs."""

    def test_render_contains_expected_sections(self):
        """Rendered HTML should include key headings and blocks from the markdown."""
        renderer = _load_renderer_module()
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
        md_path = os.path.join(repo_root, "docs", "competition_submission", "03_design.md")

        with open(md_path, "r", encoding="utf-8") as f:
            markdown_text = f.read()

        html_text = renderer["render_markdown_to_html"](markdown_text)

        self.assertIn("<h1>", html_text)
        self.assertIn("背景（S）", html_text)
        self.assertIn("工具调用链路（用户动作闭环）", html_text)
        self.assertIn("<svg", html_text)
        self.assertIn("<code>plan_trip</code>", html_text)
        self.assertIn("fixup_agent", html_text)
        self.assertNotIn(r"fixup\_agent", html_text)

    def test_renderer_wraps_orphan_svg_fragments(self):
        """Renderer should tolerate SVG fragments without an explicit <svg> start tag."""
        renderer = _load_renderer_module()
        markdown_text = (
            "# T\n\n"
            '<rect x="0" y="0" width="10" height="10" />\n'
            "</svg>\n"
        )
        html_text = renderer["render_markdown_to_html"](markdown_text)
        self.assertIn("<svg", html_text)
        self.assertIn('<rect x="0" y="0" width="10" height="10" />', html_text)


if __name__ == "__main__":
    unittest.main()
