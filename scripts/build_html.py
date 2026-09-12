import base64
import html
import mimetypes
import re
import sys
from pathlib import Path


def local_asset_url(src: str, base: Path) -> str:
    if src.startswith(("http://", "https://", "data:")):
        return src
    path = (base / src).resolve()
    if not path.exists():
        return path.as_uri()
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def md_to_html(text: str, base: Path) -> str:
    # Convert fenced code blocks first.
    text = re.sub(
        r"```(?:[\w+-]*)\n(.*?)```",
        lambda m: "<pre><code>" + html.escape(m.group(1)) + "</code></pre>",
        text,
        flags=re.S,
    )

    # Headings.
    for n in range(6, 0, -1):
        text = re.sub(rf"^({'#' * n}) (.*)$", rf"<h{n}>\2</h{n}>", text, flags=re.M)

    # Local images are embedded directly into the HTML so Chromium cannot lose
    # them when printing the file:// document to PDF.
    def image(m):
        alt = m.group(1)
        src = local_asset_url(m.group(2), base)
        return f'<img src="{html.escape(src)}" alt="{html.escape(alt)}">'

    text = re.sub(r"![([^\]]*)]\(([^)]+)\)", image, text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)

    out = []
    in_list = False
    for line in text.splitlines():
        s = line.strip()
        if not s:
            if in_list:
                out.append("</ul>")
                in_list = False
            continue

        if s.startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{s[2:]}</li>")
        elif s.startswith("> "):
            out.append(f"<blockquote>{s[2:]}</blockquote>")
        elif s.startswith("<"):
            out.append(s)
        else:
            out.append(f"<p>{s}</p>")

    if in_list:
        out.append("</ul>")

    return "\n".join(out)


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: build_html.py <markdown_root> <output_html>")

    root = Path(sys.argv[1]).resolve()
    output = Path(sys.argv[2]).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    files = sorted(root.rglob("*.md"))
    if not files:
        raise SystemExit(f"No Markdown files found under {root}")

    toc = []
    sections = []

    for index, path in enumerate(files, 1):
        title = path.stem.replace("-", " ").replace("_", " ").title()
        content = path.read_text(encoding="utf-8", errors="replace")
        anchor = f"section-{index}"

        toc.append(f'<li><a href="#{anchor}">{html.escape(title)}</a></li>')
        sections.append(
            f'<section id="{anchor}">'
            f"<h1>{html.escape(title)}</h1>"
            f"{md_to_html(content, path.parent)}"
            f"</section>"
        )

    doc = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Maintain.ai Android Documentation</title>
<style>
@page {{ size: A4; margin: 18mm 16mm; }}
body {{ font-family: Arial, sans-serif; color:#202124; line-height:1.5; font-size:10.5pt; }}
.cover {{ page-break-after:always; min-height:250mm; display:flex; flex-direction:column; justify-content:center; align-items:center; text-align:center; }}
.cover h1 {{ font-size:32pt; margin-bottom:8mm; }}
.cover h2 {{ font-size:18pt; font-weight:normal; color:#666; }}
.toc {{ page-break-after:always; }}
section {{ page-break-before:always; }}
section:first-of-type {{ page-break-before:auto; }}
pre {{ background:#f4f4f4; padding:4mm; white-space:pre-wrap; overflow-wrap:anywhere; font-family:Consolas,monospace; font-size:8.5pt; }}
img {{ max-width:100%; height:auto; display:block; margin:6mm auto; page-break-inside:avoid; }}
h1 {{ font-size:20pt; border-bottom:1px solid #ddd; padding-bottom:3mm; }}
h2 {{ font-size:16pt; }}
h3 {{ font-size:13pt; }}
blockquote {{ border-left:3px solid #bbb; padding-left:4mm; color:#555; }}
</style>
</head>
<body>
<div class="cover">
  <h1>Maintain.ai Android</h1>
  <h2>Technical Documentation</h2>
  <p>Generated from DeepWiki by WikiToDoc</p>
</div>
<div class="toc">
  <h1>Table of Contents</h1>
  <ol>{''.join(toc)}</ol>
</div>
{''.join(sections)}
</body>
</html>
"""

    output.write_text(doc, encoding="utf-8")
    print(f"Built HTML from {len(files)} Markdown files: {output}")


if __name__ == "__main__":
    main()
