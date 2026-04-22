"""Deterministic parser for www.nosler.com bullet + cartridge pages.

Nosler runs on Magento — no JSON-LD Product block, no BigCommerce attribute
array. Spec data lives in an HTML table of ``<tr><th>KEY</th><td>VALUE</td></tr>``
rows; muzzle velocity on cartridge pages is in a separate VELOCITY (FPS)
table whose first data row's leading cell is the muzzle value.

Stable bullet spec keys (99%+ coverage): ``Diameter``, ``Bullet Weight``,
``BC G1``, ``Bullet Type``, ``Bullet Base``, ``Manufacturer SKU``. Partial:
``BC G7`` (22/209 — most Nosler bullets only publish G1), ``Overall Length
(OAL) (in.)`` (92%), ``Sectional Density (SD.)`` (94%).

Stable cartridge keys: ``Cartridge`` (caliber), ``Bullet Type`` (bullet_name
linkage — "AccuBond", "Ballistic Tip", "Partition"), ``Bullet Weight``,
``Test Barrel Length``, ``Box Qty`` (round_count), ``Manufacturer SKU``.
BC fields are absent on cartridge pages (Nosler publishes BCs on separate
load-data pages) so cartridges always ship with null BCs — matches current
LLM behavior, no regression.

Third parser after Hornady (inline JSON) and Sierra (BigCommerce attribute
array). This one stresses table-row scraping, the BaseParser ABC didn't
need widening, and the cartridge resolver path runs without BC-boost signal.

Confidence tiers:
  1.0 — spec-table scalars (Diameter, Bullet Weight, BC G1, SKU, name).
  0.9 — values derived from a controlled vocab row (base_type from
        Bullet Base, tip_type inferred from Bullet Profile + Bullet Type).
  0.8 — muzzle velocity from the VELOCITY table's first data cell —
        one structural assumption away from the spec rows, so slightly
        lower confidence.
"""

from __future__ import annotations

import html as _html
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

MANUFACTURER = "Nosler"

# Spec table row — Nosler's product-specs table pattern.
_SPEC_ROW_RE = re.compile(
    r"<tr>\s*<th[^>]*>([^<]+)</th>\s*<td[^>]*>([^<]+)</td>",
    re.IGNORECASE,
)

# SKU via schema.org microdata — present on every product page.
_SKU_ITEMPROP_RE = re.compile(
    r'itemprop="sku"[^>]*>\s*([^<\s]+)',
    re.IGNORECASE,
)

# VELOCITY (FPS) region: everything between the header and the next ballistics
# section header (ENERGY, TRAJECTORY, </tbody>, </table>). Two common shapes:
#   Format A: <th>VELOCITY (FPS)</th>
#             <tr><td>Muzzle</td><td>100</td>...</tr>         ← header row
#             <tr><td>3950</td><td>3420</td>...</tr>          ← data row
#   Format B: <th>VELOCITY (FPS)</th>
#             <tr><td>2700</td><td>2490</td>...</tr>          ← no header row
# Both end before the ENERGY section. We scope the search to the VELOCITY
# region so we don't accidentally pull Muzzle Energy as MV (seen on the
# 35 Whelen 225gr AccuBond cartridge page).
_VELOCITY_REGION_RE = re.compile(
    r"VELOCITY\s*\(FPS\)(.*?)(?=ENERGY|TRAJECTORY|</table>|$)",
    re.IGNORECASE | re.DOTALL,
)
_VELOCITY_CELL_RE = re.compile(r"<tr[^>]*>\s*<td[^>]*>\s*([\d,]+)\s*</td>", re.IGNORECASE)

# "150gr" → 150.0. Nosler always uses "gr" suffix, no spaces guaranteed.
_WEIGHT_RE = re.compile(r"([\d.]+)\s*gr", re.IGNORECASE)

# "24\"" or "24 inches" — test barrel length.
_BARREL_RE = re.compile(r"([\d.]+)\s*(?:\"|in|inches)", re.IGNORECASE)

