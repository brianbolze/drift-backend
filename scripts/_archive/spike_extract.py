"""Spike: extract structured product data from reduced HTML using Claude Haiku.

Reads reduced.html (output of spike_reduce.py), sends it to Claude Haiku with
an entity-specific extraction prompt, and saves the structured JSON output.

Usage:
    pyt n scripts/spike_extract.py --entity-type bullet
    python scripts/spike_extract.py --entity-type cartridge
    python scripts/spike_extract.py --entity-type rifle
    python scripts/spike_extract.py --entity-type bullet --model claude-sonnet-4-20250514
"""

# flake8: noqa: E501 B950 — prompt strings are intentionally long

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

import anthropic
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env", override=True)
SPIKE_DIR = _ROOT / "data" / "pipeline" / "spike"

DEFAULT_MODEL = "claude-haiku-4-5-20251001"

# ── Extraction prompts per entity type ──────────────────────────────────────

BULLET_SCHEMA = """\
Extract ALL bullet products from this page. For each bullet, extract:

{
  "name": {"value": "string — full product name", "source_text": "exact text from page", "confidence": 0.0-1.0},
  "manufacturer": {"value": "string — company name", "source_text": "...", "confidence": ...},
  "caliber": {"value": "string — e.g. '6.5 Creedmoor', '.308 Winchester'", "source_text": "...", "confidence": ...},
  "weight_grains": {"value": number, "source_text": "...", "confidence": ...},
  "bc_g1": {"value": number or null, "source_text": "...", "confidence": ...},
  "bc_g7": {"value": number or null, "source_text": "...", "confidence": ...},
  "length_inches": {"value": number or null, "source_text": "...", "confidence": ...},
  "sectional_density": {"value": number or null, "source_text": "...", "confidence": ...},
  "base_type": {"value": "one of: boat_tail, flat_base, rebated_boat_tail, hybrid — or null", "source_text": "...", "confidence": ...},
  "tip_type": {"value": "one of: polymer_tip, hollow_point, open_tip_match, fmj, soft_point, ballistic_tip, meplat — or null", "source_text": "...", "confidence": ...},
  "type_tags": {"value": ["list of: match, hunting, target, varmint, long_range, tactical, plinking"], "source_text": "...", "confidence": ...},
  "used_for": {"value": ["list of: competition, hunting_deer, hunting_elk, hunting_varmint, long_range, precision, self_defense, plinking"], "source_text": "...", "confidence": ...},
  "sku": {"value": "string or null — manufacturer part number", "source_text": "...", "confidence": ...}
}

Return a JSON array of extracted bullets. If a field is not found on the page, set value to null with confidence 0.0.
"""

CARTRIDGE_SCHEMA = """\
Extract ALL factory-loaded cartridge/ammunition products from this page. For each cartridge, extract:

{
  "name": {"value": "string — full product name", "source_text": "...", "confidence": ...},
  "manufacturer": {"value": "string", "source_text": "...", "confidence": ...},
  "caliber": {"value": "string — e.g. '6.5 Creedmoor'", "source_text": "...", "confidence": ...},
  "bullet_name": {"value": "string — name of the bullet used", "source_text": "...", "confidence": ...},
  "bullet_weight_grains": {"value": number, "source_text": "...", "confidence": ...},
  "muzzle_velocity_fps": {"value": integer, "source_text": "...", "confidence": ...},
  "test_barrel_length_inches": {"value": number or null, "source_text": "...", "confidence": ...},
  "round_count": {"value": integer or null — rounds per box, "source_text": "...", "confidence": ...},
  "product_line": {"value": "string or null — e.g. 'Precision Hunter', 'Match'", "source_text": "...", "confidence": ...},
  "sku": {"value": "string or null", "source_text": "...", "confidence": ...}
}

Return a JSON array of extracted cartridges. If a field is not found on the page, set value to null with confidence 0.0.
"""

RIFLE_SCHEMA = """\
Extract ALL rifle model products from this page. For each rifle, extract:

{
  "model": {"value": "string — model name", "source_text": "...", "confidence": ...},
  "manufacturer": {"value": "string", "source_text": "...", "confidence": ...},
  "caliber": {"value": "string — chambered caliber", "source_text": "...", "confidence": ...},
  "barrel_length_inches": {"value": number or null, "source_text": "...", "confidence": ...},
  "twist_rate": {"value": "string or null — e.g. '1:8'", "source_text": "...", "confidence": ...},
  "weight_lbs": {"value": number or null, "source_text": "...", "confidence": ...},
  "barrel_material": {"value": "string or null — e.g. 'stainless steel', 'carbon fiber'", "source_text": "...", "confidence": ...},
  "barrel_finish": {"value": "string or null", "source_text": "...", "confidence": ...},
  "model_family": {"value": "string or null — e.g. 'Tikka T3x', 'Ruger Precision'", "source_text": "...", "confidence": ...}
}

Return a JSON array of extracted rifle models. If a field is not found on the page, set value to null with confidence 0.0.
"""

SCHEMAS = {
    "bullet": BULLET_SCHEMA,
    "cartridge": CARTRIDGE_SCHEMA,
    "rifle": RIFLE_SCHEMA,
}

