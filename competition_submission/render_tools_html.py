"""Render the competition tools markdown into a self-contained HTML file."""

from __future__ import annotations

import argparse
import html as _html
import os
import re
from typing import Iterable, List, Optional, Tuple


_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
_TABLE_SEPARATOR_RE = re.compile(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")


def _unescape_markdown(text: str) -> str:
    """Unescape a small subset of Markdown escapes."""

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
    """Render inline code and bold markup."""

    text = _unescape_markdown(text)

    def _code_sub(match: re.Match[str]) -> str:
        return f"<code>{_html.escape(match.group(1), quote=False)}</code>"

    text = _INLINE_CODE_RE.sub(_code_sub, text)
    text = _BOLD_RE.sub(
        lambda m: f"<strong>{_html.escape(m.group(1), quote=False)}</strong>",
        text,
    )
    escaped = _html.escape(text, quote=False)
    escaped = escaped.replace("&lt;code&gt;", "<code>").replace("&lt;/code&gt;", "</code>")
    escaped = escaped.replace("&lt;strong&gt;", "<strong>").replace("&lt;/strong&gt;", "</strong>")
    return escaped


def _normalize_title(title: str) -> str:
    """Normalize a Markdown title line to a plain string."""

    title = title.strip()
    if title.startswith("#"):
        title = title.lstrip("#").strip()
    return title or "Document"


def _iter_lines(text: str) -> Iterable[str]:
    """Iterate input lines with newline removed."""

    for line in text.splitlines():
        yield line.rstrip("\n")


def _split_table_row(line: str) -> list[str]:
    raw = line.strip()
    if raw.startswith("|"):
        raw = raw[1:]
    if raw.endswith("|"):
        raw = raw[:-1]
    return [cell.strip() for cell in raw.split("|")]


def _is_table_row(line: str) -> bool:
    stripped = line.strip()
    return "|" in stripped and not stripped.startswith("```")


def render_markdown_to_html(markdown_text: str) -> str:
    """Convert a limited subset of Markdown into a self-contained HTML page."""

    lines = list(_iter_lines(markdown_text))
    doc_title = _normalize_title(lines[0] if lines else "Document")

    out: List[str] = []
    in_code: bool = False
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
        nonlocal in_code, code_lines
        if not in_code:
            return
        escaped = _html.escape("\n".join(code_lines), quote=False)
        out.append(f"<pre><code>{escaped}</code></pre>")
        in_code = False
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

    idx = 0
    while idx < len(lines):
        line = lines[idx]

        if in_code:
            if line.strip().startswith("```"):
                _flush_code()
            else:
                code_lines.append(line)
            idx += 1
            continue

        if in_raw_html:
            raw_html_lines.append(line)
            if "</svg>" in line:
                _flush_raw_html()
            idx += 1
            continue

        stripped = line.strip()

        if stripped.startswith("```"):
            _flush_paragraph()
            _flush_ul()
            in_code = True
            code_lines = []
            idx += 1
            continue

        if stripped.startswith("<svg"):
            _flush_paragraph()
            _flush_ul()
            in_raw_html = True
            raw_html_lines = [line]
            if "</svg>" in line:
                _flush_raw_html()
            idx += 1
            continue

        if _is_svg_fragment_line(stripped):
            _flush_paragraph()
            _flush_ul()
            in_raw_html = True
            auto_wrapped_svg = not stripped.startswith("<svg")
            raw_html_lines = []
            if auto_wrapped_svg:
                raw_html_lines.append(
                    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1040 520" role="img" style="max-width: 100%; height: auto; display: block; margin: 10px 0 12px;">'
                )
            raw_html_lines.append(line)
            if "</svg>" in line:
                _flush_raw_html()
            idx += 1
            continue

        if not stripped:
            _flush_paragraph()
            _flush_ul()
            _flush_raw_html()
            idx += 1
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
            idx += 1
            continue

        next_line = lines[idx + 1] if idx + 1 < len(lines) else ""
        if _is_table_row(stripped) and _TABLE_SEPARATOR_RE.match(next_line.strip()):
            _flush_paragraph()
            _flush_ul()
            header_cells = _split_table_row(stripped)
            idx += 2
            body_rows: list[list[str]] = []
            while idx < len(lines):
                row_line = lines[idx]
                if not row_line.strip():
                    break
                if not _is_table_row(row_line):
                    break
                body_rows.append(_split_table_row(row_line))
                idx += 1
            out.append("<table>")
            out.append("<thead><tr>")
            for cell in header_cells:
                out.append(f"<th>{_render_inlines(cell)}</th>")
            out.append("</tr></thead>")
            out.append("<tbody>")
            for row in body_rows:
                out.append("<tr>")
                for cell in row:
                    out.append(f"<td>{_render_inlines(cell)}</td>")
                out.append("</tr>")
            out.append("</tbody></table>")
            continue

        if stripped.startswith("- "):
            _flush_paragraph()
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            item = stripped[2:].strip()
            out.append(f"<li>{_render_inlines(item)}</li>")
            idx += 1
            continue

        hard_break = line.endswith("  ")
        paragraph_lines.append((stripped, hard_break))
        idx += 1

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
        line-height: 1.45;
        font-size: 14px;
      }}
      body {{
        margin: 0;
        padding: 16px 12px;
      }}
      .page {{
        max-width: 980px;
        margin: 0 auto;
      }}
      h1 {{
        font-size: 24px;
        margin: 0 0 8px;
        letter-spacing: 0.2px;
      }}
      h2 {{
        font-size: 16px;
        margin: 12px 0 6px;
        padding-top: 2px;
        border-top: 1px solid var(--border);
      }}
      p {{
        margin: 6px 0;
      }}
      ul {{
        margin: 4px 0 8px 18px;
        padding: 0;
      }}
      li {{
        margin: 2px 0;
      }}
      table {{
        width: 100%;
        border-collapse: collapse;
        margin: 10px 0 12px;
        border: 1px solid var(--border);
        border-radius: 8px;
        overflow: hidden;
      }}
      th,
      td {{
        border: 1px solid var(--border);
        padding: 8px 10px;
        vertical-align: top;
        text-align: left;
        font-size: 13px;
      }}
      th {{
        background: #f9fafb;
        font-weight: 600;
      }}
      pre {{
        background: var(--code-bg);
        color: var(--code-fg);
        padding: 10px 12px;
        border-radius: 10px;
        overflow: auto;
        margin: 8px 0 10px;
      }}
      code {{
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono",
          "Courier New", monospace;
        font-size: 12px;
        background: rgba(17, 24, 39, 0.06);
        padding: 0 4px;
        border-radius: 6px;
      }}
      pre code {{
        background: transparent;
        padding: 0;
        border-radius: 0;
        font-size: 12px;
      }}
    </style>
  </head>
  <body>
    <div class="page">
      {body}
    </div>
  </body>
</html>
"""


def main() -> None:
    """Render markdown file into HTML file."""

    base_dir = os.path.abspath(os.path.dirname(__file__))

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default="02_tools.md",
        help="Markdown input file path.",
    )
    parser.add_argument(
        "--output",
        default="02_tools.html",
        help="HTML output file path.",
    )
    args = parser.parse_args()

    input_path = args.input
    if not os.path.isabs(input_path):
        input_path = os.path.join(base_dir, input_path)
        if not os.path.exists(input_path):
            input_path = args.input

    output_path = args.output
    if not os.path.isabs(output_path):
        output_path = os.path.join(base_dir, output_path)

    with open(input_path, "r", encoding="utf-8") as f:
        markdown_text = f.read()
    html_text = render_markdown_to_html(markdown_text)
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_text)


if __name__ == "__main__":
    main()