# Controlled-vocab mappings.
_BASE_TYPE_MAP = {
    "boat tail": "boat_tail",
    "flat base": "flat_base",
    "rebated boat tail": "rebated_boat_tail",
    "hybrid": "hybrid",
}

# Nosler bullet-type heuristics. Lower confidence than JSON-derived fields.
_TIP_TYPE_FROM_BULLET_TYPE = [
    (re.compile(r"ballistic\s*tip", re.I), "polymer_tip"),
    (re.compile(r"accubond", re.I), "polymer_tip"),
    (re.compile(r"e[- ]?tip", re.I), "polymer_tip"),
    (re.compile(r"expansion\s*tip", re.I), "polymer_tip"),
    (re.compile(r"varmageddon", re.I), "polymer_tip"),
    (re.compile(r"\bhpbt\b|hollow\s*point\s*boat\s*tail", re.I), "hollow_point"),
    (re.compile(r"custom\s*competition|match", re.I), "open_tip_match"),
    (re.compile(r"jhp|jacketed\s*hollow\s*point|hollow\s*point", re.I), "hollow_point"),
    (re.compile(r"\bfmj\b|full\s*metal\s*jacket", re.I), "fmj"),
    (re.compile(r"partition|protected\s*point|trophy\s*bonded", re.I), "soft_point"),
    (re.compile(r"round\s*ball|solid", re.I), "fmj"),
]


def _unescape(text: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(text)).strip()


def _find_spec_rows(html: str) -> dict[str, str]:
    """Collect the Nosler spec table into a {key: value} dict.

    Keys and values are HTML-unescaped and whitespace-collapsed. Duplicate
    keys take the last value (Nosler's layout rarely duplicates).
    """
    rows: dict[str, str] = {}
    for key_raw, val_raw in _SPEC_ROW_RE.findall(html):
        key = _unescape(key_raw)
        val = _unescape(val_raw)
        if not key or not val:
            continue
        rows[key] = val
    return rows


def _find_sku(html: str, spec: dict[str, str]) -> str | None:
    """Prefer the schema.org ``itemprop="sku"`` value over the spec row.

    Both carry the Nosler catalog number on pages where both exist; the
    microdata form is a tighter anchor and doesn't require the spec row to
    be present.
    """
    m = _SKU_ITEMPROP_RE.search(html)
    if m:
        sku = m.group(1).strip()
        if sku:
            return sku
    return (spec.get("Manufacturer SKU") or "").strip() or None


def _find_muzzle_velocity(html: str) -> int | None:
    """Pull muzzle velocity from the VELOCITY (FPS) table.

    Scoped to the VELOCITY region so we don't pick up Muzzle Energy values
    from the adjacent ENERGY table. Handles both Nosler table formats (with
    and without a Muzzle/100/200 header row). Returns None when the table
    is absent (≈16% of cached cartridge pages — mostly NoslerCustom
    specialty loads that don't publish ballistics).
    """
    region_match = _VELOCITY_REGION_RE.search(html)
    if not region_match:
        return None
    region = region_match.group(1)
    # First numeric cell in the region is the muzzle velocity — whether or
    # not the page has a header row, the first number is what we want.
    for val_match in _VELOCITY_CELL_RE.finditer(region):
        raw = val_match.group(1).replace(",", "")
        try:
            return int(raw)
        except ValueError:
            continue
    return None


def _parse_weight_grains(raw: str) -> float | None:
    """``"150gr"`` or ``"150"`` → 150.0."""
    if raw is None:
        return None
    m = _WEIGHT_RE.search(raw)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    # Fallback: raw numeric.
    try:
        return float(raw.strip())
    except (TypeError, ValueError):
        return None


def _parse_float(raw: str | None) -> float | None:
    if raw is None:
        return None
    try:
        return float(str(raw).strip())
    except (TypeError, ValueError):
        return None


def _parse_barrel_inches(raw: str | None) -> float | None:
    """``'24"'`` → 24.0."""
    if raw is None:
        return None
    m = _BARREL_RE.search(raw)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return _parse_float(raw)


