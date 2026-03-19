# flake8: noqa: E501 B950
"""HTML reducer — multi-strategy progressive stripping for LLM extraction.

Three strategies, selected by domain:
  - generic (default): 14-step progressive reduction. Works for most sites.
  - main_content: extract <main> (or custom CSS selector) + JSON-LD, then reduce.
    For sites where <main> has all product data but the page is bloated with JS/consent.
  - jsonld_only: extract JSON-LD + meta tags only. For SPAs where the HTML body is
    a useless JS app shell but structured data exists in JSON-LD.

Key design principle: remove CSS aggressively, scripts selectively.
Many manufacturer sites embed structured product data inside inline <script>
tags (JSON-LD, Angular bootstraps, __NEXT_DATA__, etc.). Blindly removing
all scripts destroys the richest extraction signal.
"""

from __future__ import annotations

import json
import logging
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Comment, Tag

from drift.pipeline.config import (
    DOMAIN_CONTENT_SELECTORS,
    DOMAIN_REDUCER_STRATEGY,
    REDUCE_MIN_SIZE,
    REDUCE_TARGET_SIZE,
)

logger = logging.getLogger(__name__)

# Patterns that identify tracking / analytics inline scripts (case-insensitive).
TRACKING_PATTERNS = re.compile(
    r"google.analytics|googletagmanager|gtag\s*\(|"
    r"fbq\s*\(|facebook\.net|"
    r"rdt\s*\(|redditstatic|"
    r"dataLayer\.push|"
    r"hotjar|hj\s*\(|"
    r"_satellite|_tealium|"
    r"adsbygoogle|googlesyndication|"
    r"doubleclick\.net|"
    r"amplitude\.getInstance|"
    r"mixpanel\.track|"
    r"segment\.com|analytics\.js|"
    r"tiktok\.com/i18n|"
    r"pinterest.*pinit|"
    r"klaviyo|"
    r"optimizely|"
    r"snaptr\s*\(|snap\.licdn",
    re.IGNORECASE,
)

_MIN_JSON_KEYS = 3
_JSON_KEY_RE = re.compile(r'"[a-zA-Z_]\w*"\s*:')

# Attributes worth keeping — everything else is presentation / framework noise
KEEP_ATTRS = {"href", "alt", "title", "type", "content", "name", "value", "property", "rel"}


def _text_len(soup: BeautifulSoup) -> int:
    return len(str(soup))


def _class_word_match(tag: Tag, keyword: str) -> bool:
    """Check if a tag has a class that IS the keyword or is keyword-delimited.

    Matches: "social-share", "social", "my-social-widget"
    Does NOT match: "antisocial", "modals-container" for "modal"

    The rule: keyword must appear as a standalone hyphen-delimited segment.
    """
    classes = tag.get("class", [])
    if isinstance(classes, str):
        classes = classes.split()
    for cls in classes:
        segments = cls.lower().split("-")
        if keyword.lower() in segments:
            return True
    return False


def _remove_by_class_word(soup: BeautifulSoup, keyword: str) -> None:
    """Remove elements whose class contains keyword as a whole hyphenated segment."""
    targets = [
        tag
        for tag in soup.find_all(True)
        if isinstance(tag, Tag)
        and tag.attrs is not None
        and tag.name not in ("body", "html")
        and _class_word_match(tag, keyword)
    ]
    for tag in targets:
        tag.decompose()


def _remove_tags(soup: BeautifulSoup, selector: str) -> None:
    for el in soup.select(selector):
        if el.name in ("body", "html"):
            continue
        el.decompose()


def _remove_comments(soup: BeautifulSoup) -> None:
    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()


def _is_data_bearing_script(tag: Tag) -> bool:
    """Return True if an inline script likely contains structured product data."""
    text = tag.get_text()

    if tag.get("type", "").lower() == "application/ld+json":
        return True

    if len(_JSON_KEY_RE.findall(text[:2000])) >= _MIN_JSON_KEYS:
        return True

    script_id = tag.get("id", "").lower()
    if script_id in ("__next_data__", "__nuxt_data__", "__gatsby_data__", "__remix_data__"):
        return True

    return False


