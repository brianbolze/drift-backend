"""Spike: fetch a single URL and save the raw HTML.

Validates that httpx (and optionally Firecrawl) can reach manufacturer sites
and we get usable HTML back.

Usage:
    python scripts/spike_fetch.py https://www.hornady.com/bullets/rifle/6.5mm-.264-130-gr-eld-match#!/
    python scripts/spike_fetch.py --firecrawl https://www.hornady.com/bullets/rifle/6.5mm-.264-130-gr-eld-match#!/
"""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env", override=True)
SPIKE_DIR = _ROOT / "data" / "pipeline" / "spike"


async def fetch_httpx(url: str) -> tuple[int, str]:
    """Fetch a URL with httpx and return (status_code, html)."""
    import httpx

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    timeout = httpx.Timeout(30.0, connect=10.0)

    async with httpx.AsyncClient(headers=headers, timeout=timeout, follow_redirects=True, max_redirects=5) as client:
        resp = await client.get(url)
        return resp.status_code, resp.text


async def fetch_firecrawl(url: str) -> tuple[int, str]:
    """Fetch a URL with Firecrawl (JS-rendered) and return (status_code, html)."""
    from firecrawl import FirecrawlApp

    api_key = os.environ.get("FIRECRAWL_API_KEY")
    if not api_key:
        raise SystemExit("FIRECRAWL_API_KEY not set. Export it or add to .env") from None

    app = FirecrawlApp(api_key=api_key)
    doc = app.scrape(url, formats=["html"])

    html = doc.html or ""
    status = getattr(doc.metadata, "statusCode", 200) if doc.metadata else 200
    return status, html


async def main() -> None:
    parser = argparse.ArgumentParser(description="Spike: fetch a single URL")
    parser.add_argument("url", help="URL to fetch")
    parser.add_argument("--firecrawl", action="store_true", help="Use Firecrawl instead of httpx")
    parser.add_argument("-o", "--output", type=Path, default=SPIKE_DIR / "raw.html", help="Output path")
    args = parser.parse_args()

    backend = "firecrawl" if args.firecrawl else "httpx"
    print(f"Fetching: {args.url}")
    print(f"Backend:  {backend}")
    print()

    if args.firecrawl:
        status, html = await fetch_firecrawl(args.url)
    else:
        status, html = await fetch_httpx(args.url)

    print(f"Status:         {status}")
    print(f"Content length: {len(html):,} chars")
    print()
    print("--- First 500 chars ---")
    print(html[:500])
    print("--- End preview ---")

    # Save
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    print(f"\nSaved raw HTML to {args.output} ({len(html):,} chars)")


if __name__ == "__main__":
    asyncio.run(main())
