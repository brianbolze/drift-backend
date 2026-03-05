# flake8: noqa: E501 B950
"""HTML reducer — progressive stripping to get product pages under ~30KB for LLM extraction.

Key design principle: remove CSS aggressively, scripts selectively.
Many manufacturer sites embed structured product data inside inline <script>
tags (JSON-LD, Angular bootstraps, __NEXT_DATA__, etc.). Blindly removing
all scripts destroys the richest extraction signal.

Promoted from scripts/spike_reduce.py after validation across 5 manufacturer sites.

Known limitation: Angular SPA pages (e.g., Hornady ammunition pages) can retain
~80%+ of their original size after reduction because the bulk of the content is
raw template text in the <body> rather than removable tag structures. These pages
still extract correctly (Haiku handles 95K+ input tokens fine) but cost more per
page. A future improvement could truncate non-product sections by detecting
Angular template boundaries or applying a secondary text-level reduction pass.
"""

from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup, Comment, Tag

from drift.pipeline.config import REDUCE_MIN_SIZE, REDUCE_TARGET_SIZE

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
    Does NOT match: "antisocial", "avada-has-boxed-modal-shadow-none" for "modal"

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


class HtmlReducer:
    """Progressive HTML reducer that preserves product data while stripping chrome."""

    def __init__(self, target_size: int = REDUCE_TARGET_SIZE, min_size: int = REDUCE_MIN_SIZE):
        self.target_size = target_size
        self.min_size = min_size

    def reduce(self, html: str) -> tuple[str, dict]:  # noqa: C901
        """Progressively reduce HTML, returning (reduced_html, metadata)."""
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
            return self._finalize(soup, original_size, steps_applied)

        # Step 2: Smart script removal
        size = step("smart_remove_scripts", _smart_remove_scripts)
        if size <= self.target_size:
            return self._finalize(soup, original_size, steps_applied)

        # Step 3: Remove noscript
        size = step("remove_noscript", lambda s: _remove_tags(s, "noscript"))
        if size <= self.target_size:
            return self._finalize(soup, original_size, steps_applied)

        # Step 4: Remove comments (except DATA comments from step 2)
        def remove_non_data_comments(s: BeautifulSoup) -> None:
            for comment in s.find_all(string=lambda t: isinstance(t, Comment)):
                if not str(comment).strip().startswith("DATA:"):
                    comment.extract()

        size = step("remove_comments", remove_non_data_comments)
        if size <= self.target_size:
            return self._finalize(soup, original_size, steps_applied)

        # Step 5: Remove navigation, headers, footers
        size = step(
            "remove_nav_chrome",
            lambda s: [
                _remove_tags(s, sel)
                for sel in ["nav", "header", "footer", "[role=navigation]", "[role=banner]", "[role=contentinfo]"]
            ],
        )
        if size <= self.target_size:
            return self._finalize(soup, original_size, steps_applied)

        # Step 6: Remove social/sharing widgets, ads, modals
        def remove_widgets(s: BeautifulSoup) -> None:
            for sel in [".social-share", ".share-buttons", "iframe"]:
                _remove_tags(s, sel)
            for keyword in ["social", "cookie", "popup", "modal", "newsletter", "subscribe", "advertisement"]:
                _remove_by_class_word(s, keyword)

        size = step("remove_widgets", remove_widgets)
        if size <= self.target_size:
            return self._finalize(soup, original_size, steps_applied)

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
            return self._finalize(soup, original_size, steps_applied)

        # Step 8: Remove SVGs
        size = step("remove_svgs", lambda s: _remove_tags(s, "svg"))
        if size <= self.target_size:
            return self._finalize(soup, original_size, steps_applied)

        # Step 9: Strip non-essential attributes
        size = step("strip_attrs", _strip_attrs)
        if size <= self.target_size:
            return self._finalize(soup, original_size, steps_applied)

        # Step 10: Remove sidebar / aside
        def remove_sidebars(s: BeautifulSoup) -> None:
            _remove_tags(s, "aside")
            for keyword in ["sidebar", "related", "recommend"]:
                _remove_by_class_word(s, keyword)

        size = step("remove_sidebars", remove_sidebars)
        if size <= self.target_size:
            return self._finalize(soup, original_size, steps_applied)

        # Step 11: Remove form elements
        size = step("remove_forms", lambda s: _remove_tags(s, "form"))
        if size <= self.target_size:
            return self._finalize(soup, original_size, steps_applied)

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
            return self._finalize(soup, original_size, steps_applied)

        # Step 13: Strip ALL remaining attributes (aggressive)
        size = step("strip_all_attrs", lambda s: _strip_attrs(s, keep=set()))
        if size <= self.target_size:
            return self._finalize(soup, original_size, steps_applied)

        # Step 14: Unwrap non-semantic containers (div, span)
        def unwrap_containers(s: BeautifulSoup) -> None:
            for tag_name in ["div", "span"]:
                for tag in s.find_all(tag_name):
                    if isinstance(tag, Tag):
                        tag.unwrap()

        step("unwrap_containers", unwrap_containers)

        return self._finalize(soup, original_size, steps_applied)

    def _finalize(self, soup: BeautifulSoup, original_size: int, steps: list[dict]) -> tuple[str, dict]:
        html = _collapse_whitespace(str(soup))
        reduced_size = len(html)
        metadata = {
            "original_size": original_size,
            "reduced_size": reduced_size,
            "reduction_ratio": round(reduced_size / original_size, 3) if original_size > 0 else 0,
            "steps_applied": len(steps),
            "steps": steps,
            "under_target": reduced_size <= self.target_size,
        }
        return html, metadata