def _is_tracking_script(tag: Tag) -> bool:
    """Return True if an inline script is tracking/analytics junk."""
    text = tag.get_text()
    return bool(TRACKING_PATTERNS.search(text[:3000]))


def _smart_remove_scripts(soup: BeautifulSoup) -> None:
    """Remove scripts selectively — keep data-bearing ones, remove the rest."""
    for script in soup.find_all("script"):
        if not isinstance(script, Tag):
            continue

        if script.get("src"):
            script.decompose()
            continue

        if _is_data_bearing_script(script):
            text = script.get_text(strip=True)
            if script.get("type", "").lower() == "application/ld+json":
                try:
                    data = json.loads(text)
                    text = json.dumps(data, separators=(",", ":"))
                except (json.JSONDecodeError, TypeError):
                    pass
            script.replace_with(f"\n<!-- DATA: {text} -->\n")
        elif _is_tracking_script(script):
            script.decompose()
        else:
            if len(script.get_text()) < 500:
                script.decompose()
            else:
                text = script.get_text(strip=True)
                script.replace_with(f"\n<!-- DATA: {text} -->\n")


def _strip_attrs(soup: BeautifulSoup, keep: set[str] | None = None) -> None:
    """Strip attributes, keeping only semantically useful ones."""
    keep = keep if keep is not None else KEEP_ATTRS
    for tag in soup.find_all(True):
        if not isinstance(tag, Tag):
            continue
        attrs = dict(tag.attrs)
        for attr in attrs:
            if attr not in keep:
                del tag.attrs[attr]


def _collapse_whitespace(html: str) -> str:
    html = re.sub(r"\n\s*\n+", "\n", html)
    html = re.sub(r"[ \t]+", " ", html)
    return html.strip()


def _extract_jsonld_comments(soup: BeautifulSoup) -> list[str]:
    """Extract JSON-LD scripts as DATA comments, compacting the JSON."""
    comments = []
    for script in soup.find_all("script", type="application/ld+json"):
        text = script.get_text(strip=True)
        try:
            data = json.loads(text)
            text = json.dumps(data, separators=(",", ":"))
        except (json.JSONDecodeError, TypeError):
            pass
        comments.append(f"<!-- DATA: {text} -->")
    return comments


def _domain_from_url(url: str) -> str:
    """Extract domain (with www prefix if present) from a URL."""
    return urlparse(url).netloc.lower()


