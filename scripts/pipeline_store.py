"""Store extracted and resolved entities into the database.

Reads extraction results from data/pipeline/extracted/, runs EntityResolver
to link to existing entities and detect duplicates, then creates new DB records
for unmatched entities.

Dry-run mode (default): resolves and reports without writing to DB.
Commit mode (--commit): actually writes to the database.

Usage:
    python scripts/pipeline_store.py                  # dry-run
    python scripts/pipeline_store.py --commit         # write to DB
    python scripts/pipeline_store.py --limit 5        # process first 5
"""

from __future__ import annotations

import argparse
import json
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.exc import DataError, IntegrityError

from drift.database import get_session_factory
from drift.models.bullet import Bullet, BulletBCSource
from drift.models.caliber import Caliber
from drift.models.cartridge import Cartridge
from drift.models.entity_alias import EntityAlias
from drift.models.rifle_model import RifleModel
from drift.pipeline.config import EXTRACTED_DIR, REJECTED_CALIBERS_PATH, STORE_REPORT_PATH
from drift.pipeline.normalization import normalize_entity
from drift.pipeline.resolution.resolver import EntityResolver, _get_value
from drift.resolution.aliases import normalize_name

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Matches below this confidence are flagged for review instead of auto-skipped
MATCH_CONFIDENCE_THRESHOLD = 0.7

# Below this confidence, a weight-mismatched bullet match is treated as "no match"
# and the entity is auto-created instead of flagged. This handles the common case
# where a new weight variant (e.g. 200gr ELD-X) fuzzy-matches to an existing variant
# (e.g. 178gr ELD-X) at low confidence because the correct record doesn't exist yet.
AUTO_CREATE_CONFIDENCE_CEILING = 0.5

# Winning match methods that are non-deterministic (use similarity thresholds on names).
# A matched_existing entry decided by one of these is a candidate for EntityAlias
# promotion so the next run can hit the deterministic lookup path.
_FUZZY_MATCH_METHODS = frozenset({"composite_key", "fuzzy_name"})

# A successful match below this confidence is counted as low-confidence in the
# end-of-run method breakdown. Independent of MATCH_CONFIDENCE_THRESHOLD so the
# reporting threshold can be moved without affecting auto-match gating.
_LOW_CONFIDENCE_REPORT_THRESHOLD = 0.5

# Valid data_source values for provenance tracking
_VALID_DATA_SOURCES = {"pipeline", "cowork", "manual"}

# ORM model class for each entity type (used for locked-record checks)
_ENTITY_MODEL = {
    "bullet": Bullet,
    "cartridge": Cartridge,
    "rifle": RifleModel,
}


def _get_data_source(extraction_data: dict) -> str:
    """Read data_source from extraction metadata, defaulting to 'pipeline'."""
    ds = extraction_data.get("data_source", "pipeline")
    return ds if ds in _VALID_DATA_SOURCES else "pipeline"


def _load_rejected_calibers() -> set[str]:
    """Load caliber names that should be auto-rejected (pistol, shotgun, etc.).

    Returns a set of lowercased caliber names from data/pipeline/rejected_calibers.json.
    If the file doesn't exist, returns an empty set (no rejections).
    """
    if not REJECTED_CALIBERS_PATH.exists():
        return set()
    data = json.loads(REJECTED_CALIBERS_PATH.read_text(encoding="utf-8"))
    return {name.lower().strip() for name in data.get("calibers", [])}


def _build_alias_suggestion(
    session,
    entity_type: str,
    match,
    existing,
    extracted_name: str,
) -> dict | None:
    """Return a candidate EntityAlias for a fuzzy matched_existing entry, or None.

    Skips deterministic matches (SKU, product_line), cases where the extracted
    name is identical to the canonical name after normalization, and aliases
    that already exist in the EntityAlias table.
    """
    if match.method not in _FUZZY_MATCH_METHODS or existing is None or not match.entity_id:
        return None
    canonical = getattr(existing, "name", None) or getattr(existing, "model", None)
    if not canonical or not extracted_name:
        return None
    target_norm = normalize_name(extracted_name)
    if not target_norm or target_norm == normalize_name(canonical):
        return None
    existing_aliases = session.scalars(
        select(EntityAlias).where(
            EntityAlias.entity_type == entity_type,
            EntityAlias.entity_id == match.entity_id,
        )
    )
    for alias in existing_aliases:
        if normalize_name(alias.alias) == target_norm:
            return None
    return {
        "entity_type": entity_type,
        "entity_id": match.entity_id,
        "canonical_name": canonical,
        "alias": extracted_name,
        "method": match.method,
        "confidence": round(match.confidence, 3),
    }


