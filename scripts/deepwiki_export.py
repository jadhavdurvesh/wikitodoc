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
    parsed_base = urlparse(base_url)
    parts = parsed_base.path.strip('/').split('/')
    if len(parts) < 2:
        raise RuntimeError(f'Expected DeepWiki repository URL, got: {base_url}')

    out = Path(args.output)
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
        await page.wait_for_timeout(4000)

        repo_prefix = parsed_base.path.rstrip('/') + '/'
        links = await page.locator('a[href]').evaluate_all(
            """els => els.map(a => ({href:a.href, title:(a.textContent||'').trim()}))
            .filter(x => x.href && x.title)"""
        )

        unique = []
        seen = set()
        for item in links:
            href = urljoin(base_url + '/', item['href']).split('#')[0]
            parsed = urlparse(href)
            title = re.sub(r'\s+', ' ', item['title']).strip()
            if parsed.netloc != parsed_base.netloc:
                continue
            if parsed.path != parsed_base.path and not parsed.path.startswith(repo_prefix):
                continue
            if href in seen or not title:
                continue
            if title.lower() in {'edit wiki', 'share', 'sign in', 'login'}:
                continue
            seen.add(href)
            unique.append({'href': href, 'title': title})

        # The repository root and /1-overview are duplicate Overview pages.
        has_child_overview = any(
            x['href'].rstrip('/').endswith('/1-overview') for x in unique
        )
        if has_child_overview:
            unique = [x for x in unique if x['href'] != base_url]
        else:
            unique = [{'href': base_url, 'title': 'Overview'}] + [
                x for x in unique if x['href'] != base_url
            ]

        print(f'Found {len(unique)} wiki page links')
        index = []

        for number, item in enumerate(unique, 1):
            href = item['href']
            fallback_title = item['title']
            print(f'[{number}/{len(unique)}] {fallback_title} -> {href}')
            await page.goto(href, wait_until='domcontentloaded', timeout=120000)
            await page.wait_for_timeout(1800)

            candidates = [
                page.locator('[class*="prose"]').first,
                page.locator('article').first,
                page.locator('main').first,
            ]
            content = None
            for candidate in candidates:
                if await candidate.count() and (await candidate.inner_text()).strip():
                    content = candidate
                    break
            if content is None:
                raise RuntimeError(f'Could not find wiki content for {href}')

            actual_title = fallback_title
            h1 = page.locator('main h1, article h1, h1').first
            if await h1.count():
                candidate_title = (await h1.inner_text()).strip()
                if candidate_title:
                    actual_title = candidate_title

            html = await content.inner_html()
            soup = BeautifulSoup(html, 'html.parser')
            for node in soup.select('nav, aside, header, footer'):
                node.decompose()
            for node in soup.select('button, [role="button"]'):
                node.decompose()

            # Export every rendered Mermaid SVG. Assets live in target_dir/images.
            svgs = soup.select('svg[id^="mermaid-"], svg[id*="mermaid"], svg.mermaid')
            for diagram_number, svg in enumerate(svgs, 1):
                filename = f'{number:02d}-diagram-{diagram_number:02d}.svg'
                (image_dir / filename).write_text(str(svg), encoding='utf-8')
                replacement = soup.new_tag('p')
                image = soup.new_tag(
                    'img',
                    src=f'images/{filename}',
                    alt=f'Mermaid diagram {diagram_number}',
                )
                replacement.append(image)
                parent = svg.find_parent('pre')
                if parent:
                    parent.replace_with(replacement)
                else:
                    svg.replace_with(image)

            markdown = clean_markdown(
                md(str(soup), heading_style='ATX', bullets='-', code_language='')
            )
            filename = f'{number:02d}-{slugify(actual_title)}.md'
            (target_dir / filename).write_text(
                f'# {actual_title}\n\n{markdown}', encoding='utf-8'
            )
            index.append((actual_title, filename))

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
