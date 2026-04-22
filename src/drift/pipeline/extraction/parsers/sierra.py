"""Deterministic parser for sierrabullets.com bullet pages.

Sierra (BigCommerce) serves two clean signals on every bullet page:

  1. A ``<script type="application/ld+json">`` block with ``@type: "Product"``
     carrying ``name`` and ``sku``.
  2. An embedded JSON array of BigCommerce custom-field objects of the form
     ``{"id":"<n>","name":"<key>","value":"<val>"}`` with stable keys:
     ``Bullet Diameter``, ``Bullet Weight``, ``G1 BC``, ``G7 BC``,
     ``Bullet Type``, ``Tipped/Non-Tipped``, ``Product Family``, ``Purpose``,
     ``Pursuit``, ``Item #``. Present on 247/248 cached pages; the one
     outlier is a catalog page with no specs.

Bullet-only (supported_entity_types = {"bullet"}); Sierra has no cartridge
pages in the manifest. Product family → ``product_line`` is a direct lift
from an explicit attribute — the LLM path was returning null for this field
across the board, so the parser is a net improvement there.

Confidence tiers (per docs/parser_first_extraction.md):
  1.0 — attribute-map scalars (diameter, weight, G1/G7, sku, product_line).
  0.8 — values derived via well-known vocab mapping (base_type/tip_type
        from the "Bullet Type" value).
  0.7 — heuristic inference from Purpose + Pursuit into used_for/type_tags.
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
    ExtractedValue,
)

logger = logging.getLogger(__name__)

MANUFACTURER = "Sierra Bullets"

# BigCommerce custom-field objects embedded in a JS string. The backslash-
# escaped variant appears when the JSON is itself inside another JSON string;
# the raw variant appears in the primary attribute array. One regex covers both.
_ATTR_RE = re.compile(
    r'\{\\?"id\\?":\\?"\d+\\?",' r'\\?"name\\?":\\?"([^"\\]+)\\?",' r'\\?"value\\?":\\?"([^"\\]+)\\?"\}'
)

# Product-type JSON-LD blocks. Sierra has several JSON-LD blocks per page
# (Organization, Store, BreadcrumbList, Product) — we only want Product.
_JSONLD_BLOCK_RE = re.compile(
    r"<script[^>]*application/ld\+json[^>]*>\s*(\{.*?\})\s*</script>",
    re.DOTALL,
)

# Deterministic field extraction — confidence 1.0 when the attribute is
# present, null otherwise.
_DIRECT_ATTRS = {
    "Bullet Diameter": "bullet_diameter_inches",
    "Bullet Weight": "weight_grains",
    "G1 BC": "bc_g1",
    "G7 BC": "bc_g7",
    "Item #": "sku",
    "Product Family": "product_line",
}


def _find_product_jsonld(html: str) -> dict[str, Any] | None:
    """Return the first JSON-LD block whose @type is Product, or None."""
    for match in _JSONLD_BLOCK_RE.finditer(html):
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "Product":
            return data
    return None


def _find_attributes(html: str) -> dict[str, str]:
    """Collect the BigCommerce attribute name→value map.

    The same attribute typically appears multiple times (desktop/mobile
    renders); last wins, but they carry identical values in practice.
    """
    attrs: dict[str, str] = {}
    for name, value in _ATTR_RE.findall(html):
        name = _html.unescape(name).strip()
        value = _html.unescape(value).strip()
        if not name or not value:
            continue
        # Guard against the "Product Family":"Product Family" defect seen on
        # one cached page — value equals its key, treat as missing.
        if value.lower() == name.lower():
            continue
        attrs[name] = value
    return attrs


def _value(val: Any, source_text: str, confidence: float) -> ExtractedValue:
    if len(source_text) > 80:
        source_text = source_text[:77] + "..."
    return ExtractedValue(value=val, source_text=source_text, confidence=confidence)


def _null() -> ExtractedValue:
    return ExtractedValue(value=None, source_text="", confidence=0.0)


def _empty_list() -> ExtractedValue:
    return ExtractedValue(value=[], source_text="", confidence=0.0)


def _parse_float(raw: str) -> float | None:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _parse_bullet_type(bullet_type: str) -> tuple[str | None, str | None]:
    """Map a Sierra ``Bullet Type`` value to (base_type, tip_type).

    Sierra's controlled vocabulary (see data survey) covers 20 distinct
    values; this function handles the big ones and returns (None, None)
    for anything it isn't sure about so confidence stays honest.
    """
    bt = bullet_type.lower()
    base: str | None = None
    tip: str | None = None

    if "boat tail" in bt or "hpbt" in bt or "sbt" in bt or "(bt)" in bt:
        base = "boat_tail"
    elif "flatnose" in bt or "flat nose" in bt or "roundnose" in bt or "round nose" in bt:
        base = "flat_base"
    elif "spitzer" in bt:
        # Plain Spitzer (SPT) is flat-base; Spitzer Boat Tail is caught above.
        base = "flat_base"

    if "tipped" in bt or "ballistic tip" in bt:
        tip = "polymer_tip"
    elif "hollow point" in bt or "(hp" in bt or "jhp" in bt or "jhc" in bt:
        tip = "hollow_point"
    elif "full metal jacket" in bt or "fmj" in bt:
        tip = "fmj"
    elif "soft point" in bt or "jsp" in bt or "spt" in bt:
        tip = "soft_point"
    elif "flatnose" in bt or "flat nose" in bt:
        tip = "meplat"

    return base, tip


def _map_purpose_pursuit(purpose: str, pursuit: str) -> tuple[list[str], list[str]]:
    """Map Sierra's Purpose + Pursuit into (type_tags, used_for).

    Heuristic — confidence 0.7. Sierra's controlled vocabulary (see survey)
    is small: Purpose ∈ {Match/Target, Hunting, Personal Defense}; Pursuit
    adds sub-categories like Big Game, Varmint, Target.
    """
    p = (purpose or "").lower()
    pu = (pursuit or "").lower()

    type_tags: list[str] = []
    used_for: list[str] = []

    if "match" in p or "target" in p:
        type_tags.extend(["match", "target"])
        used_for.extend(["competition", "precision"])
    if "hunt" in p:
        type_tags.append("hunting")
        if "big game" in pu:
            used_for.extend(["hunting_deer", "hunting_elk"])
        elif "varmint" in pu:
            type_tags.append("varmint")
            used_for.append("hunting_varmint")
        else:
            used_for.append("hunting_deer")
    if "personal defense" in p or "self defense" in p:
        type_tags.append("tactical")
        used_for.append("self_defense")

    # Dedupe while preserving order
    return list(dict.fromkeys(type_tags)), list(dict.fromkeys(used_for))


def _clean_name(raw: str) -> str:
    """Decode HTML entities and collapse whitespace in a product name."""
    return re.sub(r"\s+", " ", _html.unescape(raw)).strip()


class SierraParser(BaseParser):
    """Parse sierrabullets.com bullet pages from JSON-LD + BigCommerce attributes."""

    name = "sierra"
    supported_entity_types = frozenset({"bullet"})

    def parse(self, raw_html: str, url: str, entity_type: str) -> ParserResult | None:  # noqa: C901
        if entity_type != "bullet":
            return None

        product = _find_product_jsonld(raw_html)
        if product is None:
            logger.debug("sierra: no Product JSON-LD on %s", url)
            return None

        name_raw = product.get("name") or ""
        name = _clean_name(name_raw)
        if not name:
            logger.debug("sierra: empty product name on %s", url)
            return None

        attrs = _find_attributes(raw_html)
        if not attrs:
            logger.debug("sierra: no attribute map on %s", url)
            return None

        # ── Required numeric fields ──────────────────────────────────────
        diameter_raw = attrs.get("Bullet Diameter")
        weight_raw = attrs.get("Bullet Weight")
        diameter = _parse_float(diameter_raw) if diameter_raw else None
        weight = _parse_float(weight_raw) if weight_raw else None
        if diameter is None or weight is None:
            logger.debug("sierra: missing diameter or weight on %s", url)
            return None

        bc_g1_raw = attrs.get("G1 BC")
        bc_g1 = _parse_float(bc_g1_raw) if bc_g1_raw else None
        bc_g7_raw = attrs.get("G7 BC")
        bc_g7 = _parse_float(bc_g7_raw) if bc_g7_raw else None

        # ── Derived categorical fields ───────────────────────────────────
        bullet_type_raw = attrs.get("Bullet Type", "")
        base_type, tip_type = _parse_bullet_type(bullet_type_raw)
        tipped_flag = attrs.get("Tipped/Non-Tipped", "").lower()
        if "tipped" in tipped_flag and tip_type is None:
            # Tipped/Non-Tipped is a direct boolean for polymer tip presence.
            tip_type = "polymer_tip"

        type_tags, used_for = _map_purpose_pursuit(
            attrs.get("Purpose", ""),
            attrs.get("Pursuit", ""),
        )

        # ── Product line + SKU ──────────────────────────────────────────
        product_line = (attrs.get("Product Family") or "").strip() or None
        # Prefer the "Item #" attribute over JSON-LD sku: JSON-LD carries the
        # BigCommerce internal product_id (e.g. 505), while Item # is Sierra's
        # catalog number. Strip trailing BigCommerce variant suffixes (C, T,
        # K, etc.) because the DB's canonical form is the numeric part
        # (130 of 144 current Sierra rows have no suffix). A handful of true
        # catalog suffixes (11 ending "T", 1 "C", 2 "GT" in the DB today)
        # will drift by one char — those are a known minor mismatch the DB
        # would resolve via alias if we ever cared to match by SKU.
        sku_raw = str(attrs.get("Item #") or product.get("sku") or "").strip()
        sku_match = re.match(r"^(\d+)", sku_raw)
        sku = sku_match.group(1) if sku_match else (sku_raw or None)

        # ── Build the entity ────────────────────────────────────────────
        try:
            bullet = ExtractedBullet(
                name=_value(name, name_raw[:80], 1.0),
                manufacturer=_value(MANUFACTURER, "sierrabullets.com", 1.0),
                bullet_diameter_inches=_value(diameter, f"Bullet Diameter={diameter_raw}", 1.0),
                weight_grains=_value(weight, f"Bullet Weight={weight_raw}", 1.0),
                bc_g1=(_value(bc_g1, f"G1 BC={bc_g1_raw}", 1.0) if bc_g1 is not None else _null()),
                bc_g7=(_value(bc_g7, f"G7 BC={bc_g7_raw}", 1.0) if bc_g7 is not None else _null()),
                length_inches=_null(),
                sectional_density=_null(),
                base_type=(_value(base_type, f"Bullet Type={bullet_type_raw}"[:80], 0.8) if base_type else _null()),
                tip_type=(_value(tip_type, f"Bullet Type={bullet_type_raw}"[:80], 0.8) if tip_type else _null()),
                type_tags=(_value(type_tags, f"Purpose/Pursuit→{type_tags}"[:80], 0.7) if type_tags else _empty_list()),
                used_for=(_value(used_for, f"Purpose/Pursuit→{used_for}"[:80], 0.7) if used_for else _empty_list()),
                product_line=(_value(product_line, f"Product Family={product_line}", 1.0) if product_line else _null()),
                sku=_value(sku, f"sku={sku}", 1.0) if sku else _null(),
            )
        except Exception as e:
            raise ParserError(f"failed to build ExtractedBullet for {url}: {e}") from e

        bc_sources: list[ExtractedBCSource] = []
        if bc_g1 is not None:
            bc_sources.append(ExtractedBCSource(bullet_name=name, bc_type="g1", bc_value=bc_g1, source="manufacturer"))
        if bc_g7 is not None:
            bc_sources.append(ExtractedBCSource(bullet_name=name, bc_type="g7", bc_value=bc_g7, source="manufacturer"))

        return ParserResult(entities=[bullet], bc_sources=bc_sources)