def _record_method_telemetry(stats: dict, entity_type: str, match) -> None:
    """Accumulate winning-method counts + confidence distribution per entity type.

    Only successful matches (match.matched=True) are recorded. A match is counted
    once per resolution, under its winning tier; tiers attempted but not selected
    are already visible on each entry via ``methods_tried``.
    """
    if not match.matched:
        return
    methods = stats[entity_type].setdefault("methods", {})
    method_name = match.method or "unknown"
    bucket = methods.setdefault(method_name, {"count": 0, "confidence_sum": 0.0, "low_confidence": 0})
    bucket["count"] += 1
    bucket["confidence_sum"] += match.confidence
    if match.confidence < _LOW_CONFIDENCE_REPORT_THRESHOLD:
        bucket["low_confidence"] += 1


def _print_method_breakdown(stats: dict) -> None:
    """Print per-entity-type method usage (share %, avg confidence, low-conf count)."""
    any_printed = False
    for entity_type in ("bullet", "cartridge", "rifle"):
        methods = stats.get(entity_type, {}).get("methods", {})
        if not methods:
            continue
        if not any_printed:
            print("\nMatch method breakdown:")
            any_printed = True
        total = sum(bucket["count"] for bucket in methods.values())
        print(f"  {entity_type} ({total} matched):")
        for method_name, bucket in sorted(methods.items(), key=lambda kv: kv[1]["count"], reverse=True):
            share = 100.0 * bucket["count"] / total
            avg_conf = bucket["confidence_sum"] / bucket["count"]
            line = f"    {method_name:<14} {bucket['count']:>4} ({share:5.1f}%), avg conf {avg_conf:.2f}"
            if bucket["low_confidence"]:
                line += f", {bucket['low_confidence']} < {_LOW_CONFIDENCE_REPORT_THRESHOLD:.1f}"
            print(line)


def _has_rejected_caliber(resolution, rejected_calibers: set[str]) -> bool:
    """Check if an entity's unresolved refs include a rejected caliber."""
    if not rejected_calibers:
        return False
    for ref in resolution.unresolved_refs:
        if ref.startswith("caliber:"):
            cal_name = ref.split(":", 1)[1].strip().lower()
            if cal_name in rejected_calibers:
                return True
    return False


def _bc_source_exists(session, bullet_id: str, bc_type: str, bc_value: float, source: str) -> bool:
    """Check if a BulletBCSource row already exists with these values (epsilon tolerance on bc_value)."""
    eps = 1e-9
    return (
        session.scalars(
            select(BulletBCSource).where(
                BulletBCSource.bullet_id == bullet_id,
                BulletBCSource.bc_type == bc_type,
                BulletBCSource.bc_value.between(bc_value - eps, bc_value + eps),
                BulletBCSource.source == source,
            )
        ).first()
        is not None
    )


def _make_bullet(
    entity: dict, manufacturer_id: str, bullet_diameter_inches: float, source_url: str, data_source: str = "pipeline"
) -> Bullet:
    """Create a Bullet ORM instance from an extracted entity dict."""
    return Bullet(
        id=str(uuid.uuid4()),
        manufacturer_id=manufacturer_id,
        bullet_diameter_inches=bullet_diameter_inches,
        name=_get_value(entity, "name", ""),
        sku=_get_value(entity, "sku"),
        weight_grains=_safe_float(_get_value(entity, "weight_grains")) or 0.0,
        bc_g1_published=_safe_float(_get_value(entity, "bc_g1")),
        bc_g7_published=_safe_float(_get_value(entity, "bc_g7")),
        length_inches=_safe_float(_get_value(entity, "length_inches")),
        sectional_density=_safe_float(_get_value(entity, "sectional_density")),
        base_type=_get_value(entity, "base_type"),
        tip_type=_get_value(entity, "tip_type"),
        type_tags=_get_value(entity, "type_tags"),
        used_for=_get_value(entity, "used_for"),
        product_line=_get_value(entity, "product_line"),
        source_url=source_url,
        extraction_confidence=_avg_confidence(entity),
        data_source=data_source,
    )


