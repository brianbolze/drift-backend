"""Generate a shopping list of data gaps to fill.

Queries the DB for calibers ordered by lr_popularity_rank, counts existing
bullets/cartridges/rifle_models, and outputs a JSON shopping list showing
what needs to be scraped.

Usage:
    python scripts/generate_shopping_list.py
    python scripts/generate_shopping_list.py -o data/pipeline/shopping_list.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from drift.database import get_session_factory
from drift.models import Bullet, Caliber, Cartridge, Manufacturer, RifleModel

_ROOT = Path(__file__).resolve().parent.parent


def _target_counts(lr_rank: int | None, overall_rank: int | None) -> dict:
    """Derive target counts based on caliber popularity tier."""
    if lr_rank is not None and lr_rank <= 5:
        return {"bullets": 15, "cartridges": 12, "rifle_models": 6}
    elif lr_rank is not None and lr_rank <= 10:
        return {"bullets": 12, "cartridges": 10, "rifle_models": 5}
    elif lr_rank is not None and lr_rank <= 15:
        return {"bullets": 10, "cartridges": 8, "rifle_models": 4}
    elif overall_rank is not None and overall_rank <= 20:
        return {"bullets": 8, "cartridges": 6, "rifle_models": 3}
    else:
        return {"bullets": 5, "cartridges": 4, "rifle_models": 2}


def generate_shopping_list(session: Session) -> dict:
    """Build the shopping list from current DB state."""
    # Get all calibers with popularity ranks, ordered by LR rank then overall rank
    calibers = (
        session.execute(
            select(Caliber).order_by(
                # LR-ranked calibers first (nulls last), then by overall rank
                func.coalesce(Caliber.lr_popularity_rank, 9999),
                func.coalesce(Caliber.overall_popularity_rank, 9999),
                Caliber.name,
            )
        )
        .scalars()
        .all()
    )

    # Count entities per caliber
    bullet_counts = dict(
        session.execute(select(Bullet.bullet_diameter_inches, func.count(Bullet.id)).group_by(Bullet.bullet_diameter_inches)).all()
    )
    cartridge_counts = dict(
        session.execute(select(Cartridge.caliber_id, func.count(Cartridge.id)).group_by(Cartridge.caliber_id)).all()
    )

    # RifleModel uses chamber_id, not caliber_id directly — count via chamber→caliber link
    # For simplicity, just get total rifle model count per chamber
    rifle_counts_raw = session.execute(
        select(RifleModel.chamber_id, func.count(RifleModel.id)).group_by(RifleModel.chamber_id)
    ).all()

    # Map chamber_id → caliber_id via ChamberAcceptsCaliber
    from drift.models import ChamberAcceptsCaliber

    chamber_caliber_map = dict(
        session.execute(
            select(ChamberAcceptsCaliber.chamber_id, ChamberAcceptsCaliber.caliber_id).where(
                ChamberAcceptsCaliber.is_primary.is_(True)
            )
        ).all()
    )

    rifle_counts: dict[str, int] = {}
    for chamber_id, count in rifle_counts_raw:
        caliber_id = chamber_caliber_map.get(chamber_id)
        if caliber_id:
            rifle_counts[caliber_id] = rifle_counts.get(caliber_id, 0) + count

    # Build caliber entries
    caliber_entries = []
    total_gaps = {"bullets": 0, "cartridges": 0, "rifle_models": 0}

    for cal in calibers:
        targets = _target_counts(cal.lr_popularity_rank, cal.overall_popularity_rank)
        have_bullets = bullet_counts.get(cal.bullet_diameter_inches, 0)
        have_cartridges = cartridge_counts.get(cal.id, 0)
        have_rifles = rifle_counts.get(cal.id, 0)

        entry = {
            "name": cal.name,
            "lr_rank": cal.lr_popularity_rank,
            "overall_rank": cal.overall_popularity_rank,
            "is_common_lr": cal.is_common_lr,
            "bullets": {
                "have": have_bullets,
                "target": targets["bullets"],
                "gap": max(0, targets["bullets"] - have_bullets),
            },
            "cartridges": {
                "have": have_cartridges,
                "target": targets["cartridges"],
                "gap": max(0, targets["cartridges"] - have_cartridges),
            },
            "rifle_models": {
                "have": have_rifles,
                "target": targets["rifle_models"],
                "gap": max(0, targets["rifle_models"] - have_rifles),
            },
        }

        total_gaps["bullets"] += entry["bullets"]["gap"]
        total_gaps["cartridges"] += entry["cartridges"]["gap"]
        total_gaps["rifle_models"] += entry["rifle_models"]["gap"]

        caliber_entries.append(entry)

    # Get manufacturers with website URLs
    manufacturers = (
        session.execute(select(Manufacturer).where(Manufacturer.website_url.isnot(None)).order_by(Manufacturer.name))
        .scalars()
        .all()
    )

    manufacturer_entries = [
        {
            "name": m.name,
            "website_url": m.website_url,
            "type_tags": m.type_tags,
        }
        for m in manufacturers
    ]

    return {
        "summary": {
            "total_calibers": len(caliber_entries),
            "calibers_with_gaps": sum(
                1
                for c in caliber_entries
                if c["bullets"]["gap"] > 0 or c["cartridges"]["gap"] > 0 or c["rifle_models"]["gap"] > 0
            ),
            "total_gaps": total_gaps,
        },
        "calibers": caliber_entries,
        "manufacturers": manufacturer_entries,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate data gap shopping list")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=_ROOT / "data" / "pipeline" / "shopping_list.json",
        help="Output JSON path",
    )
    parser.add_argument("--lr-only", action="store_true", help="Only show calibers with LR popularity rank")
    args = parser.parse_args()

    SessionFactory = get_session_factory()
    with SessionFactory() as session:
        shopping_list = generate_shopping_list(session)

    if args.lr_only:
        shopping_list["calibers"] = [c for c in shopping_list["calibers"] if c["lr_rank"] is not None]

    # Print summary
    s = shopping_list["summary"]
    print(f"Calibers: {s['total_calibers']} total, {s['calibers_with_gaps']} with gaps")
    print(
        f"Gaps:     {s['total_gaps']['bullets']} bullets, {s['total_gaps']['cartridges']} cartridges, "
        f"{s['total_gaps']['rifle_models']} rifle models"
    )
    print()

    # Print top priority calibers
    priority = [c for c in shopping_list["calibers"] if c["lr_rank"] is not None][:15]
    if priority:
        print(f"{'Caliber':<25s} {'LR':>3s} {'Bullets':>12s} {'Cartridges':>12s} {'Rifles':>12s}")
        print("-" * 70)
        for c in priority:
            b = c["bullets"]
            ct = c["cartridges"]
            r = c["rifle_models"]
            print(
                f"{c['name']:<25s} {c['lr_rank'] or '':>3} "
                f"{b['have']}/{b['target']} ({b['gap']}){'':<3s} "
                f"{ct['have']}/{ct['target']} ({ct['gap']}){'':<3s} "
                f"{r['have']}/{r['target']} ({r['gap']})"
            )

    print(f"\nManufacturers with websites: {len(shopping_list['manufacturers'])}")

    # Save
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(shopping_list, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved to {args.output}")


if __name__ == "__main__":
    main()
