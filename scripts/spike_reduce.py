# flake8: noqa: E501 B950
"""Spike: reduce raw HTML to a compact form suitable for LLM extraction.

Reads raw.html (output of spike_fetch.py), applies progressive stripping
to get the HTML under ~30KB while preserving product data (specs, BCs, weights).

Key design principle: remove CSS aggressively, scripts selectively.
Many manufacturer sites embed structured product data inside inline <script>
tags (JSON-LD, Angular bootstraps, __NEXT_DATA__, etc.). Blindly removing
all scripts destroys the richest extraction signal.

Usage:
    python scripts/spike_reduce.py
    python scripts/spike_reduce.py -i data/pipeline/spike/raw.html -o data/pipeline/spike/reduced.html
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup, Comment, Tag

_ROOT = Path(__file__).resolve().parent.parent
SPIKE_DIR = _ROOT / "data" / "pipeline" / "spike"

TARGET_SIZE = 30_000  # chars — fits comfortably in LLM context
MIN_SIZE = 6_000  # below this we've over-stripped

# Patterns that identify tracking / analytics inline scripts (case-insensitive).
# If an inline script's text matches any of these, it's safe to remove.
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

# Minimum number of key-like patterns to consider an inline script "data-bearing"
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

    The rule: keyword must appear as a standalone hyphen-delimited segment
    in at least one of the tag's CSS classes.
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
    # Collect first, then decompose — avoids mutating during iteration
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
        # Never decompose <body> or <html> — over-broad selectors can match these
        if el.name in ("body", "html"):
            continue
        el.decompose()


def _remove_comments(soup: BeautifulSoup) -> None:
    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()


def _is_data_bearing_script(tag: Tag) -> bool:
    """Return True if an inline script likely contains structured product data."""
    text = tag.get_text()

    # JSON-LD is always data
    if tag.get("type", "").lower() == "application/ld+json":
        return True

    # Try to detect inline JSON blobs — look for multiple quoted keys
    if len(_JSON_KEY_RE.findall(text[:2000])) >= _MIN_JSON_KEYS:
        return True

    # __NEXT_DATA__, Nuxt, Gatsby, etc.
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

        # External scripts (src=...) — always remove the tag, data is elsewhere
        if script.get("src"):
            script.decompose()
            continue

        # Check inline scripts
        if _is_data_bearing_script(script):
            # Strip the <script> wrapper but keep the JSON text as a raw node.
            # This makes it visible to the LLM without the tag overhead.
            text = script.get_text(strip=True)
            # If it's JSON-LD, try to compact it
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
            # Unknown inline script — remove if small, keep if large (likely data)
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


def reduce_html(html: str) -> tuple[str, dict]:  # noqa: C901
    """Progressively reduce HTML, returning (reduced_html, metadata)."""
    original_size = len(html)
    soup = BeautifulSoup(html, "lxml")
    steps_applied = []

    def step(name: str, fn):
        before = _text_len(soup)
        fn(soup)
        after = _text_len(soup)
        steps_applied.append({"step": name, "before": before, "after": after, "removed": before - after})
        return after

    # Step 1: Remove styles and stylesheets (always safe — zero extraction value)
    size = step(
        "remove_styles",
        lambda s: [_remove_tags(s, tag) for tag in ["style", "link[rel=stylesheet]"]],
    )
    if size <= TARGET_SIZE:
        return _finalize(soup, original_size, steps_applied)

    # Step 2: Smart script removal — keep data-bearing, remove tracking/external
    size = step("smart_remove_scripts", _smart_remove_scripts)
    if size <= TARGET_SIZE:
        return _finalize(soup, original_size, steps_applied)

    # Step 3: Remove noscript (tracking pixels, fallback content)
    size = step("remove_noscript", lambda s: _remove_tags(s, "noscript"))
    if size <= TARGET_SIZE:
        return _finalize(soup, original_size, steps_applied)

    # Step 4: Remove comments (except our DATA comments from step 2)
    def remove_non_data_comments(s):
        for comment in s.find_all(string=lambda t: isinstance(t, Comment)):
            if not str(comment).strip().startswith("DATA:"):
                comment.extract()

    size = step("remove_comments", remove_non_data_comments)
    if size <= TARGET_SIZE:
        return _finalize(soup, original_size, steps_applied)

    # Step 5: Remove navigation, headers, footers
    size = step(
        "remove_nav_chrome",
        lambda s: [
            _remove_tags(s, sel)
            for sel in ["nav", "header", "footer", "[role=navigation]", "[role=banner]", "[role=contentinfo]"]
        ],
    )
    if size <= TARGET_SIZE:
        return _finalize(soup, original_size, steps_applied)

    # Step 6: Remove social/sharing widgets, ads, modals
    # NOTE: avoid [class*=X] — it matches substrings and can nuke the <body>
    # (e.g. Berger's body class has "avada-has-boxed-modal-shadow-none").
    # Instead use _remove_by_class_word() for word-boundary matching.
    def remove_widgets(s):
        # Safe exact selectors
        for sel in [".social-share", ".share-buttons", "iframe"]:
            _remove_tags(s, sel)
        # Word-boundary class matching (won't match "avada-has-boxed-modal-shadow-none" for "modal")
        for keyword in ["social", "cookie", "popup", "modal", "newsletter", "subscribe", "advertisement"]:
            _remove_by_class_word(s, keyword)

    size = step("remove_widgets", remove_widgets)
    if size <= TARGET_SIZE:
        return _finalize(soup, original_size, steps_applied)

    # Step 7: Replace images with alt text markers
    def replace_images(s):
        for img in s.find_all("img"):
            alt = img.get("alt", "")
            if alt:
                img.replace_with(f"[image: {alt}]")
            else:
                img.decompose()

    size = step("replace_images", replace_images)
    if size <= TARGET_SIZE:
        return _finalize(soup, original_size, steps_applied)

    # Step 8: Remove SVGs (icons, decorative)
    size = step("remove_svgs", lambda s: _remove_tags(s, "svg"))
    if size <= TARGET_SIZE:
        return _finalize(soup, original_size, steps_applied)

    # Step 9: Strip non-essential attributes
    size = step("strip_attrs", _strip_attrs)
    if size <= TARGET_SIZE:
        return _finalize(soup, original_size, steps_applied)

    # Step 10: Remove sidebar / aside
    def remove_sidebars(s):
        _remove_tags(s, "aside")
        for keyword in ["sidebar", "related", "recommend"]:
            _remove_by_class_word(s, keyword)

    size = step("remove_sidebars", remove_sidebars)
    if size <= TARGET_SIZE:
        return _finalize(soup, original_size, steps_applied)

    # Step 11: Remove form elements
    size = step("remove_forms", lambda s: _remove_tags(s, "form"))
    if size <= TARGET_SIZE:
        return _finalize(soup, original_size, steps_applied)

    # Step 12: Flatten empty containers
    def flatten_empty(s):
        changed = True
        while changed:
            changed = False
            for tag in s.find_all(True):
                if isinstance(tag, Tag) and not tag.get_text(strip=True) and tag.name not in ("br", "hr"):
                    tag.decompose()
                    changed = True

    size = step("flatten_empty", flatten_empty)
    if size <= TARGET_SIZE:
        return _finalize(soup, original_size, steps_applied)

    # Step 13: Strip ALL remaining attributes (aggressive)
    size = step("strip_all_attrs", lambda s: _strip_attrs(s, keep=set()))
    if size <= TARGET_SIZE:
        return _finalize(soup, original_size, steps_applied)

    # Step 14: Unwrap non-semantic containers (div, span)
    def unwrap_containers(s):
        for tag_name in ["div", "span"]:
            for tag in s.find_all(tag_name):
                if isinstance(tag, Tag):
                    tag.unwrap()

    size = step("unwrap_containers", unwrap_containers)

    return _finalize(soup, original_size, steps_applied)


def _finalize(soup: BeautifulSoup, original_size: int, steps: list[dict]) -> tuple[str, dict]:
    html = _collapse_whitespace(str(soup))
    reduced_size = len(html)
    metadata = {
        "original_size": original_size,
        "reduced_size": reduced_size,
        "reduction_ratio": round(reduced_size / original_size, 3) if original_size > 0 else 0,
        "steps_applied": len(steps),
        "steps": steps,
        "under_target": reduced_size <= TARGET_SIZE,
    }
    return html, metadata


def main() -> None:
    parser = argparse.ArgumentParser(description="Spike: reduce HTML for LLM extraction")
    parser.add_argument("-i", "--input", type=Path, default=SPIKE_DIR / "raw.html", help="Input HTML path")
    parser.add_argument("-o", "--output", type=Path, default=SPIKE_DIR / "reduced.html", help="Output HTML path")
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"Input not found: {args.input}\nRun spike_fetch.py first.")

    raw_html = args.input.read_text(encoding="utf-8")
    print(f"Input: {args.input} ({len(raw_html):,} chars)")

    reduced_html, meta = reduce_html(raw_html)

    print(f"\nOriginal:  {meta['original_size']:>10,} chars")
    print(f"Reduced:   {meta['reduced_size']:>10,} chars")
    print(f"Ratio:     {meta['reduction_ratio']:.1%}")
    print(f"Under target ({TARGET_SIZE:,}): {'yes' if meta['under_target'] else 'NO — may need manual trimming'}")
    print(f"\nSteps applied ({meta['steps_applied']}):")
    for s in meta["steps"]:
        removed = s["removed"]
        if removed > 0:
            print(f"  {s['step']:<25s} -{removed:>8,} chars  ({s['after']:>8,} remaining)")
        else:
            print(f"  {s['step']:<25s}  (no change)")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(reduced_html, encoding="utf-8")
    print(f"\nSaved reduced HTML to {args.output}")


if __name__ == "__main__":
    main()
