"""
Weighted Buy/Accumulate/Hold/Reduce/Sell scoring -- a weighting/aggregation/storage
layer, NOT an autonomous scorer. No pillar score here is ever formula-derived from
raw numbers without a human/AI reading step in between: the caller (Claude, reading
a company's financial_statements, market_data, dividends, and summary) assigns each
available pillar a 1-10 subscore with a cited rationale, then calls save_thesis().
Assigning those subscores is out of this module's scope on purpose -- doing that
mechanically here would silently reintroduce the "no black boxes, cite everything"
violation this whole project has been built to avoid.

Phase 1 has no macro/industry data source (no CBSL/IMF/World Bank/news integration),
so `macro_industry` is always unavailable and its weight is redistributed
proportionally across the other five pillars -- never silently dropped, never
guessed at with a neutral filler score.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

PILLAR_WEIGHTS = {
    "financial_quality": 0.30,
    "growth_outlook": 0.20,
    "valuation": 0.20,
    "business_quality": 0.15,
    "macro_industry": 0.10,
    "governance_risk": 0.05,
}

# Always unavailable in Phase 1 -- no macro/news/consensus-estimate data source exists.
UNAVAILABLE_PILLARS = {"macro_industry"}

# Starting point, not fixed -- flagged for the user to confirm/adjust once real
# theses have been generated and can be sanity-checked against how they read.
TIER_THRESHOLDS = [
    (70, "BUY"),
    (55, "ACCUMULATE"),
    (40, "HOLD"),
    (25, "REDUCE"),
    (0, "SELL"),
]

MIN_PERIODS_FOR_RATING = 2


def renormalized_weights(unavailable: set[str] | None = None) -> dict[str, float]:
    """Redistributes unavailable pillars' weight proportionally across the rest,
    so the weights actually used still sum to 1.0. Never drops a pillar's
    influence silently -- if everything is available, this is a no-op copy of
    PILLAR_WEIGHTS."""
    if unavailable is None:
        unavailable = UNAVAILABLE_PILLARS
    available = {k: w for k, w in PILLAR_WEIGHTS.items() if k not in unavailable}
    total_available_weight = sum(available.values())
    if total_available_weight <= 0:
        return {}
    return {k: w / total_available_weight for k, w in available.items()}


def _tier_for_score(score: float) -> str:
    for threshold, tier in TIER_THRESHOLDS:
        if score >= threshold:
            return tier
    return "SELL"


def compute_composite(pillar_scores: dict[str, float | None], periods_on_file: int) -> dict:
    """pillar_scores: {pillar_name: subscore_1_to_10 | None}. Pillars absent from
    the dict, set to None, or named in UNAVAILABLE_PILLARS are excluded and the
    remaining weights renormalized around them.

    Data gate: if `periods_on_file` (count of financial_statements rows for this
    symbol) is below MIN_PERIODS_FOR_RATING, returns UNRATED regardless of scores
    -- a thesis built on a single data point isn't a trend-aware call, it's a guess
    wearing a score.

    Returns {composite, weights_used, tier, gate_reason}."""
    if periods_on_file < MIN_PERIODS_FOR_RATING:
        return {
            "composite": None,
            "weights_used": {},
            "tier": "UNRATED",
            "gate_reason": (
                f"Only {periods_on_file} period(s) of financial_statements on file "
                f"(need >= {MIN_PERIODS_FOR_RATING}) -- not enough history for a "
                f"trend-aware rating."
            ),
        }

    available_pillars = {
        k: v for k, v in pillar_scores.items()
        if v is not None and k not in UNAVAILABLE_PILLARS and k in PILLAR_WEIGHTS
    }
    if not available_pillars:
        return {
            "composite": None,
            "weights_used": {},
            "tier": "UNRATED",
            "gate_reason": "No pillar scores available to compute a rating from.",
        }

    weights = renormalized_weights(
        unavailable=UNAVAILABLE_PILLARS | (set(PILLAR_WEIGHTS) - set(available_pillars))
    )
    composite_0_10 = sum(available_pillars[k] * weights.get(k, 0) for k in available_pillars)
    composite_0_100 = composite_0_10 * 10

    return {
        "composite": round(composite_0_100, 1),
        "weights_used": weights,
        "tier": _tier_for_score(composite_0_100),
        "gate_reason": None,
    }


def save_thesis(
    conn,
    symbol: str,
    company_name: str,
    pillar_scores: dict[str, float | None],
    periods_on_file: int,
    rationale_by_pillar: dict[str, str],
    citations_by_pillar: dict[str, list[str]],
    thesis_text: str,
    key_reasons: list[str],
    watch_factors: list[str],
    horizon_notes: dict[str, str],
    gaps_note: str,
    source_financials_asof: str | None,
    source_market_data_asof: str | None,
    confidence: float,
) -> dict:
    """Computes the composite/tier via compute_composite() and upserts the `thesis`
    row (one row per symbol, like `summaries`). Returns the computed result dict
    so the caller can print/verify it immediately."""
    result = compute_composite(pillar_scores, periods_on_file)

    pillar_scores_json = json.dumps({
        pillar: {
            "score": pillar_scores.get(pillar),
            "weight_used": result["weights_used"].get(pillar),
            "rationale": rationale_by_pillar.get(pillar, ""),
            "citations": citations_by_pillar.get(pillar, []),
        }
        for pillar in PILLAR_WEIGHTS
    })

    conn.execute(
        """
        INSERT INTO thesis (
            symbol, company_name, generated_at, recommendation, composite_score,
            confidence, pillar_scores_json, weights_used_json, macro_pillar_available,
            key_reasons_json, watch_factors_json, horizon_notes_json, thesis_text,
            gaps_note, source_financials_asof, source_market_data_asof
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol) DO UPDATE SET
            company_name=excluded.company_name, generated_at=excluded.generated_at,
            recommendation=excluded.recommendation, composite_score=excluded.composite_score,
            confidence=excluded.confidence, pillar_scores_json=excluded.pillar_scores_json,
            weights_used_json=excluded.weights_used_json,
            key_reasons_json=excluded.key_reasons_json, watch_factors_json=excluded.watch_factors_json,
            horizon_notes_json=excluded.horizon_notes_json, thesis_text=excluded.thesis_text,
            gaps_note=excluded.gaps_note, source_financials_asof=excluded.source_financials_asof,
            source_market_data_asof=excluded.source_market_data_asof
        """,
        (
            symbol, company_name, datetime.now(timezone.utc).isoformat(), result["tier"],
            result["composite"], confidence, pillar_scores_json,
            json.dumps(result["weights_used"]),
            json.dumps(key_reasons), json.dumps(watch_factors), json.dumps(horizon_notes),
            thesis_text, gaps_note, source_financials_asof, source_market_data_asof,
        ),
    )
    conn.commit()
    return result
