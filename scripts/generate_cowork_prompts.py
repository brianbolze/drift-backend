"""Generate research prompts for Claude CoWork agents to discover product URLs.

Reads the shopping list and generates targeted prompts for CoWork to research
manufacturer websites and find product page URLs. CoWork agents have web browsing
capabilities and access to a domain mapping tool for discovering site structure.

Usage:
    python scripts/generate_cowork_prompts.py
    python scripts/generate_cowork_prompts.py --limit 5
    python scripts/generate_cowork_prompts.py --entity-type bullet --output prompts/
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SHOPPING_LIST_PATH = _ROOT / "data" / "pipeline" / "shopping_list.json"


def _load_shopping_list(path: Path) -> dict:
    """Load the shopping list JSON."""
    if not path.exists():
        raise SystemExit(f"Shopping list not found at {path}\n" f"Run: python scripts/generate_shopping_list.py")
    return json.loads(path.read_text(encoding="utf-8"))


def _generate_prompt(
    manufacturer: dict,
    entity_type: str,
    calibers_with_gaps: list[dict],
) -> dict:
    """Generate a single CoWork research prompt (manufacturer-centric).

    Args:
        manufacturer: Manufacturer entry (name, website_url, type_tags)
        entity_type: One of "bullet", "cartridge", "rifle"
        calibers_with_gaps: List of caliber dicts that need this entity type,
                           ordered by priority (LR rank)

    Returns:
        Dict with prompt text and metadata.
    """
    mfr_name = manufacturer["name"]
    website = manufacturer["website_url"]

    # Group calibers by priority tier
    high_priority = [c for c in calibers_with_gaps if c.get("lr_rank") and c["lr_rank"] <= 5]
    medium_priority = [c for c in calibers_with_gaps if c.get("lr_rank") and 5 < c["lr_rank"] <= 15]
    low_priority = [c for c in calibers_with_gaps if c.get("overall_rank") and c["overall_rank"] <= 30]

    total_gap = sum(
        c[
            (
                f"{entity_type}s"
                if entity_type == "bullet"
                else "cartridges" if entity_type == "cartridge" else "rifle_models"
            )
        ]["gap"]
        for c in calibers_with_gaps
    )

    # Build caliber lists by priority
    def format_caliber_list(cals):
        return ", ".join(c["name"] for c in cals[:10])  # Limit to 10 per tier for readability

    high_priority_str = format_caliber_list(high_priority) if high_priority else None
    medium_priority_str = format_caliber_list(medium_priority) if medium_priority else None
    low_priority_str = format_caliber_list(low_priority) if low_priority else None

    # Entity-specific wording
    entity_descriptions = {
        "bullet": "component bullets (projectiles)",
        "cartridge": "factory-loaded ammunition",
        "rifle": "rifle models",
    }
    entity_desc = entity_descriptions.get(entity_type, entity_type)

    entity_plural = "bullets" if entity_type == "bullet" else "cartridges" if entity_type == "cartridge" else "rifles"

    # Entity-specific guidance
    entity_guidance = {
        "bullet": """
Look for pages with:
- Ballistic coefficient (BC) values (G1 and/or G7)
- Bullet weight in grains
- Bullet diameter or caliber designation
- Base type (boat tail, flat base, etc.)
- Tip type (hollow point, polymer tip, etc.)
""",
        "cartridge": """
Look for pages with:
- Muzzle velocity (fps)
- Bullet weight (grains)
- Bullet name/type (e.g., "ELD Match", "Scenar")
- Test barrel length (if specified)
- Round count per box
""",
        "rifle": """
Look for pages with:
- Barrel length (inches)
- Twist rate (e.g., "1:8")
- Chambering/caliber
- Barrel material and finish
- Weight (lbs)
""",
    }
    guidance = entity_guidance.get(entity_type, "")

    # Build priority section
    priority_section = ""
    if high_priority_str:
        priority_section += f"\n**High Priority (LR Top 5)**: {high_priority_str}"
    if medium_priority_str:
        priority_section += f"\n**Medium Priority (LR Top 15)**: {medium_priority_str}"
    if low_priority_str:
        priority_section += f"\n**Lower Priority (Popular Overall)**: {low_priority_str}"

    prompt = f"""Research all {entity_desc} from {mfr_name} across multiple calibers.

