#!/usr/bin/env python3
import argparse
import asyncio
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from markdownify import markdownify as md
from playwright.async_api import async_playwright


def slugify(text: str) -> str:
    text = re.sub(r'[^\w\- ]+', '', text, flags=re.UNICODE)
    text = re.sub(r'\s+', '-', text.strip())
    return text or 'page'


def clean_markdown(text: str) -> str:
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip() + '\n'


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('url')
    parser.add_argument('-o', '--output', required=True)
    args = parser.parse_args()

    base_url = args.url.rstrip('/')
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    parts = urlparse(base_url).path.strip('/').split('/')
    target_dir = out / 'wiki' / parts[0] / parts[1]
    target_dir.mkdir(parents=True, exist_ok=True)
    image_dir = target_dir / 'images'
    image_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage'],
        )
        context = await browser.new_context(viewport={'width': 1440, 'height': 1000})
        page = await context.new_page()

        print(f'Opening DeepWiki: {base_url}')
        await page.goto(base_url, wait_until='domcontentloaded', timeout=120000)
        await page.wait_for_timeout(3000)

        # DeepWiki's DOM has changed over time. Try the current sidebar first,
        # then fall back to the repo-page navigation container.
        links = await page.locator('.border-r-border ul li a').evaluate_all(
            """els => els.map(a => ({href:a.href, title:(a.textContent||'').trim()}))
            .filter(x => x.href && x.title)"""
        )
        if not links:
            links = await page.locator('#codebase-wiki-repo-page a[href]').evaluate_all(
                """els => els.map(a => ({href:a.href, title:(a.textContent||'').trim()}))
                .filter(x => x.href && x.title)"""
            )

        origin = urlparse(base_url).netloc
        unique = []
        seen = set()
        for item in links:
            href = urljoin(base_url + '/', item['href']).split('#')[0]
            if urlparse(href).netloc != origin or href in seen:
                continue
            seen.add(href)
            unique.append({'href': href, 'title': item['title'].strip()})

        if not unique:
            unique = [{'href': base_url, 'title': 'Overview'}]

        print(f'Found {len(unique)} wiki pages')
        index = []

        for number, item in enumerate(unique, 1):
            href = item['href']
            title = item['title']
            print(f'[{number}/{len(unique)}] {title}')
            await page.goto(href, wait_until='domcontentloaded', timeout=120000)
            await page.wait_for_timeout(1800)

            candidates = [
                page.locator('.container > div:nth-child(2) .prose').first,
                page.locator('.container > div:nth-child(2) .prose-custom').first,
                page.locator('article').first,
                page.locator('main').first,
            ]
            content = None
            for candidate in candidates:
                if await candidate.count():
                    content = candidate
                    break
            if content is None:
                raise RuntimeError(f'Could not find wiki content for {href}')

            html = await content.inner_html()
            soup = BeautifulSoup(html, 'html.parser')

            # Save rendered Mermaid SVGs as local assets and replace them with
            # normal image elements so the later HTML/PDF stage can render them.
            svgs = soup.select('svg[id^="mermaid-"], svg[id*="mermaid"]')
            for diagram_number, svg in enumerate(svgs, 1):
                filename = f'{number:02d}-diagram-{diagram_number:02d}.svg'
                (image_dir / filename).write_text(str(svg), encoding='utf-8')
                replacement = soup.new_tag('p')
                image = soup.new_tag('img', src=f'images/{filename}', alt=f'Mermaid diagram {diagram_number}')
                replacement.append(image)
                parent = svg.find_parent('pre')
                if parent:
                    parent.replace_with(replacement)
                else:
                    svg.replace_with(image)

            for node in soup.select('button, [role="button"]'):
                node.decompose()

            markdown = clean_markdown(
                md(str(soup), heading_style='ATX', bullets='-', code_language='')
            )
            filename = f'{number:02d}-{slugify(title)}.md'
            (target_dir / filename).write_text(
                f'# {title}\n\n{markdown}', encoding='utf-8'
            )
            index.append((title, filename))

        readme = [
            '# Maintain.ai Android — DeepWiki Export',
            '',
            f'Source: {base_url}',
            '',
            '## Wiki Pages',
            '',
        ]
        readme.extend(f'- [{title}]({filename})' for title, filename in index)
        readme.append('')
        (target_dir / 'README.md').write_text('\n'.join(readme), encoding='utf-8')

        await browser.close()

    print(f'Exported {len(index)} pages to {target_dir}')


if __name__ == '__main__':
    asyncio.run(main())
