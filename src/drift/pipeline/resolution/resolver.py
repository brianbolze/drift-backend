# flake8: noqa: E501 B950
"""Entity resolver — links extracted product data to existing DB entities.

Tiered matching strategy:
  1. Exact SKU match
  2. Composite key match (manufacturer + caliber + weight/model + name substring)
  3. Fuzzy name match (Jaccard word-overlap, scaled by 0.8 confidence ceiling)

Also resolves FK references:
  - manufacturer → match by name or alt_names
  - caliber → match by name or alt_names
  - chamber → match by name or alt_names (for rifles)
  - bullet → match by manufacturer + caliber + weight + name (for cartridges)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from drift.models.bullet import Bullet, BulletBCSource
from drift.models.caliber import Caliber
from drift.models.cartridge import Cartridge
from drift.models.chamber import Chamber, ChamberAcceptsCaliber
from drift.models.manufacturer import Manufacturer
from drift.models.rifle_model import RifleModel

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """Result of attempting to match an extracted entity to the DB."""

    matched: bool
    entity_id: str | None = None
    confidence: float = 0.0
    method: str = ""
    details: str = ""


@dataclass
class ResolutionResult:
    """Full resolution result for an extracted entity."""

    entity_type: str
    match: MatchResult = field(default_factory=lambda: MatchResult(matched=False))
    manufacturer_id: str | None = None
    caliber_id: str | None = None
    chamber_id: str | None = None
    bullet_id: str | None = None
    unresolved_refs: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _normalize(name: str) -> str:
    """Normalize a name for comparison: lowercase, strip punctuation (preserving periods), collapse whitespace."""
    name = name.lower().strip()
    # Keep periods to preserve caliber names like ".308", ".223"
    name = re.sub(r"[^\w\s.]", " ", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()


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


class EntityResolver:
    """Resolves extracted entities against existing DB records."""

    def __init__(self, session: Session):
        self._session = session
        # Cache lookups on first use
        self._manufacturers: list[Manufacturer] | None = None
        self._calibers: list[Caliber] | None = None
        self._chambers: list[Chamber] | None = None

    # ── FK resolution helpers ────────────────────────────────────────────────

    def _get_manufacturers(self) -> list[Manufacturer]:
        if self._manufacturers is None:
            self._manufacturers = self._session.query(Manufacturer).all()
        return self._manufacturers

    def _get_calibers(self) -> list[Caliber]:
        if self._calibers is None:
            self._calibers = self._session.query(Caliber).all()
        return self._calibers

    def _get_chambers(self) -> list[Chamber]:
        if self._chambers is None:
            self._chambers = self._session.query(Chamber).all()
        return self._chambers

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

        # Fuzzy: check if extracted name contains or is contained in DB name
        best_match: MatchResult | None = None
        best_score = 0.0
        for mfr in self._get_manufacturers():
            score = _name_similarity(name, mfr.name)
            if score > 0.5 and score > best_score:
                best_score = score
                best_match = MatchResult(
                    matched=True,
                    entity_id=mfr.id,
                    confidence=round(score * 0.9, 2),
                    method="fuzzy_name",
                    details=f"matched '{mfr.name}' with score {score:.2f}",
                )

        if best_match:
            return best_match

        return MatchResult(matched=False, details=f"no match for manufacturer '{name}'")

    def resolve_caliber(self, name: str) -> MatchResult:
        """Resolve a caliber name to an existing DB record."""
        norm_name = _normalize(name)

        for cal in self._get_calibers():
            if _normalize(cal.name) == norm_name:
                return MatchResult(matched=True, entity_id=cal.id, confidence=1.0, method="exact_name")
            if cal.alt_names:
                for alt in cal.alt_names:
                    if _normalize(alt) == norm_name:
                        return MatchResult(matched=True, entity_id=cal.id, confidence=0.95, method="alt_name")

        # Fuzzy match
        best_match: MatchResult | None = None
        best_score = 0.0
        for cal in self._get_calibers():
            score = _name_similarity(name, cal.name)
            if score > 0.4 and score > best_score:
                best_score = score
                best_match = MatchResult(
                    matched=True,
                    entity_id=cal.id,
                    confidence=round(score * 0.85, 2),
                    method="fuzzy_name",
                    details=f"matched '{cal.name}' with score {score:.2f}",
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
        links = (
            self._session.query(ChamberAcceptsCaliber)
            .filter(ChamberAcceptsCaliber.caliber_id == cal_match.entity_id)
            .all()
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

    def match_bullet(self, extracted: dict, manufacturer_id: str | None, caliber_id: str | None) -> MatchResult:
        """Match an extracted bullet against existing DB bullets."""
        # Extract values from the ExtractedValue wrapper
        name = _get_value(extracted, "name", "")
        sku = _get_value(extracted, "sku")
        weight = _get_value(extracted, "weight_grains")

        # Tier 1: Exact SKU match
        if sku:
            bullet = self._session.query(Bullet).filter(Bullet.sku == sku).first()
            if bullet:
                return MatchResult(
                    matched=True, entity_id=bullet.id, confidence=1.0, method="exact_sku", details=f"SKU={sku}"
                )

        # Build query for tier 2/3
        query = self._session.query(Bullet)
        if manufacturer_id:
            query = query.filter(Bullet.manufacturer_id == manufacturer_id)
        if caliber_id:
            query = query.filter(Bullet.caliber_id == caliber_id)

        candidates = query.all()

        # Tier 2: Composite key — manufacturer + caliber + weight + name substring
        if weight is not None:
            for bullet in candidates:
                if abs(bullet.weight_grains - float(weight)) < 0.5:
                    name_score = _name_similarity(name, bullet.name) if name and bullet.name else 0.0
                    if name_score > 0.3:
                        return MatchResult(
                            matched=True,
                            entity_id=bullet.id,
                            confidence=round(0.85 + name_score * 0.1, 2),
                            method="composite_key",
                            details=f"weight={weight}, name_score={name_score:.2f}",
                        )

        # Tier 3: Fuzzy name match — with weight agreement check
        if name:
            best_score = 0.0
            best_bullet: Bullet | None = None
            best_weight_agrees = False
            for bullet in candidates:
                score = _name_similarity(name, bullet.name)
                if score > best_score:
                    best_score = score
                    best_bullet = bullet
                    if weight is not None:
                        try:
                            best_weight_agrees = abs(bullet.weight_grains - float(weight)) <= 1.0
                        except (ValueError, TypeError):
                            best_weight_agrees = False
                    else:
                        best_weight_agrees = False

            if best_bullet and best_score > 0.5:
                confidence_factor = 0.8 if best_weight_agrees else 0.4
                return MatchResult(
                    matched=True,
                    entity_id=best_bullet.id,
                    confidence=round(best_score * confidence_factor, 2),
                    method="fuzzy_name",
                    details=f"matched '{best_bullet.name}' score={best_score:.2f} weight_agrees={best_weight_agrees}",
                )

        return MatchResult(matched=False, details=f"no match for bullet '{name}'")

    def match_cartridge(self, extracted: dict, manufacturer_id: str | None, caliber_id: str | None) -> MatchResult:
        """Match an extracted cartridge against existing DB cartridges."""
        name = _get_value(extracted, "name", "")
        sku = _get_value(extracted, "sku")
        weight = _get_value(extracted, "bullet_weight_grains")

        # Tier 1: Exact SKU match
        if sku:
            cart = self._session.query(Cartridge).filter(Cartridge.sku == sku).first()
            if cart:
                return MatchResult(
                    matched=True, entity_id=cart.id, confidence=1.0, method="exact_sku", details=f"SKU={sku}"
                )

        # Build query for tier 2/3
        query = self._session.query(Cartridge)
        if manufacturer_id:
            query = query.filter(Cartridge.manufacturer_id == manufacturer_id)
        if caliber_id:
            query = query.filter(Cartridge.caliber_id == caliber_id)

        candidates = query.all()

        # Tier 2: Composite key
        if weight is not None:
            for cart in candidates:
                if abs(cart.bullet_weight_grains - float(weight)) < 0.5:
                    name_score = _name_similarity(name, cart.name) if name and cart.name else 0.0
                    if name_score > 0.3:
                        return MatchResult(
                            matched=True,
                            entity_id=cart.id,
                            confidence=round(0.85 + name_score * 0.1, 2),
                            method="composite_key",
                            details=f"weight={weight}, name_score={name_score:.2f}",
                        )

        # Tier 3: Fuzzy name match — with weight agreement check
        if name:
            best_score = 0.0
            best_cart: Cartridge | None = None
            best_weight_agrees = False
            for cart in candidates:
                score = _name_similarity(name, cart.name)
                if score > best_score:
                    best_score = score
                    best_cart = cart
                    if weight is not None:
                        try:
                            best_weight_agrees = abs(cart.bullet_weight_grains - float(weight)) <= 1.0
                        except (ValueError, TypeError):
                            best_weight_agrees = False
                    else:
                        best_weight_agrees = False

            if best_cart and best_score > 0.5:
                confidence_factor = 0.8 if best_weight_agrees else 0.4
                return MatchResult(
                    matched=True,
                    entity_id=best_cart.id,
                    confidence=round(best_score * confidence_factor, 2),
                    method="fuzzy_name",
                    details=f"matched '{best_cart.name}' score={best_score:.2f} weight_agrees={best_weight_agrees}",
                )

        return MatchResult(matched=False, details=f"no match for cartridge '{name}'")

    def match_rifle(self, extracted: dict, manufacturer_id: str | None, chamber_id: str | None) -> MatchResult:
        """Match an extracted rifle model against existing DB rifles."""
        model_name = _get_value(extracted, "model", "")

        query = self._session.query(RifleModel)
        if manufacturer_id:
            query = query.filter(RifleModel.manufacturer_id == manufacturer_id)
        if chamber_id:
            query = query.filter(RifleModel.chamber_id == chamber_id)

        candidates = query.all()

        # Tier 2: Composite key — manufacturer + chamber + model name
        for rifle in candidates:
            name_score = _name_similarity(model_name, rifle.model)
            if name_score > 0.5:
                return MatchResult(
                    matched=True,
                    entity_id=rifle.id,
                    confidence=round(0.85 + name_score * 0.1, 2),
                    method="composite_key",
                    details=f"model_score={name_score:.2f}",
                )

        # Tier 3: Fuzzy — search all rifles by this manufacturer, with chamber agreement check
        if manufacturer_id:
            all_by_mfr = self._session.query(RifleModel).filter(RifleModel.manufacturer_id == manufacturer_id).all()
            best_score = 0.0
            best_rifle: RifleModel | None = None
            for rifle in all_by_mfr:
                score = _name_similarity(model_name, rifle.model)
                if score > best_score:
                    best_score = score
                    best_rifle = rifle

            if best_rifle and best_score > 0.5:
                chamber_agrees = chamber_id is not None and best_rifle.chamber_id == chamber_id
                confidence_factor = 0.8 if chamber_agrees else 0.4
                return MatchResult(
                    matched=True,
                    entity_id=best_rifle.id,
                    confidence=round(best_score * confidence_factor, 2),
                    method="fuzzy_name",
                    details=f"matched '{best_rifle.model}' score={best_score:.2f} chamber_agrees={chamber_agrees}",
                )

        return MatchResult(matched=False, details=f"no match for rifle '{model_name}'")

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

        # Resolve caliber / chamber
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

        # Match against existing entities
        if entity_type == "bullet":
            result.match = self.match_bullet(extracted, result.manufacturer_id, result.caliber_id)
        elif entity_type == "cartridge":
            result.match = self.match_cartridge(extracted, result.manufacturer_id, result.caliber_id)
            # Also try to resolve bullet FK for cartridges
            bullet_name = _get_value(extracted, "bullet_name")
            if bullet_name and result.manufacturer_id and result.caliber_id:
                weight = _get_value(extracted, "bullet_weight_grains")
                bullet_stub = {"name": {"value": bullet_name}, "weight_grains": {"value": weight}}
                bullet_match = self.match_bullet(bullet_stub, result.manufacturer_id, result.caliber_id)
                if bullet_match.matched:
                    result.bullet_id = bullet_match.entity_id
                else:
                    result.unresolved_refs.append(f"bullet: {bullet_name}")
        elif entity_type == "rifle":
            result.match = self.match_rifle(extracted, result.manufacturer_id, result.chamber_id)
        else:
            result.match = MatchResult(matched=False, details=f"unknown entity type: {entity_type}")
            result.warnings.append(f"Unknown entity type: {entity_type}")

        return result


def _get_value(entity: dict, field_name: str, default=None):
    """Extract the raw value from an ExtractedValue dict wrapper."""
    field_data = entity.get(field_name)
    if field_data is None:
        return default
    if isinstance(field_data, dict):
        return field_data.get("value", default)
    return field_data