**Manufacturer**: {mfr_name} ({website})
**Entity type**: {entity_type}
**Estimated gap**: ~{total_gap} {entity_plural} needed across {len(calibers_with_gaps)} calibers

## Target Calibers
{priority_section}

Focus on **high priority calibers first**, but if you find products in other calibers while \
exploring the site, include them too.

## Your Task

Use your domain mapping tool to explore the {mfr_name} website structure and find **individual \
product pages** (not category/listing pages) for {entity_desc}.

Most manufacturer sites organize by caliber with predictable URL patterns like:
- `/bullets/[caliber]/[model]`
- `/ammunition/[caliber]/[product-line]`
- `/rifles/[model-family]/[chambering]`
- `/products/[category]/[sku]`

Explore the site systematically and find products with actual specifications.{guidance}

## Requirements

1. **Product pages only** — Each URL should be for a specific SKU/model with detailed specs. \
Avoid category pages, search results, or product family landing pages.

2. **Multi-variant pages are OK** — If a single product page lists multiple weights/variants \
(e.g., "LRX Boat Tail: 175gr, 190gr, 200gr, 208gr"), that's perfect — include it as one URL.

3. **Verify specs exist** — Briefly check each page to confirm it has the specifications we \
need for extraction (BC values, velocities, weights, etc.). **Important**: Note in the "notes" \
field if specs are complete on the product page vs. in a separate section (e.g., load data, \
reloading guide, PDF downloads).

4. **Prioritize high-value calibers** — Focus on the high/medium priority calibers listed above, \
but include others if you find them.

5. **Cast a wide net** — Find as many products as you can across all relevant calibers. \
We're building a comprehensive database.

6. **Deduplication** — If you find multiple pages for the same product (different pack sizes, \
etc.), pick the one with the most complete specifications.

## Output Format

Return a JSON array with this structure:

```json
[
  {{
    "url": "https://example.com/product/...",
    "entity_type": {entity_type!r},
    "expected_manufacturer": {mfr_name!r},
    "expected_caliber": "6.5 Creedmoor",
    "brief_description": "140gr Hybrid Target",
    "confidence": "high",
    "notes": "Has G1/G7 BC, sectional density listed"
  }},
  {{
    "url": "https://example.com/product/another",
    "entity_type": {entity_type!r},
    "expected_manufacturer": {mfr_name!r},
    "expected_caliber": "6mm Creedmoor",
    "brief_description": "105gr VLD Target",
    "confidence": "high",
    "notes": "Complete specs available"
  }}
]
```

Note: Return products from **all calibers** you find, not just one. The array can contain \
dozens of products across multiple calibers.

**Confidence levels**:
- `high`: Product page with complete specs on the page (BC/velocity/weight/specs all visible)
- `medium`: Product page exists but some specs are in separate sections (load data, PDFs) or \
require navigation
- `low`: Uncertain if this is the canonical product page, specs are minimal, or page structure \
is unclear

## Notes

