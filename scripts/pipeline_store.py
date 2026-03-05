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

from drift.database import get_session_factory
from drift.models.bullet import Bullet, BulletBCSource
from drift.models.cartridge import Cartridge
from drift.models.rifle_model import RifleModel
from drift.pipeline.config import EXTRACTED_DIR, STORE_REPORT_PATH
from drift.pipeline.resolution.resolver import EntityResolver, _get_value

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _make_bullet(entity: dict, manufacturer_id: str, caliber_id: str, source_url: str) -> Bullet:
    """Create a Bullet ORM instance from an extracted entity dict."""
    return Bullet(
        id=str(uuid.uuid4()),
        manufacturer_id=manufacturer_id,
        caliber_id=caliber_id,
        name=_get_value(entity, "name", ""),
        sku=_get_value(entity, "sku"),
        weight_grains=float(_get_value(entity, "weight_grains", 0)),
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
    )


def _make_cartridge(
    entity: dict,
    manufacturer_id: str,
    caliber_id: str,
    bullet_id: str,
    source_url: str,
) -> Cartridge:
    """Create a Cartridge ORM instance from an extracted entity dict."""
    return Cartridge(
        id=str(uuid.uuid4()),
        manufacturer_id=manufacturer_id,
        caliber_id=caliber_id,
        bullet_id=bullet_id,
        name=_get_value(entity, "name", ""),
        sku=_get_value(entity, "sku"),
        bullet_weight_grains=float(_get_value(entity, "bullet_weight_grains", 0)),
        muzzle_velocity_fps=int(_get_value(entity, "muzzle_velocity_fps", 0)),
        test_barrel_length_inches=_safe_float(_get_value(entity, "test_barrel_length_inches")),
        round_count=_safe_int(_get_value(entity, "round_count")),
        product_line=_get_value(entity, "product_line"),
        source_url=source_url,
        extraction_confidence=_avg_confidence(entity),
    )


def _make_rifle(entity: dict, manufacturer_id: str, chamber_id: str, source_url: str) -> RifleModel:
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
    )


def _make_bc_sources(bullet_id: str, bc_sources: list[dict], source_url: str) -> list[BulletBCSource]:
    """Create BulletBCSource ORM instances from extracted BC source dicts."""
    results = []
    for bc in bc_sources:
        results.append(
            BulletBCSource(
                id=str(uuid.uuid4()),
                bullet_id=bullet_id,
                bc_type=bc.get("bc_type", ""),
                bc_value=float(bc.get("bc_value", 0)),
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
        return None


def _safe_int(val) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
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
    session = SessionFactory()

    resolver = EntityResolver(session)

    stats = {
        "bullet": {"created": 0, "matched": 0, "flagged": 0},
        "cartridge": {"created": 0, "matched": 0, "flagged": 0},
        "rifle": {"created": 0, "matched": 0, "flagged": 0},
    }
    report_entries: list[dict] = []

    entries = extracted_files[: args.limit] if args.limit > 0 else extracted_files

    try:
        for i, extracted_path in enumerate(entries):
            uhash = extracted_path.stem
            extraction_data = json.loads(extracted_path.read_text(encoding="utf-8"))

            url = extraction_data.get("url", uhash)
            entity_type = extraction_data.get("entity_type", "")
            entities = extraction_data.get("entities", [])
            bc_sources = extraction_data.get("bc_sources", [])

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
                    "unresolved_refs": resolution.unresolved_refs,
                    "warnings": resolution.warnings,
                    "action": "",
                }

                if resolution.match.matched:
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
                elif resolution.unresolved_refs:
                    entry["action"] = "flagged_unresolved"
                    stats[entity_type]["flagged"] += 1
                    logger.warning("  [%d] FLAGGED (unresolved refs): %s — %s", j + 1, name, resolution.unresolved_refs)
                else:
                    # New entity — create it
                    entry["action"] = "created"
                    stats[entity_type]["created"] += 1

                    if args.commit:
                        try:
                            if entity_type == "bullet":
                                obj = _make_bullet(entity, resolution.manufacturer_id, resolution.caliber_id, url)
                                session.add(obj)
                                # BC sources
                                for bc_obj in _make_bc_sources(obj.id, bc_sources, url):
                                    session.add(bc_obj)
                                entry["created_id"] = obj.id
                            elif entity_type == "cartridge":
                                # bullet_id might be None if unresolved
                                bullet_id = resolution.bullet_id or ""
                                obj = _make_cartridge(
                                    entity, resolution.manufacturer_id, resolution.caliber_id, bullet_id, url
                                )
                                session.add(obj)
                                entry["created_id"] = obj.id
                            elif entity_type == "rifle":
                                obj = _make_rifle(entity, resolution.manufacturer_id, resolution.chamber_id, url)
                                session.add(obj)
                                entry["created_id"] = obj.id
                        except Exception as e:
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
        session.rollback()
        raise
    finally:
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
        print(f"  {etype}: {counts['created']} created, {counts['matched']} matched, {counts['flagged']} flagged")
    print(f"\nReport written to: {STORE_REPORT_PATH}")


if __name__ == "__main__":
    main()
