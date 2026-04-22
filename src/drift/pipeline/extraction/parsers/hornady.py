"""Deterministic parser for www.hornady.com product pages.

Hornady embeds the full product record as a single inline JSON object whose
first characters match ``{"id":<n>,``. The object has stable keys across every
bullet and cartridge page in the cache (775 of 775 sampled). We locate the
object, extract the fields we trust verbatim (weight, ball_coef, sku,
muzzlevelocity), and regex-parse a handful of fields out of rich-text
strings (diameter from ``title``, product family from anchor titles,
test barrel length from ``ballistics`` HTML).

Confidence tiers (per docs/parser_first_extraction.md):
  1.0 — verbatim JSON scalars (weight, ball_coef, sku, muzzlevelocity).
  0.8 — regex-extracted from prose fields (diameter from title).
  0.7 — heuristic (base_type / tip_type inferred from title tokens).

Any condition the parser doesn't explicitly handle returns ``None`` so the
engine falls back to the LLM path.
"""

from __future__ import annotations

import html as _html
import json
import logging
import re
from typing import Any

from drift.pipeline.extraction.parsers.base import BaseParser, ParserError, ParserResult
from drift.pipeline.extraction.schemas import (
    ExtractedBCSource,
    ExtractedBullet,
    ExtractedCartridge,
    ExtractedValue,
)

logger = logging.getLogger(__name__)

MANUFACTURER = "Hornady"

# First field after id in every Hornady product record (see data survey).
_PRODUCT_JSON_START = re.compile(r'\{"id":\d+(?=,)')

# Hornady International / Custom International lines publish ballistics in
# metric units (m/s, cm) inside the same JSON fields US loads use for fps/in.
# Detect by URL slug or title — both match all 21 International cached pages.
_INTERNATIONAL_URL_RE = re.compile(r"(?:hornady|custom)-international", re.IGNORECASE)

_MS_TO_FPS = 3.2808  # exact: 1 m/s = 3.28084 fps
_CM_TO_INCHES = 1.0 / 2.54

# ".XXX" diameter in a bullet title, e.g. "22 Cal .224 80 gr ELD-X".
_DIAMETER_RE = re.compile(r"\.(\d{3})(?:\D|$)")

# Test Barrel (<inches>") in the inline ballistics HTML.
_TEST_BARREL_RE = re.compile(r'Test Barrel\s*\(\s*(\d+(?:\.\d+)?)\s*"', re.IGNORECASE)

# Clean trademark glyphs + <sup> noise from titles. Replace with a space so
# adjacent words (e.g. "SST® Superformance®") don't collapse into "SSTSuperformance".
_TRADEMARK_RE = re.compile(r"(?:<sup>[^<]*</sup>|[\u00ae\u2122])")