SYSTEM_PROMPT = """\
You are a firearms and ammunition data extraction specialist. Your job is to extract \
structured product data from manufacturer web pages.

Rules:
1. ONLY extract data that is explicitly present on the page. Never guess or infer values.
2. For every extracted field, include "source_text" — the exact snippet from the HTML that supports this value.
3. Set "confidence" between 0.0 and 1.0: 1.0 = explicitly stated, 0.7-0.9 = clearly implied, below 0.7 = uncertain.
4. If a value is not on the page, set it to null with confidence 0.0 and source_text "".
5. Numeric validation ranges:
   - BC (G1/G7): 0.05 to 1.2
   - Muzzle velocity: 400 to 4000 fps
   - Bullet weight: 15 to 750 grains
   - Barrel length: 10 to 34 inches
   - Sectional density: 0.05 to 0.500
   Flag any values outside these ranges by setting confidence to 0.3 or lower.
6. Return valid JSON only — no markdown fencing, no commentary outside the JSON.
"""

# ── Validation ──────────────────────────────────────────────────────────────

RANGES = {
    "bc_g1": (0.05, 1.2),
    "bc_g7": (0.05, 1.2),
    "weight_grains": (15, 750),
    "bullet_weight_grains": (15, 750),
    "muzzle_velocity_fps": (400, 4000),
    "barrel_length_inches": (10, 34),
    "test_barrel_length_inches": (10, 34),
    "sectional_density": (0.05, 0.500),
    "length_inches": (0.2, 3.0),
    "weight_lbs": (2, 20),
}


def validate_ranges(entities: list[dict]) -> list[str]:
    """Check extracted numeric values against known ranges. Returns list of warnings."""
    warnings = []
    for i, entity in enumerate(entities):
        for field, (lo, hi) in RANGES.items():
            if field not in entity:
                continue
            extracted = entity[field]
            val = extracted.get("value") if isinstance(extracted, dict) else extracted
            if val is None:
                continue
            try:
                num = float(val)
            except (ValueError, TypeError):
                continue
            if num < lo or num > hi:
                name = entity.get("name", {})
                name_val = name.get("value", f"entity[{i}]") if isinstance(name, dict) else name
                warnings.append(f"  {name_val}: {field}={num} outside range [{lo}, {hi}]")
    return warnings


def main() -> None:  # noqa: C901
    parser = argparse.ArgumentParser(description="Spike: LLM extraction from reduced HTML")
    parser.add_argument(
        "--entity-type", required=True, choices=["bullet", "cartridge", "rifle"], help="Type of entity to extract"
    )
    parser.add_argument("-i", "--input", type=Path, default=SPIKE_DIR / "reduced.html", help="Input reduced HTML path")
    parser.add_argument("-o", "--output", type=Path, default=SPIKE_DIR / "extracted.json", help="Output JSON path")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Claude model to use (default: {DEFAULT_MODEL})")
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"Input not found: {args.input}\nRun spike_reduce.py first.")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("ANTHROPIC_API_KEY not set. Export it or add to .env")

    reduced_html = args.input.read_text(encoding="utf-8")
    schema = SCHEMAS[args.entity_type]

    print(f"Entity type: {args.entity_type}")
    print(f"Model:       {args.model}")
    print(f"Input:       {args.input} ({len(reduced_html):,} chars)")
    print()

    client = anthropic.Anthropic(api_key=api_key)

    user_prompt = f"{schema}\n\nHere is the HTML content to extract from:\n\n{reduced_html}"

    print("Sending to Claude...")
    response = client.messages.create(
        model=args.model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw_text = response.content[0].text
    print(f"Response: {len(raw_text):,} chars")
    print(f"Usage: {response.usage.input_tokens:,} input, {response.usage.output_tokens:,} output tokens")
    print()

    # Parse JSON
    try:
        entities = json.loads(raw_text)
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        print("Raw response:")
        print(raw_text[:2000])
        # Try to extract JSON from markdown code block
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw_text)
        if match:
            print("\nFound JSON in code block, retrying...")
            entities = json.loads(match.group(1))
        else:
            raise SystemExit("Could not parse response as JSON") from None

    if not isinstance(entities, list):
        entities = [entities]

    print(f"Extracted {len(entities)} {args.entity_type}(s)")
    print()

    # Validate ranges
    warnings = validate_ranges(entities)
    if warnings:
        print("Range warnings:")
        for w in warnings:
            print(w)
        print()

    # Pretty print
    for i, entity in enumerate(entities):
        name = entity.get("name", {})
        name_val = name.get("value", "???") if isinstance(name, dict) else name
        print(f"  [{i+1}] {name_val}")
        for key, val in entity.items():
            if key == "name":
                continue
            if isinstance(val, dict):
                v = val.get("value")
                conf = val.get("confidence", "?")
                src = val.get("source_text", "")
                src_preview = (src[:60] + "...") if len(src) > 60 else src
                if v is not None:
                    print(f"      {key}: {v}  (conf={conf}, src={src_preview!r})")
            else:
                print(f"      {key}: {val}")
        print()

    # Save
    result = {
        "entity_type": args.entity_type,
        "model": args.model,
        "input_file": str(args.input),
        "input_chars": len(reduced_html),
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        },
        "entities": entities,
        "range_warnings": warnings,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved to {args.output}")


if __name__ == "__main__":
    main()