- Return products from **all relevant calibers** you find on the site, not just the high \
priority ones.
- If the site structure makes individual product pages hard to find (e.g., everything behind \
a configurator), document what you found and provide the best alternative (product family \
pages, etc.).
- The manufacturer may not make products in all listed calibers — that's fine, just return \
what exists.
- Use your judgment on completeness — aim for comprehensive coverage of their catalog in \
relevant calibers.
"""

    return {
        "manufacturer": mfr_name,
        "entity_type": entity_type,
        "caliber_count": len(calibers_with_gaps),
        "total_gap": total_gap,
        "high_priority_calibers": [c["name"] for c in high_priority],
        "prompt": prompt.strip(),
    }


def _generate_all_prompts(shopping_list: dict, entity_type: str | None, limit: int) -> list[dict]:
    """Generate all research prompts based on the shopping list (manufacturer-centric).

    Returns a prioritized list of prompt dicts.
    """
    calibers = shopping_list["calibers"]
    manufacturers = shopping_list["manufacturers"]

    # Build manufacturer lists by type tags
    bullet_mfrs = [m for m in manufacturers if any("bullet" in tag for tag in m.get("type_tags", []))]
    ammo_mfrs = [m for m in manufacturers if any("ammo" in tag for tag in m.get("type_tags", []))]
    rifle_mfrs = [m for m in manufacturers if any("rifle" in tag for tag in m.get("type_tags", []))]

    # Build caliber lists with gaps for each entity type
    def calibers_needing(entity_key):
        result = [c for c in calibers if c[entity_key]["gap"] > 0]
        # Sort by LR rank first (nulls last), then overall rank
        result.sort(
            key=lambda c: (
                c.get("lr_rank") if c.get("lr_rank") else 999,
                c.get("overall_rank") if c.get("overall_rank") else 999,
            )
        )
        return result

    bullet_calibers = calibers_needing("bullets")
    cartridge_calibers = calibers_needing("cartridges")
    rifle_calibers = calibers_needing("rifle_models")

    prompts = []

    # Generate one prompt per manufacturer for each entity type
    if entity_type is None or entity_type == "bullet":
        for mfr in bullet_mfrs:
            prompts.append(_generate_prompt(mfr, "bullet", bullet_calibers))

    if entity_type is None or entity_type == "cartridge":
        for mfr in ammo_mfrs:
            prompts.append(_generate_prompt(mfr, "cartridge", cartridge_calibers))

    if entity_type is None or entity_type == "rifle":
        for mfr in rifle_mfrs:
            prompts.append(_generate_prompt(mfr, "rifle", rifle_calibers))

    # Sort by total gap (highest first) - manufacturers with biggest potential contribution first
    prompts.sort(key=lambda p: -p["total_gap"])

    if limit > 0:
        prompts = prompts[:limit]

    return prompts


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate CoWork research prompts for URL discovery")
    parser.add_argument(
        "--shopping-list",
        type=Path,
        default=_SHOPPING_LIST_PATH,
        help="Path to shopping list JSON",
    )
    parser.add_argument(
        "--entity-type",
        type=str,
        choices=["bullet", "cartridge", "rifle"],
        help="Only generate prompts for this entity type",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max number of prompts to generate (0 = all)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_ROOT / "data" / "pipeline" / "cowork_prompts",
        help="Output directory for prompt files",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["json", "txt", "both"],
        default="both",
        help="Output format (default: both)",
    )
    args = parser.parse_args()

    shopping_list = _load_shopping_list(args.shopping_list)
    prompts = _generate_all_prompts(shopping_list, args.entity_type, args.limit)

    if not prompts:
        print("No prompts generated (all targets met or no gaps found).")
        return

    args.output.mkdir(parents=True, exist_ok=True)

    # Save prompts
    for i, p in enumerate(prompts, 1):
        # Build filename
        mfr_slug = p["manufacturer"].replace(" ", "_").replace(".", "").lower()
        filename_base = f"{i:02d}_{p['entity_type']}_{mfr_slug}"

        # Save as JSON
        if args.format in ["json", "both"]:
            json_path = args.output / f"{filename_base}.json"
            json_path.write_text(
                json.dumps(p, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        # Save as text
        if args.format in ["txt", "both"]:
            txt_path = args.output / f"{filename_base}.txt"
            txt_path.write_text(p["prompt"], encoding="utf-8")

    # Print summary
    print(f"Generated {len(prompts)} CoWork research prompt(s)")
    print(f"Saved to: {args.output}/")
    print()

    # Show first few prompts
    show_count = min(10, len(prompts))
    print(f"First {show_count} prompts:\n")
    print(f"{'#':<4} {'Type':<10} {'Manufacturer':<25} {'Calibers':<8} {'Gap':<6}")
    print("-" * 60)
    for i, p in enumerate(prompts[:show_count], 1):
        print(f"{i:<4} {p['entity_type']:<10} {p['manufacturer']:<25} " f"{p['caliber_count']:<8} ~{p['total_gap']:<5}")

    if len(prompts) > show_count:
        print(f"\n... and {len(prompts) - show_count} more")

    print("\nTo use: Copy a .txt file's contents and paste into Claude CoWork.")


if __name__ == "__main__":
    main()
