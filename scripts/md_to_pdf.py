"""Convert all .md files in docs/ to PDF using markdown + Playwright Chromium."""

from __future__ import annotations

import sys
from pathlib import Path

import markdown
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs"
OUT = SRC / "pdf"

CSS = """
@page { size: A4; margin: 20mm 18mm; }
body {
  font-family: 'Segoe UI', 'Noto Sans', -apple-system, BlinkMacSystemFont, sans-serif;
  font-size: 11pt;
  line-height: 1.55;
  color: #1b1b1b;
  max-width: 100%;
}
h1, h2, h3, h4 { color: #111; margin-top: 1.4em; margin-bottom: 0.5em; page-break-after: avoid; }
h1 { font-size: 22pt; border-bottom: 2px solid #333; padding-bottom: 0.25em; }
h2 { font-size: 17pt; border-bottom: 1px solid #ccc; padding-bottom: 0.2em; }
h3 { font-size: 13pt; }
h4 { font-size: 11pt; }
p { margin: 0.5em 0; }
code { background: #f4f4f4; padding: 1px 5px; border-radius: 3px; font-family: 'Consolas','Courier New',monospace; font-size: 10pt; }
pre { background: #f6f8fa; padding: 10px 12px; border-radius: 5px; overflow-x: auto; page-break-inside: avoid; font-size: 9.5pt; }
pre code { background: transparent; padding: 0; }
blockquote { border-left: 3px solid #aaa; margin: 0.8em 0; padding: 0.1em 1em; color: #555; }
table { border-collapse: collapse; margin: 0.8em 0; width: 100%; }
th, td { border: 1px solid #bbb; padding: 6px 9px; text-align: left; font-size: 10pt; }
th { background: #f0f0f0; }
a { color: #0366d6; text-decoration: none; }
ul, ol { padding-left: 1.5em; }
li { margin: 0.15em 0; }
hr { border: 0; border-top: 1px solid #ccc; margin: 1.5em 0; }
img { max-width: 100%; }
"""

HTML_TPL = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
{body}
</body>
</html>
"""


def md_to_html(md_path: Path) -> str:
    text = md_path.read_text(encoding="utf-8")
    html_body = markdown.markdown(
        text,
        extensions=["extra", "codehilite", "toc", "tables", "fenced_code", "sane_lists"],
        extension_configs={"codehilite": {"guess_lang": False, "css_class": "codehilite"}},
    )
    return HTML_TPL.format(title=md_path.stem, css=CSS, body=html_body)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    md_files = sorted(SRC.glob("*.md"))
    if not md_files:
        print("No .md files found", file=sys.stderr)
        return 1
    print(f"Converting {len(md_files)} files -> {OUT}")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        page = context.new_page()
        for i, md in enumerate(md_files, 1):
            html = md_to_html(md)
            pdf_path = OUT / f"{md.stem}.pdf"
            page.set_content(html, wait_until="load")
            page.emulate_media(media="print")
            page.pdf(
                path=str(pdf_path),
                format="A4",
                margin={"top": "20mm", "bottom": "20mm", "left": "18mm", "right": "18mm"},
                print_background=True,
            )
            size_kb = pdf_path.stat().st_size / 1024
            print(f"  [{i:2d}/{len(md_files)}] {md.name} -> {pdf_path.name} ({size_kb:.0f} KB)")
        browser.close()
    print(f"\nDone. {len(md_files)} PDFs in {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