def _base_type_from_row(raw: str | None) -> str | None:
    if not raw:
        return None
    return _BASE_TYPE_MAP.get(raw.strip().lower())


def _tip_type_from_bullet_type(bullet_type: str | None) -> str | None:
    if not bullet_type:
        return None
    for rx, tip in _TIP_TYPE_FROM_BULLET_TYPE:
        if rx.search(bullet_type):
            return tip
    return None


def _value(val: Any, source_text: str, confidence: float) -> ExtractedValue:
    if len(source_text) > 80:
        source_text = source_text[:77] + "..."
    return ExtractedValue(value=val, source_text=source_text, confidence=confidence)


def _null() -> ExtractedValue:
    return ExtractedValue(value=None, source_text="", confidence=0.0)


def _empty_list() -> ExtractedValue:
    return ExtractedValue(value=[], source_text="", confidence=0.0)


class NoslerParser(BaseParser):
    """Parse www.nosler.com bullet and cartridge pages from spec-table rows."""

    name = "nosler"
    supported_entity_types = frozenset({"bullet", "cartridge"})

    def parse(self, raw_html: str, url: str, entity_type: str) -> ParserResult | None:
        spec = _find_spec_rows(raw_html)
        if not spec:
            logger.debug("nosler: no spec table on %s", url)
            return None

        # Every Nosler product page has Product Name + Manufacturer SKU;
        # if neither is present this isn't a product page.
        name_raw = spec.get("Product Name")
        sku = _find_sku(raw_html, spec)
        if not name_raw or not sku:
            logger.debug("nosler: no Product Name or SKU on %s", url)
            return None
        name = _unescape(name_raw)

        if entity_type == "bullet":
            return self._parse_bullet(spec, sku, name, name_raw, url)
        if entity_type == "cartridge":
            return self._parse_cartridge(spec, sku, name, name_raw, raw_html, url)
        return None

    def _parse_bullet(
        self,
        spec: dict[str, str],
        sku: str,
        name: str,
        name_raw: str,
        url: str,
    ) -> ParserResult | None:
        diameter = _parse_float(spec.get("Diameter"))
        weight = _parse_weight_grains(spec.get("Bullet Weight", ""))
        if diameter is None or weight is None:
            logger.debug("nosler: missing diameter or weight on bullet %s", url)
            return None

        bc_g1 = _parse_float(spec.get("BC G1"))
        bc_g7 = _parse_float(spec.get("BC G7"))
        sd = _parse_float(spec.get("Sectional Density (SD.)"))
        oal = _parse_float(spec.get("Overall Length (OAL) (in.)"))

        bullet_type_row = (spec.get("Bullet Type") or "").strip() or None
        bullet_base_row = (spec.get("Bullet Base") or "").strip() or None

        base_type = _base_type_from_row(bullet_base_row)
        tip_type = _tip_type_from_bullet_type(bullet_type_row)

        try:
            bullet = ExtractedBullet(
                name=_value(name, name_raw[:80], 1.0),
                manufacturer=_value(MANUFACTURER, "nosler.com", 1.0),
                bullet_diameter_inches=_value(diameter, f"Diameter={spec.get('Diameter')}", 1.0),
                weight_grains=_value(weight, f"Bullet Weight={spec.get('Bullet Weight')}", 1.0),
                bc_g1=(_value(bc_g1, f"BC G1={spec.get('BC G1')}", 1.0) if bc_g1 is not None else _null()),
                bc_g7=(_value(bc_g7, f"BC G7={spec.get('BC G7')}", 1.0) if bc_g7 is not None else _null()),
                length_inches=(
                    _value(oal, f"OAL={spec.get('Overall Length (OAL) (in.)')}", 1.0) if oal is not None else _null()
                ),
                sectional_density=(
                    _value(sd, f"SD={spec.get('Sectional Density (SD.)')}", 1.0) if sd is not None else _null()
                ),
                base_type=(_value(base_type, f"Bullet Base={bullet_base_row}", 0.9) if base_type else _null()),
                tip_type=(_value(tip_type, f"Bullet Type={bullet_type_row}", 0.7) if tip_type else _null()),
                type_tags=_empty_list(),
                used_for=_empty_list(),
                product_line=(
                    _value(bullet_type_row, f"Bullet Type={bullet_type_row}", 1.0) if bullet_type_row else _null()
                ),
                sku=_value(sku, f"sku={sku}", 1.0),
            )
        except Exception as e:
            raise ParserError(f"failed to build ExtractedBullet for {url}: {e}") from e

        bc_sources: list[ExtractedBCSource] = []
        if bc_g1 is not None:
            bc_sources.append(ExtractedBCSource(bullet_name=name, bc_type="g1", bc_value=bc_g1, source="manufacturer"))
        if bc_g7 is not None:
            bc_sources.append(ExtractedBCSource(bullet_name=name, bc_type="g7", bc_value=bc_g7, source="manufacturer"))

        return ParserResult(entities=[bullet], bc_sources=bc_sources)

    def _parse_cartridge(
        self,
        spec: dict[str, str],
        sku: str,
        name: str,
        name_raw: str,
        raw_html: str,
        url: str,
    ) -> ParserResult | None:
        caliber = (spec.get("Cartridge") or "").strip() or None
        if not caliber:
            logger.debug("nosler: missing Cartridge row on %s", url)
            return None

        weight = _parse_weight_grains(spec.get("Bullet Weight", ""))
        if weight is None:
            logger.debug("nosler: missing Bullet Weight on cartridge %s", url)
            return None

        # Bullet Type is the projectile family — the resolver's bullet_name
        # linkage hook. Nosler's values are canonical ("AccuBond",
        # "Ballistic Tip", "Partition"), not free-form prose.
        bullet_name = (spec.get("Bullet Type") or "").strip() or None

        muzzle_velocity = _find_muzzle_velocity(raw_html)
        barrel_raw = spec.get("Test Barrel Length")
        test_barrel = _parse_barrel_inches(barrel_raw)

        box_qty_raw = spec.get("Box Qty", "")
        try:
            round_count = int(box_qty_raw.strip()) if box_qty_raw and box_qty_raw.strip().isdigit() else None
        except ValueError:
            round_count = None

        try:
            cartridge = ExtractedCartridge(
                name=_value(name, name_raw[:80], 1.0),
                manufacturer=_value(MANUFACTURER, "nosler.com", 1.0),
                caliber=_value(caliber, f"Cartridge={caliber}", 1.0),
                bullet_name=(_value(bullet_name, f"Bullet Type={bullet_name}", 1.0) if bullet_name else _null()),
                bullet_weight_grains=_value(weight, f"Bullet Weight={spec.get('Bullet Weight')}", 1.0),
                # BC fields are never on Nosler cartridge pages (BCs live on
                # separate load-data pages). Matches current LLM behavior.
                bc_g1=_null(),
                bc_g7=_null(),
                bullet_length_inches=_null(),
                muzzle_velocity_fps=(
                    _value(muzzle_velocity, f"VELOCITY Muzzle={muzzle_velocity}", 0.8)
                    if muzzle_velocity is not None
                    else _null()
                ),
                test_barrel_length_inches=(
                    _value(test_barrel, f"Test Barrel={barrel_raw}", 1.0) if test_barrel is not None else _null()
                ),
                round_count=(
                    _value(round_count, f"Box Qty={box_qty_raw}", 1.0) if round_count is not None else _null()
                ),
                # Nosler's cartridge product_line (Trophy Grade, NoslerCustom,
                # Varmageddon, etc.) is embedded in the Product Name prose
                # rather than a dedicated spec row. Leave null — matches LLM.
                product_line=_null(),
                sku=_value(sku, f"sku={sku}", 1.0),
            )
        except Exception as e:
            raise ParserError(f"failed to build ExtractedCartridge for {url}: {e}") from e

        # Cartridge pages have no BC — nothing to attribute to bullet_bc_source.
        return ParserResult(entities=[cartridge], bc_sources=[])
