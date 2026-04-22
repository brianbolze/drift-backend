"""Pipeline configuration: API keys, cache paths, validation ranges, and controlled vocabulary."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (without override so env vars set by tests take precedence)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

# ── API Keys ─────────────────────────────────────────────────────────────────

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")

# ── Models ───────────────────────────────────────────────────────────────────

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
FALLBACK_MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 8192  # Required for multi-variant pages (e.g., Bergara HMR with 7 caliber variants)

# ── Cache Directories ────────────────────────────────────────────────────────

DATA_DIR = _PROJECT_ROOT / "data" / "pipeline"
SPIKE_DIR = DATA_DIR / "spike"
FETCHED_DIR = DATA_DIR / "fetched"
REDUCED_DIR = DATA_DIR / "reduced"
EXTRACTED_DIR = DATA_DIR / "extracted"
REVIEW_DIR = DATA_DIR / "review"
MANIFEST_PATH = DATA_DIR / "url_manifest.json"
STORE_REPORT_PATH = DATA_DIR / "store_report.json"
REJECTED_CALIBERS_PATH = DATA_DIR / "rejected_calibers.json"

# ── Numeric Validation Ranges ────────────────────────────────────────────────
# Values outside these ranges are flagged for review.

VALIDATION_RANGES: dict[str, tuple[float, float]] = {
    "bc_g1": (0.05, 1.2),
    "bc_g7": (0.05, 1.2),
    "bc_value": (0.05, 1.2),
    "bullet_diameter_inches": (0.172, 0.510),
    "weight_grains": (15, 750),
    "bullet_weight_grains": (15, 750),
    "muzzle_velocity_fps": (400, 4000),
    "barrel_length_inches": (10, 34),
    "test_barrel_length_inches": (10, 34),
    "sectional_density": (0.05, 0.500),
    "length_inches": (0.2, 3.0),
    "bullet_length_inches": (0.2, 3.0),
    "weight_lbs": (2, 20),
}

# ── Controlled Vocabulary ────────────────────────────────────────────────────
# From wi2 design proposal addendum section 2.

BULLET_TYPE_TAGS = frozenset(
    {
        "match",
        "hunting",
        "target",
        "varmint",
        "long_range",
        "tactical",
        "plinking",
    }
)

BULLET_USED_FOR = frozenset(
    {
        "competition",
        "hunting_deer",
        "hunting_elk",
        "hunting_varmint",
        "long_range",
        "precision",
        "self_defense",
        "plinking",
    }
)

BULLET_BASE_TYPES = frozenset(
    {
        "boat_tail",
        "flat_base",
        "rebated_boat_tail",
        "hybrid",
    }
)

BULLET_TIP_TYPES = frozenset(
    {
        "polymer_tip",
        "hollow_point",
        "open_tip_match",
        "fmj",
        "soft_point",
        "ballistic_tip",
        "meplat",
    }
)

BC_TYPES = frozenset({"g1", "g7"})

BC_SOURCE_TYPES = frozenset(
    {
        "manufacturer",
        "cartridge_page",
        "applied_ballistics",
        "doppler_radar",
        "independent_test",
        "estimated",
    }
)

# ── Batch Extraction ────────────────────────────────────────────────────────

BATCH_DIR = DATA_DIR / "batches"  # Stores batch metadata (batch_id → item mapping)
BATCH_POLL_INTERVAL_SECONDS = 30  # How often to poll for batch completion
BATCH_MAX_WAIT_SECONDS = 3600  # 1 hour default timeout for batch polling

# ── Sync Extraction Retries ─────────────────────────────────────────────────

SYNC_MAX_RETRIES = 5
SYNC_RETRY_BASE_SECONDS = 2.0  # Exponential backoff: 2s, 4s, 8s, 16s, 32s

# ── Fetching ─────────────────────────────────────────────────────────────────

HTTPX_TIMEOUT_SECONDS = 30.0
HTTPX_CONNECT_TIMEOUT_SECONDS = 10.0
FIRECRAWL_RATE_LIMIT_SECONDS = 1.0  # Default inter-request delay (used for all fetchers, not just Firecrawl)
FIRECRAWL_TIMEOUT_SECONDS = 60.0  # Max time for a single Firecrawl scrape

FETCH_MAX_RETRIES = 3  # Retries on transient errors (TimeoutException, ConnectError)
FETCH_RETRY_BASE_SECONDS = 2.0  # Exponential backoff: 2s, 4s, 8s

HTTPX_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# ── HTML Reduction ───────────────────────────────────────────────────────────

REDUCE_TARGET_SIZE = 30_000  # chars — fits comfortably in LLM context
REDUCE_MIN_SIZE = 6_000  # below this we've over-stripped

# Per-domain reducer strategy override. Domains not listed here use "generic".
DOMAIN_REDUCER_STRATEGY: dict[str, str] = {
    # main_content: extract <main> (or custom selector) + JSON-LD only
    "barnesbullets.com": "main_content",
    "www.nosler.com": "main_content",
    "bergerbullets.com": "main_content",
    "www.swiftbullets.com": "main_content",
    "cuttingedgebullets.com": "main_content",
    "lehighdefense.com": "main_content",
    # jsonld_only: SPA pages where HTML body is useless
    "www.norma-ammunition.com": "jsonld_only",
}

# Per-domain CSS selector for main_content strategy. Defaults to "main" if not listed.
DOMAIN_CONTENT_SELECTORS: dict[str, str] = {
    "cuttingedgebullets.com": "#main",  # Shopify — uses div#main, not <main>
    "lehighdefense.com": "main#maincontent",  # Magento 2
}

# ── Parser-First Extraction ─────────────────────────────────────────────────
# Per-domain deterministic parser override. Domains listed here run through a
# typed parser first; the LLM path is used as a fallback when the parser
# returns None, raises, or produces out-of-range values.

DOMAIN_PARSER: dict[str, str] = {
    "www.hornady.com": "hornady",
}