class HtmlReducer:
    """Multi-strategy HTML reducer that preserves product data while stripping chrome."""

    def __init__(self, target_size: int = REDUCE_TARGET_SIZE, min_size: int = REDUCE_MIN_SIZE):
        self.target_size = target_size
        self.min_size = min_size

    def reduce(self, html: str, url: str | None = None) -> tuple[str, dict]:
        """Reduce HTML using strategy selected by domain. Returns (reduced_html, metadata)."""
        strategy = "generic"
        if url:
            domain = _domain_from_url(url)
            strategy = DOMAIN_REDUCER_STRATEGY.get(domain, "generic")

        if strategy == "main_content":
            return self._reduce_main_content(html, domain)
        elif strategy == "jsonld_only":
            return self._reduce_jsonld_only(html)
        else:
            return self._reduce_generic(html, strategy_name="generic")

    # ── Strategy: generic ────────────────────────────────────────────────────

    def _reduce_generic(self, html: str, strategy_name: str = "generic") -> tuple[str, dict]:  # noqa: C901
        """14-step progressive reduction — the original algorithm."""
        original_size = len(html)
        soup = BeautifulSoup(html, "lxml")
        steps_applied: list[dict] = []

        def step(name: str, fn) -> int:
            before = _text_len(soup)
            fn(soup)
            after = _text_len(soup)
            steps_applied.append({"step": name, "before": before, "after": after, "removed": before - after})
            return after

        # Step 1: Remove styles and stylesheets
        size = step("remove_styles", lambda s: [_remove_tags(s, tag) for tag in ["style", "link[rel=stylesheet]"]])
        if size <= self.target_size:
            return self._finalize(soup, original_size, steps_applied, strategy_name)

        # Step 2: Smart script removal
        size = step("smart_remove_scripts", _smart_remove_scripts)
        if size <= self.target_size:
            return self._finalize(soup, original_size, steps_applied, strategy_name)

        # Step 3: Remove noscript
        size = step("remove_noscript", lambda s: _remove_tags(s, "noscript"))
        if size <= self.target_size:
            return self._finalize(soup, original_size, steps_applied, strategy_name)

        # Step 4: Remove comments (except DATA comments from step 2)
        def remove_non_data_comments(s: BeautifulSoup) -> None:
            for comment in s.find_all(string=lambda t: isinstance(t, Comment)):
                if not str(comment).strip().startswith("DATA:"):
                    comment.extract()

        size = step("remove_comments", remove_non_data_comments)
        if size <= self.target_size:
            return self._finalize(soup, original_size, steps_applied, strategy_name)

        # Step 5: Remove navigation, headers, footers
        size = step(
            "remove_nav_chrome",
            lambda s: [
                _remove_tags(s, sel)
                for sel in ["nav", "header", "footer", "[role=navigation]", "[role=banner]", "[role=contentinfo]"]
            ],
        )
        if size <= self.target_size:
            return self._finalize(soup, original_size, steps_applied, strategy_name)

        # Step 6: Remove social/sharing widgets, ads, modals
        def remove_widgets(s: BeautifulSoup) -> None:
            for sel in [".social-share", ".share-buttons", "iframe"]:
                _remove_tags(s, sel)
            for keyword in ["social", "cookie", "popup", "modal", "newsletter", "subscribe", "advertisement"]:
                _remove_by_class_word(s, keyword)

        size = step("remove_widgets", remove_widgets)
        if size <= self.target_size:
            return self._finalize(soup, original_size, steps_applied, strategy_name)

        # Step 7: Replace images with alt text markers
        def replace_images(s: BeautifulSoup) -> None:
            for img in s.find_all("img"):
                alt = img.get("alt", "")
                if alt:
                    img.replace_with(f"[image: {alt}]")
                else:
                    img.decompose()

        size = step("replace_images", replace_images)
        if size <= self.target_size:
            return self._finalize(soup, original_size, steps_applied, strategy_name)

        # Step 8: Remove SVGs
        size = step("remove_svgs", lambda s: _remove_tags(s, "svg"))
        if size <= self.target_size:
            return self._finalize(soup, original_size, steps_applied, strategy_name)

        # Step 9: Strip non-essential attributes
        size = step("strip_attrs", _strip_attrs)
        if size <= self.target_size:
            return self._finalize(soup, original_size, steps_applied, strategy_name)

        # Step 10: Remove sidebar / aside
        def remove_sidebars(s: BeautifulSoup) -> None:
            _remove_tags(s, "aside")
            for keyword in ["sidebar", "related", "recommend"]:
                _remove_by_class_word(s, keyword)

        size = step("remove_sidebars", remove_sidebars)
        if size <= self.target_size:
            return self._finalize(soup, original_size, steps_applied, strategy_name)

        # Step 11: Remove form elements
        size = step("remove_forms", lambda s: _remove_tags(s, "form"))
        if size <= self.target_size:
            return self._finalize(soup, original_size, steps_applied, strategy_name)

        # Step 12: Flatten empty containers
        def flatten_empty(s: BeautifulSoup) -> None:
            changed = True
            while changed:
                changed = False
                for tag in s.find_all(True):
                    if isinstance(tag, Tag) and not tag.get_text(strip=True) and tag.name not in ("br", "hr"):
                        tag.decompose()
                        changed = True

        size = step("flatten_empty", flatten_empty)
        if size <= self.target_size:
            return self._finalize(soup, original_size, steps_applied, strategy_name)

        # Step 13: Strip ALL remaining attributes (aggressive)
        size = step("strip_all_attrs", lambda s: _strip_attrs(s, keep=set()))
        if size <= self.target_size:
            return self._finalize(soup, original_size, steps_applied, strategy_name)

        # Step 14: Unwrap non-semantic containers (div, span)
        def unwrap_containers(s: BeautifulSoup) -> None:
            for tag_name in ["div", "span"]:
                for tag in s.find_all(tag_name):
                    if isinstance(tag, Tag):
                        tag.unwrap()

        step("unwrap_containers", unwrap_containers)

        return self._finalize(soup, original_size, steps_applied, strategy_name)

    # ── Strategy: main_content ───────────────────────────────────────────────

    def _reduce_main_content(self, html: str, domain: str) -> tuple[str, dict]:
        """Extract content container + JSON-LD, then run generic reduction on the subset."""
        original_size = len(html)
        soup = BeautifulSoup(html, "lxml")

        # Find content container
        selector = DOMAIN_CONTENT_SELECTORS.get(domain, "main")
        container = soup.select_one(selector)

        if not container:
            logger.warning("main_content: selector %r not found for %s — falling back to generic", selector, domain)
            return self._reduce_generic(html, strategy_name="main_content_fallback")

        # Extract JSON-LD from the full page (may be outside <main>)
        jsonld_comments = _extract_jsonld_comments(soup)

        # Build reduced HTML from container content + JSON-LD
        container_html = str(container)
        jsonld_block = "\n".join(jsonld_comments)
        assembled = f"<html><body>\n{jsonld_block}\n{container_html}\n</body></html>"

        # Check we haven't over-stripped
        if len(assembled) < self.min_size:
            logger.warning(
                "main_content: extracted content too small (%d chars) for %s — falling back to generic",
                len(assembled),
                domain,
            )
            return self._reduce_generic(html, strategy_name="main_content_fallback")

        # Run generic reduction on the smaller document
        return self._reduce_generic(assembled, strategy_name="main_content")

    # ── Strategy: jsonld_only ────────────────────────────────────────────────

    def _reduce_jsonld_only(self, html: str) -> tuple[str, dict]:
        """Extract JSON-LD + meta tags for SPA pages where the HTML body is useless."""
        original_size = len(html)
        soup = BeautifulSoup(html, "lxml")

        # Extract title
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""

        # Extract meta description and og: tags
        meta_parts = []
        for meta in soup.find_all("meta"):
            name = meta.get("name", "").lower()
            prop = meta.get("property", "").lower()
            content = meta.get("content", "")
            if content and (name == "description" or prop.startswith("og:")):
                label = name or prop
                meta_parts.append(f"<p>{label}: {content}</p>")

        # Extract JSON-LD
        jsonld_comments = _extract_jsonld_comments(soup)

        if not jsonld_comments:
            logger.warning("jsonld_only: no JSON-LD found — falling back to generic")
            return self._reduce_generic(html, strategy_name="jsonld_only_fallback")

        # Assemble clean document
        meta_block = "\n".join(meta_parts)
        jsonld_block = "\n".join(jsonld_comments)
        assembled = f"<html><head><title>{title}</title></head>\n<body>\n{meta_block}\n{jsonld_block}\n</body></html>"

        # This is already minimal — just finalize
        reduced = _collapse_whitespace(assembled)
        metadata = {
            "original_size": original_size,
            "reduced_size": len(reduced),
            "reduction_ratio": round(len(reduced) / original_size, 3) if original_size > 0 else 0,
            "steps_applied": 0,
            "steps": [],
            "under_target": len(reduced) <= self.target_size,
            "strategy_used": "jsonld_only",
        }
        return reduced, metadata

    # ── Finalization ─────────────────────────────────────────────────────────

    def _finalize(self, soup: BeautifulSoup, original_size: int, steps: list[dict], strategy: str) -> tuple[str, dict]:
        html = _collapse_whitespace(str(soup))
        reduced_size = len(html)
        metadata = {
            "original_size": original_size,
            "reduced_size": reduced_size,
            "reduction_ratio": round(reduced_size / original_size, 3) if original_size > 0 else 0,
            "steps_applied": len(steps),
            "steps": steps,
            "under_target": reduced_size <= self.target_size,
            "strategy_used": strategy,
        }
        return html, metadata
