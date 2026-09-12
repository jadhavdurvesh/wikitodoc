from pathlib import Path
import html
import re
import sys


def md_to_html(text: str) -> str:
    text = re.sub(r"```(?:[\\w+-]*)\\n(.*?)```", lambda m: "<pre><code>" + html.escape(m.group(1)) + "</code></pre>", text, flags=re.S)
    for n in range(6, 0, -1):
        text = re.sub(rf"^{('#' * n)} (.*)$", rf"<h{n}>\\2</h{n}>", text, flags=re.M)
    text = re.sub(r"!\\[([^]]*)\\]\\(([^)]+)\\)", lambda m: f'<img src="{html.escape(m.group(2))}" alt="{html.escape(m.group(1))}">', text)
    text = re.sub(r"\\[([^]]+)\\]\\(([^)]+)\\)", r'<a href="\\2">\\1</a>', text)
    out=[]; in_list=False
    for line in text.splitlines():
        s=line.strip()
        if not s:
            if in_list: out.append('</ul>'); in_list=False
            continue
        if s.startswith('- '):
            if not in_list: out.append('<ul>'); in_list=True
            out.append(f'<li>{s[2:]}</li>')
        elif s.startswith('> '): out.append(f'<blockquote>{s[2:]}</blockquote>')
        elif s.startswith('<'): out.append(s)
        else: out.append(f'<p>{s}</p>')
    if in_list: out.append('</ul>')
    return '\n'.join(out)


def main():
    root=Path(sys.argv[1]).resolve(); output=Path(sys.argv[2]).resolve(); output.parent.mkdir(parents=True,exist_ok=True)
    files=sorted(root.rglob('*.md'))
    toc=[]; sections=[]
    for i,path in enumerate(files,1):
        title=path.stem.replace('-',' ').replace('_',' ').title()
        content=path.read_text(encoding='utf-8',errors='replace')
        base=path.parent
        content=re.sub(r'!\\[([^]]*)\\]\\((?!https?://)([^)]+)\\)', lambda m:f'![{m.group(1)}]({(base/m.group(2)).resolve().as_uri()})', content)
        anchor=f'section-{i}'; toc.append(f'<li><a href="#{anchor}">{html.escape(title)}</a></li>')
        sections.append(f'<section id="{anchor}"><h1>{html.escape(title)}</h1>{md_to_html(content)}</section>')
    doc=f'''<!doctype html><html><head><meta charset="utf-8"><title>Maintain.ai Android Documentation</title><style>@page{{size:A4;margin:18mm 16mm}}body{{font-family:Arial,sans-serif;color:#202124;line-height:1.5;font-size:10.5pt}}.cover{{page-break-after:always;min-height:250mm;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center}}.cover h1{{font-size:32pt}}.cover h2{{font-size:18pt;font-weight:normal;color:#666}}.toc{{page-break-after:always}}section{{page-break-before:always}}section:first-of-type{{page-break-before:auto}}pre{{background:#f4f4f4;padding:4mm;white-space:pre-wrap;overflow-wrap:anywhere;font-family:Consolas,monospace;font-size:8.5pt}}img{{max-width:100%;height:auto;display:block;margin:5mm auto;page-break-inside:avoid}}h1{{font-size:20pt;border-bottom:1px solid #ddd;padding-bottom:3mm}}h2{{font-size:16pt}}h3{{font-size:13pt}}</style></head><body><div class="cover"><h1>Maintain.ai Android</h1><h2>Technical Documentation</h2><p>Generated from DeepWiki by WikiToDoc</p></div><div class="toc"><h1>Table of Contents</h1><ol>{''.join(toc)}</ol></div>{''.join(sections)}</body></html>'''
    output.write_text(doc,encoding='utf-8')

if __name__=='__main__': main()
