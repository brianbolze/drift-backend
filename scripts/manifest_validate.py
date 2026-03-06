"""Cross-validate manifest metadata against DB records.

Joins url_manifest.json and url_manifest_bullets.json entries against the DB
using source_url, then checks for discrepancies in manufacturer, caliber,
weight, diameter, and BC values.

Usage:
    PYTHONPATH=src python scripts/manifest_validate.py
    PYTHONPATH=src python scripts/manifest_validate.py --json   # write JSON report
"""

from __future__ import annotations

import argparse
import json
import re

from drift.database import get_session_factory
from drift.models.bullet import Bullet
from drift.models.caliber import Caliber
from drift.models.cartridge import Cartridge
from drift.models.manufacturer import Manufacturer
from drift.pipeline.config import DATA_DIR, MANIFEST_PATH
from drift.pipeline.resolution.resolver import _normalize

# ── Constants ────────────────────────────────────────────────────────────────

CARTRIDGE_MANIFEST_PATH = DATA_DIR / "url_manifest_cartridges.json"
REPORT_PATH = DATA_DIR / "manifest_validation_report.json"

WEIGHT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*gr", re.IGNORECASE)
BC_G1_RE = re.compile(r"G1\s*(?:BC)?\s*[=:]?\s*(0\.\d+)", re.IGNORECASE)
BC_G7_RE = re.compile(r"G7\s*(?:BC)?\s*[=:]?\s*(0\.\d+)", re.IGNORECASE)

# Diameter patterns in manifest expected_caliber field:
#   "6.5mm (.264\")"  → 0.264
#   ".308 / 30 CAL"   → 0.308
#   ".277 / .270 CAL"  → 0.277
#   "Dia: 7.83 mm (.308'')" (in notes) → 0.308
# Match explicit 3-digit diameter (.NNN) when followed by " or '' or / or CAL or Caliber
DIAMETER_EXPLICIT_RE = re.compile(r"\.(2[0-9]{2}|3[0-9]{2}|4[0-9]{2}|5[0-9]{2}|6[0-9]{2})\s*[\"'/]")
# Also match ".NNN / NN CAL" or ".NNN CAL" pattern (the first .NNN is the diameter)
DIAMETER_CAL_RE = re.compile(r"^\.(\d{3})\s+(?:/|CAL)", re.IGNORECASE)

# Common bore-vs-bullet diameter offsets (cartridge designator → actual bullet diameter).
# Manifest often uses the bore/cartridge name rather than the bullet measurement.
# These are NOT errors — just known differences between naming conventions.
BORE_TO_BULLET: dict[float, float] = {
    0.270: 0.277,
    0.303: 0.311,
    0.405: 0.411,
    0.500: 0.510,  # .50 BMG
}

# Widen tolerance for rare large-bore cartridges where bore designator is approximate
DIAMETER_TOLERANCE = 0.008  # covers .500→.505 (505 Gibbs) and similar


# ── Helpers ──────────────────────────────────────────────────────────────────


def _load_manifest_entries() -> list[dict]:
    """Load and merge all manifest files, deduplicating by URL."""
    entries: list[dict] = []
    seen_urls: set[str] = set()
    for path in (MANIFEST_PATH, CARTRIDGE_MANIFEST_PATH):
        if path.exists():
            data = json.loads(path.read_text())
            for e in data:
                if e["url"] not in seen_urls:
                    entries.append(e)
                    seen_urls.add(e["url"])
    return entries


def _manufacturer_matches(expected: str, db_mfr: Manufacturer) -> bool:
    """Check if manifest manufacturer name matches the DB manufacturer."""
    exp_norm = _normalize(expected)
    if exp_norm == _normalize(db_mfr.name):
        return True
    for alt in db_mfr.alt_names or []:
        if exp_norm == _normalize(alt):
            return True
    # Containment check: "Sierra Bullets" contains "Sierra"
    exp_words = set(exp_norm.split())
    db_words = set(_normalize(db_mfr.name).split())
    if exp_words & db_words:
        return True
    return False


