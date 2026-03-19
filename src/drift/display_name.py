"""Compute display_name for bullets and cartridges.

Pure functions with no DB dependencies. Called during production export.
The display_name is the short, clean product identity shown in the iOS app,
stripped of weight, caliber, manufacturer, and other info shown elsewhere in the row.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Brand-word casing normalization (Sierra ALL-CAPS → proper casing)
# ---------------------------------------------------------------------------
_BRAND_CASING: dict[str, str] = {
    "matchking": "MatchKing",
    "gameking": "GameKing",
    "varmintking": "VarmintKing",
    "tippedmatchking": "Tipped MatchKing",
    "interlock": "InterLock",
    "superformance": "Superformance",
}

# Product line casing normalization (applied after trademark stripping)
_PRODUCT_LINE_CASING: dict[str, str] = {
    "v-match": "V-Match",
    "v-max": "V-MAX",
}

# Known bullet manufacturer names (for stripping from cartridge product lines)
_BULLET_MANUFACTURERS: set[str] = {
    "sierra",
    "berger",
    "barnes",
    "hornady",
    "nosler",
    "swift",
    "speer",
    "lapua",
    "norma",
}

# Suffixes to strip from cartridge product lines before combining
_CART_PL_STRIP_SUFFIXES = re.compile(r"\s+(?:Rifle|TIPPED|Rimfire)$", re.IGNORECASE)

# Abbreviations for generic bullet descriptions (Federal comma-delimited format)
_FEDERAL_BULLET_ABBREV: dict[str, str] = {
    "jacketed soft point": "JSP",
    "jacketed hollow point": "JHP",
    "full metal jacket boat-tail": "FMJ-BT",
    "full metal jacket": "FMJ",
    "open tip match": "OTM",
    "boat-tail hollow point": "BTHP",
    "bonded soft point": "BSP",
    "hollow point": "HP",
    "soft point": "SP",
    "copper hp": "Copper HP",
}

# ---------------------------------------------------------------------------
# Text normalization helpers
# ---------------------------------------------------------------------------


def _normalize_text(text: str) -> str:
    """Normalize unicode hyphens and strip trademark symbols."""
    # Non-breaking hyphen (U+2011), en-dash (U+2013), em-dash (U+2014) → regular hyphen
    text = text.replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")
    # Trademark symbols
    text = text.replace("\u00ae", "").replace("\u2122", "")  # ® ™
    return text


def _strip_caliber_prefix(text: str) -> str:
    """Remove caliber/diameter designations from bullet/cartridge names."""
    # Order matters: match combined patterns first, then individual ones

    # ".243/6mm", ".264/6.5mm", ".264/6.5"
    text = re.sub(r"\.\d{3}/\d+[,.]?\d*\s*(?:mm|MM)?\b\s*", " ", text)

    # '0.308"', '0.284"' (with quotes)
    text = re.sub(r"\d*\.\d{3}\"\s*", " ", text)

    # "(.308)", "(.366)", "(9.3mm)" — parenthetical diameter/caliber
    text = re.sub(r"\(\.\d{2,3}\)", " ", text)
    text = re.sub(r"\(\d+[,.]?\d*\s*(?:mm|MM)\)", " ", text)

    # ".308", ".264", ".30", ".375" (2-3 digit decimals, without quotes)
    text = re.sub(r"(?<!\d)\.\d{2,3}\b\s*,?\s*", " ", text)

    # "6.5mm", "6MM", "6.5 mm", "7mm", "9,3mm" (comma decimal — Norma format)
    text = re.sub(r"\d+[,.]?\d*\s*(?:mm|MM)\b\s*", " ", text)

    # "30 Cal 308" → strip "30 Cal" and bare 3-digit caliber number (NOT weight)
    # Negative lookahead: don't match if 3-digit number is followed by a weight unit
    text = re.sub(
        r"\d+\s+(?:Cal|CAL|cal|Caliber|CALIBER)\.?\s+\d{3}(?!\s*(?:gr|GR|g\b|grain|Grain))\b\s*",
        " ",
        text,
    )
    # "30 Cal", "338 CAL", "30 Caliber" (without trailing number)
    text = re.sub(r"\d+\s+(?:Cal|CAL|cal|Caliber|CALIBER)\.?\b\s*", " ", text)

    # "Cal. 7MM" or "Cal." standalone (Swift format — "Cal." may remain after mm stripping)
    text = re.sub(r"Cal\.\s*\d+\.?\d*\s*(?:mm|MM)?\b\s*", " ", text)
    text = re.sub(r"\bCal\.\s*", " ", text)

    # "30-30 WIN", "22 HORNET", "22 ARC", "300 ACC BLK"
    text = re.sub(r"\d+-\d+\s+(?:WIN|HORNET|ARC|MAG)\b\s*", " ", text)
    text = re.sub(r"\d+\s+ACC\s+BLK\b\s*", " ", text)

    # "diameter," or "diameter" (Lehigh Defense format)
    text = re.sub(r"\bdiameter,?\s*", " ", text, flags=re.IGNORECASE)

    return text


def _strip_weight(text: str) -> str:
    """Remove weight patterns."""
    # Lapua metric weight with slash: "9,7 g / " or "12,0 g / "
    text = re.sub(r"\d+[,.]\d+\s*g\s*/\s*", " ", text)

    # Standalone metric weight: "15,0g", "9,27g" (Norma format, no slash)
    text = re.sub(r"\d+[,.]\d+\s*g\b\s*", " ", text)

    # Standard: "150 gr", "168gr", "175 GR", "130 Grain", "150 Grains"
    text = re.sub(r"\d+\.?\d*\s*(?:gr|GR|grain|Grain|Grains|GRAIN)\b\.?\s*", " ", text)

    return text


def _strip_generic_suffixes(text: str) -> str:
    """Remove generic bullet/component suffixes."""
    # "Rifle Bullet", "Rifle Bullets", "Component Bullet", "Bullet", "Bullets"
    text = re.sub(r"\bComponent\s+Bullet\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bRifle\s+Bullets?\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bBullets?\b", "", text, flags=re.IGNORECASE)
    return text


def _strip_pack_counts(text: str) -> str:
    """Remove pack count patterns: (100ct), (50ct), - 50ct, (50 count)."""
    text = re.sub(r"\(\d+\s*(?:ct|count)\)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"-\s*\d+\s*ct\b", "", text, flags=re.IGNORECASE)
    return text


def _strip_sku_codes(text: str) -> str:
    """Remove Lapua-style SKU codes (GB547, E469, GB432)."""
    # Pattern: uppercase letter(s) followed by digits at end of string or before whitespace
    text = re.sub(r"\b[A-Z]{1,2}\d{3,4}\b", "", text)
    return text


def _strip_brand_abbreviations(text: str) -> str:
    """Remove parenthetical brand abbreviations like (SMK), (SGK), (TVK)."""
    text = re.sub(r"\([A-Z]{2,4}\)", "", text)
    return text


def _normalize_brand_casing(text: str) -> str:
    """Fix known brand word casing: MATCHKING → MatchKing, etc."""
    for lower_key, proper in _BRAND_CASING.items():
        # First try the proper form with spaces
        if " " in proper:
            space_pattern = re.compile(
                r"\b" + r"\s+".join(re.escape(w) for w in proper.split()) + r"\b",
                re.IGNORECASE,
            )
            text = space_pattern.sub(proper, text)
        else:
            text = re.sub(r"\b" + re.escape(lower_key) + r"\b", proper, text, flags=re.IGNORECASE)
    return text


def _strip_manufacturer_prefix(text: str, manufacturer_name: str) -> str:
    """Strip manufacturer name from the beginning of display text.

    E.g., "Norma Oryx" with manufacturer="Norma" → "Oryx".
    Only strips if the manufacturer name is at the start and there's content after.
    """
    if not manufacturer_name:
        return text
    # Try the full manufacturer name first, then common short forms
    names_to_try = [manufacturer_name]
    # "Barnes Bullets" → also try "Barnes"
    if " " in manufacturer_name:
        names_to_try.append(manufacturer_name.split()[0])
    for name in names_to_try:
        if text.lower().startswith(name.lower()):
            remaining = text[len(name) :].lstrip()
            if remaining:  # don't strip if nothing is left
                return remaining
    return text


def _clean_whitespace(text: str) -> str:
    """Remove extra whitespace, trailing punctuation, stray separators."""
    # Remove empty parentheses from partial stripping
    text = re.sub(r"\(\s*\)", "", text)
    # Remove stray commas, pipes, and surrounding whitespace
    text = re.sub(r"\s*[,|]\s*", " ", text)
    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text)
    # Strip leading/trailing whitespace and hyphens
    text = text.strip(" \t\n-")
    return text


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_bullet_display_name(
    name: str,
    product_line: str | None = None,
    manufacturer_name: str = "",
) -> str:
    """Compute a clean display name for a bullet.

    The display name is the product identity stripped of weight, caliber,
    diameter, manufacturer, and other data shown separately in the iOS UI.

    Args:
        name: Raw bullet name from manufacturer catalog.
        product_line: Cleaned product line (e.g. "ELD-X", "MatchKing"), if known.
        manufacturer_name: Manufacturer name (for context, not currently used in logic).

    Returns:
        Cleaned display name string.
    """
    text = _normalize_text(name)
    text = _strip_caliber_prefix(text)
    text = _strip_weight(text)
    text = _strip_generic_suffixes(text)
    text = _strip_pack_counts(text)
    text = _strip_sku_codes(text)
    text = _strip_brand_abbreviations(text)
    text = _normalize_brand_casing(text)
    text = _strip_manufacturer_prefix(text, manufacturer_name)
    text = _clean_whitespace(text)

    # If cleaning produced nothing useful, fall back to product_line
    if product_line and (not text or len(text) < 2):
        text = _normalize_text(product_line)
        text = _normalize_brand_casing(text)
        text = _clean_whitespace(text)

    return text


def compute_cartridge_display_name(
    name: str,
    product_line: str | None = None,
    bullet_product_line: str | None = None,
    manufacturer_name: str = "",
) -> str:
    """Compute a clean display name for a cartridge.

    The display name combines the cartridge product line and bullet identity,
    stripped of caliber, weight, MV, and other data shown separately in the iOS UI.

    Args:
        name: Raw cartridge name from manufacturer catalog.
        product_line: Cartridge product line (e.g. "Precision Hunter", "Gold Medal").
        bullet_product_line: Linked bullet's product line (e.g. "ELD-X", "MatchKing").
        manufacturer_name: Manufacturer name (for context).

    Returns:
        Cleaned display name string.
    """
    cart_pl = _clean_cart_product_line(product_line) if product_line else None
    bullet_pl = _clean_bullet_product_line(bullet_product_line) if bullet_product_line else None

    # Path 1: Both product lines available — combine with dedup
    if cart_pl and bullet_pl:
        result = _combine_product_lines(cart_pl, bullet_pl)
        if result:
            return result

    # Path 2: Only cartridge product line — extract bullet identity from name
    if cart_pl:
        bullet_id = _extract_bullet_identity_from_name(name, cart_pl)
        if bullet_id:
            return _combine_product_lines(cart_pl, bullet_id)
        return cart_pl

    # Path 3: Only bullet product line
    if bullet_pl:
        return bullet_pl

    # Path 4: Derive everything from name
    return _derive_cartridge_from_name(name)


# ---------------------------------------------------------------------------
# Cartridge helpers
# ---------------------------------------------------------------------------


def _clean_cart_product_line(product_line: str) -> str:
    """Clean a cartridge product line for display."""
    text = _normalize_text(product_line)
    text = _CART_PL_STRIP_SUFFIXES.sub("", text)
    # Normalize known product line casing
    for lower_key, proper in _PRODUCT_LINE_CASING.items():
        text = re.sub(r"(?i)\b" + re.escape(lower_key) + r"\b", proper, text)
    text = _clean_whitespace(text)
    return text


def _clean_bullet_product_line(product_line: str) -> str:
    """Clean a bullet product line for display."""
    text = _normalize_text(product_line)
    text = _normalize_brand_casing(text)
    text = _clean_whitespace(text)
    return text


def _combine_product_lines(cart_pl: str, bullet_pl: str) -> str:
    """Combine cartridge and bullet product lines with deduplication."""
    # Exact match (case-insensitive) → use one copy
    if cart_pl.lower() == bullet_pl.lower():
        return cart_pl

    # One contains the other → use the longer one, but strip embedded manufacturer names
    cart_lower = cart_pl.lower()
    bullet_lower = bullet_pl.lower()

    if bullet_lower in cart_lower:
        # Bullet PL is already in cart PL — strip manufacturer name if present
        # e.g. "Gold Medal Sierra MatchKing" → "Gold Medal MatchKing" when bullet_pl="MatchKing"
        result = _strip_manufacturer_before_bullet_pl(cart_pl, bullet_pl)
        return result

    if cart_lower in bullet_lower:
        return bullet_pl

    # Neither contains the other → combine: cart first, then bullet
    return f"{cart_pl} {bullet_pl}"


def _strip_manufacturer_before_bullet_pl(cart_pl: str, bullet_pl: str) -> str:
    """Strip a manufacturer name that appears right before bullet_pl in cart_pl.

    E.g., "Gold Medal Sierra MatchKing" with bullet_pl="MatchKing"
    → "Gold Medal MatchKing" (strips "Sierra").

    But "Barnes TSX" with bullet_pl="TSX" → "Barnes TSX" (keep "Barnes"
    because it's the distinguishing part of the Federal product line name).
    """
    # Find bullet_pl in cart_pl (case-insensitive)
    idx = cart_pl.lower().find(bullet_pl.lower())
    if idx <= 0:
        return cart_pl

    # Check if the word before bullet_pl is a known manufacturer
    before = cart_pl[:idx].rstrip()
    words = before.split()
    if words and words[-1].lower() in _BULLET_MANUFACTURERS:
        # Only strip if there's other meaningful text before the manufacturer name.
        # "Barnes TSX" → "Barnes" is the only text before "TSX", don't strip it.
        # "Gold Medal Sierra MatchKing" → "Gold Medal" exists before "Sierra", strip it.
        if len(words) < 2:
            return cart_pl
        cleaned_before = " ".join(words[:-1])
        result = f"{cleaned_before} {cart_pl[idx:]}".strip()
        return _clean_whitespace(result)

    return cart_pl


def _extract_bullet_identity_from_name(name: str, cart_pl: str) -> str | None:
    """Try to extract bullet identity from the cartridge name.

    For Hornady-style names: after stripping caliber, weight, trademarks, and the
    cart product line, what remains is the bullet identity.
    """
    text = _normalize_text(name)

    # For comma-delimited names (Federal format), parse segments
    if ", " in text and text.count(",") >= 3:
        return _extract_federal_bullet_identity(text)

    # Hornady-style: strip caliber, weight, trademarks
    text = _strip_cartridge_caliber(text)
    text = _strip_weight(text)
    text = _strip_muzzle_velocity(text)
    text = _clean_whitespace(text)

    if not text:
        return None

    # Remove the cart product line from what remains to get bullet identity
    # e.g., "ELD-X Precision Hunter" with cart_pl="Precision Hunter" → "ELD-X"
    cart_pl_clean = cart_pl.lower()
    text_lower = text.lower()

    if cart_pl_clean in text_lower:
        # Remove cart_pl and clean up
        idx = text_lower.find(cart_pl_clean)
        remaining = text[:idx] + text[idx + len(cart_pl) :]
        remaining = _clean_whitespace(remaining)
        # Skip generic bullet type abbreviations (SP, HP, RN, FMJ, etc.)
        # These are not meaningful bullet identities on their own
        generic_types = {"SP", "HP", "RN", "FMJ", "FN", "BT", "FB", "BTSP"}
        if remaining and len(remaining) >= 2 and remaining.upper() not in generic_types:
            return remaining

    return None


def _extract_federal_bullet_identity(name: str) -> str | None:
    """Extract bullet identity from Federal comma-delimited format.

    Format: "product_line, caliber, weight, bullet_desc, MV"
    The bullet_desc (4th segment) may contain the bullet identity.
    """
    segments = [s.strip() for s in name.split(",")]
    if len(segments) < 4:
        return None

    bullet_desc = segments[3]
    desc_lower = bullet_desc.lower()

    # If the bullet_desc is the same as the product line name, skip it (dedup)
    pl_segment = segments[0].lower()
    # Strip manufacturer names from bullet desc
    for mfr in _BULLET_MANUFACTURERS:
        desc_lower = re.sub(r"\b" + mfr + r"\b", "", desc_lower).strip()
        bullet_desc = re.sub(r"\b" + mfr + r"\b", "", bullet_desc, flags=re.IGNORECASE).strip()

    # Check if it's a generic description we can abbreviate
    desc_check = bullet_desc.lower().strip()
    for full, abbr in _FEDERAL_BULLET_ABBREV.items():
        if desc_check == full:
            return abbr

    # Check for branded descriptions: "Fusion Soft Point" → skip (redundant)
    # "ELD-X" → keep, "Terminal Ascent" → skip if same as product line
    if desc_check in pl_segment or pl_segment.startswith(desc_check):
        return None

    # Strip generic suffixes from branded descriptions
    bullet_desc = re.sub(
        r"\b(?:Boat-Tail Hollow Point|Soft Point|Hollow Point)\b",
        "",
        bullet_desc,
        flags=re.IGNORECASE,
    )
    bullet_desc = _clean_whitespace(bullet_desc)

    # If we still have something meaningful and it's different from the product line
    if bullet_desc and len(bullet_desc) >= 2:
        return bullet_desc

    return None


def _strip_cartridge_caliber(text: str) -> str:
    """Strip cartridge caliber designations (more patterns than bullet caliber)."""
    # Common cartridge calibers: "6.5 Creedmoor", "308 Win", "300 Win Mag", etc.
    caliber_patterns = [
        r"\d+\.?\d*\s+(?:Creedmoor|PRC|Win(?:chester)?|WSM|Rem(?:ington)?|"
        r"Wby\s+Mag(?:num)?|Lapua(?:\s+Mag)?|Blackout|Hornet|HMR|WMR|WSSM|"
        r"Valkyrie|Springfield|Grendel)\b",
        r"\d+-\d+\s+(?:Win|Springfield|Rem)\b",  # 30-06 Springfield, 30-30 Win
        r"\d+x\d+\w*\s*(?:NATO)?\b",  # 7.62x39, 7.62x51mm NATO
        r"\d+\s+(?:Win|Rem)\s+Mag\b",  # 300 Win Mag, 7mm Rem Mag
    ]
    for pat in caliber_patterns:
        text = re.sub(pat, " ", text, flags=re.IGNORECASE)

    return text


def _strip_muzzle_velocity(text: str) -> str:
    """Strip muzzle velocity patterns: '2675 fps', '3000fps'."""
    text = re.sub(r"\d+\s*fps\b", "", text, flags=re.IGNORECASE)
    return text


def _derive_cartridge_from_name(name: str) -> str:
    """Derive cartridge display name from raw name when no product lines are available."""
    text = _normalize_text(name)

    # Handle Federal comma format
    if ", " in text and text.count(",") >= 3:
        segments = [s.strip() for s in text.split(",")]
        # First segment is usually the product line
        text = segments[0]
        text = _CART_PL_STRIP_SUFFIXES.sub("", text)
        return _clean_whitespace(text)

    # Hornady-style: strip caliber + weight + MV
    text = _strip_cartridge_caliber(text)
    text = _strip_weight(text)
    text = _strip_muzzle_velocity(text)
    text = _normalize_brand_casing(text)
    text = _clean_whitespace(text)

    return text
