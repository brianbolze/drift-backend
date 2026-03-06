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

from sqlalchemy.exc import DataError, IntegrityError

from drift.database import get_session_factory
from drift.models.bullet import Bullet, BulletBCSource
from drift.models.cartridge import Cartridge
from drift.models.rifle_model import RifleModel
from drift.pipeline.config import EXTRACTED_DIR, REJECTED_CALIBERS_PATH, STORE_REPORT_PATH
from drift.pipeline.resolution.resolver import EntityResolver, _get_value

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Matches below this confidence are flagged for review instead of auto-skipped
MATCH_CONFIDENCE_THRESHOLD = 0.7

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

    stats = {
        "bullet": {"created": 0, "matched": 0, "updated": 0, "flagged": 0, "rejected": 0, "skipped_locked": 0},
        "cartridge": {"created": 0, "matched": 0, "updated": 0, "flagged": 0, "rejected": 0, "skipped_locked": 0},
        "rifle": {"created": 0, "matched": 0, "updated": 0, "flagged": 0, "rejected": 0, "skipped_locked": 0},
    }
    report_entries: list[dict] = []

    entries = extracted_files[: args.limit] if args.limit > 0 else extracted_files

    session = None
    try:
        session = SessionFactory()
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
                resolution = resolver.resolve(entity, entity_type)

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
                    "warnings": resolution.warnings,
                    "action": "",
                }

                # Check if entity references a rejected caliber (pistol, shotgun, etc.)
                if _has_rejected_caliber(resolution, rejected_calibers):
                    entry["action"] = "rejected"
                    stats[entity_type]["rejected"] += 1
                    logger.info("  [%d] REJECTED (excluded caliber): %s", j + 1, name)
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
                        # Also create BulletBCSource rows for matched cartridges with BC data
                        if args.commit and resolution.bullet_id:
                            _add_cartridge_bc_sources(session, resolution.bullet_id, bc_sources, entity, url)
                elif resolution.match.matched:
                    # Low-confidence match — flag for review instead of auto-skipping
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
                    stats[entity_type]["created"] += 1

                    if args.commit:
                        savepoint = session.begin_nested()
                        try:
                            if entity_type == "bullet":
                                if resolution.bullet_diameter_inches is None:
                                    raise ValueError(f"Cannot create bullet '{name}': bullet_diameter_inches is None")
                                obj = _make_bullet(
                                    entity,
                                    resolution.manufacturer_id,
                                    resolution.bullet_diameter_inches,
                                    url,
                                    data_source=data_source,
                                )
                                session.add(obj)
                                # Only attach BC sources that belong to this bullet
                                bullet_name = _get_value(entity, "name", "")
                                bullet_bc_sources = [
                                    bc for bc in bc_sources if bc.get("bullet_name", "") == bullet_name
                                ]
                                for bc_obj in _make_bc_sources(obj.id, bullet_bc_sources, url):
                                    session.add(bc_obj)
                                entry["created_id"] = obj.id
                            elif entity_type == "cartridge":
                                obj = _make_cartridge(
                                    entity,
                                    resolution.manufacturer_id,
                                    resolution.caliber_id,
                                    resolution.bullet_id,  # None if unresolved (not empty string)
                                    url,
                                    data_source=data_source,
                                )
                                session.add(obj)
                                entry["created_id"] = obj.id
                                _add_cartridge_bc_sources(session, resolution.bullet_id, bc_sources, entity, url)
                            elif entity_type == "rifle":
                                obj = _make_rifle(
                                    entity,
                                    resolution.manufacturer_id,
                                    resolution.chamber_id,
                                    url,
                                    data_source=data_source,
                                )
                                session.add(obj)
                                entry["created_id"] = obj.id
                            savepoint.commit()
                        except (IntegrityError, DataError) as e:
                            savepoint.rollback()
                            logger.exception("  [%d] CREATE FAILED: %s — %s", j + 1, name, e)
                            entry["action"] = "create_failed"
                            entry["error"] = str(e)
                            stats[entity_type]["flagged"] += 1
                    else:
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

    # Write report
    report = {
        "mode": mode,
        "stats": stats,
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
        print(f"  {etype}: {', '.join(parts)}")
    print(f"\nReport written to: {STORE_REPORT_PATH}")


if __name__ == "__main__":
    main()
