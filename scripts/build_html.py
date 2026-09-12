import base64
import html
import mimetypes
import re
import sys
from pathlib import Path

IMAGE_RE = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
LINK_RE = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
HEADING_RE = [re.compile(rf"^({'#' * n}) (.*)$") for n in range(6, 0, -1)]
DIAGRAM_RE = re.compile(r"^\*{0,2}Diagram:\s*(.*?)\*{0,2}$", re.I)
FENCE_RE = re.compile(r'^\s*```')


def asset_data_url(path):
    mime = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def embed_image(path, alt):
    if not path.exists():
        return f'<p><strong>Missing image asset:</strong> {html.escape(str(path))}</p>'
    return (
        '<figure class="diagram">'
        f'<img src="{asset_data_url(path)}" alt="{html.escape(alt)}">'
        f'<figcaption>{html.escape(alt)}</figcaption>'
        '</figure>'
    )


def md_to_html(text, page_path):
    out = []
    in_code = False
    code_lines = []
    in_list = False
    embedded = 0

    def close_list():
        nonlocal in_list
        if in_list:
            out.append('</ul>')
            in_list = False

    def resolve_asset(src):
        if src.startswith(('http://', 'https://', 'data:')):
            return None
        candidate = (page_path.parent / src).resolve()
        return candidate if candidate.exists() else None

    for raw in text.splitlines():
        line = raw.rstrip('\n')
        if FENCE_RE.match(line):
            close_list()
            if in_code:
                out.append('<pre><code>' + html.escape('\n'.join(code_lines)) + '</code></pre>')
                code_lines = []
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue

        s = line.strip()
        if not s:
            close_list()
            continue

        dm = DIAGRAM_RE.match(s)
        if dm:
            # The actual SVG is represented by the following Markdown image/link.
            # Keep the label here, but embed the asset exactly once below.
            close_list()
            out.append(f'<h3>Diagram: {html.escape(dm.group(1).strip("* ").strip())}</h3>')
            continue

        matched = False
        for hr in HEADING_RE:
            hm = hr.match(s)
            if hm:
                close_list()
                level = len(hm.group(1))
                out.append(f'<h{level}>{html.escape(hm.group(2))}</h{level}>')
                matched = True
                break
        if matched:
            continue

        if s.startswith('- '):
            if not in_list:
                out.append('<ul>')
                in_list = True
            out.append(f'<li>{s[2:]}</li>')
            continue

        if s.startswith('> '):
            close_list()
            out.append(f'<blockquote>{html.escape(s[2:])}</blockquote>')
            continue

        if s.startswith('<img '):
            close_list()
            out.append(s)
            continue

        if s.startswith('<'):
            close_list()
            out.append(s)
            continue

        def image_repl(match):
            nonlocal embedded
            src = match.group(2).strip()
            asset = resolve_asset(src)
            if asset and asset.suffix.lower() == '.svg':
                embedded += 1
                return embed_image(asset, match.group(1).strip() or asset.stem)
            return f'<img src="{html.escape(src)}" alt="{html.escape(match.group(1))}">' 

        def link_repl(match):
            nonlocal embedded
            label = match.group(1)
            src = match.group(2).strip()
            asset = resolve_asset(src)
            if asset and asset.suffix.lower() == '.svg':
                embedded += 1
                return embed_image(asset, label.strip() or asset.stem)
            return f'<a href="{html.escape(src)}">{html.escape(label)}</a>'

        s = IMAGE_RE.sub(image_repl, s)
        s = LINK_RE.sub(link_repl, s)
        out.append(f'<p>{s}</p>')

    close_list()
    if in_code:
        out.append('<pre><code>' + html.escape('\n'.join(code_lines)) + '</code></pre>')

    return '\n'.join(out), embedded


def main():
    if len(sys.argv) != 3:
        raise SystemExit('Usage: build_html.py <markdown_root> <output_html>')

    root = Path(sys.argv[1]).resolve()
    output = Path(sys.argv[2]).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    files = sorted(root.rglob('*.md'))
    if not files:
        raise SystemExit(f'No Markdown files found under {root}')

    toc = []
    sections = []
    embedded_total = 0

    for i, path in enumerate(files, 1):
        title = path.stem.replace('-', ' ').replace('_', ' ').title()
        anchor = f'section-{i}'
        body, embedded = md_to_html(path.read_text(encoding='utf-8', errors='replace'), path)
        embedded_total += embedded
        toc.append(f'<li><a href="#{anchor}">{html.escape(title)}</a></li>')
        sections.append(
            f'<section id="{anchor}"><h1>{html.escape(title)}</h1>{body}</section>'
        )

    total_diagrams = len(list(root.rglob('*.svg')))

    doc = (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<title>Maintain.ai Android Documentation</title>'
        '<style>@page{size:A4;margin:16mm 15mm}'
        'body{font-family:Arial,sans-serif;color:#202124;line-height:1.5;font-size:10.5pt}'
        '.cover{page-break-after:always;min-height:250mm;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center}'
        '.cover h1{font-size:32pt;margin-bottom:8mm}.cover h2{font-size:18pt;font-weight:normal;color:#666}'
        '.toc{page-break-after:always}section{page-break-before:always}section:first-of-type{page-break-before:auto}'
        'pre{background:#f4f4f4;padding:4mm;white-space:pre-wrap;overflow-wrap:anywhere;font-family:Consolas,monospace;font-size:8.5pt}'
        '.diagram{margin:7mm 0 9mm;text-align:center;page-break-inside:avoid}'
        '.diagram img{max-width:100%;max-height:180mm;height:auto;display:block;margin:0 auto}'
        '.diagram figcaption{margin-top:2mm;font-size:9pt;color:#666}'
        'h1{font-size:20pt;border-bottom:1px solid #ddd;padding-bottom:3mm}h2{font-size:16pt}h3{font-size:13pt}'
        'blockquote{border-left:3px solid #bbb;padding-left:4mm;color:#555}'
        '</style></head><body>'
        '<div class="cover"><h1>Maintain.ai Android</h1><h2>Technical Documentation</h2>'
        '<p>Generated from DeepWiki by WikiToDoc</p>'
        f'<p>Exported diagrams: {total_diagrams}</p></div>'
        '<div class="toc"><h1>Table of Contents</h1><ol>' + ''.join(toc) + '</ol></div>'
        + ''.join(sections) + '</body></html>'
    )

    output.write_text(doc, encoding='utf-8')
    print(f'Built HTML from {len(files)} Markdown files and {total_diagrams} SVG diagrams.')
    print(f'Embedded SVG diagrams in HTML: {embedded_total}')
    if embedded_total != total_diagrams:
        raise SystemExit(
            f'Diagram mismatch: exported {total_diagrams} SVG files but embedded {embedded_total}'
        )


if __name__ == '__main__':
    main()