# Extract anchor text / title attribute from an <a> tag in linktitle / bullettitle.
_ANCHOR_TITLE_RE = re.compile(r'<a[^>]*?title="([^"]+)"[^>]*>', re.IGNORECASE)
_ANCHOR_TEXT_RE = re.compile(r"<a\b[^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL)


def _strip_trademarks(text: str) -> str:
    return re.sub(r"\s+", " ", _TRADEMARK_RE.sub(" ", text)).strip()


def _strip_html(text: str) -> str:
    """Remove HTML tags, decode HTML entities, and normalize whitespace."""
    no_tags = re.sub(r"<[^>]+>", "", text)
    decoded = _html.unescape(no_tags)
    return re.sub(r"\s+", " ", decoded).strip()


def _find_product_json(html: str) -> dict[str, Any] | None:
    """Locate and return the product JSON object embedded in a Hornady page."""
    decoder = json.JSONDecoder()
    for match in _PRODUCT_JSON_START.finditer(html):
        start = match.start()
        try:
            obj, _ = decoder.raw_decode(html, start)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "ball_coef" in obj:
            return obj
    return None


def _value(val: Any, source_text: str, confidence: float) -> ExtractedValue:
    """Build an ExtractedValue with a short source_text (spec: under 80 chars)."""
    if len(source_text) > 80:
        source_text = source_text[:77] + "..."
    return ExtractedValue(value=val, source_text=source_text, confidence=confidence)


def _null(confidence: float = 0.0) -> ExtractedValue:
    return ExtractedValue(value=None, source_text="", confidence=confidence)


def _empty_list() -> ExtractedValue:
    return ExtractedValue(value=[], source_text="", confidence=0.0)


def _parse_diameter(title: str) -> tuple[float | None, str]:
    """Parse diameter in inches from a Hornady title like ``22 Cal .224 80 gr ELD-X``.

    Returns (diameter_inches, matched_text) or (None, '').
    """
    match = _DIAMETER_RE.search(title)
    if not match:
        return None, ""
    inches = float("0." + match.group(1))
    return inches, match.group(0).strip()


def _product_line_from_linktitle(linktitle: str) -> tuple[str | None, str]:
    """Extract product line from Hornady's ``linktitle`` anchor.

    Prefers anchor inner text (e.g. ``"ELD-X® "``) over the ``title`` attribute
    (e.g. ``"ELD‑X® (Extremely Low Drag ‑ eXpanding)"``) — the title carries
    the full marketing expansion which isn't what we want in a product_line.
    Always strips trailing ``(...)`` parenthetical descriptors as a safety net.
    """
    if not linktitle:
        return None, ""

    def _clean(raw: str) -> str:
        without_parens = re.sub(r"\s*\([^)]*\)\s*", " ", raw)
        return _strip_trademarks(without_parens)

    text_match = _ANCHOR_TEXT_RE.search(linktitle)
    if text_match:
        cleaned = _clean(_strip_html(text_match.group(1)))
        if cleaned:
            return cleaned, text_match.group(0)[:80]
    title_match = _ANCHOR_TITLE_RE.search(linktitle)
    if title_match:
        cleaned = _clean(title_match.group(1))
        if cleaned:
            return cleaned, title_match.group(0)[:80]
    return None, ""


def _bullet_name_from_bullettitle(bullettitle: str) -> tuple[str | None, str]:
    """Extract bullet family name from a cartridge's ``bullettitle`` field.

    Examples:
      ``<a ... title="SST® (Super Shock Tip)">150 gr SST®</a>`` → ``SST``
      ``<a ... title="Match™">125 gr HP Match™</a>`` → ``HP Match``
      ``124 gr FlexLock®`` (no anchor) → ``FlexLock``

    The anchor text (after stripping weight prefix + trademarks) is usually
    more descriptive than the anchor ``title`` attribute: Hornady points
    multiple bullet variants at a single family landing page, and the title
    attribute carries the landing-page name rather than the specific load's
    bullet. Fall back to the title attribute only if no anchor text is found.
    """
    if not bullettitle:
        return None, ""

    anchor_text_match = _ANCHOR_TEXT_RE.search(bullettitle)
    if anchor_text_match:
        inner = _strip_html(anchor_text_match.group(1))
        stripped = re.sub(r"^\s*\d+\s*gr\.?\s*", "", inner, flags=re.IGNORECASE)
        cleaned = _strip_trademarks(stripped)
        if cleaned:
            return cleaned, anchor_text_match.group(0)[:80]

    title_match = _ANCHOR_TITLE_RE.search(bullettitle)
    if title_match:
        # Titles like "SST® (Super Shock Tip)" — drop the parenthetical descriptor.
        primary = re.sub(r"\s*\([^)]*\)\s*", "", title_match.group(1))
        cleaned = _strip_trademarks(primary)
        if cleaned:
            return cleaned, title_match.group(0)[:80]

    plain = _strip_html(bullettitle)
    stripped = re.sub(r"^\s*\d+\s*gr\.?\s*", "", plain, flags=re.IGNORECASE)
    cleaned = _strip_trademarks(stripped)
    if cleaned:
        return cleaned, plain[:80]
    return None, ""


def _test_barrel_inches(ballistics_html: str) -> tuple[float | None, str]:
    if not ballistics_html:
        return None, ""
    m = _TEST_BARREL_RE.search(ballistics_html)
    if not m:
        return None, ""
    return float(m.group(1)), m.group(0)


def _bc_pair(obj: dict) -> tuple[
    tuple[float | None, str],
    tuple[float | None, str],
]:
    """Extract (g1, g7) BC values from the Hornady product JSON.

    Across 775 cached pages, ``ball_coef_type`` is always ``1`` (meaning G1) and
    ``ball_coef_type_2`` is always the literal string ``"(G7)"``. We still
    guard each branch so a surprise variation falls through to the LLM rather
    than mislabeling a BC type. Zero is treated as "unknown" — Hornady uses 0
    (not null) for unpublished BCs.
    """
    primary = obj.get("ball_coef") or None
    primary_type = obj.get("ball_coef_type")
    secondary = obj.get("ball_coef_2") or None
    secondary_type_raw = obj.get("ball_coef_type_2")

    g1: tuple[float | None, str] = (None, "")
    g7: tuple[float | None, str] = (None, "")

    if primary is not None and primary_type == 1:
        g1 = (float(primary), f'"ball_coef":{primary}')
    elif primary is not None and primary_type == 7:
        g7 = (float(primary), f'"ball_coef":{primary}')

    if secondary is not None and isinstance(secondary_type_raw, str):
        label = secondary_type_raw.strip().upper()
        if "G7" in label:
            g7 = (float(secondary), f'"ball_coef_2":{secondary}')
        elif "G1" in label:
            g1 = (float(secondary), f'"ball_coef_2":{secondary}')

    return g1, g7


def _build_bc_sources(
    bullet_name: str,
    g1: tuple[float | None, str],
    g7: tuple[float | None, str],
    *,
    source: str,
) -> list[ExtractedBCSource]:
    out: list[ExtractedBCSource] = []
    if g1[0] is not None:
        out.append(ExtractedBCSource(bullet_name=bullet_name, bc_type="g1", bc_value=g1[0], source=source))
    if g7[0] is not None:
        out.append(ExtractedBCSource(bullet_name=bullet_name, bc_type="g7", bc_value=g7[0], source=source))
    return out


class HornadyParser(BaseParser):
    """Parse www.hornady.com bullet + cartridge pages from their inline JSON."""

    name = "hornady"
    supported_entity_types = frozenset({"bullet", "cartridge"})

    def parse(self, raw_html: str, url: str, entity_type: str) -> ParserResult | None:
        obj = _find_product_json(raw_html)
        if obj is None:
            logger.debug("hornady: no product JSON found in %s", url)
            return None

        if entity_type == "bullet":
            return self._parse_bullet(obj, url)
        if entity_type == "cartridge":
            return self._parse_cartridge(obj, raw_html, url)
        return None

    def _parse_bullet(self, obj: dict, url: str) -> ParserResult | None:
        title_raw = obj.get("title") or ""
        title = _strip_trademarks(_strip_html(title_raw))
        if not title:
            logger.debug("hornady: empty title on %s", url)
            return None

        weight = obj.get("weight")
        if weight in (None, 0):
            logger.debug("hornady: missing weight on %s", url)
            return None

        diameter, diameter_src = _parse_diameter(title)
        if diameter is None:
            # Bullet pages without a ".XXX" diameter in the title are rare, but
            # we can't infer diameter safely from other fields — fall through.
            logger.debug("hornady: no diameter in title %r (%s)", title_raw, url)
            return None

        g1, g7 = _bc_pair(obj)
        product_line, pl_src = _product_line_from_linktitle(obj.get("linktitle") or "")
        sku = obj.get("sku") or None

        sectional_density_raw = obj.get("sectional_density")
        sd_value: float | None
        if sectional_density_raw in (None, 0, 0.0):
            sd_value = None
        else:
            try:
                sd_value = float(sectional_density_raw)
            except (TypeError, ValueError) as e:
                raise ParserError(f"unparseable sectional_density: {sectional_density_raw!r}") from e

        bullet = ExtractedBullet(
            name=_value(title, title_raw[:80], 1.0),
            manufacturer=_value(MANUFACTURER, "hornady.com", 1.0),
            bullet_diameter_inches=_value(diameter, diameter_src, 0.8),
            weight_grains=_value(float(weight), f'"weight":{weight}', 1.0),
            bc_g1=_value(g1[0], g1[1], 1.0 if g1[0] is not None else 0.0),
            bc_g7=_value(g7[0], g7[1], 1.0 if g7[0] is not None else 0.0),
            length_inches=_null(),
            sectional_density=(
                _value(sd_value, f'"sectional_density":{sectional_density_raw}', 1.0)
                if sd_value is not None
                else _null()
            ),
            base_type=_null(),
            tip_type=_null(),
            type_tags=_empty_list(),
            used_for=_empty_list(),
            product_line=(_value(product_line, pl_src, 1.0) if product_line else _null()),
            sku=_value(sku, f"sku={sku}", 1.0) if sku else _null(),
        )

        bc_sources = _build_bc_sources(title, g1, g7, source="manufacturer")
        return ParserResult(entities=[bullet], bc_sources=bc_sources)

    def _parse_cartridge(self, obj: dict, raw_html: str, url: str) -> ParserResult | None:
        title_raw = obj.get("title") or ""
        title = _strip_trademarks(_strip_html(title_raw))
        if not title:
            logger.debug("hornady: empty title on %s", url)
            return None

        is_international = bool(_INTERNATIONAL_URL_RE.search(url)) or "International" in title_raw

        weight = obj.get("weight")
        muzzle_velocity_raw = obj.get("muzzlevelocity")
        muzzle_velocity: int | None
        if isinstance(muzzle_velocity_raw, (int, float)) and muzzle_velocity_raw > 0:
            if is_international:
                # Hornady International JSON carries m/s; store in canonical fps.
                muzzle_velocity = int(round(muzzle_velocity_raw * _MS_TO_FPS))
            else:
                muzzle_velocity = int(muzzle_velocity_raw)
        else:
            muzzle_velocity = None

        # A cartridge without a muzzle velocity is still valid output, but the
        # downstream pipeline treats zero/null MV as a flag; preserve that.
        if weight in (None, 0):
            logger.debug("hornady: missing weight on cartridge %s", url)
            return None

        # Prefer the more specific `caliber` when present, otherwise cartridgename.
        caliber = (obj.get("caliber") or "").strip() or (obj.get("cartridgename") or "").strip()
        if not caliber:
            logger.debug("hornady: no caliber/cartridgename on %s", url)
            return None
        caliber_src_field = "caliber" if (obj.get("caliber") or "").strip() else "cartridgename"
        caliber_src = f"{caliber_src_field}={caliber}"

        bullet_name, bn_src = _bullet_name_from_bullettitle(obj.get("bullettitle") or "")
        if not bullet_name:
            # Some pages omit bullettitle — fall back to bullet_des if non-empty.
            bullet_des = (obj.get("bullet_des") or "").strip()
            if bullet_des:
                bullet_name = _strip_trademarks(bullet_des)
                bn_src = f"bullet_des={bullet_des}"

        g1, g7 = _bc_pair(obj)
        product_line, pl_src = _product_line_from_linktitle(obj.get("linktitle") or "")
        sku = obj.get("sku") or None

        # `ballistics` is HTML; extract the test barrel length from its title row.
        test_barrel, tb_src = _test_barrel_inches(obj.get("ballistics") or "")
        if test_barrel is not None and is_international:
            # International ballistics use cm; convert to the canonical inches unit.
            test_barrel = round(test_barrel * _CM_TO_INCHES, 2)

        box_count = obj.get("box_count")
        round_count_val = int(box_count) if isinstance(box_count, int) and box_count > 0 else None

        cartridge = ExtractedCartridge(
            name=_value(title, title_raw[:80], 1.0),
            manufacturer=_value(MANUFACTURER, "hornady.com", 1.0),
            caliber=_value(caliber, caliber_src, 1.0),
            bullet_name=(_value(bullet_name, bn_src, 0.9) if bullet_name else _null()),
            bullet_weight_grains=_value(float(weight), f'"weight":{weight}', 1.0),
            bc_g1=_value(g1[0], g1[1], 1.0 if g1[0] is not None else 0.0),
            bc_g7=_value(g7[0], g7[1], 1.0 if g7[0] is not None else 0.0),
            bullet_length_inches=_null(),
            muzzle_velocity_fps=(
                _value(
                    muzzle_velocity,
                    (
                        f'"muzzlevelocity":{muzzle_velocity_raw} (m/s→fps)'
                        if is_international
                        else f'"muzzlevelocity":{muzzle_velocity_raw}'
                    ),
                    1.0 if not is_international else 0.9,
                )
                if muzzle_velocity is not None
                else _null()
            ),
            test_barrel_length_inches=(_value(test_barrel, tb_src, 0.9) if test_barrel is not None else _null()),
            round_count=(
                _value(round_count_val, f'"box_count":{round_count_val}', 1.0)
                if round_count_val is not None
                else _null()
            ),
            product_line=(_value(product_line, pl_src, 1.0) if product_line else _null()),
            sku=_value(sku, f"sku={sku}", 1.0) if sku else _null(),
        )

        # Attribute BCs to the bullet family (consistent with LLM path).
        bc_attribution = bullet_name or title
        bc_sources = _build_bc_sources(bc_attribution, g1, g7, source="cartridge_page")
        return ParserResult(entities=[cartridge], bc_sources=bc_sources)
