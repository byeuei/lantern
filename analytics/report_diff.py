"""
Compares the two most recent `financial_statements` periods for a symbol and
surfaces the most significant changes -- raw line items plus computed ratios, so
a margin/leverage shift surfaces even when no single raw line moved dramatically.
"""
from __future__ import annotations

from datetime import date

from analytics.metrics import fundamental_ratios

RAW_FIELDS = [
    ("revenue", "Revenue"),
    ("cost_of_sales", "Cost of Sales"),
    ("gross_profit", "Gross Profit"),
    ("operating_profit", "Operating Profit"),
    ("finance_costs", "Finance Costs"),
    ("profit_before_tax", "Profit Before Tax"),
    ("tax_expense", "Tax Expense"),
    ("profit_after_tax", "Profit After Tax"),
    ("eps_basic", "EPS (Basic)"),
    ("total_assets", "Total Assets"),
    ("current_assets", "Current Assets"),
    ("inventory", "Inventory"),
    ("trade_receivables", "Trade Receivables"),
    ("cash_and_equivalents", "Cash & Equivalents"),
    ("total_liabilities", "Total Liabilities"),
    ("current_liabilities", "Current Liabilities"),
    ("short_term_borrowings", "Short-Term Borrowings"),
    ("long_term_borrowings", "Long-Term Borrowings"),
    ("total_equity", "Total Equity"),
    ("cash_from_operations", "Cash From Operations"),
    ("capex", "Capex"),
]

RATIO_FIELDS = [
    ("gross_margin", "Gross Margin"),
    ("operating_margin", "Operating Margin"),
    ("net_margin", "Net Margin"),
    ("ebitda_margin", "EBITDA Margin"),
    ("roe", "ROE"),
    ("roa", "ROA"),
    ("current_ratio", "Current Ratio"),
    ("debt_to_equity", "Debt / Equity"),
    ("net_debt_to_ebitda", "Net Debt / EBITDA"),
    ("interest_coverage", "Interest Coverage"),
    ("free_cash_flow", "Free Cash Flow"),
]


def _pct_change(prior, new):
    if prior is None or new is None:
        return None
    if prior == 0:
        return None  # undefined; caller treats this as "newly meaningful" not a %
    return (new - prior) / abs(prior)


def _diff_rows(new_row: dict, prior_row: dict, limit: int) -> list[dict]:
    """Core diffing logic shared by diff_periods (QoQ) and diff_yoy: raw line items
    plus computed ratios, ranked by abs(pct_change) descending."""
    new_ratios = fundamental_ratios(new_row)
    prior_ratios = fundamental_ratios(prior_row)

    changes = []
    for field, label in RAW_FIELDS:
        prior_val, new_val = prior_row.get(field), new_row.get(field)
        if prior_val is None and new_val is None:
            continue
        if prior_val is None or new_val is None:
            changes.append({
                "metric": field, "label": label,
                "prior_period_label": prior_row["period_label"], "prior_value": prior_val,
                "new_period_label": new_row["period_label"], "new_value": new_val,
                "pct_change": None,
                "direction": "newly_disclosed" if prior_val is None else "no_longer_disclosed",
            })
            continue
        pct = _pct_change(prior_val, new_val)
        changes.append({
            "metric": field, "label": label,
            "prior_period_label": prior_row["period_label"], "prior_value": prior_val,
            "new_period_label": new_row["period_label"], "new_value": new_val,
            "pct_change": pct,
            "direction": "improved" if (new_val > prior_val) else ("deteriorated" if new_val < prior_val else "unchanged"),
        })

    for field, label in RATIO_FIELDS:
        prior_val, new_val = prior_ratios.get(field), new_ratios.get(field)
        if prior_val is None or new_val is None:
            continue
        pct = _pct_change(prior_val, new_val)
        changes.append({
            "metric": field, "label": label,
            "prior_period_label": prior_row["period_label"], "prior_value": prior_val,
            "new_period_label": new_row["period_label"], "new_value": new_val,
            "pct_change": pct,
            "direction": "improved" if (new_val > prior_val) else ("deteriorated" if new_val < prior_val else "unchanged"),
        })

    ranked = sorted(
        changes,
        key=lambda c: (c["pct_change"] is None, -(abs(c["pct_change"]) if c["pct_change"] is not None else 0)),
    )
    return ranked[:limit]


def diff_periods(conn, symbol: str, period_type: str = "ANNUAL", basis: str = "GROUP", limit: int = 20) -> list[dict]:
    """QoQ/period-over-period: returns up to `limit` of the most significant changes
    between the two most recent financial_statements rows for (symbol, period_type,
    basis), ranked by abs(pct_change) descending. Falls back to the other basis if
    the requested one has fewer than 2 periods on file. Returns [] if fewer than 2
    periods exist for either basis."""
    rows = conn.execute(
        """
        SELECT * FROM financial_statements
        WHERE symbol = ? AND period_type = ? AND basis = ?
        ORDER BY period_end_date DESC LIMIT 2
        """,
        (symbol, period_type, basis),
    ).fetchall()

    if len(rows) < 2:
        other_basis = "COMPANY" if basis == "GROUP" else "GROUP"
        rows = conn.execute(
            """
            SELECT * FROM financial_statements
            WHERE symbol = ? AND period_type = ? AND basis = ?
            ORDER BY period_end_date DESC LIMIT 2
            """,
            (symbol, period_type, other_basis),
        ).fetchall()

    if len(rows) < 2:
        return []

    return _diff_rows(dict(rows[0]), dict(rows[1]), limit)


def diff_yoy(conn, symbol: str, period_type: str = "INTERIM", basis: str = "GROUP", limit: int = 20) -> list[dict]:
    """Year-over-year: compares the newest period against whichever earlier period's
    period_end_date is closest to exactly 1 year before it (skipping over any
    intervening periods, e.g. the immediately preceding quarter) -- distinct from
    diff_periods, which always compares the two most recent periods regardless of
    gap. Returns [] if fewer than 2 periods exist, or if no period from
    roughly a year earlier (300-430 days back) is on file."""
    rows = conn.execute(
        """
        SELECT * FROM financial_statements
        WHERE symbol = ? AND period_type = ? AND basis = ?
        ORDER BY period_end_date DESC
        """,
        (symbol, period_type, basis),
    ).fetchall()

    if len(rows) < 2:
        other_basis = "COMPANY" if basis == "GROUP" else "GROUP"
        rows = conn.execute(
            """
            SELECT * FROM financial_statements
            WHERE symbol = ? AND period_type = ? AND basis = ?
            ORDER BY period_end_date DESC
            """,
            (symbol, period_type, other_basis),
        ).fetchall()

    if len(rows) < 2:
        return []

    rows = [dict(r) for r in rows]
    newest = rows[0]
    newest_date = date.fromisoformat(newest["period_end_date"])

    best_match = None
    best_diff_days = None
    for candidate in rows[1:]:
        candidate_date = date.fromisoformat(candidate["period_end_date"])
        diff_days = abs((newest_date - candidate_date).days - 365)
        if diff_days <= 65 and (best_diff_days is None or diff_days < best_diff_days):
            best_match = candidate
            best_diff_days = diff_days

    if best_match is None:
        return []

    return _diff_rows(newest, best_match, limit)
