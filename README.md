# WikiToDoc

Automated DeepWiki exporter and documentation builder.

This repository turns a complete DeepWiki repository into:

- Raw Markdown pages
- Mermaid diagrams and image assets
- A single PDF technical document
- A bundled ZIP containing the raw export

Default source: `https://deepwiki.com/jadhavdurvesh/Maintain.ai.android`

## GitHub Actions

Run **Build DeepWiki Documentation** manually from Actions, or let the weekly schedule refresh it.

The workflow publishes a single artifact containing:

```text
Maintain.ai-Android-Documentation.pdf
raw-deepwiki/
  wiki/.../*.md
  wiki/.../images/*.svg
```

The exporter used is [`suwa-sh/deepwiki-to-md`](https://github.com/suwa-sh/deepwiki-to-md), which exports complete wiki pages and preserves Mermaid diagrams as SVG assets.