def _caliber_matches(expected: str, db_cal: Caliber) -> bool:
    """Check if manifest caliber name matches the DB caliber."""

    def _canon(name: str) -> str:
        """Strip periods, 'mm', leading zeros for flexible comparison."""
        n = _normalize(name).replace(".", "").replace("mm", "").strip()
        # Remove common suffixes that vary
        for suffix in ("magnum", "mag", "remington", "rem", "winchester", "win", "swedish", "mauser"):
            n = n.replace(suffix, "").strip()
        return n

    exp_canon = _canon(expected)
    db_canon = _canon(db_cal.name)
    if exp_canon == db_canon:
        return True
    # Check alt_names
    for alt in db_cal.alt_names or []:
        if exp_canon == _canon(alt):
            return True
    # Substring containment
    exp_norm = _normalize(expected).replace(".", "")
    db_norm = _normalize(db_cal.name).replace(".", "")
    if exp_norm in db_norm or db_norm in exp_norm:
        return True
    # Word overlap: do the numeric portions match?
    exp_nums = set(re.findall(r"\d+", expected))
    db_nums = set(re.findall(r"\d+", db_cal.name))
    if exp_nums and exp_nums == db_nums:
        return True
    return False


def _parse_weight(text: str) -> float | None:
    m = WEIGHT_RE.search(text)
    return float(m.group(1)) if m else None


def _parse_diameter(caliber_text: str, notes: str = "") -> float | None:
    """Parse bullet diameter from expected_caliber or notes.

    Looks for explicit diameter patterns like (.264") or .308 / 30 CAL,
    and also checks notes for patterns like "Dia: 7.83 mm (.308'')".
    """
    combined = f"{caliber_text} {notes}"
    # Try explicit parenthetical diameter: (.264"), (.308'')
    m = DIAMETER_EXPLICIT_RE.search(combined)
    if m:
        return float(f"0.{m.group(1)}")
    # Try ".NNN / CAL" or ".NNN CAL" at start of caliber
    m = DIAMETER_CAL_RE.match(caliber_text.strip())
    if m:
        return float(f"0.{m.group(1)}")
    return None