def _make_cartridge(
    entity: dict,
    manufacturer_id: str,
    caliber_id: str,
    bullet_id: str | None,
    source_url: str,
    data_source: str = "pipeline",
    bullet_match_confidence: float | None = None,
    bullet_match_method: str | None = None,
) -> Cartridge:
    """Create a Cartridge ORM instance from an extracted entity dict."""
    return Cartridge(
        id=str(uuid.uuid4()),
        manufacturer_id=manufacturer_id,
        caliber_id=caliber_id,
        bullet_id=bullet_id,
        name=_get_value(entity, "name", ""),
        sku=_get_value(entity, "sku"),
        bullet_weight_grains=_safe_float(_get_value(entity, "bullet_weight_grains")) or 0.0,
        bc_g1=_safe_float(_get_value(entity, "bc_g1")),
        bc_g7=_safe_float(_get_value(entity, "bc_g7")),
        bullet_length_inches=_safe_float(_get_value(entity, "bullet_length_inches")),
        muzzle_velocity_fps=_safe_int(_get_value(entity, "muzzle_velocity_fps")) or 0,
        test_barrel_length_inches=_safe_float(_get_value(entity, "test_barrel_length_inches")),
        round_count=_safe_int(_get_value(entity, "round_count")),
        product_line=_get_value(entity, "product_line"),
        source_url=source_url,
        extraction_confidence=_avg_confidence(entity),
        data_source=data_source,
        bullet_match_confidence=bullet_match_confidence,
        bullet_match_method=bullet_match_method,
    )


def _make_rifle(
    entity: dict, manufacturer_id: str, chamber_id: str, source_url: str, data_source: str = "pipeline"
) -> RifleModel:
    """Create a RifleModel ORM instance from an extracted entity dict."""
    return RifleModel(
        id=str(uuid.uuid4()),
        manufacturer_id=manufacturer_id,
        chamber_id=chamber_id,
        model=_get_value(entity, "model", ""),
        barrel_length_inches=_safe_float(_get_value(entity, "barrel_length_inches")),
        twist_rate=_get_value(entity, "twist_rate"),
        weight_lbs=_safe_float(_get_value(entity, "weight_lbs")),
        barrel_material=_get_value(entity, "barrel_material"),
        barrel_finish=_get_value(entity, "barrel_finish"),
        model_family=_get_value(entity, "model_family"),
        source_url=source_url,
        data_source=data_source,
    )


def _make_bc_sources(bullet_id: str, bc_sources: list[dict], source_url: str) -> list[BulletBCSource]:
    """Create BulletBCSource ORM instances from extracted BC source dicts."""
    results = []
    for bc in bc_sources:
        bc_val = _safe_float(bc.get("bc_value"))
        if bc_val is None:
            logger.warning(
                "Skipping BC source with unparseable bc_value=%r for bullet %s", bc.get("bc_value"), bullet_id
            )
            continue
        results.append(
            BulletBCSource(
                id=str(uuid.uuid4()),
                bullet_id=bullet_id,
                bc_type=bc.get("bc_type", ""),
                bc_value=bc_val,
                source=bc.get("source", "manufacturer"),
                source_url=source_url,
                source_methodology=bc.get("source_methodology"),
            )
        )
    return results


def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        logger.debug("Could not convert %r to float", val)
        return None


def _add_cartridge_bc_sources(session, bullet_id: str, bc_sources: list[dict], entity: dict, url: str) -> None:
    """Create BulletBCSource rows for cartridge-sourced BC data, if any."""
    if not bullet_id:
        return
    cart_bc_sources = [bc for bc in bc_sources if bc.get("source") == "cartridge_page"]
    if not cart_bc_sources:
        return
    cart_name = _get_value(entity, "name", "")
    cart_sku = _get_value(entity, "sku", "N/A")
    for bc_obj in _make_bc_sources(bullet_id, cart_bc_sources, url):
        if _bc_source_exists(session, bc_obj.bullet_id, bc_obj.bc_type, bc_obj.bc_value, bc_obj.source):
            continue
        bc_obj.notes = f"from cartridge: {cart_name} (SKU: {cart_sku})"
        session.add(bc_obj)


def _safe_int(val) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        logger.debug("Could not convert %r to int", val)
        return None


