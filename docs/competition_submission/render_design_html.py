"""Render the competition design markdown into a self-contained HTML file."""

from __future__ import annotations

import argparse
import html as _html
import os
import re
from typing import Iterable, List, Optional, Tuple


_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")


def _unescape_markdown(text: str) -> str:
    return (
        text.replace(r"\_", "_")
        .replace(r"\*", "*")
        .replace(r"\`", "`")
        .replace(r"\[", "[")
        .replace(r"\]", "]")
        .replace(r"\(", "(")
        .replace(r"\)", ")")
    )


def _render_inlines(text: str) -> str:
    text = _unescape_markdown(text)

    def _code_sub(match: re.Match[str]) -> str:
        return f"<code>{_html.escape(match.group(1), quote=False)}</code>"

    text = _INLINE_CODE_RE.sub(_code_sub, text)
    text = _BOLD_RE.sub(lambda m: f"<strong>{_html.escape(m.group(1), quote=False)}</strong>", text)
    return _html.escape(text, quote=False).replace("&lt;code&gt;", "<code>").replace("&lt;/code&gt;", "</code>").replace("&lt;strong&gt;", "<strong>").replace("&lt;/strong&gt;", "</strong>")


def _normalize_title(title: str) -> str:
    title = title.strip()
    if title.startswith("#"):
        title = title.lstrip("#").strip()
    return title or "Document"


def _iter_lines(text: str) -> Iterable[str]:
    for line in text.splitlines():
        yield line.rstrip("\n")


def render_markdown_to_html(markdown_text: str) -> str:
    lines = list(_iter_lines(markdown_text))
    doc_title = _normalize_title(lines[0] if lines else "Document")

    out: List[str] = []
    in_code: bool = False
    code_lang: Optional[str] = None
    code_lines: List[str] = []
    in_ul: bool = False
    in_raw_html: bool = False
    raw_html_lines: List[str] = []
    auto_wrapped_svg: bool = False
    paragraph_lines: List[Tuple[str, bool]] = []

    def _flush_paragraph() -> None:
        nonlocal paragraph_lines
        if not paragraph_lines:
            return
        parts: List[str] = []
        for line, hard_break in paragraph_lines:
            rendered = _render_inlines(line)
            parts.append(rendered)
            if hard_break:
                parts.append("<br />")
        while parts and parts[-1] == "<br />":
            parts.pop()
        out.append(f"<p>{' '.join(parts)}</p>")
        paragraph_lines = []

    def _flush_ul() -> None:
        nonlocal in_ul
        if in_ul:
            out.append("</ul>")
            in_ul = False

    def _flush_code() -> None:
        nonlocal in_code, code_lang, code_lines
        if not in_code:
            return
        escaped = _html.escape("\n".join(code_lines), quote=False)
        out.append(f"<pre><code>{escaped}</code></pre>")
        in_code = False
        code_lang = None
        code_lines = []

    def _flush_raw_html() -> None:
        nonlocal in_raw_html, raw_html_lines, auto_wrapped_svg
        if not in_raw_html:
            return
        if auto_wrapped_svg:
            if not any("</svg>" in l for l in raw_html_lines):
                raw_html_lines.append("</svg>")
            auto_wrapped_svg = False
        out.append("\n".join(raw_html_lines))
        in_raw_html = False
        raw_html_lines = []

    def _is_svg_fragment_line(text: str) -> bool:
        if not text:
            return False
        if text.startswith("</svg"):
            return True
        return text.startswith("<rect") or text.startswith("<text") or text.startswith("<path") or text.startswith("<defs") or text.startswith("<marker") or text.startswith("<style")

    for line in lines:
        if in_code:
            if line.strip().startswith("```"):
                _flush_code()
            else:
                code_lines.append(line)
            continue

        if in_raw_html:
            raw_html_lines.append(line)
            if "</svg>" in line:
                _flush_raw_html()
            continue

        stripped = line.strip()

        if stripped.startswith("```"):
            _flush_paragraph()
            _flush_ul()
            in_code = True
            code_lang = stripped[3:].strip() or None
            code_lines = []
            continue

        if stripped.startswith("<svg"):
            _flush_paragraph()
            _flush_ul()
            in_raw_html = True
            raw_html_lines = [line]
            if "</svg>" in line:
                _flush_raw_html()
            continue

        if _is_svg_fragment_line(stripped):
            _flush_paragraph()
            _flush_ul()
            in_raw_html = True
            auto_wrapped_svg = not stripped.startswith("<svg")
            raw_html_lines = []
            if auto_wrapped_svg:
                raw_html_lines.append(
                    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 980 520" role="img" style="max-width: 100%; height: auto; display: block; margin: 10px 0 12px;">'
                )
            raw_html_lines.append(line)
            if "</svg>" in line:
                _flush_raw_html()
            continue

        if not stripped:
            _flush_paragraph()
            _flush_ul()
            _flush_raw_html()
            continue

        if stripped.startswith("#"):
            _flush_paragraph()
            _flush_ul()
            level = len(stripped) - len(stripped.lstrip("#"))
            heading_text = stripped[level:].strip()
            if level == 1:
                out.append(f"<h1>{_render_inlines(heading_text)}</h1>")
            elif level == 2:
                out.append(f"<h2>{_render_inlines(heading_text)}</h2>")
            else:
                out.append(
                    f'<h3 style="margin: 10px 0 6px; font-size: 15px;">{_render_inlines(heading_text)}</h3>'
                )
            continue

        if stripped.startswith("- "):
            _flush_paragraph()
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            item = stripped[2:].strip()
            out.append(f"<li>{_render_inlines(item)}</li>")
            continue

        hard_break = line.endswith("  ")
        paragraph_lines.append((stripped, hard_break))

    _flush_paragraph()
    _flush_ul()
    _flush_code()
    _flush_raw_html()

    body_html = "\n".join(out)
    return _HTML_TEMPLATE.format(title=_html.escape(doc_title, quote=True), body=body_html)


