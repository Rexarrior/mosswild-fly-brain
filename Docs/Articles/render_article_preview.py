#!/usr/bin/env python3
"""Render the Habr article locally using Marked, with collapsible HFM spoilers.

Run from the project root:
    python3 Docs/Articles/render_article_preview.py

Dependencies: Python 3.10+, Node.js and Marked. The defaults use the existing
Codex runtime bundle (Marked 17.0.5); no Python packages are required. A different
installation can be selected with --node and --marked (path to marked.esm.js).
The generated HTML is a local reading preview, not a Habr editor emulator.
"""

from __future__ import annotations

import argparse
import html
from html.parser import HTMLParser
import os
from pathlib import Path
import subprocess
from urllib.parse import quote, unquote, urlsplit, urlunsplit


ARTICLE_DIR = Path(__file__).resolve().parent
RUNTIME_DIR = (
    Path.home()
    / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node"
)

MARKED_DRIVER = """
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
const { marked } = await import(pathToFileURL(process.argv[1]).href);
const source = readFileSync(0, 'utf8');
process.stdout.write(marked.parse(source, { gfm: true, breaks: false }));
"""

CSS = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body { margin: 0; background: #f1f3f3; color: #253136;
  font: 18px/1.65 -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif; }
main { max-width: 980px; margin: 32px auto; padding: 32px 40px 64px;
  background: #fff; border: 1px solid #e1e7e8; border-radius: 12px; }
.preview-note { margin: 0 0 32px; padding: 12px 16px; background: #eef5f5;
  border-left: 3px solid #4b7d7a; font-size: 14px; line-height: 1.5; color: #486360; }
h1, h2, h3 { line-height: 1.22; color: #17272c; }
h1 { font-size: 34px; margin: 0 0 28px; }
h2 { font-size: 26px; margin: 36px 0 18px; }
h3 { font-size: 22px; margin: 28px 0 14px; }
p { margin: 0 0 20px; }
a { color: #216b82; text-underline-offset: 3px; overflow-wrap: anywhere; }
img { display: block; max-width: 100%; height: auto; margin: 24px auto 12px;
  border-radius: 6px; }
p:has(> em:only-child) { color: #667276; font-size: 15px; line-height: 1.5; }
table { border-collapse: collapse; width: 100%; margin: 20px 0;
  font-size: 16px; line-height: 1.5; }
th, td { padding: 10px 12px; border: 1px solid #dfe6e7; text-align: left; }
th { background: #f1f6f6; font-weight: 600; }
code, pre { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
code { padding: 2px 5px; background: #f1f3f4; border-radius: 4px; font-size: .88em; }
pre { overflow-x: auto; padding: 18px; background: #f1f3f4; border-radius: 6px;
  line-height: 1.5; font-size: 14px; }
pre code { padding: 0; background: none; font-size: inherit; }
blockquote { margin: 24px 0; padding-left: 20px; border-left: 3px solid #bed2d4; }
details { margin: 24px 0; border: 1px solid #d3e0e2; border-radius: 8px; }
summary { padding: 14px 18px; cursor: pointer; color: #285e69; font-size: 16px;
  font-weight: 600; background: #f5f9f9; border-radius: 8px; }
summary:hover { background: #edf4f4; }
summary:focus-visible { outline: 3px solid #679aa8; outline-offset: 3px; }
details[open] > summary { border-radius: 8px 8px 0 0; border-bottom: 1px solid #d3e0e2; }
.spoiler-content { padding: 20px 20px 2px; overflow-x: auto; }
.spoiler-content > :last-child { margin-bottom: 18px; }
@media (max-width: 680px) {
  body { font-size: 16px; }
  main { margin: 0; border: 0; border-radius: 0; padding: 22px 18px 40px; }
  h1 { font-size: 28px; }
  .spoiler-content { padding: 16px 12px 2px; }
  th, td { padding: 8px; font-size: 14px; }
}
"""


class PreviewHTML(HTMLParser):
    """Adapt already-rendered HTML; Markdown is parsed by Marked, not here."""

    def __init__(self, output_dir: Path) -> None:
        super().__init__(convert_charrefs=False)
        self.output_dir = output_dir
        self.parts: list[str] = []
        self.spoiler_depth = 0
        self.spoiler_count = 0
        self.image_count = 0

    def relative_image(self, value: str) -> str:
        url = urlsplit(value)
        if url.scheme or url.netloc:
            return value
        local_path = Path(unquote(url.path))
        if not local_path.is_absolute():
            return value
        relative = os.path.relpath(local_path, self.output_dir)
        return urlunsplit(("", "", quote(relative, safe="/"), url.query, url.fragment))

    @staticmethod
    def format_attrs(attrs: list[tuple[str, str | None]]) -> str:
        return "".join(
            f" {name}" if value is None else f' {name}="{html.escape(value, quote=True)}"'
            for name, value in attrs
        )

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "spoiler":
            title = dict(attrs).get("title") or "Подробности"
            self.parts.append(
                f"<details><summary>{html.escape(title)}</summary>"
                '<div class="spoiler-content">'
            )
            self.spoiler_depth += 1
            self.spoiler_count += 1
        elif tag == "img":
            image_attrs = [
                (name, self.relative_image(value) if name == "src" and value else value)
                for name, value in attrs
                if name not in {"loading", "decoding"}
            ]
            image_attrs.extend([("loading", "lazy"), ("decoding", "async")])
            self.parts.append(f"<img{self.format_attrs(image_attrs)}>")
            self.image_count += 1
        else:
            self.parts.append(self.get_starttag_text())

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "img":
            self.handle_starttag(tag, attrs)
        else:
            self.parts.append(self.get_starttag_text())

    def handle_endtag(self, tag: str) -> None:
        if tag == "spoiler":
            if not self.spoiler_depth:
                raise ValueError("Closing </spoiler> has no matching opening tag")
            self.parts.append("</div></details>")
            self.spoiler_depth -= 1
        else:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_entityref(self, name: str) -> None:
        self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.parts.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        self.parts.append(f"<!--{data}-->")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ARTICLE_DIR / "Habr-fly-brain.md")
    parser.add_argument("--output", type=Path, default=ARTICLE_DIR / "Habr-fly-brain.preview.html")
    parser.add_argument("--node", type=Path, default=RUNTIME_DIR / "bin/node")
    parser.add_argument(
        "--marked", type=Path,
        default=RUNTIME_DIR / "node_modules/marked/lib/marked.esm.js",
    )
    args = parser.parse_args()
    for dependency in (args.node, args.marked):
        if not dependency.is_file():
            parser.error(f"Dependency not found: {dependency}; use --node or --marked")

    source = args.source.resolve().read_text(encoding="utf-8")
    result = subprocess.run(
        [str(args.node), "--input-type=module", "-e", MARKED_DRIVER, str(args.marked.resolve())],
        input=source, text=True, capture_output=True, check=True,
    )
    output = args.output.resolve()
    converter = PreviewHTML(output.parent)
    converter.feed(result.stdout)
    converter.close()
    if converter.spoiler_depth:
        raise ValueError("An opening <spoiler> is missing its closing tag")

    document = f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Мозг мухи в Unreal — локальный предпросмотр</title>
<style>{CSS}</style>
</head>
<body>
<main>
<aside class="preview-note">Локальный предпросмотр для проверки текста, изображений
и раскрываемых блоков. Оформление в редакторе Хабра может отличаться.</aside>
<article>
{''.join(converter.parts)}
</article>
</main>
</body>
</html>
"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")
    print(f"Wrote {output}")
    print(f"Closed spoilers: {converter.spoiler_count}; images: {converter.image_count}")


if __name__ == "__main__":
    main()
