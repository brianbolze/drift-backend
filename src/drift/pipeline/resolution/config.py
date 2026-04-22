"""Resolver calibration constants, consolidated into one dataclass.

Every threshold, tolerance, and confidence scalar the resolver + pipeline store
use to decide match / create / flag actions lives here. Previously these were
scattered as magic numbers across ``resolver.py`` and ``scripts/pipeline_store.py``
with no documented rationale. Consolidating them has three purposes:

1. Makes the calibration surface visible in one place when tuning.
2. Lets the golden-set regression test capture current behavior as a baseline
   (see ``tests/test_resolution_golden_set.py``) so any future retune that
   regresses match accuracy is caught loudly.
3. Allows tests to construct alternate configs without monkeypatching.

Values are the baseline as of step 4 of the entity resolution refactor
(``docs/entity_resolution_review.md``). Do not retune without running the
golden-set test before and after.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResolutionConfig:
    """Tunable knobs for entity resolution.

    Field groups map roughly to: (1) similarity thresholds that decide whether
    a candidate is *considered* at all, (2) confidence-scaling factors that
    convert a similarity score into a reported confidence, (3) fixed confidence
    values for deterministic tiers, (4) numeric tolerances for weight/diameter/BC
    comparisons, (5) ambiguity detection, and (6) pipeline-store-level action gates.
    """

    # ── Similarity thresholds ────────────────────────────────────────────────
    # Minimum token_set_ratio / containment score (0–1) below which a candidate
    # is discarded outright. These should be *conservative* floors: raising them
    # trades recall for precision.

    # Fuzzy fallback when the deterministic manufacturer lookup misses.
    # Manufacturer names are short and stable, so a relatively high floor is
    # safe; typos ("Hornday") still score ~0.8+ on token_set_ratio.
    manufacturer_fuzzy_threshold: float = 0.5

    # Caliber floor is lower because LLM extractions drop the leading period
    # (".308" vs "308") and mix "Winchester" vs "Win", which token_set_ratio
    # handles but only after normalization. Setting this below the manufacturer
    # floor caught a real class of legit variants; raise with care.
    caliber_fuzzy_threshold: float = 0.4

    # Tier 2 (composite key) and Tier 3 (fuzzy name) thresholds for
    # bullet/cartridge. Composite tier already requires weight agreement, so
    # the name floor is slightly higher — we have two signals and want them to
    # agree. Fuzzy tier is the last resort and uses the lower floor.
    composite_name_score_threshold: float = 0.55
    fuzzy_name_threshold: float = 0.5

    # Rifles don't use weight; both tiers gate on name similarity alone.
    rifle_composite_name_threshold: float = 0.5
    rifle_fuzzy_name_threshold: float = 0.5

    # ── Confidence scaling factors ───────────────────────────────────────────
    # How a raw similarity score maps to reported match confidence. Keeping
    # fuzzy-tier ceilings *below* deterministic tiers is intentional: a Jaccard
    # ~1.0 on a fuzzy tier should still score lower than any exact/alias hit.

    # Fuzzy manufacturer: score * 0.9 — cap at 0.9 confidence even for a
    # perfect fuzzy match, because the deterministic EntityAlias path is
    # preferred and should always win when present.
    manufacturer_fuzzy_confidence_scale: float = 0.9

    # Fuzzy caliber: score * 0.85 — slightly lower than manufacturer because
    # caliber names are harder to disambiguate (6.5 Creedmoor vs 6.5 PRC share
    # 2/3 tokens).
    caliber_fuzzy_confidence_scale: float = 0.85

    # Composite key: base + score * weight. With score_weight=0.1, a perfect
    # name_score=1.0 yields 0.95 confidence; the 0.55 floor yields 0.905.
    # The 0.85 base reflects that two agreeing signals (weight + name) are
    # already strong evidence.
    composite_confidence_base: float = 0.85
    composite_confidence_score_weight: float = 0.1

    # Fuzzy tier (bullet/cartridge): weight-agreement is a hard signal, so
    # agreeing weights lift the confidence (0.8 × score) and disagreeing weights
    # cap it aggressively (0.4 × score). A 1.0-similarity fuzzy match with
    # disagreeing weight tops out at 0.4 — below the store's match threshold
    # of 0.7, forcing a flag rather than a silent auto-match.
    fuzzy_weight_agrees_factor: float = 0.8
    fuzzy_weight_mismatch_factor: float = 0.4

    # Rifle fuzzy: same logic as bullet/cartridge but gated on chamber_id
    # agreement instead of weight.
    rifle_fuzzy_chamber_agrees_factor: float = 0.8
    rifle_fuzzy_chamber_mismatch_factor: float = 0.4

    # ── Fixed confidence values ──────────────────────────────────────────────
    # Confidences for deterministic tiers where similarity isn't used.

    # Product-line tier (resolver.match_bullet). Product line + weight +
    # diameter is three signals agreeing → 0.93. Without weight, we don't have
    # evidence to distinguish weight variants of the same product line, so
    # confidence drops to 0.80 — below store match threshold if weight is
    # missing but above flag-for-review threshold.
    product_line_with_weight_confidence: float = 0.93
    product_line_no_weight_confidence: float = 0.80

    # Caliber→chamber resolution for rifles. Primary chamber is the
    # canonically-correct match (.223 Rem → .223 Rem chamber); non-primary is
    # a compatibility match (.223 Rem → .223 Wylde). Both are legitimate but
    # we prefer the primary when present.
    chamber_primary_confidence: float = 0.9
    chamber_secondary_confidence: float = 0.7

    # ── Weight tolerances (grains) ───────────────────────────────────────────
    # Tolerance controls how forgiving we are of float-precision mismatches and
    # manufacturer spec rounding. Match tolerances must be tight; auto-create
    # and hard-reject gates can be looser.

    # Composite-key + product-line tier + BC-boost weight agreement tolerance.
    # 0.5gr comfortably absorbs "0.499" vs "0.500" float noise while rejecting
    # the common failure mode of confusing 140gr vs 147gr.
    composite_weight_tolerance_grains: float = 0.5

    # Fuzzy tier weight agreement tolerance — looser than composite because the
    # fuzzy tier already has name evidence and we only use weight as a
    # confidence scalar, not a hard filter.
    fuzzy_weight_tolerance_grains: float = 1.0

    # Hard reject gate for cartridge→bullet FK assignment. Beyond this, the
    # match is treated as no-match and the cartridge gets no bullet_id.
    # 5gr lets same-product-line different-weight misses (178gr ELD-X fuzzy-
    # matching 175gr ELD-X) through but catches dramatic cross-weight linkages
    # (a 200gr extraction matched against a 110gr bullet).
    bullet_weight_gate_grains: float = 5.0

    # Auto-create tolerances for "low-confidence match but weight-mismatched"
    # scenarios — tighter than bullet_weight_gate because we want to create
    # new weight variants even for small disagreements. Bullet variants are
    # typically 1gr apart at the extremes; cartridge SKUs more often round to
    # the nearest 5gr so we allow 2gr before forcing a new record.
    auto_create_bullet_weight_tolerance_grains: float = 1.0
    auto_create_cartridge_weight_tolerance_grains: float = 2.0

    # ── Diameter tolerance (inches) ──────────────────────────────────────────
    # Bullet diameters are measured to 3 decimal places by manufacturers, but
    # the same physical diameter can appear as 0.264 vs 0.2645 vs 0.2638
    # across sources. ±0.001" is tight enough to distinguish .264/6.5mm from
    # .277/.270 Win while absorbing measurement noise.
    bullet_diameter_tolerance_inches: float = 0.001

    # ── BC tolerance and boost ───────────────────────────────────────────────
    # BC values are published to 3 decimal places, so rounding differences
    # (0.3255 shown as 0.326 by one source and 0.325 by another) need to be
    # absorbed. ±5e-4 covers max rounding error at 3dp.
    bc_tolerance: float = 5e-4

    # Additive confidence boost applied once per matching signal (weight, BC G1,
    # BC G7) when a matched cartridge's published values agree with its linked
    # bullet. 3 × 0.05 = max +0.15 boost, which can push a composite-key match
    # from 0.85 to 1.0.
    bc_weight_boost_per_signal: float = 0.05

    # ── Ambiguity detection ──────────────────────────────────────────────────
    # ``MatchResult.is_ambiguous`` reports when the top match is close to the
    # runner-up. Currently informational only (not yet gating behavior — see
    # finding #5), but the thresholds belong here for consistency.

    # Above this confidence, don't bother flagging ambiguity — a 0.98 match
    # with a 0.85 runner-up is still a clean win.
    ambiguity_skip_above_confidence: float = 0.97

    # Minimum confidence gap between top match and runner-up. Below this, the
    # match is flagged ambiguous in diagnostics.
    ambiguity_gap_threshold: float = 0.2

    # ── Cartridge→bullet linkage ─────────────────────────────────────────────
    # Bullet FK assignment floor for cartridges. A bullet match below this is
    # not linked — the cartridge ships with bullet_id=None and the bullet
    # lookup is added to unresolved_refs for later review.
    bullet_fk_min_confidence: float = 0.5

    # Relaxed-diameter fallback: when the primary diameter-filtered match
    # returns nothing or gets weight-gated, retry the bullet lookup without
    # the diameter filter. Recovers the "wrong caliber resolved → wrong
    # diameter → no bullet at that diameter" failure mode (e.g. 30-378 Wby
    # Mag fuzzy-matched to .338-378 Wby Mag in the caliber table, so the
    # bullet search filtered to .338 and missed the actual .308 bullet).
    # Accepted only when the fallback's weight exactly matches the cartridge
    # (±1 gr) and raw name similarity (extracted vs matched bullet name)
    # meets ``fallback_min_raw_name_similarity``. The older
    # ``fallback_min_name_confidence`` gated on the composite-inflated
    # ``MatchResult.confidence``, which is ≥0.85 for any composite_key hit
    # regardless of name quality — so it was effectively a no-op and let
    # cross-caliber bullets through (see v6 regression, 2026-04-22).
    enable_relaxed_diameter_fallback: bool = True
    fallback_weight_tolerance_grains: float = 1.0
    fallback_min_name_confidence: float = 0.85
    fallback_min_raw_name_similarity: float = 0.9
    # Confidence penalty applied to a relaxed-diameter match (multiplicative).
    fallback_confidence_penalty: float = 0.9

    # Cartridge→bullet two-pass resolution: first try restricting the bullet
    # candidate pool to the cartridge's own manufacturer. If that narrow search
    # returns a match with confidence ≥ this threshold, accept it. Only fall
    # back to the cross-brand search (manufacturer_id=None, needed for
    # factory-loaded component bullets like Federal Gold Medal carrying a
    # Sierra MatchKing) when the narrow search misses. This breaks ties that
    # previously went to whichever bullet happened to come first in the
    # candidate list — e.g. Hornady BLACK 105gr BTHP vs Sierra SMK 105gr both
    # scored composite_key=0.95 and SMK won by iteration order. Threshold is
    # set just below the 0.93 product_line + weight ceiling so that a
    # product_line-tier hit by the cartridge's own manufacturer is enough to
    # skip the fallback, but a weak fuzzy-tier same-brand hit is not.
    enable_cart_bullet_mfr_preference: bool = True
    cart_bullet_mfr_preferred_min_confidence: float = 0.9

    # ── Pipeline store action gates ──────────────────────────────────────────
    # These drive the store script's create / match / flag decision. Separated
    # from resolver-internal confidence scalars because the store is the
    # policy layer (what do we *do* with a match of confidence X) while the
    # resolver is the measurement layer (what confidence *is* X).

    # Minimum match confidence for auto-match action. Below this the entry
    # goes to flagged_low_confidence for manual review.
    match_confidence_threshold: float = 0.7

    # Below this confidence, a weight-mismatched fuzzy match is treated as
    # no-match and the entity is auto-created instead of flagged. Handles the
    # common case where a new weight variant fuzzy-matches to an existing
    # variant because the correct record doesn't exist yet.
    auto_create_confidence_ceiling: float = 0.5

    # Matches below this confidence are reported as "low confidence" in the
    # end-of-run method breakdown. Independent of match_confidence_threshold
    # so the reporting threshold can move without affecting gating behavior.
    low_confidence_report_threshold: float = 0.5

    # Gate for auto-promoting a fuzzy-tier EntityAlias suggestion directly into
    # the DB on pipeline-store-commit. When a fuzzy win has confidence strictly
    # above this AND is not ambiguous (runner-up gap ≥ ambiguity_gap_threshold),
    # the store inserts the alias row itself rather than emitting a suggestion
    # for a human-authored curation patch.
    #
    # 0.85 is set above the product-line-no-weight confidence (0.80) so that
    # only matches with at least two agreeing signals (weight + name, or a BC
    # boost on top of a composite hit) can auto-promote — the goal is to pick
    # off the obvious wins, not to expand the gate silently. Ambiguous matches
    # are excluded regardless of confidence because a tight runner-up means the
    # alias would teach the resolver a mapping we aren't sure of.
    alias_auto_promote_threshold: float = 0.85


# Module-level singleton used by the resolver and pipeline store. Tests or
# calibration harnesses can construct alternate configs and pass them through
# ``EntityResolver(session, config=...)``.
DEFAULT_CONFIG = ResolutionConfig()