def _avg_confidence(entity: dict) -> float:
    """Average the confidence scores across all ExtractedValue fields."""
    scores = []
    for v in entity.values():
        if isinstance(v, dict) and "confidence" in v:
            scores.append(v["confidence"])
    return round(sum(scores) / len(scores), 3) if scores else 0.0


def _should_auto_create_weight_variant(
    entity: dict,
    entity_type: str,
    resolution,
    session,
) -> bool:
    """Decide if a low-confidence match is a new weight variant that should be auto-created.

    Returns True when ALL of these hold:
    - Match confidence is below AUTO_CREATE_CONFIDENCE_CEILING
    - The entity has all required resolved references for creation
    - The extracted weight is present and positive
    - The matched entity's weight disagrees with the extracted weight

    This catches the common case where a new weight variant (e.g. Barnes 30cal 130gr TTSX)
    fuzzy-matches to a different weight (e.g. Barnes 30cal 110gr TTSX) because the correct
    record doesn't exist yet.
    """
    if resolution.match.confidence >= AUTO_CREATE_CONFIDENCE_CEILING:
        return False

    if entity_type == "bullet":
        if not resolution.manufacturer_id or resolution.bullet_diameter_inches is None:
            return False
        weight_field = "weight_grains"
        model_cls = Bullet
        tolerance = 1.0
    elif entity_type == "cartridge":
        if not resolution.manufacturer_id or not resolution.caliber_id or not resolution.bullet_id:
            return False
        weight_field = "bullet_weight_grains"
        model_cls = Cartridge
        tolerance = 2.0
    else:
        return False

    extracted_weight = _safe_float(_get_value(entity, weight_field))
    if not extracted_weight or extracted_weight <= 0:
        return False

    matched = session.get(model_cls, resolution.match.entity_id) if resolution.match.entity_id else None
    if not matched:
        if resolution.match.entity_id:
            logger.warning(
                "Match target %s %s not found in DB — treating as unmatched", entity_type, resolution.match.entity_id
            )
        return True  # No match target — safe to create

    matched_weight = getattr(matched, weight_field)
    return abs(matched_weight - extracted_weight) > tolerance


def _create_entity(
    entity_type: str,
    entity: dict,
    resolution,
    session,
    url: str,
    data_source: str,
    bc_sources: list[dict],
) -> str:
    """Create an entity ORM object, add it to the session, and return its ID.

    Handles bullet (with BC sources), cartridge (with cartridge BC sources),
    and rifle entity types. Raises ValueError if required fields are missing.
    """
    if entity_type == "bullet":
        if resolution.bullet_diameter_inches is None:
            name = _get_value(entity, "name", "")
            raise ValueError(f"Cannot create bullet {name!r}: bullet_diameter_inches is None")
        obj = _make_bullet(entity, resolution.manufacturer_id, resolution.bullet_diameter_inches, url, data_source)
        session.add(obj)
        bullet_name = _get_value(entity, "name", "")
        bullet_bc_sources = [bc for bc in bc_sources if bc.get("bullet_name", "") == bullet_name]
        for bc_obj in _make_bc_sources(obj.id, bullet_bc_sources, url):
            if not _bc_source_exists(session, bc_obj.bullet_id, bc_obj.bc_type, bc_obj.bc_value, bc_obj.source):
                session.add(bc_obj)
    elif entity_type == "cartridge":
        obj = _make_cartridge(
            entity,
            resolution.manufacturer_id,
            resolution.caliber_id,
            resolution.bullet_id,
            url,
            data_source,
            bullet_match_confidence=resolution.bullet_match_confidence,
            bullet_match_method=resolution.bullet_match_method,
        )
        session.add(obj)
        _add_cartridge_bc_sources(session, resolution.bullet_id, bc_sources, entity, url)
    elif entity_type == "rifle":
        obj = _make_rifle(entity, resolution.manufacturer_id, resolution.chamber_id, url, data_source)
        session.add(obj)
    else:
        raise ValueError(f"Unknown entity type: {entity_type!r}")
    return obj.id