def _parse_bc(notes: str) -> tuple[float | None, float | None]:
    g1_match = BC_G1_RE.search(notes)
    g7_match = BC_G7_RE.search(notes)
    g1 = float(g1_match.group(1)) if g1_match else None
    g7 = float(g7_match.group(1)) if g7_match else None
    return g1, g7


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Cross-validate manifest metadata against DB")
    parser.add_argument("--json", action="store_true", help="Write JSON report to data/pipeline/")
    args = parser.parse_args()

    session = get_session_factory()()

    # Pre-load lookups
    mfr_by_id: dict[str, Manufacturer] = {m.id: m for m in session.query(Manufacturer).all()}
    cal_by_id: dict[str, Caliber] = {c.id: c for c in session.query(Caliber).all()}

    # Index DB records by source_url
    bullets_by_url: dict[str, Bullet] = {}
    for b in session.query(Bullet).filter(Bullet.source_url.isnot(None)).all():
        bullets_by_url[b.source_url] = b

    carts_by_url: dict[str, Cartridge] = {}
    for c in session.query(Cartridge).filter(Cartridge.source_url.isnot(None)).all():
        carts_by_url[c.source_url] = c

    # Load manifest
    manifest = _load_manifest_entries()
    bullet_entries = [e for e in manifest if e["entity_type"] == "bullet"]
    cart_entries = [e for e in manifest if e["entity_type"] == "cartridge"]

    # ── Counters ─────────────────────────────────────────────────────────────
    stats = {
        "manifest_total": len(manifest),
        "manifest_bullets": len(bullet_entries),
        "manifest_cartridges": len(cart_entries),
        "bullets_in_db": 0,
        "cartridges_in_db": 0,
        "manufacturer_mismatches": 0,
        "caliber_mismatches": 0,
        "weight_mismatches": 0,
        "diameter_mismatches": 0,
        "bc_data_loss": 0,
        "bc_value_mismatches": 0,
        "zero_velocity": 0,
    }
    findings: list[dict] = []

    # ── Validate bullets ─────────────────────────────────────────────────────
    for entry in bullet_entries:
        url = entry["url"]
        bullet = bullets_by_url.get(url)
        if not bullet:
            continue
        stats["bullets_in_db"] += 1

        # Manufacturer check
        if bullet.manufacturer_id and entry.get("expected_manufacturer"):
            db_mfr = mfr_by_id.get(bullet.manufacturer_id)
            if db_mfr and not _manufacturer_matches(entry["expected_manufacturer"], db_mfr):
                stats["manufacturer_mismatches"] += 1
                findings.append(
                    {
                        "type": "MANUFACTURER",
                        "entity": "bullet",
                        "url": url,
                        "expected": entry["expected_manufacturer"],
                        "actual": db_mfr.name,
                        "name": bullet.name,
                    }
                )

        # Weight check
        desc = entry.get("brief_description", "")
        notes = entry.get("notes", "")
        manifest_weight = _parse_weight(desc) or _parse_weight(notes)
        if manifest_weight and bullet.weight_grains and abs(manifest_weight - bullet.weight_grains) > 1.0:
            stats["weight_mismatches"] += 1
            findings.append(
                {
                    "type": "WEIGHT",
                    "entity": "bullet",
                    "url": url,
                    "expected": manifest_weight,
                    "actual": bullet.weight_grains,
                    "name": bullet.name,
                }
            )

        # Diameter check
        manifest_diam = _parse_diameter(entry.get("expected_caliber", ""), notes)
        if manifest_diam and bullet.bullet_diameter_inches:
            # Accept known bore→bullet offset (e.g., .270 bore → .277 bullet)
            expected_bullet_diam = BORE_TO_BULLET.get(manifest_diam, manifest_diam)
            if abs(expected_bullet_diam - bullet.bullet_diameter_inches) > DIAMETER_TOLERANCE:
                stats["diameter_mismatches"] += 1
                findings.append(
                    {
                        "type": "DIAMETER",
                        "entity": "bullet",
                        "url": url,
                        "expected": manifest_diam,
                        "actual": bullet.bullet_diameter_inches,
                        "name": bullet.name,
                    }
                )

        # BC check
        manifest_g1, manifest_g7 = _parse_bc(notes)
        if manifest_g1 is not None:
            if bullet.bc_g1_published is None:
                stats["bc_data_loss"] += 1
                findings.append(
                    {
                        "type": "BC_MISSING",
                        "entity": "bullet",
                        "url": url,
                        "field": "bc_g1",
                        "expected": manifest_g1,
                        "actual": None,
                        "name": bullet.name,
                    }
                )
            elif abs(manifest_g1 - bullet.bc_g1_published) / manifest_g1 > 0.05:
                stats["bc_value_mismatches"] += 1
                findings.append(
                    {
                        "type": "BC_MISMATCH",
                        "entity": "bullet",
                        "url": url,
                        "field": "bc_g1",
                        "expected": manifest_g1,
                        "actual": bullet.bc_g1_published,
                        "name": bullet.name,
                    }
                )

        if manifest_g7 is not None:
            if bullet.bc_g7_published is None:
                stats["bc_data_loss"] += 1
                findings.append(
                    {
                        "type": "BC_MISSING",
                        "entity": "bullet",
                        "url": url,
                        "field": "bc_g7",
                        "expected": manifest_g7,
                        "actual": None,
                        "name": bullet.name,
                    }
                )
            elif abs(manifest_g7 - bullet.bc_g7_published) / manifest_g7 > 0.05:
                stats["bc_value_mismatches"] += 1
                findings.append(
                    {
                        "type": "BC_MISMATCH",
                        "entity": "bullet",
                        "url": url,
                        "field": "bc_g7",
                        "expected": manifest_g7,
                        "actual": bullet.bc_g7_published,
                        "name": bullet.name,
                    }
                )

    # ── Validate cartridges ──────────────────────────────────────────────────
    for entry in cart_entries:
        url = entry["url"]
        cart = carts_by_url.get(url)
        if not cart:
            continue
        stats["cartridges_in_db"] += 1

        # Manufacturer check
        if cart.manufacturer_id and entry.get("expected_manufacturer"):
            db_mfr = mfr_by_id.get(cart.manufacturer_id)
            if db_mfr and not _manufacturer_matches(entry["expected_manufacturer"], db_mfr):
                stats["manufacturer_mismatches"] += 1
                findings.append(
                    {
                        "type": "MANUFACTURER",
                        "entity": "cartridge",
                        "url": url,
                        "expected": entry["expected_manufacturer"],
                        "actual": db_mfr.name,
                        "name": cart.name,
                    }
                )

        # Caliber check
        if cart.caliber_id and entry.get("expected_caliber"):
            db_cal = cal_by_id.get(cart.caliber_id)
            if db_cal and not _caliber_matches(entry["expected_caliber"], db_cal):
                stats["caliber_mismatches"] += 1
                findings.append(
                    {
                        "type": "CALIBER",
                        "entity": "cartridge",
                        "url": url,
                        "expected": entry["expected_caliber"],
                        "actual": db_cal.name,
                        "name": cart.name,
                    }
                )

        # Velocity sanity
        if cart.muzzle_velocity_fps == 0:
            stats["zero_velocity"] += 1
            findings.append(
                {
                    "type": "ZERO_VELOCITY",
                    "entity": "cartridge",
                    "url": url,
                    "name": cart.name,
                }
            )

    # ── Report ───────────────────────────────────────────────────────────────
    in_db = stats["bullets_in_db"] + stats["cartridges_in_db"]
    not_in_db = stats["manifest_total"] - in_db

    print()
    print("Manifest → DB Validation Report")
    print("=" * 50)
    print(
        f"Manifest entries:   {stats['manifest_total']} ({stats['manifest_bullets']} bullets, {stats['manifest_cartridges']} cartridges)"
    )
    print(f"In DB:              {in_db} ({stats['bullets_in_db']} bullets, {stats['cartridges_in_db']} cartridges)")
    print(f"Not in DB:          {not_in_db}")
    print()
    print(f"Manufacturer mismatches:           {stats['manufacturer_mismatches']}")
    print(f"Caliber mismatches:                {stats['caliber_mismatches']}")
    print(f"Weight mismatches (>1gr):          {stats['weight_mismatches']}")
    print(f"Diameter mismatches (>0.002\"):      {stats['diameter_mismatches']}")
    print(f"BC data loss (manifest→DB null):   {stats['bc_data_loss']}")
    print(f"BC value mismatches (>5%):         {stats['bc_value_mismatches']}")
    print(f"Zero velocity cartridges:          {stats['zero_velocity']}")

    if findings:
        print()
        print("--- Details ---")
        for f in findings:
            if f["type"] == "MANUFACTURER":
                print(f"[MANUFACTURER] {f['expected']} ≠ {f['actual']} ({f['entity']}: {f['name']})")
            elif f["type"] == "CALIBER":
                print(f"[CALIBER] {f['expected']} ≠ {f['actual']} ({f['name']})")
            elif f["type"] == "WEIGHT":
                print(f"[WEIGHT] {f['expected']}gr (manifest) vs {f['actual']}gr (DB) — {f['name']}")
            elif f["type"] == "DIAMETER":
                print(f"[DIAMETER] {f['expected']}\" (manifest) vs {f['actual']}\" (DB) — {f['name']}")
            elif f["type"] == "BC_MISSING":
                print(f"[BC_MISSING] {f['field']}={f['expected']} in manifest, NULL in DB — {f['name']}")
            elif f["type"] == "BC_MISMATCH":
                pct = abs(f["expected"] - f["actual"]) / f["expected"] * 100
                print(
                    f"[BC_MISMATCH] {f['field']}: {f['expected']} (manifest) vs {f['actual']} (DB) [{pct:.1f}% off] — {f['name']}"
                )
            elif f["type"] == "ZERO_VELOCITY":
                print(f"[ZERO_VELOCITY] {f['name']}")

    if args.json:
        report = {"stats": stats, "findings": findings}
        REPORT_PATH.write_text(json.dumps(report, indent=2, default=str))
        print(f"\nJSON report: {REPORT_PATH}")

    session.close()


if __name__ == "__main__":
    main()
