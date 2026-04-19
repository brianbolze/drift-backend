"""Deterministic name → entity_id lookup, shared by curation and the pipeline resolver.

Lookup order (per call):
  1. Exact, case-insensitive match on the model's name field.
  2. Case-insensitive match on the model's ``alt_names`` JSON column (when present).
  3. Match on the ``EntityAlias`` table for the given ``entity_type``.
  4. For calibers only, a final period-insensitive pass so ``"308 Win"`` matches
     ``".308 Winchester"`` regardless of where the canonical/alias text lives.

Fuzzy matching is layered on top of this by the pipeline resolver — this module
covers only deterministic ("the curator said this name means that entity") lookups
so curation patches and pipeline runs agree on every alias they share.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from drift.models import (
    Bullet,
    BulletProductLine,
    Caliber,
    Cartridge,
    Chamber,
    EntityAlias,
    Manufacturer,
    RifleModel,
)

# (model class, name attribute) per entity_type. Kept narrow on purpose — only
# entity types that participate in deterministic name lookups belong here.
_ENTITY_TYPE_MAP: dict[str, tuple[type, str]] = {
    "manufacturer": (Manufacturer, "name"),
    "caliber": (Caliber, "name"),
    "chamber": (Chamber, "name"),
    "bullet": (Bullet, "name"),
    "cartridge": (Cartridge, "name"),
    "bullet_product_line": (BulletProductLine, "name"),
    "rifle": (RifleModel, "model"),
}


@dataclass(frozen=True)
class LookupResult:
    """A deterministic-lookup hit.

    ``confidence`` is the canonical score the pipeline resolver should treat
    each method as worth — kept here so both callers attribute the same weight
    to a given match.
    """

    entity_id: str
    method: str  # "exact_name" | "alt_name" | "entity_alias" | "caliber_norm" | ...
    confidence: float
    matched_text: str
    canonical_name: str
    details: str = ""


def strip_trademarks(name: str) -> str:
    """Strip trademark/copyright symbols: ®, ™, ©."""
    return name.replace("\u00ae", "").replace("\u2122", "").replace("\u00a9", "")


def normalize_name(name: str) -> str:
    """Normalize a name for deterministic comparison.

    Strips trademarks, lowercases, replaces non-word punctuation with spaces
    (preserving leading periods on tokens — caliber names like ".308" stay
    distinct), collapses whitespace, and drops trailing periods on tokens
    (so "Hornady Inc." matches "Hornady Inc").
    """
    s = strip_trademarks(name).lower().strip()
    # Keep periods so caliber prefixes like ".308" survive
    s = re.sub(r"[^\w\s.]", " ", s)
    s = re.sub(r"\s+", " ", s)
    tokens = [t.rstrip(".") if not t.startswith(".") else t for t in s.split()]
    return " ".join(tokens).strip()


def normalize_caliber(name: str) -> str:
    """Caliber-specific normalization: strip leading periods so '308 Win' ↔ '.308 Win'."""
    norm = normalize_name(name)
    tokens = [t.lstrip(".") if t.startswith(".") else t for t in norm.split()]
    return " ".join(tokens)


def _scoped(stmt, model: type, manufacturer_id: str | None):
    if manufacturer_id and hasattr(model, "manufacturer_id"):
        return stmt.where(model.manufacturer_id == manufacturer_id)
    return stmt


def _exact_or_alt(candidates: Iterable, name_attr: str, target_norm: str, supports_alt: bool) -> LookupResult | None:
    """Tier 1+2: exact canonical match, then alt_names match. One pass each."""
    for candidate in candidates:
        canonical = getattr(candidate, name_attr)
        if canonical and normalize_name(canonical) == target_norm:
            return LookupResult(
                entity_id=candidate.id,
                method="exact_name",
                confidence=1.0,
                matched_text=canonical,
                canonical_name=canonical,
            )
    if not supports_alt:
        return None
    for candidate in candidates:
        for alt in candidate.alt_names or []:
            if alt and normalize_name(alt) == target_norm:
                canonical = getattr(candidate, name_attr)
                return LookupResult(
                    entity_id=candidate.id,
                    method="alt_name",
                    confidence=0.95,
                    matched_text=alt,
                    canonical_name=canonical,
                    details=f"alt_name {alt!r} on {canonical!r}",
                )
    return None


def _entity_alias_lookup(
    session: Session,
    model: type,
    entity_type: str,
    name_attr: str,
    target_norm: str,
    manufacturer_id: str | None,
) -> LookupResult | None:
    """Tier 3: EntityAlias table lookup, scoped by manufacturer_id when applicable."""
    has_mfr = hasattr(model, "manufacturer_id")
    for alias in session.scalars(select(EntityAlias).where(EntityAlias.entity_type == entity_type)):
        if normalize_name(alias.alias) != target_norm:
            continue
        candidate = session.get(model, alias.entity_id)
        if candidate is None:
            continue
        if manufacturer_id and has_mfr and candidate.manufacturer_id != manufacturer_id:
            continue
        canonical = getattr(candidate, name_attr)
        return LookupResult(
            entity_id=candidate.id,
            method="entity_alias",
            confidence=0.9,
            matched_text=alias.alias,
            canonical_name=canonical,
            details=f"alias {alias.alias!r} → {canonical!r}",
        )
    return None


def _caliber_period_insensitive(session: Session, candidates: Iterable[Caliber], name: str) -> LookupResult | None:
    """Tier 4: period-insensitive caliber match across name, alt_names, and aliases."""
    target_cal = normalize_caliber(name)
    if not target_cal:
        return None
    for cal in candidates:
        if normalize_caliber(cal.name) == target_cal:
            return LookupResult(
                entity_id=cal.id,
                method="caliber_norm",
                confidence=0.95,
                matched_text=cal.name,
                canonical_name=cal.name,
                details=f"period-insensitive: {name!r} → {cal.name!r}",
            )
        for alt in cal.alt_names or []:
            if alt and normalize_caliber(alt) == target_cal:
                return LookupResult(
                    entity_id=cal.id,
                    method="caliber_norm_alt",
                    confidence=0.9,
                    matched_text=alt,
                    canonical_name=cal.name,
                    details=f"period-insensitive alt: {name!r} → {alt!r} (via {cal.name!r})",
                )
    for alias in session.scalars(select(EntityAlias).where(EntityAlias.entity_type == "caliber")):
        if normalize_caliber(alias.alias) != target_cal:
            continue
        cal = session.get(Caliber, alias.entity_id)
        if cal is None:
            continue
        return LookupResult(
            entity_id=cal.id,
            method="caliber_norm_alias",
            confidence=0.9,
            matched_text=alias.alias,
            canonical_name=cal.name,
            details=f"period-insensitive alias: {alias.alias!r} → {cal.name!r}",
        )
    return None


def lookup_entity(
    session: Session,
    entity_type: str,
    name: str,
    *,
    manufacturer_id: str | None = None,
) -> LookupResult | None:
    """Resolve ``name`` to an entity via exact + alias matching.

    Returns the first hit across the four tiers documented at the module level,
    or ``None`` if nothing matches. ``manufacturer_id`` scopes the lookup for
    entities that have a ``manufacturer_id`` column (bullets, cartridges,
    bullet_product_lines) and is otherwise ignored.

    Raises ``ValueError`` for unknown ``entity_type``.
    """
    if entity_type not in _ENTITY_TYPE_MAP:
        raise ValueError(f"Unknown entity_type: {entity_type!r}")

    model, name_attr = _ENTITY_TYPE_MAP[entity_type]
    target_norm = normalize_name(name)
    if not target_norm:
        return None

    # Single scan over candidates feeds tiers 1, 2, and (for calibers) 4.
    candidates = list(session.scalars(_scoped(select(model), model, manufacturer_id)))

    hit = _exact_or_alt(candidates, name_attr, target_norm, hasattr(model, "alt_names"))
    if hit is not None:
        return hit

    hit = _entity_alias_lookup(session, model, entity_type, name_attr, target_norm, manufacturer_id)
    if hit is not None:
        return hit

    if entity_type == "caliber":
        return _caliber_period_insensitive(session, candidates, name)

    return None
