# flake8: noqa: E501 B950
"""Entity resolver — links extracted product data to existing DB entities.

Tiered matching strategy:
  1. Exact SKU match
  2. Composite key match (manufacturer + diameter/caliber + weight/model + name substring)
  3. Fuzzy name match (Jaccard word-overlap, scaled by 0.8 confidence ceiling)

Also resolves FK references:
  - manufacturer → match by name or alt_names
  - bullet_diameter_inches → physical diameter for bullet matching (±0.001")
  - caliber → match by name or alt_names (for cartridges/rifles)
  - chamber → match by name or alt_names (for rifles)
  - bullet → match by manufacturer + diameter + weight + name (for cartridges)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from drift.models.bullet import Bullet, BulletBCSource
from drift.models.caliber import Caliber
from drift.models.cartridge import Cartridge
from drift.models.chamber import Chamber, ChamberAcceptsCaliber
from drift.models.entity_alias import EntityAlias
from drift.models.manufacturer import Manufacturer
from drift.models.rifle_model import RifleModel

logger = logging.getLogger(__name__)


@dataclass
class AlternativeMatch:
    """A runner-up candidate captured during entity matching for audit/diagnostics."""

    entity_id: str
    confidence: float
    method: str
    details: str = ""


@dataclass
class MatchResult:
    """Result of attempting to match an extracted entity to the DB."""

    matched: bool
    entity_id: str | None = None
    confidence: float = 0.0
    method: str = ""
    details: str = ""
    alternatives: list[AlternativeMatch] = field(default_factory=list)
    methods_tried: list[str] = field(default_factory=list)

    @property
    def is_ambiguous(self) -> bool:
        """True if the gap between best match and next-best is < 0.2."""
        if not self.alternatives or self.confidence >= 0.97:
            return False
        return (self.confidence - self.alternatives[0].confidence) < 0.2


@dataclass
class ResolutionResult:
    """Full resolution result for an extracted entity."""

    entity_type: str
    match: MatchResult = field(default_factory=lambda: MatchResult(matched=False))
    manufacturer_id: str | None = None
    caliber_id: str | None = None
    chamber_id: str | None = None
    bullet_id: str | None = None
    bullet_match_confidence: float | None = None
    bullet_diameter_inches: float | None = None
    unresolved_refs: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    methods_tried: list[str] = field(default_factory=list)


def _strip_trademarks(name: str) -> str:
    """Strip trademark/copyright symbols: ®, ™, ©."""
    return name.replace("\u00ae", "").replace("\u2122", "").replace("\u00a9", "")


def _normalize(name: str) -> str:
    """Normalize a name for comparison: lowercase, strip punctuation, collapse whitespace.

    Periods are kept only when leading a token (caliber names like ".308", ".223").
    Trailing periods are stripped (handles "Inc." vs "Inc", "INC." vs "Inc").
    """
    name = _strip_trademarks(name).lower().strip()
    # Keep periods to preserve caliber names like ".308", ".223"
    name = re.sub(r"[^\w\s.]", " ", name)
    name = re.sub(r"\s+", " ", name)
    # Strip trailing periods from tokens that don't start with "." (caliber prefix)
    tokens = [t.rstrip(".") if not t.startswith(".") else t for t in name.split()]
    return " ".join(tokens).strip()


def _normalize_caliber(name: str) -> str:
    """Caliber-specific normalization: strip leading periods so '308 Win' matches '.308 Win'.

    LLM-extracted caliber names often omit the leading period that our DB uses
    (e.g. "308 Winchester" vs ".308 Winchester"). This normalizes both forms to
    the same string for comparison.
    """
    norm = _normalize(name)
    # Strip leading period from tokens: ".308" → "308", ".223" → "223"
    tokens = [t.lstrip(".") if t.startswith(".") else t for t in norm.split()]
    return " ".join(tokens)


# Manufacturer prefixes to strip from product-line names during normalization.
_MANUFACTURER_PREFIXES = frozenset(
    {
        "sierra",
        "nosler",
        "berger",
        "barnes",
        "hornady",
        "speer",
        "lapua",
        "federal",
        "winchester",
        "remington",
        "swift",
        "cutting edge",
        "lehigh",
    }
)


def _normalize_product_line(name: str) -> str:
    """Normalize a product-line name for matching.

    Unlike _normalize(), this preserves hyphens (ELD-X stays ELD-X) and strips
    manufacturer prefixes. Also extracts parenthetical abbreviations as alternatives.

    Returns the best (shortest, most canonical) form.
    """
    s = _strip_trademarks(name).lower().strip()
    # Normalize unicode dashes to ASCII hyphen
    s = re.sub(r"[\u2010\u2011\u2012\u2013\u2014\u2015]", "-", s)
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()

    # Extract parenthetical abbreviation: "Barnes Triple-Shock X Bullet (TSX)" → "TSX"
    paren_match = re.search(r"\(([^)]+)\)", s)
    paren_content = paren_match.group(1).strip() if paren_match else None

    # Strip parenthetical from main string
    main = re.sub(r"\([^)]*\)", "", s).strip()

    # Strip manufacturer prefixes
    for prefix in _MANUFACTURER_PREFIXES:
        if main.startswith(prefix + " "):
            main = main[len(prefix) + 1 :].strip()
            break

    # Strip generic suffixes that add noise (longest first to avoid partial matches)
    for suffix in ("component bullet", "soft point", "bullets", "bullet"):
        if main.endswith(" " + suffix):
            candidate = main[: -(len(suffix) + 1)].strip()
            if candidate:
                main = candidate
                break

    # If parenthetical is shorter and non-numeric (ignore count suffixes like "50ct"), prefer it
    if paren_content and not re.match(r"^\d+\w*$", paren_content):
        paren_clean = paren_content.strip()
        # Strip manufacturer prefix from paren too
        for prefix in _MANUFACTURER_PREFIXES:
            if paren_clean.startswith(prefix + " "):
                paren_clean = paren_clean[len(prefix) + 1 :].strip()
                break
        if paren_clean and len(paren_clean) <= len(main):
            return paren_clean

    return main


def _name_similarity(a: str, b: str) -> float:
    """Simple word-overlap similarity between two normalized names.

    Returns 0.0 to 1.0 based on Jaccard index of word sets.
    """
    words_a = set(_normalize(a).split())
    words_b = set(_normalize(b).split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


# Noise words that don't help distinguish bullet identity (caliber/weight/generic suffixes).
_BULLET_NOISE_WORDS = frozenset(
    {
        "gr",
        "grain",
        "grains",
        "cal",
        "caliber",
        "mm",
        "ct",
        "count",
        "bullet",
        "bullets",
        "component",
        "rifle",
        "handgun",
        "pistol",
        # Manufacturer names that LLMs include in bullet descriptions but that
        # don't appear in the bullet's own DB product name.  The manufacturer is
        # already resolved separately — including it in name scoring only adds noise.
        "sierra",
        "nosler",
        "berger",
        "barnes",
        "hornady",
        "speer",
        "lapua",
        "federal",
        "winchester",
        "remington",
    }
)

# Abbreviation ↔ expansion map for bullet type names.
# "HPBT" in a DB name should match "Hollow Point Boat Tail" from an extraction (and vice versa).
# Both directions are handled: abbreviation → words, and each word-set → abbreviation.
_BULLET_ABBREVIATIONS: dict[str, set[str]] = {
    "hpbt": {"hollow", "point", "boat", "tail"},
    "bthp": {"boat", "tail", "hollow", "point"},
    "hp": {"hollow", "point"},
    "bt": {"boat", "tail"},
    "sp": {"soft", "point"},
    "fmj": {"full", "metal", "jacket"},
    "otm": {"open", "tip", "match"},
    "smk": {"sierra", "matchking"},
    "tmk": {"tipped", "matchking"},
    "jhp": {"jacketed", "hollow", "point"},
    "jsp": {"jacketed", "soft", "point"},
    "rn": {"round", "nose"},
    "fn": {"flat", "nose"},
    "spbt": {"soft", "point", "boat", "tail"},
}


def _expand_abbreviations(words: set[str]) -> set[str]:
    """Expand known bullet abbreviations into their constituent words.

    E.g. {"hpbt", "matchking"} → {"hollow", "point", "boat", "tail", "matchking"}.
    Also works in reverse: if the word set contains all expansion words for an
    abbreviation, the abbreviation is added to the set.
    """
    expanded = set(words)
    for abbrev, expansion in _BULLET_ABBREVIATIONS.items():
        if abbrev in expanded:
            expanded |= expansion
        if expansion <= expanded:
            expanded.add(abbrev)
    return expanded


def _bullet_name_score(extracted_name: str, db_name: str) -> float:
    """Score how well an extracted bullet type name matches a DB bullet product name.

    Cartridge pages give short type names ("ELD-X", "SST", "CX") while DB bullet
    names are full product strings ("30 Cal .308 178 gr ELD-X®").  Standard Jaccard
    fails here because the union is dominated by caliber/weight tokens in the DB name.

    Strategy: extract meaningful keywords from both sides (strip noise words and
    pure-numeric tokens), expand known abbreviations (HPBT ↔ Hollow Point Boat Tail),
    then check what fraction of the extracted keywords appear in the DB name.
    Returns 0.0–1.0.

    Handles parenthetical expansions — LLM often extracts "SST (Super Shock Tip)"
    where the DB just has "SST®".  We score both the full name and the portion
    before any parenthetical, taking the best.
    """

    def _meaningful_words(name: str) -> set[str]:
        """Extract semantically meaningful words, stripping noise and numbers."""
        tokens = set(_normalize(name).split())
        # Remove pure numbers (weights, calibers like "308", "140") and noise
        return {t for t in tokens if not t.replace(".", "").isdigit() and t not in _BULLET_NOISE_WORDS}

    def _score_pair(query_words: set[str], target_words: set[str]) -> float:
        if not query_words or not target_words:
            return 0.0
        matched = query_words & target_words
        if not matched:
            return 0.0
        containment = len(matched) / len(query_words)
        length_factor = min(len(query_words) / 2.0, 1.0)
        return containment * (0.5 + 0.5 * length_factor)

    target_words = _expand_abbreviations(_meaningful_words(db_name))

    # Score the full extracted name
    full_words = _expand_abbreviations(_meaningful_words(extracted_name))
    score = _score_pair(full_words, target_words)

    # Also try the portion before any parenthetical — handles "SST (Super Shock Tip)"
    paren_idx = extracted_name.find("(")
    if paren_idx > 0:
        prefix = extracted_name[:paren_idx].strip()
        prefix_words = _expand_abbreviations(_meaningful_words(prefix))
        score = max(score, _score_pair(prefix_words, target_words))

    return score


def _pick_best_with_alternatives(
    all_scored: list[tuple[str, float, str, str]],
    methods_tried: list[str],
    fallback_detail: str,
) -> MatchResult:
    """Deduplicate scored candidates by entity_id, pick the best, and build alternatives.

    Args:
        all_scored: List of (entity_id, confidence, method, details) tuples from all tiers.
        methods_tried: Which matching tiers were attempted.
        fallback_detail: Detail string for the no-match case.

    Returns:
        MatchResult with best candidate selected and top 3 runner-ups as alternatives.
    """
    if not all_scored:
        return MatchResult(matched=False, details=fallback_detail, methods_tried=methods_tried)

    # Deduplicate by entity_id — keep highest confidence per entity
    best_per_entity: dict[str, tuple[str, float, str, str]] = {}
    for entity_id, conf, method, details in all_scored:
        if entity_id not in best_per_entity or conf > best_per_entity[entity_id][1]:
            best_per_entity[entity_id] = (entity_id, conf, method, details)

    # Sort by confidence descending
    ranked = sorted(best_per_entity.values(), key=lambda x: x[1], reverse=True)
    best_id, best_conf, best_method, best_details = ranked[0]

    # Build alternatives from runners-up (top 3)
    alternatives = [
        AlternativeMatch(entity_id=eid, confidence=conf, method=method, details=details)
        for eid, conf, method, details in ranked[1:4]
    ]

    return MatchResult(
        matched=True,
        entity_id=best_id,
        confidence=best_conf,
        method=best_method,
        details=best_details,
        alternatives=alternatives,
        methods_tried=methods_tried,
    )


class EntityResolver:
    """Resolves extracted entities against existing DB records."""

    def __init__(self, session: Session):
        self._session = session
        # Cache lookups on first use
        self._manufacturers: list[Manufacturer] | None = None
        self._calibers: list[Caliber] | None = None
        self._chambers: list[Chamber] | None = None
        self._caliber_aliases: list[EntityAlias] | None = None

    # ── FK resolution helpers ────────────────────────────────────────────────

    def _get_manufacturers(self) -> list[Manufacturer]:
        if self._manufacturers is None:
            self._manufacturers = list(self._session.scalars(select(Manufacturer)))
        return self._manufacturers

    def _get_calibers(self) -> list[Caliber]:
        if self._calibers is None:
            self._calibers = list(self._session.scalars(select(Caliber)))
        return self._calibers

    def _get_chambers(self) -> list[Chamber]:
        if self._chambers is None:
            self._chambers = list(self._session.scalars(select(Chamber)))
        return self._chambers

    def _get_caliber_aliases(self) -> list[EntityAlias]:
        if self._caliber_aliases is None:
            self._caliber_aliases = list(
                self._session.scalars(select(EntityAlias).where(EntityAlias.entity_type == "caliber"))
            )
        return self._caliber_aliases

    def resolve_manufacturer(self, name: str) -> MatchResult:
        """Resolve a manufacturer name to an existing DB record."""
        norm_name = _normalize(name)

        for mfr in self._get_manufacturers():
            # Exact name match
            if _normalize(mfr.name) == norm_name:
                return MatchResult(matched=True, entity_id=mfr.id, confidence=1.0, method="exact_name")

            # Alt names match
            if mfr.alt_names:
                for alt in mfr.alt_names:
                    if _normalize(alt) == norm_name:
                        return MatchResult(matched=True, entity_id=mfr.id, confidence=0.95, method="alt_name")

        # Fuzzy: check main name and all alt_names
        best_match: MatchResult | None = None
        best_score = 0.0
        for mfr in self._get_manufacturers():
            candidates = [mfr.name] + (mfr.alt_names or [])
            for candidate in candidates:
                score = _name_similarity(name, candidate)
                if score > 0.5 and score > best_score:
                    best_score = score
                    best_match = MatchResult(
                        matched=True,
                        entity_id=mfr.id,
                        confidence=round(score * 0.9, 2),
                        method="fuzzy_name",
                        details=f"matched '{candidate}' (via {mfr.name}) with score {score:.2f}",
                    )

        if best_match:
            return best_match

        return MatchResult(matched=False, details=f"no match for manufacturer '{name}'")

    def resolve_caliber(self, name: str) -> MatchResult:
        """Resolve a caliber name to an existing DB record.

        Matching tiers:
          1. Exact name / alt_name (standard normalization)
          2. Period-insensitive match (caliber-specific: "308 Win" ↔ ".308 Win")
          3. EntityAlias table lookup
          4. Fuzzy name match (Jaccard word-overlap across name + alt_names)
        """
        norm_name = _normalize(name)
        cal_norm_name = _normalize_caliber(name)

        # Tier 1: Exact name / alt_name match (standard normalization)
        for cal in self._get_calibers():
            if _normalize(cal.name) == norm_name:
                return MatchResult(matched=True, entity_id=cal.id, confidence=1.0, method="exact_name")
            if cal.alt_names:
                for alt in cal.alt_names:
                    if _normalize(alt) == norm_name:
                        return MatchResult(matched=True, entity_id=cal.id, confidence=0.95, method="alt_name")

        # Tier 2: Period-insensitive match (handles "308 Win" vs ".308 Winchester")
        for cal in self._get_calibers():
            if _normalize_caliber(cal.name) == cal_norm_name:
                return MatchResult(
                    matched=True,
                    entity_id=cal.id,
                    confidence=0.95,
                    method="caliber_norm",
                    details=f"period-insensitive match: '{name}' → '{cal.name}'",
                )
            if cal.alt_names:
                for alt in cal.alt_names:
                    if _normalize_caliber(alt) == cal_norm_name:
                        return MatchResult(
                            matched=True,
                            entity_id=cal.id,
                            confidence=0.9,
                            method="caliber_norm_alt",
                            details=f"period-insensitive alt match: '{name}' → '{alt}' (via {cal.name})",
                        )

        # Tier 3: EntityAlias table lookup
        for alias in self._get_caliber_aliases():
            if _normalize(alias.alias) == norm_name or _normalize_caliber(alias.alias) == cal_norm_name:
                # Verify the referenced caliber exists
                cal = self._session.get(Caliber, alias.entity_id)
                if cal:
                    return MatchResult(
                        matched=True,
                        entity_id=cal.id,
                        confidence=0.9,
                        method="entity_alias",
                        details=f"alias '{alias.alias}' → '{cal.name}'",
                    )

        # Tier 4: Fuzzy match (check name + alt_names)
        best_match: MatchResult | None = None
        best_score = 0.0
        for cal in self._get_calibers():
            candidates = [cal.name] + (cal.alt_names or [])
            for candidate in candidates:
                score = _name_similarity(name, candidate)
                if score > 0.4 and score > best_score:
                    best_score = score
                    best_match = MatchResult(
                        matched=True,
                        entity_id=cal.id,
                        confidence=round(score * 0.85, 2),
                        method="fuzzy_name",
                        details=f"matched '{candidate}' (via {cal.name}) with score {score:.2f}",
                    )

        if best_match:
            return best_match

        return MatchResult(matched=False, details=f"no match for caliber '{name}'")

    def resolve_chamber(self, caliber_name: str) -> MatchResult:
        """Resolve a chamber from a caliber name (for rifles).

        Rifles reference chamber_id, not caliber_id. We find the chamber
        that accepts the given caliber.
        """
        # First resolve the caliber
        cal_match = self.resolve_caliber(caliber_name)
        if not cal_match.matched or not cal_match.entity_id:
            return MatchResult(matched=False, details=f"cannot resolve chamber: caliber '{caliber_name}' not found")

        # Find chambers that accept this caliber
        links = list(
            self._session.scalars(
                select(ChamberAcceptsCaliber).where(ChamberAcceptsCaliber.caliber_id == cal_match.entity_id)
            )
        )
        if not links:
            return MatchResult(matched=False, details=f"no chamber found for caliber '{caliber_name}'")

        # Prefer the primary chamber
        for link in links:
            if link.is_primary:
                return MatchResult(
                    matched=True,
                    entity_id=link.chamber_id,
                    confidence=0.9,
                    method="caliber_to_chamber",
                    details=f"primary chamber for caliber '{caliber_name}'",
                )

        # Fall back to first link
        return MatchResult(
            matched=True,
            entity_id=links[0].chamber_id,
            confidence=0.7,
            method="caliber_to_chamber",
            details=f"non-primary chamber for caliber '{caliber_name}'",
        )

    # ── Entity matching ──────────────────────────────────────────────────────

    def match_bullet(
        self, extracted: dict, manufacturer_id: str | None, bullet_diameter_inches: float | None
    ) -> MatchResult:
        """Match an extracted bullet against existing DB bullets.

        Collects scored candidates across product_line matching, Tier 2 (composite key),
        and Tier 3 (fuzzy), picks the global best, and records runner-up alternatives.
        """
        name = _get_value(extracted, "name", "")
        sku = _get_value(extracted, "sku")
        weight = _get_value(extracted, "weight_grains")
        extracted_product_line = _get_value(extracted, "product_line")
        methods_tried: list[str] = []

        # Tier 1: Exact SKU match (deterministic, short-circuits)
        if sku:
            methods_tried.append("exact_sku")
            bullet = self._session.scalars(select(Bullet).where(Bullet.sku == sku)).first()
            if bullet:
                return MatchResult(
                    matched=True,
                    entity_id=bullet.id,
                    confidence=1.0,
                    method="exact_sku",
                    details=f"SKU={sku}",
                    methods_tried=methods_tried,
                )

        # Build candidate pool for tier 2/3
        stmt = select(Bullet)
        if manufacturer_id:
            stmt = stmt.where(Bullet.manufacturer_id == manufacturer_id)
        if bullet_diameter_inches is not None:
            stmt = stmt.where(
                Bullet.bullet_diameter_inches.between(bullet_diameter_inches - 0.001, bullet_diameter_inches + 0.001)
            )
        else:
            logger.warning("match_bullet called without diameter filter — may match across caliber families")

        candidates = list(self._session.scalars(stmt))

        # Collect all scored candidates across tiers: (entity_id, confidence, method, details)
        all_scored: list[tuple[str, float, str, str]] = []

        # Derive a normalized product line from the extracted name for matching.
        # This is used both for product_line matching and as a fallback when
        # the extracted entity doesn't have an explicit product_line field.
        norm_extracted_pl = _normalize_product_line(name) if name else ""
        if extracted_product_line:
            norm_extracted_pl = _normalize_product_line(extracted_product_line)

        # Product-line matching — when the extracted name (or explicit product_line)
        # matches a bullet's product_line, that's a strong signal. Combined with
        # weight + diameter (already filtered), this is highly deterministic.
        if norm_extracted_pl:
            methods_tried.append("product_line")
            for bullet in candidates:
                if not bullet.product_line:
                    continue
                norm_bullet_pl = _normalize_product_line(bullet.product_line)
                if norm_bullet_pl != norm_extracted_pl:
                    continue
                # Product line matches — score based on weight agreement
                if weight is not None:
                    try:
                        weight_matches = abs(bullet.weight_grains - float(weight)) < 0.5
                    except (ValueError, TypeError):
                        weight_matches = False
                else:
                    weight_matches = False
                if weight_matches:
                    conf = 0.93
                    detail = f"product_line={norm_extracted_pl}, weight={weight}"
                else:
                    conf = 0.80
                    detail = f"product_line={norm_extracted_pl}, no weight match"
                all_scored.append((bullet.id, conf, "product_line", detail))

        # Tier 2: Composite key — weight match + best name similarity
        if weight is not None:
            methods_tried.append("composite_key")
            for bullet in candidates:
                if abs(bullet.weight_grains - float(weight)) < 0.5:
                    if name and bullet.name:
                        jaccard = _name_similarity(name, bullet.name)
                        containment = _bullet_name_score(name, bullet.name)
                        name_score = max(jaccard, containment)
                    else:
                        name_score = 0.0
                    if name_score > 0.55:
                        conf = round(0.85 + name_score * 0.1, 2)
                        all_scored.append(
                            (bullet.id, conf, "composite_key", f"weight={weight}, name_score={name_score:.2f}")
                        )

        # Tier 3: Fuzzy name match — with weight agreement check
        if name:
            methods_tried.append("fuzzy_name")
            for bullet in candidates:
                jaccard = _name_similarity(name, bullet.name)
                containment = _bullet_name_score(name, bullet.name)
                score = max(jaccard, containment)
                if score > 0.5:
                    if weight is not None:
                        try:
                            weight_agrees = abs(bullet.weight_grains - float(weight)) <= 1.0
                        except (ValueError, TypeError):
                            weight_agrees = False
                    else:
                        weight_agrees = False
                    confidence_factor = 0.8 if weight_agrees else 0.4
                    conf = round(score * confidence_factor, 2)
                    all_scored.append(
                        (
                            bullet.id,
                            conf,
                            "fuzzy_name",
                            f"matched '{bullet.name}' score={score:.2f} weight_agrees={weight_agrees}",
                        )
                    )

        return _pick_best_with_alternatives(all_scored, methods_tried, f"no match for bullet '{name}'")

    def match_cartridge(self, extracted: dict, manufacturer_id: str | None, caliber_id: str | None) -> MatchResult:
        """Match an extracted cartridge against existing DB cartridges.

        Collects scored candidates across Tier 2 (composite key) and Tier 3 (fuzzy),
        picks the global best, and records runner-up alternatives for diagnostics.
        """
        name = _get_value(extracted, "name", "")
        sku = _get_value(extracted, "sku")
        weight = _get_value(extracted, "bullet_weight_grains")
        methods_tried: list[str] = []

        # Tier 1: Exact SKU match (deterministic, short-circuits)
        if sku:
            methods_tried.append("exact_sku")
            cart = self._session.scalars(select(Cartridge).where(Cartridge.sku == sku)).first()
            if cart:
                return MatchResult(
                    matched=True,
                    entity_id=cart.id,
                    confidence=1.0,
                    method="exact_sku",
                    details=f"SKU={sku}",
                    methods_tried=methods_tried,
                )

        # Build candidate pool for tier 2/3
        stmt = select(Cartridge)
        if manufacturer_id:
            stmt = stmt.where(Cartridge.manufacturer_id == manufacturer_id)
        if caliber_id:
            stmt = stmt.where(Cartridge.caliber_id == caliber_id)

        candidates = list(self._session.scalars(stmt))
        all_scored: list[tuple[str, float, str, str]] = []

        # Tier 2: Composite key — weight match + best name similarity
        # Uses both Jaccard and containment-based scoring to handle asymmetric names.
        if weight is not None:
            methods_tried.append("composite_key")
            for cart in candidates:
                if abs(cart.bullet_weight_grains - float(weight)) < 0.5:
                    if name and cart.name:
                        jaccard = _name_similarity(name, cart.name)
                        containment = _bullet_name_score(name, cart.name)
                        name_score = max(jaccard, containment)
                    else:
                        name_score = 0.0
                    if name_score > 0.55:
                        conf = round(0.85 + name_score * 0.1, 2)
                        all_scored.append(
                            (cart.id, conf, "composite_key", f"weight={weight}, name_score={name_score:.2f}")
                        )

        # Tier 3: Fuzzy name match — with weight agreement check
        if name:
            methods_tried.append("fuzzy_name")
            for cart in candidates:
                jaccard = _name_similarity(name, cart.name)
                containment = _bullet_name_score(name, cart.name)
                score = max(jaccard, containment)
                if score > 0.5:
                    if weight is not None:
                        try:
                            weight_agrees = abs(cart.bullet_weight_grains - float(weight)) <= 1.0
                        except (ValueError, TypeError):
                            weight_agrees = False
                    else:
                        weight_agrees = False
                    confidence_factor = 0.8 if weight_agrees else 0.4
                    conf = round(score * confidence_factor, 2)
                    all_scored.append(
                        (
                            cart.id,
                            conf,
                            "fuzzy_name",
                            f"matched '{cart.name}' score={score:.2f} weight_agrees={weight_agrees}",
                        )
                    )

        return _pick_best_with_alternatives(all_scored, methods_tried, f"no match for cartridge '{name}'")

    def match_rifle(self, extracted: dict, manufacturer_id: str | None, chamber_id: str | None) -> MatchResult:
        """Match an extracted rifle model against existing DB rifles.

        Collects scored candidates across Tier 2 (composite key) and Tier 3 (fuzzy),
        picks the global best, and records runner-up alternatives for diagnostics.
        """
        model_name = _get_value(extracted, "model", "")
        methods_tried: list[str] = []

        stmt = select(RifleModel)
        if manufacturer_id:
            stmt = stmt.where(RifleModel.manufacturer_id == manufacturer_id)
        if chamber_id:
            stmt = stmt.where(RifleModel.chamber_id == chamber_id)

        candidates = list(self._session.scalars(stmt))
        all_scored: list[tuple[str, float, str, str]] = []

        # Tier 2: Composite key — manufacturer + chamber + model name
        methods_tried.append("composite_key")
        for rifle in candidates:
            name_score = _name_similarity(model_name, rifle.model)
            if name_score > 0.5:
                conf = round(0.85 + name_score * 0.1, 2)
                all_scored.append((rifle.id, conf, "composite_key", f"model_score={name_score:.2f}"))

        # Tier 3: Fuzzy — search all rifles by this manufacturer, with chamber agreement check
        if manufacturer_id:
            methods_tried.append("fuzzy_name")
            all_by_mfr = list(
                self._session.scalars(select(RifleModel).where(RifleModel.manufacturer_id == manufacturer_id))
            )
            for rifle in all_by_mfr:
                score = _name_similarity(model_name, rifle.model)
                if score > 0.5:
                    chamber_agrees = chamber_id is not None and rifle.chamber_id == chamber_id
                    confidence_factor = 0.8 if chamber_agrees else 0.4
                    conf = round(score * confidence_factor, 2)
                    all_scored.append(
                        (
                            rifle.id,
                            conf,
                            "fuzzy_name",
                            f"matched '{rifle.model}' score={score:.2f} chamber_agrees={chamber_agrees}",
                        )
                    )

        return _pick_best_with_alternatives(all_scored, methods_tried, f"no match for rifle '{model_name}'")

    # ── Full resolution ──────────────────────────────────────────────────────

    def resolve(self, extracted: dict, entity_type: str) -> ResolutionResult:
        """Resolve an extracted entity: match FKs and check for existing duplicates.

        Args:
            extracted: Raw extracted entity dict (with ExtractedValue wrappers).
            entity_type: One of "bullet", "cartridge", "rifle".

        Returns:
            ResolutionResult with match info, resolved FK IDs, and any warnings.
        """
        result = ResolutionResult(entity_type=entity_type)

        # Resolve manufacturer
        mfr_name = _get_value(extracted, "manufacturer")
        if mfr_name:
            mfr_match = self.resolve_manufacturer(mfr_name)
            if mfr_match.matched:
                result.manufacturer_id = mfr_match.entity_id
            else:
                result.unresolved_refs.append(f"manufacturer: {mfr_name}")
        else:
            result.unresolved_refs.append("manufacturer: not extracted")

        # Resolve caliber / chamber / diameter depending on entity type
        if entity_type == "bullet":
            # Bullets use bullet_diameter_inches (physical property), not caliber_id FK
            diameter = _get_value(extracted, "bullet_diameter_inches")
            if diameter is not None:
                try:
                    result.bullet_diameter_inches = float(diameter)
                except (ValueError, TypeError):
                    result.unresolved_refs.append(f"bullet_diameter_inches: invalid value '{diameter}'")
            else:
                result.unresolved_refs.append("bullet_diameter_inches: not extracted")
        else:
            # Cartridges and rifles still use caliber_id FK
            caliber_name = _get_value(extracted, "caliber")
            if caliber_name:
                if entity_type == "rifle":
                    chamber_match = self.resolve_chamber(caliber_name)
                    if chamber_match.matched:
                        result.chamber_id = chamber_match.entity_id
                    else:
                        result.unresolved_refs.append(f"chamber (from caliber): {caliber_name}")
                    # Also resolve caliber for reference
                    cal_match = self.resolve_caliber(caliber_name)
                    if cal_match.matched:
                        result.caliber_id = cal_match.entity_id
                else:
                    cal_match = self.resolve_caliber(caliber_name)
                    if cal_match.matched:
                        result.caliber_id = cal_match.entity_id
                    else:
                        result.unresolved_refs.append(f"caliber: {caliber_name}")
            else:
                result.unresolved_refs.append("caliber: not extracted")

        # Match against existing entities — propagate methods_tried to ResolutionResult
        if entity_type == "bullet":
            result.match = self.match_bullet(extracted, result.manufacturer_id, result.bullet_diameter_inches)
            result.methods_tried = result.match.methods_tried
        elif entity_type == "cartridge":
            result.match = self.match_cartridge(extracted, result.manufacturer_id, result.caliber_id)
            result.methods_tried = result.match.methods_tried
            # Also try to resolve bullet FK for cartridges
            bullet_name = _get_value(extracted, "bullet_name")
            if bullet_name and result.caliber_id:
                # Look up the caliber's bullet diameter so we can match bullets by diameter
                cal_obj = self._session.get(Caliber, result.caliber_id)
                if cal_obj is None:
                    logger.warning(
                        "Caliber %s resolved but not found in DB — bullet diameter "
                        "filter will be skipped for bullet '%s'",
                        result.caliber_id,
                        bullet_name,
                    )
                    result.warnings.append(
                        f"caliber {result.caliber_id} not found; bullet match has no diameter filter"
                    )
                cart_bullet_diameter = cal_obj.bullet_diameter_inches if cal_obj else None
                weight = _get_value(extracted, "bullet_weight_grains")
                bullet_stub = {"name": {"value": bullet_name}, "weight_grains": {"value": weight}}
                # Search across ALL bullet manufacturers — factory ammo often uses
                # bullets from a different company (e.g. Federal loads Sierra MatchKings).
                # Diameter + weight narrow the candidates; name similarity picks the best.
                bullet_match = self.match_bullet(bullet_stub, None, cart_bullet_diameter)
                # Require minimum confidence for bullet FK assignment — low-confidence
                # fuzzy matches (e.g. weight-mismatched Tier 3) should be flagged, not assigned.
                if bullet_match.matched and bullet_match.confidence >= 0.5:
                    result.bullet_id = bullet_match.entity_id
                    # Boost confidence when cartridge BC/weight exactly match the bullet
                    boost, bc_warnings = _bc_weight_confidence_boost(extracted, bullet_match.entity_id, self._session)
                    result.bullet_match_confidence = min(bullet_match.confidence + boost, 1.0)
                    result.warnings.extend(bc_warnings)
                elif bullet_match.matched:
                    result.unresolved_refs.append(
                        f"bullet: {bullet_name} (low confidence {bullet_match.confidence:.0%}: {bullet_match.details})"
                    )
                else:
                    result.unresolved_refs.append(f"bullet: {bullet_name}")
        elif entity_type == "rifle":
            result.match = self.match_rifle(extracted, result.manufacturer_id, result.chamber_id)
            result.methods_tried = result.match.methods_tried
        else:
            result.match = MatchResult(matched=False, details=f"unknown entity type: {entity_type}")
            result.warnings.append(f"Unknown entity type: {entity_type}")

        return result


_BC_TOLERANCE = 5e-4  # Covers manufacturer rounding at 3 decimal places (max rounding error = 0.0005)


def _bc_weight_confidence_boost(extracted: dict, bullet_id: str, session: Session) -> tuple[float, list[str]]:
    """Compare cartridge-extracted BC/weight against the matched bullet's published values.

    Returns a (boost, warnings) tuple:
      - boost: additive confidence increase (0.0–0.15) for matching signals
      - warnings: list of disagreement warnings (informational, not disqualifying)

    Weight uses ±0.5 gr tolerance (same as composite key matching).
    BC uses ±5e-4 tolerance to absorb manufacturer rounding at 3 decimal places.
    """
    boost = 0.0
    warnings: list[str] = []
    bullet = session.get(Bullet, bullet_id)
    if bullet is None:
        logger.warning("Bullet %s referenced by BC/weight boost not found in DB", bullet_id)
        return boost, warnings

    # Weight agreement (±0.5 gr — same tolerance as match_bullet composite key)
    cart_weight = _get_value(extracted, "bullet_weight_grains")
    if cart_weight is not None and bullet.weight_grains is not None:
        try:
            if abs(float(cart_weight) - bullet.weight_grains) <= 0.5:
                boost += 0.05
        except (ValueError, TypeError):
            logger.warning("Cannot compare weight for bullet %s: cart_weight=%r is not numeric", bullet_id, cart_weight)

    # BC G1 match (±5e-4 tolerance)
    cart_g1 = _get_value(extracted, "bc_g1")
    if cart_g1 is not None and bullet.bc_g1_published is not None:
        try:
            if abs(float(cart_g1) - bullet.bc_g1_published) < _BC_TOLERANCE:
                boost += 0.05
            else:
                warnings.append(f"bc_g1 mismatch: cartridge={cart_g1}, bullet={bullet.bc_g1_published}")
        except (ValueError, TypeError):
            logger.warning("Cannot compare bc_g1 for bullet %s: cart_g1=%r is not numeric", bullet_id, cart_g1)

    # BC G7 match (±5e-4 tolerance)
    cart_g7 = _get_value(extracted, "bc_g7")
    if cart_g7 is not None and bullet.bc_g7_published is not None:
        try:
            if abs(float(cart_g7) - bullet.bc_g7_published) < _BC_TOLERANCE:
                boost += 0.05
            else:
                warnings.append(f"bc_g7 mismatch: cartridge={cart_g7}, bullet={bullet.bc_g7_published}")
        except (ValueError, TypeError):
            logger.warning("Cannot compare bc_g7 for bullet %s: cart_g7=%r is not numeric", bullet_id, cart_g7)

    return boost, warnings


def _get_value(entity: dict, field_name: str, default=None):
    """Extract the raw value from an ExtractedValue dict wrapper."""
    field_data = entity.get(field_name)
    if field_data is None:
        return default
    if isinstance(field_data, dict):
        return field_data.get("value", default)
    return field_data
