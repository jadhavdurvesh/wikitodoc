import html
import re
import sys
from pathlib import Path

def inline(text, base):
    def image(m):
        src=m.group(2)
        url=src if src.startswith(('http://','https://','data:')) else (base/src).resolve().as_uri()
        return f'<img src="{html.escape(url)}" alt="{html.escape(m.group(1))}">'
    text=re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', image, text)
    text=re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    return text

def convert(text, base):
    text=inline(text,base); out=[]; in_code=False; code=[]
    for raw in text.splitlines():
        s=raw.strip()
        if s.startswith('```'):
            if in_code: out.append('<pre><code>'+html.escape('\n'.join(code))+'</code></pre>'); code=[]; in_code=False
            else: in_code=True
            continue
        if in_code: code.append(raw); continue
        m=re.match(r'^(#{1,6})\s+(.*)$',s)
        if m: n=len(m.group(1)); out.append(f'<h{n}>{m.group(2)}</h{n}>'); continue
        if not s: continue
        if s.startswith('- '): out.append(f'<li>{s[2:]}</li>')
        elif s.startswith('> '): out.append(f'<blockquote>{s[2:]}</blockquote>')
        elif s.startswith('<'): out.append(s)
        else: out.append(f'<p>{s}</p>')
    return '\n'.join(out)

def main():
    root=Path(sys.argv[1]).resolve(); out=Path(sys.argv[2]).resolve(); out.parent.mkdir(parents=True,exist_ok=True)
    files=sorted(root.rglob('*.md'))
    if not files: raise SystemExit(f'No Markdown files found under {root}')
    toc=[]; sections=[]
    for i,p in enumerate(files,1):
        title=p.stem.replace('-',' ').replace('_',' ').title(); anchor=f'section-{i}'
        toc.append(f'<li><a href="#{anchor}">{html.escape(title)}</a></li>')
        sections.append(f'<section id="{anchor}"><h1>{html.escape(title)}</h1>{convert(p.read_text(encoding="utf-8",errors="replace"),p.parent)}</section>')
    doc='<!doctype html><html><head><meta charset="utf-8"><title>Maintain.ai Android Documentation</title><style>@page{size:A4;margin:18mm 16mm}body{font-family:Arial,sans-serif;color:#202124;line-height:1.5;font-size:10.5pt}.cover{page-break-after:always;min-height:250mm;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center}.cover h1{font-size:32pt}.cover h2{font-size:18pt;font-weight:normal;color:#666}.toc{page-break-after:always}section{page-break-before:always}section:first-of-type{page-break-before:auto}pre{background:#f4f4f4;padding:4mm;white-space:pre-wrap;overflow-wrap:anywhere;font-family:Consolas,monospace;font-size:8.5pt}img{max-width:100%;height:auto;display:block;margin:5mm auto;page-break-inside:avoid}h1{font-size:20pt;border-bottom:1px solid #ddd;padding-bottom:3mm}h2{font-size:16pt}h3{font-size:13pt}blockquote{border-left:3px solid #bbb;padding-left:4mm;color:#555}</style></head><body><div class="cover"><h1>Maintain.ai Android</h1><h2>Technical Documentation</h2><p>Generated from DeepWiki by WikiToDoc</p></div><div class="toc"><h1>Table of Contents</h1><ol>'+''.join(toc)+'</ol></div>'+''.join(sections)+'</body></html>'
    out.write_text(doc,encoding='utf-8'); print(f'Built HTML from {len(files)} Markdown files: {out}')

if __name__=='__main__': main()