_HTML_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    <style>
      :root {{
        --fg: #111827;
        --muted: #374151;
        --bg: #ffffff;
        --code-bg: #0b1020;
        --code-fg: #e5e7eb;
        --border: #e5e7eb;
      }}
      html,
      body {{
        background: var(--bg);
        color: var(--fg);
        font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Arial, "Noto Sans SC",
          "Microsoft YaHei", sans-serif;
        line-height: 1.6;
      }}
      body {{
        margin: 0;
        padding: 24px 14px;
      }}
      .page {{
        max-width: 980px;
        margin: 0 auto;
      }}
      h1 {{
        font-size: 28px;
        margin: 0 0 10px;
        letter-spacing: 0.2px;
      }}
      h2 {{
        font-size: 18px;
        margin: 18px 0 8px;
        padding-top: 4px;
        border-top: 1px solid var(--border);
      }}
      p {{
        margin: 8px 0;
      }}
      ul {{
        margin: 6px 0 10px 18px;
        padding: 0;
      }}
      li {{
        margin: 4px 0;
      }}
      code {{
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono",
          "Courier New", monospace;
      }}
      pre {{
        background: var(--code-bg);
        color: var(--code-fg);
        padding: 12px 14px;
        border-radius: 10px;
        overflow: auto;
        line-height: 1.5;
        font-size: 13px;
        margin: 10px 0 14px;
      }}
      pre code {{
        color: inherit;
      }}
      .muted {{
        color: var(--muted);
      }}
      .badge {{
        display: inline-block;
        padding: 2px 8px;
        border: 1px solid var(--border);
        border-radius: 999px;
        font-size: 12px;
        color: var(--muted);
        margin-right: 6px;
      }}
    </style>
  </head>
  <body>
    <main class="page">
{body}
    </main>
  </body>
</html>
"""


def _resolve_repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))


def render_file(md_path: str, html_path: str) -> None:
    with open(md_path, "r", encoding="utf-8") as f:
        markdown_text = f.read()

    html_text = render_markdown_to_html(markdown_text)

    with open(html_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(html_text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--md", default=os.path.join(os.path.dirname(__file__), "03_design.md"))
    parser.add_argument("--html", default=os.path.join(os.path.dirname(__file__), "03_design.html"))
    args = parser.parse_args()
    render_file(args.md, args.html)


if __name__ == "__main__":
    main()