def main() -> None:  # noqa: C901
    parser = argparse.ArgumentParser(description="Store extracted entities in the database")
    parser.add_argument("--commit", action="store_true", help="Actually write to DB (default is dry-run)")
    parser.add_argument("--limit", type=int, default=0, help="Max extraction files to process (0 = all)")
    args = parser.parse_args()

    mode = "COMMIT" if args.commit else "DRY-RUN"
    logger.info("Running in %s mode", mode)

    extracted_files = sorted(EXTRACTED_DIR.glob("*.json"))
    if not extracted_files:
        raise SystemExit(f"No extracted files found in {EXTRACTED_DIR}\nRun pipeline_extract.py first.")

    SessionFactory = get_session_factory()

    rejected_calibers = _load_rejected_calibers()
    if rejected_calibers:
        logger.info("Loaded %d rejected calibers", len(rejected_calibers))

    valid_bullet_diameters: set[float] = set()

    stats: dict = {
        "bullet": {
            "created": 0,
            "matched": 0,
            "updated": 0,
            "flagged": 0,
            "rejected": 0,
            "skipped_locked": 0,
            "alias_suggestions": 0,
            "methods": {},
        },
        "cartridge": {
            "created": 0,
            "matched": 0,
            "updated": 0,
            "flagged": 0,
            "rejected": 0,
            "skipped_locked": 0,
            "alias_suggestions": 0,
            "methods": {},
        },
        "rifle": {
            "created": 0,
            "matched": 0,
            "updated": 0,
            "flagged": 0,
            "rejected": 0,
            "skipped_locked": 0,
            "alias_suggestions": 0,
            "methods": {},
        },
    }
    report_entries: list[dict] = []

    entries = extracted_files[: args.limit] if args.limit > 0 else extracted_files

    session = None
    try:
        session = SessionFactory()
        valid_bullet_diameters = set(session.scalars(select(Caliber.bullet_diameter_inches).distinct()))
        logger.info("Loaded %d valid bullet diameters from caliber table", len(valid_bullet_diameters))
        resolver = EntityResolver(session)
        for i, extracted_path in enumerate(entries):
            uhash = extracted_path.stem
            extraction_data = json.loads(extracted_path.read_text(encoding="utf-8"))

            url = extraction_data.get("url", uhash)
            entity_type = extraction_data.get("entity_type", "")
            entities = extraction_data.get("entities", [])
            bc_sources = extraction_data.get("bc_sources", [])
            data_source = _get_data_source(extraction_data)

            if entity_type not in stats:
                logger.warning("[%d/%d] SKIP (unknown type '%s'): %s", i + 1, len(entries), entity_type, url)
                continue

            logger.info("[%d/%d] STORE (%s, %d entities): %s", i + 1, len(entries), entity_type, len(entities), url)

            for j, entity in enumerate(entities):
                name = _get_value(entity, "name") or _get_value(entity, "model") or f"entity[{j}]"

                # Normalize BEFORE resolution so unit-confusion errors (grams vs grains,
                # m/s vs fps, mm vs inches) don't poison entity matching downstream.
                norm = normalize_entity(entity, entity_type)
                entity = norm.entity

                if norm.rejected:
                    entry = {
                        "url": url,
                        "url_hash": uhash,
                        "entity_type": entity_type,
                        "entity_name": name,
                        "matched": False,
                        "match_method": "",
                        "match_confidence": 0.0,
                        "match_entity_id": None,
                        "manufacturer_id": None,
                        "caliber_id": None,
                        "chamber_id": None,
                        "bullet_id": None,
                        "bullet_diameter_inches": None,
                        "unresolved_refs": [],
                        "warnings": list(norm.warnings),
                        "normalization_events": [e.as_dict() for e in norm.events],
                        "action": "rejected",
                        "rejection_reason": norm.rejection_reason,
                    }
                    stats[entity_type]["rejected"] += 1
                    logger.warning("  [%d] REJECTED (normalization): %s — %s", j + 1, name, norm.rejection_reason)
                    report_entries.append(entry)
                    continue

                resolution = resolver.resolve(entity, entity_type)
                _record_method_telemetry(stats, entity_type, resolution.match)

                entry = {
                    "url": url,
                    "url_hash": uhash,
                    "entity_type": entity_type,
                    "entity_name": name,
                    "matched": resolution.match.matched,
                    "match_method": resolution.match.method,
                    "match_confidence": resolution.match.confidence,
                    "match_entity_id": resolution.match.entity_id,
                    "manufacturer_id": resolution.manufacturer_id,
                    "caliber_id": resolution.caliber_id,
                    "chamber_id": resolution.chamber_id,
                    "bullet_id": resolution.bullet_id,
                    "bullet_diameter_inches": resolution.bullet_diameter_inches,
                    "unresolved_refs": resolution.unresolved_refs,
                    "warnings": list(norm.warnings) + list(resolution.warnings),
                    "action": "",
                }
                if norm.events:
                    entry["normalization_events"] = [e.as_dict() for e in norm.events]
                    for warning in norm.warnings:
                        logger.info("  [%d] NORMALIZED: %s", j + 1, warning)

                # Check if entity references a rejected caliber (pistol, shotgun, etc.)
                if _has_rejected_caliber(resolution, rejected_calibers):
                    entry["action"] = "rejected"
                    stats[entity_type]["rejected"] += 1
                    logger.info("  [%d] REJECTED (excluded caliber): %s", j + 1, name)
                    report_entries.append(entry)
                    continue

                # Check if bullet diameter matches any caliber in the DB
                if (
                    entity_type == "bullet"
                    and resolution.bullet_diameter_inches is not None
                    and resolution.bullet_diameter_inches not in valid_bullet_diameters
                ):
                    entry["action"] = "rejected"
                    stats[entity_type]["rejected"] += 1
                    logger.info(
                        "  [%d] REJECTED (orphan diameter %.4f): %s",
                        j + 1,
                        resolution.bullet_diameter_inches,
                        name,
                    )
                    report_entries.append(entry)
                    continue

                if resolution.match.matched and resolution.match.confidence >= MATCH_CONFIDENCE_THRESHOLD:
                    # Check if the existing record is locked (manually curated)
                    model_cls = _ENTITY_MODEL.get(entity_type)
                    existing = session.get(model_cls, resolution.match.entity_id) if model_cls else None
                    if existing and getattr(existing, "is_locked", False):
                        entry["action"] = "skipped_locked"
                        stats[entity_type]["skipped_locked"] += 1
                        logger.info("  [%d] SKIPPED (locked): %s → %s", j + 1, name, resolution.match.entity_id)
                        report_entries.append(entry)
                        continue

                    entry["action"] = "matched_existing"
                    stats[entity_type]["matched"] += 1
                    logger.info(
                        "  [%d] MATCHED: %s → %s (%.0f%%, %s)",
                        j + 1,
                        name,
                        resolution.match.entity_id,
                        resolution.match.confidence * 100,
                        resolution.match.method,
                    )

                    suggestion = _build_alias_suggestion(session, entity_type, resolution.match, existing, name)
                    if suggestion is not None:
                        entry["alias_suggestion"] = suggestion
                        stats[entity_type]["alias_suggestions"] = stats[entity_type].get("alias_suggestions", 0) + 1

                    # Check if FK references should be updated on the existing entity.
                    # This allows re-runs with improved resolvers to fix previously committed
                    # bad matches (e.g. wrong bullet_id assigned before abbreviation expansion).
                    if entity_type == "cartridge" and resolution.match.entity_id:
                        existing_cart = existing or session.get(Cartridge, resolution.match.entity_id)
                        if existing_cart and resolution.bullet_id and existing_cart.bullet_id != resolution.bullet_id:
                            entry["action"] = "matched_updated"
                            entry["old_bullet_id"] = existing_cart.bullet_id
                            stats[entity_type]["updated"] = stats[entity_type].get("updated", 0) + 1
                            stats[entity_type]["matched"] -= 1
                            logger.info(
                                "  [%d] UPDATED bullet_id: %s → %s",
                                j + 1,
                                existing_cart.bullet_id[:8] if existing_cart.bullet_id else "None",
                                resolution.bullet_id[:8],
                            )
                            if args.commit:
                                existing_cart.bullet_id = resolution.bullet_id
                                existing_cart.bullet_match_confidence = resolution.bullet_match_confidence
                                existing_cart.bullet_match_method = resolution.bullet_match_method
                        elif existing_cart and not existing_cart.bullet_id and resolution.bullet_id:
                            entry["action"] = "matched_updated"
                            entry["old_bullet_id"] = None
                            stats[entity_type]["updated"] = stats[entity_type].get("updated", 0) + 1
                            stats[entity_type]["matched"] -= 1
                            logger.info(
                                "  [%d] UPDATED bullet_id: None → %s",
                                j + 1,
                                resolution.bullet_id[:8],
                            )
                            if args.commit:
                                existing_cart.bullet_id = resolution.bullet_id
                                existing_cart.bullet_match_confidence = resolution.bullet_match_confidence
                                existing_cart.bullet_match_method = resolution.bullet_match_method
                        # Also create BulletBCSource rows for matched cartridges with BC data
                        if args.commit and resolution.bullet_id:
                            _add_cartridge_bc_sources(session, resolution.bullet_id, bc_sources, entity, url)
                elif resolution.match.matched:
                    # Low-confidence match — check if this is a new weight variant that
                    # should be auto-created rather than flagged for manual review.
                    if _should_auto_create_weight_variant(entity, entity_type, resolution, session):
                        entry["action"] = "created"
                        entry["auto_create_reason"] = "weight_mismatch_low_confidence"
                        logger.info(
                            "  [%d] AUTO-CREATE (weight mismatch, conf=%.0f%%): %s",
                            j + 1,
                            resolution.match.confidence * 100,
                            name,
                        )
                    else:
                        # Genuine low-confidence match — flag for review
                        entry["action"] = "flagged_low_confidence"
                        entry["suggested_match"] = resolution.match.entity_id
                        stats[entity_type]["flagged"] += 1
                        logger.warning(
                            "  [%d] FLAGGED (low confidence %.0f%%): %s → %s (%s)",
                            j + 1,
                            resolution.match.confidence * 100,
                            name,
                            resolution.match.entity_id,
                            resolution.match.details,
                        )
                elif resolution.unresolved_refs:
                    entry["action"] = "flagged_unresolved"
                    stats[entity_type]["flagged"] += 1
                    logger.warning("  [%d] FLAGGED (unresolved refs): %s — %s", j + 1, name, resolution.unresolved_refs)
                elif entity_type == "cartridge" and resolution.bullet_id is None:
                    entry["action"] = "flagged_unresolved"
                    stats[entity_type]["flagged"] += 1
                    logger.warning("  [%d] FLAGGED (no bullet_id): %s", j + 1, name)
                else:
                    # New entity — create it
                    entry["action"] = "created"

                # Commit path for all "created" actions (both auto-create and new entity)
                if entry["action"] == "created":
                    if args.commit:
                        savepoint = session.begin_nested()
                        try:
                            entry["created_id"] = _create_entity(
                                entity_type, entity, resolution, session, url, data_source, bc_sources
                            )
                            savepoint.commit()
                            stats[entity_type]["created"] += 1
                        except (IntegrityError, DataError, ValueError) as e:
                            savepoint.rollback()
                            logger.exception("  [%d] CREATE FAILED: %s — %s", j + 1, name, e)
                            entry["action"] = "create_failed"
                            entry["error"] = str(e)
                            stats[entity_type]["flagged"] += 1
                    else:
                        stats[entity_type]["created"] += 1
                        if "auto_create_reason" not in entry:
                            logger.info("  [%d] WOULD CREATE: %s", j + 1, name)

                report_entries.append(entry)

        if args.commit:
            session.commit()
            logger.info("Committed to database")
        else:
            session.rollback()
            logger.info("Dry-run complete — no changes written")

    except Exception:
        if session is not None:
            session.rollback()
        raise
    finally:
        if session is not None:
            session.close()

    # Collect alias suggestions into a top-level list for easy curator scanning
    alias_suggestions = [e["alias_suggestion"] for e in report_entries if "alias_suggestion" in e]

    # Write report
    report = {
        "mode": mode,
        "stats": stats,
        "alias_suggestions": alias_suggestions,
        "entries": report_entries,
    }
    STORE_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    STORE_REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print()
    print(f"Store report ({mode}):")
    for etype, counts in stats.items():
        updated = counts.get("updated", 0)
        rejected = counts.get("rejected", 0)
        locked = counts.get("skipped_locked", 0)
        suggested = counts.get("alias_suggestions", 0)
        parts = [
            f"{counts['created']} created",
            f"{counts['matched']} matched",
        ]
        if updated:
            parts.append(f"{updated} updated")
        parts.append(f"{counts['flagged']} flagged")
        if rejected:
            parts.append(f"{rejected} rejected")
        if locked:
            parts.append(f"{locked} skipped (locked)")
        if suggested:
            parts.append(f"{suggested} alias suggestions")
        print(f"  {etype}: {', '.join(parts)}")
    _print_method_breakdown(stats)
    print(f"\nReport written to: {STORE_REPORT_PATH}")


if __name__ == "__main__":
    main()
