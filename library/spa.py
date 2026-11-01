"""Serves the React single-page app.

The Vite build produces frontend/dist/index.html. For every page request we inject, server-side:
  * SEO tags (title, description, canonical, Open Graph, JSON-LD) so ad crawlers and link previews work,
  * the product's theme colours as CSS variables (no colour flash before React starts),
  * "boot" JSON (site settings + the product being viewed) so React paints without an extra request.

Nothing here is executable script: boot data lives in <script type="application/json">, which a strict
Content-Security-Policy (script-src 'self') allows. All values are HTML-escaped or JSON-escaped.
"""
from __future__ import annotations

import html
import json
from typing import Any, Dict, Optional

from library.config import BASE_DIR, base_url

DIST = BASE_DIR / "frontend" / "dist"
INDEX = DIST / "index.html"
HEAD_MARK = "<!--SSR:HEAD-->"
BOOT_MARK = "<!--SSR:BOOT-->"

FALLBACK = (
    '<!doctype html><html lang="en"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width, initial-scale=1">' + HEAD_MARK + "</head>"
    '<body><div id="root"></div>' + BOOT_MARK +
    '<p style="font:16px system-ui;padding:2rem;max-width:40rem">The React frontend has not been built yet. '
    "Run <code>cd frontend &amp;&amp; npm install &amp;&amp; npm run build</code>, then reload this page.</p>"
    "</body></html>"
)

_cache: Dict[str, Any] = {"mtime": None, "html": FALLBACK, "fonts": ""}

_ESC = {ord("<"): "\\u003c", ord(">"): "\\u003e", ord("&"): "\\u0026", 0x2028: "\\u2028", 0x2029: "\\u2029"}


def json_for_html(obj: Any) -> str:
    """JSON that is safe to place inside a <script> element (cannot close the tag or start a comment)."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).translate(_ESC)


def _shell() -> tuple[str, str]:
    """Return (index.html text, font-preload tags). Re-read only when the build changes."""
    try:
        mtime = INDEX.stat().st_mtime
    except OSError:
        return FALLBACK, ""
    if _cache["mtime"] != mtime:
        text = INDEX.read_text(encoding="utf-8")
        if HEAD_MARK not in text:
            text = text.replace("</head>", HEAD_MARK + "</head>", 1)
        if BOOT_MARK not in text:
            text = text.replace("</body>", BOOT_MARK + "</body>", 1)
        assets = DIST / "assets"
        fonts = "".join(
            f'<link rel="preload" href="/static/assets/{p.name}" as="font" type="font/woff2" crossorigin>'
            for p in sorted(assets.glob("*.woff2")) if p.name.startswith(("display", "body"))
        ) if assets.is_dir() else ""
        _cache.update(mtime=mtime, html=text, fonts=fonts)
    return _cache["html"], _cache["fonts"]


def _theme_css(theme: Dict[str, str]) -> str:
    # Values were validated as #RRGGBB when the catalog loaded; escape anyway.
    pairs = ";".join(f"--{k.replace('_', '-')}:{html.escape(str(v))}" for k, v in theme.items())
    return f"<style>:root{{{pairs}}}</style>"


def render_page(*, title: str, description: str, path: str, robots: str = "index,follow",
                theme: Optional[Dict[str, str]] = None, jsonld: Optional[Dict[str, Any]] = None,
                boot: Optional[Dict[str, Any]] = None, h1: str = "", blurb: str = "") -> str:
    shell, fonts = _shell()
    canonical = f"{base_url()}{path}"
    t, d, c = html.escape(title), html.escape(description, quote=True), html.escape(canonical, quote=True)
    color = html.escape((theme or {}).get("hero_bg", "#2B2BFF"), quote=True)
    ld_tag = f'<script type="application/ld+json">{json_for_html(jsonld)}</script>' if jsonld else ""
    head = (
        f"<title>{t}</title>"
        f'<meta name="description" content="{d}">'
        f'<meta name="robots" content="{html.escape(robots, quote=True)}">'
        f'<link rel="canonical" href="{c}">'
        f'<link rel="icon" href="/favicon.svg" type="image/svg+xml">'
        f'<meta name="theme-color" content="{color}">'
        f'<meta property="og:title" content="{html.escape(title, quote=True)}">'
        f'<meta property="og:description" content="{d}">'
        f'<meta property="og:url" content="{c}"><meta property="og:type" content="website">'
        f'<meta name="twitter:card" content="summary">'
        f"{fonts}"
        f"{_theme_css(theme) if theme else ''}"
        f"{ld_tag}"
    )
    body = ""
    if h1:
        body += f"<noscript><main><h1>{html.escape(h1)}</h1><p>{html.escape(blurb)}</p></main></noscript>"
    body += f'<script id="boot" type="application/json">{json_for_html(boot or {})}</script>'
    return shell.replace(HEAD_MARK, head, 1).replace(BOOT_MARK, body, 1)
